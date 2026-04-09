"""
AI service mocking utilities for deterministic testing.

Provides:
- Mock classifiers with predictable responses
- Mock similarity search with controlled results
- Mock response generators with template responses
- Test data fixtures for various scenarios
- Configuration for different test scenarios

All mocks are deterministic and don't depend on external AI services.
"""

from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock
import json
import pytest


class MockClassifier:
    """Mock intent classifier with predictable responses."""
    
    def __init__(self):
        self.responses = {
            "login": {"intent": "login_issue", "confidence": 0.85},
            "password": {"intent": "login_issue", "confidence": 0.9},
            "account": {"intent": "account_issue", "confidence": 0.8},
            "payment": {"intent": "payment_issue", "confidence": 0.92},
            "charge": {"intent": "payment_issue", "confidence": 0.88},
            "billing": {"intent": "payment_issue", "confidence": 0.75},
            "technical": {"intent": "technical_issue", "confidence": 0.82},
            "crash": {"intent": "technical_issue", "confidence": 0.9},
            "feature": {"intent": "feature_request", "confidence": 0.78},
            "add": {"intent": "feature_request", "confidence": 0.8},
            "how": {"intent": "general_query", "confidence": 0.7},
            "what": {"intent": "general_query", "confidence": 0.65},
            "default": {"intent": "unknown", "confidence": 0.3}
        }
        self._confidence_overrides = {}
    
    def set_confidence(self, intent: str, confidence: float):
        """Override confidence for a specific intent."""
        self._confidence_overrides[intent] = confidence
    
    def reset(self):
        """Clear all confidence overrides between tests."""
        self._confidence_overrides = {}
    
    def __call__(self, message: str) -> dict:
        """Allow classifier to be called directly like a function."""
        return self.classify(message)
    
    def classify(self, message: str) -> Dict[str, Any]:
        """Classify message with deterministic results."""
        if not message or message.strip() == "":
            return {"intent": "unknown", "confidence": 0.0}
        
        message_lower = message.lower()
        
        # Check for specific keywords
        for keyword, response in self.responses.items():
            if keyword == "default":
                continue
            if keyword in message_lower:
                result = response.copy()
                # Apply confidence override if present
                if result["intent"] in self._confidence_overrides:
                    result["confidence"] = self._confidence_overrides[result["intent"]]
                return result
        
        # Return default for unknown messages
        result = self.responses["default"].copy()
        if result["intent"] in self._confidence_overrides:
            result["confidence"] = self._confidence_overrides[result["intent"]]
        return result


class MockSimilaritySearch:
    """Mock similarity search with controlled results."""
    
    def __init__(self):
        self.similarity_threshold = 0.7
        self.tickets_db = []
    
    def add_ticket(self, message: str, response: str):
        """Add a ticket to the mock database."""
        self.tickets_db.append({
            "message": message,
            "response": response
        })
    
    def clear(self):
        """Clear all tickets between tests."""
        self.tickets_db = []
    
    def find_similar(self, query: str, threshold: float = None) -> Optional[Dict[str, Any]]:
        """Find similar ticket with deterministic results."""
        if not query or not self.tickets_db:
            return None
        
        threshold = threshold or self.similarity_threshold
        
        # Simple similarity simulation based on common words
        best_match = None
        best_score = 0.0
        
        query_words = set(query.lower().split())
        
        for ticket in self.tickets_db:
            ticket_words = set(ticket["message"].lower().split())
            
            # Calculate Jaccard similarity
            intersection = query_words.intersection(ticket_words)
            union = query_words.union(ticket_words)
            
            if len(union) > 0:
                similarity = len(intersection) / len(union)
            else:
                similarity = 0.0
            
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = {
                    "matched_text": ticket["message"],
                    "similarity_score": similarity,
                    "ticket": ticket
                }
        
        return best_match
    
    def set_similarity_score(self, query: str, score: float):
        """Override similarity score for testing."""
        # This would be implemented based on specific test needs
        pass


