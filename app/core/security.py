"""
 =============================================================================
 SRS (Support Request System) - Security Utilities
 =============================================================================

Purpose:
--------
Security utilities for the application.
Provides password hashing/verification and JWT token creation/decoding.

Responsibilities:
-----------------
- Hash and verify passwords using bcrypt via passlib
- Create and decode JWT access tokens using python-jose
- Read security configuration from settings
- Password truncation handling for bcrypt compatibility
- Security validation and logging

Owner:
------
Backend Team

DO NOT:
-------
- Store state here
- Access database directly
- Implement auth business logic (that belongs in app/api/auth.py)
- Log sensitive information like passwords

References:
-----------
- Technical Spec § 10.1 (Authentication)
- Technical Spec § 10.2 (Password Handling)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Password Hashing Configuration
# -----------------------------------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto", 
    truncate_error=True,
    bcrypt__rounds=12  # Higher rounds for better security
)

# -----------------------------------------------------------------------------
# Password Security Constants
# -----------------------------------------------------------------------------
BCRYPT_MAX_BYTES = 72
MIN_PASSWORD_LENGTH = 8

def check_password_security(plain_password: str) -> dict:
    """
    Comprehensive password security analysis.
    
    Args:
        plain_password: The raw password to analyze
        
    Returns:
        dict: Security analysis including truncation, length, and recommendations
    """
    original_bytes = len(plain_password.encode('utf-8'))
    would_be_truncated = original_bytes > BCRYPT_MAX_BYTES
    is_too_short = len(plain_password) < MIN_PASSWORD_LENGTH
    
    # Basic security checks
    has_upper = any(c.isupper() for c in plain_password)
    has_lower = any(c.islower() for c in plain_password)
    has_digit = any(c.isdigit() for c in plain_password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in plain_password)
    
    security_score = sum([
        has_upper, has_lower, has_digit, has_special,
        not would_be_truncated, not is_too_short
    ])
    
    return {
        "would_be_truncated": would_be_truncated,
        "original_bytes": original_bytes,
        "max_bytes": BCRYPT_MAX_BYTES,
        "is_too_short": is_too_short,
        "min_length": MIN_PASSWORD_LENGTH,
        "has_upper": has_upper,
        "has_lower": has_lower,
        "has_digit": has_digit,
        "has_special": has_special,
        "security_score": security_score,
        "security_strength": _get_security_strength(security_score)
    }

def _get_security_strength(score: int) -> str:
    """Get security strength description based on score."""
    if score >= 5:
        return "strong"
    elif score >= 3:
        return "moderate"
    else:
        return "weak"

def _truncate_password_for_bcrypt(plain_password: str) -> str:
    """
    Truncate password to fit bcrypt's 72-byte limit without splitting UTF-8 characters.
    
    Args:
        plain_password: The raw password to truncate
        
    Returns:
        Password truncated to maximum 72 bytes
        
    Raises:
        ValueError: If password is too short after truncation
    """
    original_length = len(plain_password)
    original_bytes = len(plain_password.encode('utf-8'))
    
    if original_bytes > BCRYPT_MAX_BYTES:
        # Find the character position that keeps us within 72 bytes
        truncated_password = ""
        byte_count = 0
        for char in plain_password:
            char_bytes = char.encode('utf-8')
            if byte_count + len(char_bytes) > BCRYPT_MAX_BYTES:
                break
            truncated_password += char
            byte_count += len(char_bytes)
        
        # Log the truncation for security monitoring (without revealing details)
        logger.warning(
            "Password truncated to fit bcrypt 72-byte limit for security"
        )
        
        if len(truncated_password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                "Password becomes too short after bcrypt truncation. "
                f"Must be at least {MIN_PASSWORD_LENGTH} characters after truncation."
            )
        
        return truncated_password
    
    return plain_password

def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt with security validation.

    A random salt is generated automatically by bcrypt on every call,
    so the same plain-text input produces a different hash each time.
    This is the expected and secure behaviour.

    Args:
        plain_password: The raw password supplied by the user.

    Returns:
        str: A bcrypt-hashed password string (includes salt + cost factor).

    Raises:
        ValueError: If password doesn't meet security requirements

    Reference: Technical Spec § 10.2 (Password Handling)
    """
    # Security validation
    security_check = check_password_security(plain_password)
    
    if security_check["is_too_short"]:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
        )
    
    if security_check["security_strength"] == "weak":
        logger.warning(
            "Weak password detected - consider using stronger password"
        )
    
    # Truncate for bcrypt compatibility if needed
    safe_password = _truncate_password_for_bcrypt(plain_password)
    
    try:
        return pwd_context.hash(safe_password)
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        raise ValueError("Failed to hash password") from e

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Uses passlib's constant-time comparison to prevent timing attacks.

    Args:
        plain_password:  The raw password supplied during login.
        hashed_password: The bcrypt hash stored in the database.

    Returns:
        bool: True if the password matches, False otherwise.

    Reference: Technical Spec § 10.2 (Password Handling)
    """
    try:
        # Truncate for comparison (bcrypt truncates internally)
        safe_password = _truncate_password_for_bcrypt(plain_password)
        return pwd_context.verify(safe_password, hashed_password)
    except ValueError as e:
        # Log truncation failures (security issue)
        logger.warning(f"Password verification failed due to truncation: {e}")
        return False
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def check_password_needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed due to updated security settings.
    
    Args:
        hashed_password: The stored bcrypt hash
        
    Returns:
        bool: True if rehashing is recommended
    """
    try:
        return pwd_context.needs_update(hashed_password)
    except Exception:
        # If we can't determine, assume it needs rehash for safety
        return True

