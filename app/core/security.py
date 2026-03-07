"""
app/core/security.py

Purpose:
--------
Security utilities for the application.
Provides password hashing/verification and JWT token creation/decoding.

Owner:
------
Om (Backend / System)

Responsibilities:
-----------------
- Hash and verify passwords using bcrypt via passlib
- Create and decode JWT access tokens using python-jose
- Read security configuration from settings

DO NOT:
-------
- Store state here
- Access database directly
- Implement auth business logic (that belongs in app/api/auth.py)

References:
-----------
- Technical Spec § 10.1 (Authentication)
- Technical Spec § 10.2 (Password Handling)
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# -------------------------------------------------
# Password Hashing
# -------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=True)
"""
Passlib CryptContext configured for bcrypt.
Using 'deprecated="auto"' ensures old hashes are automatically
flagged as needing re-hashing (forward-compatible).
"""


def check_password_truncation(plain_password: str) -> dict:
    """
    Check if a password would be truncated by bcrypt.
    
    Args:
        plain_password: The raw password to check
        
    Returns:
        dict: Information about potential truncation
    """
    original_bytes = len(plain_password.encode('utf-8'))
    would_be_truncated = original_bytes > 72
    
    return {
        "would_be_truncated": would_be_truncated,
        "original_bytes": original_bytes,
        "max_bytes": 72
    }


def _truncate_password_for_bcrypt(plain_password: str) -> str:
    """
    Truncate password to fit bcrypt's 72-byte limit without splitting UTF-8 characters.
    
    Args:
        plain_password: The raw password to truncate
        
    Returns:
        Password truncated to maximum 72 bytes
    """
    # bcrypt has a 72-byte limit for passwords
    original_length = len(plain_password)
    original_bytes = len(plain_password.encode('utf-8'))
    
    if original_bytes > 72:
        import logging
        logger = logging.getLogger(__name__)
        
        # Find the character position that keeps us within 72 bytes
        truncated_password = ""
        byte_count = 0
        for char in plain_password:
            char_bytes = char.encode('utf-8')
            if byte_count + len(char_bytes) > 72:
                break
            truncated_password += char
            byte_count += len(char_bytes)
        
        # Log the truncation for security monitoring
        logger.warning(
            f"Password truncated from {original_length} characters ({original_bytes} bytes) "
            f"to {len(truncated_password)} characters ({byte_count} bytes) to fit bcrypt limit"
        )
        
        return truncated_password
    
    return plain_password


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    A random salt is generated automatically by bcrypt on every call,
    so the same plain-text input produces a different hash each time.
    This is the expected and secure behaviour.

    Args:
        plain_password: The raw password supplied by the user.

    Returns:
        str: A bcrypt-hashed password string (includes salt + cost factor).

    Reference: Technical Spec § 10.2 (Password Handling)
    """
    plain_password = _truncate_password_for_bcrypt(plain_password)
    return pwd_context.hash(plain_password)


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
        plain_password = _truncate_password_for_bcrypt(plain_password)
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# -------------------------------------------------
# JWT Token Utilities
# -------------------------------------------------


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token.

    The token payload is a copy of `data` with an `exp` (expiry) claim
    appended. The token is signed using the configured SECRET_KEY and
    ALGORITHM (default HS256).

    Args:
        data:          Dictionary of claims to include in the token payload.
                       Typically contains at least ``{"sub": "<user_id>"}``.
        expires_delta: Optional override for token lifetime. When None,
                       falls back to ``settings.ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        str: A compact, URL-safe JWT string.

    Reference: Technical Spec § 10.1 (Authentication)
    """
    to_encode = data.copy()

    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode["exp"] = expire

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    Verifies the token signature and expiry using the configured
    SECRET_KEY and ALGORITHM.

    Args:
        token: The JWT string to decode.

    Returns:
        dict: The decoded token payload (claims).

    Raises:
        jose.JWTError: If the token is expired, has an invalid signature,
                       or is malformed in any way.

    Reference: Technical Spec § 10.1 (Authentication)
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
