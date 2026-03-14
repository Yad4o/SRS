"""
Test feedback API functionality.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.db.session import get_db, Base
from app.models.ticket import Ticket
from app.models.feedback import Feedback


app = create_app()
client = TestClient(app)


class TestFeedbackAPI:
    """Test feedback API endpoints."""
    
    def test_create_feedback_success(self, db_session: Session):
        """Test successful feedback creation."""
        # Create a test ticket first
        ticket = Ticket(
            message="Test ticket for feedback",
            status="auto_resolved"
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        # Submit feedback
        feedback_data = {
            "ticket_id": ticket.id,
            "rating": 5,
            "resolved": True
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["ticket_id"] == ticket.id
        assert data["rating"] == 5
        assert data["resolved"] is True
        assert "created_at" in data
    
    def test_create_feedback_invalid_ticket(self, db_session: Session):
        """Test feedback creation with non-existent ticket."""
        feedback_data = {
            "ticket_id": 99999,
            "rating": 5,
            "resolved": True
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_create_feedback_invalid_rating(self, db_session: Session):
        """Test feedback creation with invalid rating."""
        # Create a test ticket first
        ticket = Ticket(message="Test ticket", status="auto_resolved")
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        feedback_data = {
            "ticket_id": ticket.id,
            "rating": 6,  # Invalid rating (should be 1-5)
            "resolved": True
        }
        
        response = client.post("/feedback/", json=feedback_data)
        
        assert response.status_code == 400
        assert "Rating must be between 1 and 5" in response.json()["detail"]
    
    def test_get_feedback_by_id(self, db_session: Session):
        """Test retrieving feedback by ticket ID."""
        # Create ticket and feedback
        ticket = Ticket(message="Test ticket", status="auto_resolved")
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
        
        # Retrieve feedback
        response = client.get(f"/feedback/{ticket.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticket_id"] == ticket.id
        assert data["rating"] == 4
        assert data["resolved"] is True
    
    def test_get_feedback_by_query(self, db_session: Session):
        """Test retrieving feedback using query parameter."""
        # Create ticket and feedback
        ticket = Ticket(message="Test ticket", status="auto_resolved")
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        feedback = Feedback(
            ticket_id=ticket.id,
            rating=3,
            resolved=False
        )
        db_session.add(feedback)
        db_session.commit()
        db_session.refresh(feedback)
        
        # Retrieve feedback using query parameter
        response = client.get(f"/feedback/?ticket_id={ticket.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ticket_id"] == ticket.id
        assert data["rating"] == 3
        assert data["resolved"] is False
    
    def test_get_feedback_not_found(self):
        """Test retrieving feedback for non-existent ticket."""
        response = client.get("/feedback/99999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_feedback_health(self):
        """Test feedback health endpoint."""
        response = client.get("/feedback/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "feedback-api"
        assert "endpoints" in data


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    from app.db.session import engine, Base
    from sqlalchemy.orm import sessionmaker
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
