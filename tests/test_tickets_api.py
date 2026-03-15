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
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.main import app
from app.db.session import get_db, engine, init_db
from app.models.ticket import Ticket
from app.schemas.ticket import TicketCreate


# Test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Initialize database for all tests."""
    init_db()
    
    # Clean up any existing data before each test
    with engine.connect() as conn:
        conn.execute(Ticket.__table__.delete())
        conn.commit()


class TestCreateTicket:
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
        
        # Should return empty list for invalid status
        assert "tickets" in data
        assert isinstance(data["tickets"], list)
        assert len(data["tickets"]) == 0

    def test_list_tickets_multiple_tickets(self):
        """Test listing multiple tickets."""
        # Create multiple tickets
        messages = ["First ticket", "Second ticket", "Third ticket"]
        created_ids = []
        
        for message in messages:
            response = client.post("/tickets/", json={"message": message})
            if response.status_code == 201:
                created_ids.append(response.json()["id"])
        
        # List tickets
        response = client.get("/tickets/")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have our tickets (plus any existing ones)
        assert len(data["tickets"]) >= len(messages)
        
        # Check ordering (newest first)
        if len(data["tickets"]) >= 2:
            first_created = data["tickets"][0]["created_at"]
            second_created = data["tickets"][1]["created_at"]
            # First should be newer than second
            assert first_created >= second_created


