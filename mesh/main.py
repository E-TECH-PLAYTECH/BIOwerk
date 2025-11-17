from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, httpx, time
from contextlib import asynccontextmanager
from typing import Dict, Optional
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
from matrix.auth_dependencies import (
    get_current_user,
    get_current_user_or_api_key,
    has_permission,
    get_postgres_session
)
from matrix.db_models import User
from sqlalchemy.ext.asyncio import AsyncSession
from matrix.versioning import version_middleware, get_version_from_request
from matrix.security_headers import create_security_headers_middleware, SecurityHeadersConfig
from matrix.audit import get_audit_logger, EventType, EventCategory, EventStatus, Severity, AuditContext

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
setup_instrumentation(app, service_name="mesh", service_version="1.0.0")
logger = setup_logging("mesh")

# ============================================================================
# CORS Configuration
# ============================================================================
# Configure allowed origins based on environment
if settings.environment == "production":
    # In production, use explicit allowed origins (no wildcard)
    allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
    if not allowed_origins:
        logger.warning(
            "No CORS_ALLOWED_ORIGINS configured in production. "
            "CORS will be disabled. Set CORS_ALLOWED_ORIGINS environment variable."
        )
else:
    # In development, allow all origins for easier testing
    allowed_origins = ["*"]
    logger.info("CORS configured for development - allowing all origins")

# Only add CORS middleware if origins are configured
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,  # Allow cookies and authorization headers
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-Request-ID",
            "X-Correlation-ID",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Requested-With",
        ],
        max_age=600,  # Cache preflight requests for 10 minutes
    )
    logger.info(f"CORS middleware configured with origins: {allowed_origins}")

# ============================================================================
# Security Headers Middleware
# ============================================================================
app.add_middleware(create_security_headers_middleware())
logger.info("Security headers middleware configured")

# Add API versioning middleware
app.middleware("http")(version_middleware)

# Setup comprehensive health and readiness endpoints
from matrix.health import setup_health_endpoints
setup_health_endpoints(app, service_name="mesh", version="1.0.0")

# ============================================================================
# CSP Violation Reporting Endpoint
# ============================================================================

