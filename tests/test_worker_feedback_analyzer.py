"""
Tests for workers/feedback_analyzer.py

Covers:
- _safe_avg: empty list, single value, multiple values
- analyze_feedback: empty records, aggregation correctness, per-intent/status
  breakdowns, rating distribution, null handling
- fetch_feedback_with_tickets: joins feedback with ticket data from DB
- run_feedback_analyzer: end-to-end integration, JSON output
- _parse_args: CLI defaults and --output override
"""
import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.feedback import Feedback
from app.models.ticket import Ticket
from workers.feedback_analyzer import (
    _parse_args,
    _safe_avg,
    analyze_feedback,
    fetch_feedback_with_tickets,
    run_feedback_analyzer,
)


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def temp_db_path():
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
    url = f"sqlite:///{temp_db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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

def _make_ticket(db, message="msg", intent=None, status="auto_resolved") -> Ticket:
    t = Ticket(message=message, intent=intent, status=status)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _make_feedback(db, ticket_id: int, rating: int = 4, resolved: bool = True) -> Feedback:
    fb = Feedback(ticket_id=ticket_id, rating=rating, resolved=resolved)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def _make_record(rating=4, resolved=True, intent="login_issue", ticket_status="auto_resolved"):
    """Return a feedback+ticket dict as produced by fetch_feedback_with_tickets."""
    return {
        "feedback_id": 1,
        "ticket_id": 1,
        "rating": rating,
        "resolved": resolved,
        "created_at": "2024-01-01T00:00:00",
        "intent": intent,
        "ticket_status": ticket_status,
    }


# ---------------------------------------------------------------------------
# _safe_avg
# ---------------------------------------------------------------------------

class TestSafeAvg:

    def test_empty_list_returns_zero(self):
        assert _safe_avg([]) == 0.0

    def test_single_value(self):
        assert _safe_avg([5.0]) == 5.0

    def test_multiple_values(self):
        result = _safe_avg([1.0, 3.0, 5.0])
        assert abs(result - 3.0) < 1e-6

    def test_rounded_to_three_decimals(self):
        result = _safe_avg([1, 2])
        assert result == 1.5


# ---------------------------------------------------------------------------
# analyze_feedback
# ---------------------------------------------------------------------------

