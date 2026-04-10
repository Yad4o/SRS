"""
app/schemas/user.py

Purpose:
Defines Pydantic schemas for User-related API requests and responses.

Responsibilities:
- Validate incoming user data (login, registration)
- Shape API responses (never expose hashed_password)
- Define the Token response schema for JWT auth

DO NOT:
- Access database here
- Hash passwords here
- Implement authentication logic here

Reference: Technical Spec § 5.4 (Schema Layer)
"""

import re
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator


def validate_password_complexity(v: str) -> str:
    """
    Validate password complexity:
    - Min 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
        raise ValueError("Password must contain at least one special character")
    return v


def validate_otp_code(v: str) -> str:
    """Validate OTP format."""
    if not v.isdigit() or len(v) != 6:
        raise ValueError("OTP must be a 6-digit number")
    return v


# -------------------------------------------------
# Request Schemas
# -------------------------------------------------


class UserLogin(BaseModel):
    """
    Schema used for user login.

    Used in:
    POST /auth/login

    Fields:
    - email: User email address (validated as EmailStr)
    - password: Plain-text password (never stored — passed to verify_password)
    """

    email: EmailStr
    password: str


class UserCreate(BaseModel):
    """
    Schema used when registering a new user.

    Used in:
    POST /auth/register

    Fields:
    - email: User email (validated as EmailStr)
    - password: Plain-text password (will be hashed by auth API before storage)
    - role: User role (optional, defaults to "user")
    """

    email: EmailStr
    password: str
    role: str = "user"  # Default to "user" if not specified

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """
        Validate that role is one of the allowed roles.
        """
        from app.core.config import ALLOWED_ROLES
        if v not in ALLOWED_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(ALLOWED_ROLES)}")
        return v


class ForgotPasswordRequest(BaseModel):
    """
    Schema for forgot password request.

    Used in:
    POST /auth/forgot-password

    Fields:
    - email: User email address to send OTP to
    """

    email: EmailStr


class VerifyOTPRequest(BaseModel):
    """
    Schema for OTP verification request.

    Used in:
    POST /auth/verify-otp

    Fields:
    - email: User email address
    - otp: 6-digit OTP code
    """

    email: EmailStr
    otp: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        return validate_otp_code(v)


class ResetPasswordRequest(BaseModel):
    """
    Schema for password reset request.

    Used in:
    POST /auth/reset-password

    Fields:
    - email: User email address
    - otp: 6-digit OTP code
    - new_password: New password to set
    """

    email: EmailStr
    otp: str
    new_password: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        return validate_otp_code(v)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)


# -------------------------------------------------
# Response Schemas
# -------------------------------------------------


class UserResponse(BaseModel):
    """
    Schema returned when user information is sent to clients.

    IMPORTANT:
    Never include sensitive fields such as:
    - hashed_password

    Used in:
    POST /auth/register (response)
    GET  /users/me (future)
    """

    id: int
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """
    Schema returned after a successful login.

    Contains a signed JWT access token that the client must send
    in the Authorization header as ``Bearer <token>`` for protected routes.

    Used in:
    POST /auth/login (response)

    Fields:
    - access_token: The signed JWT string
    - token_type:   Always "bearer" (OAuth 2.0 convention)

    Reference: Technical Spec § 10.1 (Authentication)
    """

    access_token: str
    token_type: str = "bearer"


class ForgotPasswordResponse(BaseModel):
    """
    Schema for forgot password response.

    Used in:
    POST /auth/forgot-password (response)

    Fields:
    - message: Success message indicating OTP was sent
    - otp_expires_in: Number of minutes until OTP expires
    """

    message: str
    otp_expires_in: int


class VerifyOTPResponse(BaseModel):
    """
    Schema for OTP verification response.

    Used in:
    POST /auth/verify-otp (response)

    Fields:
    - message: Success message indicating OTP is valid
    - is_valid: Boolean indicating if OTP is valid
    """

    message: str
    is_valid: bool


class ResetPasswordResponse(BaseModel):
    """
    Schema for password reset response.

    Used in:
    POST /auth/reset-password (response)

    Fields:
    - message: Success message indicating password was reset
    """

    message: str