# -----------------------------------------------------------------------------
# JWT Token Utilities
# -----------------------------------------------------------------------------

def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None
) -> str:
    """
    Create a signed JWT access token with comprehensive claims.

    The token payload includes standard claims and any additional claims provided.
    The token is signed using the configured SECRET_KEY and ALGORITHM.

    Args:
        data: Dictionary of claims to include in the token payload.
               Typically contains at least {"sub": "<user_id>", "role": "<role>"}.
        expires_delta: Optional override for token lifetime. When None,
                       falls back to settings.ACCESS_TOKEN_EXPIRE_MINUTES.
        additional_claims: Optional additional claims to include in the token.

    Returns:
        str: A compact, URL-safe JWT string.

    Raises:
        ValueError: If required claims are missing or invalid

    Reference: Technical Spec § 10.1 (Authentication)
    """
    # Validate required claims
    if "sub" not in data:
        raise ValueError("Token must contain 'sub' claim (user ID)")
    
    if "role" not in data:
        raise ValueError("Token must contain 'role' claim")
    
    to_encode = data.copy()
    
    # Add additional claims if provided
    if additional_claims:
        to_encode.update(additional_claims)
    
    # Set expiration time
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),  # Issued at
        "iss": settings.APP_NAME,  # Issuer
        "aud": "srs-users"  # Audience
    })

    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        
        logger.debug(f"Created access token for user {data.get('sub')}")
        return encoded_jwt
        
    except Exception as e:
        logger.error(f"Token creation failed: {e}")
        raise ValueError("Failed to create access token") from e

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT access token with comprehensive validation.

    Verifies the token signature, expiry, and other claims using the configured
    SECRET_KEY and ALGORITHM.

    Args:
        token: The JWT string to decode.

    Returns:
        dict: The decoded token payload (claims).

    Raises:
        JWTError: If the token is expired, has an invalid signature,
                  is malformed, or fails any validation.

    Reference: Technical Spec § 10.1 (Authentication)
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience="srs-users",
            issuer=settings.APP_NAME,
        )
        
        # Validate required claims
        if "sub" not in payload:
            raise JWTError("Token missing required 'sub' claim")
        
        if "role" not in payload:
            raise JWTError("Token missing required 'role' claim")
        
        if "exp" not in payload:
            raise JWTError("Token missing required 'exp' claim")
        
        # Additional validation
        if payload.get("aud") != "srs-users":
            raise JWTError("Invalid token audience")
        
        if payload.get("iss") != settings.APP_NAME:
            raise JWTError("Invalid token issuer")
        
        logger.debug(f"Successfully decoded token for user {payload.get('sub')}")
        return payload
        
    except (JWTError, ValueError, UnicodeDecodeError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise JWTError(f"Invalid token: {str(e)}") from e

def create_refresh_token(data: dict) -> str:
    """
    Create a refresh token with longer expiration.
    
    Args:
        data: Dictionary containing user identifier
        
    Returns:
        str: A compact JWT refresh token
    """
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    return create_access_token(
        data=data,
        expires_delta=expires_delta,
        additional_claims={"type": "refresh"}
    )

def verify_token_type(payload: dict, expected_type: str = "access") -> bool:
    """
    Verify that the token payload matches the expected token type.
    
    Args:
        payload: Decoded token payload
        expected_type: Expected token type ("access" or "refresh")
        
    Returns:
        bool: True if token type matches
    """
    token_type = payload.get("type", "access")  # Default to access for backward compatibility
    return token_type == expected_type

# -----------------------------------------------------------------------------
# Token Utilities
# -----------------------------------------------------------------------------

def extract_token_from_header(auth_header: str) -> Optional[str]:
    """
    Extract JWT token from Authorization header.
    
    Args:
        auth_header: The Authorization header value
        
    Returns:
        Optional[str]: The extracted token or None if invalid
    """
    if not auth_header:
        return None
    
    try:
        scheme, token = auth_header.split(" ", 1)
        if scheme.lower() != "bearer":
            return None
        return token
    except (ValueError, AttributeError):
        return None

def get_token_expiration_time(payload: dict) -> Optional[datetime]:
    """
    Extract expiration time from token payload.
    
    Args:
        payload: Decoded token payload
        
    Returns:
        Optional[datetime]: Expiration time or None if not found
    """
    exp_timestamp = payload.get("exp")
    if exp_timestamp:
        return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    return None

def is_token_expired(payload: dict) -> bool:
    """
    Check if token is expired.
    
    Args:
        payload: Decoded token payload
        
    Returns:
        bool: True if token is expired
    """
    exp_time = get_token_expiration_time(payload)
    if exp_time:
        return datetime.now(timezone.utc) > exp_time
    return False
