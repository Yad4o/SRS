"""
Tests for response generation service.

Tests cover all intent types, priority order, and edge cases.
Version: 3.3 - Response Generation Tests
"""

import pytest
from app.services.response_generator import ResponseGenerator, generate_response


class TestResponseGenerator:
    """Test cases for response generation service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = ResponseGenerator()
    
    def test_priority_1_similar_solution_reuse(self):
        """Test priority 1: reuse similar solution when provided."""
        intent = "login_issue"
        original_message = "I can't access my account"
        similar_solution = "Try resetting your password"
        
        response = self.generator.generate_response(intent, original_message, similar_solution)
        
        assert "Try resetting your password" in response
        assert "I understand you're having trouble logging in" in response
        assert response.startswith("I understand you're having trouble logging in")
    
    def test_priority_2_intent_based_template(self):
        """Test priority 2: use intent-based template when no similar solution."""
        intent = "payment_issue"
        original_message = "My card was charged twice"
        similar_solution = None
        
        response = self.generator.generate_response(intent, original_message, similar_solution)
        
        assert "Please check that your payment method is valid" in response
        assert "I understand you're experiencing a payment problem" in response
        assert len(response) > 50  # Should be a substantial response
    
    def test_priority_3_fallback_for_unknown_intent(self):
        """Test priority 3: fallback for unknown intent."""
        intent = "unknown_intent"
        original_message = "Random message"
        similar_solution = None
        
        response = self.generator.generate_response(intent, original_message, similar_solution)
        
        assert "Could you please provide more details" in response
        assert "I'll do my best to help you" in response
    
    def test_empty_similar_solution_uses_template(self):
        """Test that empty similar solution falls back to template."""
        intent = "account_issue"
        original_message = "Help with account"
        similar_solution = "   "  # Empty/whitespace only
        
        response = self.generator.generate_response(intent, original_message, similar_solution)
        
        # Should use fallback template, not the similar solution
        assert "account settings" in response.lower()
        assert "I understand you need help with your account" in response
    
    def test_all_intents_have_templates(self):
        """Test that all defined intents have proper templates."""
        intents = [
            "login_issue", "payment_issue", "account_issue", 
            "technical_issue", "feature_request", "general_query"
        ]
        
        for intent in intents:
            # Should not raise error
            response = self.generator.generate_response(intent, "test message", None)
            assert isinstance(response, str)
            assert len(response) > 20  # Should be meaningful
            assert any(word in response.lower() for word in ["please", "thank", "understand", "help"])
    
    def test_polite_and_safe_wording(self):
        """Test that responses use polite and safe wording."""
        test_cases = [
            ("login_issue", "can't login"),
            ("payment_issue", "payment failed"),
            ("technical_issue", "app crashes"),
            ("feature_request", "add dark mode")
        ]
        
        for intent, message in test_cases:
            response = self.generator.generate_response(intent, message, None)
            
            # Check for polite language
            assert any(word in response.lower() for word in ["please", "thank", "understand", "sorry"])
            
            # Check for safe, conservative wording
            assert "guarantee" not in response.lower()
            assert "definitely" not in response.lower()
            assert "immediately" not in response.lower()
    
    def test_no_database_or_decision_logic(self):
        """Test that responses don't contain DB or decision logic."""
        response = self.generator.generate_response("login_issue", "test", None)
        
        # Should not mention database operations
        assert "database" not in response.lower()
        assert "update" not in response.lower()
        assert "insert" not in response.lower()
        
        # Should not make auto-resolve/escalate decisions
        assert "auto-resolve" not in response.lower()
        assert "escalate" not in response.lower()
        assert "automatically" not in response.lower()
    
    def test_similar_solution_formatting(self):
        """Test that similar solutions are properly formatted in responses."""
        test_cases = [
            ("login_issue", "Reset your password"),
            ("payment_issue", "Contact your bank"),
            ("account_issue", "Update email in settings")
        ]
        
        for intent, solution in test_cases:
            response = self.generator.generate_response(intent, "test", solution)
            
            # Should contain the solution
            assert solution in response
            
            # Should be grammatically integrated
            assert response.count(solution) == 1  # Should appear once
            assert len(response) > len(solution)  # Should have additional context
    
    def test_response_length_reasonable(self):
        """Test that responses have reasonable length."""
        intents = ["login_issue", "payment_issue", "account_issue", "technical_issue"]
        
        for intent in intents:
            response = self.generator.generate_response(intent, "test message", None)
            
            # Should be substantial but not overly long
            assert 100 <= len(response) <= 500
    
    def test_multiple_similar_solution_calls(self):
        """Test multiple calls with different similar solutions."""
        intent = "general_query"
        original_message = "How does this work?"
        
        solutions = [
            "Check the documentation",
            "Visit the help center", 
            "Contact support for details"
        ]
        
        responses = []
        for solution in solutions:
            response = self.generator.generate_response(intent, original_message, solution)
            responses.append(response)
        
        # Each should be different
        assert len(set(responses)) == len(responses)
        
        # Each should contain its solution
        for i, solution in enumerate(solutions):
            assert solution in responses[i]


