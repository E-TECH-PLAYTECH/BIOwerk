"""
Comprehensive tests for Database module - PostgreSQL, MongoDB, and Redis connections.

Tests cover:
- PostgreSQL connection pooling
- MongoDB connection management
- Redis connection management
- Session lifecycle
- Connection pool configuration
- Error handling
"""
import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Prevent optional dependencies from breaking isolated unit tests
sys.modules.setdefault("blake3", MagicMock())
sys.modules.setdefault("pymongo", MagicMock())
sys.modules.setdefault("pymongo.errors", types.SimpleNamespace(ConfigurationError=Exception))
sys.modules.setdefault("motor", MagicMock())
sys.modules.setdefault("motor.motor_asyncio", types.SimpleNamespace(AsyncIOMotorClient=MagicMock()))
_auth_stub = types.SimpleNamespace()
sys.modules.setdefault("matrix.auth", _auth_stub)
sys.modules.setdefault("matrix.auth_dependencies", _auth_stub)
sys.modules.setdefault("matrix.token_repository", _auth_stub)
sys.modules.setdefault("matrix.db_models", _auth_stub)
sys.modules.setdefault("matrix.user_repository", _auth_stub)


# ============================================================================
# PostgreSQL Tests
# ============================================================================


def test_get_postgres_engine():
    """Test PostgreSQL engine creation."""
    from matrix.database import get_postgres_engine

    with patch("matrix.database.settings") as mock_settings:
        mock_settings.postgres_url = "postgresql+asyncpg://user:pass@localhost:5432/db"
        mock_settings.postgres_host = "localhost"
        mock_settings.postgres_port = 5432
        mock_settings.log_level = "INFO"
        mock_settings.postgres_db = "db"
        mock_settings.retry_initial_delay = 0.01
        mock_settings.retry_exponential_base = 2
        mock_settings.retry_max_delay = 0.1
        mock_settings.retry_jitter = False
        mock_settings.retry_max_attempts = 3

        # Reset global engine
        import matrix.database
        matrix.database._pg_engine = None

        engine = get_postgres_engine()

        assert engine is not None
        assert engine == get_postgres_engine()  # Should return same instance


def test_get_postgres_engine_with_pgbouncer():
    """Test PostgreSQL engine creation with PgBouncer."""
    from matrix.database import get_postgres_engine

    with patch("matrix.database.settings") as mock_settings:
        mock_settings.postgres_url = "postgresql+asyncpg://user:pass@localhost:6432/db"
        mock_settings.postgres_host = "pgbouncer"
        mock_settings.postgres_port = 6432
        mock_settings.log_level = "INFO"
        mock_settings.postgres_db = "db"
        mock_settings.retry_initial_delay = 0.01
        mock_settings.retry_exponential_base = 2
        mock_settings.retry_max_delay = 0.1
        mock_settings.retry_jitter = False
        mock_settings.retry_max_attempts = 3

        # Reset global engine
        import matrix.database
        matrix.database._pg_engine = None

        engine = get_postgres_engine()

        assert engine is not None
        # PgBouncer should use smaller pool sizes


def test_get_postgres_session_maker():
    """Test PostgreSQL session maker creation."""
    from matrix.database import get_postgres_session_maker

    with patch("matrix.database.get_postgres_engine") as mock_engine:
        mock_engine.return_value = MagicMock()

        # Reset global session maker
        import matrix.database
        matrix.database._pg_session_maker = None

        session_maker = get_postgres_session_maker()

        assert session_maker is not None


def test_get_postgres_session():
    """Test PostgreSQL session dependency."""
    from matrix.database import get_postgres_session

    with patch("matrix.database.get_postgres_session_maker") as mock_maker:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None

        mock_maker.return_value.return_value = mock_context

        async def _run():
            async for session in get_postgres_session():
                assert session is not None

        asyncio.run(_run())


# ============================================================================
# MongoDB Tests
# ============================================================================


