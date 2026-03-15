import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import get_db, Base
from app.main import app
from app.models.ticket import Ticket
from app.models.feedback import Feedback


@pytest.fixture(scope="function")
def temp_db():
    """Create temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close file descriptor, keep path for SQLAlchemy
    yield path
    # Clean up after test - use try/except for Windows file locking
    try:
        if os.path.exists(path):
            os.unlink(path)
    except (OSError, PermissionError):
        # File might be locked, try again after a short delay
        import time
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
    
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)  # Drop tables before disposing engine
        engine.dispose()


@pytest.fixture(scope="function")
def client(temp_db):
    """Create test client with database override."""
    # Set up a separate engine and sessionmaker for this client, using the temp DB
    test_db_url = f"sqlite:///{temp_db}"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Ensure tables exist for the duration of this fixture
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        # Clean up override and database after test
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


class TestFeedbackAPI:
    """Test cases for Feedback API endpoints."""

    def test_create_feedback_success(self, client, db_session):
        """Test successful feedback creation."""
        # Create a ticket first
        ticket = Ticket(
            message="Test ticket for feedback",
            intent="login_issue",
            confidence=0.9,
            status="auto_resolved",
            response="Test response"
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        # Create feedback for the ticket
        feedback_data = {
            "ticket_id": ticket.id,
            "rating": 5,
            "resolved": True
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 201
        feedback_response = response.json()
        
        assert feedback_response["ticket_id"] == ticket.id
        assert feedback_response["rating"] == 5
        assert feedback_response["resolved"] is True
        assert "id" in feedback_response
        assert "created_at" in feedback_response

    def test_create_feedback_ticket_not_resolved(self, client, db_session):
        """Test feedback creation with non-resolved ticket."""
        # Create a ticket that's not resolved
        ticket = Ticket(
            message="Test ticket not resolved",
            intent="general",
            confidence=0.8,
            status="open"  # Not resolved
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        feedback_data = {
            "ticket_id": ticket.id,
            "rating": 3,
            "resolved": False
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 400
        error_detail = response.json()
        assert "error" in error_detail
        assert "not resolved" in error_detail["error"]["message"].lower()

    def test_create_feedback_duplicate(self, client, db_session):
        """Test duplicate feedback prevention."""
        # Create a resolved ticket
        ticket = Ticket(
            message="Test ticket for duplicate",
            intent="payment_issue",
            confidence=0.7,
            status="auto_resolved",
            response="Payment issue resolved"
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        # Create first feedback
        feedback_data = {
            "ticket_id": ticket.id,
            "rating": 4,
            "resolved": True
        }
        
        response1 = client.post("/feedback/", json=feedback_data)
        assert response1.status_code == 201
        
        # Try to create second feedback for same ticket
        response2 = client.post("/feedback/", json=feedback_data)
        
        assert response2.status_code == 409
        error_detail = response2.json()
        assert "error" in error_detail
        assert "already exists" in error_detail["error"]["message"].lower()

    def test_create_feedback_ticket_not_found(self, client, db_session):
        """Test feedback creation with non-existent ticket."""
        feedback_data = {
            "ticket_id": 99999,
            "rating": 3,
            "resolved": False
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 404
        error_detail = response.json()
        assert "error" in error_detail
        assert "not found" in error_detail["error"]["message"].lower()

    def test_create_feedback_invalid_rating(self, client, db_session):
        """Test feedback creation with invalid rating."""
        # Create a ticket first
        ticket = Ticket(
            message="Test ticket",
            intent="general",
            confidence=0.8,
            status="escalated"
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        # Test with invalid rating (too high)
        feedback_data = {
            "ticket_id": ticket.id,
            "rating": 6,  # Invalid: should be 1-5
            "resolved": True
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 400  # Validation error

    def test_get_feedback_by_ticket_id_success(self, client, db_session):
        """Test successful feedback retrieval by ticket ID."""
        # Create ticket and feedback
        ticket = Ticket(
            message="Test ticket",
            intent="payment_issue",
            confidence=0.7,
            status="auto_resolved",
            response="Payment issue resolved"
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        feedback = Feedback(
            ticket_id=ticket.id,
            rating=4,
            resolved=True
        )
        db_session.add(feedback)
        db_session.commit()
        db_session.refresh(feedback)
        
        # Get feedback by ticket ID
        response = client.get(f"/feedback/{ticket.id}")
        
        assert response.status_code == 200
        feedback_response = response.json()
        
        assert feedback_response["id"] == feedback.id
        assert feedback_response["ticket_id"] == ticket.id
        assert feedback_response["rating"] == 4
        assert feedback_response["resolved"] is True
        assert "created_at" in feedback_response

    def test_get_feedback_by_ticket_id_not_found(self, client, db_session):
        """Test feedback retrieval for non-existent ticket."""
        response = client.get("/feedback/99999")
        
        assert response.status_code == 404
        error_detail = response.json()
        assert "error" in error_detail
        assert "no feedback found" in error_detail["error"]["message"].lower()

    def test_get_feedback_by_query_success(self, client, db_session):
        """Test successful feedback retrieval using query parameter."""
        # Create ticket and feedback
        ticket = Ticket(
            message="Test ticket for query",
            intent="account_issue",
            confidence=0.6,
            status="escalated"
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        feedback = Feedback(
            ticket_id=ticket.id,
            rating=2,
            resolved=False
        )
        db_session.add(feedback)
        db_session.commit()
        db_session.refresh(feedback)
        
        # Get feedback using query parameter
        response = client.get(f"/feedback/?ticket_id={ticket.id}")
        
        assert response.status_code == 200
        feedback_response = response.json()
        
        assert feedback_response["id"] == feedback.id
        assert feedback_response["ticket_id"] == ticket.id
        assert feedback_response["rating"] == 2
        assert feedback_response["resolved"] is False

    def test_get_feedback_by_query_not_found(self, client, db_session):
        """Test feedback retrieval using query parameter for non-existent ticket."""
        response = client.get("/feedback/?ticket_id=99999")
        
        assert response.status_code == 404
        error_detail = response.json()
        assert "error" in error_detail
        assert "no feedback found" in error_detail["error"]["message"].lower()

    def test_feedback_schema_validation(self, client, db_session):
        """Test feedback schema validation."""
        # Test missing required fields
        invalid_data = {
            "rating": 3
            # Missing ticket_id and resolved
        }
        
        response = client.post("/feedback/", json=invalid_data)
        
        assert response.status_code == 400  # Validation error
        
        # Test invalid rating range
        invalid_rating_data = {
            "ticket_id": 1,
            "rating": 0,  # Invalid: should be 1-5
            "resolved": True
        }
        
        response = client.post("/feedback/", json=invalid_rating_data)
        
        assert response.status_code == 400  # Validation error

    def test_feedback_end_to_end_workflow(self, client, db_session):
        """Test complete feedback workflow."""
        # 1. Create a ticket
        ticket_data = {"message": "I need help with my account"}
        ticket_response = client.post("/tickets/", json=ticket_data)
        assert ticket_response.status_code == 201
        ticket = ticket_response.json()
        
        # 2. Manually set ticket to resolved state before creating feedback
        # This ensures the feedback creation requirement (status in {"auto_resolved", "closed"}) is satisfied
        db_ticket = db_session.query(Ticket).filter(Ticket.id == ticket["id"]).first()
        if db_ticket:
            # Update ticket to auto_resolved state
            db_ticket.status = "auto_resolved"
            db_ticket.response = "Test resolution for feedback workflow"
            db_session.commit()
            db_session.refresh(db_ticket)
            # Update ticket dict with resolved status
            ticket["status"] = "auto_resolved"
            ticket["response"] = "Test resolution for feedback workflow"
        
        # 3. Create feedback for the resolved ticket
        feedback_data = {
            "ticket_id": ticket["id"],
            "rating": 4,
            "resolved": True
        }
        feedback_response = client.post("/feedback/", json=feedback_data)
        assert feedback_response.status_code == 201
        feedback = feedback_response.json()
        
        # 4. Retrieve feedback
        get_response = client.get(f"/feedback/{ticket['id']}")
        assert get_response.status_code == 200
        retrieved_feedback = get_response.json()
        
        # 5. Verify all data is consistent
        assert retrieved_feedback["id"] == feedback["id"]
        assert retrieved_feedback["ticket_id"] == ticket["id"]
        assert retrieved_feedback["rating"] == 4
        assert retrieved_feedback["resolved"] is True
        assert "created_at" in retrieved_feedback
