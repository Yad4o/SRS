"""
pytest configuration and shared fixtures.

Sets up test environment before any app imports.
Uses file-based SQLite for database tests to ensure table persistence.
Enhanced with common test utilities and helper classes.
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Ensure this project's app is loaded (not a parent directory's)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Create a temporary database file for tests
temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
temp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{temp_db.name}"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"

# Import app components after setting up environment
from app.main import app
from app.db.session import engine, init_db
from app.models.ticket import Ticket
from app.models.user import User
from app.api.auth import create_access_token

# Test client
client = TestClient(app)


class TestDataFactory:
    """Factory for creating test data objects."""
    
    @staticmethod
    def create_user_data(email: str = None, role: str = "user") -> Dict[str, Any]:
        """Create user test data."""
        return {
            "email": email or f"test_{role}@example.com",
            "role": role,
            "hashed_password": "fake-password-hash"
        }
    
    @staticmethod
    def create_ticket_data(message: str = None) -> Dict[str, Any]:
        """Create ticket test data."""
        return {
            "message": message or "Test ticket message"
        }


class DatabaseHelper:
    """Helper class for database operations in tests."""
    
    @staticmethod
    def cleanup_tables():
        """Clean up all test data."""
        with engine.connect() as conn:
            conn.execute(Ticket.__table__.delete())
            conn.execute(User.__table__.delete())
            conn.commit()
    
    @staticmethod
    def create_user(db: Session, email: str = None, role: str = "user") -> User:
        """Create a user in the database."""
        user_data = TestDataFactory.create_user_data(email, role)
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def create_ticket(db: Session, message: str = None, user_id: Optional[int] = None) -> Ticket:
        """Create a ticket in the database."""
        ticket_data = TestDataFactory.create_ticket_data(message)
        ticket = Ticket(**ticket_data, user_id=user_id)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket


class AuthHelper:
    """Helper class for authentication in tests."""
    
    @staticmethod
    def create_token(user_id: str, role: str = "user") -> str:
        """Create an access token for testing."""
        token = create_access_token(data={"sub": str(user_id), "role": role})
        return f"Bearer {token}"
    
    @staticmethod
    def create_agent_token(user_id: str) -> str:
        """Create an agent token for testing."""
        return AuthHelper.create_token(user_id, "agent")
    
    @staticmethod
    def create_user_token(user_id: str) -> str:
        """Create a user token for testing."""
        return AuthHelper.create_token(user_id, "user")

    @staticmethod
    def create_admin_token(user_id: str) -> str:
        """Create an admin token for testing."""
        return AuthHelper.create_token(user_id, "admin")


# Enhanced fixtures
@pytest.fixture(autouse=True)
def setup_database():
    """Initialize database for all tests."""
    init_db()
    DatabaseHelper.cleanup_tables()


@pytest.fixture
def db():
    """Create a new database session for a test."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset rate limiter between tests."""
    from app.core.limiter import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def agent_user(db):
    """Create an agent user for testing."""
    return DatabaseHelper.create_user(db, role="agent")


@pytest.fixture
def regular_user(db):
    """Create a regular user for testing."""
    return DatabaseHelper.create_user(db, role="user")


@pytest.fixture
def agent_token(agent_user):
    """Create an agent token for testing."""
    return AuthHelper.create_agent_token(str(agent_user.id))


@pytest.fixture
def user_token(regular_user):
    """Create a user token for testing."""
    return AuthHelper.create_user_token(str(regular_user.id))


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    return DatabaseHelper.create_user(db, role="admin")


@pytest.fixture
def admin_token(admin_user):
    """Create an admin token for testing."""
    return AuthHelper.create_admin_token(str(admin_user.id))


class BaseTestClass:
    """Base class for test classes with common functionality."""
    
    @staticmethod
    def assert_ticket_response(data: Dict[str, Any], expected_message: str):
        """Assert common ticket response structure."""
        assert data["message"] == expected_message
        assert data["status"] in ["auto_resolved", "escalated", "open"]
        assert "id" in data
        assert "created_at" in data
    
    @staticmethod
    def assert_error_response(response, expected_status: int, expected_message: Optional[str] = None):
        """Assert error response structure."""
        assert response.status_code == expected_status
        if expected_message:
            data = response.json()
            if "error" in data:
                error_val = data.get("error")
                actual_msg = error_val.get("message", "") if isinstance(error_val, dict) else str(error_val)
            else:
                actual_msg = data.get("detail", "")
                if isinstance(actual_msg, list):
                    actual_msg = str(actual_msg)
            assert expected_message.lower() in actual_msg.lower()
    
    @staticmethod
    def create_mock_ticket():
        """Create a mock ticket object."""
        mock_ticket = MagicMock()
        mock_ticket.id = 1
        mock_ticket.message = "Test message"
        mock_ticket.status = "open"
        return mock_ticket


# Clean up the temp database file after tests
def pytest_sessionfinish(session, exitstatus):
    """Clean up temporary database file after test session."""
    try:
        # Properly dispose the engine and close all connections
        engine.dispose()
        
        # Wait a moment for file handles to be released
        import time
        time.sleep(0.1)
        os.unlink(temp_db.name)
    except (OSError, PermissionError) as e:
        # Log the error but don't fail the test session
        print(f"Warning: Could not clean up temporary database file {temp_db.name}: {e}")
    except FileNotFoundError:
        # File already cleaned up, ignore
        pass
