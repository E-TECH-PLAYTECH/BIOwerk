"""FastAPI dependencies for authentication and authorization."""
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from .database import get_postgres_session
from .db_models import User, APIKey
from .auth import decode_token, verify_api_key
from .config import settings

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer(auto_error=False)


# ============================================================================
# JWT Authentication
# ============================================================================

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_postgres_session)
) -> Optional[User]:
    """
    Get current user from JWT token.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        User object if authenticated, None otherwise

    Raises:
        HTTPException: 401 if token is invalid or user not found
    """
    if not credentials:
        if settings.require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get current active user (raises exception if user is None or inactive).

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_active_user)):
            return {"user_id": user.id}
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return current_user


# ============================================================================
# API Key Authentication
# ============================================================================

async def get_user_from_api_key(
    api_key: Optional[str] = Header(None, alias=None),  # Will be set dynamically
    db: AsyncSession = Depends(get_postgres_session)
) -> Optional[User]:
    """
    Get user from API key header.

    Args:
        api_key: API key from header
        db: Database session

    Returns:
        User object if API key is valid, None otherwise
    """
    if not api_key:
        return None

    # Find API key in database
    stmt = select(APIKey).where(APIKey.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    api_keys = result.scalars().all()

    for db_api_key in api_keys:
        if verify_api_key(api_key, db_api_key.key_hash):
            # Update last_used_at
            from datetime import datetime
            db_api_key.last_used_at = datetime.utcnow()
            await db.commit()

            # Fetch user
            stmt = select(User).where(User.id == db_api_key.user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if user and user.is_active:
                return user

    return None


async def get_current_user_or_api_key(
    user_from_jwt: Optional[User] = Depends(get_current_user),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_postgres_session)
) -> Optional[User]:
    """
    Get current user from either JWT token or API key.

    Tries JWT first, then API key.

    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user_or_api_key)):
            if not user:
                raise HTTPException(401, "Not authenticated")
            return {"user_id": user.id}
    """
    if user_from_jwt:
        return user_from_jwt

    if x_api_key:
        user = await get_user_from_api_key(x_api_key, db)
        if user:
            return user

    return None


# ============================================================================
# Role-Based Access Control (RBAC)
# ============================================================================

def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Require admin role for endpoint.

    Usage:
        @app.post("/admin/users")
        async def create_user(user: User = Depends(require_admin)):
            # Only admins can access this
            return {"message": "Admin only"}
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_scopes(*required_scopes: str):
    """
    Require specific scopes from API key.

    Usage:
        @app.post("/sensitive")
        async def sensitive_route(user: User = Depends(require_scopes("read:sensitive", "write:sensitive"))):
            return {"message": "Authorized"}
    """
    async def _check_scopes(
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_postgres_session)
    ) -> User:
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required"
            )

        # Find API key
        stmt = select(APIKey).where(APIKey.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        api_keys = result.scalars().all()

        for db_api_key in api_keys:
            if verify_api_key(x_api_key, db_api_key.key_hash):
                # Check scopes
                key_scopes = db_api_key.scopes or []
                if not all(scope in key_scopes for scope in required_scopes):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required scopes: {required_scopes}"
                    )

                # Fetch user
                stmt = select(User).where(User.id == db_api_key.user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if user and user.is_active:
                    return user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return _check_scopes


# ============================================================================
# Optional Authentication
# ============================================================================

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_postgres_session)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise (no exception).

    Usage:
        @app.get("/public-or-private")
        async def endpoint(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"message": "Hello, authenticated user!"}
            return {"message": "Hello, anonymous user!"}
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
