"""
app/api/auth.py

Purpose:
Authentication API endpoints for user login and registration.

Responsibilities:
- Handle user login with email and password
- Generate JWT access tokens for authenticated users
- Optional: Handle user registration with password hashing
- Return appropriate HTTP status codes and error messages

DO NOT:
- Store passwords in plain text
- Implement business logic beyond authentication
- Access database without proper error handling

References:
- Technical Spec § 10.1 (Authentication)
- Task 2.1 (Security Utilities)
- Task 2.2 (User Schemas)
"""

import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timedelta, timezone
from typing import Annotated
from jose import JWTError

from app.constants import (
    UserRole,
    AUTH_SERVICE_UNAVAILABLE,
    INCORRECT_CREDENTIALS,
    EMAIL_ALREADY_REGISTERED,
    EMAIL_PASSWORD_REQUIRED,
    INVALID_DEFAULT_ROLE,
    COULD_NOT_VALIDATE_CREDENTIALS,
    EMAIL_NOT_FOUND,
    INVALID_OTP,
    OTP_EXPIRED,
    MAX_OTP_ATTEMPTS,
    EMAIL_SEND_FAILED,
    FORGOT_PASSWORD_SAFE_RESPONSE,
    INVALID_REFRESH_TOKEN,
)

from app.core.security import (
    verify_password, create_access_token, hash_password, decode_token, check_password_truncation,
    create_refresh_token, hash_refresh_token, verify_refresh_token_hash, get_refresh_token_expiration_time,
)
from app.core.config import settings, ALLOWED_ROLES
from app.core.limiter import limiter
from app.core.otp import generate_otp, hash_otp, verify_otp_hash, send_otp_email, log_otp_for_dev, is_otp_expired, get_otp_expiration_time
from app.db.session import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import (
    UserLogin, UserCreate, UserResponse, Token,
    ForgotPasswordRequest, ForgotPasswordResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    ResetPasswordRequest, ResetPasswordResponse,
    RefreshTokenRequest, LogoutResponse,
)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Configure logger
logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    """
    Normalize email address for consistent storage and lookup.
    
    Args:
        email: Email string to normalize
        
    Returns:
        Normalized email (lowercase and stripped)
        
    Raises:
        ValueError: If email is empty or only whitespace
    """
    if not email:
        raise ValueError("Email cannot be empty")
    
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email cannot be empty")
    
    return normalized


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """
    Authenticate a user by email and password.
    
    Args:
        db: Database session
        email: User email address
        password: Plain-text password to verify
        
    Returns:
        User object if authentication successful, None otherwise
        
    Raises:
        HTTPException: If database error occurs (500 Internal Server Error)
    """
    # Validate inputs
    if not email or not password:
        return None
        
    try:
        # Normalize email to lowercase for consistent storage and lookup
        normalized_email = normalize_email(email)
            
        user = db.query(User).filter(User.email == normalized_email).first()
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    except SQLAlchemyError as e:
        logger.exception("Database error during authentication")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )


