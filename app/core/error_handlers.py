"""
app/core/error_handlers.py

Purpose:
--------
Implement FastAPI exception handlers for consistent error responses.

Owner:
------
Backend Team

Responsibilities:
-----------------
- Register FastAPI exception handlers
- Log errors server-side without exposing details
- Return appropriate HTTP status codes
- Handle AI/service failures with fallback responses

DO NOT:
-------
- Expose stack traces to clients
- Include sensitive internal information
- Return raw exception messages to clients
"""

import logging
import traceback
from typing import Any
from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    BaseAPIException,
    AppValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    InternalError,
    AIServiceError,
    DatabaseError,
    RateLimitError,
    create_error_response
)

# Configure logger for error handling
logger = logging.getLogger(__name__)


def _sanitize_error_details(error_details: dict[str, Any] | None) -> str:
    """
    Sanitize error details for safe logging.
    
    Args:
        error_details: Raw error details that may contain sensitive information
        
    Returns:
        Sanitized string safe for logging
    """
    if error_details is None:
        return "Unknown error"
    
    # Extract safe information only
    safe_parts = []
    
    if "service" in error_details:
        safe_parts.append(f"service={error_details['service']}")
    
    if "operation" in error_details:
        safe_parts.append(f"operation={error_details['operation']}")
    
    if "error_type" in error_details:
        safe_parts.append(f"error_type={error_details['error_type']}")
    
    # Never include error_message as it may contain sensitive data
    if safe_parts:
        return ", ".join(safe_parts) + " (<redacted error>)"
    else:
        return "<redacted error>"


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle FastAPI request validation errors.
    
    Args:
        request: FastAPI request object
        exc: RequestValidationError exception
        
    Returns:
        JSONResponse with validation error details
    """
    # Log the validation error — only field path and type, NOT the input value
    # to avoid logging user-supplied data (passwords, PII, secrets, etc.)
    safe_errors = [{"loc": e["loc"], "type": e["type"]} for e in exc.errors()]
    logger.warning(f"Validation error in {request.method} {request.url.path}: {safe_errors}")
    
    # Convert Pydantic validation errors to our format
    validation_details = []
    for error in exc.errors():
        validation_details.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    # Create application validation exception
    app_exc = AppValidationError(
        message="Request validation failed",
        details={"validation_errors": validation_details}
    )
    
    return JSONResponse(
        status_code=400,
        content=create_error_response(app_exc, include_details=True)
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions.
    
    Args:
        request: FastAPI request object
        exc: HTTPException
        
    Returns:
        JSONResponse with HTTP error details
    """
    # Log the HTTP exception
    logger.warning(f"HTTP exception in {request.method} {request.url.path}: {exc.status_code} - {exc.detail}")
    
    # Map HTTP status codes to our custom exception types
    error_mapping = {
        400: AppValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        405: InternalError,
        429: RateLimitError,
        500: InternalError,
    }

    error_class = error_mapping.get(exc.status_code, InternalError)

    # Create exception with appropriate constructor
    try:
        if exc.status_code == 400:
            app_exc = error_class(message=exc.detail, details=None)
        else:
            app_exc = error_class(message=exc.detail)
    except TypeError:
        # Fallback to generic InternalError if constructor fails
        logger.error(
            f"Failed to create {error_class.__name__} from {type(exc).__name__}: "
            f"status_code={getattr(exc, 'status_code', None)}, "
            f"detail={getattr(exc, 'detail', None)}"
        )
        app_exc = InternalError(message=exc.detail)

    # Ensure proper error code preservation for non-500 responses
    if error_class is not InternalError:
        app_exc.code = getattr(error_class, "code", None)
    elif exc.status_code < 500:
        app_exc.code = f"HTTP_{exc.status_code}"
    
    # Ensure the JSON body status_code reflects the real HTTP status, not
    # the default from the exception class (e.g. InternalError defaults to 500
    # but a 405 should report 405 in the body as well).
    app_exc.status_code = exc.status_code

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(app_exc)
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions.
    
    Args:
        request: FastAPI request object
        exc: Unhandled exception
        
    Returns:
        JSONResponse with generic error message
    """
    # Log the full exception for debugging
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: {type(exc).__name__}: {exc!s}\n"
        f"Traceback: {traceback.format_exc()}"
    )
    
    # Return generic internal error to client
    app_exc = InternalError("An unexpected error occurred")
    
    return JSONResponse(
        status_code=500,
        content=create_error_response(app_exc)
    )


async def api_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    """
    Handle our custom API exceptions.
    
    Args:
        request: FastAPI request object
        exc: BaseAPIException
        
    Returns:
        JSONResponse with standardized error format
    """
    # Log the API exception
    log_level = logging.WARNING if exc.status_code < 500 else logging.ERROR
    logger.log(
        log_level,
        f"API exception in {request.method} {request.url.path}: {exc.error_code} - {exc.message}"
    )
    
    # Special handling for AI service errors (return 200 with fallback)
    if isinstance(exc, AIServiceError):
        logger.info(f"AI service fallback activated: {exc.message}")
        
        # Set Retry-After header if specified
        headers = {}
        if exc.details and "retry_after" in exc.details:
            headers["Retry-After"] = str(exc.details["retry_after"])
        
        return JSONResponse(
            status_code=200,
            content=create_error_response(exc, include_details=True),
            headers=headers
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc, include_details=False)
    )


def setup_exception_handlers(app) -> None:
    """
    Register all exception handlers with FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # Register handlers for different exception types
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # Register both FastAPI and Starlette HTTPException variants.
    # FastAPI raises its own HTTPException in route handlers, but the router
    # raises starlette.exceptions.HTTPException for 404/405. We need both so
    # route-not-found and method-not-allowed errors use our standardised format.
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(BaseAPIException, api_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")


def handle_ai_service_failure(
    operation: str,
    fallback_data: dict[str, Any],
    error_details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Handle AI service failures with fallback response.
    
    Args:
        operation: Description of the AI operation that failed
        fallback_data: Fallback response data
        error_details: Optional error details for logging
        
    Returns:
        Response dictionary with fallback data and error information
    """
    # Log the AI service failure
    logger.warning(
        f"AI service failure in {operation}: {_sanitize_error_details(error_details)}"
    )
    
    # Return fallback response with error information
    return {
        "data": fallback_data,
        "fallback_used": True,
        "error": {
            "code": "AI_SERVICE_ERROR",
            "message": "AI service temporarily unavailable, using fallback response"
        }
    }
