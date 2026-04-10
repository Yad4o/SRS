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
    create_mock_ai_service
)

# Test database setup - use temporary database for parallel safety
import tempfile
import os

@pytest.fixture(scope="session")
def temp_db_file():
    """Create a temporary database file for the test session."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    yield temp_db.name
    # Clean up after session
    import gc
    gc.collect()
    try:
        import time
        time.sleep(0.1)
        os.unlink(temp_db.name)
    except (OSError, PermissionError):
        pass  # Ignore cleanup errors

@pytest.fixture(scope="function")
def comprehensive_engine(temp_db_file):
    """Create database engine for this test session."""
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{temp_db_file}"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    yield engine

@pytest.fixture(scope="function")
def db_session(comprehensive_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=comprehensive_engine)
    Base.metadata.create_all(bind=comprehensive_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=comprehensive_engine)




@pytest.fixture(scope="function")
def client(comprehensive_engine):
    """Create test client with database override."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=comprehensive_engine)
    
    def override_get_db():
        """Override database dependency for testing."""
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class TestRealAIImplementation:
    """Test real AI service implementations with realistic inputs."""

    def test_real_intent_classification(self):
        """Test real intent classifier with realistic inputs."""
        from app.services.classifier import classify_intent
        
        # Test login issues - should return high confidence
        login_messages = [
            "I cannot login to my account",
            "login credentials not working",
            "forgot my password and can't login",
            "login page says invalid credentials"
        ]
        
        for message in login_messages:
            result = classify_intent(message)
            assert result["intent"] == "login_issue"
            assert result["confidence"] >= 0.8, f"Expected confidence >= 0.8 for '{message}', got {result['confidence']}"
            assert isinstance(result["confidence"], float)
            assert 0.0 <= result["confidence"] <= 1.0

        # Test payment issues - should return high confidence
        payment_messages = [
            "I was charged twice for my order",
            "payment method declined",
            "billing question about invoice",
            "refund not processed yet"
        ]
        
        for message in payment_messages:
            result = classify_intent(message)
            assert result["intent"] == "payment_issue"
            assert result["confidence"] >= 0.8, f"Expected confidence >= 0.8 for '{message}', got {result['confidence']}"

        # Test unknown messages - should return low confidence
        unknown_messages = [
            "xyz123 random text",
            "the weather is nice today",
            ""
        ]
        
        for message in unknown_messages:
            result = classify_intent(message)
            assert result["intent"] == "unknown"
            assert result["confidence"] <= 0.3, f"Expected confidence <= 0.3 for '{message}', got {result['confidence']}"

        # Test general query messages - should return general_query with high confidence
        general_query_messages = [
            "what time is it",
            "how are you"
        ]
        
        for message in general_query_messages:
            result = classify_intent(message)
            assert result["intent"] == "general_query"
            assert result["confidence"] >= 0.7, f"Expected confidence >= 0.7 for '{message}', got {result['confidence']}"

    def test_real_similarity_search(self):
        """Test real similarity search with realistic inputs."""
        from app.services.similarity_search import find_similar_ticket
        
        # Add some realistic tickets
        resolved_tickets = [
            {"message": "Cannot login to account", "response": "Reset password using forgot password link"},
            {"message": "Payment was declined", "response": "Check payment method and try again"},
            {"message": "Need help with billing", "response": "Contact billing support"}
        ]
        
        # Test exact match
        result = find_similar_ticket("Cannot login to account", resolved_tickets, 0.8)
        assert result is not None
        assert result["similarity_score"] >= 0.8
        assert result["matched_text"] == "Cannot login to account"
        assert result["ticket"]["response"] == "Reset password using forgot password link"
        
        # Test partial match
        result = find_similar_ticket("login problem", resolved_tickets, 0.2)
        assert result is not None
        assert result["similarity_score"] >= 0.2
        assert "Cannot login to account" in result["matched_text"]
        assert result["ticket"]["response"] == "Reset password using forgot password link"
        
        # Test no match
        result = find_similar_ticket("completely different topic", resolved_tickets, 0.8)
        assert result is None
        
        # Test threshold behavior
        result = find_similar_ticket("payment issue", resolved_tickets, 0.3)
        assert result is not None
        assert result["similarity_score"] >= 0.3
        assert "Payment was declined" in result["matched_text"]
        assert result["ticket"]["response"] == "Check payment method and try again"

    def test_real_response_generation(self):
        """Test real response generation with realistic inputs."""
        from app.services.response_generator import generate_response
        
        # Test response with similar solution
        response = generate_response(
            intent="login_issue",
            original_message="Cannot login to my account",
            similar_solution="Reset password using forgot password link"
        )
        
        assert response is not None
        assert isinstance(response, tuple)
        assert len(response) == 2
        response_text, source_label = response
        assert isinstance(response_text, str)
        assert isinstance(source_label, str)
        assert len(response_text) > 0
        assert "Reset password" in response_text
        assert source_label == "similarity"
        
        # Test response without similar solution
        response = generate_response(
            intent="login_issue",
            original_message="Cannot login to my account",
            similar_solution=None
        )
        
        assert response is not None
        assert isinstance(response, tuple)
        assert len(response) == 2
        response_text, source_label = response
        assert isinstance(response_text, str)
        assert isinstance(source_label, str)
        assert len(response_text) > 0
        
        # Test response for unknown intent
        response = generate_response(
            intent="unknown",
            original_message="random message",
            similar_solution=None
        )
        
        assert response is not None
        assert isinstance(response, tuple)
        assert len(response) == 2
        response_text, source_label = response
        assert isinstance(response_text, str)
        assert isinstance(source_label, str)
        assert len(response_text) > 0

    def test_real_decision_engine(self):
        """Test real decision engine with realistic confidence values."""
        from app.services.decision_engine import decide_resolution
        
        # Test high confidence - should auto-resolve
        decision = decide_resolution(0.9)
        assert decision == "AUTO_RESOLVE"
        
        # Test exactly at threshold - should auto-resolve
        decision = decide_resolution(0.75)
        assert decision == "AUTO_RESOLVE"
        
        # Test below threshold - should escalate
        decision = decide_resolution(0.7)
        assert decision == "ESCALATE"
        
        # Test very low confidence - should escalate
        decision = decide_resolution(0.1)
        assert decision == "ESCALATE"
        
        # Test invalid values - should escalate (safety first)
        invalid_values = [None, "invalid", [], {}, True, False, -0.1, 1.1, float('inf'), float('-inf'), float('nan')]
        for invalid_value in invalid_values:
            decision = decide_resolution(invalid_value)
            assert decision == "ESCALATE"


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
            "ticket": {"response": "Reset your password using forgot password link"},
            "similarity_score": 0.8
        }
        mock_decision.return_value = "AUTO_RESOLVE"
        mock_response.return_value = ("I understand you're experiencing a login issue. Based on a similar case, Reset your password using forgot password link", "similarity")
        
        # Create ticket
        response = client.post("/tickets/", json={"message": "I cannot login to my account"})
        
        assert response.status_code == 201
        ticket_data = response.json()
        
        # Verify complete flow
        assert ticket_data["status"] == "auto_resolved"  # Updated to match API output
        assert ticket_data["intent"] == "login_issue"
        assert ticket_data["confidence"] == 0.95  # Actual classifier confidence
        assert "Reset your password" in ticket_data["response"]
        assert ticket_data["response_source"] == "similarity"
        
        # Verify database state
        db_ticket = db_session.query(Ticket).filter(Ticket.id == ticket_data["id"]).first()
        assert db_ticket.status == "auto_resolved"  # Updated to match API output
        assert db_ticket.intent == "login_issue"
        assert db_ticket.response_source == "similarity"

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

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch('app.api.tickets.classify_intent')
    def test_very_long_message(self, mock_classify, client, db_session):
        """Test handling of very long messages."""
        mock_classify.return_value = {"intent": "unknown", "confidence": 0.3}
        
        long_message = "x" * 10000
        response = client.post("/tickets/", json={"message": long_message})
        
        assert response.status_code == 201
        ticket_data = response.json()
        assert ticket_data["message"] == long_message

    @patch('app.api.tickets.classify_intent')
    def test_special_characters(self, mock_classify, client, db_session):
        """Test handling of special characters and unicode."""
        mock_classify.return_value = {"intent": "login_issue", "confidence": 0.85}
        
        special_message = "🚨 LOGIN??? émojis & spëcial chars! @#$%^&*()"
        response = client.post("/tickets/", json={"message": special_message})
        
        assert response.status_code == 201
        ticket_data = response.json()
        assert ticket_data["message"] == special_message

    @patch('app.api.tickets.classify_intent')
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

    @patch('app.api.tickets.classify_intent')
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
            mock_response.return_value = ("Reset your password", "template")
            
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
            assert db_ticket.response_source == "template"
            assert ticket_data["response_source"] == "template"

    def test_api_endpoints_integration(self, client, db_session):
        """Test API endpoints integration."""
        with patch('app.api.tickets.classify_intent') as mock_classify:
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

    def test_scenario_setup(self):
        """Test scenario setup."""
        service = create_mock_ai_service()
        
        # Setup login scenario
        scenario = service.setup_scenario("login")
        assert scenario is not None
        assert scenario["expected_intent"] == "login_issue"
        
        # Should have similar tickets added
        assert len(service.similarity_search.tickets_db) > 0
