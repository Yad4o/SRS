import pytest
from app.services.classifier import classify_intent


def test_login_issue():
    result = classify_intent("I cannot login to my account")
    assert result["intent"] == "login_issue"
    assert result["confidence"] == 0.8


def test_payment_issue():
    result = classify_intent("My payment was debited twice")
    assert result["intent"] == "payment_issue"
    assert result["confidence"] == 0.8


def test_account_issue():
    result = classify_intent("Please delete my account")
    assert result["intent"] == "account_issue"
    assert result["confidence"] == 0.8


def test_technical_issue():
    result = classify_intent("The app is crashing with an error")
    assert result["intent"] == "technical_issue"
    assert result["confidence"] == 0.8


def test_feature_request():
    result = classify_intent("Please add a dark mode feature")
    assert result["intent"] == "feature_request"
    assert result["confidence"] == 0.8


def test_general_query():
    result = classify_intent("How can I use this app?")
    assert result["intent"] == "general_query"
    assert result["confidence"] == 0.8


def test_unknown_intent():
    result = classify_intent("blabla xyz random text")
    assert result["intent"] == "unknown"
    assert result["confidence"] == 0.3


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
    assert result["confidence"] == 0.8
