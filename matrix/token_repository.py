"""Repository utilities for managing refresh tokens and their lifecycle."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import RefreshToken


class RefreshTokenRepository:
    """Persistence helpers for refresh token creation, rotation, and revocation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def generate_jti() -> str:
        """Create a new JTI identifier."""
        return str(uuid4())

    async def create_token(
        self,
        user_id: str,
        jti: str,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        commit: bool = True,
    ) -> RefreshToken:
        """
        Persist a refresh token metadata record.

        Args:
            user_id: ID of the token subject.
            jti: Unique token identifier to embed in the JWT.
            expires_at: Expiration timestamp matching the JWT payload.
            user_agent: Optional user agent string for auditing.
            ip_address: Optional IP address for auditing.
            commit: Whether to commit immediately (default) or defer to caller.
        """
        token = RefreshToken(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(token)
        if commit:
            await self.db.commit()
            await self.db.refresh(token)
        else:
            await self.db.flush()
        return token

    async def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """Fetch a refresh token by its JTI."""
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """Fetch an active (non-revoked, non-rotated, unexpired) refresh token by JTI."""
        now = datetime.utcnow()
        stmt = select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.rotated_at.is_(None),
            RefreshToken.expires_at > now,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_for_user(self, jti: str, user_id: str) -> Optional[RefreshToken]:
        """Fetch an active refresh token scoped to a specific user."""
        now = datetime.utcnow()
        stmt = select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.rotated_at.is_(None),
            RefreshToken.expires_at > now,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_by_jti(self, jti: str, reason: Optional[str] = None) -> bool:
        """Revoke a refresh token by JTI if it is not already revoked."""
        now = datetime.utcnow()
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason or "revoked")
        )
        result = await self.db.execute(stmt)
        if result.rowcount:
            await self.db.commit()
            return True
        return False

    async def revoke_tokens_for_user(self, user_id: str, reason: Optional[str] = None) -> int:
        """Revoke all active refresh tokens for a user."""
        now = datetime.utcnow()
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason=reason or "revoked")
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def mark_rotated(
        self,
        token: RefreshToken,
        replaced_by_jti: Optional[str] = None,
        revoke: bool = True,
        commit: bool = False,
    ) -> RefreshToken:
        """
        Mark a refresh token as rotated, optionally revoking it.

        Args:
            token: RefreshToken instance to update.
            replaced_by_jti: JTI of the newly issued token, if applicable.
            revoke: Whether to mark the token revoked alongside rotation.
            commit: Whether to commit immediately (default False to allow batched commits).
        """
        now = datetime.utcnow()
        token.last_used_at = now
        token.rotated_at = now
        token.replaced_by_jti = replaced_by_jti
        if revoke:
            token.revoked_at = token.revoked_at or now
            token.revoked_reason = token.revoked_reason or "rotated"

        if commit:
            await self.db.commit()
            await self.db.refresh(token)
        else:
            await self.db.flush()

        return token
