"""
Comprehensive test suite using AI mocks for deterministic testing.

This suite combines unit and integration tests with mocked AI services
to ensure reliability, predictability, and confidence in automation.

Features:
- Deterministic test results with mocked AI services
- Edge case testing at confidence thresholds
- Performance and reliability testing
- Full lifecycle integration testing
- Error handling and recovery testing
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import get_db, Base
from app.models.ticket import Ticket
from tests.test_ai_mocks import (
    MockAIService, 
    TestScenarios, 
    setup_test_data,
    create_mock_ai_service
)

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_comprehensive.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """Create test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def db_session():
    """Create test database session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def mock_ai():
    """Create mock AI service for testing."""
    return setup_test_data()


class TestDeterministicClassification:
    """Test classification with deterministic mocked responses."""

    def test_login_issue_classification(self, mock_ai):
        """Test login issue classification."""
        result = mock_ai.classifier.classify("I cannot login to my account")
        
        assert result["intent"] == "login_issue"
        assert result["confidence"] == 0.85
        assert isinstance(result["confidence"], float)

    def test_payment_issue_classification(self, mock_ai):
        """Test payment issue classification."""
        result = mock_ai.classifier.classify("My payment was charged twice")
        
        assert result["intent"] == "payment_issue"
        assert result["confidence"] == 0.92

    def test_unknown_classification(self, mock_ai):
        """Test unknown message classification."""
        result = mock_ai.classifier.classify("xyz123 random text")
        
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.3

    def test_empty_message_classification(self, mock_ai):
        """Test empty message classification."""
        result = mock_ai.classifier.classify("")
        
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0

    def test_consistent_classification(self, mock_ai):
        """Test that same message gets same classification."""
        message = "I cannot login to my account"
        
        result1 = mock_ai.classifier.classify(message)
        result2 = mock_ai.classifier(message)
        
        assert result1 == result2

    def test_classification_confidence_override(self, mock_ai):
        """Test overriding confidence for testing."""
        mock_ai.classifier.set_confidence("login_issue", 0.95)
        
        result = mock_ai.classifier.classify("login problem")
        
        assert result["confidence"] == 0.95


class TestThresholdBehavior:
    """Test behavior at and around confidence thresholds."""

    def test_exactly_at_threshold(self, mock_ai):
        """Test behavior exactly at threshold (0.75)."""
        mock_ai.decision_engine.set_threshold(0.75)
        
        # Exactly at threshold should auto-resolve
        decision = mock_ai.decision_engine.decide(0.75)
        assert decision == "AUTO_RESOLVE"
        
        # Just below should escalate
        decision = mock_ai.decision_engine.decide(0.749)
        assert decision == "ESCALATE"
        
        # Just above should auto-resolve
        decision = mock_ai.decision_engine.decide(0.751)
        assert decision == "AUTO_RESOLVE"

    def test_threshold_configuration(self, mock_ai):
        """Test different threshold configurations."""
        thresholds = [0.5, 0.8, 0.9]
        
        for threshold in thresholds:
            mock_ai.decision_engine.set_threshold(threshold)
            
            # Test below threshold
            decision = mock_ai.decision_engine.decide(threshold - 0.1)
            assert decision == "ESCALATE"
            
            # Test at threshold
            decision = mock_ai.decision_engine.decide(threshold)
            assert decision == "AUTO_RESOLVE"
            
            # Test above threshold
            decision = mock_ai.decision_engine.decide(threshold + 0.1)
            assert decision == "AUTO_RESOLVE"

    def test_invalid_confidence_values(self, mock_ai):
        """Test handling of invalid confidence values."""
        invalid_values = [
            None, "invalid", [], {}, True, False,
            -0.1, 1.1, float('inf'), float('-inf'), float('nan')
        ]
        
        for invalid_value in invalid_values:
            decision = mock_ai.decision_engine.decide(invalid_value)
            assert decision == "ESCALATE"  # Safety first

    @patch('app.api.tickets.classify_intent')
    def test_threshold_with_real_api(self, mock_classify, client, db_session):
        """Test threshold behavior with real API."""
        # Mock classifier to return exact threshold
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.75}
        
        response = client.post("/tickets/", json={"message": "Test at threshold"})
        
        assert response.status_code == 201
        ticket_data = response.json()
        assert ticket_data["status"] == "auto_resolved"
        assert ticket_data["confidence"] == 0.75


class TestSimilaritySearch:
    """Test similarity search with deterministic results."""

    def test_exact_match(self, mock_ai):
        """Test finding exact match."""
        mock_ai.similarity_search.add_ticket("I cannot login", "Reset password")
        
        result = mock_ai.similarity_search.find_similar("I cannot login", 0.8)
        
        assert result is not None
        assert result["similarity_score"] >= 0.8
        assert result["ticket"]["response"] == "Reset password"

    def test_no_match_below_threshold(self, mock_ai):
        """Test no match when below threshold."""
        mock_ai.similarity_search.add_ticket("Payment issue", "Check billing")
        
        result = mock_ai.similarity_search.find_similar("Login problem", 0.9)
        
        assert result is None

    def test_partial_match(self, mock_ai):
        """Test partial match with moderate similarity."""
        mock_ai.similarity_search.add_ticket("Login problem help", "Reset password")  # Different message
        
        result = mock_ai.similarity_search.find_similar("Login issue", 0.2)  # Lower threshold
        
        assert result is not None
        assert result["similarity_score"] >= 0.2
        assert result["similarity_score"] < 1.0
        assert result["ticket"]["response"] == "Reset password"

    def test_empty_database(self, mock_ai):
        """Test similarity search with empty database."""
        result = mock_ai.similarity_search.find_similar("Any message", 0.5)
        
        assert result is None

    def test_multiple_tickets_best_match(self, mock_ai):
        """Test selecting best match from multiple tickets."""
        mock_ai.similarity_search.clear()  # Clear pre-populated data
        mock_ai.similarity_search.add_ticket("Login help needed", "Help with login")  # Different message
        mock_ai.similarity_search.add_ticket("Cannot login to my account", "Reset password")  # Different message
        mock_ai.similarity_search.add_ticket("Password reset issue", "Check password")  # Different message
        
        result = mock_ai.similarity_search.find_similar("Cannot login", 0.2)
        
        assert result is not None
        # Should find the most similar match - "Cannot login to my account" has highest similarity (0.4)
        assert result["ticket"]["response"] == "Reset password"


class TestResponseGeneration:
    """Test response generation with templates."""

    def test_response_with_similar_solution(self, mock_ai):
        """Test response generation with similar solution."""
        response = mock_ai.response_generator.generate(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution="Reset your password"
        )
        
        assert "Reset your password" in response
        assert "similar case" in response.lower()

    def test_response_without_similar_solution(self, mock_ai):
        """Test response generation without similar solution."""
        response = mock_ai.response_generator.generate(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution=None
        )
        
        assert isinstance(response, str)
        assert len(response) > 10
        assert "logging" in response.lower()  # Template contains "logging", not "login"

    def test_response_all_intents(self, mock_ai):
        """Test response generation for all intents."""
        intents = [
            "login_issue", "payment_issue", "account_issue",
            "technical_issue", "feature_request", "general_query", "unknown"
        ]
        
        for intent in intents:
            response = mock_ai.response_generator.generate(
                intent=intent,
                original_message=f"Test {intent}",
                similar_solution=None
            )
            
            assert isinstance(response, str)
            assert len(response) > 10

    def test_response_consistency(self, mock_ai):
        """Test response generation consistency."""
        # Generate same response multiple times
        response1 = mock_ai.response_generator.generate(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution=None
        )
        response2 = mock_ai.response_generator.generate(
            intent="login_issue",
            original_message="Cannot login",
            similar_solution=None
        )
        
        assert response1 == response2


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    @patch('app.api.tickets.classify_intent')
    @patch('app.api.tickets.find_similar_ticket')
    @patch('app.api.tickets.decide_resolution')
    @patch('app.api.tickets.generate_response')
    def test_login_issue_auto_resolve(self, mock_response, mock_decision, mock_similarity, mock_classify, client, db_session):
        """Test complete login issue auto-resolve scenario."""
        # Setup mocks
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.95}  # Match actual classifier
        mock_similarity.return_value = {
            "ticket": {"response": "Reset your password using forgot password link"}
        }
        mock_decision.return_value = "AUTO_RESOLVE"
        mock_response.return_value = "I understand you're experiencing a login issue. Based on a similar case, Reset your password using forgot password link"
        
        # Create ticket
        response = client.post("/tickets/", json={"message": "I cannot login to my account"})
        
        assert response.status_code == 201
        ticket_data = response.json()
        
        # Verify complete flow
        assert ticket_data["status"] == "auto_resolved"
        assert ticket_data["intent"] == "login_issue"
        assert ticket_data["confidence"] == 0.95  # Actual classifier confidence
        assert "Reset your password" in ticket_data["response"]
        
        # Verify database state
        db_ticket = db_session.query(Ticket).filter(Ticket.id == ticket_data["id"]).first()
        assert db_ticket.status == "auto_resolved"
        assert db_ticket.intent == "login_issue"

    @patch('app.api.tickets.classify_intent')
    @patch('app.api.tickets.decide_resolution')
    def test_unknown_intent_escalate(self, mock_decision, mock_classify, client, db_session):
        """Test unknown intent escalation scenario."""
        # Setup mocks
        mock_classify.return_value = {"intent": "unknown", "confidence": 0.2}
        mock_decision.return_value = "ESCALATE"
        
        # Create ticket
        response = client.post("/tickets/", json={"message": "Random unusual text xyz123"})
        
        assert response.status_code == 201
        ticket_data = response.json()
        
        # Verify escalation
        assert ticket_data["status"] == "escalated"
        assert ticket_data["intent"] == "unknown"
        assert ticket_data["confidence"] == 0.2
        assert ticket_data["response"] is None

    def test_scenario_based_testing(self, mock_ai):
        """Test predefined scenarios."""
        scenarios = ["login", "payment", "low_confidence", "threshold"]
        
        for scenario_name in scenarios:
            scenario = mock_ai.setup_scenario(scenario_name)
            assert scenario is not None
            
            # Process ticket through mock pipeline
            result = mock_ai.process_ticket(scenario["message"])
            
            # Verify expected results
            assert result["intent"] == scenario["expected_intent"]
            assert result["confidence"] == scenario["expected_confidence"]
            assert result["decision"] == scenario["expected_decision"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_edge_cases_scenarios(self, mock_ai):
        """Test all edge case scenarios."""
        edge_cases = TestScenarios.edge_cases()
        
        for case in edge_cases:
            result = mock_ai.process_ticket(case["message"])
            
            assert result["intent"] == case["expected_intent"]
            assert result["confidence"] == case["expected_confidence"]
            assert result["decision"] == case["expected_decision"]

    @patch('app.services.classifier.classify_intent')
    def test_very_long_message(self, mock_classify, client, db_session):
        """Test handling of very long messages."""
        mock_classify.return_value = {"intent": "unknown", "confidence": 0.3}
        
        long_message = "x" * 10000
        response = client.post("/tickets/", json={"message": long_message})
        
        assert response.status_code == 201
        ticket_data = response.json()
        assert ticket_data["message"] == long_message

    @patch('app.services.classifier.classify_intent')
    def test_special_characters(self, mock_classify, client, db_session):
        """Test handling of special characters and unicode."""
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.85}
        
        special_message = "🚨 LOGIN??? émojis & spëcial chars! @#$%^&*()"
        response = client.post("/tickets/", json={"message": special_message})
        
        assert response.status_code == 201
        ticket_data = response.json()
        assert ticket_data["message"] == special_message

    @patch('app.services.classifier.classify_intent')
    def test_concurrent_processing(self, mock_classify, client, db_session):
        """Test concurrent ticket processing."""
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.8}
        
        import threading
        results = []
        
        def create_ticket(index):
            response = client.post("/tickets/", json={"message": f"Login issue {index}"})
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_ticket, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert all(status == 201 for status in results)
        
        # Verify all tickets created
        tickets = db_session.query(Ticket).all()
        assert len(tickets) == 5


class TestPerformanceAndReliability:
    """Test performance and reliability characteristics."""

    @patch('app.services.classifier.classify_intent')
    def test_processing_performance(self, mock_classify, client, db_session):
        """Test processing performance meets requirements."""
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.8}
        
        # Measure processing time
        start_time = time.time()
        response = client.post("/tickets/", json={"message": "Performance test"})
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        assert processing_time < 3.0
        assert response.status_code == 201

    def test_mock_performance(self, mock_ai):
        """Test mock service performance."""
        # Test classification performance
        start_time = time.time()
        for i in range(100):
            mock_ai.classifier.classify(f"Test message {i}")
        classification_time = time.time() - start_time
        
        # Should be very fast for mocks
        assert classification_time < 1.0
        
        # Test similarity search performance
        mock_ai.similarity_search.add_ticket("Test ticket", "Test response")
        
        start_time = time.time()
        for i in range(100):
            mock_ai.similarity_search.find_similar(f"Query {i}")
        similarity_time = time.time() - start_time
        
        assert similarity_time < 1.0

    def test_memory_usage(self, mock_ai):
        """Test memory usage doesn't grow excessively."""
        import gc
        import sys
        
        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Process many tickets
        for i in range(1000):
            mock_ai.process_ticket(f"Test message {i}")
        
        # Check memory usage
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory growth should be reasonable
        object_growth = final_objects - initial_objects
        assert object_growth < 10000  # Arbitrary reasonable limit

    @patch('app.api.tickets.classify_intent')
    def test_error_recovery(self, mock_classify, client, db_session):
        """Test system recovery from errors."""
        # Mock to fail on first call, succeed on second
        call_count = 0
        def classify_side_effect(message):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("AI service temporarily unavailable")
            return {"intent": "login_issue", "confidence": 0.8}
        
        mock_classify.side_effect = classify_side_effect
        
        # First call should handle error gracefully
        response1 = client.post("/tickets/", json={"message": "First ticket"})
        assert response1.status_code == 201
        ticket1_data = response1.json()
        assert ticket1_data["status"] == "escalated"  # Safety escalation
        
        # Second call should succeed normally
        response2 = client.post("/tickets/", json={"message": "Second ticket"})
        assert response2.status_code == 201
        ticket2_data = response2.json()
        assert ticket2_data["intent"] == "login_issue"


