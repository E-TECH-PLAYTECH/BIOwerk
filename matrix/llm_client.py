"""LLM client utility for unified access to OpenAI, Anthropic, DeepSeek, Ollama, and Local models."""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import ollama
from matrix.config import settings
from matrix.resilience import CircuitBreaker, retry_with_backoff
from matrix import budget_metrics

logger = logging.getLogger(__name__)

# Optional: Import llama-cpp-python for local models
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logger.warning("llama-cpp-python not installed. Local model support disabled. Install with: pip install llama-cpp-python")


class LLMClient:
    """Unified LLM client supporting OpenAI, Anthropic, DeepSeek, Ollama, and Local models."""

    def __init__(self):
        """Initialize LLM clients based on configuration."""
        self.provider = settings.llm_provider.lower()

        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._retry_enabled = settings.retry_enabled

        if settings.circuit_breaker_enabled:
            circuit_kwargs = {
                "failure_threshold": settings.circuit_breaker_failure_threshold,
                "success_threshold": settings.circuit_breaker_success_threshold,
                "timeout": settings.circuit_breaker_timeout,
                "failure_rate_threshold": settings.circuit_breaker_failure_rate_threshold,
                "window_size": settings.circuit_breaker_window_size,
            }
            for provider_name in ["openai", "anthropic", "deepseek", "ollama", "local"]:
                self._circuit_breakers[provider_name] = CircuitBreaker(
                    service_name=f"llm-{provider_name}",
                    **circuit_kwargs
                )

        # Initialize OpenAI client
        if settings.openai_api_key:
            self.openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout
            )
        else:
            self.openai_client = None

        # Initialize Anthropic client
        if settings.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.anthropic_timeout
            )
        else:
            self.anthropic_client = None

        # Initialize DeepSeek client (uses OpenAI SDK with custom base URL)
        if settings.deepseek_api_key:
            self.deepseek_client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=settings.deepseek_timeout
            )
        else:
            self.deepseek_client = None

        # Initialize Ollama client
        self.ollama_client = ollama.AsyncClient(host=settings.ollama_base_url)

        # Initialize Local model client
        self.local_model = None
        if self.provider == "local" and LLAMA_CPP_AVAILABLE:
            self._load_local_model()

    def _get_retry_config(self, provider: str) -> Optional[dict]:
        """Build retry configuration for provider calls."""
        if not self._retry_enabled:
            return None

        return {
            "max_attempts": settings.retry_max_attempts,
            "initial_delay": settings.retry_initial_delay,
            "max_delay": settings.retry_max_delay,
            "exponential_base": settings.retry_exponential_base,
            "jitter": settings.retry_jitter,
            "service_name": f"llm-{provider}",
        }

    def _get_provider_timeout(self, provider: str, override: Optional[float] = None) -> float:
        """Get the timeout to apply for a specific provider call."""
        if override is not None:
            return float(override)

        provider = (provider or self.provider).lower()
        if provider == "openai":
            return float(settings.openai_timeout)
        if provider == "anthropic":
            return float(settings.anthropic_timeout)
        if provider == "deepseek":
            return float(settings.deepseek_timeout)
        if provider == "ollama":
            return float(settings.ollama_timeout)
        if provider == "local":
            return float(settings.service_timeout_agent)
        return float(settings.service_timeout_default)

    def _get_default_model(self, provider: str) -> str:
        """Resolve default model name for a provider."""
        provider = provider.lower()
        if provider == "openai":
            return settings.openai_model
        if provider == "anthropic":
            return settings.anthropic_model
        if provider == "deepseek":
            return settings.deepseek_model
        if provider == "ollama":
            return settings.ollama_model
        if provider == "local":
            return settings.local_model_name
        return "unknown"

    async def _execute_with_resilience(
        self,
        provider: str,
        func: Callable[[], Any]
    ) -> Any:
        """Apply circuit breaker and retry policies around the provider call."""
        retry_config = self._get_retry_config(provider)
        circuit_breaker = self._circuit_breakers.get(provider)

        if circuit_breaker and retry_config:
            return await circuit_breaker.call(retry_with_backoff, func, **retry_config)
        if circuit_breaker:
            return await circuit_breaker.call(func)
        if retry_config:
            return await retry_with_backoff(func, **retry_config)
        return await func()

    def _load_local_model(self):
        """Load local GGUF model from disk."""
        model_path = Path(settings.local_model_path) / settings.local_model_name / settings.local_model_file

        if not model_path.exists():
            logger.error(f"Local model not found at: {model_path}")
            logger.error("Please download models using: ./scripts/download-models.sh")
            raise FileNotFoundError(f"Model file not found: {model_path}")

        logger.info(f"Loading local model from: {model_path}")

        try:
            self.local_model = Llama(
                model_path=str(model_path),
                n_ctx=settings.local_context_size,
                n_gpu_layers=settings.local_gpu_layers,
                verbose=False
            )
            logger.info(f"Local model loaded successfully: {settings.local_model_name}")
        except Exception as e:
            logger.error(f"Failed to load local model: {str(e)}")
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        json_mode: bool = False,
        timeout: Optional[float] = None
    ) -> str:
        """
        Generate a chat completion using the configured LLM provider.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt (overrides messages system if provided)
            temperature: Sampling temperature (uses config default if None)
            max_tokens: Maximum tokens to generate (uses config default if None)
            provider: Override default provider ('openai', 'anthropic', 'deepseek', 'ollama', or 'local')
            model: Override default model
            json_mode: Enable JSON response mode
            timeout: Optional per-call timeout override in seconds

        Returns:
            Generated text response

        Raises:
            ValueError: If provider is not configured or invalid
            Exception: If API call fails
        """
        provider = (provider or self.provider).lower()
        model_name = model or self._get_default_model(provider)
        timeout_seconds = self._get_provider_timeout(provider, timeout)
        start_time = time.time()
        outcome = "success"

        async def _dispatch():
            if provider == "openai":
                return await self._openai_completion(
                    messages, system_prompt, temperature, max_tokens, model_name, json_mode
                )
            if provider == "anthropic":
                return await self._anthropic_completion(
                    messages, system_prompt, temperature, max_tokens, model_name
                )
            if provider == "deepseek":
                return await self._deepseek_completion(
                    messages, system_prompt, temperature, max_tokens, model_name, json_mode
                )
            if provider == "ollama":
                return await self._ollama_completion(
                    messages, system_prompt, temperature, max_tokens, model_name, json_mode
                )
            if provider == "local":
                return await self._local_completion(
                    messages, system_prompt, temperature, max_tokens, model_name, json_mode
                )

            raise ValueError(f"Invalid LLM provider: {provider}")

        try:
            return await self._execute_with_resilience(
                provider,
                lambda: asyncio.wait_for(_dispatch(), timeout=timeout_seconds)
            )
        except asyncio.TimeoutError as e:
            outcome = "timeout"
            budget_metrics.record_provider_error(provider, model_name, "TimeoutError")
            logger.error(
                "LLM completion timed out",
                exc_info=True,
                extra={"provider": provider, "model": model_name, "timeout_seconds": timeout_seconds}
            )
            raise e
        except Exception as e:
            outcome = "error"
            budget_metrics.record_provider_error(provider, model_name, type(e).__name__)
            logger.error(
                f"LLM completion failed: {str(e)}",
                exc_info=True,
                extra={"provider": provider, "model": model_name}
            )
            raise
        finally:
            duration = time.time() - start_time
            budget_metrics.record_provider_latency(provider, model_name, duration, outcome)

    async def _openai_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str],
        json_mode: bool
    ) -> str:
        """Generate completion using OpenAI API."""
        if not self.openai_client:
            raise ValueError("OpenAI client not configured. Set OPENAI_API_KEY in environment.")

        # Prepare messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        # Prepare parameters
        params = {
            "model": model or settings.openai_model,
            "messages": formatted_messages,
            "temperature": temperature if temperature is not None else settings.openai_temperature,
            "max_tokens": max_tokens or settings.openai_max_tokens
        }

        if json_mode:
            params["response_format"] = {"type": "json_object"}

        logger.info(f"Calling OpenAI API with model {params['model']}")

        response = await self.openai_client.chat.completions.create(**params)
        content = response.choices[0].message.content

        logger.info(f"OpenAI API call successful. Tokens used: {response.usage.total_tokens}")

        return content

    async def _anthropic_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str]
    ) -> str:
        """Generate completion using Anthropic Claude API."""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not configured. Set ANTHROPIC_API_KEY in environment.")

        # Extract system prompt from messages if not provided
        if not system_prompt and messages and messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]

        # Prepare parameters
        params = {
            "model": model or settings.anthropic_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.anthropic_temperature,
            "max_tokens": max_tokens or settings.anthropic_max_tokens
        }

        if system_prompt:
            params["system"] = system_prompt

        logger.info(f"Calling Anthropic API with model {params['model']}")

        response = await self.anthropic_client.messages.create(**params)
        content = response.content[0].text

        logger.info(f"Anthropic API call successful. Tokens used: {response.usage.input_tokens + response.usage.output_tokens}")

        return content

    async def _deepseek_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str],
        json_mode: bool
    ) -> str:
        """Generate completion using DeepSeek API (OpenAI-compatible)."""
        if not self.deepseek_client:
            raise ValueError("DeepSeek client not configured. Set DEEPSEEK_API_KEY in environment.")

        # Prepare messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        # Prepare parameters
        params = {
            "model": model or settings.deepseek_model,
            "messages": formatted_messages,
            "temperature": temperature if temperature is not None else settings.deepseek_temperature,
            "max_tokens": max_tokens or settings.deepseek_max_tokens
        }

        if json_mode:
            params["response_format"] = {"type": "json_object"}

        logger.info(f"Calling DeepSeek API with model {params['model']}")

        response = await self.deepseek_client.chat.completions.create(**params)
        content = response.choices[0].message.content

        logger.info(f"DeepSeek API call successful. Tokens used: {response.usage.total_tokens}")

        return content

    async def _ollama_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str],
        json_mode: bool
    ) -> str:
        """Generate completion using Ollama (local/open-source LLMs)."""
        # Prepare messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        # Prepare options
        options = {
            "temperature": temperature if temperature is not None else settings.ollama_temperature,
            "num_predict": max_tokens or settings.ollama_max_tokens,
        }

        model_name = model or settings.ollama_model

        logger.info(f"Calling Ollama API with model {model_name}")

        try:
            response = await self.ollama_client.chat(
                model=model_name,
                messages=formatted_messages,
                options=options,
                format="json" if json_mode else None
            )

            content = response['message']['content']

            logger.info(f"Ollama API call successful with model {model_name}")

            return content

        except Exception as e:
            logger.error(f"Ollama API call failed: {str(e)}")
            # If model not found, try to pull it
            if "not found" in str(e).lower():
                logger.info(f"Model {model_name} not found. Attempting to pull...")
                try:
                    await self.ollama_client.pull(model_name)
                    logger.info(f"Model {model_name} pulled successfully. Retrying request...")
                    # Retry the request
                    response = await self.ollama_client.chat(
                        model=model_name,
                        messages=formatted_messages,
                        options=options,
                        format="json" if json_mode else None
                    )
                    return response['message']['content']
                except Exception as pull_error:
                    logger.error(f"Failed to pull model {model_name}: {str(pull_error)}")
                    raise ValueError(f"Ollama model {model_name} not available and pull failed: {str(pull_error)}")
            raise

    async def _local_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str],
        json_mode: bool
    ) -> str:
        """Generate completion using local GGUF model."""
        if not LLAMA_CPP_AVAILABLE:
            raise ValueError("Local model support not available. Install llama-cpp-python: pip install llama-cpp-python")

        if self.local_model is None:
            self._load_local_model()

        # Prepare messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        logger.info(f"Calling local model: {settings.local_model_name}")

        try:
            # llama-cpp-python expects messages format
            response = self.local_model.create_chat_completion(
                messages=formatted_messages,
                temperature=temperature if temperature is not None else settings.local_temperature,
                max_tokens=max_tokens or settings.local_max_tokens,
                response_format={"type": "json_object"} if json_mode else None
            )

            content = response['choices'][0]['message']['content']

            logger.info(f"Local model completion successful")

            return content

        except Exception as e:
            logger.error(f"Local model API call failed: {str(e)}")
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None
    ) -> str:
        """
        Generate JSON output from a prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            provider: Override default provider

        Returns:
            JSON string response
        """
        messages = [{"role": "user", "content": prompt}]

        # For OpenAI, DeepSeek, Ollama, and Local use JSON mode; for others, rely on system prompt
        effective_provider = provider or self.provider
        if effective_provider in ["openai", "deepseek", "ollama", "local"]:
            return await self.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                json_mode=True,
                provider=provider
            )
        else:
            # For Anthropic, add JSON instruction to system prompt
            json_system = (system_prompt or "") + "\n\nYou must respond with valid JSON only. Do not include any text outside the JSON structure."
            return await self.chat_completion(
                messages=messages,
                system_prompt=json_system,
                provider=provider
            )


# Global LLM client instance
llm_client = LLMClient()
