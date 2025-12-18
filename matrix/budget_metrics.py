"""
Prometheus metrics for LLM cost tracking and budget monitoring.

Provides comprehensive metrics for:
- Token usage and costs per user/project/provider/model
- Budget utilization and threshold alerts
- Cost spike detection
- Model fallback tracking
- Request success rates
"""

from prometheus_client import Counter, Histogram, Gauge, Summary
from typing import Optional

# ============================================================================
# Token Usage Metrics
# ============================================================================

token_usage_total = Counter(
    "biowerk_llm_tokens_total",
    "Total LLM tokens consumed",
    ["user_id", "project_id", "provider", "model", "service", "token_type"]
)

token_cost_total = Counter(
    "biowerk_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["user_id", "project_id", "provider", "model", "service"]
)

request_count_total = Counter(
    "biowerk_llm_requests_total",
    "Total LLM requests",
    ["user_id", "project_id", "provider", "model", "service", "status"]
)

request_duration_seconds = Histogram(
    "biowerk_llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model", "service"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Provider Resilience Metrics
provider_latency_seconds = Histogram(
    "biowerk_llm_provider_latency_seconds",
    "LLM provider call latency in seconds",
    ["provider", "model", "outcome"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

provider_errors_total = Counter(
    "biowerk_llm_provider_errors_total",
    "Total LLM provider errors by type",
    ["provider", "model", "error_type"]
)

provider_timeouts_total = Counter(
    "biowerk_llm_provider_timeouts_total",
    "Total LLM provider timeouts by stage (primary, fallback, etc.)",
    ["provider", "model", "stage"]
)

fallback_events_total = Counter(
    "biowerk_llm_fallback_events_total",
    "Total LLM fallback events across providers and reasons",
    ["from_provider", "from_model", "to_provider", "to_model", "reason"]
)

fallback_attempts_total = Counter(
    "biowerk_llm_fallback_attempts_total",
    "Total attempts to route to fallback models/providers",
    ["from_provider", "from_model", "to_provider", "to_model", "reason"]
)

fallback_failures_total = Counter(
    "biowerk_llm_fallback_failures_total",
    "Total fallback attempts that failed",
    ["from_provider", "from_model", "to_provider", "to_model", "reason"]
)

# ============================================================================
# Budget Metrics
# ============================================================================

budget_usage_percentage = Gauge(
    "biowerk_budget_usage_percentage",
    "Current budget usage as percentage of limit",
    ["budget_id", "budget_name", "budget_type", "limit_period"]
)

budget_usage_value = Gauge(
    "biowerk_budget_usage_value",
    "Current budget usage value (cost or tokens)",
    ["budget_id", "budget_name", "budget_type", "limit_type", "limit_period"]
)

budget_limit_value = Gauge(
    "biowerk_budget_limit_value",
    "Budget limit value",
    ["budget_id", "budget_name", "budget_type", "limit_type", "limit_period"]
)

budget_exceeded_total = Counter(
    "biowerk_budget_exceeded_total",
    "Total budget limit violations",
    ["budget_id", "budget_name", "budget_type", "threshold"]
)

budget_fallback_total = Counter(
    "biowerk_budget_fallback_total",
    "Total model fallbacks triggered by budget",
    ["original_provider", "original_model", "fallback_provider", "fallback_model"]
)

# ============================================================================
# Alert Metrics
# ============================================================================

cost_alerts_total = Counter(
    "biowerk_cost_alerts_total",
    "Total cost alerts generated",
    ["alert_type", "severity", "budget_type"]
)

cost_spike_detected_total = Counter(
    "biowerk_cost_spike_detected_total",
    "Total cost spikes detected",
    ["user_id", "project_id"]
)

cost_spike_multiplier = Gauge(
    "biowerk_cost_spike_multiplier",
    "Cost spike multiplier (recent cost / baseline)",
    ["user_id", "project_id"]
)

# ============================================================================
# Provider Performance Metrics
# ============================================================================

provider_success_rate = Gauge(
    "biowerk_llm_provider_success_rate",
    "Provider success rate (0.0-1.0)",
    ["provider", "model"]
)

provider_avg_cost = Gauge(
    "biowerk_llm_provider_avg_cost_usd",
    "Average cost per request by provider",
    ["provider", "model"]
)

provider_avg_tokens = Gauge(
    "biowerk_llm_provider_avg_tokens",
    "Average tokens per request by provider",
    ["provider", "model"]
)

# ============================================================================
# Helper Functions
# ============================================================================

def record_token_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    service: Optional[str] = None,
    success: bool = True
):
    """Record token usage metrics."""
    user = user_id or "unknown"
    project = project_id or "unknown"
    svc = service or "unknown"

    # Record token counts
    token_usage_total.labels(
        user_id=user,
        project_id=project,
        provider=provider,
        model=model,
        service=svc,
        token_type="input"
    ).inc(input_tokens)

    token_usage_total.labels(
        user_id=user,
        project_id=project,
        provider=provider,
        model=model,
        service=svc,
        token_type="output"
    ).inc(output_tokens)

    # Record cost
    token_cost_total.labels(
        user_id=user,
        project_id=project,
        provider=provider,
        model=model,
        service=svc
    ).inc(cost)

    # Record request count
    status = "success" if success else "error"
    request_count_total.labels(
        user_id=user,
        project_id=project,
        provider=provider,
        model=model,
        service=svc,
        status=status
    ).inc()


def record_request_duration(
    provider: str,
    model: str,
    duration_seconds: float,
    service: Optional[str] = None
):
    """Record request duration."""
    svc = service or "unknown"
    request_duration_seconds.labels(
        provider=provider,
        model=model,
        service=svc
    ).observe(duration_seconds)


def record_provider_latency(
    provider: str,
    model: str,
    duration_seconds: float,
    outcome: str
):
    """Record provider latency with outcome (success, timeout, error)."""
    provider_latency_seconds.labels(
        provider=provider,
        model=model,
        outcome=outcome
    ).observe(duration_seconds)


def record_provider_error(
    provider: str,
    model: str,
    error_type: str
):
    """Increment provider error counter for given error type."""
    provider_errors_total.labels(
        provider=provider,
        model=model,
        error_type=error_type
    ).inc()


def record_provider_timeout(
    provider: str,
    model: str,
    stage: str
):
    """Increment provider timeout counter with stage context (primary vs fallback)."""
    provider_timeouts_total.labels(
        provider=provider,
        model=model,
        stage=stage
    ).inc()


def record_fallback_event(
    original_provider: str,
    original_model: str,
    fallback_provider: str,
    fallback_model: str,
    reason: str
):
    """Record a fallback routing event between providers/models."""
    fallback_events_total.labels(
        from_provider=original_provider,
        from_model=original_model,
        to_provider=fallback_provider,
        to_model=fallback_model,
        reason=reason
    ).inc()


def record_fallback_attempt(
    original_provider: str,
    original_model: str,
    fallback_provider: str,
    fallback_model: str,
    reason: str
):
    """Record an attempt to route to a fallback provider/model."""
    fallback_attempts_total.labels(
        from_provider=original_provider,
        from_model=original_model,
        to_provider=fallback_provider,
        to_model=fallback_model,
        reason=reason
    ).inc()


def record_fallback_failure(
    original_provider: str,
    original_model: str,
    fallback_provider: str,
    fallback_model: str,
    reason: str
):
    """Record a failed fallback attempt."""
    fallback_failures_total.labels(
        from_provider=original_provider,
        from_model=original_model,
        to_provider=fallback_provider,
        to_model=fallback_model,
        reason=reason
    ).inc()


def update_budget_metrics(
    budget_id: str,
    budget_name: str,
    budget_type: str,
    limit_type: str,
    limit_period: str,
    current_usage: float,
    limit_value: float,
    usage_percentage: float
):
    """Update budget-related metrics."""
    budget_usage_value.labels(
        budget_id=budget_id,
        budget_name=budget_name,
        budget_type=budget_type,
        limit_type=limit_type,
        limit_period=limit_period
    ).set(current_usage)

    budget_limit_value.labels(
        budget_id=budget_id,
        budget_name=budget_name,
        budget_type=budget_type,
        limit_type=limit_type,
        limit_period=limit_period
    ).set(limit_value)

    budget_usage_percentage.labels(
        budget_id=budget_id,
        budget_name=budget_name,
        budget_type=budget_type,
        limit_period=limit_period
    ).set(usage_percentage)


def record_budget_exceeded(
    budget_id: str,
    budget_name: str,
    budget_type: str,
    threshold: str
):
    """Record budget limit violation."""
    budget_exceeded_total.labels(
        budget_id=budget_id,
        budget_name=budget_name,
        budget_type=budget_type,
        threshold=threshold
    ).inc()


def record_fallback(
    original_provider: str,
    original_model: str,
    fallback_provider: str,
    fallback_model: str
):
    """Record model fallback event."""
    budget_fallback_total.labels(
        original_provider=original_provider,
        original_model=original_model,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model
    ).inc()


def record_cost_alert(
    alert_type: str,
    severity: str,
    budget_type: Optional[str] = None
):
    """Record cost alert generation."""
    cost_alerts_total.labels(
        alert_type=alert_type,
        severity=severity,
        budget_type=budget_type or "unknown"
    ).inc()


def record_cost_spike(
    multiplier: float,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None
):
    """Record cost spike detection."""
    user = user_id or "unknown"
    project = project_id or "unknown"

    cost_spike_detected_total.labels(
        user_id=user,
        project_id=project
    ).inc()

    cost_spike_multiplier.labels(
        user_id=user,
        project_id=project
    ).set(multiplier)


def update_provider_metrics(
    provider: str,
    model: str,
    success_rate: float,
    avg_cost: float,
    avg_tokens: float
):
    """Update provider performance metrics."""
    provider_success_rate.labels(
        provider=provider,
        model=model
    ).set(success_rate)

    provider_avg_cost.labels(
        provider=provider,
        model=model
    ).set(avg_cost)

    provider_avg_tokens.labels(
        provider=provider,
        model=model
    ).set(avg_tokens)
