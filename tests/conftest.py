"""
 =============================================================================
 SRS (Support Request System) - Pytest Configuration and Shared Fixtures
 =============================================================================

Purpose:
--------
Comprehensive pytest configuration and shared test fixtures for the SRS application.

Features:
--------
- File-based SQLite database for consistent test isolation
- Comprehensive test data factories and helpers
- Authentication fixtures for different user roles
- Database cleanup and session management
- Mock utilities and assertion helpers
- Performance testing utilities
- Integration test helpers

Owner:
------
Backend Team

DO NOT:
-------
- Import application modules before environment setup
- Use in-memory SQLite (file-based ensures table persistence)
- Mix test concerns with production code
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Generator, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Ensure this project's app is loaded (not a parent directory's)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Create a temporary database file for tests
temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
temp_db.close()

# Set up test environment variables
os.environ["DATABASE_URL"] = f"sqlite:///{temp_db.name}"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-32-chars-long"
os.environ["ENV"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["REDIS_URL"] = ""  # Disable Redis for tests

# Import app components after setting up environment
from app.main import app
from app.db.session import engine, init_db, SessionLocal
from app.models.ticket import Ticket
from app.models.user import User
from app.models.feedback import Feedback
from app.api.auth import create_access_token
from app.core.config import settings

# Test client
client = TestClient(app)


class TestDataFactory:
    """Factory for creating comprehensive test data objects."""
    
    @staticmethod
    def create_user_data(
        email: str = None, 
        role: str = "user",
        **overrides
    ) -> Dict[str, Any]:
        """Create user test data with optional overrides."""
        base_data = {
            "email": email or f"test_{role}_{int(time.time())}@example.com",
            "role": role,
            "hashed_password": "fake-password-hash"
        }
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def create_ticket_data(
        message: str = None,
        status: str = "open",
        **overrides
    ) -> Dict[str, Any]:
        """Create ticket test data with optional overrides."""
        base_data = {
            "message": message or f"Test ticket message {int(time.time())}",
            "status": status
        }
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def create_feedback_data(
        ticket_id: int = None,
        rating: int = 5,
        comment: str = None,
        **overrides
    ) -> Dict[str, Any]:
        """Create feedback test data with optional overrides."""
        base_data = {
            "ticket_id": ticket_id or 1,
            "rating": rating,
            "comment": comment or "Test feedback comment"
        }
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def create_multiple_tickets(count: int, **overrides) -> List[Dict[str, Any]]:
        """Create multiple ticket data objects."""
        return [
            TestDataFactory.create_ticket_data(
                message=f"Test ticket message {i+1}",
                **overrides
            )
            for i in range(count)
        ]


class DatabaseHelper:
    """Helper class for comprehensive database operations in tests."""
    
    @staticmethod
    def cleanup_tables():
        """Clean up all test data in proper order to avoid foreign key constraints."""
        with engine.connect() as conn:
            # Delete in order of dependencies
            conn.execute(Feedback.__table__.delete())
            conn.execute(Ticket.__table__.delete())
            conn.execute(User.__table__.delete())
            conn.commit()
    
    @staticmethod
    def create_user(db: Session, email: str = None, role: str = "user", **overrides) -> User:
        """Create a user in the database."""
        user_data = TestDataFactory.create_user_data(email, role, **overrides)
        user = User(**user_data)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def create_ticket(
        db: Session, 
        message: str = None, 
        user_id: Optional[int] = None,
        status: str = "open",
        **overrides
    ) -> Ticket:
        """Create a ticket in the database."""
        ticket_data = TestDataFactory.create_ticket_data(message, status, **overrides)
        ticket = Ticket(**ticket_data, user_id=user_id)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket
    
    @staticmethod
    def create_feedback(
        db: Session,
        ticket_id: int,
        rating: int = 5,
        comment: str = None,
        **overrides
    ) -> Feedback:
        """Create feedback in the database."""
        feedback_data = TestDataFactory.create_feedback_data(ticket_id, rating, comment, **overrides)
        feedback = Feedback(**feedback_data)
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback
    
    @staticmethod
    def create_test_dataset(db: Session) -> Dict[str, Any]:
        """Create a comprehensive test dataset."""
        # Create users
        admin_user = DatabaseHelper.create_user(db, role="admin")
        agent_user = DatabaseHelper.create_user(db, role="agent")
        regular_user = DatabaseHelper.create_user(db, role="user")
        
        # Create tickets
        ticket1 = DatabaseHelper.create_ticket(
            db, 
            message="Login issue test ticket",
            user_id=regular_user.id,
            status="auto_resolved",
            response="Test response for login issue"
        )
        
        ticket2 = DatabaseHelper.create_ticket(
            db,
            message="Payment problem test ticket",
            user_id=regular_user.id,
            status="escalated"
        )
        
        ticket3 = DatabaseHelper.create_ticket(
            db,
            message="General inquiry test ticket",
            user_id=agent_user.id,
            status="open"
        )
        
        # Create feedback
        feedback1 = DatabaseHelper.create_feedback(
            db,
            ticket_id=ticket1.id,
            rating=5,
            comment="Great support!"
        )
        
        return {
            "admin_user": admin_user,
            "agent_user": agent_user,
            "regular_user": regular_user,
            "tickets": [ticket1, ticket2, ticket3],
            "feedback": [feedback1]
        }


class AuthHelper:
    """Helper class for comprehensive authentication in tests."""
    
    @staticmethod
    def create_token(user_id: str, role: str = "user", **claims) -> str:
        """Create an access token for testing with additional claims."""
        token_data = {"sub": str(user_id), "role": role}
        token_data.update(claims)
        token = create_access_token(data=token_data)
        return f"Bearer {token}"
    
    @staticmethod
    def create_admin_token(user_id: str) -> str:
        """Create an admin token for testing."""
        return AuthHelper.create_token(user_id, "admin")
    
    @staticmethod
    def create_agent_token(user_id: str) -> str:
        """Create an agent token for testing."""
        return AuthHelper.create_token(user_id, "agent")
    
    @staticmethod
    def create_user_token(user_id: str) -> str:
        """Create a user token for testing."""
        return AuthHelper.create_token(user_id, "user")
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode a token for testing purposes."""
        from app.core.security import decode_token
        clean_token = token.replace("Bearer ", "")
        return decode_token(clean_token)


