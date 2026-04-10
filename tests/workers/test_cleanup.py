"""
Tests for workers/cleanup.py

Covers:
- archive_old_tickets: archiving eligible tickets, skipping open tickets,
  dry-run mode, cutoff date boundary
- remove_orphaned_feedback: detecting and removing orphaned feedback records,
  dry-run mode, no-op when no orphans exist
- run_cleanup: integration through the full cleanup pipeline
- _parse_args: CLI argument defaults and overrides
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.feedback import Feedback
from app.models.ticket import Ticket
from workers.cleanup import (
    ARCHIVABLE_STATUSES,
    _parse_args,
    archive_old_tickets,
    remove_orphaned_feedback,
    run_cleanup,
)


# ---------------------------------------------------------------------------
# Shared DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def temp_db_path():
    """Yield a temporary SQLite file path and remove it afterwards."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


@pytest.fixture()
def db_session(temp_db_path):
    """Provide a fresh SQLAlchemy session backed by a temporary database."""
    url = f"sqlite:///{temp_db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import models so they register with Base
    from app.models import feedback, ticket, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ticket(db, message="Test ticket", status="open", age_days=0) -> Ticket:
    """Insert a ticket with a specific status and age, return it."""
    created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    ticket = Ticket(message=message, status=status, created_at=created_at)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def _make_feedback(db, ticket_id: int, rating: int = 4, resolved: bool = True) -> Feedback:
    """Insert a feedback record for a ticket."""
    fb = Feedback(ticket_id=ticket_id, rating=rating, resolved=resolved)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


# ---------------------------------------------------------------------------
# archive_old_tickets
# ---------------------------------------------------------------------------

