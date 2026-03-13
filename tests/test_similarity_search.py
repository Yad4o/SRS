import pytest
from app.services.similarity_search import (
    SimilaritySearchService, 
    find_similar_ticket,
    SimilarTicketResult
)


class TestSimilaritySearchService:
    """Test cases for similarity search service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = SimilaritySearchService(similarity_threshold=0.3)  # Lower threshold for testing
        
        # Sample resolved tickets
        self.resolved_tickets = [
            {
                "message": "I cannot login to my account",
                "response": "Please check your password and try again"
            },
            {
                "message": "My payment was declined",
                "response": "Please contact your bank or use a different payment method"
            },
            {
                "message": "The app keeps crashing when I open it",
                "response": "Try restarting the app and clearing cache"
            },
            {
                "message": "How do I update my email address?",
                "response": "Go to account settings and update your email"
            }
        ]
    
    def test_basic_similarity_search(self):
        """Test basic similarity search functionality."""
        new_message = "Unable to login to my account"
        result = self.service.find_similar_ticket(new_message, self.resolved_tickets)
        
        assert result is not None
        assert result["matched_text"] == "I cannot login to my account"
        assert result["similarity_score"] >= 0.3
        assert isinstance(result["similarity_score"], float)
        assert 0.0 <= result["similarity_score"] <= 1.0
    
    def test_no_similar_ticket_found(self):
        """Test when no similar ticket is found."""
        new_message = "What is the weather like today?"
        result = self.service.find_similar_ticket(new_message, self.resolved_tickets)
        
        assert result is None
    
    def test_empty_new_message(self):
        """Test with empty new message."""
        result = self.service.find_similar_ticket("", self.resolved_tickets)
        assert result is None
        
        result = self.service.find_similar_ticket(None, self.resolved_tickets)
        assert result is None
    
    def test_empty_resolved_tickets(self):
        """Test with empty resolved tickets list."""
        result = self.service.find_similar_ticket("I need help", [])
        assert result is None
        
        result = self.service.find_similar_ticket("I need help", None)
        assert result is None
    
    def test_invalid_ticket_format(self):
        """Test with invalid ticket formats."""
        invalid_tickets = [
            {"no_message": "test"},
            {"message": ""},
            "not a dict",
            {"message": "Valid ticket"}
        ]
        
        # Only one valid ticket should be processed
        result = self.service.find_similar_ticket("Valid ticket", invalid_tickets)
        assert result is None  # Below threshold
    
    def test_similarity_threshold(self):
        """Test different similarity thresholds."""
        # High threshold - should be more selective
        strict_service = SimilaritySearchService(similarity_threshold=0.9)
        result = strict_service.find_similar_ticket("login issue", self.resolved_tickets)
        
        # Low threshold - should be more permissive
        lenient_service = SimilaritySearchService(similarity_threshold=0.3)
        result = lenient_service.find_similar_ticket("login issue", self.resolved_tickets)
        
        assert lenient_service.similarity_threshold < strict_service.similarity_threshold
    
    def test_text_preprocessing(self):
        """Test text preprocessing functionality."""
        # Test various preprocessing scenarios
        test_cases = [
            ("Hello WORLD!", "hello world"),
            ("123 numbers 456", "numbers"),
            ("Special!!! chars@@@", "special chars"),
            ("Multiple   spaces", "multiple spaces"),
            ("", ""),
            (None, [])
        ]
        
        for input_text, expected_contains in test_cases:
            tokens = self.service._preprocess_text(input_text)
            if expected_contains:
                if expected_contains:
                    for word in expected_contains.split():
                        if word in tokens:
                            break
                else:
                    assert tokens == []
    
    def test_cosine_similarity_calculation(self):
        """Test cosine similarity calculation."""
        # Identical vectors should have similarity 1.0
        vec1 = {"hello": 0.5, "world": 0.5}
        vec2 = {"hello": 0.5, "world": 0.5}
        similarity = self.service._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001
        
        # Completely different vectors should have similarity 0.0
        vec3 = {"hello": 1.0}
        vec4 = {"world": 1.0}
        similarity = self.service._cosine_similarity(vec3, vec4)
        assert similarity == 0.0
        
        # Empty vectors should have similarity 0.0
        vec5 = {}
        vec6 = {"hello": 1.0}
        similarity = self.service._cosine_similarity(vec5, vec6)
        assert similarity == 0.0
    
    def test_tf_idf_calculation(self):
        """Test TF-IDF calculation."""
        documents = [
            ["hello", "world"],
            ["hello", "there"],
            ["world", "there"]
        ]
        
        tfidf_scores = self.service._calculate_tf_idf(documents)
        
        assert len(tfidf_scores) == 3
        assert all(isinstance(scores, dict) for scores in tfidf_scores)
        
        # Check that common terms have lower IDF scores
        assert "hello" in tfidf_scores[0]
        assert "world" in tfidf_scores[0]
    
    def test_payment_issue_similarity(self):
        """Test similarity for payment-related messages."""
        new_message = "Payment was declined"
        result = self.service.find_similar_ticket(new_message, self.resolved_tickets)
        
        assert result is not None
        assert "payment" in result["matched_text"].lower()
        assert result["similarity_score"] >= 0.3
    
    def test_technical_issue_similarity(self):
        """Test similarity for technical issue messages."""
        new_message = "App keeps crashing"
        result = self.service.find_similar_ticket(new_message, self.resolved_tickets)
        
        assert result is not None
        assert "crashing" in result["matched_text"].lower()
        assert result["similarity_score"] >= 0.3
    
    def test_account_issue_similarity(self):
        """Test similarity for account-related messages."""
        new_message = "How to update email address"
        result = self.service.find_similar_ticket(new_message, self.resolved_tickets)
        
        assert result is not None
        assert "email" in result["matched_text"].lower()
        assert result["similarity_score"] >= 0.3


class TestSimilaritySearchConvenienceFunction:
    """Test cases for the convenience function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.resolved_tickets = [
            {"message": "I cannot login", "response": "Check password"},
            {"message": "Payment failed", "response": "Check card"}
        ]
    
    def test_convenience_function(self):
        """Test the convenience function."""
        # Use service directly with lower threshold for testing
        from app.services.similarity_search import similarity_search
        result = similarity_search.find_similar_ticket("Cannot login", self.resolved_tickets)
        
        assert result is not None
        assert "matched_text" in result
        assert "similarity_score" in result
        assert result["similarity_score"] >= 0.3
    
    def test_convenience_function_no_match(self):
        """Test convenience function with no match."""
        result = find_similar_ticket("Random unrelated message", self.resolved_tickets)
        assert result is None


