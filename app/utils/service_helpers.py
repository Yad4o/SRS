"""
app/utils/service_helpers.py

Purpose:
--------
Common utility functions for service layer operations.

Owner:
------
Service Utilities

Responsibilities:
-----------------
- Common database operations
- Error handling helpers
- Validation utilities
- Response formatting
"""

import hashlib
import json
import logging
import re
from datetime import datetime, date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DatabaseOps:
    """Common database operations."""
    
    @staticmethod
    def safe_commit(db: Session) -> bool:
        """Safely commit a database transaction."""
        try:
            db.commit()
            return True
        except Exception as e:
            logger.exception("Database commit failed")
            db.rollback()
            return False
    
    @staticmethod
    def create_with_rollback(db: Session, model, **kwargs):
        """Create a model instance with automatic rollback on failure."""
        try:
            instance = model(**kwargs)
            db.add(instance)
            db.commit()
            db.refresh(instance)
            return instance
        except Exception as e:
            logger.exception(f"Failed to create {model.__name__}")
            db.rollback()
            raise
    
    @staticmethod
    def get_or_none(db: Session, model, id: int):
        """Get a model instance by ID or return None."""
        try:
            return db.query(model).filter(model.id == id).first()
        except Exception as e:
            logger.exception(f"Failed to get {model.__name__} with id {id}")
            return None


class ResponseFormatter:
    """Common response formatting utilities."""
    
    @staticmethod
    def success_response(data: Any = None, message: str = "Operation successful") -> dict[str, Any]:
        """Format a successful response."""
        response = {"success": True, "message": message}
        if data is not None:
            response["data"] = data
        return response
    
    @staticmethod
    def error_response(message: str, code: str = "ERROR", details: Any = None) -> dict[str, Any]:
        """Format an error response."""
        response = {"success": False, "error": {"code": code, "message": message}}
        if details is not None:
            response["error"]["details"] = details
        return response
    
    @staticmethod
    def paginated_response(items: list[Any], total: int, page: int = 1, limit: int = 50) -> dict[str, Any]:
        """Format a paginated response."""
        return {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit
            }
        }


class ValidationHelper:
    """Common validation utilities."""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Basic email validation."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def sanitize_string(text: str, max_length: int | None = None) -> str:
        """Sanitize string input."""
        if not isinstance(text, str):
            text = str(text)

        text = re.sub(r'[<>]', '', text)

        if max_length and len(text) > max_length:
            text = text[:max_length]

        return text.strip()
    
    @staticmethod
    def validate_pagination_params(page: int = 1, limit: int = 50) -> tuple[int, int]:
        """Validate and normalize pagination parameters."""
        page = max(1, int(page)) if page else 1
        limit = min(max(1, int(limit)) if limit else 50, 100)  # Max 100 items per page
        return page, limit


class CacheHelper:
    """Common caching utilities."""
    
    @staticmethod
    def make_cache_key(prefix: str, *args) -> str:
        """Generate a cache key from prefix and arguments."""
        key_string = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    @staticmethod
    def serialize_for_cache(data: Any) -> str:
        """Serialize data for caching."""
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                if isinstance(obj, Decimal):
                    return float(obj)
                return super().default(obj)

        return json.dumps(data, cls=CustomJSONEncoder)
    
    @staticmethod
    def deserialize_from_cache(data: str) -> Any:
        """Deserialize data from cache."""
        return json.loads(data)


class ErrorHelper:
    """Common error handling utilities."""
    
    @staticmethod
    def log_and_raise(error: Exception, message: str = "An error occurred"):
        """Log an error and raise it."""
        logger.exception(message)
        raise error
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str) -> dict[str, Any]:
        """Handle database errors consistently."""
        logger.exception(f"Database error during {operation}")
        return ResponseFormatter.error_response(
            message="Database operation failed",
            code="DATABASE_ERROR",
            details={"operation": operation}
        )
    
    @staticmethod
    def handle_validation_error(errors: list[str]) -> dict[str, Any]:
        """Handle validation errors consistently."""
        return ResponseFormatter.error_response(
            message="Validation failed",
            code="VALIDATION_ERROR",
            details={"validation_errors": errors}
        )


class MetricsHelper:
    """Common metrics and logging utilities."""
    
    @staticmethod
    def log_operation(operation: str, user_id: str | None = None, **kwargs):
        """Log an operation with optional user context."""
        log_data = {"operation": operation, "timestamp": datetime.utcnow().isoformat()}
        if user_id:
            log_data["user_id"] = user_id
        log_data.update(kwargs)
        logger.info(f"Operation: {log_data}")
    
    @staticmethod
    def log_performance(operation: str, duration: float, **kwargs):
        """Log performance metrics."""
        logger.info(f"Performance: {operation} took {duration:.2f}s")
        if kwargs:
            logger.info(f"Additional metrics: {kwargs}")


# Convenience imports for backward compatibility
safe_commit = DatabaseOps.safe_commit
create_with_rollback = DatabaseOps.create_with_rollback
get_or_none = DatabaseOps.get_or_none