class MockHelper:
    """Helper class for creating and managing mocks in tests."""
    
    @staticmethod
    def create_openai_mock(response_text: str = "Mock AI response") -> MagicMock:
        """Create a mock OpenAI client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = response_text
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client
    
    @staticmethod
    def create_redis_mock() -> MagicMock:
        """Create a mock Redis client."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.ping.return_value = True
        mock_redis.keys.return_value = []
        mock_redis.delete.return_value = 0
        return mock_redis
    
    @staticmethod
    def patch_openai(response_text: str = "Mock AI response"):
        """Context manager for patching OpenAI."""
        with patch('app.services.ai_service.openai') as mock_openai:
            mock_openai.ChatCompletion.create.return_value = {
                'choices': [{'message': {'content': response_text}}]
            }
            yield mock_openai
    
    @staticmethod
    def patch_redis():
        """Context manager for patching Redis."""
        mock_redis = MockHelper.create_redis_mock()
        with patch('app.services.similarity_search._redis_client', mock_redis):
            yield mock_redis


class PerformanceHelper:
    """Helper class for performance testing utilities."""
    
    @staticmethod
    def measure_time(func, *args, **kwargs) -> tuple:
        """Measure execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        return result, duration
    
    @staticmethod
    def assert_response_time(response_time: float, max_time: float):
        """Assert response time is within acceptable limits."""
        assert response_time < max_time, f"Response time {response_time:.3f}s exceeds limit {max_time:.3f}s"
    
    @staticmethod
    def create_performance_load(count: int, func, *args, **kwargs) -> List[float]:
        """Create performance load and return execution times."""
        times = []
        for _ in range(count):
            _, duration = PerformanceHelper.measure_time(func, *args, **kwargs)
            times.append(duration)
        return times


class BaseTestClass:
    """Base class for test classes with comprehensive functionality."""
    
    @staticmethod
    def assert_ticket_response(data: Dict[str, Any], expected_message: str = None):
        """Assert common ticket response structure."""
        assert "id" in data
        assert "message" in data
        assert "status" in data
        assert "created_at" in data
        
        if expected_message:
            assert data["message"] == expected_message
        
        assert data["status"] in ["auto_resolved", "escalated", "open", "closed"]
    
    @staticmethod
    def assert_user_response(data: Dict[str, Any], expected_email: str = None):
        """Assert common user response structure."""
        assert "id" in data
        assert "email" in data
        assert "role" in data
        
        if expected_email:
            assert data["email"] == expected_email
        
        assert data["role"] in ["user", "agent", "admin"]
    
    @staticmethod
    def assert_error_response(response, expected_status: int, expected_detail: str = None):
        """Assert error response structure."""
        assert response.status_code == expected_status
        
        response_data = response.json()
        assert "detail" in response_data
        
        if expected_detail:
            assert expected_detail in response_data["detail"]
    
    @staticmethod
    def assert_pagination_response(data: Dict[str, Any], expected_count: int = None):
        """Assert pagination response structure."""
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data
        assert "pages" in data
        
        if expected_count:
            assert data["total"] == expected_count
    
    @staticmethod
    def create_mock_ticket(**overrides) -> MagicMock:
        """Create a mock ticket object."""
        mock_ticket = MagicMock()
        mock_ticket.id = overrides.get("id", 1)
        mock_ticket.message = overrides.get("message", "Test message")
        mock_ticket.status = overrides.get("status", "open")
        mock_ticket.created_at = overrides.get("created_at", time.time())
        mock_ticket.user_id = overrides.get("user_id", 1)
        return mock_ticket
    
    @staticmethod
    def create_mock_user(**overrides) -> MagicMock:
        """Create a mock user object."""
        mock_user = MagicMock()
        mock_user.id = overrides.get("id", 1)
        mock_user.email = overrides.get("email", "test@example.com")
        mock_user.role = overrides.get("role", "user")
        return mock_user


# -----------------------------------------------------------------------------
# Enhanced Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_database():
    """Initialize database for all tests with proper cleanup."""
    init_db()
    DatabaseHelper.cleanup_tables()
    yield
    DatabaseHelper.cleanup_tables()


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


@pytest.fixture
def reset_limiter():
    """Reset rate limiter between tests."""
    from app.core.limiter import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    return DatabaseHelper.create_user(db, role="admin")


@pytest.fixture
def agent_user(db):
    """Create an agent user for testing."""
    return DatabaseHelper.create_user(db, role="agent")


@pytest.fixture
def regular_user(db):
    """Create a regular user for testing."""
    return DatabaseHelper.create_user(db, role="user")


@pytest.fixture
def admin_token(admin_user):
    """Create an admin token for testing."""
    return AuthHelper.create_admin_token(str(admin_user.id))


@pytest.fixture
def agent_token(agent_user):
    """Create an agent token for testing."""
    return AuthHelper.create_agent_token(str(agent_user.id))


@pytest.fixture
def user_token(regular_user):
    """Create a user token for testing."""
    return AuthHelper.create_user_token(str(regular_user.id))


@pytest.fixture
def sample_ticket(db, regular_user):
    """Create a sample ticket for testing."""
    return DatabaseHelper.create_ticket(
        db,
        message="Sample test ticket message",
        user_id=regular_user.id
    )


@pytest.fixture
def sample_feedback(db, sample_ticket):
    """Create sample feedback for testing."""
    return DatabaseHelper.create_feedback(
        db,
        ticket_id=sample_ticket.id,
        rating=4,
        comment="Sample feedback comment"
    )


@pytest.fixture
def test_dataset(db):
    """Create a comprehensive test dataset."""
    return DatabaseHelper.create_test_dataset(db)


@pytest.fixture
def mock_openai():
    """Provide a mock OpenAI client."""
    return MockHelper.create_openai_mock()


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    return MockHelper.create_redis_mock()


@pytest.fixture
def performance_monitor():
    """Provide performance monitoring utilities."""
    return PerformanceHelper()


# -----------------------------------------------------------------------------
# Custom Pytest Markers
# -----------------------------------------------------------------------------

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "ai: marks tests that require AI services"
    )
    config.addinivalue_line(
        "markers", "redis: marks tests that require Redis"
    )


# -----------------------------------------------------------------------------
# Test Collection Hooks
# -----------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test characteristics."""
    for item in items:
        # Add markers based on test names
        if "performance" in item.name.lower():
            item.add_marker(pytest.mark.slow)
        
        if "integration" in item.name.lower():
            item.add_marker(pytest.mark.integration)
        
        if "ai" in item.name.lower() or "openai" in item.name.lower():
            item.add_marker(pytest.mark.ai)
        
        if "redis" in item.name.lower():
            item.add_marker(pytest.mark.redis)


