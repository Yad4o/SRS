"""
tests/services/test_classifier_ai.py

Tests for the LLM-based classification path added in app/services/classifier.py
(Issue #1 — "AI Classifier is Rule-Based, Not Real AI").

Follows the existing mocking convention used in
tests/services/test_response_generator.py: patch the module's `settings`
reference and its own `_call_openai_*` helper directly, rather than the
raw OpenAI SDK client.
"""
from unittest.mock import patch, MagicMock

from app.services.classifier import (
    classify_intent,
    classify_intent_ai,
    _call_openai_classifier,
    _detect_sub_intent,
    _normalize_text,
)


class TestClassifyIntentAIFallback:
    """When the LLM is unavailable/unconfigured, classify_intent_ai must
    behave identically to calling classify_intent() directly."""

    def test_no_api_key_falls_back_to_rule_based(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None

            result = classify_intent_ai("I forgot my password and need to reset it")
            rule_based = classify_intent("I forgot my password and need to reset it")

            assert result["intent"] == rule_based["intent"]
            assert result["confidence"] == rule_based["confidence"]
            assert result["sub_intent"] == rule_based["sub_intent"]
            assert result["source"] == "rule_based"

    def test_llm_call_failure_falls_back_to_rule_based(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('app.services.classifier._call_openai_classifier') as mock_call:
                mock_call.return_value = None  # Simulates any LLM failure

                result = classify_intent_ai("My payment was charged twice")
                rule_based = classify_intent("My payment was charged twice")

                assert result["intent"] == rule_based["intent"]
                assert result["confidence"] == rule_based["confidence"]
                assert result["source"] == "rule_based"

    def test_empty_message_never_calls_llm(self):
        with patch('app.services.classifier._call_openai_classifier') as mock_call:
            result = classify_intent_ai("")
            mock_call.assert_not_called()
            assert result["intent"] == "unknown"
            assert result["confidence"] == 0.0
            assert result["source"] == "rule_based"

    def test_none_message_never_calls_llm(self):
        with patch('app.services.classifier._call_openai_classifier') as mock_call:
            result = classify_intent_ai(None)
            mock_call.assert_not_called()
            assert result["intent"] == "unknown"

    def test_too_short_message_never_calls_llm(self):
        with patch('app.services.classifier._call_openai_classifier') as mock_call:
            result = classify_intent_ai("hi")
            mock_call.assert_not_called()
            assert result["intent"] == "unknown"


class TestClassifyIntentAILLMPath:
    """When the LLM is configured and returns a valid result, it should be
    used in preference to the rule-based classifier."""

    def test_llm_result_is_used_when_available(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('app.services.classifier._call_openai_classifier') as mock_call:
                mock_call.return_value = {"intent": "feature_request", "confidence": 0.88}

                result = classify_intent_ai("Could you please add dark mode")

                assert result["intent"] == "feature_request"
                assert result["confidence"] == 0.88
                assert result["source"] == "llm"

    def test_llm_result_still_computes_sub_intent(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('app.services.classifier._call_openai_classifier') as mock_call:
                mock_call.return_value = {"intent": "login_issue", "confidence": 0.93}

                result = classify_intent_ai("I forgot my password completely")

                assert result["intent"] == "login_issue"
                assert result["sub_intent"] == "password_reset"
                assert result["source"] == "llm"

    def test_llm_unknown_intent_has_no_sub_intent(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('app.services.classifier._call_openai_classifier') as mock_call:
                mock_call.return_value = {"intent": "unknown", "confidence": 0.4}

                result = classify_intent_ai("asdkjfh qwoeiru")

                assert result["intent"] == "unknown"
                assert result["sub_intent"] is None


class TestCallOpenAIClassifier:
    """Lower-level tests for _call_openai_classifier's own validation/parsing,
    using a mocked OpenAI client (not a live network call)."""

    def _make_mock_client(self, content: str):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=content))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_returns_none_when_sdk_not_installed(self):
        with patch('app.services.classifier.OpenAI', None):
            assert _call_openai_classifier("test message") is None

    def test_returns_none_when_provider_not_openai(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "spacy"
            mock_settings.OPENAI_API_KEY = "test-key"
            assert _call_openai_classifier("test message") is None

    def test_returns_none_when_no_api_key(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None
            assert _call_openai_classifier("test message") is None

    def test_valid_json_response_is_parsed(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client('{"intent": "payment_issue", "confidence": 0.91}')
            with patch('app.services.classifier.OpenAI', return_value=mock_client):
                result = _call_openai_classifier("I was charged twice")

            assert result == {"intent": "payment_issue", "confidence": 0.91}

    def test_disallowed_intent_returns_none(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            # Model hallucinates an intent that isn't in ALLOWED_INTENTS
            mock_client = self._make_mock_client('{"intent": "make_me_a_sandwich", "confidence": 0.9}')
            with patch('app.services.classifier.OpenAI', return_value=mock_client):
                result = _call_openai_classifier("nonsense")

            assert result is None

    def test_malformed_json_returns_none(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = self._make_mock_client("not valid json at all")
            with patch('app.services.classifier.OpenAI', return_value=mock_client):
                result = _call_openai_classifier("test")

            assert result is None

    def test_confidence_is_clamped_to_valid_range(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            # Model returns an out-of-range confidence value
            mock_client = self._make_mock_client('{"intent": "technical_issue", "confidence": 1.7}')
            with patch('app.services.classifier.OpenAI', return_value=mock_client):
                result = _call_openai_classifier("the app keeps crashing")

            assert result["confidence"] == 1.0

    def test_network_exception_returns_none(self):
        with patch('app.services.classifier.settings') as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.OPENAI_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_TIMEOUT = 8

            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = ConnectionError("network down")
            with patch('app.services.classifier.OpenAI', return_value=mock_client):
                result = _call_openai_classifier("test")

            assert result is None


class TestSubIntentHelpers:
    """The SUB_INTENT_PATTERNS extraction must behave identically to the
    inline logic classify_intent() used before the refactor."""

    def test_detect_sub_intent_matches_first_pattern(self):
        text = _normalize_text("I forgot my password please help")
        assert _detect_sub_intent("login_issue", text) == "password_reset"

    def test_detect_sub_intent_returns_none_for_no_match(self):
        text = _normalize_text("something totally unrelated to any keyword")
        assert _detect_sub_intent("login_issue", text) is None

    def test_detect_sub_intent_returns_none_for_unknown_intent(self):
        text = _normalize_text("anything at all")
        assert _detect_sub_intent("unknown", text) is None

    def test_normalize_text_matches_classify_intent_behavior(self):
        # classify_intent() and the LLM path must see identical normalized
        # text for sub-intent lookups to be consistent regardless of which
        # path determined the primary intent.
        raw = "I FORGOT my Password!!! 123"
        assert _normalize_text(raw) == "i forgot my password 123"
