"""Unit tests for API key identifier-based lookups."""
from datetime import datetime, timedelta
import hashlib
import hmac
import importlib.util
from pathlib import Path
import sys
import types

import pytest
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, Index, JSON, String
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

try:
    import aiosqlite  # noqa: F401
except ImportError:  # pragma: no cover - environment guard
    pytest.skip("aiosqlite not available in test environment", allow_module_level=True)

# ---------------------------------------------------------------------------
# Test-time stubs to decouple the matrix package from heavy optional deps
# ---------------------------------------------------------------------------

if "blake3" not in sys.modules:
    class _Blake3Digest:
        def __init__(self, data: bytes = b""):
            self._hasher = hashlib.blake2s(data)

        def update(self, data: bytes) -> None:
            self._hasher.update(data)

        def hexdigest(self) -> str:
            return self._hasher.hexdigest()

    sys.modules["blake3"] = types.SimpleNamespace(blake3=lambda data=None: _Blake3Digest(data or b""))


# Stub matrix package root to avoid loading the real package during import
matrix_pkg = types.ModuleType("matrix")
matrix_pkg.__path__ = [str(Path(__file__).resolve().parents[2] / "matrix")]
sys.modules["matrix"] = matrix_pkg


# Infrastructure dependency stubs
for module_name, module_obj in [
    ("redis", types.ModuleType("redis")),
    ("motor", types.ModuleType("motor")),
    ("pymongo", types.ModuleType("pymongo")),
]:
    module_obj.__path__ = []
    sys.modules[module_name] = module_obj

redis_async = types.ModuleType("redis.asyncio")
redis_async.Redis = type("Redis", (), {"from_url": classmethod(lambda cls, *_args, **_kwargs: cls())})
sys.modules["redis.asyncio"] = redis_async

redis_exceptions = types.ModuleType("redis.exceptions")
redis_exceptions.RedisError = Exception
sys.modules["redis.exceptions"] = redis_exceptions

motor_asyncio = types.ModuleType("motor.motor_asyncio")
motor_asyncio.AsyncIOMotorClient = type("AsyncIOMotorClient", (), {})
sys.modules["motor.motor_asyncio"] = motor_asyncio

pymongo_errors = types.ModuleType("pymongo.errors")
pymongo_errors.ConfigurationError = Exception
sys.modules["pymongo.errors"] = pymongo_errors

pymongo_cursor = types.ModuleType("pymongo.cursor")
pymongo_cursor._QUERY_OPTIONS = None
pymongo_cursor.Cursor = type("Cursor", (), {})
pymongo_cursor.RawBatchCursor = type("RawBatchCursor", (), {})
sys.modules["pymongo.cursor"] = pymongo_cursor

matrix_cache_stub = types.ModuleType("matrix.cache")
matrix_cache_stub.cache = None
matrix_cache_stub.cached = lambda func=None, **_kwargs: func if func else (lambda f: f)
sys.modules["matrix.cache"] = matrix_cache_stub


# Minimal ORM models for the auth dependency module
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, index=True)
    key_identifier = Column(String(128), nullable=True)
    name = Column(String(255), nullable=False)
    scopes = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_api_keys_identifier", "key_identifier", unique=True),
        Index("idx_api_keys_expiry", "expires_at"),
        Index("idx_api_keys_active_expiry", "is_active", "expires_at"),
    )


db_models_stub = types.ModuleType("matrix.db_models")
db_models_stub.APIKey = APIKey
db_models_stub.User = User
db_models_stub.Base = Base
db_models_stub.__spec__ = importlib.util.spec_from_loader("matrix.db_models", loader=None)
sys.modules["matrix.db_models"] = db_models_stub


token_repo_stub = types.ModuleType("matrix.token_repository")
token_repo_stub.RefreshTokenRepository = type("RefreshTokenRepository", (), {})
token_repo_stub.__spec__ = importlib.util.spec_from_loader("matrix.token_repository", loader=None)
sys.modules["matrix.token_repository"] = token_repo_stub


# Auth stub mirroring the production hashing/identifier strategy
auth_stub = types.ModuleType("matrix.auth")
auth_stub.settings = types.SimpleNamespace(jwt_secret_key="test-secret")
auth_stub.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_api_key(api_key: str) -> str:
    return auth_stub.pwd_context.hash(api_key)


def _verify_api_key(api_key: str, hashed: str) -> bool:
    return auth_stub.pwd_context.verify(api_key, hashed)


def _derive_api_key_identifier(api_key: str) -> str:
    secret = auth_stub.settings.jwt_secret_key.encode()
    return hmac.new(secret, api_key.encode(), hashlib.sha256).hexdigest()


def _decode_token(_token: str):
    return None


auth_stub.hash_api_key = _hash_api_key
auth_stub.verify_api_key = _verify_api_key
auth_stub.derive_api_key_identifier = _derive_api_key_identifier
auth_stub.decode_token = _decode_token
auth_stub.__spec__ = importlib.util.spec_from_loader("matrix.auth", loader=None)
sys.modules["matrix.auth"] = auth_stub


auth_dep_path = Path(__file__).resolve().parents[2] / "matrix" / "auth_dependencies.py"
auth_dep_source = auth_dep_path.read_text()
auth_dep_source = auth_dep_source.replace(
    "from .db_models import User, APIKey",
    "from matrix.db_models import User, APIKey",
)
auth_dep_source = auth_dep_source.replace(
    "from .auth import decode_token, verify_api_key, derive_api_key_identifier",
    "from matrix.auth import decode_token, verify_api_key, derive_api_key_identifier",
)

auth_dependencies = types.ModuleType("matrix.auth_dependencies")
exec(compile(auth_dep_source, str(auth_dep_path), "exec"), auth_dependencies.__dict__)
sys.modules["matrix.auth_dependencies"] = auth_dependencies


from matrix.auth import derive_api_key_identifier, hash_api_key  # type: ignore  # noqa: E402
from matrix.auth_dependencies import _get_valid_api_key  # type: ignore  # noqa: E402


@pytest.fixture()
async def db_session():
    """Provide an isolated in-memory database for API key tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[APIKey.__table__])

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.anyio
async def test_valid_api_key_updates_last_used(db_session):
    """Valid keys resolve via identifier lookup and update last_used_at."""
    plain_key = "test-valid-key"
    api_key = APIKey(
        user_id="user-123",
        key_hash=hash_api_key(plain_key),
        key_identifier=derive_api_key_identifier(plain_key),
        name="integration-agent",
        scopes=["read"],
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )

    db_session.add(api_key)
    await db_session.commit()

    resolved = await _get_valid_api_key(plain_key, db_session)

    assert resolved is not None
    assert resolved.last_used_at is not None
    assert resolved.id == api_key.id


@pytest.mark.anyio
async def test_expired_api_key_returns_unauthorized_without_verification(db_session, monkeypatch):
    """Expired keys short-circuit before bcrypt verification and raise 401."""
    plain_key = "expired-key"
    expired_key = APIKey(
        user_id="user-456",
        key_hash=hash_api_key(plain_key),
        key_identifier=derive_api_key_identifier(plain_key),
        name="expired-agent",
        scopes=[],
        is_active=True,
        expires_at=datetime.utcnow() - timedelta(hours=1),
    )

    db_session.add(expired_key)
    await db_session.commit()

    # Ensure bcrypt verification is never invoked for expired keys
    monkeypatch.setattr(
        "matrix.auth_dependencies.verify_api_key",
        lambda *_args, **_kwargs: pytest.fail("verify_api_key should not be called for expired keys"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_valid_api_key(plain_key, db_session)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
