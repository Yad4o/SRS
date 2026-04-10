from unittest.mock import MagicMock, patch
import json
import app.services.similarity_search as ss
from app.services.similarity_search import find_similar_ticket

def test_cache_prevents_duplicate_db_queries():
    """
    Test that the similarity search successfully uses the Redis cache.
    Verification:
    1. First call results in a cache miss and performs a calculation.
    2. Second call results in a cache hit and skips calculation.
    """
    # Ensure clean state for the singleton before test
    ss._redis_client = None
    
    mock_cache = MagicMock()
    # First call: None (miss), Second call: JSON string (hit)
    mock_cache.get.side_effect = [None, json.dumps({"matched_text": "cached", "similarity_score": 1.0})]

    resolved_tickets = [
        {"message": "test issue", "response": "restart", "quality_score": 1.0}
    ]

    try:
        # Patch _get_cache_client to bypass the missing redis library check completely
        with patch("app.services.similarity_search._get_cache_client", return_value=mock_cache):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.REDIS_URL = "redis://localhost"
                mock_settings.SIMILARITY_THRESHOLD = 0.5

                # First call (Miss)
                res1 = find_similar_ticket("test issue", resolved_tickets)
                assert res1 is not None
                assert res1["matched_text"] == "test issue"
                # Verify first call did real work (cache miss -> computation -> write)
                assert mock_cache.setex.call_count == 1

                # Second call (Hit)
                res2 = find_similar_ticket("test issue", resolved_tickets)
                assert res2 is not None
                assert res2["matched_text"] == "cached"  # Came from mock, not computation
                
                # Verify total cache reads
                assert mock_cache.get.call_count == 2
    finally:
        # Prevent singleton leak: always reset after the test ends
        ss._redis_client = None
