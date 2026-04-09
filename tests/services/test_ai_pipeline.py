import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import get_db, Base
from app.main import app
from app.models.ticket import Ticket
import os
import tempfile

@pytest.fixture(scope="session")
def temp_db_file():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    yield db_path
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db_engine(temp_db_file):
    url = f"sqlite:///{temp_db_file}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, TestingSessionLocal

def override_get_db(db_engine):
    engine, TestingSessionLocal = db_engine
    def _override():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    return _override


@pytest.fixture(scope="function")
def client(db_engine):
    app.dependency_overrides[get_db] = override_get_db(db_engine)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def db_session(db_engine):
    engine, TestingSessionLocal = db_engine
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_ai_pipeline_auto_resolve(db_session, client):
    """Test AI pipeline with auto-resolve decision."""
    # Create a resolved ticket for similarity search
    resolved_ticket = Ticket(
        message="I cannot login to my account",
        intent="login_issue",
        confidence=0.9,
        status="auto_resolved",
        response="Try resetting your password using the forgot password link."
    )
    db_session.add(resolved_ticket)
    db_session.commit()
    
    # Create new ticket with similar message
    response = client.post("/tickets/", json={"message": "Cannot login to my account"})
    
    assert response.status_code == 201
    ticket_data = response.json()
    
    # Should be auto-resolved
    assert ticket_data["status"] == "auto_resolved"
    assert ticket_data["intent"] == "login_issue"
    assert ticket_data["confidence"] is not None
    assert ticket_data["response"] is not None
    assert "password" in ticket_data["response"].lower()


def test_ai_pipeline_escalate(db_session, client):
    """Test AI pipeline with escalate decision."""
    # Create new ticket with low confidence intent
    response = client.post("/tickets/", json={"message": "Something completely new and unusual"})
    
    assert response.status_code == 201
    ticket_data = response.json()
    
    # Should be escalated
    assert ticket_data["status"] == "escalated"
    assert ticket_data["intent"] is not None
    assert ticket_data["confidence"] is not None
    assert ticket_data["response"] is None


def test_ai_pipeline_similarity_reuse(db_session, client):
    """Test AI pipeline reuses similar solutions."""
    # Create resolved ticket with specific solution
    resolved_ticket = Ticket(
        message="Payment was charged twice",
        intent="payment_issue",
        confidence=0.8,
        status="auto_resolved",
        response="We've processed a refund for the duplicate charge. It should appear in 3-5 business days."
    )
    db_session.add(resolved_ticket)
    db_session.commit()
    
    # Create similar ticket
    response = client.post("/tickets/", json={"message": "I was charged twice for my order"})
    
    assert response.status_code == 201
    ticket_data = response.json()
    
    # Should be auto-resolved with similar solution
    assert ticket_data["status"] == "auto_resolved"
    assert ticket_data["response"] is not None
    assert len(ticket_data["response"]) > 10  # Just check it's a meaningful response


def test_ai_pipeline_response_schema(db_session, client):
    """Test AI pipeline returns correct response schema."""
    response = client.post("/tickets/", json={"message": "Test message"})
    
    assert response.status_code == 201
    ticket_data = response.json()
    
    # Verify all required fields are present
    required_fields = ["id", "message", "intent", "confidence", "status", "response", "created_at"]
    for field in required_fields:
        assert field in ticket_data, f"Missing field: {field}"
    
    # Verify data types
    assert isinstance(ticket_data["id"], int)
    assert isinstance(ticket_data["message"], str)
    assert ticket_data["intent"] is None or isinstance(ticket_data["intent"], str)
    assert ticket_data["confidence"] is None or isinstance(ticket_data["confidence"], (int, float))
    assert isinstance(ticket_data["status"], str)
    assert ticket_data["response"] is None or isinstance(ticket_data["response"], str)
    assert ticket_data["created_at"] is not None


def test_ai_pipeline_end_to_end(db_session, client):
    """Test complete end-to-end AI pipeline."""
    # Create several resolved tickets with different solutions
    resolved_tickets = [
        Ticket(
            message="Cannot login to account",
            intent="login_issue",
            confidence=0.9,
            status="auto_resolved",
            response="Reset your password using the forgot password link."
        ),
        Ticket(
            message="Payment problem",
            intent="payment_issue", 
            confidence=0.8,
            status="auto_resolved",
            response="Check your billing statement for recent transactions."
        ),
        Ticket(
            message="Account update needed",
            intent="account_issue",
            confidence=0.7,
            status="auto_resolved",
            response="Update your profile information in account settings."
        )
    ]
    
    for ticket in resolved_tickets:
        db_session.add(ticket)
    db_session.commit()
    
    # Test different scenarios
    test_cases = [
        ("I can't log in", "auto_resolved"),  # High confidence, similar solution
        ("xyz123 abc456", None),  # Very low confidence - let AI decide
        ("Need to update profile", None),  # Let AI decide - just verify it's processed
    ]
    
    for message, expected_status in test_cases:
        response = client.post("/tickets/", json={"message": message})
        assert response.status_code == 201
        
        ticket_data = response.json()
        
        # Check status based on expected_status
        if expected_status:
            assert ticket_data["status"] == expected_status  # Enforce specific outcome
        else:
            # Just verify it's processed by AI
            assert ticket_data["status"] in ["auto_resolved", "escalated"]
        
        assert ticket_data["intent"] is not None
        assert ticket_data["confidence"] is not None
        
        if ticket_data["status"] == "auto_resolved":
            assert ticket_data["response"] is not None
            assert len(ticket_data["response"]) > 10
        else:
            assert ticket_data["response"] is None
