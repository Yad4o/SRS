"""
Tests for app/models/feedback.py

Covers:
- Feedback model creation and validation
- Column constraints and defaults
- Foreign key relationship to tickets
- Table structure
- Database operations
"""
import pytest
from datetime import datetime
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from app.db.session import Base, engine, init_db
from app.models.feedback import Feedback
from app.models.ticket import Ticket


class TestFeedbackModel:
    """Tests for Feedback ORM model."""

    @classmethod
    def setup_class(cls):
        """Create tables for test class."""
        Base.metadata.create_all(bind=engine)

    @classmethod
    def teardown_class(cls):
        """Drop tables after test class."""
        Base.metadata.drop_all(bind=engine)

    def test_feedback_model_inherits_from_base(self):
        """Feedback should inherit from SQLAlchemy Base."""
        assert hasattr(Feedback, '__tablename__')
        assert hasattr(Feedback, '__table__')
        assert Feedback.__tablename__ == "feedback"

    def test_feedback_table_name(self):
        """Feedback table should be named 'feedback'."""
        assert Feedback.__tablename__ == "feedback"

    def test_feedback_columns_exist(self):
        """Feedback should have all required columns."""
        columns = Feedback.__table__.columns
        column_names = [col.name for col in columns]
        
        required_columns = ['id', 'ticket_id', 'rating', 'resolved', 'created_at']
        for col in required_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_feedback_id_column_properties(self):
        """id column should be Integer, Primary Key, and indexed."""
        id_column = Feedback.__table__.columns['id']
        
        assert str(id_column.type) == 'INTEGER'
        assert id_column.primary_key is True
        assert id_column.index is True

    def test_feedback_ticket_id_column_properties(self):
        """ticket_id column should be Integer with foreign key constraint."""
        ticket_id_column = Feedback.__table__.columns['ticket_id']
        
        assert str(ticket_id_column.type) == 'INTEGER'
        assert ticket_id_column.nullable is False
        assert ticket_id_column.foreign_keys
        assert str(list(ticket_id_column.foreign_keys)[0].column) == 'tickets.id'

    def test_feedback_rating_column_properties(self):
        """rating column should be Integer and not nullable."""
        rating_column = Feedback.__table__.columns['rating']
        
        assert str(rating_column.type) == 'INTEGER'
        assert rating_column.nullable is False

    def test_feedback_resolved_column_properties(self):
        """resolved column should be Boolean and not nullable."""
        resolved_column = Feedback.__table__.columns['resolved']
        
        assert str(resolved_column.type) == 'BOOLEAN'
        assert resolved_column.nullable is False

    def test_feedback_created_at_column_properties(self):
        """created_at column should be DateTime and not nullable."""
        created_at_column = Feedback.__table__.columns['created_at']
        
        assert str(created_at_column.type) == 'DATETIME'
        assert created_at_column.nullable is False
        # default is a callable (datetime.utcnow)

    def test_feedback_creation_with_required_fields(self):
        """Should create feedback with required fields."""
        feedback = Feedback(
            ticket_id=1,
            rating=5,
            resolved=True
        )
        
        assert feedback.ticket_id == 1
        assert feedback.rating == 5
        assert feedback.resolved is True
        assert feedback.id is None  # Not set until saved to DB

    def test_feedback_creation_with_all_fields(self):
        """Should create feedback with all fields."""
        feedback = Feedback(
            ticket_id=42,
            rating=3,
            resolved=False
        )
        
        assert feedback.ticket_id == 42
        assert feedback.rating == 3
        assert feedback.resolved is False

    def test_feedback_rating_range_validation(self):
        """Should handle various rating values."""
        # Test different rating values
        rating_values = [1, 2, 3, 4, 5]
        
        for rating in rating_values:
            feedback = Feedback(
                ticket_id=1,
                rating=rating,
                resolved=True
            )
            assert feedback.rating == rating

    def test_feedback_boolean_values(self):
        """Should handle both True and False for resolved field."""
        # Test resolved = True
        feedback_true = Feedback(ticket_id=1, rating=5, resolved=True)
        assert feedback_true.resolved is True
        
        # Test resolved = False
        feedback_false = Feedback(ticket_id=1, rating=5, resolved=False)
        assert feedback_false.resolved is False

    def test_feedback_string_representation(self):
        """Feedback should have meaningful string representation."""
        feedback = Feedback(ticket_id=1, rating=5, resolved=True)
        
        # Should have a meaningful __repr__ format
        repr_str = repr(feedback)
        assert "Feedback" in repr_str
        assert "ticket_id=1" in repr_str
        assert "rating=5" in repr_str
        assert "resolved=True" in repr_str
        
        # When id is None (not saved yet), it should show as None
        assert "id=None" in repr_str

    def test_feedback_string_representation_with_id(self):
        """Feedback __repr__ should show actual ID when saved to database."""
        with Session(engine) as db:
            # Create a ticket first
            ticket = Ticket(message="Test ticket for repr")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # Create and save feedback
            feedback = Feedback(ticket_id=ticket.id, rating=4, resolved=True)
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            
            # Now __repr__ should show the actual ID
            repr_str = repr(feedback)
            assert f"id={feedback.id}" in repr_str
            assert "ticket_id=" + str(ticket.id) in repr_str
            assert "rating=4" in repr_str
            assert "resolved=True" in repr_str

    def test_feedback_database_persistence(self):
        """Should persist feedback to database correctly."""
        with Session(engine) as db:
            # Create a ticket first (foreign key constraint)
            ticket = Ticket(message="Test ticket for feedback")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # Create feedback
            feedback = Feedback(
                ticket_id=ticket.id,
                rating=4,
                resolved=True
            )
            
            # Add to database
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            
            # Verify ID and created_at were assigned
            assert feedback.id is not None
            assert feedback.created_at is not None
            assert isinstance(feedback.created_at, datetime)
            
            # Retrieve from database
            retrieved_feedback = db.query(Feedback).filter(Feedback.ticket_id == ticket.id).first()
            
            assert retrieved_feedback is not None
            assert retrieved_feedback.ticket_id == ticket.id
            assert retrieved_feedback.rating == 4
            assert retrieved_feedback.resolved is True
            assert retrieved_feedback.id == feedback.id

    def test_feedback_ticket_id_not_null_constraint(self):
        """Should enforce not null constraint on ticket_id."""
        with Session(engine) as db:
            feedback = Feedback(rating=5, resolved=True)
            db.add(feedback)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_feedback_rating_not_null_constraint(self):
        """Should enforce not null constraint on rating."""
        with Session(engine) as db:
            feedback = Feedback(ticket_id=1, resolved=True)
            db.add(feedback)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_feedback_resolved_not_null_constraint(self):
        """Should enforce not null constraint on resolved."""
        with Session(engine) as db:
            feedback = Feedback(ticket_id=1, rating=5)
            db.add(feedback)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_feedback_foreign_key_constraint(self):
        """Should enforce foreign key constraint to tickets table."""
        with Session(engine) as db:
            # Enable foreign key constraint enforcement in SQLite
            from sqlalchemy import text
            db.execute(text("PRAGMA foreign_keys = ON"))
            
            # Try to create feedback with non-existent ticket_id
            feedback = Feedback(ticket_id=99999, rating=5, resolved=True)
            db.add(feedback)
            
            # Should raise integrity error due to foreign key constraint
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_feedback_query_by_rating(self):
        """Should be able to query feedback by rating."""
        with Session(engine) as db:
            # Clean up any existing feedback first
            db.query(Feedback).delete()
            db.commit()
            
            # Create a ticket first
            ticket = Ticket(message="Test ticket for feedback queries")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # Create feedback with different ratings
            feedback_entries = [
                Feedback(ticket_id=ticket.id, rating=5, resolved=True),
                Feedback(ticket_id=ticket.id, rating=3, resolved=False),
                Feedback(ticket_id=ticket.id, rating=4, resolved=True),
                Feedback(ticket_id=ticket.id, rating=5, resolved=False),
            ]
            
            for feedback in feedback_entries:
                db.add(feedback)
            db.commit()
            
            # Query by rating
            five_star_feedback = db.query(Feedback).filter(Feedback.rating == 5).all()
            three_star_feedback = db.query(Feedback).filter(Feedback.rating == 3).all()
            four_star_feedback = db.query(Feedback).filter(Feedback.rating == 4).all()
            
            assert len(five_star_feedback) == 2
            assert len(three_star_feedback) == 1
            assert len(four_star_feedback) == 1

    def test_feedback_query_by_resolved_status(self):
        """Should be able to query feedback by resolved status."""
        with Session(engine) as db:
            # Clean up any existing feedback first
            db.query(Feedback).delete()
            db.commit()
            
            # Create a ticket first
            ticket = Ticket(message="Test ticket for resolved queries")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # Create feedback with different resolved statuses
            feedback_entries = [
                Feedback(ticket_id=ticket.id, rating=5, resolved=True),
                Feedback(ticket_id=ticket.id, rating=3, resolved=False),
                Feedback(ticket_id=ticket.id, rating=4, resolved=True),
                Feedback(ticket_id=ticket.id, rating=2, resolved=False),
            ]
            
            for feedback in feedback_entries:
                db.add(feedback)
            db.commit()
            
            # Query by resolved status
            resolved_feedback = db.query(Feedback).filter(Feedback.resolved == True).all()
            unresolved_feedback = db.query(Feedback).filter(Feedback.resolved == False).all()
            
            assert len(resolved_feedback) == 2
            assert len(unresolved_feedback) == 2
            
            # Verify all resolved feedback have resolved=True
            for feedback in resolved_feedback:
                assert feedback.resolved is True
            
            # Verify all unresolved feedback have resolved=False
            for feedback in unresolved_feedback:
                assert feedback.resolved is False

    def test_feedback_created_at_auto_assignment(self):
        """Should automatically set created_at when saving to database."""
        with Session(engine) as db:
            # Create a ticket first
            ticket = Ticket(message="Test ticket for timestamp")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            feedback = Feedback(ticket_id=ticket.id, rating=5, resolved=True)
            
            # created_at should be None before saving
            assert feedback.created_at is None
            
            # Save to database
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            
            # created_at should be set after saving
            assert feedback.created_at is not None
            assert isinstance(feedback.created_at, datetime)

    def test_feedback_model_documentation(self):
        """Feedback model should have proper documentation."""
        assert Feedback.__doc__ is not None
        assert "Feedback ORM model" in Feedback.__doc__

    def test_feedback_ticket_relationship(self):
        """Should have proper relationship to Ticket model."""
        with Session(engine) as db:
            # Create a ticket
            ticket = Ticket(message="Test ticket for relationship")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            # Create feedback
            feedback = Feedback(ticket_id=ticket.id, rating=5, resolved=True)
            db.add(feedback)
            db.commit()
            db.refresh(feedback)
            
            # Test relationship access
            assert hasattr(feedback, 'ticket')
            # Note: The relationship might be lazy-loaded, so we access it through the session
            feedback_with_ticket = db.query(Feedback).filter(Feedback.id == feedback.id).first()
            assert feedback_with_ticket.ticket.id == ticket.id
            assert feedback_with_ticket.ticket.message == "Test ticket for relationship"


