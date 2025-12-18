"""Database connection management for PostgreSQL, MongoDB, and Redis."""
import asyncio
import logging
import random
import time
from typing import AsyncGenerator, Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from .config import settings

logger = logging.getLogger(__name__)


def _calculate_backoff_delay(attempt: int) -> float:
    """Calculate bounded exponential backoff delay with optional jitter."""
    base_delay = settings.retry_initial_delay
    delay = base_delay * (settings.retry_exponential_base ** (attempt - 1))
    delay = min(delay, settings.retry_max_delay)

    if settings.retry_jitter:
        delay += random.uniform(0, base_delay)

    return delay


async def _retry_async(operation_name: str, operation, fatal_exceptions: tuple = ()):
    """Run an async operation with bounded retries and backoff."""
    last_error = None
    max_attempts = settings.retry_max_attempts

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except fatal_exceptions as exc:  # type: ignore[misc]
            logger.error(
                "Fatal error while performing %s: %s", operation_name, exc,
                exc_info=True,
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive logging path
            last_error = exc
            delay = _calculate_backoff_delay(attempt)
            logger.warning(
                "Attempt %s/%s for %s failed: %s", attempt, max_attempts, operation_name, exc,
                exc_info=settings.log_level.upper() == "DEBUG",
            )

            if attempt >= max_attempts:
                break

            await asyncio.sleep(delay)

    raise RuntimeError(f"{operation_name} failed after {max_attempts} attempts") from last_error


def _retry_sync(operation_name: str, operation, fatal_exceptions: tuple = ()):  # pragma: no cover - thin sync wrapper
    """Run a sync operation with bounded retries and jitter-aware backoff."""
    last_error = None
    max_attempts = settings.retry_max_attempts

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except fatal_exceptions as exc:  # type: ignore[misc]
            logger.error(
                "Fatal error while performing %s: %s", operation_name, exc,
                exc_info=True,
            )
            raise
        except Exception as exc:
            last_error = exc
            delay = _calculate_backoff_delay(attempt)
            logger.warning(
                "Attempt %s/%s for %s failed: %s", attempt, max_attempts, operation_name, exc,
                exc_info=settings.log_level.upper() == "DEBUG",
            )

            if attempt >= max_attempts:
                break

            time.sleep(delay)

    raise RuntimeError(f"{operation_name} failed after {max_attempts} attempts") from last_error

# SQLAlchemy Base for ORM models
Base = declarative_base()

# Global database connections
_pg_engine = None
_pg_session_maker = None
_mongo_client = None
_mongo_db = None
_redis_client = None


# ============================================================================
# PostgreSQL Connection Management
# ============================================================================

def get_postgres_engine():
    """
    Get or create PostgreSQL async engine.

    Connection pooling is optimized based on whether PgBouncer is in use:
    - With PgBouncer (port 6432): Small application pools (5 + 5 overflow)
      PgBouncer handles the actual connection pooling to PostgreSQL
    - Direct PostgreSQL (port 5432): Larger application pools (10 + 20 overflow)
      Each service manages its own connection pool

    Using smaller pools with PgBouncer prevents over-subscription and
    allows PgBouncer to efficiently multiplex connections.

    HORIZONTAL SCALING CONSIDERATIONS:

    When running multiple replicas of a service, each replica creates its own
    connection pool. Total connection usage calculation:

    Example with 3 mesh instances and PgBouncer:
    - Per instance pool: 5 + 5 overflow = 10 max connections
    - 3 instances × 10 connections = 30 total connections to PgBouncer
    - PgBouncer pool (default 100) handles these efficiently

    Example with 3 mesh instances without PgBouncer:
    - Per instance pool: 10 + 20 overflow = 30 max connections
    - 3 instances × 30 connections = 90 total connections to PostgreSQL
    - PostgreSQL max_connections should be configured accordingly (e.g., 200+)

    **IMPORTANT**: When scaling horizontally:
    1. Always use PgBouncer in production to prevent connection exhaustion
    2. Configure PgBouncer pool size based on: (replicas × pool_size) + buffer
    3. Monitor connection usage with pg_stat_activity
    4. Set appropriate pool_size based on workload characteristics

    For services that scale to 10+ replicas:
    - Reduce pool_size to 3 + 3 overflow (6 max per instance)
    - This gives 60 connections for 10 instances (well within PgBouncer limits)
    - PgBouncer efficiently multiplexes to PostgreSQL backend pool
    """
    global _pg_engine
    if _pg_engine is None:
        # Detect if using PgBouncer based on port
        is_using_pgbouncer = settings.postgres_port == 6432 or settings.postgres_host == "pgbouncer"

        def _build_engine():
            if is_using_pgbouncer:
                # Smaller pools when using PgBouncer
                # PgBouncer handles connection pooling, so we don't need large app pools
                pool_size = 5
                max_overflow = 5
                logger.info("Using PgBouncer - configuring small application connection pool")
            else:
                # Larger pools for direct PostgreSQL connection
                pool_size = 10
                max_overflow = 20
                logger.info("Direct PostgreSQL connection - using standard connection pool")

            engine = create_async_engine(
                settings.postgres_url,
                echo=settings.log_level == "DEBUG",
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                # Pool recycle time - close connections after 1 hour
                # Prevents stale connections and works well with PgBouncer
                pool_recycle=3600,
                # Timeout for getting connection from pool
                pool_timeout=30,
            )
            logger.info(
                "PostgreSQL engine created: %s:%s (pool_size=%s, max_overflow=%s)",
                settings.postgres_host,
                settings.postgres_port,
                pool_size,
                max_overflow,
            )
            return engine

        try:
            _pg_engine = _retry_sync(
                "PostgreSQL engine initialization",
                _build_engine,
                fatal_exceptions=(ArgumentError,),
            )
        except Exception as exc:
            logger.critical(
                "Failed to initialize PostgreSQL engine for %s:%s/%s after %s attempts: %s",
                settings.postgres_host,
                settings.postgres_port,
                settings.postgres_db,
                settings.retry_max_attempts,
                exc,
            )
            raise
    return _pg_engine


def get_postgres_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create PostgreSQL session maker."""
    global _pg_session_maker
    if _pg_session_maker is None:
        engine = get_postgres_engine()
        _pg_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _pg_session_maker


async def get_postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get PostgreSQL session.

    Usage:
        @app.post("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_postgres_session)):
            # Use db session here
    """
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ping_postgres() -> float:
    """Execute a lightweight PostgreSQL connectivity probe."""
    session_maker = get_postgres_session_maker()
    start = time.time()
    async with session_maker() as session:
        result = await session.execute("SELECT 1")
        result.scalar_one()
    return round((time.time() - start) * 1000, 2)


async def ensure_postgres_ready() -> None:
    """Ensure PostgreSQL is reachable with bounded retries."""
    try:
        latency_ms = await _retry_async(
            "PostgreSQL connectivity",
            ping_postgres,
            fatal_exceptions=(ArgumentError,),
        )
        logger.info("PostgreSQL ready (%.2fms)", latency_ms)
    except Exception as exc:
        logger.critical(
            "PostgreSQL unreachable at %s:%s/%s after %s attempts: %s",
            settings.postgres_host,
            settings.postgres_port,
            settings.postgres_db,
            settings.retry_max_attempts,
            exc,
        )
        raise


async def close_postgres():
    """Close PostgreSQL connections."""
    global _pg_engine, _pg_session_maker
    if _pg_engine:
        await _pg_engine.dispose()
        _pg_engine = None
        _pg_session_maker = None
        logger.info("PostgreSQL connections closed")


# ============================================================================
# MongoDB Connection Management
# ============================================================================

def get_mongo_client() -> AsyncIOMotorClient:
    """Get or create MongoDB client."""
    global _mongo_client
    if _mongo_client is None:
        def _build_mongo_client() -> AsyncIOMotorClient:
            client = AsyncIOMotorClient(
                settings.mongo_url,
                maxPoolSize=50,
                minPoolSize=10,
            )
            logger.info(
                "MongoDB client created: %s:%s (db=%s)",
                settings.mongo_host,
                settings.mongo_port,
                settings.mongo_db,
            )
            return client

        try:
            _mongo_client = _retry_sync(
                "MongoDB client initialization",
                _build_mongo_client,
                fatal_exceptions=(ConfigurationError,),
            )
        except Exception as exc:
            logger.critical(
                "Failed to initialize MongoDB client for %s:%s/%s after %s attempts: %s",
                settings.mongo_host,
                settings.mongo_port,
                settings.mongo_db,
                settings.retry_max_attempts,
                exc,
            )
            raise
    return _mongo_client


def get_mongo_db():
    """Get MongoDB database instance."""
    global _mongo_db
    if _mongo_db is None:
        client = get_mongo_client()
        _mongo_db = client[settings.mongo_db]
    return _mongo_db


async def ping_mongo() -> float:
    """Execute a lightweight MongoDB connectivity probe."""
    client = get_mongo_client()
    start = time.time()
    await client.admin.command("ping")
    return round((time.time() - start) * 1000, 2)


async def ensure_mongo_ready() -> None:
    """Ensure MongoDB is reachable with bounded retries."""
    try:
        latency_ms = await _retry_async(
            "MongoDB connectivity",
            ping_mongo,
            fatal_exceptions=(ConfigurationError,),
        )
        logger.info("MongoDB ready (%.2fms)", latency_ms)
    except Exception as exc:
        logger.critical(
            "MongoDB unreachable at %s:%s/%s after %s attempts: %s",
            settings.mongo_host,
            settings.mongo_port,
            settings.mongo_db,
            settings.retry_max_attempts,
            exc,
        )
        raise


async def close_mongo():
    """Close MongoDB connections."""
    global _mongo_client, _mongo_db
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB connections closed")


# ============================================================================
# Redis Connection Management
# ============================================================================

def get_redis_client() -> Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        def _build_redis_client() -> Redis:
            client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=50,
            )
            logger.info(
                "Redis client created: %s:%s (db=%s)",
                settings.redis_host,
                settings.redis_port,
                settings.redis_db,
            )
            return client

        try:
            _redis_client = _retry_sync(
                "Redis client initialization",
                _build_redis_client,
                fatal_exceptions=(RedisError,),
            )
        except Exception as exc:
            logger.critical(
                "Failed to initialize Redis client for %s:%s/db%s after %s attempts: %s",
                settings.redis_host,
                settings.redis_port,
                settings.redis_db,
                settings.retry_max_attempts,
                exc,
            )
            raise
    return _redis_client