class TestArchiveOldTickets:

    def test_archives_eligible_ticket(self, db_session):
        """Tickets with archivable status and old enough should be marked is_archived=True."""
        ticket = _make_ticket(db_session, status="closed", age_days=100)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        count = archive_old_tickets(db_session, cutoff)

        assert count == 1
        db_session.refresh(ticket)
        assert ticket.is_archived is True
        assert ticket.status == "closed"  # original status preserved

    def test_skips_open_tickets(self, db_session):
        """Open tickets must never be archived."""
        _make_ticket(db_session, status="open", age_days=200)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        count = archive_old_tickets(db_session, cutoff)

        assert count == 0

    def test_skips_recent_ticket(self, db_session):
        """Closed tickets newer than cutoff should not be archived."""
        ticket = _make_ticket(db_session, status="closed", age_days=10)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        count = archive_old_tickets(db_session, cutoff)

        assert count == 0
        db_session.refresh(ticket)
        assert ticket.is_archived is False
        assert ticket.status == "closed"

    def test_archives_all_archivable_statuses(self, db_session):
        """All statuses in ARCHIVABLE_STATUSES should be eligible."""
        for status in ARCHIVABLE_STATUSES:
            _make_ticket(db_session, status=status, age_days=100)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        count = archive_old_tickets(db_session, cutoff)

        assert count == len(ARCHIVABLE_STATUSES)
        # All archived tickets should still have their original status
        for status in ARCHIVABLE_STATUSES:
            t = db_session.query(Ticket).filter_by(status=status).one()
            assert t.is_archived is True

    def test_dry_run_does_not_write(self, db_session):
        """Dry-run mode should return the count but not change the DB."""
        ticket = _make_ticket(db_session, status="closed", age_days=100)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        count = archive_old_tickets(db_session, cutoff, dry_run=True)

        assert count == 1
        db_session.refresh(ticket)
        assert ticket.is_archived is False  # unchanged
        assert ticket.status == "closed"    # unchanged

    def test_returns_zero_when_nothing_to_archive(self, db_session):
        """Returns 0 when there are no eligible tickets."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        count = archive_old_tickets(db_session, cutoff)
        assert count == 0

    def test_exact_cutoff_boundary(self, db_session):
        """Tickets created exactly at the cutoff should NOT be archived (strictly older)."""
        # created at exactly the cutoff — not strictly before it
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        ticket = Ticket(message="boundary ticket", status="closed", created_at=cutoff)
        db_session.add(ticket)
        db_session.commit()

        count = archive_old_tickets(db_session, cutoff)

        assert count == 0

    def test_archives_multiple_tickets(self, db_session):
        """Multiple eligible tickets are all archived."""
        for i in range(5):
            _make_ticket(db_session, status="auto_resolved", age_days=100 + i)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        count = archive_old_tickets(db_session, cutoff)

        assert count == 5
        for t in db_session.query(Ticket).filter_by(status="auto_resolved").all():
            assert t.is_archived is True


# ---------------------------------------------------------------------------
# remove_orphaned_feedback
# ---------------------------------------------------------------------------

class TestRemoveOrphanedFeedback:

    def test_removes_orphaned_feedback(self, db_session):
        """
        Feedback whose ticket_id doesn't match any existing ticket should be removed.

        SQLite doesn't enforce FK constraints by default, so we can insert orphaned
        feedback directly by bypassing the normal FK path.
        """
        # Insert an orphaned feedback record using raw SQL to bypass FK enforcement
        from sqlalchemy import text
        db_session.execute(
            text("INSERT INTO feedback (ticket_id, rating, resolved, created_at) VALUES (9999, 5, 1, CURRENT_TIMESTAMP)")
        )
        db_session.commit()

        count = remove_orphaned_feedback(db_session)

        assert count == 1
        remaining = db_session.query(Feedback).filter_by(ticket_id=9999).all()
        assert remaining == []

    def test_does_not_remove_valid_feedback(self, db_session):
        """Feedback that has a valid parent ticket should be left alone."""
        ticket = _make_ticket(db_session, status="auto_resolved")
        fb = _make_feedback(db_session, ticket_id=ticket.id)

        count = remove_orphaned_feedback(db_session)

        assert count == 0
        assert db_session.query(Feedback).filter_by(id=fb.id).one_or_none() is not None

    def test_dry_run_does_not_delete(self, db_session):
        """Dry-run should report orphans but not delete them."""
        from sqlalchemy import text
        db_session.execute(
            text("INSERT INTO feedback (ticket_id, rating, resolved, created_at) VALUES (8888, 3, 0, CURRENT_TIMESTAMP)")
        )
        db_session.commit()

        count = remove_orphaned_feedback(db_session, dry_run=True)

        assert count == 1
        # still present
        remaining = db_session.query(Feedback).filter_by(ticket_id=8888).all()
        assert len(remaining) == 1

    def test_returns_zero_when_no_orphans(self, db_session):
        """Returns 0 when there are no orphaned feedback records."""
        count = remove_orphaned_feedback(db_session)
        assert count == 0


# ---------------------------------------------------------------------------
# run_cleanup integration
# ---------------------------------------------------------------------------

class TestRunCleanup:

    @pytest.fixture()
    def isolated_session_factory(self, temp_db_path):
        """Return a (engine, SessionLocal) pair pointing at the temp DB."""
        url = f"sqlite:///{temp_db_path}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        from app.models import feedback, ticket, user  # noqa: F401
        Base.metadata.create_all(bind=engine)
        yield engine, Session
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    def test_returns_summary_dict(self, monkeypatch, isolated_session_factory):
        """run_cleanup should return a dict with the expected keys."""
        _engine, TestSession = isolated_session_factory
        import workers.cleanup as wc
        monkeypatch.setattr(wc, "SessionLocal", TestSession)
        monkeypatch.setattr(wc, "init_db", lambda: None)

        result = run_cleanup(days=90, dry_run=True)

        assert isinstance(result, dict)
        assert "archived_tickets" in result
        assert "removed_feedback" in result

    def test_empty_db_returns_zeros(self, monkeypatch, isolated_session_factory):
        """On an empty database both counters should be zero."""
        _engine, TestSession = isolated_session_factory
        import workers.cleanup as wc
        monkeypatch.setattr(wc, "SessionLocal", TestSession)
        monkeypatch.setattr(wc, "init_db", lambda: None)

        result = run_cleanup(days=90, dry_run=False)

        assert result["archived_tickets"] == 0
        assert result["removed_feedback"] == 0


# ---------------------------------------------------------------------------
# CLI arg parsing
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_defaults(self):
        """Default days=90 and dry_run=False."""
        args = _parse_args([])
        assert args.days == 90
        assert args.dry_run is False

    def test_custom_days(self):
        """--days flag is accepted."""
        args = _parse_args(["--days", "30"])
        assert args.days == 30

    def test_dry_run_flag(self):
        """--dry-run flag sets dry_run=True."""
        args = _parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_combined_flags(self):
        """Both flags can be combined."""
        args = _parse_args(["--days", "7", "--dry-run"])
        assert args.days == 7
        assert args.dry_run is True