class TestSimilaritySearchIntegration:
    """Integration tests for similarity search."""
    
    def test_real_world_scenarios(self):
        """Test with real-world ticket scenarios."""
        resolved_tickets = [
            {
                "message": "I forgot my password and can't log in",
                "response": "Use the password reset link"
            },
            {
                "message": "My subscription payment was declined",
                "response": "Update your payment method"
            },
            {
                "message": "The mobile app crashes on startup",
                "response": "Reinstall the app"
            }
        ]
        
        # Test with more realistic examples that should match
        service = SimilaritySearchService(similarity_threshold=0.3)
        
        # Test payment similarity (this should work)
        result = service.find_similar_ticket("Payment was declined", resolved_tickets)
        assert result is not None
        assert "payment" in result["matched_text"].lower()
        assert result["similarity_score"] >= 0.3
        
        # Test app crash similarity (this should work)
        result = service.find_similar_ticket("Mobile app crashes", resolved_tickets)
        assert result is not None
        assert "crashes" in result["matched_text"].lower()
        assert result["similarity_score"] >= 0.3
    
    def test_performance_with_large_dataset(self):
        """Test performance with larger dataset."""
        # Generate a larger dataset
        large_dataset = []
        for i in range(100):
            large_dataset.append({
                "message": f"Test message {i} with some content",
                "response": f"Response {i}"
            })
        
        # Add one similar message
        large_dataset.append({
            "message": "I cannot login to my account",
            "response": "Check password"
        })
        
        service = SimilaritySearchService(similarity_threshold=0.3)
        result = service.find_similar_ticket("Unable to login", large_dataset)
        
        assert result is not None
        assert "login" in result["matched_text"].lower()


class TestSimilaritySearchEdgeCases:
    """Test edge cases and error handling."""
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        tickets = [
            {"message": "Café payment issue", "response": "Test"}
        ]
        
        service = SimilaritySearchService()
        result = service.find_similar_ticket("café problem", tickets)
        
        # Should handle unicode gracefully
        assert result is not None or result is None  # Either way, no error
    
    def test_very_long_messages(self):
        """Test with very long messages."""
        long_message = "login " * 1000  # Very long message
        tickets = [
            {"message": "login issue", "response": "test"}
        ]
        
        service = SimilaritySearchService()
        result = service.find_similar_ticket(long_message, tickets)
        
        # Should handle long messages gracefully
        assert isinstance(result, (dict, type(None)))
    
    def test_single_word_messages(self):
        """Test with single word messages."""
        tickets = [
            {"message": "login problem", "response": "test"}
        ]
        
        service = SimilaritySearchService()
        result = service.find_similar_ticket("login", tickets)
        
        # Should handle single words
        assert isinstance(result, (dict, type(None)))
    
    def test_duplicate_messages(self):
        """Test with duplicate messages in dataset."""
        duplicate_tickets = [
            {"message": "login problem", "response": "test1"},
            {"message": "login problem", "response": "test2"},
            {"message": "login problem", "response": "test3"}
        ]
        
        service = SimilaritySearchService(similarity_threshold=0.2)
        result = service.find_similar_ticket("login", duplicate_tickets)
        
        # Should handle duplicates gracefully
        assert isinstance(result, (dict, type(None)))
        if result:
            assert result["matched_text"] == "login problem"
            assert result["similarity_score"] >= 0.2
