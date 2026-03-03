"""
app/api/auth.py

Purpose:
--------
Authentication API endpoints for user login and registration.

Owner:
------
Om (Backend / API Development)

Responsibilities:
-----------------
- Handle user login with email and password
- Generate JWT access tokens for authenticated users
- Optional: Handle user registration with password hashing
- Return appropriate HTTP status codes and error messages

DO NOT:
-------
- Store passwords in plain text
- Implement business logic beyond authentication
- Access database without proper error handling

References:
-----------
- Technical Spec § 10.1 (Authentication)
- Task 2.1 (Security Utilities)
- Task 2.2 (User Schemas)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated

from app.core.security import verify_password, create_access_token, hash_password
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserLogin, UserCreate, UserResponse, Token

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """
    Authenticate a user by email and password.
    
    Args:
        db: Database session
        email: User email address
        password: Plain-text password to verify
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, user_create: UserCreate) -> User:
    """
    Create a new user with hashed password.
    
    Args:
        db: Database session
        user_create: UserCreate schema with email and password
        
    Returns:
        Created User object
    """
    hashed_password = hash_password(user_create.password)
    db_user = User(
        email=user_create.email,
        hashed_password=hashed_password,
        role="user"  # Default role for new registrations
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=Token)
async def login(
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
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with user info
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/register", response_model=UserResponse)
async def register(
    user_create: UserCreate,
    db: Annotated[Session, Depends(get_db)]
):
    """
    Register a new user and return user information.
    
    This is an optional endpoint that creates a new user with hashed password.
    The password is validated by the UserCreate schema before reaching here.
    
    Args:
        user_create: UserCreate schema with email and password
        db: Database session dependency
        
    Returns:
        UserResponse schema with user information (no password)
        
    Raises:
        HTTPException: If user already exists (400 Bad Request)
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_create.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = create_user(db, user_create)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role
    )


async def get_current_user(
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
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    
    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
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
