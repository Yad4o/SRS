"""
Tests for workers/metrics_collector.py

Covers:
- collect_metrics: empty DB returns zeros, counts tickets by status and intent,
  auto_resolve_rate / escalation_rate calculation, feedback averages
- run_metrics_collector: end-to-end, JSON output with correct keys
- _parse_args: CLI defaults and --output override
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.feedback import Feedback
from app.models.ticket import Ticket
from workers.metrics_collector import (
    _parse_args,
    collect_metrics,
    run_metrics_collector,
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

def _add_ticket(db, status="open", intent=None, message="Test ticket") -> Ticket:
    t = Ticket(message=message, status=status, intent=intent)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _add_feedback(db, ticket_id: int, rating: int = 4, resolved: bool = True) -> Feedback:
    fb = Feedback(ticket_id=ticket_id, rating=rating, resolved=resolved)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


# ---------------------------------------------------------------------------
# collect_metrics
# ---------------------------------------------------------------------------

class TestCollectMetrics:

    def test_empty_db_returns_zeros(self, db_session):
        result = collect_metrics(db_session)

        assert result["tickets"]["total"] == 0
        assert result["tickets"]["by_status"] == {}
        assert result["tickets"]["by_intent"] == {}
        assert result["feedback"]["total"] == 0
        assert result["feedback"]["average_rating"] == 0.0
        assert result["feedback"]["resolution_rate"] == 0.0
        assert result["auto_resolve_rate"] == 0.0
        assert result["escalation_rate"] == 0.0

    def test_result_has_expected_top_level_keys(self, db_session):
        result = collect_metrics(db_session)
        for key in ("collected_at", "tickets", "feedback", "auto_resolve_rate", "escalation_rate"):
            assert key in result

    def test_collected_at_is_iso_timestamp(self, db_session):
        result = collect_metrics(db_session)
        # Should parse without error
        dt = datetime.fromisoformat(result["collected_at"])
        assert dt.tzinfo is not None  # timezone-aware

    def test_ticket_total_count(self, db_session):
        for _ in range(3):
            _add_ticket(db_session)

        result = collect_metrics(db_session)

        assert result["tickets"]["total"] == 3

    def test_tickets_by_status(self, db_session):
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="escalated")

        result = collect_metrics(db_session)
        by_status = result["tickets"]["by_status"]

        assert by_status["auto_resolved"] == 3
        assert by_status["escalated"] == 1

    def test_tickets_by_intent(self, db_session):
        _add_ticket(db_session, intent="login_issue")
        _add_ticket(db_session, intent="login_issue")
        _add_ticket(db_session, intent="payment_issue")
        _add_ticket(db_session, intent=None)  # should not appear

        result = collect_metrics(db_session)
        by_intent = result["tickets"]["by_intent"]

        assert by_intent["login_issue"] == 2
        assert by_intent["payment_issue"] == 1
        assert None not in by_intent

    def test_auto_resolve_rate(self, db_session):
        # 2 auto_resolved, 1 escalated, 1 closed → decided = 4, auto_resolve = 2/4 = 0.5
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="escalated")
        _add_ticket(db_session, status="closed")

        result = collect_metrics(db_session)

        assert abs(result["auto_resolve_rate"] - 0.5) < 1e-6

    def test_escalation_rate(self, db_session):
        # 1 escalated, 3 auto_resolved → escalation rate = 1/4 = 0.25
        _add_ticket(db_session, status="escalated")
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="auto_resolved")

        result = collect_metrics(db_session)

        assert abs(result["escalation_rate"] - 0.25) < 1e-6

    def test_auto_resolve_rate_zero_when_no_decided_tickets(self, db_session):
        _add_ticket(db_session, status="open")

        result = collect_metrics(db_session)

        assert result["auto_resolve_rate"] == 0.0
        assert result["escalation_rate"] == 0.0

    def test_rates_sum_to_one_when_only_two_statuses(self, db_session):
        """auto_resolve_rate + escalation_rate ≤ 1."""
        _add_ticket(db_session, status="auto_resolved")
        _add_ticket(db_session, status="escalated")

        result = collect_metrics(db_session)
        total = result["auto_resolve_rate"] + result["escalation_rate"]
        assert abs(total - 1.0) < 1e-6

    def test_feedback_total_count(self, db_session):
        for _ in range(4):
            t = _add_ticket(db_session)
            _add_feedback(db_session, t.id)

        result = collect_metrics(db_session)

        assert result["feedback"]["total"] == 4

    def test_feedback_average_rating(self, db_session):
        t1 = _add_ticket(db_session)
        t2 = _add_ticket(db_session)
        _add_feedback(db_session, t1.id, rating=4)
        _add_feedback(db_session, t2.id, rating=2)

        result = collect_metrics(db_session)

        assert abs(result["feedback"]["average_rating"] - 3.0) < 1e-6

    def test_feedback_resolution_rate_all_resolved(self, db_session):
        for _ in range(3):
            t = _add_ticket(db_session)
            _add_feedback(db_session, t.id, resolved=True)

        result = collect_metrics(db_session)

        assert result["feedback"]["resolution_rate"] == 1.0

    def test_feedback_resolution_rate_none_resolved(self, db_session):
        t = _add_ticket(db_session)
        _add_feedback(db_session, t.id, resolved=False)

        result = collect_metrics(db_session)

        assert result["feedback"]["resolution_rate"] == 0.0

    def test_feedback_resolution_rate_partial(self, db_session):
        t1 = _add_ticket(db_session)
        t2 = _add_ticket(db_session)
        _add_feedback(db_session, t1.id, resolved=True)
        _add_feedback(db_session, t2.id, resolved=False)

        result = collect_metrics(db_session)

        assert abs(result["feedback"]["resolution_rate"] - 0.5) < 1e-6

    def test_tickets_sub_dict_has_correct_keys(self, db_session):
        result = collect_metrics(db_session)
        assert "total" in result["tickets"]
        assert "by_status" in result["tickets"]
        assert "by_intent" in result["tickets"]

    def test_feedback_sub_dict_has_correct_keys(self, db_session):
        result = collect_metrics(db_session)
        assert "total" in result["feedback"]
        assert "average_rating" in result["feedback"]
        assert "resolution_rate" in result["feedback"]


# ---------------------------------------------------------------------------
# run_metrics_collector integration
# ---------------------------------------------------------------------------

class TestRunMetricsCollector:

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
        import workers.metrics_collector as wmc
        monkeypatch.setattr(wmc, "SessionLocal", TestSession)
        monkeypatch.setattr(wmc, "init_db", lambda: None)

        out = tmp_path / "metrics.json"
        result = run_metrics_collector(output_path=out)

        assert isinstance(result, dict)
        assert "tickets" in result
        assert out.exists()

    def test_output_file_is_valid_json(self, monkeypatch, tmp_path, isolated_session_factory):
        _engine, TestSession = isolated_session_factory
        import workers.metrics_collector as wmc
        monkeypatch.setattr(wmc, "SessionLocal", TestSession)
        monkeypatch.setattr(wmc, "init_db", lambda: None)

        out = tmp_path / "metrics.json"
        run_metrics_collector(output_path=out)

        loaded = json.loads(out.read_text())
        assert "collected_at" in loaded
        assert "tickets" in loaded
        assert "feedback" in loaded

    def test_empty_db_zero_totals(self, monkeypatch, tmp_path, isolated_session_factory):
        _engine, TestSession = isolated_session_factory
        import workers.metrics_collector as wmc
        monkeypatch.setattr(wmc, "SessionLocal", TestSession)
        monkeypatch.setattr(wmc, "init_db", lambda: None)

        result = run_metrics_collector(output_path=tmp_path / "metrics.json")

        assert result["tickets"]["total"] == 0
        assert result["feedback"]["total"] == 0


# ---------------------------------------------------------------------------
# CLI arg parsing
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_default_output(self):
        args = _parse_args([])
        assert "metrics" in str(args.output)

    def test_custom_output(self, tmp_path):
        custom = str(tmp_path / "custom.json")
        args = _parse_args(["--output", custom])
        assert str(args.output) == custom