class TestGetTicket:
    """Test cases for GET /tickets/{id} endpoint."""

    def test_get_ticket_success(self):
        """Test getting an existing ticket."""
        # Create a ticket first
        create_response = client.post("/tickets/", json={"message": "Test ticket"})
        assert create_response.status_code == 201
        
        ticket_id = create_response.json()["id"]
        
        # Get the ticket
        response = client.get(f"/tickets/{ticket_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == ticket_id
        assert data["message"] == "Test ticket"
        assert data["status"] in ["auto_resolved", "escalated"]  # AI processed
        assert "created_at" in data

    def test_get_ticket_not_found(self):
        """Test getting a non-existent ticket."""
        response = client.get("/tickets/99999")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
        assert "not found" in data["error"]["message"].lower()

    def test_get_ticket_invalid_id(self):
        """Test getting a ticket with invalid ID."""
        response = client.get("/tickets/invalid_id")
        
        assert response.status_code == 400  # Validation error

    def test_get_ticket_zero_id(self):
        """Test getting a ticket with ID 0."""
        response = client.get("/tickets/0")
        
        assert response.status_code == 404

    def test_get_ticket_negative_id(self):
        """Test getting a ticket with negative ID."""
        response = client.get("/tickets/-1")
        
        assert response.status_code == 404

    def test_get_ticket_structure(self):
        """Test the structure of ticket response."""
        # Create a ticket
        create_response = client.post("/tickets/", json={"message": "Structure test"})
        assert create_response.status_code == 201
        
        ticket_id = create_response.json()["id"]
        
        # Get the ticket
        response = client.get(f"/tickets/{ticket_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        required_fields = ["id", "message", "intent", "confidence", "status", "created_at"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Check field types
        assert isinstance(data["id"], int)
        assert isinstance(data["message"], str)
        assert data["intent"] is None or isinstance(data["intent"], str)
        assert data["confidence"] is None or isinstance(data["confidence"], (int, float))
        assert isinstance(data["status"], str)
        assert isinstance(data["created_at"], str)


class TestTicketAPIIntegration:
    """Integration tests for the complete ticket workflow."""

    def test_complete_workflow(self):
        """Test complete ticket creation and retrieval workflow."""
        # 1. Create a ticket
        create_data = {"message": "Integration test ticket"}
        create_response = client.post("/tickets/", json=create_data)
        
        assert create_response.status_code == 201
        created_ticket = create_response.json()
        ticket_id = created_ticket["id"]
        
        # Verify created ticket structure
        assert created_ticket["message"] == create_data["message"]
        assert created_ticket["status"] in ["auto_resolved", "escalated"]  # AI processed
        
        # 2. List all tickets and verify our ticket is there
        list_response = client.get("/tickets/")
        
        assert list_response.status_code == 200
        ticket_list = list_response.json()
        
        # Find our ticket in the list
        our_ticket = None
        for ticket in ticket_list["tickets"]:
            if ticket["id"] == ticket_id:
                our_ticket = ticket
                break
        
        assert our_ticket is not None
        assert our_ticket["message"] == create_data["message"]
        
        # 3. Get the specific ticket
        get_response = client.get(f"/tickets/{ticket_id}")
        
        assert get_response.status_code == 200
        retrieved_ticket = get_response.json()
        
        # Verify it matches the original
        assert retrieved_ticket["id"] == ticket_id
        assert retrieved_ticket["message"] == create_data["message"]
        assert retrieved_ticket["status"] in ["auto_resolved", "escalated"]  # AI processed

    def test_multiple_tickets_workflow(self):
        """Test workflow with multiple tickets."""
        # Create multiple tickets
        messages = ["First issue", "Second issue", "Third issue"]
        created_tickets = []
        
        for message in messages:
            response = client.post("/tickets/", json={"message": message})
            if response.status_code == 201:
                created_tickets.append(response.json())
        
        # List all tickets
        list_response = client.get("/tickets/")
        assert list_response.status_code == 200
        
        ticket_list = list_response.json()
        assert len(ticket_list["tickets"]) >= len(messages)
        
        # Verify each created ticket is in the list
        created_ids = [ticket["id"] for ticket in created_tickets]
        listed_ids = [ticket["id"] for ticket in ticket_list["tickets"]]
        
        for created_id in created_ids:
            assert created_id in listed_ids
        
        # Get each ticket individually
        for ticket in created_tickets:
            get_response = client.get(f"/tickets/{ticket['id']}")
            assert get_response.status_code == 200
            
            retrieved_ticket = get_response.json()
            assert retrieved_ticket["id"] == ticket["id"]
            assert retrieved_ticket["message"] == ticket["message"]

    def test_status_filtering_workflow(self):
        """Test status filtering workflow with AI processing."""
        # Create several tickets and validate each creation
        created_tickets = []
        for i in range(3):
            response = client.post("/tickets/", json={"message": f"Ticket {i+1}"})
            assert response.status_code == 201, f"Failed to create ticket {i+1}"
            created_tickets.append(response.json())
        
        # Get all tickets
        all_response = client.get("/tickets/")
        assert all_response.status_code == 200
        all_tickets = all_response.json()["tickets"]
        
        # Get only escalated tickets (since AI processes all tickets)
        escalated_response = client.get("/tickets/?status=escalated")
        assert escalated_response.status_code == 200
        escalated_tickets = escalated_response.json()["tickets"]
        
        # Get only auto_resolved tickets
        auto_resolved_response = client.get("/tickets/?status=auto_resolved")
        assert auto_resolved_response.status_code == 200
        auto_resolved_tickets = auto_resolved_response.json()["tickets"]
        
        # Verify all tickets are either escalated or auto_resolved
        total_processed = len(escalated_tickets) + len(auto_resolved_tickets)
        assert total_processed == len(all_tickets)
        
        # Verify ticket statuses are valid
        for ticket in escalated_tickets:
            assert ticket["status"] == "escalated"
        for ticket in auto_resolved_tickets:
            assert ticket["status"] == "auto_resolved"
        
        # Verify we created the expected number of tickets
        assert len(created_tickets) == 3
        for ticket in created_tickets:
            assert ticket["status"] in ["auto_resolved", "escalated"]
            assert ticket["message"].startswith("Ticket")


class TestTicketsHealth:
    """Test cases for GET /tickets/health endpoint."""

    def test_tickets_health_check(self):
        """Test tickets API health check endpoint."""
        response = client.get("/tickets/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "tickets-api"
        assert "version" in data
        assert "endpoints" in data
        assert isinstance(data["endpoints"], list)
        assert len(data["endpoints"]) == 3
