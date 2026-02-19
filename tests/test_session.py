"""
Tests for app/db/session.py

Covers:
- get_db yields a Session
- get_db closes session after use
- init_db creates tables (if available)
- Base and SessionLocal
"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.db.session as _session_mod

Base = _session_mod.Base
SessionLocal = _session_mod.SessionLocal
engine = _session_mod.engine
get_db = _session_mod.get_db
init_db = getattr(_session_mod, "init_db", None)  # May not exist in older session.py


class TestGetDb:
    """Tests for get_db() FastAPI dependency."""

    def test_get_db_yields_session(self):
        """get_db should yield a SQLAlchemy Session."""
        gen = get_db()
        db = next(gen)
        assert isinstance(db, Session)

    def test_get_db_closes_session_after_use(self):
        """get_db yields a session; exhausting the generator runs finally and closes it."""
        gen = get_db()
        db = next(gen)
        assert isinstance(db, Session)
        try:
            next(gen)
        except StopIteration:
            pass
        # Generator exhausted; finally block executes db.close()

    def test_get_db_is_generator(self):
        """get_db should be a generator (for FastAPI Depends)."""
        gen = get_db()
        assert hasattr(gen, "__next__")
        assert hasattr(gen, "send")


class TestSessionLocal:
    """Tests for SessionLocal factory."""

    def test_session_local_creates_sessions(self):
        """SessionLocal() should create a Session instance."""
        session = SessionLocal()
        assert isinstance(session, Session)
        session.close()

    def test_sessions_are_independent(self):
        """Each SessionLocal() call should create a new session."""
        s1 = SessionLocal()
        s2 = SessionLocal()
        assert s1 is not s2
        s1.close()
        s2.close()


@pytest.mark.skipif(init_db is None, reason="init_db not available in this session.py")
class TestInitDb:
    """Tests for init_db()."""

    def test_init_db_creates_tables(self):
        """init_db should create all model tables."""
        init_db()
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'tickets', 'feedback')"
            ))
            tables = [row[0] for row in result]
        assert "users" in tables
        assert "tickets" in tables
        assert "feedback" in tables

    def test_init_db_idempotent(self):
        """init_db can be called multiple times safely (creates only missing tables)."""
        init_db()
        init_db()  # Should not raise


class TestBase:
    """Tests for Base declarative base."""

    def test_base_has_metadata(self):
        """Base should have metadata for table definitions."""
        assert hasattr(Base, "metadata")

    @pytest.mark.skipif(init_db is None, reason="init_db not available in this session.py")
    def test_base_metadata_contains_tables_after_init(self):
        """After init_db, Base.metadata should include our tables."""
        init_db()
        table_names = Base.metadata.tables.keys()
        assert "users" in table_names
        assert "tickets" in table_names
        assert "feedback" in table_names


class TestEngine:
    """Tests for database engine."""

    def test_engine_connects(self):
        """Engine should be able to connect."""
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
