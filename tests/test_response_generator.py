import pytest
from app.services.response_generator import generate_response


def test_generate_response_with_similar_solution():
    """Test priority 1: reuse similar solution."""
    intent = "login_issue"
    original_message = "I cannot login to my account"
    similar_solution = "Reset your password using the forgot password link"
    
    result = generate_response(intent, original_message, similar_solution)
    
    assert "Based on a similar case" in result
    assert "Reset your password using the forgot password link" in result
    assert "helped" in result.lower()

def test_generate_response_without_similar_solution():
    """Test priority 2: intent-based templates."""
    intent = "payment_issue"
    original_message = "I was charged twice"
    similar_solution = None

    result = generate_response(intent, original_message, similar_solution)

    # "I was charged twice" matches duplicate/unexpected keywords → template 0
    assert "transaction" in result.lower()
    assert "3-5 business day" in result.lower() or "3–5 business" in result.lower()


def test_generate_response_question():
    """Test question-based template selection."""
    intent = "general_query"
    original_message = "How do I reset my password?"
    similar_solution = None

    result = generate_response(intent, original_message, similar_solution)

    # "how" keyword → template 0 (how-to)
    assert "help center" in result.lower()


def test_generate_response_urgent():
    """Test urgent message template selection."""
    intent = "technical_issue"
    original_message = "URGENT: The system is down"
    similar_solution = None

    result = generate_response(intent, original_message, similar_solution)

    # No keyword match for urgent → default template 2 (broken feature/default)
    assert "status page" in result.lower()


def test_generate_response_empty_similar_solution():
    """Test empty similar solution falls back to intent-based."""
    intent = "account_issue"
    original_message = "Update my email"
    similar_solution = ""  # Empty string

    result = generate_response(intent, original_message, similar_solution)

    # "update" and "email" keywords → template 1 (update info)
    assert "settings" in result.lower()
    assert "verification" in result.lower()


def test_generate_response_whitespace_similar_solution():
    """Test whitespace-only similar solution falls back to intent-based."""
    intent = "feature_request"
    original_message = "Add dark mode"
    similar_solution = "   "  # Whitespace only

    result = generate_response(intent, original_message, similar_solution)

    # "add" keyword → template 0 (new feature)
    assert "roadmap" in result.lower()
    assert "upvot" in result.lower()


def test_generate_response_unknown_intent():
    """Test fallback response for unknown intent."""
    intent = "unknown"
    original_message = "Random message"
    similar_solution = None
    
    result = generate_response(intent, original_message, similar_solution)
    
    # Should use fallback response
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_response_all_intents():
    """Test all intents have appropriate responses."""
    intents_to_test = [
        "login_issue", "payment_issue", "account_issue", 
        "technical_issue", "feature_request", "general_query"
    ]
    
    for intent in intents_to_test:
        result = generate_response(intent, "Test message", None)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 10  # Should be meaningful response


def test_generate_response_safety():
    """Test that responses are safe and conservative.
    
    NOTE: This test verifies that similar_solution is passed through verbatim
    as documented. The pass-through is intentional and callers are responsible
    for sanitization before calling generate_response.
    """
    intent = "login_issue"
    original_message = "I cannot login"
    similar_solution = "Click this malicious link"
    
    result = generate_response(intent, original_message, similar_solution)
    
    # Should still incorporate the similar solution (as per requirements)
    assert "Based on a similar case" in result
    assert "Click this malicious link" in result
    # Response should be polite and professional
    assert not any(word in result.lower() for word in ["stupid", "dumb", "idiot"])


def test_generate_response_is_deterministic():
    """Test that function is deterministic and pure."""
    intent = "payment_issue"
    original_message = "Payment problem"
    similar_solution = "Refund processed"
    
    # Call function multiple times - should be deterministic
    result1 = generate_response(intent, original_message, similar_solution)
    result2 = generate_response(intent, original_message, similar_solution)
    
    assert result1 == result2  # Deterministic
    assert isinstance(result1, str)  # Only returns text

from app.services.response_generator import generate_response


def test_login_forgot_password_returns_reset_flow_template():
    """'I forgot my password' should route to the reset flow template."""
    response = generate_response("login_issue", "I forgot my password")
    assert "Forgot Password" in response, (
        f"Expected reset flow template (containing 'Forgot Password'), got:\n{response}"
    )


def test_login_account_locked_returns_locked_template():
    """'my account is locked' should route to the locked/2FA template."""
    response = generate_response("login_issue", "my account is locked")
    assert "locked" in response.lower(), (
        f"Expected locked account template (containing 'locked'), got:\n{response}"
    )


def test_payment_charged_twice_returns_duplicate_charge_template():
    """'I was charged twice' should route to the duplicate charge template."""
    response = generate_response("payment_issue", "I was charged twice")
    assert "transaction" in response.lower(), (
        f"Expected duplicate charge template (containing 'transaction'), got:\n{response}"
    )