# -----------------------------------------------------------------------------
# Environment Cleanup
# -----------------------------------------------------------------------------

def pytest_sessionfinish(session, exitstatus):
    """Clean up temporary database file after test session."""
    import gc
    
    # Force garbage collection to close any remaining connections
    gc.collect()
    
    # Close database engine
    engine.dispose()
    
    try:
        # Wait a moment for file handles to be released
        time.sleep(0.1)
        os.unlink(temp_db.name)
    except (OSError, PermissionError) as e:
        # Log the error but don't fail the test session
        print(f"Warning: Could not clean up temporary database file {temp_db.name}: {e}")
    except FileNotFoundError:
        # File already cleaned up, ignore
        pass


# -----------------------------------------------------------------------------
# Test Utilities
# -----------------------------------------------------------------------------

def run_performance_test(test_func, iterations: int = 10, max_time: float = 1.0):
    """Run a performance test with multiple iterations."""
    times = PerformanceHelper.create_performance_load(iterations, test_func)
    
    avg_time = sum(times) / len(times)
    max_time_actual = max(times)
    min_time_actual = min(times)
    
    print(f"Performance Results ({iterations} iterations):")
    print(f"  Average: {avg_time:.3f}s")
    print(f"  Min: {min_time_actual:.3f}s")
    print(f"  Max: {max_time_actual:.3f}s")
    
    # Assert performance requirements
    PerformanceHelper.assert_response_time(avg_time, max_time)
    
    return {
        "average": avg_time,
        "min": min_time_actual,
        "max": max_time_actual,
        "times": times
    }


def create_authenticated_client(token: str) -> TestClient:
    """Create an authenticated test client."""
    return TestClient(app, headers={"Authorization": token})


def assert_api_response_format(response, expected_status: int = 200):
    """Assert common API response format."""
    assert response.status_code == expected_status
    
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, (dict, list))
    
    elif response.status_code >= 400:
        data = response.json()
        assert "detail" in data
