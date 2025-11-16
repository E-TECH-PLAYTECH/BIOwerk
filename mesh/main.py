from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os, httpx, time
from contextlib import asynccontextmanager
from typing import Dict
from matrix.models import Msg, Reply
from matrix.observability import setup_instrumentation
from matrix.utils import state_hash
from matrix.logging_config import setup_logging, log_request, log_response, log_error
from matrix.errors import AgentNotFoundError
from matrix.config import settings
from matrix.resilience import (
    ResilientHttpClient,
    CircuitBreakerError,
    RetryExhaustedError,
    BulkheadFullError,
    HealthAwareRouter
)

# Agent URLs configuration
AGENT_URLS = {
    "osteon": os.getenv("AGENT_OSTEON_URL","http://osteon:8001"),
    "myocyte": os.getenv("AGENT_MYOCYTE_URL","http://myocyte:8002"),
    "synapse": os.getenv("AGENT_SYNAPSE_URL","http://synapse:8003"),
    "circadian": os.getenv("AGENT_CIRCADIAN_URL","http://circadian:8004"),
    "nucleus": os.getenv("AGENT_NUCLEUS_URL","http://nucleus:8005"),
    "chaperone": os.getenv("AGENT_CHAPERONE_URL","http://chaperone:8006"),
}

# Global resilient HTTP clients for each agent
resilient_clients: Dict[str, ResilientHttpClient] = {}

# Health-aware router for intelligent routing
health_router: HealthAwareRouter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global resilient_clients, health_router

    # Initialize health-aware router if enabled
    if settings.health_check_enabled:
        health_router = HealthAwareRouter(
            health_check_interval=settings.health_check_interval,
            unhealthy_threshold=settings.health_unhealthy_threshold,
            healthy_threshold=settings.health_healthy_threshold
        )

        # Register all agents for health monitoring
        for agent_name, agent_url in AGENT_URLS.items():
            health_router.register_service(
                service_name=agent_name,
                health_url=f"{agent_url}/health"
            )

        logger.info("Health-aware router initialized for all agents")

    # Initialize resilient HTTP clients for each agent
    for agent_name, agent_url in AGENT_URLS.items():
        circuit_breaker_kwargs = {
            'failure_threshold': settings.circuit_breaker_failure_threshold,
            'success_threshold': settings.circuit_breaker_success_threshold,
            'timeout': settings.circuit_breaker_timeout,
            'failure_rate_threshold': settings.circuit_breaker_failure_rate_threshold,
            'window_size': settings.circuit_breaker_window_size
        } if settings.circuit_breaker_enabled else None

        retry_kwargs = {
            'max_attempts': settings.retry_max_attempts,
            'initial_delay': settings.retry_initial_delay,
            'max_delay': settings.retry_max_delay,
            'exponential_base': settings.retry_exponential_base,
            'jitter': settings.retry_jitter
        } if settings.retry_enabled else None

        bulkhead_kwargs = {
            'max_concurrent': settings.bulkhead_max_concurrent,
            'queue_size': settings.bulkhead_queue_size,
            'timeout': settings.bulkhead_timeout
        } if settings.bulkhead_enabled else None

        resilient_clients[agent_name] = ResilientHttpClient(
            service_name=agent_name,
            base_url=agent_url,
            timeout=settings.service_timeout_mesh,
            circuit_breaker_kwargs=circuit_breaker_kwargs,
            retry_kwargs=retry_kwargs,
            bulkhead_kwargs=bulkhead_kwargs,
            enable_circuit_breaker=settings.circuit_breaker_enabled,
            enable_retry=settings.retry_enabled,
            enable_bulkhead=settings.bulkhead_enabled
        )

        logger.info(f"Initialized resilient client for agent: {agent_name}")

    logger.info("Service mesh resilience initialized successfully")

    yield

    # Cleanup: close all HTTP clients
    for agent_name, client in resilient_clients.items():
        await client.aclose()
        logger.info(f"Closed resilient client for agent: {agent_name}")

    resilient_clients.clear()


app = FastAPI(title="Mesh Gateway", lifespan=lifespan)
setup_instrumentation(app)
logger = setup_logging("mesh")

