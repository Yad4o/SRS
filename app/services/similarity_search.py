"""
 =============================================================================
 SRS (Support Request System) - Similarity Search Service
 =============================================================================

Purpose:
--------
Advanced similarity search for finding similar resolved tickets using TF-IDF
and cosine similarity algorithms with caching and performance optimizations.

Responsibilities:
-----------------
- Find similar resolved tickets based on message content
- Implement TF-IDF vectorization and cosine similarity
- Cache similarity results for performance
- Handle edge cases and validation
- Provide configurable similarity thresholds

Owner:
------
Backend Team

DO NOT:
-------
- Access database directly (use provided ticket data)
- Implement business logic for ticket resolution
- Cache sensitive user data

References:
-----------
- Technical Spec § 9.2 (Similarity Search)
- Information Retrieval best practices
"""

import json
import logging
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any

from app.core.config import settings
from app.models.ticket import Ticket
from app.utils.service_helpers import CacheHelper, ErrorHelper, MetricsHelper, ValidationHelper
from sqlalchemy.orm import Session

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Constants and Configuration
# -----------------------------------------------------------------------------
REDIS_CACHE_TTL = 300  # 5 minutes
MAX_TICKETS_TO_PROCESS = 100
MIN_TOKEN_LENGTH = 2
SIMILARITY_CACHE_PREFIX = "srs:similarity"

# Redis client singleton for lazy load
_redis_client = None


class SafeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles non-serializable objects safely."""
    
    def default(self, obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)


def _get_cache_client():
    """
    Return a Redis client if REDIS_URL is configured, else None.
    
    Returns:
        Redis client or None if Redis is not configured
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not settings.REDIS_URL:
        logger.debug("Redis not configured, skipping cache")
        return None
        
    try:
        import redis
        _redis_client = redis.from_url(
            settings.REDIS_URL, 
            decode_responses=True, 
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        
        # Test connection
        _redis_client.ping()
        logger.info("Redis client initialized successfully")
        return _redis_client
        
    except Exception as e:
        logger.warning(f"Failed to create Redis client: {e}")
        _redis_client = None  # Don't cache the failure
        return None


def _cache_key(message: str) -> str:
    """
    Generate a consistent cache key from the message content.
    
    Args:
        message: Input message to generate key for
        
    Returns:
        Cache key string
    """
    if not message:
        return f"{SIMILARITY_CACHE_PREFIX}:empty"
    
    # Create a consistent hash of the message
    import hashlib
    message_hash = hashlib.md5(message.encode('utf-8')).hexdigest()[:16]
    return f"{SIMILARITY_CACHE_PREFIX}:{message_hash}"


def _validate_input(message: str, resolved_tickets: List[Any]) -> Tuple[bool, str]:
    """
    Validate input parameters for similarity search.
    
    Args:
        message: New ticket message
        resolved_tickets: List of resolved tickets
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not message or not isinstance(message, str):
        return False, "Invalid message: must be a non-empty string"
    
    if len(message.strip()) < 10:
        return False, "Message too short for meaningful similarity comparison"
    
    if not resolved_tickets or not isinstance(resolved_tickets, list):
        return False, "Invalid resolved_tickets: must be a non-empty list"
    
    if len(resolved_tickets) > MAX_TICKETS_TO_PROCESS:
        logger.warning(f"Too many tickets provided, limiting to {MAX_TICKETS_TO_PROCESS}")
        resolved_tickets = resolved_tickets[:MAX_TICKETS_TO_PROCESS]
    
    return True, ""


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text into words with advanced preprocessing.
    
    Args:
        text: Input text to tokenize
        
    Returns:
        List of cleaned, lowercase tokens
    """
    if not text or not isinstance(text, str):
        return []
    
    try:
        # Sanitize and normalize text
        text = ValidationHelper.sanitize_string(text)
        text = text.lower()
        
        # Extract tokens (words, numbers)
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        
        # Filter short tokens and common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
        }
        
        filtered_tokens = [
            token for token in tokens 
            if len(token) >= MIN_TOKEN_LENGTH and token not in stop_words
        ]
        
        return filtered_tokens
        
    except Exception as e:
        logger.error(f"Tokenization failed: {e}")
        return []


