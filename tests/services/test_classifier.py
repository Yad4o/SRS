import pytest
from app.services.classifier import classify_intent


def test_login_issue():
    result = classify_intent("I cannot login to my account")
    assert result["intent"] == "login_issue"
    assert 0.8 <= result["confidence"] <= 1.0


def test_payment_issue():
    result = classify_intent("My payment was debited twice")
    assert result["intent"] == "payment_issue"
    assert 0.8 <= result["confidence"] <= 1.0


def test_account_issue():
    result = classify_intent("Please delete my account")
    assert result["intent"] == "account_issue"
    assert 0.7 <= result["confidence"] <= 1.0


def test_technical_issue():
    result = classify_intent("The app is crashing with an error")
    assert result["intent"] == "technical_issue"
    assert 0.7 <= result["confidence"] <= 1.0


def test_feature_request():
    result = classify_intent("Please add a dark mode feature")
    assert result["intent"] == "feature_request"
    assert 0.7 <= result["confidence"] <= 1.0


def test_general_query():
    result = classify_intent("How can I use this app?")
    assert result["intent"] == "general_query"
    assert 0.6 <= result["confidence"] <= 1.0


def test_unknown_intent():
    result = classify_intent("blabla xyz random text")
    assert result["intent"] == "unknown"
    assert 0.0 <= result["confidence"] <= 0.3


def test_empty_string():
    result = classify_intent("")
    assert result["intent"] == "unknown"
    assert result["confidence"] == 0.0


def test_none_input():
    result = classify_intent(None)
    assert result["intent"] == "unknown"
    assert result["confidence"] == 0.0


def test_special_characters_cleanup():
    result = classify_intent("!!! LOGIN??? ###")
    assert result["intent"] == "login_issue"
    assert 0.8 <= result["confidence"] <= 1.0


# Edge-case tests for improved coverage
def test_overlapping_keywords():
    """Test overlapping keywords between account_issue and login_issue."""
    result = classify_intent("I have an account login issue")
    # Should prioritize login_issue due to priority order when scores are equal
    assert result["intent"] == "login_issue"
    assert 0.8 <= result["confidence"] <= 1.0


def test_long_message_confidence_boost():
    """Test confidence boost for messages longer than 50 characters."""
    long_message = "I am experiencing a very serious technical issue with the application that is causing it to crash repeatedly"
    result = classify_intent(long_message)
    assert result["intent"] == "technical_issue"
    assert 0.75 <= result["confidence"] <= 1.0  # Should get length boost


def test_explain_billing_query():
    """Test billing-related phrasing to ensure proper intent classification."""
    # Informational billing query should go to general_query
    result = classify_intent("explain billing")
    assert result["intent"] == "general_query"
    assert 0.8 <= result["confidence"] <= 1.0
    
    # Action-oriented billing query should go to payment_issue
    result2 = classify_intent("explain billing charge failed")
    assert result2["intent"] == "payment_issue"
    assert 0.8 <= result2["confidence"] <= 1.0


def test_pattern_only_matching():
    """Test pattern-only matching for general_query without keyword overlap."""
    result = classify_intent("how do I contact support")
    assert result["intent"] == "general_query"
    assert 0.7 <= result["confidence"] <= 1.0


def test_classifier_sub_intent_reset():
    """Verify 'forgot my password' -> sub_intent == 'password_reset'."""
    result = classify_intent("forgot my password")
    assert result["intent"] == "login_issue"
    assert result["sub_intent"] == "password_reset"