@app.post("/{agent}/{endpoint}")
async def route(agent: str, endpoint: str, request: Request):
    """
    Route requests to agents with enterprise-grade resilience.

    Features:
    - Circuit breaker: Fails fast when agent is down
    - Retry with exponential backoff: Handles transient failures
    - Bulkhead: Prevents resource exhaustion
    - Health-aware routing: Checks agent health before routing
    """
    start_time = time.time()
    data = await request.json()
    msg = Msg(**data)

    log_request(logger, msg.id, agent, endpoint)

    # Validate agent exists
    if agent not in AGENT_URLS:
        error = AgentNotFoundError(
            f"Unknown agent: {agent}",
            {"agent": agent, "available_agents": list(AGENT_URLS.keys())}
        )
        log_error(logger, msg.id, error, agent=agent, endpoint=endpoint)
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent}")

    # Health-aware routing: Check if agent is healthy
    if health_router and not health_router.is_healthy(agent):
        health_score = health_router.get_health_score(agent)
        logger.warning(
            f"Agent {agent} is marked unhealthy (health_score={health_score:.2f}). "
            f"Attempting request anyway with circuit breaker protection."
        )

    # Get resilient client for this agent
    client = resilient_clients.get(agent)
    if not client:
        # Fallback to basic HTTP client if resilient client not initialized
        logger.warning(f"Resilient client not found for {agent}, using fallback")
        async with httpx.AsyncClient(timeout=settings.service_timeout_mesh) as fallback_client:
            url = f"{AGENT_URLS[agent]}/{endpoint}"
            headers = {}
            auth_header = request.headers.get("authorization")
            if auth_header:
                headers["Authorization"] = auth_header

            try:
                r = await fallback_client.post(url, json=msg.model_dump(), headers=headers or None)
                r.raise_for_status()
                response_data = r.json()

                duration_ms = (time.time() - start_time) * 1000
                log_response(logger, msg.id, agent, response_data.get("ok", True), duration_ms, endpoint=endpoint)

                return response_data
            except httpx.HTTPError as exc:
                duration_ms = (time.time() - start_time) * 1000
                log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, duration_ms=duration_ms)
                raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Prepare headers
    headers = {}
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["Authorization"] = auth_header

    # Make request using resilient client with all patterns
    try:
        url = f"/{endpoint}"
        r = await client.post(url, json=msg.model_dump(), headers=headers or None)

        # Update health status on success
        if health_router:
            await health_router.update_health(agent, is_healthy=True)

        response_data = r.json()

        duration_ms = (time.time() - start_time) * 1000
        log_response(logger, msg.id, agent, response_data.get("ok", True), duration_ms, endpoint=endpoint)

        return response_data

    except CircuitBreakerError as exc:
        # Circuit breaker is open, fail fast
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, duration_ms=duration_ms)

        if health_router:
            await health_router.update_health(agent, is_healthy=False)

        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service Unavailable",
                "message": f"Circuit breaker is OPEN for {agent}. Service is temporarily unavailable.",
                "agent": agent,
                "retry_after": settings.circuit_breaker_timeout
            }
        )

    except RetryExhaustedError as exc:
        # All retries exhausted
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, duration_ms=duration_ms)

        if health_router:
            await health_router.update_health(agent, is_healthy=False)

        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service Unavailable",
                "message": f"All retry attempts exhausted for {agent}. Service may be down.",
                "agent": agent,
                "max_attempts": settings.retry_max_attempts
            }
        )

    except BulkheadFullError as exc:
        # Bulkhead is full
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, duration_ms=duration_ms)

        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too Many Requests",
                "message": f"Too many concurrent requests to {agent}. Please try again later.",
                "agent": agent,
                "max_concurrent": settings.bulkhead_max_concurrent,
                "retry_after": 1
            }
        )

    except httpx.HTTPStatusError as exc:
        # HTTP error response from agent
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, status_code=exc.response.status_code, duration_ms=duration_ms)

        # Update health on server errors (5xx)
        if health_router and exc.response.status_code >= 500:
            await health_router.update_health(agent, is_healthy=False)

        try:
            content = exc.response.json()
        except ValueError:
            content = {"detail": exc.response.text}

        return JSONResponse(status_code=exc.response.status_code, content=content)

    except httpx.HTTPError as exc:
        # Network/connection error
        duration_ms = (time.time() - start_time) * 1000
        log_error(logger, msg.id, exc, agent=agent, endpoint=endpoint, duration_ms=duration_ms)

        if health_router:
            await health_router.update_health(agent, is_healthy=False)

        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/health")
def health():
    return {"ok": True, "ts": time.time(), "agents": list(AGENT_URLS.keys())}