def _compute_idf(all_texts: List[str]) -> Dict[str, float]:
    """
    Precompute IDF (Inverse Document Frequency) scores for all texts in corpus.
    
    Args:
        all_texts: All texts in corpus
        
    Returns:
        Dictionary of word -> IDF score
    """
    if not all_texts:
        return {}
    
    try:
        total_docs = len(all_texts)
        doc_counts = Counter()
        
        # Count documents containing each word
        for doc_text in all_texts:
            doc_tokens = set(_tokenize(doc_text))
            for token in doc_tokens:
                doc_counts[token] += 1
        
        # Calculate IDF for each word with smoothing
        idf_scores = {}
        for word, doc_count in doc_counts.items():
            # Add 1 smoothing to avoid division by zero
            idf = math.log((total_docs + 1) / (doc_count + 1)) + 1
            idf_scores[word] = idf
        
        logger.debug(f"Computed IDF for {len(idf_scores)} unique terms")
        return idf_scores
        
    except Exception as e:
        logger.error(f"IDF computation failed: {e}")
        return {}


def _calculate_tf(text: str) -> Dict[str, float]:
    """
    Calculate term frequency (TF) scores for a text.
    
    Args:
        text: The text to calculate TF for
        
    Returns:
        Dictionary of word -> TF score
    """
    if not text:
        return {}
    
    try:
        tokens = _tokenize(text)
        if not tokens:
            return {}
        
        # Count term frequencies
        tf = Counter(tokens)
        total_tokens = len(tokens)
        
        # Normalize by total tokens
        tf_scores = {word: count / total_tokens for word, count in tf.items()}
        
        return tf_scores
        
    except Exception as e:
        logger.error(f"TF calculation failed: {e}")
        return {}


def _apply_idf(tf_scores: Dict[str, float], idf_scores: Dict[str, float]) -> Dict[str, float]:
    """
    Apply IDF scores to TF scores to get TF-IDF vectors.
    
    Args:
        tf_scores: Term frequency scores
        idf_scores: Precomputed IDF scores
        
    Returns:
        Dictionary of word -> TF-IDF score
    """
    if not tf_scores:
        return {}
    
    try:
        tfidf_scores = {}
        for word, tf_score in tf_scores.items():
            tfidf_scores[word] = tf_score * idf_scores.get(word, 1.0)
        
        return tfidf_scores
        
    except Exception as e:
        logger.error(f"TF-IDF application failed: {e}")
        return {}