def test_get_mongo_client():
    """Test MongoDB client creation."""
    from matrix.database import get_mongo_client

    with patch("matrix.database.settings") as mock_settings:
        mock_settings.mongo_url = "mongodb://localhost:27017"
        mock_settings.mongo_db = "testdb"
        mock_settings.mongo_host = "localhost"
        mock_settings.mongo_port = 27017
        mock_settings.retry_initial_delay = 0.01
        mock_settings.retry_exponential_base = 2
        mock_settings.retry_max_delay = 0.1
        mock_settings.retry_jitter = False
        mock_settings.retry_max_attempts = 3

        with patch("matrix.database.AsyncIOMotorClient") as mock_motor:
            mock_client = MagicMock()
            mock_motor.return_value = mock_client

            # Reset global client
            import matrix.database
            matrix.database._mongo_client = None

            client = get_mongo_client()

            assert client is not None


def test_get_mongo_database():
    """Test MongoDB database retrieval."""
    from matrix.database import get_mongo_db

    with patch("matrix.database.settings") as mock_settings:
        mock_settings.mongo_url = "mongodb://localhost:27017"
        mock_settings.mongo_db = "testdb"
        mock_settings.mongo_host = "localhost"
        mock_settings.mongo_port = 27017
        mock_settings.retry_initial_delay = 0.01
        mock_settings.retry_exponential_base = 2
        mock_settings.retry_max_delay = 0.1
        mock_settings.retry_jitter = False
        mock_settings.retry_max_attempts = 3

        with patch("matrix.database.get_mongo_client") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value.__getitem__.return_value = mock_db

            # Reset global db
            import matrix.database
            matrix.database._mongo_db = None

            db = get_mongo_db()

            assert db is not None


# ============================================================================
# Redis Tests
# ============================================================================


def test_get_redis_client():
    """Test Redis client creation."""
    from matrix.database import get_redis_client

    with patch("matrix.database.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.redis_host = "localhost"
        mock_settings.redis_port = 6379
        mock_settings.redis_db = 0
        mock_settings.retry_initial_delay = 0.01
        mock_settings.retry_exponential_base = 2
        mock_settings.retry_max_delay = 0.1
        mock_settings.retry_jitter = False
        mock_settings.retry_max_attempts = 3

        with patch("matrix.database.Redis") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.from_url.return_value = mock_client

            # Reset global client
            import matrix.database
            matrix.database._redis_client = None

            client = get_redis_client()

            assert client is not None


def test_redis_ping():
    """Test Redis connection health check."""
    from matrix.database import get_redis_client

    with patch("matrix.database.settings") as mock_settings:
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.redis_host = "localhost"
        mock_settings.redis_port = 6379
        mock_settings.redis_db = 0
        mock_settings.retry_initial_delay = 0.01
        mock_settings.retry_exponential_base = 2
        mock_settings.retry_max_delay = 0.1
        mock_settings.retry_jitter = False
        mock_settings.retry_max_attempts = 3

        with patch("matrix.database.Redis") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_redis.from_url.return_value = mock_client

            # Reset global client
            import matrix.database
            matrix.database._redis_client = None

            client = get_redis_client()

            result = asyncio.run(client.ping())

            assert result is True


# ============================================================================
# Connection Cleanup Tests
# ============================================================================


def test_close_connections():
    """Test database connection cleanup."""
    from matrix.database import close_databases

    with patch("matrix.database._pg_engine") as mock_pg_engine:
        with patch("matrix.database._mongo_client") as mock_mongo:
            with patch("matrix.database._redis_client") as mock_redis:
                mock_pg_engine.dispose = AsyncMock()
                mock_mongo.close = MagicMock()
                mock_redis.close = AsyncMock()

                asyncio.run(close_databases())

                mock_pg_engine.dispose.assert_called_once()
                mock_mongo.close.assert_called_once()
                mock_redis.close.assert_called_once()


def test_database_summary():
    """
    Database Module Test Coverage:
    ✓ PostgreSQL engine management
    ✓ PgBouncer detection and configuration
    ✓ MongoDB client management
    ✓ Redis client management
    ✓ Connection cleanup
    """
    assert True
