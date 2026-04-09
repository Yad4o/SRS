"""
tests/test_agent_assignment.py

Tests for agent assignment and ticket close endpoints.

Session strategy
----------------
A single TestingSessionLocal session factory is created per test function.
Both the test body and the FastAPI dependency override use **the same factory**,
so writes committed by the test body (via `db`) are immediately visible to HTTP
requests handled by the app — there is no cross-session read-lock issue common
with SQLite default journal mode.

Error shape
-----------
API errors are returned with the shape {"error": {"message": "..."}}.
All assertions match against response.json()["error"]["message"].
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
def client_with_temp_db(tmp_path):
    """
    Provide (client, db) with correctly isolated sessions.

    Session isolation model
    -----------------------
    - ``db``  — test-setup session.  Use this to seed data; always call
      ``db.commit()`` before making HTTP requests so the writes land in
      SQLite and are visible to the request session.
    - ``override_get_db`` — creates a **separate** session per request,
      with full commit-on-success / rollback-on-exception / always-close
      lifecycle.  An endpoint calling ``db.rollback()`` only affects its
      own request session and never rolls back test-seeded data.
    """
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Separate session used only by the test body for seeding data.
    db = TestingSessionLocal()

    original_override = app.dependency_overrides.get(get_db)

    def override_get_db():
        """
        Per-request session with production-equivalent lifecycle:
        commit on clean exit, rollback on exception, always close.
        """
        request_db = TestingSessionLocal()
        try:
            yield request_db
            request_db.commit()
        except Exception:
            request_db.rollback()
            raise
        finally:
            request_db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        yield client, db
    finally:
        db.close()
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)
        engine.dispose()



# ---------------------------------------------------------------------------
# assign_ticket tests
# ---------------------------------------------------------------------------

def test_agent_can_assign_escalated_ticket(client_with_temp_db):
    """An agent with a valid token can claim an unassigned escalated ticket."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    agent = User(email="agent@test.com", hashed_password="hashed_password", role="agent")
    db.add(agent)
    db.commit()
    db.refresh(agent)

    ticket = Ticket(message="Escalated ticket", status="escalated", user_id=None)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    response = client.post(
        f"/tickets/{ticket.id}/assign",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["assigned_agent_id"] == agent.id
    assert data["id"] == ticket.id


def test_regular_user_gets_403_when_assigning_ticket(client_with_temp_db):
    """A regular user (role='user') must receive 403 when calling /assign."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    user = User(email="user@test.com", hashed_password="hashed_password", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    ticket = Ticket(message="Escalated ticket", status="escalated", user_id=None)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(user.id), "role": "user"})
    response = client.post(
        f"/tickets/{ticket.id}/assign",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    # FastAPI default HTTPException shape (now overridden): {"error": {"message": "..."}}
    assert "Access denied" in response.json()["error"]["message"]


def test_assign_non_escalated_ticket_returns_409(client_with_temp_db):
    """
    Assigning a ticket whose status is not 'escalated' returns 409.

    After removing the pre-fetch guard, the atomic UPDATE's WHERE clause
    won't match and the endpoint returns 409 (status conflict) rather than
    the former pre-check 400.
    """
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    agent = User(email="agent@test.com", hashed_password="hashed_password", role="agent")
    db.add(agent)
    db.commit()
    db.refresh(agent)

    ticket = Ticket(
        message="Auto resolved ticket",
        status="auto_resolved",
        user_id=None,
        response="Auto response",
        intent="test_intent",
        confidence=0.9,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    response = client.post(
        f"/tickets/{ticket.id}/assign",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "status" in response.json()["error"]["message"].lower() or "assign" in response.json()["error"]["message"].lower()


def test_assign_already_assigned_ticket_returns_409(client_with_temp_db):
    """Assigning a ticket already owned by another agent returns 409."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    agent1 = User(email="agent1@test.com", hashed_password="hashed_password", role="agent")
    agent2 = User(email="agent2@test.com", hashed_password="hashed_password", role="agent")
    db.add_all([agent1, agent2])
    db.commit()
    db.refresh(agent1)
    db.refresh(agent2)

    ticket = Ticket(
        message="Already assigned ticket",
        status="escalated",
        user_id=None,
        assigned_agent_id=agent1.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(agent2.id), "role": "agent"})
    response = client.post(
        f"/tickets/{ticket.id}/assign",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "already assigned" in response.json()["error"]["message"].lower()


def test_assign_idempotent_for_same_agent(client_with_temp_db):
    """Calling /assign when the ticket is already assigned to the same agent succeeds (idempotent)."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    agent = User(email="agent@test.com", hashed_password="hashed_password", role="agent")
    db.add(agent)
    db.commit()
    db.refresh(agent)

    ticket = Ticket(
        message="Already mine",
        status="escalated",
        user_id=None,
        assigned_agent_id=agent.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    response = client.post(
        f"/tickets/{ticket.id}/assign",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["assigned_agent_id"] == agent.id


# ---------------------------------------------------------------------------
# close_ticket tests
# ---------------------------------------------------------------------------

def test_agent_can_close_escalated_ticket(client_with_temp_db):
    """An agent can close an escalated ticket."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    agent = User(email="agent@test.com", hashed_password="hashed_password", role="agent")
    db.add(agent)
    db.commit()
    db.refresh(agent)

    ticket = Ticket(message="Escalated ticket to close", status="escalated", user_id=None)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    response = client.post(
        f"/tickets/{ticket.id}/close",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    assert data["id"] == ticket.id


def test_close_ticket_has_status_closed_in_response(client_with_temp_db):
    """
    After a successful close, the DB row and the HTTP response both show 'closed'.

    Uses a fresh db.refresh() to confirm the write landed in the database,
    not just in the response body.
    """
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    admin = User(email="admin@test.com", hashed_password="hashed_password", role="admin")
    db.add(admin)
    db.commit()
    db.refresh(admin)

    ticket = Ticket(message="Ticket to close", status="escalated", user_id=None)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    ticket_id = ticket.id

    token = create_access_token(data={"sub": str(admin.id), "role": "admin"})
    response = client.post(
        f"/tickets/{ticket_id}/close",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"

    # Confirm the write is visible through the test session
    db.expire(ticket)
    db.refresh(ticket)
    assert ticket.status == "closed"


def test_close_already_closed_ticket_is_idempotent(client_with_temp_db):
    """Closing an already-closed ticket returns 200 (idempotent path, no dangling transaction)."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    agent = User(email="agent@test.com", hashed_password="hashed_password", role="agent")
    db.add(agent)
    db.commit()
    db.refresh(agent)

    ticket = Ticket(message="Already closed", status="closed", user_id=None)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(agent.id), "role": "agent"})
    response = client.post(
        f"/tickets/{ticket.id}/close",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_regular_user_gets_403_when_closing_ticket(client_with_temp_db):
    """A regular user must receive 403 when calling /close."""
    from app.api.auth import create_access_token

    client, db = client_with_temp_db

    user = User(email="user@test.com", hashed_password="hashed_password", role="user")
    db.add(user)
    db.commit()
    db.refresh(user)

    ticket = Ticket(message="Escalated ticket", status="escalated", user_id=None)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    token = create_access_token(data={"sub": str(user.id), "role": "user"})
    response = client.post(
        f"/tickets/{ticket.id}/close",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Access denied" in response.json()["error"]["message"]
