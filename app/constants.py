"""
app/constants.py

Purpose:
Centralized constants for the application.
Application Constants

Responsibilities:
- Magic numbers
- Default values
- Error messages
- Status strings
"""

from enum import Enum


# Ticket statuses
class TicketStatus(str, Enum):
    OPEN = "open"
    AUTO_RESOLVED = "auto_resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"

# User roles
class UserRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    ADMIN = "admin"

# Pagination defaults
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100



# Similarity thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.8
MIN_SIMILARITY_THRESHOLD = 0.1
MAX_SIMILARITY_THRESHOLD = 1.0

# Cache settings
CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_KEY_PREFIX = "srs"

# Auth error messages
AUTH_SERVICE_UNAVAILABLE = "Authentication service temporarily unavailable"
INCORRECT_CREDENTIALS = "Incorrect email or password"
EMAIL_ALREADY_REGISTERED = "Email already registered"
EMAIL_PASSWORD_REQUIRED = "Email and password are required"
INVALID_DEFAULT_ROLE = "Invalid default role configuration"
COULD_NOT_VALIDATE_CREDENTIALS = "Could not validate credentials"
EMAIL_NOT_FOUND = "Email address not found"
INVALID_OTP = "Invalid or expired OTP"
OTP_EXPIRED = "OTP has expired"
MAX_OTP_ATTEMPTS = "Maximum OTP attempts exceeded. Please request a new OTP"
EMAIL_SEND_FAILED = "Failed to send OTP email. Please try again"

# General error messages
VALIDATION_FAILED = "Validation failed"
NOT_FOUND = "Resource not found"
UNAUTHORIZED = "Unauthorized access"
FORBIDDEN = "Access forbidden"
DATABASE_ERROR = "Database operation failed"
INTERNAL_ERROR = "Internal server error"
RATE_LIMIT_EXCEEDED = "Rate limit exceeded"
INVALID_INPUT = "Invalid input provided"

# Configuration defaults
DEFAULT_CONFIG = {
    "openai_model": "gpt-3.5-turbo",
    "openai_timeout": 30,
    "max_retries": 3,
    "confidence_threshold": 0.8,
}

# Validation patterns
VALIDATION_PATTERNS = {
    "email": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    "phone": r'^\+?1?-?\.?\s?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})$',
    "ticket_id": r'^\d+$',
}



# Feature flags
FEATURE_FLAGS = {
    "enable_similarity_search": True,
    "enable_openai_integration": True,
    "enable_rate_limiting": True,
    "enable_caching": True,
}

# Time formats
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

# File size limits (in bytes)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_MESSAGE_LENGTH = 10000
MAX_EMAIL_LENGTH = 255

# Security settings
SESSION_TIMEOUT_MINUTES = 30
PASSWORD_MIN_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5

# Export commonly used constants
__all__ = [
    "TicketStatus",
    "UserRole", 
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",

    "FEATURE_FLAGS",
    "AUTH_SERVICE_UNAVAILABLE",
    "INCORRECT_CREDENTIALS",
    "EMAIL_ALREADY_REGISTERED",
    "EMAIL_PASSWORD_REQUIRED",
    "COULD_NOT_VALIDATE_CREDENTIALS",
    "EMAIL_NOT_FOUND",
    "INVALID_OTP",
    "OTP_EXPIRED",
    "MAX_OTP_ATTEMPTS",
    "EMAIL_SEND_FAILED",
]

