"""
Tests for app/models/ticket.py

Covers:
- Ticket model creation and validation
- Column constraints and defaults
- Status enumeration
- Table structure
- Database operations
"""
import pytest
from datetime import datetime
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from app.db.session import Base, engine, init_db
from app.models.ticket import Ticket


class TestTicketModel:
    """Tests for Ticket ORM model."""

    @classmethod
    def setup_class(cls):
        """Create tables for test class."""
        Base.metadata.create_all(bind=engine)

    @classmethod
    def teardown_class(cls):
        """Drop tables after test class."""
        Base.metadata.drop_all(bind=engine)

    def test_ticket_model_inherits_from_base(self):
        """Ticket should inherit from SQLAlchemy Base."""
        assert hasattr(Ticket, '__tablename__')
        assert hasattr(Ticket, '__table__')
        assert Ticket.__tablename__ == "tickets"

    def test_ticket_table_name(self):
        """Ticket table should be named 'tickets'."""
        assert Ticket.__tablename__ == "tickets"

    def test_ticket_columns_exist(self):
        """Ticket should have all required columns."""
        columns = Ticket.__table__.columns
        column_names = [col.name for col in columns]
        
        required_columns = ['id', 'message', 'intent', 'confidence', 'status', 'created_at']
        for col in required_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_ticket_id_column_properties(self):
        """id column should be Integer, Primary Key, and indexed."""
        id_column = Ticket.__table__.columns['id']
        
        assert str(id_column.type) == 'INTEGER'
        assert id_column.primary_key is True
        assert id_column.index is True

    def test_ticket_message_column_properties(self):
        """message column should be String and not nullable."""
        message_column = Ticket.__table__.columns['message']
        
        assert str(message_column.type) == 'VARCHAR'
        assert message_column.nullable is False

    def test_ticket_intent_column_properties(self):
        """intent column should be String and nullable."""
        intent_column = Ticket.__table__.columns['intent']
        
        assert str(intent_column.type) == 'VARCHAR'
        assert intent_column.nullable is True

    def test_ticket_confidence_column_properties(self):
        """confidence column should be Float and nullable."""
        confidence_column = Ticket.__table__.columns['confidence']
        
        assert str(confidence_column.type) == 'FLOAT'
        assert confidence_column.nullable is True

    def test_ticket_status_column_properties(self):
        """status column should be String, not nullable, with default 'open'."""
        status_column = Ticket.__table__.columns['status']
        
        assert str(status_column.type) == 'VARCHAR'
        assert status_column.nullable is False
        assert status_column.default.arg == 'open'

    def test_ticket_created_at_column_properties(self):
        """created_at column should be DateTime and not nullable."""
        created_at_column = Ticket.__table__.columns['created_at']
        
        assert str(created_at_column.type) == 'DATETIME'
        assert created_at_column.nullable is False
        # default is a callable (datetime.utcnow)

    def test_ticket_creation_with_required_fields(self):
        """Should create ticket with required fields only."""
        ticket = Ticket(message="I need help with my account")
        
        assert ticket.message == "I need help with my account"
        assert ticket.status == "open"  # Default value
        assert ticket.intent is None
        assert ticket.confidence is None
        assert ticket.id is None  # Not set until saved to DB

    def test_ticket_creation_with_all_fields(self):
        """Should create ticket with all fields."""
        ticket = Ticket(
            message="Payment failed",
            intent="payment_issue",
            confidence=0.92,
            status="escalated"
        )
        
        assert ticket.message == "Payment failed"
        assert ticket.intent == "payment_issue"
        assert ticket.confidence == 0.92
        assert ticket.status == "escalated"

    def test_ticket_status_default(self):
        """Ticket status should default to 'open' when not specified."""
        ticket = Ticket(message="Test message")
        
        assert ticket.status == "open"

    def test_ticket_all_valid_statuses(self):
        """Should accept all valid status values."""
        valid_statuses = ["open", "auto_resolved", "escalated", "closed"]
        
        for status in valid_statuses:
            ticket = Ticket(message="Test message", status=status)
            assert ticket.status == status

    def test_ticket_string_representation(self):
        """Ticket should have meaningful string representation."""
        ticket = Ticket(message="Test message")
        
        # Should be a valid object representation
        str_repr = str(ticket)
        assert "Ticket object" in str_repr or "Test message" in str_repr

    def test_ticket_database_persistence(self):
        """Should persist ticket to database correctly."""
        with Session(engine) as db:
            # Create ticket
            ticket = Ticket(
                message="Cannot login to my account",
                intent="login_issue",
                confidence=0.78,
                status="open"
            )
            
            # Add to database
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # Verify ID and created_at were assigned
            assert ticket.id is not None
            assert ticket.created_at is not None
            assert isinstance(ticket.created_at, datetime)
            
            # Retrieve from database
            retrieved_ticket = db.query(Ticket).filter(Ticket.message == "Cannot login to my account").first()
            
            assert retrieved_ticket is not None
            assert retrieved_ticket.message == "Cannot login to my account"
            assert retrieved_ticket.intent == "login_issue"
            assert retrieved_ticket.confidence == 0.78
            assert retrieved_ticket.status == "open"
            assert retrieved_ticket.id == ticket.id

    def test_ticket_message_not_null_constraint(self):
        """Should enforce not null constraint on message."""
        with Session(engine) as db:
            ticket = Ticket()
            db.add(ticket)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_ticket_status_not_null_constraint(self):
        """Should enforce not null constraint on status at database level."""
        with Session(engine) as db:
            # Test database constraint by directly inserting NULL
            with pytest.raises((sqlalchemy_exc.IntegrityError, sqlalchemy_exc.StatementError)):
                from sqlalchemy import text
                db.execute(text("INSERT INTO tickets (message, status) VALUES (:message, :status)"), 
                         {"message": "Test message", "status": None})
                db.commit()

    def test_ticket_query_by_status(self):
        """Should be able to query tickets by status."""
        with Session(engine) as db:
            # Clean up any existing tickets first
            db.query(Ticket).delete()
            db.commit()
            
            # Create tickets with different statuses
            tickets = [
                Ticket(message="Open ticket 1", status="open"),
                Ticket(message="Auto resolved ticket", status="auto_resolved"),
                Ticket(message="Escalated ticket", status="escalated"),
                Ticket(message="Closed ticket", status="closed"),
                Ticket(message="Open ticket 2", status="open"),
            ]
            
            for ticket in tickets:
                db.add(ticket)
            db.commit()
            
            # Query by status
            open_tickets = db.query(Ticket).filter(Ticket.status == "open").all()
            auto_resolved_tickets = db.query(Ticket).filter(Ticket.status == "auto_resolved").all()
            escalated_tickets = db.query(Ticket).filter(Ticket.status == "escalated").all()
            closed_tickets = db.query(Ticket).filter(Ticket.status == "closed").all()
            
            assert len(open_tickets) == 2
            assert len(auto_resolved_tickets) == 1
            assert len(escalated_tickets) == 1
            assert len(closed_tickets) == 1
            
            # Verify specific tickets
            open_messages = [t.message for t in open_tickets]
            assert "Open ticket 1" in open_messages
            assert "Open ticket 2" in open_messages

    def test_ticket_query_by_intent(self):
        """Should be able to query tickets by intent."""
        with Session(engine) as db:
            # Clean up any existing tickets first
            db.query(Ticket).delete()
            db.commit()
            
            # Create tickets with different intents
            tickets = [
                Ticket(message="Login problem", intent="login_issue", confidence=0.8),
                Ticket(message="Payment failed", intent="payment_issue", confidence=0.9),
                Ticket(message="Refund request", intent="refund_request", confidence=0.7),
                Ticket(message="Another login problem", intent="login_issue", confidence=0.85),
            ]
            
            for ticket in tickets:
                db.add(ticket)
            db.commit()
            
            # Query by intent
            login_tickets = db.query(Ticket).filter(Ticket.intent == "login_issue").all()
            payment_tickets = db.query(Ticket).filter(Ticket.intent == "payment_issue").all()
            refund_tickets = db.query(Ticket).filter(Ticket.intent == "refund_request").all()
            
            assert len(login_tickets) == 2
            assert len(payment_tickets) == 1
            assert len(refund_tickets) == 1
            
            # Verify confidence scores are preserved
            for ticket in login_tickets:
                assert ticket.confidence in [0.8, 0.85]

    def test_ticket_confidence_range_validation(self):
        """Should handle confidence scores in valid range."""
        # Test various confidence values
        confidence_values = [0.0, 0.25, 0.5, 0.75, 1.0]
        
        for confidence in confidence_values:
            ticket = Ticket(
                message="Test message",
                intent="test_intent",
                confidence=confidence
            )
            assert ticket.confidence == confidence

    def test_ticket_created_at_auto_assignment(self):
        """Should automatically set created_at when saving to database."""
        with Session(engine) as db:
            ticket = Ticket(message="Test message")
            
            # created_at should be None before saving
            assert ticket.created_at is None
            
            # Save to database
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # created_at should be set after saving
            assert ticket.created_at is not None
            assert isinstance(ticket.created_at, datetime)

    def test_ticket_model_documentation(self):
        """Ticket model should have proper documentation."""
        assert Ticket.__doc__ is not None
        assert "Ticket ORM model" in Ticket.__doc__


class TestTicketModelIntegration:
    """Integration tests for Ticket model with database initialization."""

    def test_init_db_creates_ticket_table(self):
        """init_db should create the tickets table."""
        # Drop all tables first
        Base.metadata.drop_all(bind=engine)
        
        # Run init_db
        init_db()
        
        # Check if tickets table exists
        with Session(engine) as db:
            from sqlalchemy import text
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='tickets'"))
            tables = result.fetchall()
            assert len(tables) == 1
            assert tables[0][0] == 'tickets'