class TestSystemIntegration:
    """Test system integration with real components."""

    def test_mock_ai_service_integration(self, mock_ai):
        """Test mock AI service integration."""
        # Setup login scenario
        scenario = mock_ai.setup_scenario("login")
        
        # Process ticket
        result = mock_ai.process_ticket(scenario["message"])
        
        # Verify complete flow
        assert result["intent"] == "login_issue"
        assert result["confidence"] == 0.85
        assert result["decision"] == "AUTO_RESOLVE"
        assert result["response"] is not None
        assert "password" in result["response"].lower()

    def test_database_integration(self, client, db_session):
        """Test database integration with mocked AI."""
        with patch('app.api.tickets.classify_intent') as mock_classify, \
             patch('app.api.tickets.find_similar_ticket') as mock_similarity, \
             patch('app.api.tickets.decide_resolution') as mock_decision, \
             patch('app.api.tickets.generate_response') as mock_response:
            
            # Setup mocks
            mock_classify.return_value = {"intent": "login_issue", "confidence": 0.95}
            mock_similarity.return_value = None
            mock_decision.return_value = "AUTO_RESOLVE"
            mock_response.return_value = "Reset your password"
            
            # Create ticket
            response = client.post("/tickets/", json={"message": "Database integration test"})
            
            assert response.status_code == 201
            ticket_data = response.json()
            
            # Verify database persistence
            db_ticket = db_session.query(Ticket).filter(Ticket.id == ticket_data["id"]).first()
            assert db_ticket is not None
            assert db_ticket.message == "Database integration test"
            assert db_ticket.intent == "login_issue"
            assert db_ticket.status == "auto_resolved"

    def test_api_endpoints_integration(self, client, db_session):
        """Test API endpoints integration."""
        with patch('app.services.classifier.classify_intent') as mock_classify:
            mock_classify.return_value = {"intent": "login_issue", "confidence": 0.8}
            
            # Create ticket
            create_response = client.post("/tickets/", json={"message": "API integration test"})
            assert create_response.status_code == 201
            ticket_data = create_response.json()
            ticket_id = ticket_data["id"]
            
            # Get ticket
            get_response = client.get(f"/tickets/{ticket_id}")
            assert get_response.status_code == 200
            retrieved_data = get_response.json()
            assert retrieved_data["id"] == ticket_id
            assert retrieved_data["message"] == "API integration test"
            
            # List tickets
            list_response = client.get("/tickets/")
            assert list_response.status_code == 200
            list_data = list_response.json()
            assert len(list_data["tickets"]) >= 1
            assert any(t["id"] == ticket_id for t in list_data["tickets"])


# Test configuration and utilities
class TestConfiguration:
    """Test configuration and setup."""

    def test_mock_ai_service_creation(self):
        """Test mock AI service creation."""
        service = create_mock_ai_service()
        
        assert service.classifier is not None
        assert service.similarity_search is not None
        assert service.response_generator is not None
        assert service.decision_engine is not None

    def test_test_data_setup(self):
        """Test test data setup."""
        service = setup_test_data()
        
        # Should have common tickets in similarity search
        assert len(service.similarity_search.tickets_db) > 0
        
        # Should be able to process tickets
        result = service.process_ticket("Test message")
        assert "intent" in result
        assert "confidence" in result
        assert "decision" in result

    def test_scenario_setup(self):
        """Test scenario setup."""
        service = create_mock_ai_service()
        
        # Setup login scenario
        scenario = service.setup_scenario("login")
        assert scenario is not None
        assert scenario["expected_intent"] == "login_issue"
        
        # Should have similar tickets added
        assert len(service.similarity_search.tickets_db) > 0
