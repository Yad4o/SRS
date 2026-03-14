import pytest
import warnings
from app.services.classifier import classify_intent
from app.services.intent_classifier import classify_intent as new_classify_intent


def test_legacy_classifier_delegates_to_new_implementation():
    """Test that legacy classifier delegates to new implementation with deprecation warning."""
    message = "I cannot login to my account"
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")  # Capture all warnings
        
        # Call legacy function
        legacy_result = classify_intent(message)
        
        # Call new function directly
        new_result = new_classify_intent(message)
        
        # Should have raised a deprecation warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert "intent_classifier" in str(w[0].message)
        
        # Results should be identical
        assert legacy_result == new_result


def test_legacy_classifier_login_issue():
    result = classify_intent("I cannot login to my account")
    assert result["intent"] == "login_issue"
    assert result["confidence"] > 0.0


def test_legacy_classifier_payment_issue():
    result = classify_intent("My payment was debited twice")
    assert result["intent"] == "payment_issue"
    assert result["confidence"] > 0.0


def test_legacy_classifier_account_issue():
    result = classify_intent("Please delete my account")
    assert result["intent"] == "account_issue"
    assert result["confidence"] > 0.0


def test_legacy_classifier_technical_issue():
    result = classify_intent("The app is crashing with an error")
    assert result["intent"] == "technical_issue"
    assert result["confidence"] > 0.0


def test_legacy_classifier_feature_request():
    result = classify_intent("Please add a dark mode feature")
    assert result["intent"] == "feature_request"
    assert result["confidence"] > 0.0


def test_legacy_classifier_general_query():
    result = classify_intent("How can I use this app?")
    assert result["intent"] == "general_query"
    assert result["confidence"] > 0.0


def test_legacy_classifier_unknown_intent():
    result = classify_intent("blabla xyz random text")
    assert result["intent"] == "unknown"
    assert result["confidence"] >= 0.0


def test_legacy_classifier_empty_string():
    result = classify_intent("")
    assert result["intent"] == "unknown"
    assert result["confidence"] == 0.0


def test_legacy_classifier_none_input():
    result = classify_intent(None)
    assert result["intent"] == "unknown"
    assert result["confidence"] == 0.0


def test_legacy_classifier_special_characters_cleanup():
    result = classify_intent("!!! LOGIN??? ###")
    assert result["intent"] == "login_issue"
    assert result["confidence"] > 0.0