def _cosine_similarity(tfidf1: Dict[str, float], tfidf2: Dict[str, float]) -> float:
    """
    Calculate cosine similarity between two TF-IDF vectors.
    
    Args:
        tfidf1: First TF-IDF vector
        tfidf2: Second TF-IDF vector
        
    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    if not tfidf1 or not tfidf2:
        return 0.0
    
    try:
        # Get all unique words
        all_words = set(tfidf1.keys()) | set(tfidf2.keys())
        
        if not all_words:
            return 0.0
        
        # Calculate dot product
        dot_product = sum(
            tfidf1.get(word, 0.0) * tfidf2.get(word, 0.0) 
            for word in all_words
        )
        
        # Calculate magnitudes
        magnitude1 = math.sqrt(
            sum(tfidf1.get(word, 0.0) ** 2 for word in all_words)
        )
        magnitude2 = math.sqrt(
            sum(tfidf2.get(word, 0.0) ** 2 for word in all_words)
        )
        
        # Calculate cosine similarity
        if magnitude1 == 0.0 or magnitude2 == 0.0:
            return 0.0
        
        similarity = dot_product / (magnitude1 * magnitude2)
        
        # Ensure result is within valid range
        return max(0.0, min(1.0, similarity))
        
    except Exception as e:
        logger.error(f"Cosine similarity calculation failed: {e}")
        return 0.0


def get_resolved_tickets(db: Session, limit: int = 50) -> List[Ticket]:
    """
    Fetch recent successfully resolved tickets for similarity search.
    
    Args:
        db: Database session
        limit: Maximum number of tickets to fetch
        
    Returns:
        List of resolved Ticket objects
    """
    try:
        tickets = (
            db.query(Ticket)
            .filter(
                Ticket.status == "auto_resolved",
                Ticket.response.isnot(None),
            )
            .order_by(Ticket.created_at.desc())
            .limit(limit)
            .all()
        )
        
        logger.debug(f"Fetched {len(tickets)} resolved tickets for similarity search")
        return tickets
        
    except Exception as e:
        logger.error(f"Failed to fetch resolved tickets: {e}")
        return []


def find_similar_ticket(
    new_message: str, 
    resolved_tickets: List[Any], 
    similarity_threshold: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """
    Find the most similar resolved ticket to a new ticket message.
    
    This function implements advanced similarity search using TF-IDF vectorization
    and cosine similarity to find previously resolved tickets that match a new
    ticket's message. If a similar resolved ticket exists, its solution can be reused.
    
    Features:
    - TF-IDF vectorization with IDF precomputation
    - Cosine similarity calculation
    - Redis caching for performance
    - Input validation and error handling
    - Configurable similarity thresholds
    - Performance metrics and logging
    
    Args:
        new_message: The new ticket message to find matches for
        resolved_tickets: List of resolved ticket objects with 'message' and optionally 'response'
        similarity_threshold: Minimum similarity score to consider a match (default: from settings)
        
    Returns:
        Dict with similarity information or None if no match above threshold
        
    Raises:
        ValueError: If similarity_threshold is invalid
    """
    start_time = MetricsHelper.start_timer()
    
    try:
        # Validate inputs
        is_valid, error_msg = _validate_input(new_message, resolved_tickets)
        if not is_valid:
            logger.warning(f"Input validation failed: {error_msg}")
            return None
        
        # Set default threshold and validate
        if similarity_threshold is None:
            similarity_threshold = settings.SIMILARITY_THRESHOLD
        
        if not isinstance(similarity_threshold, (int, float)):
            raise ValueError("similarity_threshold must be a numeric value")
        
        if not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")
        
        # Try cache first
        cache = _get_cache_client()
        key = _cache_key(new_message) if cache else None
        
        if cache and key:
            try:
                cached = cache.get(key)
                if cached is not None:
                    cached_data = json.loads(cached)
                    # Apply current threshold to cached result
                    if cached_data and cached_data.get("similarity_score", 0.0) >= similarity_threshold:
                        MetricsHelper.record_metric("similarity_cache_hit", 1)
                        logger.debug(f"Cache hit for similarity search (score: {cached_data.get('similarity_score', 0.0)})")
                        return cached_data
                    MetricsHelper.record_metric("similarity_cache_miss", 1)
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}")
                _redis_client = None

        # Extract messages from resolved tickets
        ticket_messages = []
        valid_tickets = []
        
        for ticket in resolved_tickets:
            if isinstance(ticket, dict):
                message = ticket.get("message")
                ticket_obj = ticket
            elif hasattr(ticket, 'message'):
                message = ticket.message
                ticket_obj = {
                    "message": message,
                    "response": getattr(ticket, 'response', None),
                    "quality_score": getattr(ticket, 'quality_score', None)
                }
            else:
                continue
            
            if isinstance(message, str) and message.strip():
                ticket_messages.append(message.strip())
                valid_tickets.append(ticket_obj)

        if not ticket_messages:
            logger.debug("No valid ticket messages found")
            return None

        # Precompute IDF scores once for efficiency
        idf_scores = _compute_idf([new_message] + ticket_messages)

        # Calculate TF-IDF for new message
        new_tf = _calculate_tf(new_message)
        new_tfidf = _apply_idf(new_tf, idf_scores)

        # Find best match
        best_match = None
        best_similarity = 0.0
        best_ticket = None

        for i, ticket in enumerate(valid_tickets):
            ticket_message = ticket.get("message", "")
            if not isinstance(ticket_message, str) or not ticket_message.strip():
                continue

            # Calculate TF-IDF for this ticket
            ticket_tf = _calculate_tf(ticket_message)
            ticket_tfidf = _apply_idf(ticket_tf, idf_scores)

            # Calculate cosine similarity
            similarity = _cosine_similarity(new_tfidf, ticket_tfidf)

            # Update best match
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = ticket_message
                best_ticket = ticket

        # Prepare result
        result = None
        if best_match and best_similarity >= similarity_threshold:
            result = {
                "matched_text": best_match,
                "similarity_score": round(best_similarity, 3),
                "ticket": best_ticket,
                "quality_score": best_ticket.get("quality_score") if best_ticket else None,
                "threshold_used": similarity_threshold,
                "tickets_processed": len(valid_tickets)
            }
            
            logger.info(f"Found similar ticket with score {best_similarity:.3f}")
        else:
            logger.debug(f"No similar ticket found (best score: {best_similarity:.3f}, threshold: {similarity_threshold})")

        # Cache result (threshold-independent for future flexibility)
        if cache and key:
            try:
                cache_data = {
                    "matched_text": best_match,
                    "similarity_score": round(best_similarity, 3),
                    "ticket": best_ticket,
                    "quality_score": best_ticket.get("quality_score") if best_ticket else None,
                    "cached_at": MetricsHelper.get_timestamp()
                }
                cache.setex(key, REDIS_CACHE_TTL, json.dumps(cache_data, cls=SafeEncoder))
            except Exception as e:
                logger.warning(f"Cache storage failed: {e}")
                _redis_client = None

        # Record metrics
        MetricsHelper.record_metric("similarity_search_duration", MetricsHelper.get_duration(start_time))
        MetricsHelper.record_metric("similarity_tickets_processed", len(valid_tickets))
        MetricsHelper.record_metric("similarity_best_score", best_similarity)
        
        return result
        
    except ValueError as e:
        logger.error(f"Validation error in similarity search: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in similarity search: {e}")
        ErrorHelper.log_and_raise(e, "Similarity search failed")
        return None


def get_similarity_stats(db: Session) -> Dict[str, Any]:
    """
    Get statistics about the similarity search system.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with similarity system statistics
    """
    try:
        resolved_tickets = get_resolved_tickets(db, limit=100)
        
        stats = {
            "resolved_tickets_count": len(resolved_tickets),
            "cache_enabled": bool(settings.REDIS_URL),
            "similarity_threshold": settings.SIMILARITY_THRESHOLD,
            "redis_connected": bool(_get_cache_client()),
            "max_tickets_processed": MAX_TICKETS_TO_PROCESS
        }
        
        if resolved_tickets:
            # Calculate average message length
            total_length = sum(len(ticket.message or "") for ticket in resolved_tickets)
            stats["average_message_length"] = total_length / len(resolved_tickets)
            
            # Sample a few tickets for processing time estimation
            sample_tickets = resolved_tickets[:10]
            if sample_tickets:
                sample_messages = [{"message": t.message} for t in sample_tickets]
                start_time = MetricsHelper.start_timer()
                find_similar_ticket("test message", sample_messages, 0.5)
                stats["sample_processing_time"] = MetricsHelper.get_duration(start_time)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get similarity stats: {e}")
        return {"error": str(e)}


def clear_similarity_cache() -> bool:
    """
    Clear all similarity search cache entries.
    
    Returns:
        True if cache was cleared successfully
    """
    try:
        cache = _get_cache_client()
        if not cache:
            logger.info("No cache client available")
            return False
        
        # Delete all keys with similarity prefix
        pattern = f"{SIMILARITY_CACHE_PREFIX}:*"
        keys = cache.keys(pattern)
        
        if keys:
            deleted_count = cache.delete(*keys)
            logger.info(f"Cleared {deleted_count} similarity cache entries")
            return True
        else:
            logger.info("No similarity cache entries found")
            return True
            
    except Exception as e:
        logger.error(f"Failed to clear similarity cache: {e}")
        return False
