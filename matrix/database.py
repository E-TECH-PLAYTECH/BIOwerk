"""Database connection management for PostgreSQL, MongoDB, and Redis."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis
from typing import AsyncGenerator, Optional
import logging

from .config import settings

logger = logging.getLogger(__name__)

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
    """Get or create PostgreSQL async engine."""
    global _pg_engine
    if _pg_engine is None:
        _pg_engine = create_async_engine(
            settings.postgres_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        logger.info(f"PostgreSQL engine created: {settings.postgres_host}:{settings.postgres_port}")
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
        _mongo_client = AsyncIOMotorClient(
            settings.mongo_url,
            maxPoolSize=50,
            minPoolSize=10,
        )
        logger.info(f"MongoDB client created: {settings.mongo_host}:{settings.mongo_port}")
    return _mongo_client


def get_mongo_db():
    """Get MongoDB database instance."""
    global _mongo_db
    if _mongo_db is None:
        client = get_mongo_client()
        _mongo_db = client[settings.mongo_db]
    return _mongo_db


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
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
        logger.info(f"Redis client created: {settings.redis_host}:{settings.redis_port}")
    return _redis_client


async def close_redis():
    """Close Redis connections."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connections closed")


# ============================================================================
# Application Lifecycle Management
# ============================================================================

async def init_databases():
    """Initialize all database connections."""
    logger.info("Initializing database connections...")
    get_postgres_engine()
    get_mongo_client()
    get_redis_client()
    logger.info("All database connections initialized")


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