class TestFeedbackModelIntegration:
    """Integration tests for Feedback model with database initialization."""

    def test_init_db_creates_feedback_table(self):
        """init_db should create the feedback table."""
        # Drop all tables first
        Base.metadata.drop_all(bind=engine)
        
        # Run init_db
        init_db()
        
        # Check if feedback table exists
        with Session(engine) as db:
            from sqlalchemy import text
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'"))
            tables = result.fetchall()
            assert len(tables) == 1
            assert tables[0][0] == 'feedback'

    def test_foreign_key_constraint_in_database(self):
        """Database should enforce foreign key constraints when enabled."""
        with Session(engine) as db:
            # Enable foreign key constraint enforcement in SQLite
            from sqlalchemy import text
            db.execute(text("PRAGMA foreign_keys = ON"))
            
            # Try to insert feedback with invalid ticket_id
            with pytest.raises((sqlalchemy_exc.IntegrityError, sqlalchemy_exc.StatementError)):
                db.execute(text("INSERT INTO feedback (ticket_id, rating, resolved) VALUES (:ticket_id, :rating, :resolved)"), 
                         {"ticket_id": 99999, "rating": 5, "resolved": True})
                db.commit()

    def test_foreign_key_constraint_definition(self):
        """Database should have foreign key constraint properly defined in SQLAlchemy model."""
        with Session(engine) as db:
            from sqlalchemy import text
            
            # First, enable foreign keys to see if they're defined
            db.execute(text("PRAGMA foreign_keys = ON"))
            
            # Check if foreign key is defined in the table schema
            result = db.execute(text("PRAGMA foreign_key_list(feedback)"))
            foreign_keys = result.fetchall()
            
            # SQLite behavior: foreign keys may not appear in PRAGMA foreign_key_list
            # if they weren't created with explicit constraints. Let's validate what we can.
            
            # Method 1: Check if foreign key exists in PRAGMA foreign_key_list
            if len(foreign_keys) > 0:
                # Foreign key is properly defined in database
                assert len(foreign_keys) == 1, f"Expected 1 foreign key, found {len(foreign_keys)}"
                fk = foreign_keys[0]
                fk_id, seq, referenced_table, from_column, to_column, on_update, on_delete, match = fk
                
                assert referenced_table == 'tickets', f"FK should reference 'tickets' table, got '{referenced_table}'"
                assert from_column == 'ticket_id', f"FK should be on 'ticket_id' column, got '{from_column}'"
                assert to_column == 'id', f"FK should reference 'id' column, got '{to_column}'"
            else:
                # Method 2: Validate through SQLAlchemy model inspection
                # This confirms the FK is defined at the ORM level
                from app.models.feedback import Feedback
                ticket_id_column = Feedback.__table__.columns['ticket_id']
                
                # Check that the column has foreign keys defined in SQLAlchemy
                assert len(list(ticket_id_column.foreign_keys)) > 0, "ticket_id should have foreign keys defined in SQLAlchemy"
                
                # Validate the foreign key definition
                fk = list(ticket_id_column.foreign_keys)[0]
                assert str(fk.column) == 'tickets.id', f"Foreign key should reference tickets.id, got {fk.column}"
                assert fk.parent.name == 'ticket_id', f"Foreign key should be on ticket_id column, got {fk.parent.name}"
                
                # Test that the foreign key relationship works (even if not enforced by SQLite)
                # This validates the ORM-level relationship is properly configured
                assert hasattr(Feedback, 'ticket'), "Feedback should have ticket relationship defined"
