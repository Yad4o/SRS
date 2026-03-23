"""
Comprehensive unit tests for AI automation components with mocking.

Tests:
- Intent classifier with mock AI responses
- Similarity search with deterministic results
- Decision engine edge cases
- Response generator with various scenarios
- Ticket automation orchestration

All tests use mocks to ensure deterministic results without external dependencies.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.ticket import Ticket
from app.services.decision_engine import decide_resolution, get_confidence_threshold, set_confidence_threshold
from app.services.response_generator import generate_response
from app.api.tickets import _run_ticket_automation


class TestIntentClassifier:
    """Unit tests for intent classification with mocked AI responses."""

    @patch('app.services.classifier.classify_intent')
    def test_classify_intent_login_issue(self, mock_classify):
        """Test classification of login issues."""
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.95}
        
        from app.services.classifier import classify_intent
        result = classify_intent("I cannot login to my account")
        
        assert result["intent"] == "login_issue"
        assert result["confidence"] == 0.95
        mock_classify.assert_called_once_with("I cannot login to my account")

    @patch('app.services.classifier.classify_intent')
    def test_classify_intent_payment_issue(self, mock_classify):
        """Test classification of payment issues."""
        mock_classify.return_value = {"intent": "payment_issue", "confidence": 1.0}
        
        from app.services.classifier import classify_intent
        result = classify_intent("My payment was charged twice")
        
        assert result["intent"] == "payment_issue"
        assert result["confidence"] == 1.0
        mock_classify.assert_called_once_with("My payment was charged twice")

    @patch('app.services.classifier.classify_intent')
    def test_classify_intent_low_confidence(self, mock_classify):
        """Test classification with low confidence."""
        mock_classify.return_value = {"intent": "unknown", "confidence": 0.2}
        
        from app.services.classifier import classify_intent
        result = classify_intent("random text xyz")
        
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.2

    @patch('app.services.classifier.classify_intent')
    def test_classify_intent_error_handling(self, mock_classify):
        """Test error handling in classifier."""
        mock_classify.side_effect = Exception("AI service unavailable")
        
        from app.services.classifier import classify_intent
        
        # Should raise exception since classifier doesn't handle errors
        with pytest.raises(Exception, match="AI service unavailable"):
            classify_intent("test message")

    @patch('app.services.classifier.classify_intent')
    def test_classify_intent_edge_cases(self, mock_classify):
        """Test edge cases: empty string, None, special characters."""
        # Empty string
        mock_classify.return_value = {"intent": "unknown", "confidence": 0.0}
        from app.services.classifier import classify_intent
        result = classify_intent("")
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0
        
        # None input
        result = classify_intent(None)
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0
        
        # Special characters
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.855}
        result = classify_intent("!!! LOGIN??? ###")
        assert result["intent"] == "login_issue"
        assert result["confidence"] == 0.855


class TestSimilaritySearch:
    """Unit tests for similarity search with mocked results."""

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_exact_match(self, mock_find):
        """Test finding exact match."""
        mock_find.return_value = {
            "matched_text": "I cannot login to my account",
            "similarity_score": 0.95,
            "ticket": {"message": "I cannot login to my account", "response": "Reset password"}
        }
        
        from app.services.similarity_search import find_similar_ticket
        result = find_similar_ticket(
            "I cannot login to my account",
            [{"message": "I cannot login to my account", "response": "Reset password"}],
            similarity_threshold=0.8
        )
        
        assert result is not None
        assert result["similarity_score"] == 0.95
        assert result["ticket"]["response"] == "Reset password"

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_below_threshold(self, mock_find):
        """Test no match when below threshold."""
        mock_find.return_value = None
        
        from app.services.similarity_search import find_similar_ticket
        result = find_similar_ticket(
            "How do I use dark mode feature?",
            [{"message": "I cannot login to my account", "response": "Reset password"}],
            similarity_threshold=0.9
        )
        
        assert result is None

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_empty_inputs(self, mock_find):
        """Test edge cases with empty inputs."""
        mock_find.return_value = None
        
        from app.services.similarity_search import find_similar_ticket
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

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_invalid_ticket_format(self, mock_find):
        """Test handling of invalid ticket formats."""
        mock_find.return_value = {
            "matched_text": "I cannot login",
            "similarity_score": 0.8,
            "ticket": {"message": "I cannot login", "response": "Help with login"}
        }
        
        from app.services.similarity_search import find_similar_ticket
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
        assert result["similarity_score"] == 0.8

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_multiple_matches(self, mock_find):
        """Test that most similar ticket is returned."""
        mock_find.return_value = {
            "matched_text": "Password reset required for login",
            "similarity_score": 0.85,
            "ticket": {"message": "Password reset required for login", "response": "Reset password"}
        }
        
        from app.services.similarity_search import find_similar_ticket
        new_message = "Login problem with password"
        resolved_tickets = [
            {"message": "Login issue", "response": "Help with login"},
            {"message": "Password reset required for login", "response": "Reset password"},
            {"message": "Cannot login to account", "response": "Check credentials"}
        ]
        
        result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.2)
        
        assert result is not None
        # Should match most similar one (Password reset required for login)
        assert result["similarity_score"] == 0.85
        assert "matched_text" in result
        assert "similarity_score" in result
        assert "ticket" in result
        # Verify it matches expected winner
        assert result["ticket"]["message"] == "Password reset required for login"
        assert result["ticket"]["response"] == "Reset password"

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_custom_threshold(self, mock_find):
        """Test custom similarity threshold."""
        mock_find.return_value = {"ticket": {"response": "Response"}}
        
        from app.services.similarity_search import find_similar_ticket
        new_message = "Similar but not identical message"
        resolved_tickets = [
            {"message": "Similar message", "response": "Response"}
        ]
        
        # Low threshold should match
        result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.2)
        assert result is not None
        
        # High threshold should not match
        mock_find.return_value = None
        result = find_similar_ticket(new_message, resolved_tickets, similarity_threshold=0.9)
        assert result is None

    @patch('app.services.similarity_search.find_similar_ticket')
    def test_find_similar_return_format(self, mock_find):
        """Test return format contains all required fields."""
        mock_find.return_value = {
            "matched_text": "Test message",
            "similarity_score": 0.8,
            "ticket": {"message": "Test message", "response": "Test response"}
        }
        
        from app.services.similarity_search import find_similar_ticket
        result = find_similar_ticket("Test message", [{"message": "Test message", "response": "Test response"}], similarity_threshold=0.5)
        
        assert result is not None
        assert isinstance(result, dict)
        assert "matched_text" in result
        assert "similarity_score" in result
        assert "ticket" in result
        assert isinstance(result["matched_text"], str)
        assert isinstance(result["similarity_score"], (int, float))
        assert isinstance(result["ticket"], dict)
        assert 0.0 <= result["similarity_score"] <= 1.0


class TestDecisionEngine:
    """Unit tests for decision engine with threshold testing."""

    def test_decide_resolution_at_threshold(self):
        """Test decision exactly at threshold (0.75)."""
        original_threshold = get_confidence_threshold()
        try:
            set_confidence_threshold(0.75)
            
            # Exactly at threshold should auto-resolve
            result = decide_resolution(0.75)
            assert result == "AUTO_RESOLVE"
            
            # Just above threshold should auto-resolve
            result = decide_resolution(0.751)
            assert result == "AUTO_RESOLVE"
            
            # Just below threshold should escalate
            result = decide_resolution(0.749)
            assert result == "ESCALATE"
        finally:
            set_confidence_threshold(original_threshold)

    def test_decide_resolution_invalid_confidence(self):
        """Test invalid confidence values."""
        invalid_inputs = [
            None, "invalid", [], {}, True, False,
            -0.1, 1.1, float('inf'), float('-inf'), float('nan')
        ]
        
        for invalid_input in invalid_inputs:
            result = decide_resolution(invalid_input)
            assert result == "ESCALATE", f"Input {invalid_input} should escalate for safety"

    def test_decide_resolution_boundary_values(self):
        """Test boundary values."""
        # Minimum valid confidence
        result = decide_resolution(0.0)
        assert result == "ESCALATE"
        
        # Maximum valid confidence
        result = decide_resolution(1.0)
        assert result == "AUTO_RESOLVE"
        
        # Very small positive value
        result = decide_resolution(0.001)
        assert result == "ESCALATE"
        
        # Very close to 1.0
        result = decide_resolution(0.999)
        assert result == "AUTO_RESOLVE"

    def test_threshold_configuration(self):
        """Test dynamic threshold configuration."""
        original_threshold = get_confidence_threshold()
        
        try:
            # Test setting different thresholds
            for threshold in [0.5, 0.8, 0.9]:
                set_confidence_threshold(threshold)
                assert get_confidence_threshold() == threshold
                
                # Test decisions with new threshold
                result = decide_resolution(threshold - 0.1)
                assert result == "ESCALATE"
                
                result = decide_resolution(threshold + 0.1)
                assert result == "AUTO_RESOLVE"
        finally:
            set_confidence_threshold(original_threshold)

    def test_threshold_validation(self):
        """Test threshold validation."""
        original_threshold = get_confidence_threshold()
        
        try:
            # Invalid thresholds should raise ValueError
            with pytest.raises(ValueError):
                set_confidence_threshold(-0.1)
            
            with pytest.raises(ValueError):
                set_confidence_threshold(1.1)
            
            with pytest.raises(ValueError):
                set_confidence_threshold("invalid")
            
            with pytest.raises(ValueError):
                set_confidence_threshold(None)
        finally:
            set_confidence_threshold(original_threshold)


class TestResponseGenerator:
    """Unit tests for response generator with mocking."""

    @patch('app.services.response_generator.generate_response')
    def test_generate_response_with_similar_solution(self, mock_generate):
        """Test response generation with similar solution."""
        mock_generate.return_value = "I understand you're experiencing a login issue. Based on a similar case, Reset your password"
        
        from app.services.response_generator import generate_response
        result = generate_response(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution="Reset your password"
        )
        
        assert "Reset your password" in result
        assert "similar case" in result.lower()
        mock_generate.assert_called_once()

    @patch('app.services.response_generator.generate_response')
    def test_generate_response_without_similar_solution(self, mock_generate):
        """Test response generation without similar solution."""
        mock_generate.return_value = "Please double-check the email address you're signing in with — it's easy to mix up similar addresses. Also check for any accidental leading or trailing spaces in your password field. If you originally signed up via Google or another social provider, try that sign-in option instead of entering a password directly."
        
        result = generate_response(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution=None
        )
        
        assert isinstance(result, str)
        assert len(result) > 10
        assert "login" not in result.lower() and "login" not in result

    @patch('app.services.response_generator.generate_response')
    def test_generate_response_unknown_intent(self, mock_generate):
        """Test response generation for unknown intent."""
        mock_generate.return_value = "I understand you need help. A support agent will assist you shortly."
        
        result = generate_response(
            intent="unknown",
            original_message="Random text",
            similar_solution=None
        )
        
        assert isinstance(result, str)
        assert len(result) > 10

    @patch('app.services.response_generator.generate_response')
    def test_generate_response_error_handling(self, mock_generate):
        """Test error handling in response generator."""
        mock_generate.side_effect = Exception("Response generation failed")
        
        result = generate_response(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution=None
        )
        
        # Should return safe fallback
        assert isinstance(result, str)
        assert len(result) > 0

    @patch('app.services.response_generator.generate_response')
    def test_generate_response_all_intents(self, mock_generate):
        """Test response generation for all possible intents."""
        intents = ["login_issue", "payment_issue", "account_issue", "technical_issue", "feature_request", "general_query"]
        
        for intent in intents:
            mock_generate.return_value = f"Response for {intent}"
            
            from app.services.response_generator import generate_response
            result = generate_response(
                intent=intent,
                original_message=f"Test message for {intent}",
                similar_solution=None
            )
            
            assert intent in result
            assert isinstance(result, str)


class TestTicketAutomation:
    """Unit tests for ticket automation orchestration."""

    @patch('app.api.tickets.decide_resolution')
    @patch('app.api.tickets.find_similar_ticket')
    @patch('app.api.tickets.classify_intent')
    def test_automation_auto_resolve(self, mock_classify, mock_similarity, mock_decision):
        """Test full automation pipeline with auto-resolve decision."""
        # Setup mocks
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.95}
        mock_similarity.return_value = {
            "ticket": {"response": "Reset your password"}
        }
        mock_decision.return_value = "AUTO_RESOLVE"
        
        # Create test ticket
        ticket = Ticket(
            id=1,
            message="I cannot login to my account",
            status="open",
            created_at=datetime.now()
        )
        
        # Mock database session
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Run automation
        result = _run_ticket_automation(ticket, mock_db)
        
        # Verify results
        assert result.status == "auto_resolved"
        assert result.intent == "login_issue"
        assert result.confidence == 0.95
        assert result.response is not None
        # Check that response contains something about the similar solution
        assert "password" in result.response.lower()
        
        # Verify mocks called
        mock_classify.assert_called_once_with("I cannot login to my account")
        mock_decision.assert_called_once_with(0.95)

    @patch('app.api.tickets.decide_resolution')
    @patch('app.api.tickets.find_similar_ticket')
    @patch('app.api.tickets.classify_intent')
    def test_automation_escalate(self, mock_classify, mock_similarity, mock_decision):
        """Test automation pipeline with escalate decision."""
        # Setup mocks
        mock_classify.return_value = {"intent": "unknown", "confidence": 0.2}
        mock_similarity.return_value = None
        mock_decision.return_value = "ESCALATE"
        
        # Create test ticket
        ticket = Ticket(
            id=1,
            message="Random text xyz",
            status="open",
            created_at=datetime.now()
        )
        
        # Mock database session
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Run automation
        result = _run_ticket_automation(ticket, mock_db)
        
        # Verify results
        assert result.status == "escalated"
        assert result.intent == "unknown"
        assert result.confidence == 0.2
        assert result.response is None
        
        # Verify mocks called
        mock_classify.assert_called_once_with("Random text xyz")
        mock_decision.assert_called_once_with(0.2)

    @patch('app.api.tickets.decide_resolution')
    @patch('app.api.tickets.find_similar_ticket')
    @patch('app.api.tickets.classify_intent')
    def test_automation_classifier_error(self, mock_classify, mock_similarity, mock_decision):
        """Test automation pipeline with classifier error."""
        # Setup mock to raise exception
        mock_classify.side_effect = Exception("AI service unavailable")
        
        # Create test ticket
        ticket = Ticket(
            id=1,
            message="Test message",
            status="open",
            created_at=datetime.now()
        )
        
        # Mock database session
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        # Run automation - should raise exception
        with pytest.raises(Exception, match="AI service unavailable"):
            _run_ticket_automation(ticket, mock_db)

    def test_automation_confidence_at_threshold(self):
        """Test automation behavior exactly at confidence threshold."""
        original_threshold = get_confidence_threshold()
        
        try:
            set_confidence_threshold(0.75)
            
            with patch('app.api.tickets.classify_intent') as mock_classify, \
                 patch('app.api.tickets.find_similar_ticket') as mock_similarity, \
                 patch('app.api.tickets.decide_resolution') as mock_decision:
                
                # Setup mocks for threshold test
                mock_classify.return_value = {"intent": "login_issue", "confidence": 0.75}
                mock_similarity.return_value = None
                mock_decision.return_value = "AUTO_RESOLVE"  # Should auto-resolve at threshold
                
                # Create test ticket
                ticket = Ticket(
                    id=1,
                    message="Login issue",
                    status="open",
                    created_at=datetime.now()
                )
                
                # Mock database session
                mock_db = MagicMock(spec=Session)
                mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
                
                # Run automation
                result = _run_ticket_automation(ticket, mock_db)
                
                # Should auto-resolve at threshold
                assert result.status == "auto_resolved"
                assert result.confidence == 0.75
                mock_decision.assert_called_once_with(0.75)
                
        finally:
            set_confidence_threshold(original_threshold)

    def test_automation_empty_message(self):
        """Test automation with empty message."""
        with patch('app.api.tickets.find_similar_ticket') as mock_similarity, \
             patch('app.api.tickets.decide_resolution') as mock_decision:
            
            # Setup mocks - classifier will return early for empty message
            mock_similarity.return_value = None
            mock_decision.return_value = "ESCALATE"
            
            # Create test ticket with empty message
            ticket = Ticket(
                id=1,
                message="",
                status="open",
                created_at=datetime.now()
            )
            
            # Mock database session
            mock_db = MagicMock(spec=Session)
            mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            
            # Run automation
            result = _run_ticket_automation(ticket, mock_db)
            
            # Should escalate empty messages
            assert result.status == "escalated"
            assert result.intent == "unknown"
            assert result.confidence == 0.0
            
            # Note: classifier not called due to early return for empty message
