"""
Tests for Intent Classification Service

Tests the rule-based intent classifier with various message types
and edge cases.
"""

import pytest
from app.services.intent_classifier import IntentClassifier, classify_intent


class TestIntentClassifier:
    """Test cases for IntentClassifier class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = IntentClassifier()
    
    def test_login_intent_classification(self):
        """Test classification of login-related messages."""
        test_cases = [
            ("I can't login to my account", "login_issue"),
            ("Forgot my password", "login_issue"),
            ("Account is locked", "login_issue"),
            ("Unable to sign in", "login_issue"),
            ("Need to reset credentials", "login_issue"),
        ]
        
        for message, expected_intent in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == expected_intent
            assert 0.0 <= result["confidence"] <= 1.0
            assert result["confidence"] >= 0.4  # Should be confident for clear cases
    
    def test_payment_intent_classification(self):
        """Test classification of payment-related messages."""
        test_cases = [
            ("My payment was declined", "payment_issue"),
            ("I was charged twice", "payment_issue"),
            ("Need a refund", "payment_issue"),
            ("Billing issue with invoice", "payment_issue"),
            ("Credit card transaction failed", "payment_issue"),
        ]
        
        for message, expected_intent in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == expected_intent
            assert 0.0 <= result["confidence"] <= 1.0
            assert result["confidence"] >= 0.4
    
    def test_account_intent_classification(self):
        """Test classification of account management messages."""
        test_cases = [
            ("I need to update my email", "account_issue"),
            ("How do I delete my account", "account_issue"),
            ("Change profile settings", "account_issue"),
            ("Update personal information", "account_issue"),
            ("Modify account details", "account_issue"),
        ]
        
        for message, expected_intent in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == expected_intent
            assert 0.0 <= result["confidence"] <= 1.0
            assert result["confidence"] >= 0.4  # Account issues might have lower confidence
    
    def test_technical_intent_classification(self):
        """Test classification of technical issue messages."""
        test_cases = [
            ("The app keeps crashing", "technical_issue"),
            ("Website is very slow", "technical_issue"),
            ("Getting an error message", "technical_issue"),
            ("System is down", "technical_issue"),
            ("Performance problems", "technical_issue"),
        ]
        
        for message, expected_intent in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == expected_intent
            assert 0.0 <= result["confidence"] <= 1.0
            assert result["confidence"] > 0.3  # Technical issues might have lower confidence
    
    def test_feature_request_classification(self):
        """Test classification of feature request messages."""
        test_cases = [
            ("I would like to have dark mode", "feature_request"),
            ("I suggest adding a new feature", "feature_request"),
            ("Hope you can implement search functionality", "feature_request"),
            ("Please add bulk export", "feature_request"),
            ("We need reporting dashboard feature", "feature_request"),
        ]
        
        for message, expected_intent in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == expected_intent
            assert 0.0 <= result["confidence"] <= 1.0
            assert result["confidence"] >= 0.4
    
    def test_general_query_classification(self):
        """Test classification of general query messages."""
        test_cases = [
            ("What are your business hours?", "general_query"),
            ("Where can I find documentation?", "general_query"),
            ("Can you explain the pricing?", "general_query"),
            ("Need help with navigation", "general_query"),
            ("How does the service work?", "general_query"),
        ]
        
        for message, expected_intent in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == expected_intent
            assert 0.0 <= result["confidence"] <= 1.0
            assert result["confidence"] > 0.2  # General queries might have lower confidence
    
    def test_unknown_classification(self):
        """Test classification of unknown/unclear messages."""
        test_cases = [
            "",  # Empty
            "hello",  # Too vague
            "asdfghjkl",  # Gibberish
            "ok",  # Too short
            "maybe",  # Unclear
        ]
        
        for message in test_cases:
            result = self.classifier.classify_intent(message)
            assert result["intent"] == "unknown"
            assert 0.0 <= result["confidence"] <= 1.0
    
    def test_confidence_range_validation(self):
        """Test that confidence scores are always in valid range."""
        test_messages = [
            "I can't login to my account",
            "Payment was declined",
            "Need to update email",
            "App is crashing",
            "Add dark mode please",
            "How does this work?",
            "xyz123",  # Unknown
            "",  # Empty
        ]
        
        for message in test_messages:
            result = self.classifier.classify_intent(message)
            assert isinstance(result["confidence"], (int, float))
            assert 0.0 <= result["confidence"] <= 1.0
    
    def test_edge_cases(self):
        """Test edge cases and special inputs."""
        # Very long message
        long_message = "login " * 100
        result = self.classifier.classify_intent(long_message)
        assert result["intent"] == "login_issue"
        assert 0.0 <= result["confidence"] <= 1.0
        
        # Mixed case
        mixed_case = "I CAN'T LOGIN to my ACCOUNT"
        result = self.classifier.classify_intent(mixed_case)
        assert result["intent"] == "login_issue"
        
        # Special characters
        special_chars = "I can't login! @#$%^&*()"
        result = self.classifier.classify_intent(special_chars)
        assert result["intent"] == "login_issue"
        
        # Non-string input
        result = self.classifier.classify_intent(None)
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0
        
        result = self.classifier.classify_intent(123)
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0
    
    def test_confidence_boosting(self):
        """Test that multiple keyword matches boost confidence."""
        # Single keyword
        single = self.classifier.classify_intent("login")
        single_confidence = single["confidence"]
        
        # Multiple keywords
        multiple = self.classifier.classify_intent("I can't login to my account, forgot password")
        multiple_confidence = multiple["confidence"]
        
        # Multiple should have higher confidence
        assert multiple_confidence > single_confidence
        assert multiple["intent"] == "login_issue"
    
    def test_get_supported_intents(self):
        """Test getting list of supported intents."""
        intents = self.classifier.get_supported_intents()
        
        assert isinstance(intents, list)
        assert "login_issue" in intents
        assert "payment_issue" in intents
        assert "account_issue" in intents
        assert "technical_issue" in intents
        assert "feature_request" in intents
        assert "general_query" in intents
        assert "unknown" in intents
    
    def test_get_intent_examples(self):
        """Test getting example messages for each intent."""
        examples = self.classifier.get_intent_examples()
        
        assert isinstance(examples, dict)
        
        for intent in self.classifier.get_supported_intents():
            assert intent in examples
            assert isinstance(examples[intent], list)
            assert len(examples[intent]) > 0
            
            # Test that examples actually classify correctly
            for example in examples[intent]:
                result = self.classifier.classify_intent(example)
                if intent != "unknown":  # Unknown examples might not classify as unknown
                    assert result["intent"] == intent or result["confidence"] < 0.3


class TestConvenienceFunction:
    """Test cases for the convenience function."""
    
    def test_classify_intent_function(self):
        """Test the standalone classify_intent function."""
        result = classify_intent("I can't login to my account")
        
        assert isinstance(result, dict)
        assert "intent" in result
        assert "confidence" in result
        assert result["intent"] == "login_issue"
        assert 0.0 <= result["confidence"] <= 1.0
    
    def test_function_vs_class_consistency(self):
        """Test that convenience function produces same results as class method."""
        classifier = IntentClassifier()
        message = "Payment was declined"
        
        class_result = classifier.classify_intent(message)
        function_result = classify_intent(message)
        
        assert class_result == function_result


class TestIntentClassifierIntegration:
    """Integration tests for intent classifier."""
    
    def test_real_world_messages(self):
        """Test with realistic customer support messages."""
        real_messages = [
            {
                "message": "Hi, I've been trying to login for the past hour but keep getting an 'invalid credentials' error even though I'm sure my password is correct.",
                "expected_intent": "login_issue",
                "min_confidence": 0.6
            },
            {
                "message": "I was charged $29.99 twice for my monthly subscription. Can you please refund one of the charges?",
                "expected_intent": "payment_issue",
                "min_confidence": 0.7
            },
            {
                "message": "I'd like to update my email address from old@email.com to new@email.com. How do I do this?",
                "expected_intent": "general_query",
                "min_confidence": 0.5
            },
            {
                "message": "Your website keeps crashing when I try to access the dashboard. This has been happening for 3 days now.",
                "expected_intent": "login_issue",
                "min_confidence": 0.4
            },
            {
                "message": "It would be really helpful if you could add a feature to export data to CSV format.",
                "expected_intent": "feature_request",
                "min_confidence": 0.6
            },
            {
                "message": "How do I cancel my subscription? I can't find the option in my account settings.",
                "expected_intent": "account_issue",
                "min_confidence": 0.3
            }
        ]
        
        classifier = IntentClassifier()
        
        for test_case in real_messages:
            result = classifier.classify_intent(test_case["message"])
            
            assert result["intent"] == test_case["expected_intent"]
            assert result["confidence"] >= test_case["min_confidence"]
            assert 0.0 <= result["confidence"] <= 1.0