def create_user(db: Session, user_create: UserCreate) -> UserResponse:
    """
    Create a new user with hashed password.
    
    Args:
        db: Database session
        user_create: UserCreate schema with email and password
        
    Returns:
        UserResponse schema with user information (no password)
        
    Raises:
        HTTPException: If email already exists (400 Bad Request) or database error occurs
    """
    # Validate inputs
    if not user_create.email or not user_create.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=EMAIL_PASSWORD_REQUIRED
        )
        
    try:
        # Check if password would be truncated and warn user
        truncation_info = check_password_truncation(user_create.password)
        if truncation_info["would_be_truncated"]:
            logger.info("Password will be truncated to fit bcrypt limit")
        
        hashed_password = hash_password(user_create.password)
        
        # Use role from user_create, fallback to default if not provided
        user_role = getattr(user_create, 'role', None) or getattr(settings, 'DEFAULT_USER_ROLE', UserRole.USER.value)
        
        # Validate role against allowed roles
        if user_role not in ALLOWED_ROLES:
            logger.error(f"Invalid role specified: {user_role}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(ALLOWED_ROLES)}"
            )
        
        # Normalize email to lowercase for consistent storage and uniqueness
        normalized_email = normalize_email(user_create.email)
        
        db_user = User(
            email=normalized_email,
            hashed_password=hashed_password,
            role=user_role
        )
        
        db.add(db_user)
        db.flush()  # Get the ID without committing
        
        # Capture values before commit to avoid expired instance issues
        user_id = db_user.id
        user_email = db_user.email
        user_role = db_user.role
        
        db.commit()
        
        # Return UserResponse directly with captured values
        return UserResponse(
            id=user_id,
            email=user_email,
            role=user_role
        )
        
    except IntegrityError as e:
        db.rollback()
        # Check if this is a duplicate email error
        if "email" in str(e).lower() or "unique" in str(e).lower():
            logger.warning("Duplicate email registration attempt detected")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=EMAIL_ALREADY_REGISTERED
            )
        else:
            logger.exception("Database integrity error creating user")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=AUTH_SERVICE_UNAVAILABLE
            )
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database error creating user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        db.rollback()
        logger.exception("Unexpected error during user creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )


def _issue_refresh_token(db: Session, user_id: int) -> str:
    """
    Generate a new refresh token, persist its hash, and return the raw token.

    The raw token is returned to the caller exactly once (here) — only its
    HMAC-SHA256 hash is ever stored, mirroring the OTP-hashing pattern in
    app/core/otp.py.

    Args:
        db: Database session
        user_id: ID of the user this refresh token belongs to

    Returns:
        str: The raw refresh token to hand back to the client.
    """
    raw_token = create_refresh_token()
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=get_refresh_token_expiration_time(),
        revoked=False,
    )
    db.add(db_token)
    db.commit()
    return raw_token


