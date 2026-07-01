"""
tests/api/test_new_endpoints.py

Tests for the four endpoints added in fix/missing-endpoints-and-schema:

  Backend fixes:
    1. GET  /admin/agents              — list agent users for assignment modal
    2. POST /admin/tickets/{id}/assign — admin assigns a specific agent
    3. GET  /tickets/my-assignments    — agent views their assigned tickets
    4. POST /tickets/{id}/accept       — agent accepts → in_progress transition

  Schema fix:
    5. GET  /admin/tickets             — AdminTicketItem now includes
                                         assigned_agent_id and other fields
"""

import pytest
from tests.conftest import BaseTestClass, client, DatabaseHelper, AuthHelper
from app.db.session import SessionLocal
from app.models.ticket import Ticket
from app.models.user import User
from app.constants import TicketStatus, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(email: str, role: str) -> User:
    db = SessionLocal()
    try:
        user = User(email=email, hashed_password="hash", role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _make_ticket(
    status: str = TicketStatus.ESCALATED.value,
    assigned_agent_id: int | None = None,
    user_id: int | None = None,
    message: str = "Test ticket",
) -> Ticket:
    db = SessionLocal()
    try:
        ticket = Ticket(
            message=message,
            status=status,
            assigned_agent_id=assigned_agent_id,
            user_id=user_id,
            intent="login_issue",
            confidence=0.9,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. AdminTicketItem schema fix — assigned_agent_id is now serialized
# ---------------------------------------------------------------------------

class TestAdminTicketItemSchemaFix(BaseTestClass):
    """
    GET /admin/tickets now includes assigned_agent_id in every row.
    Previously this field was absent, causing the Escalations page filter
    to always return empty.
    """

    def test_admin_tickets_includes_assigned_agent_id_when_null(self):
        admin = _make_user("admin_schema@test.com", "admin")
        _make_ticket(status="escalated", assigned_agent_id=None)

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.get("/admin/tickets?status=escalated", headers={"Authorization": token})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tickets"]) >= 1
        ticket = data["tickets"][0]
        # Field must be present (null is fine — absence was the bug)
        assert "assigned_agent_id" in ticket
        assert ticket["assigned_agent_id"] is None

    def test_admin_tickets_includes_assigned_agent_id_when_set(self):
        admin = _make_user("admin_schema2@test.com", "admin")
        agent = _make_user("agent_schema@test.com", "agent")
        _make_ticket(status="escalated", assigned_agent_id=agent.id)

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.get("/admin/tickets?status=escalated", headers={"Authorization": token})

        assert resp.status_code == 200
        data = resp.json()
        ticket = data["tickets"][0]
        assert ticket["assigned_agent_id"] == agent.id

    def test_admin_tickets_includes_new_fields(self):
        """Verify all previously missing fields are now present."""
        admin = _make_user("admin_fields@test.com", "admin")
        _make_ticket(status="open")

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.get("/admin/tickets", headers={"Authorization": token})

        assert resp.status_code == 200
        ticket = resp.json()["tickets"][0]

        for field in [
            "id", "message", "status", "intent", "sub_intent",
            "confidence", "sentiment", "sentiment_confidence",
            "response", "response_source", "quality_score",
            "user_id", "assigned_agent_id", "created_at",
        ]:
            assert field in ticket, f"Field '{field}' missing from AdminTicketItem"


# ---------------------------------------------------------------------------
# 1. GET /admin/agents
# ---------------------------------------------------------------------------

class TestAdminListAgents(BaseTestClass):
    """GET /admin/agents returns all users with role='agent'."""

    def test_returns_agents_only(self):
        admin = _make_user("admin_agents@test.com", "admin")
        agent1 = _make_user("agent1@test.com", "agent")
        agent2 = _make_user("agent2@test.com", "agent")
        _make_user("user_agents@test.com", "user")  # should be excluded

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.get("/admin/agents", headers={"Authorization": token})

        assert resp.status_code == 200
        data = resp.json()
        emails = {a["email"] for a in data}
        assert agent1.email in emails
        assert agent2.email in emails
        assert "user_agents@test.com" not in emails

    def test_agent_item_shape(self):
        admin = _make_user("admin_shape@test.com", "admin")
        _make_user("agent_shape@test.com", "agent")

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.get("/admin/agents", headers={"Authorization": token})

        assert resp.status_code == 200
        agent_item = resp.json()[0]
        assert "id" in agent_item
        assert "email" in agent_item
        assert "role" in agent_item
        assert agent_item["role"] == "agent"

    def test_requires_admin_role(self):
        agent = _make_user("agent_noauth@test.com", "agent")
        token = AuthHelper.create_agent_token(str(agent.id))

        resp = client.get("/admin/agents", headers={"Authorization": token})
        assert resp.status_code == 403

    def test_requires_authentication(self):
        resp = client.get("/admin/agents")
        assert resp.status_code == 401

    def test_empty_when_no_agents(self):
        admin = _make_user("admin_empty@test.com", "admin")
        token = AuthHelper.create_admin_token(str(admin.id))

        resp = client.get("/admin/agents", headers={"Authorization": token})
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# 2. POST /admin/tickets/{id}/assign
# ---------------------------------------------------------------------------

class TestAdminAssignTicket(BaseTestClass):
    """POST /admin/tickets/{id}/assign — admin assigns any agent to a ticket."""

    def test_successful_assignment(self):
        admin = _make_user("admin_assign@test.com", "admin")
        agent = _make_user("agent_assign@test.com", "agent")
        ticket = _make_ticket(status="escalated", assigned_agent_id=None)

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.post(
            f"/admin/tickets/{ticket.id}/assign",
            json={"agent_id": agent.id},
            headers={"Authorization": token},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_agent_id"] == agent.id
        assert data["status"] == "escalated"  # status unchanged by assignment

    def test_rejects_non_agent_user(self):
        admin = _make_user("admin_assign2@test.com", "admin")
        regular_user = _make_user("user_assign@test.com", "user")
        ticket = _make_ticket(status="escalated")

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.post(
            f"/admin/tickets/{ticket.id}/assign",
            json={"agent_id": regular_user.id},
            headers={"Authorization": token},
        )
        assert resp.status_code == 400

    def test_rejects_already_assigned_ticket(self):
        admin = _make_user("admin_assign3@test.com", "admin")
        agent1 = _make_user("agent_already@test.com", "agent")
        agent2 = _make_user("agent_second@test.com", "agent")
        ticket = _make_ticket(status="escalated", assigned_agent_id=agent1.id)

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.post(
            f"/admin/tickets/{ticket.id}/assign",
            json={"agent_id": agent2.id},
            headers={"Authorization": token},
        )
        assert resp.status_code == 409

    def test_rejects_non_escalated_ticket(self):
        admin = _make_user("admin_assign4@test.com", "admin")
        agent = _make_user("agent_closed@test.com", "agent")
        ticket = _make_ticket(status="closed")

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.post(
            f"/admin/tickets/{ticket.id}/assign",
            json={"agent_id": agent.id},
            headers={"Authorization": token},
        )
        assert resp.status_code == 409

    def test_rejects_nonexistent_ticket(self):
        admin = _make_user("admin_assign5@test.com", "admin")
        agent = _make_user("agent_ghost@test.com", "agent")

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.post(
            "/admin/tickets/999999/assign",
            json={"agent_id": agent.id},
            headers={"Authorization": token},
        )
        assert resp.status_code == 404

    def test_requires_admin(self):
        agent = _make_user("agent_nonadmin@test.com", "agent")
        ticket = _make_ticket(status="escalated")
        token = AuthHelper.create_agent_token(str(agent.id))

        resp = client.post(
            f"/admin/tickets/{ticket.id}/assign",
            json={"agent_id": agent.id},
            headers={"Authorization": token},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. GET /tickets/my-assignments
# ---------------------------------------------------------------------------

class TestMyAssignments(BaseTestClass):
    """GET /tickets/my-assignments — agent sees only their own assigned tickets."""

    def test_returns_assigned_tickets(self):
        agent = _make_user("agent_myq@test.com", "agent")
        t1 = _make_ticket(status="escalated", assigned_agent_id=agent.id)
        t2 = _make_ticket(status="escalated", assigned_agent_id=agent.id)
        _make_ticket(status="escalated", assigned_agent_id=None)  # unassigned, should be excluded

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.get("/tickets/my-assignments", headers={"Authorization": token})

        assert resp.status_code == 200
        data = resp.json()
        ids = {t["id"] for t in data["tickets"]}
        assert t1.id in ids
        assert t2.id in ids

    def test_does_not_return_other_agents_tickets(self):
        agent1 = _make_user("agent_own1@test.com", "agent")
        agent2 = _make_user("agent_own2@test.com", "agent")
        t_agent1 = _make_ticket(status="escalated", assigned_agent_id=agent1.id)
        t_agent2 = _make_ticket(status="escalated", assigned_agent_id=agent2.id)

        token = AuthHelper.create_agent_token(str(agent1.id))
        resp = client.get("/tickets/my-assignments", headers={"Authorization": token})

        ids = {t["id"] for t in resp.json()["tickets"]}
        assert t_agent1.id in ids
        assert t_agent2.id not in ids

    def test_status_filter_escalated(self):
        agent = _make_user("agent_filter@test.com", "agent")
        t_esc = _make_ticket(status="escalated", assigned_agent_id=agent.id)
        t_ip = _make_ticket(status="in_progress", assigned_agent_id=agent.id)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.get(
            "/tickets/my-assignments?status=escalated",
            headers={"Authorization": token},
        )
        ids = {t["id"] for t in resp.json()["tickets"]}
        assert t_esc.id in ids
        assert t_ip.id not in ids

    def test_status_filter_in_progress(self):
        agent = _make_user("agent_ip@test.com", "agent")
        _make_ticket(status="escalated", assigned_agent_id=agent.id)
        t_ip = _make_ticket(status="in_progress", assigned_agent_id=agent.id)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.get(
            "/tickets/my-assignments?status=in_progress",
            headers={"Authorization": token},
        )
        ids = {t["id"] for t in resp.json()["tickets"]}
        assert t_ip.id in ids

    def test_rejects_invalid_status(self):
        agent = _make_user("agent_badstatus@test.com", "agent")
        token = AuthHelper.create_agent_token(str(agent.id))

        resp = client.get(
            "/tickets/my-assignments?status=open",
            headers={"Authorization": token},
        )
        assert resp.status_code == 400

    def test_requires_authentication(self):
        resp = client.get("/tickets/my-assignments")
        assert resp.status_code == 401

    def test_user_role_cannot_access(self):
        user = _make_user("user_myq@test.com", "user")
        token = AuthHelper.create_user_token(str(user.id))

        resp = client.get("/tickets/my-assignments", headers={"Authorization": token})
        assert resp.status_code == 403

    def test_empty_when_no_assignments(self):
        agent = _make_user("agent_empty@test.com", "agent")
        token = AuthHelper.create_agent_token(str(agent.id))

        resp = client.get("/tickets/my-assignments", headers={"Authorization": token})
        assert resp.status_code == 200
        assert resp.json()["tickets"] == []


# ---------------------------------------------------------------------------
# 4. POST /tickets/{id}/accept
# ---------------------------------------------------------------------------

class TestAcceptTicket(BaseTestClass):
    """POST /tickets/{id}/accept — assigned agent accepts → in_progress."""

    def test_successful_accept(self):
        agent = _make_user("agent_accept@test.com", "agent")
        ticket = _make_ticket(status="escalated", assigned_agent_id=agent.id)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["assigned_agent_id"] == agent.id

    def test_idempotent_accept(self):
        """Accepting an already-accepted ticket returns 200 without error."""
        agent = _make_user("agent_idem@test.com", "agent")
        ticket = _make_ticket(status="in_progress", assigned_agent_id=agent.id)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_only_assigned_agent_can_accept(self):
        agent1 = _make_user("agent_acc1@test.com", "agent")
        agent2 = _make_user("agent_acc2@test.com", "agent")
        ticket = _make_ticket(status="escalated", assigned_agent_id=agent1.id)

        token = AuthHelper.create_agent_token(str(agent2.id))
        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 403

    def test_cannot_accept_unassigned_ticket(self):
        agent = _make_user("agent_unassigned@test.com", "agent")
        ticket = _make_ticket(status="escalated", assigned_agent_id=None)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 403

    def test_cannot_accept_closed_ticket(self):
        agent = _make_user("agent_closed2@test.com", "agent")
        ticket = _make_ticket(status="closed", assigned_agent_id=agent.id)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 409

    def test_nonexistent_ticket_returns_404(self):
        agent = _make_user("agent_ghost2@test.com", "agent")
        token = AuthHelper.create_agent_token(str(agent.id))

        resp = client.post(
            "/tickets/999999/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 404

    def test_requires_agent_or_admin_role(self):
        user = _make_user("user_accept@test.com", "user")
        ticket = _make_ticket(status="escalated")
        token = AuthHelper.create_user_token(str(user.id))

        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 403

    def test_admin_can_accept_their_own_assigned_ticket(self):
        admin = _make_user("admin_accept@test.com", "admin")
        ticket = _make_ticket(status="escalated", assigned_agent_id=admin.id)

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.post(
            f"/tickets/{ticket.id}/accept",
            headers={"Authorization": token},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"


# ---------------------------------------------------------------------------
# IN_PROGRESS status: general ticket visibility
# ---------------------------------------------------------------------------

class TestInProgressStatus(BaseTestClass):
    """in_progress is a valid, routable status throughout the system."""

    def test_admin_tickets_can_filter_by_in_progress(self):
        admin = _make_user("admin_ip@test.com", "admin")
        agent = _make_user("agent_ipvis@test.com", "agent")
        t_ip = _make_ticket(status="in_progress", assigned_agent_id=agent.id)
        _make_ticket(status="escalated")

        token = AuthHelper.create_admin_token(str(admin.id))
        resp = client.get(
            "/admin/tickets?status=in_progress",
            headers={"Authorization": token},
        )

        assert resp.status_code == 200
        ids = {t["id"] for t in resp.json()["tickets"]}
        assert t_ip.id in ids

    def test_in_progress_ticket_visible_to_assigned_agent_via_my_assignments(self):
        agent = _make_user("agent_ipown@test.com", "agent")
        t = _make_ticket(status="in_progress", assigned_agent_id=agent.id)

        token = AuthHelper.create_agent_token(str(agent.id))
        resp = client.get("/tickets/my-assignments", headers={"Authorization": token})

        ids = {t_["id"] for t_ in resp.json()["tickets"]}
        assert t.id in ids
