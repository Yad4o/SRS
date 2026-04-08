"""
tests/test_tickets_api.py

Tests for app/api/tickets.py endpoints.

Covers:
- POST /tickets: ticket creation
- GET /tickets: list tickets (with status filtering)
- GET /tickets/{id}: get single ticket
- Error handling and validation
- Database integration
"""

import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import BaseTestClass, client, TestDataFactory, DatabaseHelper, AuthHelper
from app.schemas.ticket import TicketCreate


class TestCreateTicket(BaseTestClass):
    """Test cases for POST /tickets endpoint."""

    def test_create_ticket_success(self):
        """Test successful ticket creation."""
        ticket_data = {"message": "I can't log into my account"}
        
        response = client.post("/tickets/", json=ticket_data)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["message"] == ticket_data["message"]
        assert data["status"] in ["auto_resolved", "escalated"]  # AI pipeline processes tickets
        assert "id" in data
        assert "created_at" in data
        assert data["intent"] is not None  # AI classification
        assert data["confidence"] is not None  # AI confidence scoring

    def test_create_ticket_empty_message(self):
        """Test ticket creation with empty message."""
        ticket_data = {"message": ""}
        
        response = client.post("/tickets/", json=ticket_data)
        
        # Should succeed (empty string is valid)
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == ""

    def test_create_ticket_missing_message(self):
        """Test ticket creation without message field."""
        ticket_data = {}
        
        response = client.post("/tickets/", json=ticket_data)
        
        assert response.status_code == 400  # Validation error
        error_data = response.json()
        assert "error" in error_data
        assert error_data["error"]["code"] == "VALIDATION_ERROR"
        assert "validation_errors" in error_data["error"]["details"]

    def test_create_ticket_long_message(self):
        """Test ticket creation with very long message."""
        ticket_data = {"message": "x" * 1000}
        
        response = client.post("/tickets/", json=ticket_data)
        
        assert response.status_code == 201
        data = response.json()
        assert len(data["message"]) == 1000

    def test_create_ticket_special_characters(self):
        """Test ticket creation with special characters."""
        ticket_data = {"message": "Help! @#$%^&*()_+{}|:<>?[]\\;'\",./"}
        
        response = client.post("/tickets/", json=ticket_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == ticket_data["message"]

    def test_create_ticket_unicode_characters(self):
        """Test ticket creation with unicode characters."""
        ticket_data = {"message": "Help with émojis 🚀 and ñiño"}
        
        response = client.post("/tickets/", json=ticket_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == ticket_data["message"]

    def test_create_ticket_invalid_json(self):
        """Test ticket creation with invalid JSON."""
        response = client.post("/tickets/", data="invalid json")
        
        assert response.status_code == 400

    def test_create_ticket_database_failure_simulation(self):
        """Test ticket creation with simulated database failure."""
        ticket_data = {"message": "Test message"}
        
        # Mock the Ticket model constructor to raise an exception
        with patch('app.api.tickets.Ticket') as mock_ticket:
            mock_ticket.side_effect = Exception("Database connection failed")
            
            response = client.post("/tickets/", json=ticket_data)
            
            # Should return 500 with generic error message
            assert response.status_code == 500
            data = response.json()
            
            # Verify generic error message (no internal details exposed)
            assert "error" in data
            assert "Internal server error occurred while creating ticket" in data["error"]["message"]
            # Should not expose internal details
            assert "Database connection failed" not in data["error"]["message"]
            assert "sqlalchemy" not in data["error"]["message"].lower()
            assert "database" not in data["error"]["message"].lower()


class TestListTickets:
    """Test cases for GET /tickets endpoint."""

    def test_list_tickets_empty(self):
        """Test listing tickets when database is empty."""
        response = client.get("/tickets/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) == 0

    def test_list_tickets_with_data(self):
        """Test listing tickets when database has tickets."""
        # Create a ticket first
        create_response = client.post("/tickets/", json={"message": "Test ticket"})
        assert create_response.status_code == 201
        
        # List tickets
        response = client.get("/tickets/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) >= 1
        
        # Check ticket structure
        ticket = data["tickets"][0]
        assert "id" in ticket
        assert "message" in ticket
        assert "status" in ticket
        assert "created_at" in ticket

    def test_list_tickets_filter_by_status(self):
        """Test listing tickets filtered by status."""
        # Create tickets with different statuses
        client.post("/tickets/", json={"message": "Open ticket"})
        # Note: We can't easily create tickets with other statuses yet
        # since that requires AI processing (Phase 3)
        
        # Filter by open status
        response = client.get("/tickets/?status=open")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        
        # All returned tickets should have status "open"
        for ticket in data["tickets"]:
            assert ticket["status"] == "open"

    def test_list_tickets_filter_by_invalid_status(self):
        """Test listing tickets filtered by invalid status."""
        response = client.get("/tickets/?status=invalid_status")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tickets"]) == 0

    def test_list_tickets_multiple_tickets(self, db):
        """Test listing multiple tickets with pagination."""
        from tests.conftest import DatabaseHelper
        
        # Create multiple tickets
        for i in range(10):
            DatabaseHelper.create_ticket(db, f"Test message {i}")
        
        response = client.get("/tickets/?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tickets"]) == 5
        assert data["total"] == 10


class TestGetTicket(BaseTestClass):
    """Test cases for GET /tickets/{id} endpoint."""

    def test_get_ticket_success(self, db):
        """Test getting an existing ticket."""
        from tests.conftest import DatabaseHelper
        
        ticket = DatabaseHelper.create_ticket(db, "Test message")
        
        response = client.get(f"/tickets/{ticket.id}")
        
        assert response.status_code == 200
        data = response.json()
        self.assert_ticket_response(data, ticket.message)

    def test_get_ticket_not_found(self):
        """Test getting a non-existent ticket."""
        response = client.get("/tickets/99999")
        
        self.assert_error_response(response, 404, "not found")

    def test_get_ticket_structure(self, db):
        """Test ticket response structure."""
        from tests.conftest import DatabaseHelper
        
        ticket = DatabaseHelper.create_ticket(db, "Test message")
        
        response = client.get(f"/tickets/{ticket.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields
        required_fields = ["id", "message", "status", "created_at"]
        for field in required_fields:
            assert field in data


class TestTicketAPIIntegration(BaseTestClass):
    """Integration tests for ticket API workflows."""

    def test_complete_workflow(self, db):
        """Test complete ticket creation and retrieval workflow."""
        from tests.conftest import DatabaseHelper
        
        # Create ticket
        ticket_data = {"message": "Integration test message"}
        create_response = client.post("/tickets/", json=ticket_data)
        
        assert create_response.status_code == 201
        created_ticket = create_response.json()
        
        # Retrieve ticket
        get_response = client.get(f"/tickets/{created_ticket['id']}")
        
        assert get_response.status_code == 200
        retrieved_ticket = get_response.json()
        
        # Verify consistency
        assert created_ticket['id'] == retrieved_ticket['id']
        assert created_ticket['message'] == retrieved_ticket['message']

    def test_multiple_tickets_workflow(self, db):
        """Test workflow with multiple tickets."""
        from tests.conftest import DatabaseHelper
        
        # Create multiple tickets
        messages = ["Message 1", "Message 2", "Message 3"]
        created_ids = []
        
        for message in messages:
            response = client.post("/tickets/", json={"message": message})
            assert response.status_code == 201
            created_ids.append(response.json()['id'])
        
        # List all tickets
        response = client.get("/tickets/")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["tickets"]) >= 3
        
        # Verify our tickets are in the list
        ticket_ids = [ticket['id'] for ticket in data['tickets']]
        for created_id in created_ids:
            assert created_id in ticket_ids

    def test_status_filtering_workflow(self, db):
        """Test status filtering workflow."""
        from tests.conftest import DatabaseHelper
        
        # Create tickets
        ticket1 = DatabaseHelper.create_ticket(db, "Open ticket")
        ticket2 = DatabaseHelper.create_ticket(db, "Another ticket")
        
        # Filter by open status
        response = client.get("/tickets/?status=open")
        assert response.status_code == 200
        
        data = response.json()
        assert all(ticket['status'] == 'open' for ticket in data['tickets'])


class TestTicketAccessControl(BaseTestClass):
    """Test cases for ticket access control and permissions."""

    def test_authenticated_create_sets_user_id(self, agent_token):
        """Test that authenticated ticket creation sets user_id."""
        from app.main import app
        from app.api.auth import decode_token
        
        # Mock the authentication to set a specific user ID
        with patch("app.api.tickets.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "123", "role": "user"}
            
            response = client.post(
                "/tickets/", 
                json={"message": "Owned ticket"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["user_id"] == 123

    def test_list_tickets_user_isolation(self, db):
        """Test that users can only see their own tickets."""
        from tests.conftest import DatabaseHelper, AuthHelper
        
        # Create users in database
        user1 = DatabaseHelper.create_user(db, email="u1@ex.com", role="user")
        user2 = DatabaseHelper.create_user(db, email="u2@ex.com", role="user")
        
        # Create tickets for each user
        ticket1 = DatabaseHelper.create_ticket(db, "User 1 Ticket", user1.id)
        ticket2 = DatabaseHelper.create_ticket(db, "User 2 Ticket", user2.id)
        
        # Mock authentication for user 1
        with patch("app.api.tickets.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": str(user1.id), "role": "user"}
            
            response = client.get("/tickets/", headers={"Authorization": AuthHelper.create_user_token(str(user1.id))})
            data = response.json()
            
            # User 1 should only see their own ticket
            assert len(data["tickets"]) == 1
            assert data["tickets"][0]["message"] == "User 1 Ticket"

    def test_agent_assign_escalated_ticket(self, agent_token):
        """Test that agents can assign escalated tickets."""
        from tests.conftest import DatabaseHelper
        
        # Create an escalated ticket
        with patch("app.api.tickets.classify_intent", return_value={"intent": "login_issue", "confidence": 0.1}):
            with patch("app.api.tickets.decide_resolution", return_value="escalate"):
                resp = client.post("/tickets/", json={"message": "Fix me"})
                assert resp.json()["status"] == "escalated"
                ticket_id = resp.json()["id"]

        response = client.post(f"/tickets/{ticket_id}/assign", headers={"Authorization": agent_token})
        assert response.status_code == 200
        assert response.json()["assigned_agent_id"] is not None

    def test_user_cannot_assign_ticket(self, user_token):
        """Test that regular users cannot assign tickets."""
        from tests.conftest import DatabaseHelper
        
        # Create an escalated ticket
        with patch("app.api.tickets.classify_intent", return_value={"intent": "login_issue", "confidence": 0.1}):
            with patch("app.api.tickets.decide_resolution", return_value="escalate"):
                resp = client.post("/tickets/", json={"message": "Fix me"})
                assert resp.json()["status"] == "escalated"
                ticket_id = resp.json()["id"]

        response = client.post(f"/tickets/{ticket_id}/assign", headers={"Authorization": user_token})
        assert response.status_code == 403

    def test_agent_close_escalated_ticket(self, agent_token):
        """Test that agents can close escalated tickets."""
        from tests.conftest import DatabaseHelper
        
        # Create an escalated ticket
        with patch("app.api.tickets.classify_intent", return_value={"intent": "login_issue", "confidence": 0.1}):
            with patch("app.api.tickets.decide_resolution", return_value="escalate"):
                resp = client.post("/tickets/", json={"message": "Close me"})
                assert resp.json()["status"] == "escalated"
                ticket_id = resp.json()["id"]

        response = client.post(f"/tickets/{ticket_id}/close", headers={"Authorization": agent_token})
        assert response.status_code == 200
        assert response.json()["status"] == "closed"


class TestRateLimiting(BaseTestClass):
    """Test cases for rate limiting on ticket creation."""

    def test_create_ticket_rate_limit(self, reset_limiter):
        """Send 61 sequential POSTs to POST /tickets/ -> 61st returns HTTP 429."""
        with patch("app.api.tickets.classify_intent", return_value={"intent": "test", "confidence": 0.9}):
            for i in range(60):
                resp = client.post("/tickets/", json={"message": f"rate limit test {i}"})
                assert resp.status_code == 201

            resp = client.post("/tickets/", json={"message": "one too many"})
            assert resp.status_code == 429
