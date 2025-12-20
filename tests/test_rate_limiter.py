"""
Enterprise-grade tests for Rate Limiter and middleware behaviours.

New coverage ensures:
- Per-IP, per-user, and bypass paths are exercised
- Sliding window and token bucket behaviour under burst/sustained load
- Retry headers, logging, and throttling responses are verified
"""
import logging
import math
import sys
import time
import types
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request, status
from starlette.responses import Response

sys.modules.setdefault("blake3", MagicMock())
sys.modules.setdefault("motor", types.ModuleType("motor"))
motor_asyncio_module = types.ModuleType("motor.motor_asyncio")
setattr(motor_asyncio_module, "AsyncIOMotorClient", MagicMock())
sys.modules.setdefault("motor.motor_asyncio", motor_asyncio_module)
sys.modules.setdefault("motor.core", types.ModuleType("motor.core"))
sys.modules.setdefault("motor.motor_gridfs", types.ModuleType("motor.motor_gridfs"))
pymongo_module = types.ModuleType("pymongo")
pymongo_errors = types.ModuleType("pymongo.errors")
setattr(pymongo_errors, "ConfigurationError", Exception)
sys.modules.setdefault("pymongo", pymongo_module)
sys.modules.setdefault("pymongo.errors", pymongo_errors)
pymongo_cursor = types.ModuleType("pymongo.cursor")
setattr(pymongo_cursor, "_QUERY_OPTIONS", None)
setattr(pymongo_cursor, "Cursor", object)
setattr(pymongo_cursor, "RawBatchCursor", object)
sys.modules.setdefault("pymongo.cursor", pymongo_cursor)
dateutil_module = types.ModuleType("dateutil")
relativedelta_module = types.ModuleType("dateutil.relativedelta")
setattr(relativedelta_module, "relativedelta", MagicMock())
sys.modules.setdefault("dateutil", dateutil_module)
sys.modules.setdefault("dateutil.relativedelta", relativedelta_module)
matrix_errors_module = types.ModuleType("matrix.errors")
setattr(matrix_errors_module, "BudgetExceededError", Exception)
setattr(matrix_errors_module, "BudgetWarning", Warning)
setattr(matrix_errors_module, "BIOworkError", Exception)
setattr(matrix_errors_module, "InvalidInputError", Exception)
setattr(matrix_errors_module, "AgentProcessingError", Exception)
setattr(matrix_errors_module, "AgentNotFoundError", Exception)
setattr(matrix_errors_module, "create_error_response", MagicMock())
setattr(matrix_errors_module, "validate_msg_input", MagicMock())
sys.modules.setdefault("matrix.errors", matrix_errors_module)

from matrix.rate_limiter import RateLimitExceeded, RateLimiter, RateLimitMiddleware


@pytest.fixture
def anyio_backend():
    """Force asyncio backend to avoid pulling optional trio dependency in CI."""
    return "asyncio"


class FakeTime:
    """Deterministic clock for rate limiter tests."""

    def __init__(self, start: Optional[float] = None):
        self._current = float(start or time.time())

    def time(self) -> float:
        return self._current

    def advance(self, seconds: float) -> None:
        self._current += seconds


class FakePipeline:
    """Minimal Redis pipeline that applies operations atomically for tests."""

    def __init__(self, redis: "FakeRedis"):
        self.redis = redis
        self.operations: List[Tuple] = []

    def incr(self, key: str):
        self.operations.append(("incr", key))
        return self

    def expireat(self, key: str, timestamp: int):
        self.operations.append(("expireat", key, timestamp))
        return self

    def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        self.operations.append(("zremrangebyscore", key, min_score, max_score))
        return self

    def zcard(self, key: str):
        self.operations.append(("zcard", key))
        return self

    def zadd(self, key: str, mapping: Dict[str, float]):
        self.operations.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, ttl: int):
        self.operations.append(("expire", key, ttl))
        return self

    async def execute(self) -> List:
        results: List = []
        for operation in self.operations:
            name, *args = operation
            handler = getattr(self.redis, f"_{name}")
            results.append(handler(*args))
        self.operations.clear()
        return results