@app.post("/api/csp-report")
async def csp_report(
    request: Request,
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Endpoint for receiving CSP violation reports.

    This endpoint receives reports from browsers when Content-Security-Policy
    violations occur. All violations are logged to the audit system for
    security monitoring and analysis.
    """
    try:
        # Parse CSP violation report
        report_data = await request.json()

        # Extract CSP report from the envelope
        csp_report = report_data.get("csp-report", {})

        # Log the violation
        logger.warning(
            f"CSP Violation: {csp_report.get('violated-directive', 'unknown')} "
            f"blocked {csp_report.get('blocked-uri', 'unknown')} "
            f"on {csp_report.get('document-uri', 'unknown')}"
        )

        # Get audit logger and log to audit system
        audit_logger = get_audit_logger()
        context = AuditContext(
            user_id=None,  # CSP reports are anonymous
            session_id=None,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            service_name="mesh",
        )

        await audit_logger.log(
            event_type=EventType.SECURITY,
            event_category=EventCategory.security,
            event_action="csp_violation",
            event_status=EventStatus.warning,
            severity=Severity.WARNING,
            context=context,
            endpoint="/api/csp-report",
            http_method="POST",
            http_status_code=200,
            request_data={
                "violated_directive": csp_report.get("violated-directive"),
                "blocked_uri": csp_report.get("blocked-uri"),
                "document_uri": csp_report.get("document-uri"),
                "original_policy": csp_report.get("original-policy"),
                "source_file": csp_report.get("source-file"),
                "line_number": csp_report.get("line-number"),
                "column_number": csp_report.get("column-number"),
            },
            session=db,
        )

        # Check for repeated violations (potential attack)
        blocked_uri = csp_report.get("blocked-uri", "")
        violated_directive = csp_report.get("violated-directive", "")

        # Alert on suspicious patterns
        if blocked_uri and any(suspicious in blocked_uri.lower() for suspicious in ["eval", "inline", "data:", "javascript:"]):
            logger.error(
                f"SUSPICIOUS CSP VIOLATION: Potential XSS attempt blocked. "
                f"Directive: {violated_directive}, URI: {blocked_uri}"
            )

        return JSONResponse(
            status_code=204,  # No Content - standard for CSP reports
            content=None
        )

    except Exception as e:
        logger.error(f"Error processing CSP report: {str(e)}")
        # Return 204 even on error to avoid browser retry loops
        return JSONResponse(status_code=204, content=None)


# ============================================================================
# RBAC Configuration - Service to Resource Type Mapping
# ============================================================================

# Define which service operations require which permissions
SERVICE_PERMISSION_MAP = {
    "osteon": {
        "outline": ("write", "artifact"),
        "draft": ("write", "artifact"),
        "edit": ("write", "artifact"),
        "summarize": ("read", "artifact"),
        "export": ("read", "artifact"),
    },
    "myocyte": {
        "ingest_table": ("write", "artifact"),
        "formula_eval": ("write", "artifact"),
        "model_forecast": ("write", "artifact"),
        "export": ("read", "artifact"),
    },
    "synapse": {
        "storyboard": ("write", "artifact"),
        "slide_make": ("write", "artifact"),
        "visualize": ("write", "artifact"),
        "export": ("read", "artifact"),
    },
    "nucleus": {
        "plan": ("admin", "project"),  # Project planning requires admin
        "route": ("read", "execution"),
        "review": ("read", "execution"),
        "finalize": ("write", "execution"),
    },
    "circadian": {
        "plan_timeline": ("write", "project"),
        "assign": ("admin", "project"),  # Task assignment requires admin
        "track": ("read", "project"),
        "remind": ("read", "project"),
    },
    "chaperone": {
        "validate": ("read", "execution"),
        "monitor": ("read", "execution"),
    },
}


async def check_rbac_authorization(
    agent: str,
    endpoint: str,
    user: Optional[User],
    db: AsyncSession
) -> bool:
    """
    Check if user is authorized to access the agent endpoint.

    Args:
        agent: Service/agent name
        endpoint: Endpoint name
        user: User object (can be None if auth not required)
        db: Database session

    Returns:
        True if authorized, raises HTTPException otherwise
    """
    # If auth is not required and no user, allow access
    if not settings.require_auth and not user:
        return True

    # If auth is required but no user, deny
    if settings.require_auth and not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    # If no user at this point, allow (auth not required)
    if not user:
        return True

    # Check if service/endpoint has RBAC requirements
    if agent in SERVICE_PERMISSION_MAP:
        endpoint_perms = SERVICE_PERMISSION_MAP[agent].get(endpoint)
        if endpoint_perms:
            action, resource_type = endpoint_perms

            # Check permission
            if not await has_permission(user, action, resource_type, db):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {action} on {resource_type} required for {agent}/{endpoint}"
                )

    return True

async def _route_handler(
    agent: str,
    endpoint: str,
    request: Request,
    user: Optional[User],
    db: AsyncSession,
    api_version: str = "v1"
):
    """
    Internal route handler with enterprise-grade resilience and RBAC.

    Features:
    - Circuit breaker: Fails fast when agent is down
    - Retry with exponential backoff: Handles transient failures
    - Bulkhead: Prevents resource exhaustion
    - Health-aware routing: Checks agent health before routing
    - RBAC: Role-based access control for all endpoints
    - API versioning: Version-aware routing
    """
    start_time = time.time()
    data = await request.json()
    msg = Msg(**data)

    # Set API version from request
    msg.api_version = api_version

    log_request(logger, msg.id, agent, endpoint)

    # RBAC Authorization Check
    await check_rbac_authorization(agent, endpoint, user, db)

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

                # Ensure response includes API version
                if isinstance(response_data, dict) and "api_version" not in response_data:
                    response_data["api_version"] = api_version

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

        # Ensure response includes API version
        if isinstance(response_data, dict) and "api_version" not in response_data:
            response_data["api_version"] = api_version

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

# ============================================================================
# Versioned Routes (v1)
# ============================================================================

@app.post("/v1/{agent}/{endpoint}")
async def route_v1(
    agent: str,
    endpoint: str,
    request: Request,
    user: Optional[User] = Depends(get_current_user_or_api_key),
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Route requests to agents with API v1.

    This is the current stable version of the API.
    """
    return await _route_handler(agent, endpoint, request, user, db, api_version="v1")

# ============================================================================
# Legacy Routes (Backward Compatibility)
# ============================================================================

@app.post("/{agent}/{endpoint}")
async def route_legacy(
    agent: str,
    endpoint: str,
    request: Request,
    user: Optional[User] = Depends(get_current_user_or_api_key),
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Legacy route handler for backward compatibility.

    DEPRECATED: This unversioned endpoint is deprecated. Please use /v1/{agent}/{endpoint}.
    This endpoint defaults to API v1 but may be removed in future versions.
    """
    logger.warning(
        f"Deprecated unversioned endpoint used: /{agent}/{endpoint}. "
        f"Please migrate to /v1/{agent}/{endpoint}"
    )

    response = await _route_handler(agent, endpoint, request, user, db, api_version="v1")

    # Add deprecation warning to response
    if isinstance(response, dict):
        response["_deprecation_warning"] = {
            "message": "This unversioned endpoint is deprecated. Please use /v1/{agent}/{endpoint}",
            "legacy_path": f"/{agent}/{endpoint}",
            "recommended_path": f"/v1/{agent}/{endpoint}",
            "migration_guide": "https://github.com/E-TECH-PLAYTECH/BIOwerk/blob/main/docs/API_VERSIONING.md"
        }

    return response

# Health and readiness endpoints are now provided by setup_health_endpoints()
# Legacy endpoint for backward compatibility
@app.get("/health/legacy")
def health_legacy():
    """Legacy health endpoint for backward compatibility."""
    return {"ok": True, "ts": time.time(), "agents": list(AGENT_URLS.keys())}
