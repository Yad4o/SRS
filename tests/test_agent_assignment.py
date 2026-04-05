"""
Tests for agent assignment and ticket close endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import get_db, Base
from app.models.ticket import Ticket
from app.models.user import User


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database file."""
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def client_with_temp_db(temp_db):
    """Create test client with temporary database using shared session."""
    engine = create_engine(
        f"sqlite:///{temp_db}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Single shared session for both test and requests
    shared_db = TestingSessionLocal()
    original_override = app.dependency_overrides.get(get_db)
    
    def override_get_db():
        try:
            yield shared_db
        finally:
            pass  # Don't close here - test manages lifecycle
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, shared_db
    finally:
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)
        shared_db.close()
        engine.dispose()


def test_agent_can_assign_escalated_ticket(client_with_temp_db):
    """Test that an agent can assign an escalated ticket to themselves."""
    from app.api.auth import create_access_token
    
    client, db = client_with_temp_db
    
    agent = User(
        email="agent@test.com",
        hashed_password="hashed_password",
        role="agent"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    ticket = Ticket(
        message="Escalated ticket",
        status="escalated",
        user_id=None
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(f"/tickets/{ticket.id}/assign", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["assigned_agent_id"] == agent.id
    assert data["id"] == ticket.id


def test_regular_user_gets_403_when_assigning_ticket(client_with_temp_db):
    """Test that a regular user gets 403 when trying to assign a ticket."""
    from app.api.auth import create_access_token
    
    client, db = client_with_temp_db
    
    user = User(
        email="user@test.com",
        hashed_password="hashed_password",
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    ticket = Ticket(
        message="Escalated ticket",
        status="escalated",
        user_id=None
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    token = create_access_token(data={"sub": str(user.id), "role": "user"})
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(f"/tickets/{ticket.id}/assign", headers=headers)
    
    assert response.status_code == 403
    assert "Access denied" in response.json()["error"]["message"]


def test_assign_auto_resolved_ticket_returns_409(client_with_temp_db):
    """Test that trying to assign an auto_resolved ticket returns 409 (conflict)."""
    from app.api.auth import create_access_token
    
    client, db = client_with_temp_db
    
    agent = User(
        email="agent@test.com",
        hashed_password="hashed_password",
        role="agent"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    ticket = Ticket(
        message="Auto resolved ticket",
        status="auto_resolved",
        user_id=None,
        response="Auto response",
        intent="test_intent",
        confidence=0.9
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(f"/tickets/{ticket.id}/assign", headers=headers)
    
    assert response.status_code == 409
    assert "cannot assign" in response.json()["error"]["message"]


def test_agent_can_close_escalated_ticket(client_with_temp_db):
    """Test that an agent can close an escalated ticket."""
    from app.api.auth import create_access_token
    
    client, db = client_with_temp_db
    
    agent = User(
        email="agent@test.com",
        hashed_password="hashed_password",
        role="agent"
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    
    ticket = Ticket(
        message="Escalated ticket to close",
        status="escalated",
        user_id=None
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(f"/tickets/{ticket.id}/close", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    assert data["id"] == ticket.id


def test_close_ticket_has_status_closed_in_response(client_with_temp_db):
    """Test that the closed ticket has status 'closed' in the response."""
    from app.api.auth import create_access_token
    
    client, db = client_with_temp_db
    
    admin = User(
        email="admin@test.com",
        hashed_password="hashed_password",
        role="admin"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    ticket = Ticket(
        message="Ticket to close",
        status="escalated",
        user_id=None
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    token = create_access_token(data={"sub": str(admin.id), "role": "admin"})
    
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(f"/tickets/{ticket.id}/close", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    
    db.refresh(ticket)
    assert ticket.status == "closed"