class FakeRedis:
    """Stateful Redis double supporting pipeline and token bucket eval."""

    def __init__(self, fake_time: FakeTime):
        self.fake_time = fake_time
        self.kv = defaultdict(int)
        self.expirations = {}
        self.sorted_sets: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        self.buckets: Dict[str, Dict[str, float]] = {}

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    # Pipeline handlers -----------------------------------------------------
    def _incr(self, key: str) -> int:
        self.kv[key] += 1
        return self.kv[key]

    def _expireat(self, key: str, timestamp: int) -> bool:
        self.expirations[key] = timestamp
        return True

    def _zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        before = len(self.sorted_sets[key])
        self.sorted_sets[key] = [
            entry for entry in self.sorted_sets[key]
            if not (min_score <= entry[1] <= max_score)
        ]
        return before - len(self.sorted_sets[key])

    def _zcard(self, key: str) -> int:
        return len(self.sorted_sets[key])

    def _zadd(self, key: str, mapping: Dict[str, float]) -> int:
        members = {member for member, _ in self.sorted_sets[key]}
        for member, score in mapping.items():
            if member in members:
                self.sorted_sets[key] = [
                    entry for entry in self.sorted_sets[key] if entry[0] != member
                ]
            self.sorted_sets[key].append((member, float(score)))
        return len(mapping)

    def _expire(self, key: str, ttl: int) -> bool:
        self.expirations[key] = self.fake_time.time() + ttl
        return True

    # Direct Redis lookups --------------------------------------------------
    async def zrange(self, key: str, start: int, end: int, withscores: bool = False):
        entries = sorted(self.sorted_sets.get(key, []), key=lambda item: item[1])
        sliced = entries[start:end + 1 if end != -1 else None]
        if withscores:
            return [(member, score) for member, score in sliced]
        return [member for member, _ in sliced]

    async def zrem(self, key: str, member: str) -> int:
        before = len(self.sorted_sets[key])
        self.sorted_sets[key] = [entry for entry in self.sorted_sets[key] if entry[0] != member]
        return before - len(self.sorted_sets[key])

    async def eval(self, _lua: str, _keys: int, key: str, capacity: int, refill_rate: float,
                   now: float, window: int, burst: int):
        bucket = self.buckets.get(key, {"tokens": None, "last_refill": None})
        tokens = bucket["tokens"]
        last_refill = bucket["last_refill"]

        if tokens is None:
            tokens = capacity + burst
            last_refill = now

        elapsed = now - last_refill
        tokens = min(capacity + burst, tokens + elapsed * refill_rate)

        if tokens >= 1:
            tokens -= 1
            self.buckets[key] = {"tokens": tokens, "last_refill": now}
            return [1, math.floor(tokens)]

        tokens_needed = 1 - tokens
        retry_after = math.ceil(tokens_needed / refill_rate)
        self.buckets[key] = {"tokens": tokens, "last_refill": now}
        return [0, 0, retry_after]


def build_request(path: str = "/resource", client_ip: str = "127.0.0.1", forwarded_for: Optional[str] = None) -> Request:
    """Construct a Starlette Request for middleware testing."""
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "root_path": "",
        "scheme": "http",
        "headers": headers,
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive=receive)


# ============================================================================
# Rate limiter primitives
# ============================================================================


@pytest.mark.anyio
async def test_rate_limiter_initialization():
    """Ensure limiter carries configuration forward."""
    mock_redis = AsyncMock()
    limiter = RateLimiter(mock_redis, requests=100, window=60, strategy="sliding_window")
    assert limiter.requests == 100
    assert limiter.window == 60
    assert limiter.strategy == "sliding_window"


def test_invalid_strategy():
    """Reject unsupported strategies to prevent silent misconfiguration."""
    with pytest.raises(ValueError):
        RateLimiter(AsyncMock(), strategy="invalid_strategy")


@pytest.mark.anyio
async def test_sliding_window_sustained_load(monkeypatch: pytest.MonkeyPatch):
    """Validate sustained load trips sliding-window limits and resets after the window."""
    fake_time = FakeTime(1_000_000)
    fake_redis = FakeRedis(fake_time)
    monkeypatch.setattr("matrix.rate_limiter.time", fake_time)

    limiter = RateLimiter(fake_redis, requests=3, window=5, strategy="sliding_window")

    for _ in range(3):
        result = await limiter.check_rate_limit("ip:198.51.100.10")
        assert result["allowed"] is True
        fake_time.advance(1)

    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check_rate_limit("ip:198.51.100.10")
    assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    fake_time.advance(5)
    recovered = await limiter.check_rate_limit("ip:198.51.100.10")
    assert recovered["allowed"] is True
    assert recovered["remaining"] == limiter.requests - 1


