"""
Standalone authentication service for BIOwerk.

This service provides user registration, login, token management, and API key management.
It can be run as a standalone microservice or integrated into the mesh gateway.

Usage:
    uvicorn auth_service:app --host 0.0.0.0 --port 8100
"""
from fastapi import Body, FastAPI, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime, timedelta

from matrix.database import get_postgres_session, init_databases
from matrix.db_models import User, APIKey
from matrix.user_repository import UserRepository, APIKeyRepository
from matrix.token_repository import RefreshTokenRepository
from matrix.auth import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenResponse,
    derive_api_key_identifier,
    generate_api_key,
)
from matrix.auth_dependencies import get_current_active_user, require_admin
from matrix.observability import setup_instrumentation
from matrix.logging_config import setup_logging
from matrix.audit import AuditLogger, AuditContext, EventStatus

# Initialize app
app = FastAPI(title="BIOwerk Auth Service", version="1.0.0")
setup_instrumentation(app)
logger = setup_logging("auth_service")
audit_logger = AuditLogger()


# ============================================================================
# Request/Response Models
# ============================================================================

class UserRegister(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User response (without sensitive data)."""
    id: str
    email: str
    username: str
    auth_provider: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response with tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request that optionally carries the refresh token being invalidated."""

    refresh_token: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Password change request for authenticated users."""

    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


class APIKeyCreate(BaseModel):
    """API key creation request."""
    name: str = Field(..., min_length=1, max_length=255)
    scopes: Optional[List[str]] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API key response."""
    id: str
    name: str
    key: Optional[str] = None  # Only returned on creation
    scopes: Optional[List[str]]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize database connections on startup."""
    await init_databases()
    logger.info("Auth service started")


# ============================================================================
# Public Endpoints (No Authentication Required)
# ============================================================================

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Register a new user.

    - **email**: Valid email address
    - **username**: Unique username (3-50 characters)
    - **password**: Strong password (min 8 characters)
    """
    repo = UserRepository(db)

    # Check if email already exists
    existing_user = await repo.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username already exists
    existing_user = await repo.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create user
    user = await repo.create_user(
        email=user_data.email,
        username=user_data.username,
        password=user_data.password,
        auth_provider="local"
    )

    logger.info(f"New user registered: {user.email} (ID: {user.id})")

    return UserResponse.model_validate(user)


@app.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Login with username/email and password.

    Returns access token and refresh token.

    - **username**: Username or email
    - **password**: User password
    """
    repo = UserRepository(db)

    # Try to find user by email or username
    user = await repo.get_user_by_email(form_data.username)
    if not user:
        user = await repo.get_user_by_username(form_data.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Verify password
    if not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token, _ = await create_refresh_token(
        data={"sub": user.id},
        db=db,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    logger.info(f"User logged in: {user.email} (ID: {user.id})")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@app.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    logout_request: LogoutRequest = Body(default_factory=LogoutRequest),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_postgres_session),
):
    """
    Logout the current user and revoke all of their refresh tokens.

    - **refresh_token**: Optional refresh token to explicitly revoke alongside the blanket revocation.
    """
    context = AuditContext.from_request(request, service_name="auth")
    context.user_id = current_user.id
    context.username = current_user.username

    token_repo = RefreshTokenRepository(db)
    provided_jti: Optional[str] = None
    invalid_refresh_reason: Optional[str] = None

    if logout_request and logout_request.refresh_token:
        payload = decode_token(logout_request.refresh_token)
        provided_jti = payload.get("jti") if payload else None

        if not payload or payload.get("type") != "refresh":
            invalid_refresh_reason = "Invalid refresh token payload provided during logout"
        elif payload.get("sub") != current_user.id or not provided_jti:
            invalid_refresh_reason = "Refresh token subject mismatch during logout"
        else:
            await token_repo.revoke_by_jti(provided_jti, reason="logout")

    revoked_count = await token_repo.revoke_tokens_for_user(current_user.id, reason="logout")

    if invalid_refresh_reason:
        await audit_logger.log_authentication(
            action="logout",
            status=EventStatus.failure,
            context=context,
            authentication_method="refresh_token",
            error_message=invalid_refresh_reason,
            resource_type="refresh_token",
            resource_id=provided_jti,
            request_data={"refresh_jti": provided_jti} if provided_jti else None,
            session=db,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid refresh token",
        )

    await audit_logger.log_authentication(
        action="logout",
        status=EventStatus.success,
        context=context,
        authentication_method="access_token",
        resource_type="user",
        resource_id=current_user.id,
        request_data={
            "revoked_tokens": revoked_count,
            "refresh_jti": provided_jti,
        },
        session=db,
    )


@app.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: Request,
    password_change: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_postgres_session),
):
    """
    Change the authenticated user's password and invalidate existing refresh tokens.

    - **current_password**: Current password for verification
    - **new_password**: New password to set
    """
    context = AuditContext.from_request(request, service_name="auth")
    context.user_id = current_user.id
    context.username = current_user.username

    token_repo = RefreshTokenRepository(db)
    user_repo = UserRepository(db)

    if not current_user.hashed_password:
        await audit_logger.log_authentication(
            action="password_change",
            status=EventStatus.failure,
            context=context,
            authentication_method="password",
            error_message="Password change not supported for this account",
            resource_type="user",
            resource_id=current_user.id,
            session=db,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change not available for this account",
        )

    if not verify_password(password_change.current_password, current_user.hashed_password):
        await audit_logger.log_authentication(
            action="password_change",
            status=EventStatus.failure,
            context=context,
            authentication_method="password",
            error_message="Invalid current password",
            resource_type="user",
            resource_id=current_user.id,
            session=db,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )

    if verify_password(password_change.new_password, current_user.hashed_password):
        await audit_logger.log_authentication(
            action="password_change",
            status=EventStatus.failure,
            context=context,
            authentication_method="password",
            error_message="New password must be different from the current password",
            resource_type="user",
            resource_id=current_user.id,
            session=db,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from current password",
        )

    await user_repo.set_password(current_user.id, password_change.new_password)
    await token_repo.revoke_tokens_for_user(current_user.id, reason="password_change")

    await audit_logger.log_authentication(
        action="password_change",
        status=EventStatus.success,
        context=context,
        authentication_method="password",
        resource_type="user",
        resource_id=current_user.id,
        session=db,
    )


@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Refresh access token using refresh token.

    Each successful refresh rotates the refresh token (single use) and logs the
    outcome for auditability.

    - **refresh_token**: Valid refresh token
    """
    context = AuditContext.from_request(request, service_name="auth")
    token_repo = RefreshTokenRepository(db)
    user_repo = UserRepository(db)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    async def log_refresh_failure(reason: str, token_jti: Optional[str] = None):
        request_data = {"refresh_jti": token_jti} if token_jti else {}
        if user_agent:
            request_data["user_agent"] = user_agent
        if client_ip:
            request_data["ip_address"] = client_ip
        await audit_logger.log_authentication(
            action="refresh_token",
            status=EventStatus.failure,
            context=context,
            authentication_method="refresh_token",
            error_message=reason,
            resource_type="refresh_token",
            resource_id=token_jti,
            request_data=request_data or None,
            session=db,
        )

    payload = decode_token(refresh_request.refresh_token)

    if not payload or payload.get("type") != "refresh":
        await log_refresh_failure("Invalid refresh token payload or type")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")
    context.user_id = user_id

    if not user_id or not jti:
        await log_refresh_failure("Refresh token missing subject or jti", jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    token_record = await token_repo.get_by_jti(jti)
    if not token_record:
        await log_refresh_failure("Refresh token record not found or already cleared", jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    if token_record.user_id != user_id:
        await token_repo.revoke_by_jti(jti, reason="subject_mismatch")
        await log_refresh_failure("Refresh token subject mismatch", jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    now = datetime.utcnow()
    active_token = await token_repo.get_active_for_user(jti, user_id)

    if not active_token:
        failure_reason = "Refresh token inactive"
        http_detail = "Invalid refresh token"

        if token_record.revoked_at:
            failure_reason = "Refresh token revoked"
            http_detail = "Refresh token has been revoked"
        elif token_record.rotated_at:
            failure_reason = "Refresh token already rotated"
            http_detail = "Refresh token already used"
        elif token_record.expires_at <= now:
            failure_reason = "Refresh token expired"
            http_detail = "Refresh token expired"
            await token_repo.revoke_by_jti(jti, reason="expired")

        await log_refresh_failure(failure_reason, jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=http_detail,
        )

    token_record = active_token

    # Verify user still exists and is active
    user = await user_repo.get_user_by_id(user_id)

    if not user or not user.is_active:
        await token_repo.revoke_tokens_for_user(user_id, reason="user_inactive")
        await log_refresh_failure("User not found or inactive", jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    context.user_id = user.id
    context.username = user.username

    new_jti = RefreshTokenRepository.generate_jti()
    await token_repo.mark_rotated(token_record, replaced_by_jti=new_jti, revoke=True, commit=False)

    new_refresh_token, _ = await create_refresh_token(
        data={"sub": user.id},
        db=db,
        user_agent=user_agent,
        ip_address=client_ip,
        jti=new_jti,
    )

    access_token = create_access_token(data={"sub": user.id})

    await audit_logger.log_authentication(
        action="refresh_token",
        status=EventStatus.success,
        context=context,
        authentication_method="refresh_token",
        resource_type="refresh_token",
        resource_id=jti,
        request_data={
            "refresh_jti": jti,
            "new_jti": new_jti,
            "user_agent": user_agent,
            "ip_address": client_ip,
        },
        session=db,
    )

    logger.info(f"Token refreshed for user: {user.email}")

    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer").dict()


# ============================================================================
# Protected Endpoints (Authentication Required)
# ============================================================================

@app.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@app.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    List all users (admin only).

    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return
    """
    repo = UserRepository(db)
    users = await repo.list_users(skip=skip, limit=limit)
    return [UserResponse.model_validate(user) for user in users]


# ============================================================================
# API Key Management
# ============================================================================

@app.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_postgres_session)
):
    """
    Create a new API key for the current user.

    **Important**: The API key will only be shown once. Store it securely!

    - **name**: Friendly name for the key
    - **scopes**: List of allowed scopes (optional)
    - **expires_in_days**: Expiration in days (optional, max 365)
    """
    repo = APIKeyRepository(db)

    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)

    raw_api_key = generate_api_key()
    key_identifier = derive_api_key_identifier(raw_api_key)

    api_key, plain_key = await repo.create_api_key(
        user_id=current_user.id,
        name=key_data.name,
        scopes=key_data.scopes,
        expires_at=expires_at,
        plain_key=raw_api_key,
        key_identifier=key_identifier
    )

    logger.info(f"API key created: {api_key.name} (ID: {api_key.id}) for user {current_user.email}")

    response = APIKeyResponse.model_validate(api_key)
    response.key = plain_key  # Only shown on creation
    return response


@app.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_postgres_session)
):
    """List all API keys for the current user."""
    repo = APIKeyRepository(db)
    api_keys = await repo.list_user_api_keys(current_user.id)
    return [APIKeyResponse.model_validate(key) for key in api_keys]


@app.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_postgres_session)
):
    """Revoke an API key."""
    repo = APIKeyRepository(db)

    # Check if key belongs to current user
    api_key = await repo.get_api_key_by_id(key_id)
    if not api_key or api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    await repo.revoke_api_key(key_id)
    logger.info(f"API key revoked: {key_id} by user {current_user.email}")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "auth"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