class MockResponseGenerator:
    """Mock response generator with template responses."""
    
    def __init__(self):
        self.templates = {
            "login_issue": {
                "with_solution": "I understand you're experiencing a login issue. Based on a similar case, {solution}",
                "without_solution": "I understand you're having trouble logging in. Please try resetting your password using the forgot password link."
            },
            "payment_issue": {
                "with_solution": "I understand you're having a payment problem. Based on a similar case, {solution}",
                "without_solution": "I understand you're experiencing a payment issue. Please check your billing statement or contact our payment support team."
            },
            "account_issue": {
                "with_solution": "I understand you have an account-related question. Based on a similar case, {solution}",
                "without_solution": "I understand you need help with your account. Please visit your account settings or contact support for assistance."
            },
            "technical_issue": {
                "with_solution": "I understand you're experiencing technical difficulties. Based on a similar case, {solution}",
                "without_solution": "I understand you're facing technical issues. Please try clearing your cache or restarting the application."
            },
            "feature_request": {
                "with_solution": "I understand you'd like to request a feature. Based on similar requests, {solution}",
                "without_solution": "Thank you for your feature request! We appreciate your feedback and will consider it for future updates."
            },
            "general_query": {
                "with_solution": "I understand you have a question. Based on similar inquiries, {solution}",
                "without_solution": "I understand you need help. Please check our FAQ or contact our support team for assistance."
            },
            "unknown": {
                "with_solution": "I understand you need help. Based on similar cases, {solution}",
                "without_solution": "I understand you need assistance. A support agent will help you shortly."
            }
        }
    
    def generate(self, intent: str, original_message: str, similar_solution: Optional[str] = None) -> str:
        """Generate response with deterministic templates."""
        template = self.templates.get(intent, self.templates["unknown"])
        
        if similar_solution:
            return template["with_solution"].format(solution=similar_solution)
        else:
            return template["without_solution"]


class MockDecisionEngine:
    """Mock decision engine with configurable threshold."""
    
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold
    
    def decide(self, confidence: float) -> str:
        """Make decision based on confidence threshold."""
        # Validation: confidence must be 0.0-1.0; invalid → ESCALATE
        if not isinstance(confidence, (int, float)):
            return "ESCALATE"
        
        if isinstance(confidence, bool):  # bool is subclass of int, but we don't want it
            return "ESCALATE"
        
        # Check for NaN
        if confidence != confidence:  # NaN check
            return "ESCALATE"
        
        if not (0.0 <= confidence <= 1.0):
            return "ESCALATE"
        
        return "AUTO_RESOLVE" if confidence >= self.threshold else "ESCALATE"
    
    def set_threshold(self, threshold: float):
        """Update decision threshold."""
        self.threshold = threshold


class TestScenarios:
    """Predefined test scenarios for common use cases."""
    
    @staticmethod
    def login_issue_scenario():
        """Scenario for login issues."""
        return {
            "message": "I cannot login to my account",
            "expected_intent": "login_issue",
            "expected_confidence": 0.85,
            "expected_decision": "AUTO_RESOLVE",
            "similar_tickets": [
                {"message": "Cannot login to account", "response": "Reset your password"},
                {"message": "Login password not working", "response": "Use forgot password link"}
            ]
        }
    
    @staticmethod
    def payment_issue_scenario():
        """Scenario for payment issues."""
        return {
            "message": "I was charged twice for my order",
            "expected_intent": "payment_issue",
            "expected_confidence": 0.88,  # Actual classifier confidence for "charged"
            "expected_decision": "AUTO_RESOLVE",
            "similar_tickets": [
                {"message": "Duplicate charge detected", "response": "Refund processed in 3-5 days"},
                {"message": "Payment error occurred", "response": "Check payment method"}
            ]
        }
    
    @staticmethod
    def low_confidence_scenario():
        """Scenario for low confidence classification."""
        return {
            "message": "xyz123 random unusual text",
            "expected_intent": "unknown",
            "expected_confidence": 0.3,
            "expected_decision": "ESCALATE",
            "similar_tickets": []
        }
    
    @staticmethod
    def threshold_scenario():
        """Scenario for testing exact threshold behavior."""
        return {
            "message": "billing question",  # Contains "billing" keyword → payment_issue/0.75
            "expected_intent": "payment_issue",  # Match actual classifier result
            "expected_confidence": 0.75,  # Exactly at threshold
            "expected_decision": "AUTO_RESOLVE",
            "similar_tickets": []
        }
    
    @staticmethod
    def edge_cases():
        """Collection of edge case scenarios."""
        return [
            {
                "name": "empty_message",
                "message": "",
                "expected_intent": "unknown",
                "expected_confidence": 0.0,
                "expected_decision": "ESCALATE"
            },
            {
                "name": "special_characters",
                "message": "🚨 LOGIN??? ### !!!",
                "expected_intent": "login_issue",
                "expected_confidence": 0.85,
                "expected_decision": "AUTO_RESOLVE"
            },
            {
                "name": "very_long_message",
                "message": "x" * 1000,
                "expected_intent": "unknown",
                "expected_confidence": 0.3,
                "expected_decision": "ESCALATE"
            },
            {
                "name": "unicode_message",
                "message": "Login issue with émojis 🚨 and spëcial chars",
                "expected_intent": "login_issue",
                "expected_confidence": 0.85,
                "expected_decision": "AUTO_RESOLVE"
            }
        ]