@pytest.mark.anyio
async def test_token_bucket_burst_and_recovery(monkeypatch: pytest.MonkeyPatch):
    """Simulate burst traffic and verify recovery after retry_after delay."""
    fake_time = FakeTime(5_000_000)
    fake_redis = FakeRedis(fake_time)
    monkeypatch.setattr("matrix.rate_limiter.time", fake_time)

    limiter = RateLimiter(fake_redis, requests=5, window=10, strategy="token_bucket", burst=2)

    for _ in range(7):
        allowed = await limiter.check_rate_limit("user:alpha")
        assert allowed["allowed"] is True

    with pytest.raises(RateLimitExceeded) as exc:
        await limiter.check_rate_limit("user:alpha")
    retry_after = int(exc.value.headers["Retry-After"])
    assert retry_after >= 2

    fake_time.advance(retry_after)
    recovered = await limiter.check_rate_limit("user:alpha")
    assert recovered["allowed"] is True


@pytest.mark.parametrize("retry_after", [0, 1, 3, 9])
def test_rate_limit_exceeded_headers(retry_after: int):
    """Fuzz retry values to ensure headers consistently mirror limits."""
    exc = RateLimitExceeded(detail="Too many requests", retry_after=retry_after, limit=10, window=60)
    assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert exc.headers["Retry-After"] == str(retry_after)
    assert exc.headers["X-RateLimit-Limit"] == "10"


# ============================================================================
# Middleware matrix: per-IP, per-user, operator/bypass paths
# ============================================================================


@pytest.mark.anyio
async def test_rate_limit_middleware_tracks_ip_and_user(monkeypatch: pytest.MonkeyPatch):
    """Ensure middleware enforces per-IP and per-user identities and stamps headers."""
    limiter = AsyncMock()
    limiter.requests = 5
    limiter.check_rate_limit = AsyncMock(
        side_effect=[
            {"allowed": True, "remaining": 4, "reset": 111, "retry_after": 0},
            {"allowed": True, "remaining": 3, "reset": 222, "retry_after": 0},
        ]
    )

    async def get_user_id(_request):
        return "user-42"

    middleware = RateLimitMiddleware(
        app=AsyncMock(),
        redis_client=AsyncMock(),
        per_ip=True,
        per_user=True,
        get_user_id=get_user_id,
    )
    middleware.limiter = limiter

    request = build_request(path="/data", client_ip="198.51.100.10", forwarded_for="203.0.113.5")
    call_next = AsyncMock(return_value=Response(content=b"ok", status_code=200))

    response = await middleware.dispatch(request, call_next)

    limiter.check_rate_limit.assert_any_call("ip:203.0.113.5")
    limiter.check_rate_limit.assert_any_call("user:user-42")
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"


@pytest.mark.anyio
async def test_rate_limit_middleware_bypass_path_for_operator():
    """Operator/bypass paths should skip rate checks entirely."""
    limiter = AsyncMock()
    limiter.requests = 10

    async def get_user_id(_request):
        return "operator-1"

    middleware = RateLimitMiddleware(
        app=AsyncMock(),
        redis_client=AsyncMock(),
        per_ip=True,
        per_user=True,
        exclude_paths=["/ops/health"],
        get_user_id=get_user_id,
    )
    middleware.limiter = limiter

    request = build_request(path="/ops/health", client_ip="10.0.0.5")
    call_next = AsyncMock(return_value=Response(content=b"healthy", status_code=200))

    response = await middleware.dispatch(request, call_next)

    limiter.check_rate_limit.assert_not_called()
    assert response.status_code == 200


@pytest.mark.anyio
async def test_rate_limit_middleware_emits_retry_headers_on_exhaustion(caplog: pytest.LogCaptureFixture):
    """Validate throttling response, retry headers, and structured warnings."""
    limiter = AsyncMock()
    limiter.requests = 3
    limiter.check_rate_limit = AsyncMock(side_effect=RateLimitExceeded(retry_after=3, limit=3, window=10))

    middleware = RateLimitMiddleware(
        app=AsyncMock(),
        redis_client=AsyncMock(),
        per_ip=True,
        per_user=False,
    )
    middleware.limiter = limiter

    request = build_request(path="/throttle", client_ip="192.0.2.5")
    call_next = AsyncMock()

    with caplog.at_level(logging.WARNING):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.headers["Retry-After"] == "3"
    assert "Rate limit exceeded for ip:192.0.2.5" in caplog.text
    call_next.assert_not_awaited()
