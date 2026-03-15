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
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    BaseAPIException,
    ValidationError as AppValidationError,
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


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle FastAPI request validation errors.
    
    Args:
        request: FastAPI request object
        exc: RequestValidationError exception
        
    Returns:
        JSONResponse with validation error details
    """
    # Log the validation error for debugging
    logger.warning(f"Validation error in {request.method} {request.url}: {exc.errors()}")
    
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
    logger.warning(f"HTTP exception in {request.method} {request.url}: {exc.status_code} - {exc.detail}")
    
    # Map HTTP status codes to our error types
    error_mapping = {
        400: AppValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
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
        f"Unhandled exception in {request.method} {request.url}: {type(exc).__name__}: {exc!s}\n"
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
        f"API exception in {request.method} {request.url}: {exc.error_code} - {exc.message}"
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
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(BaseAPIException, api_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered successfully")


def handle_ai_service_failure(
    operation: str,
    fallback_data: Dict[str, Any],
    error_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
        f"AI service failure in {operation}: {error_details or 'Unknown error'}"
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
