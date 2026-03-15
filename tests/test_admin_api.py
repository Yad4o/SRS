import pytest
import tempfile
import os
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import get_db, Base
from app.main import app
from app.models.ticket import Ticket
from app.models.feedback import Feedback
from app.models.user import User
from app.api.auth import create_access_token
from datetime import timedelta


@pytest.fixture(scope="function")
def temp_db():
    """Create temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Clean up after test - use try/except for Windows file locking
    try:
        if os.path.exists(path):
            os.unlink(path)
    except (OSError, PermissionError):
        # File might be locked, try again after a short delay
        time.sleep(0.1)
        try:
            if os.path.exists(path):
                os.unlink(path)
        except (OSError, PermissionError):
            # If still locked, leave it for OS cleanup
            pass


@pytest.fixture(scope="function")
def db_session(temp_db):
    """Create test database session with temporary database."""
    # Use temporary database path
    test_db_url = f"sqlite:///{temp_db}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Import models to ensure they're registered with Base
    from app.models.feedback import Feedback
    from app.models.ticket import Ticket
    from app.models.user import User
    
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()  # Dispose engine to release file locks


@pytest.fixture(scope="function")
def admin_user(db_session):
    """Create admin user for testing."""
    admin = User(
        email="admin@test.com",
        hashed_password="hashed_password",
        role="admin"
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture(scope="function")
def regular_user(db_session):
    """Create regular user for testing."""
    user = User(
        email="user@test.com",
        hashed_password="hashed_password",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_token(admin_user):
    """Create JWT token for admin user."""
    return create_access_token(
        data={"sub": str(admin_user.id), "role": admin_user.role},
        expires_delta=timedelta(minutes=30)
    )


@pytest.fixture(scope="function")
def user_token(regular_user):
    """Create JWT token for regular user."""
    return create_access_token(
        data={"sub": str(regular_user.id), "role": regular_user.role},
        expires_delta=timedelta(minutes=30)
    )


@pytest.fixture(scope="function")
def make_client(db_session):
    """Helper fixture to create TestClient with database override."""
    def _create_client():
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app)
    
    return _create_client


@pytest.fixture(scope="function")
def admin_client(make_client, admin_token):
    """Create test client with admin authentication."""
    client = make_client()
    with client:
        yield client
    # Clean up dependency override
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def user_client(make_client, user_token):
    """Create test client with regular user authentication."""
    client = make_client()
    with client:
        yield client
    # Clean up dependency override
    app.dependency_overrides.pop(get_db, None)


class TestAdminAPI:
    """Test cases for Admin API endpoints."""

    def test_admin_metrics_success(self, admin_client, admin_token, db_session):
        """Test successful admin metrics retrieval."""
        # Create test data
        ticket1 = Ticket(message="Ticket 1", status="auto_resolved", intent="login_issue", confidence=0.9)
        ticket2 = Ticket(message="Ticket 2", status="escalated", intent="payment_issue", confidence=0.7)
        ticket3 = Ticket(message="Ticket 3", status="open", intent="general", confidence=0.5)
        
        db_session.add_all([ticket1, ticket2, ticket3])
        db_session.commit()
        
        feedback1 = Feedback(ticket_id=ticket1.id, rating=5, resolved=True)
        feedback2 = Feedback(ticket_id=ticket2.id, rating=2, resolved=False)
        
        db_session.add_all([feedback1, feedback2])
        db_session.commit()
        
        # Call admin metrics endpoint
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = admin_client.get("/admin/metrics", headers=headers)
        
        assert response.status_code == 200
        metrics = response.json()
        
        # Verify ticket metrics
        assert "tickets" in metrics
        assert metrics["tickets"]["total"] == 3
        assert metrics["tickets"]["auto_resolved"] == 1
        assert metrics["tickets"]["escalated"] == 1
        assert metrics["tickets"]["open"] == 1
        assert metrics["tickets"]["auto_resolve_rate"] == 33.33  # 1/3 * 100
        assert metrics["tickets"]["escalation_rate"] == 33.33  # 1/3 * 100
        
        # Verify feedback metrics
        assert "feedback" in metrics
        assert metrics["feedback"]["total"] == 2
        assert metrics["feedback"]["average_rating"] == 3.5  # (5+2)/2
        assert metrics["feedback"]["resolution_rate"] == 50.0  # 1/2 * 100
        
        # Verify system health metrics
        assert "system_health" in metrics
        assert "auto_resolve_rate_status" in metrics["system_health"]
        assert "escalation_rate_status" in metrics["system_health"]
        assert "feedback_coverage" in metrics["system_health"]

    def test_admin_metrics_unauthorized(self, user_client, user_token):
        """Test admin metrics endpoint with regular user."""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = user_client.get("/admin/metrics", headers=headers)
        
        assert response.status_code == 403
        error_detail = response.json()
        assert "Access denied" in error_detail["detail"]
        assert "Admin role required" in error_detail["detail"]

    def test_admin_metrics_no_token(self, admin_client):
        """Test admin metrics endpoint without authentication."""
        response = admin_client.get("/admin/metrics")
        
        assert response.status_code == 401  # Unauthorized

    def test_admin_tickets_list_success(self, admin_client, admin_token, db_session):
        """Test successful admin tickets list retrieval."""
        # Create test tickets
        tickets = [
            Ticket(message="Ticket 1", status="auto_resolved", intent="login_issue", confidence=0.9),
            Ticket(message="Ticket 2", status="escalated", intent="payment_issue", confidence=0.7),
            Ticket(message="Ticket 3", status="open", intent="general", confidence=0.5),
            Ticket(message="Ticket 4", status="closed", intent="account_issue", confidence=0.8),
        ]
        
        db_session.add_all(tickets)
        db_session.commit()
        
        # Call admin tickets endpoint
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = admin_client.get("/admin/tickets", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "tickets" in data
        assert "pagination" in data
        assert "filters" in data
        
        # Verify tickets data
        tickets_list = data["tickets"]
        assert len(tickets_list) == 4
        
        # Verify pagination
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["limit"] == 50
        assert pagination["total"] == 4
        assert pagination["total_pages"] == 1
        assert pagination["has_next"] is False
        assert pagination["has_prev"] is False
        
        # Verify filters
        filters = data["filters"]
        assert filters["status"] is None

    def test_admin_tickets_list_with_filter(self, admin_client, admin_token, db_session):
        """Test admin tickets list with status filter."""
        # Create test tickets
        tickets = [
            Ticket(message="Ticket 1", status="auto_resolved", intent="login_issue", confidence=0.9),
            Ticket(message="Ticket 2", status="escalated", intent="payment_issue", confidence=0.7),
            Ticket(message="Ticket 3", status="auto_resolved", intent="general", confidence=0.5),
        ]
        
        db_session.add_all(tickets)
        db_session.commit()
        
        # Call admin tickets endpoint with filter
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = admin_client.get("/admin/tickets?status=auto_resolved", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filtered results - should only return auto_resolved tickets
        tickets_list = data["tickets"]
        assert len(tickets_list) == 2  # Only auto_resolved tickets
        
        for ticket in tickets_list:
            assert ticket["status"] == "auto_resolved"
        
        # Verify filters in response
        filters = data["filters"]
        assert filters["status"] == "auto_resolved"

    def test_admin_tickets_list_pagination(self, admin_client, admin_token, db_session):
        """Test admin tickets list pagination."""
        # Create test tickets
        tickets = [Ticket(message=f"Ticket {i}", status="open", intent="general", confidence=0.5) for i in range(5)]
        db_session.add_all(tickets)
        db_session.commit()
        
        # Call admin tickets endpoint with pagination
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = admin_client.get("/admin/tickets?page=1&limit=2", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination
        tickets_list = data["tickets"]
        assert len(tickets_list) == 2  # First page with limit 2
        
        pagination = data["pagination"]
        assert pagination["page"] == 1
        assert pagination["limit"] == 2
        assert pagination["total"] == 5
        assert pagination["total_pages"] == 3  # ceil(5/2)
        assert pagination["has_next"] is True
        assert pagination["has_prev"] is False

    def test_admin_tickets_list_unauthorized(self, user_client, user_token):
        """Test admin tickets list endpoint with regular user."""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = user_client.get("/admin/tickets", headers=headers)
        
        assert response.status_code == 403
        error_detail = response.json()
        assert "Access denied" in error_detail["detail"]
        assert "Admin role required" in error_detail["detail"]

    def test_admin_tickets_list_invalid_status(self, admin_client, admin_token):
        """Test admin tickets list with invalid status filter."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = admin_client.get("/admin/tickets?status=invalid_status", headers=headers)
        
        assert response.status_code == 400
        error_detail = response.json()
        assert "Invalid status" in error_detail["detail"]
        assert "invalid_status" in error_detail["detail"]

    def test_admin_tickets_list_no_token(self, admin_client):
        """Test admin tickets list endpoint without authentication."""
        response = admin_client.get("/admin/tickets")
        
        assert response.status_code == 401  # Unauthorized