class TestAnalyzeFeedback:

    def test_empty_records_returns_zeros(self):
        result = analyze_feedback([])
        assert result["total_feedback"] == 0
        assert result["average_rating"] == 0.0
        assert result["resolution_rate"] == 0.0
        assert result["by_intent"] == {}
        assert result["by_ticket_status"] == {}
        assert result["rating_distribution"] == {}

    def test_total_feedback_count(self):
        records = [_make_record(rating=5), _make_record(rating=3)]
        result = analyze_feedback(records)
        assert result["total_feedback"] == 2

    def test_average_rating(self):
        records = [_make_record(rating=4), _make_record(rating=2)]
        result = analyze_feedback(records)
        assert abs(result["average_rating"] - 3.0) < 1e-6

    def test_resolution_rate_all_resolved(self):
        records = [_make_record(resolved=True), _make_record(resolved=True)]
        result = analyze_feedback(records)
        assert result["resolution_rate"] == 1.0

    def test_resolution_rate_none_resolved(self):
        records = [_make_record(resolved=False), _make_record(resolved=False)]
        result = analyze_feedback(records)
        assert result["resolution_rate"] == 0.0

    def test_resolution_rate_partial(self):
        records = [_make_record(resolved=True), _make_record(resolved=False)]
        result = analyze_feedback(records)
        assert abs(result["resolution_rate"] - 0.5) < 1e-6

    def test_by_intent_contains_correct_intents(self):
        records = [
            _make_record(intent="login_issue"),
            _make_record(intent="payment_issue"),
            _make_record(intent="login_issue"),
        ]
        result = analyze_feedback(records)
        assert "login_issue" in result["by_intent"]
        assert "payment_issue" in result["by_intent"]

    def test_by_intent_count(self):
        records = [
            _make_record(intent="login_issue", rating=5),
            _make_record(intent="login_issue", rating=3),
        ]
        result = analyze_feedback(records)
        assert result["by_intent"]["login_issue"]["count"] == 2

    def test_by_intent_average_rating(self):
        records = [
            _make_record(intent="login_issue", rating=4),
            _make_record(intent="login_issue", rating=2),
        ]
        result = analyze_feedback(records)
        assert abs(result["by_intent"]["login_issue"]["average_rating"] - 3.0) < 1e-6

    def test_by_intent_resolution_rate(self):
        records = [
            _make_record(intent="login_issue", resolved=True),
            _make_record(intent="login_issue", resolved=False),
        ]
        result = analyze_feedback(records)
        assert abs(result["by_intent"]["login_issue"]["resolution_rate"] - 0.5) < 1e-6

    def test_none_intent_grouped_as_unknown(self):
        records = [_make_record(intent=None)]
        result = analyze_feedback(records)
        assert "unknown" in result["by_intent"]

    def test_by_ticket_status_breakdown(self):
        records = [
            _make_record(ticket_status="auto_resolved"),
            _make_record(ticket_status="closed"),
            _make_record(ticket_status="auto_resolved"),
        ]
        result = analyze_feedback(records)
        assert "auto_resolved" in result["by_ticket_status"]
        assert "closed" in result["by_ticket_status"]
        assert result["by_ticket_status"]["auto_resolved"]["count"] == 2

    def test_rating_distribution(self):
        records = [
            _make_record(rating=5),
            _make_record(rating=5),
            _make_record(rating=3),
        ]
        result = analyze_feedback(records)
        dist = result["rating_distribution"]
        # Keys are strings (consistent with JSON serialization)
        assert dist["5"] == 2
        assert dist["3"] == 1

    def test_single_record(self):
        records = [_make_record(rating=5, resolved=True, intent="login_issue", ticket_status="auto_resolved")]
        result = analyze_feedback(records)
        assert result["total_feedback"] == 1
        assert result["average_rating"] == 5.0
        assert result["resolution_rate"] == 1.0


# ---------------------------------------------------------------------------
# fetch_feedback_with_tickets
# ---------------------------------------------------------------------------

class TestFetchFeedbackWithTickets:

    def test_empty_db_returns_empty(self, db_session):
        result = fetch_feedback_with_tickets(db_session)
        assert result == []

    def test_returns_correct_structure(self, db_session):
        ticket = _make_ticket(db_session, intent="login_issue")
        _make_feedback(db_session, ticket_id=ticket.id, rating=5, resolved=True)

        results = fetch_feedback_with_tickets(db_session)

        assert len(results) == 1
        r = results[0]
        for key in ("feedback_id", "ticket_id", "rating", "resolved", "created_at", "intent", "ticket_status"):
            assert key in r

    def test_returns_ticket_intent(self, db_session):
        ticket = _make_ticket(db_session, intent="payment_issue")
        _make_feedback(db_session, ticket_id=ticket.id)

        results = fetch_feedback_with_tickets(db_session)

        assert results[0]["intent"] == "payment_issue"

    def test_returns_ticket_status(self, db_session):
        ticket = _make_ticket(db_session, status="closed")
        _make_feedback(db_session, ticket_id=ticket.id)

        results = fetch_feedback_with_tickets(db_session)

        assert results[0]["ticket_status"] == "closed"

    def test_multiple_feedback_records(self, db_session):
        for i in range(3):
            t = _make_ticket(db_session, message=f"Ticket {i}", intent="login_issue")
            _make_feedback(db_session, ticket_id=t.id, rating=i + 3)

        results = fetch_feedback_with_tickets(db_session)

        assert len(results) == 3

    def test_rating_is_correct(self, db_session):
        ticket = _make_ticket(db_session)
        _make_feedback(db_session, ticket_id=ticket.id, rating=4)

        results = fetch_feedback_with_tickets(db_session)

        assert results[0]["rating"] == 4

    def test_resolved_flag_is_correct(self, db_session):
        ticket = _make_ticket(db_session)
        _make_feedback(db_session, ticket_id=ticket.id, resolved=False)

        results = fetch_feedback_with_tickets(db_session)

        assert results[0]["resolved"] is False


