"""
tests/services/test_sentiment_ai.py

Tests for the LLM-based sentiment analysis path added in
app/services/ai_service.py, and for its wiring into the actual ticket
pipeline in app/services/ticket_service.py (Issue #2 — "Sentiment
Analysis Is Fake" / never wired into the pipeline).
"""
from unittest.mock import patch, MagicMock

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import get_db, Base
from app.services.ai_service import SentimentAnalysisService, _call_openai_sentiment


# -----------------------------------------------------------------------
# Local fixtures mirroring tests/services/test_automation_integration.py
# (not in a shared conftest, so duplicated here for isolation).
# -----------------------------------------------------------------------

@pytest.fixture(scope="session")
def temp_db_file():
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    yield temp_db.name
    try:
        os.unlink(temp_db.name)
    except (OSError, PermissionError):
        pass


@pytest.fixture(scope="function")
def integration_engine(temp_db_file):
    engine = create_engine(f"sqlite:///{temp_db_file}", connect_args={"check_same_thread": False})
    yield engine


@pytest.fixture(scope="function")
def integration_db_session(integration_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)
    Base.metadata.create_all(bind=integration_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=integration_engine)


@pytest.fixture(scope="function")
def client(integration_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestCallOpenAISentiment:
    """Lower-level tests for _call_openai_sentiment's validation/parsing,
    using a mocked OpenAI client (not a live network call)."""

    def _make_mock_client(self, content: str):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_returns_none_when_sdk_not_installed(self):
        with patch('app.services.ai_service.OpenAI', None):
            assert _call_openai_sentiment("test message") is None

    def test_returns_none_when_provider_not_openai(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "spacy"
            mock_settings.OPENAI_API_KEY = "test-key"
            assert _call_openai_sentiment("test message") is None

    def test_returns_none_when_no_api_key(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None
            assert _call_openai_sentiment("test message") is None

    def test_negative_sentiment_sets_escalate_true(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client('{"sentiment": "negative", "confidence": 0.93}')
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("This is absolutely unacceptable")

            assert result == {"sentiment": "negative", "confidence": 0.93, "escalate": True}

    def test_positive_sentiment_sets_escalate_false(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client('{"sentiment": "positive", "confidence": 0.8}')
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("Thanks so much, you're great!")

            assert result["sentiment"] == "positive"
            assert result["escalate"] is False

    def test_neutral_sentiment_sets_escalate_false(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client('{"sentiment": "neutral", "confidence": 0.6}')
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("What is your refund policy?")

            assert result["sentiment"] == "neutral"
            assert result["escalate"] is False

    def test_disallowed_sentiment_value_returns_none(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client('{"sentiment": "furious", "confidence": 0.9}')
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("test")

            assert result is None

    def test_malformed_json_returns_none(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client("definitely not json")
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("test")

            assert result is None

    def test_confidence_is_clamped_to_valid_range(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client('{"sentiment": "negative", "confidence": -0.5}')
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("test")

            assert result["confidence"] == 0.0

    def test_network_exception_returns_none(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = TimeoutError("timed out")
            with patch('app.services.ai_service.OpenAI', return_value=mock_client):
                result = _call_openai_sentiment("test")

            assert result is None


class TestSentimentAnalysisServiceFallback:
    """When the LLM is unavailable, SentimentAnalysisService.analyze_sentiment
    must fall back to the original deterministic keyword heuristic — same
    behavior as before this feature existed."""

    def setup_method(self):
        self.service = SentimentAnalysisService()

    def test_falls_back_to_keyword_heuristic_negative(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None

            outcome = self.service.analyze_sentiment("I am so angry and frustrated")
            data = outcome["data"]

            assert data["sentiment"] == "negative"
            assert data["escalate"] is True
            assert outcome["fallback_used"] is False  # heuristic succeeded, no exception

    def test_falls_back_to_keyword_heuristic_positive(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None

            outcome = self.service.analyze_sentiment("This is great, I love it")
            data = outcome["data"]

            assert data["sentiment"] == "positive"
            assert data["escalate"] is False

    def test_falls_back_to_keyword_heuristic_neutral(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None

            outcome = self.service.analyze_sentiment("What time does support open")
            data = outcome["data"]

            assert data["sentiment"] == "neutral"
            assert data["escalate"] is False

    def test_llm_result_is_used_when_available(self):
        with patch('app.services.ai_service.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('app.services.ai_service._call_openai_sentiment') as mock_call:
                mock_call.return_value = {"sentiment": "negative", "confidence": 0.97, "escalate": True}

                outcome = self.service.analyze_sentiment("anything")
                data = outcome["data"]

                assert data["sentiment"] == "negative"
                assert data["confidence"] == 0.97
                assert data["escalate"] is True


class TestTicketPipelineSentimentOverride:
    """Integration-style tests for the sentiment-driven escalation override
    in app/services/ticket_service.py:run_ticket_automation."""

    def test_negative_sentiment_overrides_high_confidence_auto_resolve(self, client, integration_db_session):
        with patch('app.services.classifier.classify_intent') as mock_classify, \
             patch('app.services.ai_service._call_openai_sentiment') as mock_sentiment:
            mock_classify.return_value = {"intent": "login_issue", "confidence": 0.95}
            mock_sentiment.return_value = {"sentiment": "negative", "confidence": 0.9, "escalate": True}

            response = client.post("/tickets/", json={"message": "I cannot login and I am furious about it"})

            assert response.status_code == 201
            data = response.json()
            # Intent confidence alone (0.95) is well above the auto-resolve
            # threshold, but negative sentiment must force escalation anyway.
            assert data["status"] == "escalated"
            assert data["sentiment"] == "negative"

    def test_neutral_sentiment_does_not_block_auto_resolve(self, client, integration_db_session):
        with patch('app.services.classifier.classify_intent') as mock_classify, \
             patch('app.services.ai_service._call_openai_sentiment') as mock_sentiment:
            mock_classify.return_value = {"intent": "login_issue", "confidence": 0.95}
            mock_sentiment.return_value = {"sentiment": "neutral", "confidence": 0.7, "escalate": False}

            response = client.post("/tickets/", json={"message": "I forgot my password, please help"})

            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "auto_resolved"
            assert data["sentiment"] == "neutral"

    def test_sentiment_fields_are_persisted_on_ticket(self, client, integration_db_session):
        response = client.post("/tickets/", json={"message": "I am extremely angry, this is terrible"})

        assert response.status_code == 201
        data = response.json()
        assert data["sentiment"] in ("negative", "neutral", "positive")
        assert isinstance(data["sentiment_confidence"], float)

    def test_sentiment_analysis_failure_does_not_block_ticket_creation(self, client, integration_db_session):
        with patch(
            'app.services.ticket_service._sentiment_service.analyze_sentiment',
            side_effect=Exception("sentiment service exploded"),
        ):
            response = client.post("/tickets/", json={"message": "Test message during sentiment outage"})

            # Ticket creation must succeed regardless — sentiment analysis
            # failure must never block the user-facing flow.
            assert response.status_code == 201
            data = response.json()
            assert data["sentiment"] is None
            assert data["sentiment_confidence"] is None
