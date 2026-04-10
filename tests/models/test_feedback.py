import pytest
from sqlalchemy import exc as sqlalchemy_exc, event, text
from sqlalchemy.orm import Session

from app.db.session import Base, engine
from app.models.feedback import Feedback
from app.models.ticket import Ticket


def create_ticket(db: Session, message: str = "Test ticket") -> Ticket:
    """Helper to create a ticket and return it."""
    ticket = Ticket(message=message)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def create_feedback_seed():
    """Helper function to create tickets and feedback for testing."""
    with Session(engine) as db:
        tickets = []
        for i in range(4):
            ticket = Ticket(message=f"Test ticket {i+1} for feedback queries")
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            tickets.append(ticket)

        feedback_entries = [
            Feedback(ticket_id=tickets[0].id, rating=5, resolved=True),
            Feedback(ticket_id=tickets[1].id, rating=3, resolved=False),
            Feedback(ticket_id=tickets[2].id, rating=4, resolved=True),
            Feedback(ticket_id=tickets[3].id, rating=5, resolved=False),
        ]

        for feedback in feedback_entries:
            db.add(feedback)
        db.commit()

        # Return primitive identifiers instead of ORM instances
        ticket_ids = [t.id for t in tickets]
        feedback_data = [
            {"ticket_id": f.ticket_id, "rating": f.rating, "resolved": f.resolved} 
            for f in feedback_entries
        ]
        return ticket_ids, feedback_data


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

    def setup_method(self):
        """Clean DB state before each test for isolation."""
        with Session(engine) as db:
            db.query(Feedback).delete()
            db.query(Ticket).delete()
            db.commit()

    # -------------------------------------------------------------------------
    # Schema / model introspection tests (no DB needed)
    # -------------------------------------------------------------------------

    def test_feedback_model_inherits_from_base(self):
        """Feedback should inherit from SQLAlchemy Base."""
        assert hasattr(Feedback, '__tablename__')
        assert hasattr(Feedback, '__table__')
        assert Feedback.__tablename__ == "feedback"

    def test_feedback_table_name(self):
        """Feedback table should be named 'feedback'."""
        assert Feedback.__tablename__ == "feedback"

    def test_feedback_rating_values(self):
        """Should accept valid rating values (in-memory check)."""
        for rating in [1, 2, 3, 4, 5]:
            feedback = Feedback(ticket_id=1, rating=rating, resolved=True)
            assert feedback.rating == rating

    def test_feedback_boolean_values(self):
        """Should handle both True and False for resolved field (in-memory check)."""
        feedback_true = Feedback(ticket_id=1, rating=5, resolved=True)
        assert feedback_true.resolved is True

        feedback_false = Feedback(ticket_id=1, rating=5, resolved=False)
        assert feedback_false.resolved is False

    # -------------------------------------------------------------------------
    # FIX 1: test_feedback_creation — create a real ticket first
    # -------------------------------------------------------------------------

    def test_feedback_creation(self):
        """Should create feedback with required fields."""
        with Session(engine) as db:
            # Create a ticket so foreign key is satisfied
            ticket = create_ticket(db, "Ticket for creation test")

            feedback = Feedback(ticket_id=ticket.id, rating=5, resolved=True)
            db.add(feedback)
            db.commit()
            db.refresh(feedback)

            assert feedback.ticket_id == ticket.id
            assert feedback.rating == 5
            assert feedback.resolved is True
            assert feedback.created_at is not None

    # -------------------------------------------------------------------------
    # FIX 2: test_feedback_string_representation — verify __repr__ exists and
    # contains expected fields; skip gracefully if not yet implemented.
    # -------------------------------------------------------------------------

    def test_feedback_string_representation(self):
        """Feedback should have a meaningful __repr__."""
        feedback = Feedback(ticket_id=1, rating=5, resolved=True)
        repr_str = repr(feedback)

        # If the model has NOT defined __repr__, default SQLAlchemy repr
        # will NOT include field values — this assertion documents the contract
        # so developers know they must implement __repr__ on the model.
        assert "Feedback" in repr_str, (
            "__repr__ must include the class name 'Feedback'"
        )
        assert "ticket_id=1" in repr_str, (
            "__repr__ must include 'ticket_id=<value>'. "
            "Add __repr__ to the Feedback model."
        )
        assert "rating=5" in repr_str, (
            "__repr__ must include 'rating=<value>'"
        )
        assert "resolved=True" in repr_str, (
            "__repr__ must include 'resolved=<value>'"
        )

    # -------------------------------------------------------------------------
    # FIX 3: test_feedback_foreign_key_constraint — enable FK pragma reliably
    # using a connection-level event so it applies to every connection from
    # the pool, not just the current session.
    # -------------------------------------------------------------------------

    def test_feedback_foreign_key_constraint(self):
        """Should enforce foreign key constraint to tickets table."""
        # Create a temporary local engine for this test to avoid affecting other tests
        from sqlalchemy import create_engine, text
        from app.db.session import Base
        
        local_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=local_engine)
        
        # Enable FK enforcement at engine level for this test
        @event.listens_for(local_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        try:
            with Session(local_engine) as db:
                # Explicitly enable foreign keys for this session
                db.execute(text("PRAGMA foreign_keys = ON"))
                feedback = Feedback(ticket_id=99999, rating=5, resolved=True)
                db.add(feedback)

                with pytest.raises(sqlalchemy_exc.IntegrityError):
                    db.commit()
        finally:
            # Remove the listener so it doesn't affect other tests
            event.remove(local_engine, "connect", set_sqlite_pragma)
            # Dispose of the local engine
            local_engine.dispose()

    # -------------------------------------------------------------------------
    # Unique constraint — unchanged, already creates its own ticket
    # -------------------------------------------------------------------------

    def test_feedback_unique_constraint(self):
        """Should enforce unique constraint on ticket_id."""
        with Session(engine) as db:
            ticket = create_ticket(db, "Ticket for unique constraint test")

            feedback1 = Feedback(ticket_id=ticket.id, rating=5, resolved=True)
            db.add(feedback1)
            db.commit()

            feedback2 = Feedback(ticket_id=ticket.id, rating=3, resolved=False)
            db.add(feedback2)

            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    # -------------------------------------------------------------------------
    # FIX 4: test_feedback_not_null_constraint — create a real ticket first;
    # also add a note: SQLite only enforces NOT NULL if the column is defined
    # with nullable=False in the model.
    # -------------------------------------------------------------------------

    def test_feedback_not_null_constraint(self):
        """
        Should enforce NOT NULL constraint on the 'resolved' column.

        Requirement: Feedback.resolved must be defined as:
            resolved = Column(Boolean, nullable=False)
        SQLite silently allows NULL on Boolean columns unless nullable=False
        is explicitly set on the column definition.
        """
        with Session(engine) as db:
            # Create a real ticket to avoid FK violation masking the real error
            ticket = create_ticket(db, "Ticket for not-null test")

            feedback = Feedback(ticket_id=ticket.id, rating=5, resolved=None)
            db.add(feedback)

            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    # -------------------------------------------------------------------------
    # Query tests — unchanged logic, isolation handled by setup_method
    # -------------------------------------------------------------------------

    def test_feedback_query_by_rating(self):
        """Should be able to query feedback by rating."""
        create_feedback_seed()

        with Session(engine) as db:
            assert len(db.query(Feedback).filter(Feedback.rating == 5).all()) == 2
            assert len(db.query(Feedback).filter(Feedback.rating == 3).all()) == 1
            assert len(db.query(Feedback).filter(Feedback.rating == 4).all()) == 1

    def test_feedback_query_by_resolved_status(self):
        """Should be able to query feedback by resolved status."""
        create_feedback_seed()

        with Session(engine) as db:
            resolved = db.query(Feedback).filter(Feedback.resolved == True).all()
            unresolved = db.query(Feedback).filter(Feedback.resolved == False).all()

            assert len(resolved) == 2
            assert len(unresolved) == 2

            for f in resolved:
                assert f.resolved is True
            for f in unresolved:
                assert f.resolved is False
