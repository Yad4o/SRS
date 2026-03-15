"""
app/core/exceptions.py

Purpose:
--------
Define custom exception classes for consistent error handling across the API.

Owner:
------
Backend Team

Responsibilities:
-----------------
- Define application-specific exception types
- Map error types to HTTP status codes
- Provide consistent error structure for API responses

DO NOT:
-------
- Include sensitive internal information in error messages
- Expose stack traces or implementation details
- Use generic exceptions for business logic errors
"""

from typing import Optional, Dict, Any


class BaseAPIException(Exception):
    """Base exception for all API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseAPIException):
    """Raised when request validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details
        )


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
    """Raised when AI service operations fail."""
    
    def __init__(self, message: str = "AI service temporarily unavailable", details: Optional[Dict[str, Any]] = None, retry_after: Optional[int] = None):
        if details is None:
            details = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
            
        super().__init__(
            message=message,
            status_code=503,  # Service Unavailable
            error_code="AI_SERVICE_ERROR",
            details=details
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


# Error type to HTTP status code mapping
# Note: AIServiceError maps to 200 in ERROR_RESPONSE_STATUS_MAPPING because the handler
# returns 200 with fallback content, even though AIServiceError itself defines status_code=503
ERROR_RESPONSE_STATUS_MAPPING = {
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    NotFoundError: 404,
    InternalError: 500,
    AIServiceError: 200,  # Special case: returns 200 with fallback
    DatabaseError: 500,
    RateLimitError: 429,
}


def create_error_response(
    error: BaseAPIException,
    include_details: bool = False
) -> Dict[str, Any]:
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