@router.post("/login", response_model=Token)
@limiter.limit(settings.AUTH_RATE_LIMIT_LOGIN)
def login(
    request: Request,
    user_credentials: UserLogin,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Authenticate user and return a JWT access token plus a refresh token.
    
    Args:
        user_credentials: UserLogin schema with email and password
        db: Database session dependency
        
    Returns:
        Token schema with access_token, refresh_token, and token_type
        
    Raises:
        HTTPException: If authentication fails (401 Unauthorized)
    """
    user = authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INCORRECT_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with user info (removed email for security)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=access_token_expires
    )

    refresh_token = _issue_refresh_token(db, user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/register", response_model=UserResponse)
def register(
    user_create: UserCreate,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Register a new user and return user information.
    
    This endpoint creates a new user with hashed password.
    The password is validated by the UserCreate schema before reaching here.
    
    Args:
        user_create: UserCreate schema with email and password
        db: Database session dependency
        
    Returns:
        UserResponse schema with user information (no password)
        
    Raises:
        HTTPException: If registration fails (400 Bad Request or 500 Internal Server Error)
    """
    # Create new user - database constraints will handle duplicates
    return create_user(db, user_create)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Dependency function to get current user from JWT token.
    
    This function decodes the JWT token and retrieves the corresponding user
    from the database. It's used as a dependency for protected routes.
    
    Args:
        token: JWT token from Authorization header
        db: Database session dependency
        
    Returns:
        Current authenticated User object
        
    Raises:
        HTTPException: If token is invalid or user not found (401 Unauthorized)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=COULD_NOT_VALIDATE_CREDENTIALS,
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        
        # Validate and convert user_id to int
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise credentials_exception
        return user
    except SQLAlchemyError as e:
        logger.exception("Database error retrieving user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )




@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Get current authenticated user information.
    
    This endpoint demonstrates how to protect routes with JWT authentication.
    It requires a valid JWT token in the Authorization header.
    
    Args:
        current_user: Current authenticated user (from dependency)
        
    Returns:
        UserResponse schema with user information
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role
    )


def _get_valid_refresh_token_row(db: Session, raw_token: str) -> RefreshToken:
    """
    Look up and validate a refresh token by its raw value.

    Looks up by HMAC hash (deterministic, so a direct equality query
    works), then checks revocation and expiry.

    Args:
        db: Database session
        raw_token: The raw refresh token string supplied by the client

    Returns:
        The matching, still-valid RefreshToken row.

    Raises:
        HTTPException: 401 if the token is unknown, revoked, or expired.
    """
    invalid_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_REFRESH_TOKEN,
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_hash = hash_refresh_token(raw_token)
    token_row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not token_row:
        raise invalid_exception

    # Defence in depth: re-verify in constant time even though the lookup
    # already matched by hash equality (guards against any future change
    # to the lookup that might compare non-hash fields).
    if not verify_refresh_token_hash(raw_token, token_row.token_hash):
        raise invalid_exception

    if token_row.revoked:
        raise invalid_exception

    # SQLite doesn't actually preserve timezone-awareness for
    # DateTime(timezone=True) columns on read (unlike Postgres), so
    # expires_at may come back naive depending on the configured
    # DATABASE_URL. Normalize before comparing to avoid a "can't compare
    # naive and aware datetimes" TypeError surfacing as a 500.
    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise invalid_exception

    return token_row


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    request_body: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Exchange a valid refresh token for a new access token + refresh token.

    Implements rotation-on-refresh: the supplied refresh token is revoked
    as part of this call and a brand new one is issued, so a leaked
    refresh token can only be replayed once before detection (a second
    use of the same old token will fail with 401, since it's now
    revoked) — this is the standard OAuth2 refresh token rotation pattern.

    Args:
        request_body: RefreshTokenRequest with the current refresh_token
        db: Database session dependency

    Returns:
        Token schema with a new access_token and refresh_token

    Raises:
        HTTPException: 401 if the refresh token is invalid, revoked, or expired
    """
    try:
        token_row = _get_valid_refresh_token_row(db, request_body.refresh_token)

        user = db.query(User).filter(User.id == token_row.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=INVALID_REFRESH_TOKEN,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Rotate: revoke the old token, issue a brand new one.
        token_row.revoked = True
        db.commit()

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role},
            expires_delta=access_token_expires,
        )
        new_refresh_token = _issue_refresh_token(db, user.id)

        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error in refresh_access_token")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception("Unexpected error in refresh_access_token")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE,
        )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request_body: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Revoke a refresh token, ending that session.

    The access token itself stays valid until it naturally expires (it's
    a stateless JWT and can't be revoked early without a blocklist), but
    the client can no longer use this refresh token to mint new ones —
    the practical effect is the same as "logging out" once the short-lived
    access token expires.

    Idempotent and intentionally tolerant: an unknown or already-revoked
    refresh token still returns success, since from the caller's
    perspective the desired end state ("I'm logged out") is already true.

    Args:
        request_body: RefreshTokenRequest with the refresh_token to revoke
        db: Database session dependency

    Returns:
        LogoutResponse confirming the session was ended
    """
    try:
        token_hash = hash_refresh_token(request_body.refresh_token)
        token_row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

        if token_row and not token_row.revoked:
            token_row.revoked = True
            db.commit()

        return LogoutResponse(message="Logged out successfully")

    except SQLAlchemyError:
        logger.exception("Database error in logout")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE,
        )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit(settings.AUTH_RATE_LIMIT_FORGOT_PASSWORD)
