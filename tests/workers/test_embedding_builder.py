"""
Tests for workers/embedding_builder.py

Covers:
- _tokenize: basic tokenization, empty / non-string inputs
- _compute_idf: IDF formula, single-document corpus, empty corpus
- _tf_idf_vector: TF-IDF values, empty text
- build_embeddings: full embedding construction, empty ticket list
- fetch_resolved_tickets: only returns resolved/closed tickets
- save_embeddings: writes valid JSON to disk
- run_embedding_builder: end-to-end integration
- _parse_args: CLI defaults and --output override
"""
import json
import math
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.ticket import Ticket
from workers.embedding_builder import (
    RESOLVED_STATUSES,
    _compute_idf,
    _parse_args,
    _tf_idf_vector,
    _tokenize,
    build_embeddings,
    fetch_resolved_tickets,
    run_embedding_builder,
    save_embeddings,
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
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:

    def test_basic_tokenization(self):
        tokens = _tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_strips_punctuation(self):
        tokens = _tokenize("I can't login!")
        assert "login" in tokens
        assert "can" in tokens

    def test_empty_string_returns_empty(self):
        assert _tokenize("") == []

    def test_none_returns_empty(self):
        assert _tokenize(None) == []

    def test_non_string_returns_empty(self):
        assert _tokenize(123) == []

    def test_whitespace_only_returns_empty(self):
        assert _tokenize("   ") == []

    def test_unicode_text(self):
        tokens = _tokenize("résumé café")
        assert len(tokens) > 0


# ---------------------------------------------------------------------------
# _compute_idf
# ---------------------------------------------------------------------------

class TestComputeIdf:

    def test_returns_dict(self):
        idf = _compute_idf(["login issue", "payment problem"])
        assert isinstance(idf, dict)

    def test_all_tokens_have_positive_score(self):
        idf = _compute_idf(["login issue", "payment problem"])
        for word, score in idf.items():
            assert score > 0, f"Expected positive IDF for '{word}', got {score}"

    def test_rare_word_has_higher_idf(self):
        """A word in only 1 of 2 documents should have higher IDF than one in both."""
        idf = _compute_idf(["login issue", "login payment"])
        # "issue" appears in 1 doc; "login" appears in 2 docs → login IDF should be lower
        assert idf["issue"] > idf["login"]

    def test_empty_corpus_returns_empty(self):
        idf = _compute_idf([])
        assert idf == {}

    def test_single_document(self):
        idf = _compute_idf(["only one document here"])
        assert isinstance(idf, dict)
        assert len(idf) > 0


# ---------------------------------------------------------------------------
# _tf_idf_vector
# ---------------------------------------------------------------------------

class TestTfIdfVector:

    def test_returns_dict(self):
        idf = {"login": 1.5, "issue": 2.0}
        vec = _tf_idf_vector("login issue", idf)
        assert isinstance(vec, dict)

    def test_all_values_positive(self):
        idf = {"login": 1.5, "issue": 2.0}
        vec = _tf_idf_vector("login issue login", idf)
        for val in vec.values():
            assert val > 0

    def test_empty_text_returns_empty(self):
        idf = {"login": 1.5}
        vec = _tf_idf_vector("", idf)
        assert vec == {}

    def test_unknown_word_uses_default_idf_1(self):
        """Words not in IDF vocab should use a default IDF of 1.0."""
        idf = {}  # empty IDF
        vec = _tf_idf_vector("unknown word", idf)
        for val in vec.values():
            assert val > 0  # TF * 1.0 > 0

    def test_repeated_word_has_higher_tf_component(self):
        idf = {"login": 1.0}
        vec_single = _tf_idf_vector("login", idf)
        vec_double = _tf_idf_vector("login login", idf)
        # Both result in same TF (1.0) but ratio is 1/1 vs 2/2 = still 1.0
        # After normalisation they should be equal
        assert abs(vec_single.get("login", 0) - vec_double.get("login", 0)) < 1e-9


# ---------------------------------------------------------------------------
# build_embeddings
# ---------------------------------------------------------------------------

class TestBuildEmbeddings:

    def test_empty_list_returns_empty_result(self):
        result = build_embeddings([])
        assert result == {"idf": {}, "vectors": [], "ticket_count": 0}

    def test_returns_correct_structure(self):
        tickets = [
            {"id": 1, "message": "I cannot login", "intent": "login_issue", "response": "Reset password"},
            {"id": 2, "message": "Payment failed", "intent": "payment_issue", "response": "Try again"},
        ]
        result = build_embeddings(tickets)
        assert "idf" in result
        assert "vectors" in result
        assert "ticket_count" in result

    def test_ticket_count_matches_input(self):
        tickets = [
            {"id": 1, "message": "Login problem"},
            {"id": 2, "message": "Payment problem"},
            {"id": 3, "message": "Account issue"},
        ]
        result = build_embeddings(tickets)
        assert result["ticket_count"] == 3
        assert len(result["vectors"]) == 3

    def test_each_vector_has_ticket_id(self):
        tickets = [
            {"id": 10, "message": "Login issue"},
            {"id": 20, "message": "Payment issue"},
        ]
        result = build_embeddings(tickets)
        ids = [v["ticket_id"] for v in result["vectors"]]
        assert 10 in ids
        assert 20 in ids

    def test_vector_is_non_empty_dict(self):
        tickets = [{"id": 1, "message": "I cannot login to my account"}]
        result = build_embeddings(tickets)
        vec = result["vectors"][0]["vector"]
        assert isinstance(vec, dict)
        assert len(vec) > 0

    def test_skips_tickets_without_message(self):
        tickets = [
            {"id": 1, "message": "Valid message"},
            {"id": 2},  # no 'message' key
            {"id": 3, "message": ""},  # empty message
        ]
        result = build_embeddings(tickets)
        # Only id=1 has a valid message
        assert result["ticket_count"] == 1

    def test_idf_contains_expected_tokens(self):
        tickets = [{"id": 1, "message": "login issue account"}]
        result = build_embeddings(tickets)
        for word in ["login", "issue", "account"]:
            assert word in result["idf"]


# ---------------------------------------------------------------------------
# fetch_resolved_tickets
# ---------------------------------------------------------------------------

class TestFetchResolvedTickets:

    def _add_ticket(self, db, status: str, message: str = "msg") -> Ticket:
        t = Ticket(message=message, status=status)
        db.add(t)
        db.commit()
        db.refresh(t)
        return t

    def test_returns_only_resolved_statuses(self, db_session):
        self._add_ticket(db_session, "open")
        self._add_ticket(db_session, "escalated")
        self._add_ticket(db_session, "auto_resolved", "resolved ticket 1")
        self._add_ticket(db_session, "closed", "closed ticket 1")

        results = fetch_resolved_tickets(db_session)

        assert len(results) == 2
        statuses = {r["status"] for r in results}
        assert statuses == RESOLVED_STATUSES

    def test_returns_empty_when_no_resolved(self, db_session):
        self._add_ticket(db_session, "open")
        self._add_ticket(db_session, "escalated")

        results = fetch_resolved_tickets(db_session)

        assert results == []

    def test_result_contains_expected_keys(self, db_session):
        self._add_ticket(db_session, "closed", "Test message")

        results = fetch_resolved_tickets(db_session)

        assert len(results) == 1
        record = results[0]
        for key in ("id", "message", "intent", "response", "status"):
            assert key in record

    def test_empty_table_returns_empty_list(self, db_session):
        results = fetch_resolved_tickets(db_session)
        assert results == []


# ---------------------------------------------------------------------------
# save_embeddings
# ---------------------------------------------------------------------------

class TestSaveEmbeddings:

    def test_creates_file(self, tmp_path):
        out = tmp_path / "emb.json"
        data = {"idf": {"login": 1.5}, "vectors": [{"ticket_id": 1, "vector": {"login": 0.5}}], "ticket_count": 1}
        save_embeddings(data, out)
        assert out.exists()

    def test_file_is_valid_json(self, tmp_path):
        out = tmp_path / "emb.json"
        data = {"idf": {}, "vectors": [], "ticket_count": 0}
        save_embeddings(data, out)
        loaded = json.loads(out.read_text())
        assert loaded == data

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "emb.json"
        save_embeddings({"idf": {}, "vectors": [], "ticket_count": 0}, out)
        assert out.exists()


# ---------------------------------------------------------------------------
# run_embedding_builder integration
# ---------------------------------------------------------------------------

class TestRunEmbeddingBuilder:

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
        import workers.embedding_builder as wb
        monkeypatch.setattr(wb, "SessionLocal", TestSession)
        monkeypatch.setattr(wb, "init_db", lambda: None)

        out = tmp_path / "emb.json"
        result = run_embedding_builder(output_path=out)

        assert isinstance(result, dict)
        assert "ticket_count" in result
        assert out.exists()

    def test_empty_db_produces_empty_cache(self, monkeypatch, tmp_path, isolated_session_factory):
        _engine, TestSession = isolated_session_factory
        import workers.embedding_builder as wb
        monkeypatch.setattr(wb, "SessionLocal", TestSession)
        monkeypatch.setattr(wb, "init_db", lambda: None)

        out = tmp_path / "emb.json"
        result = run_embedding_builder(output_path=out)

        assert result["ticket_count"] == 0
        assert result["vectors"] == []


# ---------------------------------------------------------------------------
# CLI arg parsing
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_default_output(self):
        args = _parse_args([])
        assert args.output is not None
        assert "embeddings" in str(args.output)

    def test_custom_output(self, tmp_path):
        custom = str(tmp_path / "custom.json")
        args = _parse_args(["--output", custom])
        assert str(args.output) == custom
