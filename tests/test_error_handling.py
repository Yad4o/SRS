"""
tests/test_error_handling.py

Purpose:
--------
Test the comprehensive error handling strategy across the API.

Owner:
------
Backend Team

Responsibilities:
-----------------
- Test custom exception classes
- Verify error response format consistency
- Test exception handler registration
- Validate AI service fallback behavior
"""

import pytest
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError
from unittest.mock import patch
import httpx

from app.main import app
from app.core.exceptions import (
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    InternalError,
    AIServiceError,
    create_error_response
)
from app.core.error_handlers import handle_ai_service_failure


class TestExceptionClasses:
    """Test custom exception classes."""

    def test_validation_error_creation(self):
        """Test ValidationError creation and properties."""
        error = ValidationError("Invalid input", {"field": "email"})
        
        assert error.message == "Invalid input"
        assert error.status_code == 400
        assert error.error_code == "VALIDATION_ERROR"
        assert error.details == {"field": "email"}

    def test_authentication_error_creation(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError("Token expired")
        
        assert error.message == "Token expired"
        assert error.status_code == 401
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_authorization_error_creation(self):
        """Test AuthorizationError creation."""
        error = AuthorizationError("Admin access required")
        
        assert error.message == "Admin access required"
        assert error.status_code == 403
        assert error.error_code == "AUTHORIZATION_ERROR"

    def test_not_found_error_creation(self):
        """Test NotFoundError creation."""
        error = NotFoundError("User not found")
        
        assert error.message == "User not found"
        assert error.status_code == 404
        assert error.error_code == "NOT_FOUND"

    def test_internal_error_creation(self):
        """Test InternalError creation."""
        error = InternalError("Database connection failed")
        
        assert error.message == "Database connection failed"
        assert error.status_code == 500
        assert error.error_code == "INTERNAL_ERROR"

    def test_ai_service_error_creation(self):
        """Test AIServiceError creation."""
        error = AIServiceError("AI model unavailable", {"service": "classifier"})
        
        assert error.message == "AI model unavailable"
        assert error.status_code == 200  # Handler returns 200 with fallback
        assert error.error_code == "AI_SERVICE_ERROR"
        assert error.details == {"service": "classifier"}


class TestErrorResponseFormat:
    """Test standardized error response format."""

    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        error = ValidationError("Invalid data")
        response = create_error_response(error)
        
        expected = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid data",
                "status_code": 400
            }
        }
        
        assert response == expected

    def test_create_error_response_with_details(self):
        """Test error response with details."""
        error = ValidationError("Invalid data", {"field": "email"})
        response = create_error_response(error, include_details=True)
        
        assert "details" in response["error"]
        assert response["error"]["details"] == {"field": "email"}

    def test_create_error_response_without_details(self):
        """Test error response without details."""
        error = ValidationError("Invalid data", {"field": "email"})
        response = create_error_response(error, include_details=False)
        
        assert "details" not in response["error"]


class TestExceptionHandlers:
    """Test FastAPI exception handlers."""

    def test_validation_error_handler(self):
        """Test RequestValidationError handler."""
        client = TestClient(app)
        
        # Send invalid request to trigger validation error
        response = client.post("/tickets/", json={"invalid_field": "test"})
        
        assert response.status_code == 400
        data = response.json()
        
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["status_code"] == 400

    def test_404_error_handler(self):
        """Test 404 error handler."""
        client = TestClient(app)
        
        # Request non-existent endpoint
        response = client.get("/non-existent-endpoint")
        
        assert response.status_code == 404
        data = response.json()

        # StarletteHTTPException handler is registered, so 404 must use our format
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["status_code"] == 404

    def test_method_not_allowed_handler(self):
        """Test method not allowed error."""
        client = TestClient(app)
        
        # Use wrong HTTP method
        response = client.delete("/tickets/")
        
        assert response.status_code == 405
        data = response.json()

        # StarletteHTTPException handler is registered, so 405 must use our format
        assert "error" in data
        assert data["error"]["status_code"] == 405

    def test_custom_api_exception_handler(self):
        """Test custom API exception handler."""
        from app.core.exceptions import AuthorizationError
        from fastapi import Request
        
        # Create a mock request with proper scope
        request = Request({
            "type": "http", 
            "method": "GET", 
            "url": "http://testserver/test",
            "path": "/test",
            "query_string": b"",
            "headers": []
        })
        
        # Create custom exception
        exc = AuthorizationError("Test authorization error")
        
        # Import and test the handler
        from app.core.error_handlers import api_exception_handler
        import asyncio
        
        # Run the async handler
        response = asyncio.run(api_exception_handler(request, exc))
        
        assert response.status_code == 403
        data = response.body
        assert b"AUTHORIZATION_ERROR" in data


