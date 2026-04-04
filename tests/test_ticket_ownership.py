"""
Tests for ticket ownership functionality.

Covers:
- Creating tickets without authentication (user_id=None)
- Creating tickets with authentication (user_id set)
- User-specific ticket filtering
- Admin/agent access to all tickets
"""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import get_db, Base
from app.main import app
from app.models.ticket import Ticket
from app.models.user import User


@pytest.fixture(scope="function")
def temp_db():
    """Create temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close file descriptor, keep path for SQLAlchemy
    yield path
    # Clean up after test - use try/except for Windows file locking
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def client_with_temp_db(temp_db):
    """Create test client with temporary database."""
    engine = create_engine(
        f"sqlite:///{temp_db}",
        connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Create a db session for tests to use directly
    db = TestingSessionLocal()
    
    def override_get_db():
        # Create a new session per request
        request_db = TestingSessionLocal()
        try:
            yield request_db
        finally:
            request_db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        yield client, db  # Yield both client and db session for test use
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_create_ticket_without_token(client_with_temp_db, temp_db):
    """Test POST /tickets without token creates ticket with user_id=None."""
    client, _ = client_with_temp_db
    
    # Create ticket without authentication
    response = client.post("/tickets/", json={"message": "I need help with login"})
    assert response.status_code == 201
    
    ticket_data = response.json()
    assert ticket_data["user_id"] is None
    
    # Verify in database
    engine = create_engine(f"sqlite:///{temp_db}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_data["id"]).first()
    assert ticket.user_id is None
    db.close()


def test_create_ticket_with_valid_token(client_with_temp_db, temp_db):
    """Test POST /tickets with valid token creates ticket with correct user_id."""
    from app.api.auth import create_access_token
    
    client, _ = client_with_temp_db
    
    # Create a test user in the same database
    engine = create_engine(f"sqlite:///{temp_db}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    user = User(
        email="test@example.com",
        hashed_password="hashed_password",
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    # Create token for the user
    token = create_access_token(data={"sub": str(user.id), "role": "user"})
    
    # Create ticket with authentication
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/tickets/", json={"message": "I need help with payment"}, headers=headers)
    assert response.status_code == 201
    
    ticket_data = response.json()
    assert ticket_data["user_id"] == user.id
    
    # Verify in database
    db = TestingSessionLocal()
    ticket = db.query(Ticket).filter(Ticket.id == ticket_data["id"]).first()
    assert ticket.user_id == user.id
    db.close()


def test_list_tickets_user_token_filters_by_user(client_with_temp_db, temp_db):
    """Test GET /tickets with user token only returns that user's tickets."""
    from app.api.auth import create_access_token
    
    client, _ = client_with_temp_db
    
    # Create two test users in the same database
    engine = create_engine(f"sqlite:///{temp_db}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    user1 = User(
        email="user1@example.com",
        hashed_password="hashed_password",
        role="user"
    )
    user2 = User(
        email="user2@example.com", 
        hashed_password="hashed_password",
        role="user"
    )
    db.add(user1)
    db.add(user2)
    db.commit()
    db.refresh(user1)
    db.refresh(user2)
    
    # Store user IDs before closing session
    user1_id = user1.id
    user2_id = user2.id
    
    # Create tickets for both users
    ticket1 = Ticket(message="User 1 ticket", user_id=user1_id)
    ticket2 = Ticket(message="User 2 ticket", user_id=user2_id)
    ticket3 = Ticket(message="Unauthenticated ticket", user_id=None)
    
    db.add(ticket1)
    db.add(ticket2)
    db.add(ticket3)
    db.commit()
    db.close()
    
    # Create token for user1
    token = create_access_token(data={"sub": str(user1_id), "role": "user"})
    
    # Get tickets with user1 token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/tickets/", headers=headers)
    assert response.status_code == 200
    
    tickets_data = response.json()
    assert len(tickets_data["tickets"]) == 1
    assert tickets_data["tickets"][0]["user_id"] == user1_id
    assert tickets_data["tickets"][0]["message"] == "User 1 ticket"


def test_list_tickets_admin_token_returns_all_tickets(client_with_temp_db, temp_db):
    """Test GET /tickets with admin token returns all tickets."""
    from app.api.auth import create_access_token
    
    client, _ = client_with_temp_db
    
    # Create users in the same database
    engine = create_engine(f"sqlite:///{temp_db}")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    admin_user = User(
        email="admin@example.com",
        hashed_password="hashed_password",
        role="admin"
    )
    regular_user = User(
        email="user@example.com",
        hashed_password="hashed_password", 
        role="user"
    )
    db.add(admin_user)
    db.add(regular_user)
    db.commit()
    db.refresh(admin_user)
    db.refresh(regular_user)
    
    # Store user IDs before closing session
    admin_user_id = admin_user.id
    regular_user_id = regular_user.id
    
    # Create tickets
    ticket1 = Ticket(message="User ticket", user_id=regular_user_id)
    ticket2 = Ticket(message="Admin ticket", user_id=admin_user_id)
    ticket3 = Ticket(message="Unauthenticated ticket", user_id=None)
    
    db.add(ticket1)
    db.add(ticket2)
    db.add(ticket3)
    db.commit()
    db.close()
    
    # Create token for admin
    token = create_access_token(data={"sub": str(admin_user_id), "role": "admin"})
    
    # Get tickets with admin token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/tickets/", headers=headers)
    assert response.status_code == 200
    
    tickets_data = response.json()
    assert len(tickets_data["tickets"]) == 3  # All tickets returned


def test_list_tickets_agent_token_returns_all_tickets(client_with_temp_db, temp_db):
    """Test GET /tickets with agent token returns all tickets."""
    from app.api.auth import create_access_token
    
    client, db = client_with_temp_db
    
    # Create users in the same database (use the shared session)
    agent_user = User(
        email="agent2@example.com",
        hashed_password="hashed_password",
        role="agent"
    )
    regular_user = User(
        email="user2@example.com",
        hashed_password="hashed_password",
        role="user"
    )
    db.add(agent_user)
    db.add(regular_user)
    db.commit()
    db.refresh(agent_user)
    db.refresh(regular_user)
    
    # Store user IDs
    agent_user_id = agent_user.id
    regular_user_id = regular_user.id
    
    # Create tickets (use the shared session)
    ticket1 = Ticket(message="User ticket", user_id=regular_user_id)
    ticket2 = Ticket(message="Agent ticket", user_id=agent_user_id)
    
    db.add(ticket1)
    db.add(ticket2)
    db.commit()
    
    # Create token for agent
    token = create_access_token(data={"sub": str(agent_user_id), "role": "agent"})
    
    # Get tickets with agent token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/tickets/", headers=headers)
    assert response.status_code == 200
    
    tickets_data = response.json()
    assert len(tickets_data["tickets"]) == 2  # All tickets returned


def test_list_tickets_without_token_returns_all_tickets(client_with_temp_db, temp_db):
    """Test GET /tickets without token returns all tickets (unauthenticated access)."""
    client, db = client_with_temp_db
    
    # Create a user for the first ticket
    user = User(
        email="ticketowner@example.com",
        hashed_password="hashed_password",
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create tickets directly in database (use the shared session)
    ticket1 = Ticket(message="Ticket 1", user_id=user.id)
    ticket2 = Ticket(message="Ticket 2", user_id=None)
    
    db.add(ticket1)
    db.add(ticket2)
    db.commit()
    
    # Get tickets without authentication
    response = client.get("/tickets/")
    assert response.status_code == 200
    
    tickets_data = response.json()
    assert len(tickets_data["tickets"]) == 2  # All tickets returned
