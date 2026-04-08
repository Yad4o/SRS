"""
app/constants.py

Purpose:
--------
Centralized constants for the application.

Owner:
------
Application Constants

Responsibilities:
-----------------
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

# Rate limiting
RATE_LIMIT_PER_MINUTE = 60

# Similarity thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.8
MIN_SIMILARITY_THRESHOLD = 0.1
MAX_SIMILARITY_THRESHOLD = 1.0

# Cache settings
CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_KEY_PREFIX = "srs"

# Error messages
ERROR_MESSAGES = {
    "validation_failed": "Validation failed",
    "not_found": "Resource not found",
    "unauthorized": "Unauthorized access",
    "forbidden": "Access forbidden",
    "database_error": "Database operation failed",
    "internal_error": "Internal server error",
    "rate_limit_exceeded": "Rate limit exceeded",
    "invalid_input": "Invalid input provided",
}

# Success messages
SUCCESS_MESSAGES = {
    "ticket_created": "Ticket created successfully",
    "ticket_updated": "Ticket updated successfully",
    "ticket_closed": "Ticket closed successfully",
    "user_created": "User created successfully",
    "operation_successful": "Operation completed successfully",
}

# Response templates
class ResponseTemplates:
    """Template responses for common scenarios."""
    
    LOGIN_ISSUES = [
        # Password reset
        "It looks like you need to reset your password. Click 'Forgot Password' on the login page "
        "and follow the instructions. Note that the reset link expires in 15 minutes, so act quickly. "
        "If the email doesn't arrive, please check your spam or junk folder.",
        
        # Account locked
        "Your account may be temporarily locked after too many failed attempts. Please wait 30 minutes "
        "before trying again. If you have two-factor authentication (2FA) enabled, make sure you're "
        "entering the latest code from your authenticator app. If you're still locked out, our support "
        "team can unlock your account manually — just reach out.",
        
        # General login help
        "Please double-check the email address you're signing in with — it's easy to mix up similar "
        "addresses. Also check for any accidental leading or trailing spaces in your password field. "
        "If you originally signed up via Google or another social provider, try that sign-in option "
        "instead of entering a password directly.",
    ]
    
    PAYMENT_ISSUES = [
        # Refund inquiry
        "For refund requests, please allow 3-5 business days for processing. If you haven't received "
        "your refund after this period, please contact our billing department with your order number "
        "and transaction date.",
        
        # Payment failure
        "Payment failures can occur due to various reasons. Please check that your card details are "
        "correct, that you have sufficient funds, and that your bank hasn't blocked the transaction. "
        "Try using a different payment method if the issue persists.",
    ]
    
    GENERAL_HELP = [
        "Thank you for contacting us. We've received your message and will respond within 24 hours. "
        "For urgent matters, please call our support hotline at 1-800-SUPPORT.",
    ]

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

# Database settings
DATABASE_POOL_SIZE = 10
DATABASE_MAX_OVERFLOW = 20

# Logging levels
LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

# API response codes
API_CODES = {
    "SUCCESS": 200,
    "CREATED": 201,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "UNPROCESSABLE_ENTITY": 422,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
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
    "RATE_LIMIT_PER_MINUTE",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "ERROR_MESSAGES",
    "SUCCESS_MESSAGES",
    "ResponseTemplates",
    "DEFAULT_CONFIG",
    "VALIDATION_PATTERNS",
    "API_CODES",
    "FEATURE_FLAGS",
]
