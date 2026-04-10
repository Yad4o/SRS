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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import timedelta
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
    EMAIL_SEND_FAILED
)

from app.core.security import verify_password, create_access_token, hash_password, decode_token, check_password_truncation
from app.core.config import settings, ALLOWED_ROLES
from app.core.otp import generate_otp, send_otp_email, log_otp_for_dev, is_otp_expired, get_otp_expiration_time
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserLogin, UserCreate, UserResponse, Token,
    ForgotPasswordRequest, ForgotPasswordResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    ResetPasswordRequest, ResetPasswordResponse
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


@router.post("/login", response_model=Token)
def login(
    user_credentials: UserLogin,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Authenticate user and return JWT access token.
    
    Args:
        user_credentials: UserLogin schema with email and password
        db: Database session dependency
        
    Returns:
        Token schema with access_token and token_type
        
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
    
    return Token(
        access_token=access_token,
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


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Send OTP to user's email for password reset.
    
    Args:
        request: ForgotPasswordRequest with user email
        db: Database session dependency
        
    Returns:
        ForgotPasswordResponse with success message and OTP expiration time
        
    Raises:
        HTTPException: If email not found (404) or email send fails (500)
    """
    try:
        # Normalize email
        normalized_email = normalize_email(request.email)
        
        # Find user by email
        user = db.query(User).filter(User.email == normalized_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=EMAIL_NOT_FOUND
            )
        
        # Generate OTP
        otp = generate_otp()
        otp_expires_at = get_otp_expiration_time(10)  # 10 minutes
        
        # Update user with OTP
        user.reset_otp = otp
        user.reset_otp_expires_at = otp_expires_at
        user.reset_otp_attempts = 0
        
        db.commit()
        
        # Send OTP email (or log for development)
        email_sent = send_otp_email(user.email, otp)
        if not email_sent:
            # For development, log the OTP instead of failing
            log_otp_for_dev(user.email, otp)
        
        return ForgotPasswordResponse(
            message="OTP sent to your email address",
            otp_expires_in=10
        )
        
    except SQLAlchemyError as e:
        logger.exception("Database error in forgot_password")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in forgot_password")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=AUTH_SERVICE_UNAVAILABLE
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
    
    # Verify OTP
    if not secrets.compare_digest(str(user.reset_otp), str(otp)):
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