class TestConvenienceFunction:
    """Test cases for the convenience function."""
    
    def test_convenience_function_signature(self):
        """Test that convenience function works like the class method."""
        intent = "feature_request"
        original_message = "Add a new feature"
        similar_solution = "Thanks for the suggestion"
        
        # Test both approaches
        class_response = ResponseGenerator().generate_response(intent, original_message, similar_solution)
        func_response = generate_response(intent, original_message, similar_solution)
        
        assert class_response == func_response
    
    def test_convenience_function_with_none_solution(self):
        """Test convenience function with None similar solution."""
        response = generate_response("unknown", "random message")
        
        assert isinstance(response, str)
        assert len(response) > 20
        assert "provide more details" in response.lower()
    
    def test_convenience_function_optional_parameters(self):
        """Test that similar_solution parameter is truly optional."""
        # Should work without providing similar_solution
        response1 = generate_response("login_issue", "can't login")
        response2 = generate_response("login_issue", "can't login", None)
        response3 = generate_response("login_issue", "can't login", similar_solution=None)
        
        # All should work and be the same
        assert response1 == response2 == response3
        assert "password" in response1.lower()


class TestResponseQuality:
    """Test response quality and edge cases."""
    
    def test_empty_original_message(self):
        """Test response generation with empty original message."""
        response = generate_response("login_issue", "", "Reset password")
        
        assert isinstance(response, str)
        assert len(response) > 10
        assert "Reset password" in response
    
    def test_none_original_message(self):
        """Test response generation with None original message."""
        response = generate_response("payment_issue", None, "Check payment method")
        
        assert isinstance(response, str)
        assert len(response) > 10
        assert "Check payment method" in response
    
    def test_special_characters_in_original_message(self):
        """Test handling of special characters in original message."""
        special_message = "!!! HELP??? ###"
        response = generate_response("general_query", special_message)
        
        assert isinstance(response, str)
        assert len(response) > 20
        # Should not break or contain special characters
        assert "!!!" not in response
        assert "???" not in response
        assert "###" not in response
    
    def test_very_long_original_message(self):
        """Test handling of very long original messages."""
        long_message = "help " * 100  # Very long message
        response = generate_response("technical_issue", long_message)
        
        assert isinstance(response, str)
        # Response should still be reasonable length
        assert len(response) < 1000
    
    def test_all_intent_responses_unique(self):
        """Test that different intents produce different responses."""
        base_message = "I need help"
        
        responses = {}
        intents = ["login_issue", "payment_issue", "account_issue", "technical_issue", "feature_request", "general_query"]
        
        for intent in intents:
            responses[intent] = generate_response(intent, base_message)
        
        # All should be different
        unique_responses = set(responses.values())
        assert len(unique_responses) == len(intents)
        
        # Each should be appropriate to its intent
        assert "password" in responses["login_issue"].lower()
        assert "payment" in responses["payment_issue"].lower()
        assert "account" in responses["account_issue"].lower()
        assert "technical" in responses["technical_issue"].lower()
        assert "thank" in responses["feature_request"].lower()
        assert "help" in responses["general_query"].lower()