# ---------------------------------------------------------------------------
# run_feedback_analyzer integration
# ---------------------------------------------------------------------------

class TestRunFeedbackAnalyzer:

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

    def test_returns_dict(self, monkeypatch, tmp_path, isolated_session_factory):
        _engine, TestSession = isolated_session_factory
        import workers.feedback_analyzer as wfa
        monkeypatch.setattr(wfa, "SessionLocal", TestSession)
        monkeypatch.setattr(wfa, "init_db", lambda: None)

        out = tmp_path / "fa.json"
        result = run_feedback_analyzer(output_path=out)

        assert isinstance(result, dict)
        assert "total_feedback" in result
        assert out.exists()

    def test_output_file_is_valid_json(self, monkeypatch, tmp_path, isolated_session_factory):
        _engine, TestSession = isolated_session_factory
        import workers.feedback_analyzer as wfa
        monkeypatch.setattr(wfa, "SessionLocal", TestSession)
        monkeypatch.setattr(wfa, "init_db", lambda: None)

        out = tmp_path / "fa.json"
        run_feedback_analyzer(output_path=out)

        loaded = json.loads(out.read_text())
        assert "total_feedback" in loaded

    def test_empty_db_returns_zeros(self, monkeypatch, tmp_path, isolated_session_factory):
        _engine, TestSession = isolated_session_factory
        import workers.feedback_analyzer as wfa
        monkeypatch.setattr(wfa, "SessionLocal", TestSession)
        monkeypatch.setattr(wfa, "init_db", lambda: None)

        result = run_feedback_analyzer(output_path=tmp_path / "fa.json")

        assert result["total_feedback"] == 0
        assert result["average_rating"] == 0.0


# ---------------------------------------------------------------------------
# CLI arg parsing
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_default_output(self):
        args = _parse_args([])
        assert "feedback_analysis" in str(args.output)

    def test_custom_output(self, tmp_path):
        custom = str(tmp_path / "out.json")
        args = _parse_args(["--output", custom])
        assert str(args.output) == custom


def test_analyze_feedback_includes_quality_score_in_output():
    """Test that analyze_feedback includes quality score in output."""
    from workers.feedback_analyzer import analyze_feedback
    
    # Create records list with _make_record() calls, adding quality_score key to each
    records = [
        _make_record(rating=5, resolved=True) | {"quality_score": 0.9},
        _make_record(rating=3, resolved=False) | {"quality_score": 0.5}
    ]
    
    # Call analyze_feedback(records)
    result = analyze_feedback(records)
    
    # Assert "average_quality_score" is in the result
    assert "average_quality_score" in result
    assert result["average_quality_score"] == 0.7  # (0.9 + 0.5) / 2
    
    # Assert result["by_intent"]["login_issue"]["average_quality_score"] is not None
    assert "by_intent" in result
    assert "login_issue" in result["by_intent"]
    assert "average_quality_score" in result["by_intent"]["login_issue"]
    assert result["by_intent"]["login_issue"]["average_quality_score"] == 0.7


def test_fetch_feedback_includes_quality_score(db_session):
    """Test that fetch_feedback_with_tickets includes quality_score in results."""
    from workers.feedback_analyzer import fetch_feedback_with_tickets
    
    # Create a ticket with a quality_score set (e.g., 0.8)
    from app.models.ticket import Ticket
    from app.models.feedback import Feedback
    
    ticket = Ticket(
        message="Test message",
        status="auto_resolved",
        intent="login_issue",
        confidence=0.9,
        response="Test response",
        quality_score=0.8
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    
    # Create feedback for that ticket
    feedback = Feedback(
        ticket_id=ticket.id,
        rating=4,
        resolved=True
    )
    db_session.add(feedback)
    db_session.commit()
    db_session.refresh(feedback)
    
    # Call fetch_feedback_with_tickets(db_session)
    result = fetch_feedback_with_tickets(db_session)
    
    # Assert "quality_score" is in the first result
    assert len(result) == 1
    assert "quality_score" in result[0]
    
    # Assert result[0]["quality_score"] == 0.8
    assert result[0]["quality_score"] == 0.8
