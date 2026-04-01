"""
Unit tests explicitly importing the internal `generate_response` function to isolate its 
generation logic from the overall ticket pipeline, deliberately bypassing the 'DO NOT use directly' 
module header instruction to test logic in isolation.
"""
from app.services.response_generator import generate_response


def test_resolver_returns_string():
    """
    Response generator must always return a tuple (response_text, source_label).
    """
    response = generate_response(
        intent="login_issue",
        original_message="Cannot login"
    )
    assert isinstance(response, tuple)
    assert len(response) == 2
    response_text, source_label = response
    assert isinstance(response_text, str)
    assert isinstance(source_label, str)


def test_resolver_uses_similar_solution():
    """
    If similar solution exists, reuse it with polite wrapper.
    """
    response = generate_response(
        intent="login_issue",
        original_message="Cannot login",
        similar_solution="Reset your password"
    )
    response_text, source_label = response
    assert "I understand you're experiencing an issue" in response_text
    assert "Based on a similar case" in response_text
    assert "Reset your password" in response_text
    assert source_label == "similarity"


def test_resolver_fallback_response():
    """
    Unknown intent should return safe fallback with source label "fallback".
    """
    response = generate_response(
        intent="unknown",
        original_message="Something wrong"
    )
    response_text, source_label = response
    assert isinstance(response_text, str)
    assert isinstance(source_label, str)
    assert len(response_text) > 0
    # Unknown intents must use "fallback" source, not "template"
    assert source_label == "fallback"
