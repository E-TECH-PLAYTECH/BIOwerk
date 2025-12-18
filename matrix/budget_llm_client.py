"""
Budget-aware LLM client wrapper with cost tracking and enforcement.

This module provides an enterprise-grade wrapper around the base LLM client
that adds:
- Budget checking before requests
- Automatic model fallback when approaching limits
- Cost and token usage tracking
- Alert generation for budget violations
- Integration with Prometheus metrics
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from matrix.llm_client import LLMClient
from matrix.cost_tracker import CostTracker, LLMPricing
from matrix.budget_enforcement import BudgetEnforcer, BudgetExceededError
from matrix.cost_alerts import AlertManager
from matrix.database import get_db_session
from matrix import budget_metrics
from matrix.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMInvocationResult:
    """Represents a single LLM invocation outcome for tracking and metrics."""

    response: str
    provider: str
    model: str
    duration_ms: float
    input_tokens: int
    output_tokens: int
    fallback_used: bool = False
    original_provider: Optional[str] = None
    original_model: Optional[str] = None
    fallback_reason: Optional[str] = None


class BudgetAwareLLMClient:
    """
    Enterprise LLM client with budget enforcement and cost tracking.

    Wraps the base LLMClient and adds:
    - Pre-request budget validation
    - Automatic model fallback
    - Post-request cost tracking
    - Alert generation
    - Prometheus metrics
    """

    def __init__(
        self,
        db_session: AsyncSession,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        service_name: Optional[str] = None
    ):
        """
        Initialize budget-aware LLM client.

        Args:
            db_session: Database session for cost tracking
            user_id: User ID for budget enforcement
            project_id: Project ID for budget tracking
            service_name: Service name (osteon, myocyte, etc.)
        """
        self.llm_client = LLMClient()
        self.db = db_session
        self.user_id = user_id
        self.project_id = project_id
        self.service_name = service_name

        # Initialize services
        self.cost_tracker = CostTracker(db_session)
        self.budget_enforcer = BudgetEnforcer(db_session)
        self.alert_manager = AlertManager(db_session)
        self.pricing = LLMPricing()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        json_mode: bool = False,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        bypass_budget: bool = False
    ) -> str:
        """
        Generate chat completion with budget enforcement and cost tracking.

        Args:
            messages: List of message dicts
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            provider: LLM provider (optional override)
            model: Model name (optional override)
            json_mode: Enable JSON response mode
            endpoint: API endpoint being called
            request_id: Request correlation ID
            trace_id: Distributed tracing ID
            execution_id: Execution record ID
            bypass_budget: Skip budget enforcement (admin override)

        Returns:
            Generated text response

        Raises:
            BudgetExceededError: If budget hard limit is exceeded and blocking is enabled
        """
        provider = provider or self.llm_client.provider
        model = model or self._get_default_model(provider)
        estimated_input_tokens = self._estimate_tokens(messages, system_prompt)
        estimated_output_tokens = max_tokens or 1000

        try:
            result = await self._perform_request(
                provider=provider,
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                bypass_budget=bypass_budget,
            )
            return result.response

        except BudgetExceededError:
            raise
        except Exception as primary_error:
            fallback_result = await self._attempt_default_fallback(
                error=primary_error,
                provider=provider,
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                bypass_budget=bypass_budget,
            )

            if fallback_result:
                return fallback_result.response

            raise

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider."""
        if provider == "openai":
            return settings.openai_model
        elif provider == "anthropic":
            return settings.anthropic_model
        elif provider == "deepseek":
            return settings.deepseek_model
        elif provider == "ollama":
            return settings.ollama_model
        elif provider == "local":
            return settings.local_model_name
        return "unknown"

    def _estimate_tokens(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> int:
        """
        Estimate token count for messages.

        Uses a simple heuristic: ~4 characters per token.
        For production, use tiktoken or similar.
        """
        total_chars = 0

        if system_prompt:
            total_chars += len(system_prompt)

        for msg in messages:
            total_chars += len(msg.get("content", ""))

        # Rough estimate: 4 chars per token
        estimated_tokens = total_chars // 4

        return max(estimated_tokens, 1)

    async def _perform_request(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
        endpoint: Optional[str],
        request_id: Optional[str],
        trace_id: Optional[str],
        execution_id: Optional[str],
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        bypass_budget: bool,
        fallback_reason: Optional[str] = None,
        original_provider: Optional[str] = None,
        original_model: Optional[str] = None,
    ) -> LLMInvocationResult:
        """Execute a single LLM request with budget enforcement and tracking."""

        start_time = time.time()
        active_provider = provider
        active_model = model
        fallback_used = False
        budget_check_result = None

        try:
            if not bypass_budget:
                budget_check_result = await self.budget_enforcer.check_budget(
                    provider=provider,
                    model=model,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                    user_id=self.user_id,
                    project_id=self.project_id,
                    service_name=self.service_name,
                )

                for warning in budget_check_result.get("warnings", []):
                    logger.warning(
                        "Budget warning",
                        extra={"warning": warning, "provider": provider, "model": model, "user_id": self.user_id, "project_id": self.project_id},
                    )

                if not budget_check_result["allowed"]:
                    error_msg = "Budget limit exceeded: " + "; ".join(budget_check_result["warnings"])
                    logger.error(error_msg)

                    await self.cost_tracker.record_usage(
                        provider=provider,
                        model=model,
                        input_tokens=0,
                        output_tokens=0,
                        user_id=self.user_id,
                        project_id=self.project_id,
                        service_name=self.service_name,
                        endpoint=endpoint,
                        request_id=request_id,
                        trace_id=trace_id,
                        execution_id=execution_id,
                        success=False,
                        error_message=error_msg,
                    )

                    if budget_check_result.get("budgets"):
                        most_restrictive = max(
                            budget_check_result["budgets"],
                            key=lambda b: b["current_percentage"],
                        )
                        budget_id = most_restrictive["budget_id"]

                        from matrix.db_models import BudgetConfig
                        from sqlalchemy import select

                        budget_query = select(BudgetConfig).where(BudgetConfig.id == budget_id)
                        budget_result = await self.db.execute(budget_query)
                        budget = budget_result.scalar_one_or_none()

                        if budget:
                            await self.alert_manager.create_budget_alert(
                                alert_type="exceeded",
                                budget=budget,
                                current_usage=most_restrictive["current_usage"],
                                usage_percentage=most_restrictive["current_percentage"],
                                threshold_exceeded="hard_limit",
                                action_taken="blocked",
                                request_blocked=True,
                            )

                    await self.db.commit()

                    raise BudgetExceededError(error_msg, budget=None, current_usage=0)

                if budget_check_result["fallback_required"]:
                    fallback_used = True
                    active_provider = budget_check_result["fallback_provider"]
                    active_model = budget_check_result["fallback_model"] or self._get_default_model(active_provider)
                    original_provider = original_provider or provider
                    original_model = original_model or model
                    fallback_reason = fallback_reason or "budget"

                    logger.info(
                        "Using budget-directed fallback",
                        extra={
                            "provider": active_provider,
                            "model": active_model,
                            "original_provider": provider,
                            "original_model": model,
                        },
                    )

            logger.info(
                "Dispatching LLM request",
                extra={
                    "provider": active_provider,
                    "model": active_model,
                    "user_id": self.user_id,
                    "project_id": self.project_id,
                    "service_name": self.service_name,
                },
            )

            response = await self.llm_client.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                provider=active_provider,
                model=active_model,
                json_mode=json_mode,
            )

            actual_input_tokens, actual_output_tokens = await self._extract_token_usage(
                active_provider, active_model, messages, system_prompt, response
            )

            duration_ms = (time.time() - start_time) * 1000

            budget_id = None
            if budget_check_result and budget_check_result.get("budgets"):
                budget_id = budget_check_result["budgets"][0]["budget_id"]

            usage_record = await self.cost_tracker.record_usage(
                provider=active_provider,
                model=active_model,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                user_id=self.user_id,
                project_id=self.project_id,
                service_name=self.service_name,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
                duration_ms=duration_ms,
                success=True,
                budget_id=budget_id,
                fallback_used=fallback_used or bool(fallback_reason),
                original_provider=original_provider if (fallback_used or fallback_reason) else None,
                original_model=original_model if (fallback_used or fallback_reason) else None,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens_requested=max_tokens,
            )

            budget_metrics.record_request_duration(
                provider=active_provider,
                model=active_model,
                duration_seconds=duration_ms / 1000,
                service=self.service_name,
            )

            if fallback_used or fallback_reason:
                budget_metrics.record_fallback_event(
                    original_provider=original_provider or provider,
                    original_model=original_model or model,
                    fallback_provider=active_provider,
                    fallback_model=active_model,
                    reason=fallback_reason or "budget",
                )

            if budget_check_result and budget_check_result.get("budgets"):
                for budget_info in budget_check_result["budgets"]:
                    from matrix.db_models import BudgetConfig
                    from sqlalchemy import select

                    budget_query = select(BudgetConfig).where(BudgetConfig.id == budget_info["budget_id"])
                    budget_result = await self.db.execute(budget_query)
                    budget = budget_result.scalar_one_or_none()

                    if budget:
                        await self.budget_enforcer.update_budget_usage(budget)
                        await self.alert_manager.check_budget_thresholds(budget)

            await self.alert_manager.check_cost_spikes(
                user_id=self.user_id,
                project_id=self.project_id,
            )

            await self.db.commit()

            logger.info(
                "LLM request completed",
                extra={
                    "provider": active_provider,
                    "model": active_model,
                    "duration_ms": duration_ms,
                    "tokens": actual_input_tokens + actual_output_tokens,
                    "cost": usage_record.total_cost,
                    "fallback_used": fallback_used or bool(fallback_reason),
                    "original_provider": original_provider,
                    "original_model": original_model,
                    "fallback_reason": fallback_reason or ("budget" if fallback_used else None),
                },
            )

            return LLMInvocationResult(
                response=response,
                provider=active_provider,
                model=active_model,
                duration_ms=duration_ms,
                input_tokens=actual_input_tokens,
                output_tokens=actual_output_tokens,
                fallback_used=fallback_used or bool(fallback_reason),
                original_provider=original_provider,
                original_model=original_model,
                fallback_reason=fallback_reason or ("budget" if fallback_used else None),
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await self._record_failure(
                provider=active_provider,
                model=active_model,
                duration_ms=duration_ms,
                error=e,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
            )
            raise

    async def _record_failure(
        self,
        provider: str,
        model: str,
        duration_ms: float,
        error: Exception,
        endpoint: Optional[str],
        request_id: Optional[str],
        trace_id: Optional[str],
        execution_id: Optional[str],
    ) -> None:
        """Record failed invocation telemetry and cost tracking."""
        logger.error(
            "LLM request failed",
            exc_info=True,
            extra={
                "provider": provider,
                "model": model,
                "duration_ms": duration_ms,
                "error": str(error),
            },
        )

        try:
            await self.cost_tracker.record_usage(
                provider=provider,
                model=model,
                input_tokens=0,
                output_tokens=0,
                user_id=self.user_id,
                project_id=self.project_id,
                service_name=self.service_name,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
                duration_ms=duration_ms,
                success=False,
                error_message=str(error),
            )
            await self.db.commit()
        except Exception as tracking_error:
            logger.error(
                "Failed to record error usage",
                exc_info=True,
                extra={"tracking_error": str(tracking_error)},
            )

    async def _attempt_default_fallback(
        self,
        error: Exception,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
        endpoint: Optional[str],
        request_id: Optional[str],
        trace_id: Optional[str],
        execution_id: Optional[str],
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        bypass_budget: bool,
    ) -> Optional[LLMInvocationResult]:
        """Attempt configured fallback provider when primary call fails."""

        fallback_provider = settings.budget_default_fallback_provider
        fallback_model = settings.budget_default_fallback_model

        if not fallback_provider:
            return None

        if fallback_provider == provider and fallback_model == model:
            return None

        logger.warning(
            "Primary provider failed; attempting configured fallback",
            extra={
                "error": str(error),
                "provider": provider,
                "model": model,
                "fallback_provider": fallback_provider,
                "fallback_model": fallback_model,
            },
        )

        fallback_start = time.time()

        try:
            return await self._perform_request(
                provider=fallback_provider,
                model=fallback_model,
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
                bypass_budget=bypass_budget,
                fallback_reason="resilience",
                original_provider=provider,
                original_model=model,
            )
        except Exception as fallback_error:
            duration_ms = (time.time() - fallback_start) * 1000
            await self._record_failure(
                provider=fallback_provider,
                model=fallback_model,
                duration_ms=duration_ms,
                error=fallback_error,
                endpoint=endpoint,
                request_id=request_id,
                trace_id=trace_id,
                execution_id=execution_id,
            )
            return None

    async def _extract_token_usage(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        response: str
    ) -> tuple[int, int]:
        """
        Extract actual token usage from response.

        In production, this should parse the actual usage data from the API response.
        For now, we estimate based on content length.

        Args:
            provider: LLM provider
            model: Model name
            messages: Input messages
            system_prompt: System prompt
            response: Generated response

        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        # Estimate input tokens
        input_tokens = self._estimate_tokens(messages, system_prompt)

        # Estimate output tokens
        output_tokens = len(response) // 4  # Rough estimate

        return (input_tokens, max(output_tokens, 1))


@asynccontextmanager
async def get_budget_llm_client(
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    service_name: Optional[str] = None
):
    """
    Async context manager for budget-aware LLM client.

    Usage:
        async with get_budget_llm_client(user_id="user123") as client:
            response = await client.chat_completion(messages=[...])

    Args:
        user_id: User ID for budget enforcement
        project_id: Project ID for cost tracking
        service_name: Service name

    Yields:
        BudgetAwareLLMClient instance
    """
    async with get_db_session() as db_session:
        client = BudgetAwareLLMClient(
            db_session=db_session,
            user_id=user_id,
            project_id=project_id,
            service_name=service_name
        )
        yield client
