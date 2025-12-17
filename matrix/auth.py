"""Authentication utilities for JWT tokens and password hashing."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import hmac
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .token_repository import RefreshTokenRepository

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================================
# Password Hashing
# ============================================================================

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT Token Management
# ============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token (typically {"sub": user_id})
        expires_delta: Token expiration time (default: from settings)

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def create_refresh_token(
    data: Dict[str, Any],
    db: AsyncSession,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
    jti: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Create a JWT refresh token with longer expiration and persist its metadata.

    Args:
        data: Data to encode in the token
        db: Database session for persisting the refresh token metadata
        user_agent: Optional user agent string to capture token provenance
        ip_address: Optional IP address for token provenance
        jti: Optional pre-generated JWT ID to embed; generated if omitted

    Returns:
        Tuple of (encoded JWT refresh token, jti)
    """
    if "sub" not in data or not data.get("sub"):
        raise ValueError("Refresh tokens must include a subject (`sub`) claim.")

    to_encode = data.copy()
    jti = to_encode.get("jti") or jti or RefreshTokenRepository.generate_jti()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": jti,
        }
    )
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    token_repo = RefreshTokenRepository(db)
    await token_repo.create_token(
        user_id=to_encode["sub"],
        jti=jti,
        expires_at=expire,
        user_agent=user_agent,
        ip_address=ip_address,
        commit=True,
    )

    return encoded_jwt, jti


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from JWT token.

    Args:
        token: JWT token string

    Returns:
        User ID or None if invalid
    """
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None


# ============================================================================
# API Key Management
# ============================================================================

def generate_api_key() -> str:
    """
    Generate a secure random API key.

    Returns:
        Random API key (32 bytes as hex string)
    """
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage.

    Args:
        api_key: Plain API key

    Returns:
        Hashed API key
    """
    return pwd_context.hash(api_key)


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """
    Verify an API key against its hash.

    Args:
        plain_api_key: Plain API key from request
        hashed_api_key: Hashed API key from database

    Returns:
        True if API key matches, False otherwise
    """
    return pwd_context.verify(plain_api_key, hashed_api_key)


def derive_api_key_identifier(api_key: str) -> str:
    """
    Derive a stable, non-reversible identifier for an API key.

    This uses an HMAC-SHA256 digest keyed by the JWT secret to avoid leaking
    raw key material while still enabling indexed lookups.

    Args:
        api_key: Plain API key

    Returns:
        Hex-encoded identifier suitable for indexed storage
    """
    secret = settings.jwt_secret_key.encode()
    return hmac.new(secret, api_key.encode(), hashlib.sha256).hexdigest()


# ============================================================================
# Token Models
# ============================================================================

class TokenData:
    """Data extracted from JWT token."""

    def __init__(self, user_id: str, scopes: list = None):
        self.user_id = user_id
        self.scopes = scopes or []


class TokenResponse:
    """Response model for token endpoints."""

    def __init__(self, access_token: str, refresh_token: Optional[str] = None, token_type: str = "bearer"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type

    def dict(self):
        result = {
            "access_token": self.access_token,
            "token_type": self.token_type
        }
        if self.refresh_token:
            result["refresh_token"] = self.refresh_token
        return result