async def ping_redis() -> float:
    """Execute a lightweight Redis connectivity probe."""
    client = get_redis_client()
    start = time.time()
    await client.ping()
    return round((time.time() - start) * 1000, 2)


async def ensure_redis_ready() -> None:
    """Ensure Redis is reachable with bounded retries."""
    try:
        latency_ms = await _retry_async(
            "Redis connectivity",
            ping_redis,
            fatal_exceptions=(RedisError,),
        )
        logger.info("Redis ready (%.2fms)", latency_ms)
    except Exception as exc:
        logger.critical(
            "Redis unreachable at %s:%s/db%s after %s attempts: %s",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
            settings.retry_max_attempts,
            exc,
        )
        raise


async def close_redis():
    """Close Redis connections."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connections closed")


# ============================================================================
# Session Management
# ============================================================================

def get_session_manager(session_type: str = "default"):
    """
    Get a configured session manager for storing session state in Redis.

    Args:
        session_type: Type of session ("short", "default", "long", "workflow")

    Returns:
        RedisSessionManager instance configured for the specified session type

    Usage:
        session_mgr = get_session_manager("workflow")
        await session_mgr.set("msg_123", {"outline": ["Intro", "Body", "Conclusion"]})
        data = await session_mgr.get("msg_123")
    """
    from .sessions import RedisSessionManager

    redis = get_redis_client()

    ttl_map = {
        "short": settings.session_ttl_short,
        "default": settings.session_ttl_default,
        "long": settings.session_ttl_long,
        "workflow": settings.session_ttl_workflow,
    }

    prefix_map = {
        "short": f"{settings.session_prefix}:short",
        "default": settings.session_prefix,
        "long": f"{settings.session_prefix}:long",
        "workflow": f"{settings.session_prefix}:workflow",
    }

    ttl = ttl_map.get(session_type, settings.session_ttl_default)
    prefix = prefix_map.get(session_type, settings.session_prefix)

    return RedisSessionManager(
        redis_client=redis,
        prefix=prefix,
        default_ttl=ttl
    )


# ============================================================================
# Application Lifecycle Management
# ============================================================================

async def init_databases():
    """Initialize all database connections."""
    logger.info("Initializing database connections...")
    await asyncio.gather(
        ensure_postgres_ready(),
        ensure_mongo_ready(),
        ensure_redis_ready(),
    )
    logger.info("All database connections initialized and verified")


async def close_databases():
    """Close all database connections."""
    logger.info("Closing database connections...")
    await close_postgres()
    await close_mongo()
    await close_redis()
    logger.info("All database connections closed")


async def create_tables():
    """Create all PostgreSQL tables."""
    engine = get_postgres_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables created")
