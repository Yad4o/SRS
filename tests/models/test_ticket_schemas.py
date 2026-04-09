"""
tests/test_ticket_schemas.py

Tests for ticket Pydantic schemas.

Owner:
------
Prajwal (Backend / API Testing)

Responsibilities:
-----------------
- Test schema validation
- Test schema serialization
- Test edge cases and error conditions
- Test ORM model compatibility
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.ticket import TicketCreate, TicketResponse, TicketRead, TicketList


class TestTicketCreate:
    """Test cases for TicketCreate schema."""

    def test_ticket_create_valid_message(self):
        """Test TicketCreate with valid message."""
        ticket_data = {"message": "I can't log into my account"}
        ticket = TicketCreate(**ticket_data)
        
        assert ticket.message == "I can't log into my account"

    def test_ticket_create_empty_message(self):
        """Test TicketCreate accepts empty message (Pydantic v2 behavior)."""
        # In Pydantic v2, empty strings are valid unless constrained
        ticket = TicketCreate(message="")
        assert ticket.message == ""

    def test_ticket_create_missing_message(self):
        """Test TicketCreate requires message field."""
        with pytest.raises(ValidationError) as exc_info:
            TicketCreate()
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("message",)
        assert "Field required" in errors[0]["msg"]

    def test_ticket_create_whitespace_only_message(self):
        """Test TicketCreate accepts whitespace-only message."""
        ticket = TicketCreate(message="   ")
        assert ticket.message == "   "

    def test_ticket_create_long_message(self):
        """Test TicketCreate handles long messages."""
        long_message = "x" * 1000
        ticket = TicketCreate(message=long_message)
        assert ticket.message == long_message

    def test_ticket_create_special_characters(self):
        """Test TicketCreate handles special characters."""
        special_message = "Help! @#$%^&*()_+{}|:<>?[]\\;'\",./"
        ticket = TicketCreate(message=special_message)
        assert ticket.message == special_message

    def test_ticket_create_unicode_characters(self):
        """Test TicketCreate handles unicode characters."""
        unicode_message = "Help with émojis 🚀 and ñiño"
        ticket = TicketCreate(message=unicode_message)
        assert ticket.message == unicode_message


class TestTicketResponse:
    """Test cases for TicketResponse schema."""

    def test_ticket_response_all_fields(self):
        """Test TicketResponse with all fields populated."""
        created_at = datetime.now()
        ticket_data = {
            "id": 1,
            "message": "I can't log into my account",
            "intent": "login_issue",
            "confidence": 0.95,
            "status": "open",
            "created_at": created_at
        }
        
        ticket = TicketResponse(**ticket_data)
        
        assert ticket.id == 1
        assert ticket.message == "I can't log into my account"
        assert ticket.intent == "login_issue"
        assert ticket.confidence == 0.95
        assert ticket.status == "open"
        assert ticket.created_at == created_at

    def test_ticket_response_optional_fields_none(self):
        """Test TicketResponse with optional fields as None."""
        created_at = datetime.now()
        ticket_data = {
            "id": 2,
            "message": "General inquiry",
            "intent": None,
            "confidence": None,
            "status": "open",
            "created_at": created_at
        }
        
        ticket = TicketResponse(**ticket_data)
        
        assert ticket.id == 2
        assert ticket.message == "General inquiry"
        assert ticket.intent is None
        assert ticket.confidence is None
        assert ticket.status == "open"
        assert ticket.created_at == created_at

    def test_ticket_response_missing_optional_fields(self):
        """Test TicketResponse requires optional fields to be explicitly provided."""
        created_at = datetime.now()
        ticket_data = {
            "id": 3,
            "message": "Payment issue",
            "status": "escalated",
            "created_at": created_at,
            "intent": None,  # Must be explicitly provided
            "confidence": None  # Must be explicitly provided
        }
        
        ticket = TicketResponse(**ticket_data)
        
        assert ticket.id == 3
        assert ticket.message == "Payment issue"
        assert ticket.intent is None
        assert ticket.confidence is None
        assert ticket.status == "escalated"
        assert ticket.created_at == created_at

    def test_ticket_response_invalid_id(self):
        """Test TicketResponse rejects invalid ID."""
        with pytest.raises(ValidationError) as exc_info:
            TicketResponse(
                id="invalid",
                message="Test message",
                status="open",
                created_at=datetime.now(),
                intent=None,
                confidence=None
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)
        assert any("Input should be a valid integer" in error["msg"] for error in errors)

    def test_ticket_response_invalid_confidence(self):
        """Test TicketResponse rejects invalid confidence."""
        with pytest.raises(ValidationError) as exc_info:
            TicketResponse(
                id=1,
                message="Test message",
                confidence="invalid",
                status="open",
                created_at=datetime.now(),
                intent=None
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("confidence",) for error in errors)
        assert any("Input should be a valid number" in error["msg"] for error in errors)

    def test_ticket_response_invalid_created_at(self):
        """Test TicketResponse rejects invalid created_at."""
        with pytest.raises(ValidationError) as exc_info:
            TicketResponse(
                id=1,
                message="Test message",
                status="open",
                created_at="invalid",
                intent=None,
                confidence=None
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("created_at",) for error in errors)
        assert any("Input should be a valid datetime" in error["msg"] for error in errors)

    def test_ticket_response_confidence_out_of_range(self):
        """Test TicketResponse accepts confidence values outside 0-1 range."""
        # Pydantic doesn't enforce range by default, so this should work
        ticket = TicketResponse(
            id=1,
            message="Test message",
            confidence=1.5,
            status="open",
            created_at=datetime.now(),
            intent=None
        )
        assert ticket.confidence == 1.5

    def test_ticket_response_negative_confidence(self):
        """Test TicketResponse accepts negative confidence."""
        ticket = TicketResponse(
            id=1,
            message="Test message",
            confidence=-0.5,
            status="open",
            created_at=datetime.now(),
            intent=None
        )
        assert ticket.confidence == -0.5


class TestTicketRead:
    """Test cases for TicketRead alias."""

    def test_ticket_read_is_alias(self):
        """Test that TicketRead is the same as TicketResponse."""
        assert TicketRead is TicketResponse
        assert TicketRead.__name__ == "TicketResponse"

    def test_ticket_read_functionality(self):
        """Test TicketRead works the same as TicketResponse."""
        created_at = datetime.now()
        ticket_data = {
            "id": 1,
            "message": "Test message",
            "status": "open",
            "created_at": created_at,
            "intent": None,
            "confidence": None
        }
        
        ticket = TicketRead(**ticket_data)
        assert ticket.id == 1
        assert ticket.message == "Test message"
        assert ticket.status == "open"
        assert ticket.created_at == created_at


class TestTicketList:
    """Test cases for TicketList schema."""

    def test_ticket_list_empty(self):
        """Test TicketList with empty list."""
        ticket_list = TicketList(tickets=[])
        assert ticket_list.tickets == []
        assert len(ticket_list.tickets) == 0

    def test_ticket_list_single_ticket(self):
        """Test TicketList with single ticket."""
        created_at = datetime.now()
        ticket_data = {
            "id": 1,
            "message": "Test message",
            "status": "open",
            "created_at": created_at,
            "intent": None,
            "confidence": None
        }
        
        ticket = TicketResponse(**ticket_data)
        ticket_list = TicketList(tickets=[ticket])
        
        assert len(ticket_list.tickets) == 1
        assert ticket_list.tickets[0].id == 1
        assert ticket_list.tickets[0].message == "Test message"

    def test_ticket_list_multiple_tickets(self):
        """Test TicketList with multiple tickets."""
        created_at = datetime.now()
        ticket_data_list = [
            {
                "id": 1,
                "message": "Login issue",
                "status": "open",
                "created_at": created_at,
                "intent": "login_issue",
                "confidence": 0.92
            },
            {
                "id": 2,
                "message": "Payment problem",
                "status": "escalated",
                "created_at": created_at,
                "intent": "payment",
                "confidence": 0.88
            },
            {
                "id": 3,
                "message": "General question",
                "status": "closed",
                "created_at": created_at,
                "intent": None,
                "confidence": None
            }
        ]
        
        tickets = [TicketResponse(**data) for data in ticket_data_list]
        ticket_list = TicketList(tickets=tickets)
        
        assert len(ticket_list.tickets) == 3
        assert ticket_list.tickets[0].status == "open"
        assert ticket_list.tickets[1].status == "escalated"
        assert ticket_list.tickets[2].status == "closed"

    def test_ticket_list_invalid_type(self):
        """Test TicketList rejects invalid ticket type."""
        with pytest.raises(ValidationError) as exc_info:
            TicketList(tickets=["invalid", "tickets"])
        
        errors = exc_info.value.errors()
        assert len(errors) == 2  # One for each invalid item
        assert errors[0]["loc"] == ("tickets", 0)
        assert errors[1]["loc"] == ("tickets", 1)

    def test_ticket_list_missing_field(self):
        """Test TicketList rejects tickets with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            TicketList(tickets=[{
                "message": "Missing required fields"
            }])
        
        errors = exc_info.value.errors()
        assert len(errors) >= 1
        assert any(error["loc"] == ("tickets", 0, "id") for error in errors)

    def test_ticket_list_with_various_statuses(self):
        """Test TicketList with tickets in different statuses."""
        created_at = datetime.now()
        statuses = ["open", "auto_resolved", "escalated", "closed"]
        
        tickets = []
        for i, status in enumerate(statuses, 1):
            ticket = TicketResponse(
                id=i,
                message=f"Ticket {i}",
                status=status,
                created_at=created_at,
                intent=None,
                confidence=None
            )
            tickets.append(ticket)
        
        ticket_list = TicketList(tickets=tickets)
        
        assert len(ticket_list.tickets) == 4
        for i, expected_status in enumerate(statuses):
            assert ticket_list.tickets[i].status == expected_status

    def test_ticket_list_large_number(self):
        """Test TicketList handles large number of tickets."""
        created_at = datetime.now()
        
        # Create 100 tickets
        tickets = []
        for i in range(1, 101):
            ticket = TicketResponse(
                id=i,
                message=f"Ticket {i}",
                status="open",
                created_at=created_at,
                intent=None,
                confidence=None
            )
            tickets.append(ticket)
        
        ticket_list = TicketList(tickets=tickets)
        
        assert len(ticket_list.tickets) == 100
        assert ticket_list.tickets[0].id == 1
        assert ticket_list.tickets[-1].id == 100


