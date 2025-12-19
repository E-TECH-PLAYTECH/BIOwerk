import importlib
import importlib.machinery
import pathlib
import sys
import types
from datetime import datetime, timedelta

import pytest
pytest.importorskip("aiosqlite")
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


class FakeRedis:
    """Minimal Redis stub for tests without external dependencies."""

    @classmethod
    def from_url(cls, *_, **__):
        return cls()

    async def get(self, *_, **__):
        return None

    async def setex(self, *_, **__):
        return True

    async def delete(self, *_, **__):
        return 0

    async def scan_iter(self, *_, **__):
        if False:
            yield b""
        return

    async def exists(self, *_, **__):
        return 0

    async def incrby(self, *_, **__):
        return 0


fake_blake3_module = types.SimpleNamespace(
    blake3=lambda _: types.SimpleNamespace(hexdigest=lambda: "0" * 64),
)
fake_motor_module = types.ModuleType("motor")
fake_motor_asyncio = types.SimpleNamespace(AsyncIOMotorClient=lambda *_, **__: None)
fake_pymongo_module = types.ModuleType("pymongo")
fake_pymongo_errors = types.SimpleNamespace(ConfigurationError=Exception)
fake_pymongo_cursor = types.SimpleNamespace(
    _QUERY_OPTIONS=None, Cursor=object, RawBatchCursor=object
)
fake_redis_module = types.ModuleType("redis")
fake_redis_asyncio = types.SimpleNamespace(Redis=FakeRedis)
fake_redis_exceptions = types.SimpleNamespace(RedisError=Exception)

sys.modules.setdefault("blake3", fake_blake3_module)
sys.modules.setdefault("motor", fake_motor_module)
sys.modules.setdefault("motor.motor_asyncio", fake_motor_asyncio)
sys.modules.setdefault("pymongo", fake_pymongo_module)
sys.modules.setdefault("pymongo.errors", fake_pymongo_errors)
sys.modules.setdefault("pymongo.cursor", fake_pymongo_cursor)
sys.modules.setdefault("redis", fake_redis_module)
sys.modules.setdefault("redis.asyncio", fake_redis_asyncio)
sys.modules.setdefault("redis.exceptions", fake_redis_exceptions)

# Create a lightweight matrix package stub to load the repository without full dependencies
Base = declarative_base()


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    exp = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    rotated_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    replaced_by_jti = Column(String(36), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)


matrix_stub = types.ModuleType("matrix")
matrix_stub.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / "matrix")]
matrix_stub.__spec__ = importlib.machinery.ModuleSpec("matrix", loader=None, is_package=True)
sys.modules["matrix"] = matrix_stub

db_models_stub = types.ModuleType("matrix.db_models")
db_models_stub.RefreshToken = RefreshToken
db_models_stub.Base = Base
sys.modules["matrix.db_models"] = db_models_stub

token_repository = importlib.import_module("matrix.token_repository")
RefreshTokenRepository = token_repository.RefreshTokenRepository
matrix_auth = importlib.import_module("matrix.auth")


async def _build_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    session = async_session()
    return engine, session


def test_refresh_token_status_lifecycle():
    async def _run():
        engine, session = await _build_session()
        try:
            repo = RefreshTokenRepository(session)
            user_id = "user-123"
            expires_at = datetime.utcnow() + timedelta(days=1)

            token = await repo.create_token(user_id=user_id, jti="jti-1", expires_at=expires_at, commit=True)

            assert token.status == "active"
            assert token.exp == expires_at

            active = await repo.get_active_for_user("jti-1", user_id)
            assert active is not None

            await repo.revoke_by_jti("jti-1", reason="logout")
            revoked = await repo.get_by_jti("jti-1")
            assert revoked.status == "logout"
            assert revoked.revoked_reason == "logout"
        finally:
            await session.close()
            await engine.dispose()

    import asyncio
    asyncio.run(_run())


def test_refresh_token_rotation_marks_old_token():
    async def _run():
        engine, session = await _build_session()
        try:
            repo = RefreshTokenRepository(session)
            user_id = "user-rotation"
            expires_at = datetime.utcnow() + timedelta(days=1)

            token = await repo.create_token(user_id=user_id, jti="jti-old", expires_at=expires_at, commit=False)
            await repo.mark_rotated(token, replaced_by_jti="jti-new", revoke=True, commit=True)

            rotated = await repo.get_by_jti("jti-old")
            assert rotated.replaced_by_jti == "jti-new"
            assert rotated.status == "revoked"
            assert rotated.revoked_reason == "rotated"
        finally:
            await session.close()
            await engine.dispose()

    import asyncio
    asyncio.run(_run())


def test_rotate_active_token_atomic_and_single_use():
    async def _run():
        engine, session = await _build_session()
        try:
            repo = RefreshTokenRepository(session)
            user_id = "user-rotation-atomic"
            expires_at = datetime.utcnow() + timedelta(days=1)

            await repo.create_token(user_id=user_id, jti="atomic-jti-old", expires_at=expires_at, commit=False)

            rotated = await repo.rotate_active_token(
                jti="atomic-jti-old",
                user_id=user_id,
                replaced_by_jti="atomic-jti-new",
                commit=True,
            )
            assert rotated is not None
            assert rotated.status == "revoked"
            assert rotated.revoked_reason == "rotated"
            assert rotated.replaced_by_jti == "atomic-jti-new"
            assert rotated.rotated_at is not None
            first_revocation_time = rotated.revoked_at

            double_rotate = await repo.rotate_active_token(
                jti="atomic-jti-old",
                user_id=user_id,
                replaced_by_jti="atomic-jti-newer",
                commit=True,
            )
            assert double_rotate is None

            persisted = await repo.get_by_jti("atomic-jti-old")
            assert persisted.revoked_at == first_revocation_time
            assert persisted.status == "revoked"
        finally:
            await session.close()
            await engine.dispose()

    import asyncio
    asyncio.run(_run())


def test_create_refresh_token_persists_jti_and_metadata():
    async def _run():
        engine, session = await _build_session()
        try:
            data = {"sub": "user-create-jti"}
            refresh_token, jti = await matrix_auth.create_refresh_token(
                data=data,
                db=session,
                user_agent="pytest-agent",
                ip_address="127.0.0.1",
            )

            payload = matrix_auth.decode_token(refresh_token)
            assert payload is not None
            assert payload.get("jti") == jti
            assert payload.get("type") == "refresh"
            assert payload.get("sub") == data["sub"]

            repo = RefreshTokenRepository(session)
            record = await repo.get_by_jti(jti)
            assert record is not None
            assert record.user_id == data["sub"]
            assert record.user_agent == "pytest-agent"
            assert record.ip_address == "127.0.0.1"
            assert record.exp >= datetime.utcnow()
        finally:
            await session.close()
            await engine.dispose()

    import asyncio
    asyncio.run(_run())