def forgot_password(
    request: Request,
    request_body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Initiate password reset by sending an OTP to the supplied email.

    SECURITY NOTES
    --------------
    1. User enumeration (CWE-204): always returns HTTP 200 with an identical
       body whether or not the email is registered.

    2. Timing oracle: the slow Resend API call is dispatched as a FastAPI
       BackgroundTask so both the "user not found" and "user found" paths
       return at the same wall-clock time from the caller's perspective.
       DB writes are synchronous (fast); only network I/O is deferred.

    Args:
        request: FastAPI Request (required by SlowAPI rate-limiter)
        request_body: ForgotPasswordRequest with user email
        background_tasks: FastAPI BackgroundTasks for async OTP delivery
        db: Database session dependency

    Returns:
        ForgotPasswordResponse with a safe, non-leaking success message

    Raises:
        HTTPException 500 - database or unexpected internal error
    """
    # SECURITY: response body is identical regardless of email existence.
    _safe_response = ForgotPasswordResponse(
        message=FORGOT_PASSWORD_SAFE_RESPONSE,
        otp_expires_in=10,
    )

    def _deliver_otp(email: str, otp: str) -> None:
        """Background task: deliver OTP without blocking the HTTP response."""
        if not send_otp_email(email, otp):
            # Only log the raw OTP in development; in other envs log a generic
            # delivery-failure message so reset codes never appear in prod logs.
            if settings.ENV == "development":
                log_otp_for_dev(email, otp)
            else:
                logger.warning(
                    "OTP email delivery failed for user (email suppressed)"
                )

    try:
        normalized_email = normalize_email(request_body.email)

        user = db.query(User).filter(User.email == normalized_email).first()
        if not user:
            # Log at DEBUG only — never surface to the caller.
            logger.debug(
                "forgot_password: no account for email (suppressed from response)"
            )
            return _safe_response

        # Generate and persist HMAC-keyed OTP hash — never the raw token.
        otp = generate_otp()
        otp_expires_at = get_otp_expiration_time(10)  # 10 minutes

        user.reset_otp = hash_otp(otp)
        user.reset_otp_expires_at = otp_expires_at
        user.reset_otp_attempts = 0

        db.commit()

        # Dispatch delivery off the hot path to avoid a timing side-channel.
        background_tasks.add_task(_deliver_otp, user.email, otp)

        return _safe_response

    except SQLAlchemyError:
        logger.exception("Database error in forgot_password")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in forgot_password")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE,
        )


def _verify_user_otp(db: Session, email: str, otp: str) -> User:
    """Helper method to encapsulate OTP verification logic."""
    # Normalize email
    normalized_email = normalize_email(email)
    
    # Find user by email
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=EMAIL_NOT_FOUND
        )
    
    # Check if user has OTP
    if not user.reset_otp or not user.reset_otp_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_OTP
        )
    
    # Check if OTP is expired
    if is_otp_expired(user.reset_otp_expires_at):
        # Clear expired OTP
        user.reset_otp = None
        user.reset_otp_expires_at = None
        user.reset_otp_attempts = 0
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=OTP_EXPIRED
        )
    
    # Check max attempts (3 attempts allowed)
    if user.reset_otp_attempts >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=MAX_OTP_ATTEMPTS
        )
    
    # Verify OTP — compare against the stored SHA-256 hash in constant time
    if not verify_otp_hash(str(otp), str(user.reset_otp)):
        # Increment attempts
        user.reset_otp_attempts += 1
        db.commit()
        
        remaining_attempts = 3 - user.reset_otp_attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP. {remaining_attempts} attempts remaining"
        )
        
    return user


@router.post("/verify-otp", response_model=VerifyOTPResponse)
def verify_otp(
    request: VerifyOTPRequest,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Verify OTP for password reset.
    
    Args:
        request: VerifyOTPRequest with email and OTP
        db: Database session dependency
        
    Returns:
        VerifyOTPResponse with verification result
        
    Raises:
        HTTPException: If OTP is invalid/expired (400) or max attempts exceeded (429)
    """
    try:
        user = _verify_user_otp(db, request.email, request.otp)
        
        # OTP is valid - reset attempts
        user.reset_otp_attempts = 0
        db.commit()
        
        return VerifyOTPResponse(
            message="OTP verified successfully",
            is_valid=True
        )
        
    except SQLAlchemyError as e:
        logger.exception("Database error in verify_otp")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in verify_otp")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    request: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Reset user password using OTP.
    
    Args:
        request: ResetPasswordRequest with email, OTP, and new password
        db: Database session dependency
        
    Returns:
        ResetPasswordResponse with success message
        
    Raises:
        HTTPException: If OTP is invalid/expired (400) or max attempts exceeded (429)
    """
    try:
        user = _verify_user_otp(db, request.email, request.otp)
        
        # Check password truncation
        truncation_info = check_password_truncation(request.new_password)
        if truncation_info["would_be_truncated"]:
            logger.info("New password will be truncated to fit bcrypt limit")
        
        # Hash new password
        new_hashed_password = hash_password(request.new_password)
        
        # Update password and clear OTP
        user.hashed_password = new_hashed_password
        user.reset_otp = None
        user.reset_otp_expires_at = None
        user.reset_otp_attempts = 0
        
        db.commit()
        
        return ResetPasswordResponse(
            message="Password reset successfully"
        )
        
    except SQLAlchemyError as e:
        logger.exception("Database error in reset_password")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in reset_password")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )

