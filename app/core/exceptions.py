"""
app/core/exceptions.py

Purpose:
Define custom exception classes for consistent error handling across the API.

Responsibilities:
- Define application-specific exception types
- Map error types to HTTP status codes
- Provide consistent error structure for API responses

DO NOT:
- Include sensitive internal information in error messages
- Expose stack traces or implementation details
- Use generic exceptions for business logic errors
"""

from typing import Any


class BaseAPIException(Exception):
    """Base exception for all API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
        details: dict[str, Any] | None = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class AppValidationError(BaseAPIException):
    """Raised when request validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details
        )


# Backward-compatible alias — use AppValidationError in new code to avoid
# shadowing pydantic.ValidationError at import time.
ValidationError = AppValidationError


class AuthenticationError(BaseAPIException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(BaseAPIException):
    """Raised when authorization fails (user lacks permissions)."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR"
        )


class NotFoundError(BaseAPIException):
    """Raised when a requested resource is not found."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND"
        )


class InternalError(BaseAPIException):
    """Raised when an unexpected internal error occurs."""
    
    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="INTERNAL_ERROR"
        )


class AIServiceError(BaseAPIException):
    """Raised when AI service operations fail.

    The handler returns HTTP 200 with fallback content for AI failures so that
    callers (clients) do not surface hard errors to end-users — the service
    degrades gracefully.  The status_code here therefore matches that wire
    behaviour (200), not the conventional 503.
    """

    def __init__(self, message: str = "AI service temporarily unavailable", details: dict[str, Any] | None = None, retry_after: int | None = None):
        new_details = dict(details) if details is not None else {}
        if retry_after is not None:
            new_details["retry_after"] = retry_after

        super().__init__(
            message=message,
            status_code=200,  # Handler returns 200 with fallback — graceful degradation
            error_code="AI_SERVICE_ERROR",
            details=new_details
        )


class DatabaseError(BaseAPIException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR"
        )


class RateLimitError(BaseAPIException):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_ERROR"
        )


# Error type to HTTP status code mapping.
# AIServiceError maps to 200 because the handler returns 200 with fallback content.
ERROR_RESPONSE_STATUS_MAPPING = {
    AppValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    NotFoundError: 404,
    InternalError: 500,
    AIServiceError: 200,  # Special case: AI failures return 200 with fallback
    DatabaseError: 500,
    RateLimitError: 429,
}


def create_error_response(
    error: BaseAPIException,
    include_details: bool = False
) -> dict[str, Any]:
    """
    Create standardized error response.
    
    Args:
        error: The exception that occurred
        include_details: Whether to include error details (for debugging)
        
    Returns:
        Standardized error response dictionary
    """
    response = {
        "error": {
            "code": error.error_code,
            "message": error.message,
            "status_code": error.status_code
        }
    }
    
    # Include details only if explicitly requested and available
    if include_details and error.details:
        response["error"]["details"] = error.details
    
    return response