class TestSchemaIntegration:
    """Integration tests for schema combinations."""

    def test_create_to_response_workflow(self):
        """Test typical workflow: create ticket -> return response."""
        # Step 1: Create ticket from user input
        create_data = {"message": "I need help with my account"}
        ticket_create = TicketCreate(**create_data)
        
        # Step 2: Simulate database response (would come from ORM)
        created_at = datetime.now()
        response_data = {
            "id": 1,
            "message": ticket_create.message,
            "intent": "account_issue",
            "confidence": 0.87,
            "status": "open",
            "created_at": created_at
        }
        
        ticket_response = TicketResponse(**response_data)
        
        # Verify workflow
        assert ticket_response.message == ticket_create.message
        assert ticket_response.id == 1
        assert ticket_response.status == "open"

    def test_list_response_workflow(self):
        """Test typical workflow: list tickets -> return list response."""
        created_at = datetime.now()
        
        # Simulate multiple database responses
        ticket_data_list = [
            {
                "id": 1,
                "message": "Login problem",
                "intent": "login_issue",
                "confidence": 0.92,
                "status": "open",
                "created_at": created_at
            },
            {
                "id": 2,
                "message": "Payment failed",
                "intent": "payment",
                "confidence": 0.88,
                "status": "escalated",
                "created_at": created_at
            }
        ]
        
        tickets = [TicketResponse(**data) for data in ticket_data_list]
        ticket_list = TicketList(tickets=tickets)
        
        # Verify list response
        assert len(ticket_list.tickets) == 2
        assert ticket_list.tickets[0].intent == "login_issue"
        assert ticket_list.tickets[1].intent == "payment"

    def test_schema_serialization(self):
        """Test schema serialization to JSON."""
        created_at = datetime.now()
        ticket_data = {
            "id": 1,
            "message": "Test message",
            "intent": "test_intent",
            "confidence": 0.75,
            "status": "open",
            "created_at": created_at
        }
        
        ticket = TicketResponse(**ticket_data)
        
        # Test serialization with json mode to serialize datetime
        ticket_dict = ticket.model_dump(mode='json')
        assert ticket_dict["id"] == 1
        assert ticket_dict["message"] == "Test message"
        assert ticket_dict["intent"] == "test_intent"
        assert ticket_dict["confidence"] == 0.75
        assert ticket_dict["status"] == "open"
        # In json mode, datetime is serialized as ISO string
        assert isinstance(ticket_dict["created_at"], str)
        
        # Test default serialization (datetime stays as datetime object)
        ticket_dict_default = ticket.model_dump()
        assert isinstance(ticket_dict_default["created_at"], datetime)

    def test_schema_json_serialization(self):
        """Test schema JSON serialization."""
        created_at = datetime.now()
        ticket_data = {
            "id": 1,
            "message": "Test message",
            "status": "open",
            "created_at": created_at,
            "intent": None,
            "confidence": None
        }
        
        ticket = TicketResponse(**ticket_data)
        
        # Test JSON serialization
        json_str = ticket.model_dump_json()
        assert isinstance(json_str, str)
        assert "Test message" in json_str
        assert "open" in json_str