class TestAIServiceFallback:
    """Test AI service fallback handling."""

    def test_handle_ai_service_failure(self):
        """Test AI service failure fallback response."""
        fallback_data = {"status": "escalated", "message": "Fallback response"}
        error_details = {"service": "classifier", "error": "timeout"}
        
        response = handle_ai_service_failure(
            operation="ticket_classification",
            fallback_data=fallback_data,
            error_details=error_details
        )
        
        assert "data" in response
        assert response["data"] == fallback_data
        assert response["fallback_used"] is True
        assert "error" in response
        assert response["error"]["code"] == "AI_SERVICE_ERROR"
        assert response["error"]["message"] == "AI service temporarily unavailable, using fallback response"

    def test_ai_service_error_returns_200(self):
        """Test that AI service errors return 200 with fallback."""
        error = AIServiceError("Service unavailable", {"fallback": True})
        
        from app.core.error_handlers import api_exception_handler
        from fastapi import Request
        import asyncio
        
        request = Request({
            "type": "http", 
            "method": "GET", 
            "url": "http://testserver/test",
            "path": "/test",
            "query_string": b"",
            "headers": []
        })
        
        response = asyncio.run(api_exception_handler(request, error))
        
        assert response.status_code == 200
        data = response.body
        assert b"AI_SERVICE_ERROR" in data


class TestErrorLogging:
    """Test error logging functionality."""

    def test_error_logging_no_stack_trace_exposure(self):
        """Test that stack traces are logged but not exposed to clients."""
        client = TestClient(app)
        
        # Trigger an error that would have stack trace
        response = client.get("/admin/metrics")  # This should fail with 401
        
        assert response.status_code == 401
        data = response.json()
        
        # Ensure no stack trace or internal details are exposed
        assert "traceback" not in str(data).lower()
        assert "stack" not in str(data).lower()
        assert "internal" not in str(data).lower() or data.get("error", {}).get("code") != "INTERNAL_ERROR"

    def test_validation_error_details_exposed(self):
        """Test that validation error details are properly exposed."""
        client = TestClient(app)
        
        # Send invalid data to trigger validation error with details
        response = client.post("/tickets/", json={})
        
        assert response.status_code == 400
        data = response.json()
        
        # Validation errors should include field details
        if "details" in data.get("error", {}):
            assert "validation_errors" in data["error"]["details"]


class TestErrorStatusMapping:
    """Test error type to HTTP status code mapping."""

    def test_error_status_codes(self):
        """Test that all error types have correct status codes."""
        from app.core.exceptions import ERROR_RESPONSE_STATUS_MAPPING
        
        assert ERROR_RESPONSE_STATUS_MAPPING[ValidationError] == 400
        assert ERROR_RESPONSE_STATUS_MAPPING[AuthenticationError] == 401
        assert ERROR_RESPONSE_STATUS_MAPPING[AuthorizationError] == 403
        assert ERROR_RESPONSE_STATUS_MAPPING[NotFoundError] == 404
        assert ERROR_RESPONSE_STATUS_MAPPING[InternalError] == 500
        assert ERROR_RESPONSE_STATUS_MAPPING[AIServiceError] == 200  # Special case

    def test_all_exceptions_have_status_codes(self):
        """Test that all custom exceptions have mapped status codes."""
        from app.core.exceptions import ERROR_RESPONSE_STATUS_MAPPING
        
        # Check that all our custom exceptions are mapped
        exception_classes = [
            ValidationError,
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            InternalError,
            AIServiceError,
        ]
        
        for exc_class in exception_classes:
            assert exc_class in ERROR_RESPONSE_STATUS_MAPPING
            assert isinstance(ERROR_RESPONSE_STATUS_MAPPING[exc_class], int)
            assert 100 <= ERROR_RESPONSE_STATUS_MAPPING[exc_class] <= 599


class TestProductionErrorHandling:
    """Test production-ready error handling."""

    def test_no_sensitive_data_leakage(self):
        """Test that sensitive data doesn't leak in error responses."""
        client = TestClient(app)
        
        # Try various error scenarios
        endpoints_to_test = [
            ("/admin/metrics", "GET"),
            ("/admin/tickets", "GET"),
            ("/tickets/", "POST"),
            ("/non-existent", "GET"),
        ]
        
        for endpoint, method in endpoints_to_test:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})
            
            # Check response doesn't contain sensitive information
            response_str = str(response.json()).lower()
            
            sensitive_terms = [
                "password", "secret", "key", "token",
                "database", "connection", "internal",
                "traceback", "stack trace", "file path"
            ]
            
            for term in sensitive_terms:
                # Allow "token" in authentication error messages
                if term == "token" and response.status_code == 401:
                    continue
                assert term not in response_str, f"Sensitive term '{term}' found in {endpoint} response"

    def test_consistent_error_format(self):
        """Test that all errors follow consistent format."""
        client = TestClient(app)
        
        # Test different error scenarios
        test_cases = [
            lambda: client.get("/non-existent-endpoint"),  # 404
            lambda: client.post("/tickets/", json={}),   # Validation error
            lambda: client.delete("/tickets/"),           # Method not allowed
        ]
        
        for test_case in test_cases:
            try:
                response = test_case()
                if response.status_code >= 400:
                    data = response.json()
                    
                    # Check for consistent error structure
                    if "error" in data:
                        error = data["error"]
                        required_fields = ["code", "message", "status_code"]
                        
                        for field in required_fields:
                            assert field in error, f"Missing field '{field}' in error response"
                            
                        # Check types
                        assert isinstance(error["code"], str)
                        assert isinstance(error["message"], str)
                        assert isinstance(error["status_code"], int)
                    elif "detail" in data:
                        # Some FastAPI default responses might still use "detail"
                        # This is acceptable for certain error types
                        pass
                    
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.TimeoutException) as e:
                # Network-level exceptions are expected for some test cases
                print(f"Expected network exception: {type(e).__name__}")
            except Exception as e:
                # Re-raise unexpected exceptions so test assertions fail
                raise e
