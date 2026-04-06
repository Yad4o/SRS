import pytest
from app.services.similarity_search import find_similar_ticket


def test_find_similar_ticket_exact_match():
    """Test exact match returns high similarity."""
    new_message = "I cannot login to my account"
    resolved_tickets = [
        {"message": "I cannot login to my account", "response": "Reset your password"},
        {"message": "Payment was charged twice", "response": "Refund processed"}
    ]
    
    result = find_similar_ticket(new_message, resolved_tickets)
    
    assert result is not None
    assert result["matched_text"] == "I cannot login to my account"
    assert result["similarity_score"] >= 0.9
    assert result["ticket"]["response"] == "Reset your password"


def test_find_similar_ticket_partial_match():
    """Test partial match returns moderate similarity."""
    new_message = "Cannot access account login"
    resolved_tickets = [
        {"message": "I cannot login to my account", "response": "Reset password"},
        {"message": "Payment issue with credit card", "response": "Check billing"}
    ]
    
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.3)
    
    assert result is not None
    assert result["matched_text"] == "I cannot login to my account"
    assert result["similarity_score"] >= 0.3
    assert result["similarity_score"] < 1.0


def test_find_similar_ticket_below_threshold():
    """Test no match when similarity is below threshold."""
    new_message = "How do I use the dark mode feature?"
    resolved_tickets = [
        {"message": "I cannot login to my account", "response": "Reset password"},
        {"message": "Payment was charged twice", "response": "Refund processed"}
    ]
    
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.8)
    
    assert result is None


def test_find_similar_ticket_empty_inputs():
    """Test edge cases with empty inputs."""
    # Empty new message
    result = find_similar_ticket("", [{"message": "test"}])
    assert result is None
    
    # None new message
    result = find_similar_ticket(None, [{"message": "test"}])
    assert result is None
    
    # Empty resolved tickets
    result = find_similar_ticket("test message", [])
    assert result is None
    
    # None resolved tickets
    result = find_similar_ticket("test message", None)
    assert result is None


def test_find_similar_ticket_invalid_ticket_format():
    """Test handling of invalid ticket formats."""
    new_message = "Login issue"
    resolved_tickets = [
        {"message": "I cannot login", "response": "Help with login"},
        {"message": "Invalid ticket without message field", "response": "Help"},
        {"response": "Ticket with only response"},
        "Invalid string ticket",
        123  # Invalid number ticket
    ]
    
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.2)
    
    assert result is not None
    assert result["matched_text"] == "I cannot login"
    assert result["similarity_score"] >= 0.2


def test_find_similar_ticket_multiple_matches():
    """Test that the most similar ticket is returned."""
    new_message = "Login problem with password"
    resolved_tickets = [
        {"message": "Login issue", "response": "Help with login"},
        {"message": "Password reset required for login", "response": "Reset password"},
        {"message": "Cannot login to account", "response": "Check credentials"}
    ]
    
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.2)
    
    assert result is not None
    # Should match the most similar one (Password reset required for login)
    assert result["similarity_score"] >= 0.2
    assert "matched_text" in result
    assert "similarity_score" in result
    assert "ticket" in result
    # Verify it matches the expected winner
    assert result["ticket"]["message"] == "Password reset required for login"
    assert result["ticket"]["response"] == "Reset password"


def test_find_similar_ticket_custom_threshold():
    """Test custom similarity threshold."""
    new_message = "Similar but not identical message"
    resolved_tickets = [
        {"message": "Similar message", "response": "Response"}
    ]
    
    # Low threshold should match
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.2)
    assert result is not None
    
    # High threshold should not match
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.9)
    assert result is None


def test_find_similar_ticket_return_format():
    """Test return format contains all required fields."""
    new_message = "Test message"
    resolved_tickets = [
        {"message": "Test message", "response": "Test response"}
    ]
    
    result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.5)
    
    assert result is not None
    assert isinstance(result, dict)
    assert "matched_text" in result
    assert "similarity_score" in result
    assert "ticket" in result
    assert isinstance(result["matched_text"], str)
    assert isinstance(result["similarity_score"], (int, float))
    assert isinstance(result["ticket"], dict)

from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch
import json

def test_similarity_search_db_cache_hit():
    """Call search twice with identical message → DB query runs once, second call served from cache."""
    # We'll test this via _run_ticket_automation in app.api.tickets
    from app.api.tickets import _run_ticket_automation
    from app.services.similarity_search import _cache_key
    
    mock_db = MagicMock(spec=Session)
    # Create ticket with minimal attributes to avoid relationship resolution
    mock_ticket = MagicMock()
    mock_ticket.id = 1
    mock_ticket.message = "i need a refund"
    mock_ticket.status = "open"
    
    # Mocking components
    with patch("app.api.tickets.classify_intent") as mock_classify:
        mock_classify.return_value = {"intent": "payment_issue", "confidence": 0.9, "sub_intent": "refund"}
        
        with patch("app.api.tickets.generate_response", return_value=("mocked response", "template")):
            with patch("app.api.tickets.decide_resolution", return_value="auto_resolve"):
                with patch("app.api.tickets._get_cache_client") as mock_get_cache:
                    with patch("app.api.tickets._cache_key", return_value="test-cache-key"):
                        mock_cache = MagicMock()
                        mock_get_cache.return_value = mock_cache
                        
                        # 1. First call: Cache miss
                        mock_cache.get.return_value = None
                        
                        # Patch the query function as a spy (Issue #5)
                        from app.api.tickets import get_resolved_tickets
                        with patch("app.api.tickets.get_resolved_tickets", wraps=get_resolved_tickets) as spy_query:
                            # Setup return value if needed, but wraps=real_fn will call the real one (which is fine in SQLite test)
                            # Or just return empty list to be safe
                            spy_query.return_value = []
                            
                            _run_ticket_automation(mock_ticket, mock_db)
                            
                            # Verify query was made
                            assert spy_query.call_count == 1
                            
                            # 2. Second call: Same message, mock cache HIT
                            mock_cache.get.return_value = json.dumps({
                                "matched_text": "i want a refund",
                                "similarity_score": 0.95,
                                "ticket": {"response": "Refunds take 3 days"},
                                "quality_score": 1.0
                            })
                            
                            spy_query.reset_mock()
                            _run_ticket_automation(mock_ticket, mock_db)
                            
                            # Verify query was NOT made this time
                            assert spy_query.call_count == 0
                        # Verify it used the cache
                        assert mock_cache.get.call_count >= 2