class MockAIService:
    """Combined mock AI service that orchestrates all components."""
    
    def __init__(self):
        self.classifier = MockClassifier()
        self.similarity_search = MockSimilaritySearch()
        self.response_generator = MockResponseGenerator()
        self.decision_engine = MockDecisionEngine()
    
    def setup_scenario(self, scenario_name: str):
        """Setup a predefined test scenario."""
        scenarios = {
            "login": TestScenarios.login_issue_scenario,
            "payment": TestScenarios.payment_issue_scenario,
            "low_confidence": TestScenarios.low_confidence_scenario,
            "threshold": TestScenarios.threshold_scenario
        }
        
        if scenario_name in scenarios:
            scenario = scenarios[scenario_name]()
            
            # Add similar tickets to search database
            for ticket in scenario.get("similar_tickets", []):
                self.similarity_search.add_ticket(ticket["message"], ticket["response"])
            
            return scenario
        
        return None
    
    def process_ticket(self, message: str) -> Dict[str, Any]:
        """Process a ticket through the complete mock pipeline."""
        # Classify intent
        classification = self.classifier.classify(message)
        intent = classification["intent"]
        confidence = classification["confidence"]
        
        # Find similar tickets
        similar_result = self.similarity_search.find_similar(message)
        
        # Make decision
        decision = self.decision_engine.decide(confidence)
        
        # Generate response if auto-resolving
        response = None
        if decision == "AUTO_RESOLVE":
            similar_solution = similar_result["ticket"]["response"] if similar_result else None
            response = self.response_generator.generate(intent, message, similar_solution)
        
        return {
            "intent": intent,
            "confidence": confidence,
            "decision": decision,
            "response": response,
            "similar_result": similar_result
        }


def create_mock_ai_service():
    """Factory function to create a configured mock AI service."""
    return MockAIService()


def setup_test_data():
    """Setup common test data for all tests."""
    mock_service = create_mock_ai_service()
    
    # Add common resolved tickets
    common_tickets = [
        {"message": "Cannot login to account", "response": "Reset your password using forgot password link"},
        {"message": "Payment was charged twice", "response": "Refund processed in 3-5 business days"},
        {"message": "Need to delete account", "response": "Go to account settings and select delete account"},
        {"message": "App keeps crashing", "response": "Clear cache and restart the application"},
        {"message": "Add dark mode feature", "response": "Thank you for the suggestion! We'll consider it."}
    ]
    
    for ticket in common_tickets:
        mock_service.similarity_search.add_ticket(ticket["message"], ticket["response"])
    
    return mock_service


# Export main classes and functions
__all__ = [
    'MockClassifier',
    'MockSimilaritySearch', 
    'MockResponseGenerator',
    'MockDecisionEngine',
    'TestScenarios',
    'MockAIService',
    'create_mock_ai_service',
    'setup_test_data'
]

# Pytest fixture for test isolation
@pytest.fixture(scope="function")
def mock_ai():
    """Mock AI service with automatic cleanup between tests."""
    service = setup_test_data()
    yield service
    # Teardown: reset all overrides
    service.classifier.reset()
    service.similarity_search.clear()
