import json
import math
import re
from collections import Counter
from typing import Dict, List, Optional

from app.core.config import settings
from app.models.ticket import Ticket
from app.utils.service_helpers import CacheHelper, ErrorHelper, MetricsHelper
from sqlalchemy.orm import Session


class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that serialises datetime objects to ISO strings."""

    def default(self, obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return super().default(obj)


# Alias used internally
SafeEncoder = _SafeEncoder

# Redis client singleton for lazy load
_redis_client = None


def _get_cache_client():
    """Return a Redis client if REDIS_URL is configured, else None."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not settings.REDIS_URL:
        return None
        
    try:
        import redis
        _redis_client = redis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_timeout=1
        )
        return _redis_client
    except Exception as e:
        ErrorHelper.log_and_raise(e, "Failed to create Redis client")
        _redis_client = None  # Don't cache the failure
        return None


def _cache_key(message: str) -> str:
    """Generate a cache key from the message content."""
    return CacheHelper.make_cache_key("srs:similarity", message)[:32]


def _tokenize(text: str) -> List[str]:
    """
    Tokenize text into words.
    
    Args:
        text: Input text to tokenize
        
    Returns:
        List of lowercase tokens
    """
    if not text or not isinstance(text, str):
        return []
    
    # Use validation helper to sanitize input
    from app.utils.service_helpers import ValidationHelper
    text = ValidationHelper.sanitize_string(text)
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def _compute_idf(all_texts: List[str]) -> Dict[str, float]:
    """
    Precompute IDF scores for all texts in corpus.
    
    Args:
        all_texts: All texts in corpus
        
    Returns:
        Dictionary of word -> IDF score
    """
    total_docs = len(all_texts)
    doc_counts = Counter()
    
    # Count documents containing each word
    for doc_text in all_texts:
        doc_tokens = set(_tokenize(doc_text))
        for token in doc_tokens:
            doc_counts[token] += 1
    
    # Calculate IDF for each word
    idf_scores = {}
    for word in doc_counts:
        idf = math.log((total_docs + 1) / (doc_counts[word] + 1)) + 1
        idf_scores[word] = idf
    
    return idf_scores


def _calculate_tf(text: str) -> Dict[str, float]:
    """
    Calculate term frequency (TF) for a text.
    
    Args:
        text: The text to calculate TF for
        
    Returns:
        Dictionary of word -> TF score
    """
    tokens = _tokenize(text)
    if not tokens:
        return {}
    
    tf = Counter(tokens)
    total_tokens = len(tokens)
    tf_scores = {word: count / total_tokens for word, count in tf.items()}
    
    return tf_scores


def _apply_idf(tf_scores: Dict[str, float], idf_scores: Dict[str, float]) -> Dict[str, float]:
    """
    Apply IDF scores to TF scores to get TF-IDF.
    
    Args:
        tf_scores: Term frequency scores
        idf_scores: Precomputed IDF scores
        
    Returns:
        Dictionary of word -> TF-IDF score
    """
    tfidf_scores = {}
    for word, tf_score in tf_scores.items():
        tfidf_scores[word] = tf_score * idf_scores.get(word, 1)
    
    return tfidf_scores


def _calculate_tf_idf(text: str, all_texts: List[str]) -> Dict[str, float]:
    """
    Calculate TF-IDF scores for a text against a corpus.
    
    Args:
        text: The text to calculate TF-IDF for
        all_texts: All texts in the corpus (for backward compatibility)
        
    Returns:
        Dictionary of word -> TF-IDF score
    """
    # For backward compatibility, compute IDF on the fly
    idf_scores = _compute_idf(all_texts)
    tf_scores = _calculate_tf(text)
    return _apply_idf(tf_scores, idf_scores)


def _cosine_similarity(tfidf1: Dict[str, float], tfidf2: Dict[str, float]) -> float:
    """
    Calculate cosine similarity between two TF-IDF vectors.
    
    Args:
        tfidf1: First TF-IDF vector
        tfidf2: Second TF-IDF vector
        
    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    # Get all unique words
    all_words = set(tfidf1.keys()) | set(tfidf2.keys())
    
    if not all_words:
        return 0.0
    
    # Calculate dot product
    dot_product = sum(tfidf1.get(word, 0) * tfidf2.get(word, 0) for word in all_words)
    
    # Calculate magnitudes
    magnitude1 = math.sqrt(sum(tfidf1.get(word, 0) ** 2 for word in all_words))
    magnitude2 = math.sqrt(sum(tfidf2.get(word, 0) ** 2 for word in all_words))
    
    # Calculate cosine similarity
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def get_resolved_tickets(db: Session) -> List[Ticket]:
    """Fetch recent successfully resolved tickets for similarity search."""
    return (
        db.query(Ticket)
        .filter(
            Ticket.status == "auto_resolved",
            Ticket.response.isnot(None),
        )
        .order_by(Ticket.created_at.desc())
        .limit(50)
        .all()
    )


def find_similar_ticket(new_message: str, resolved_tickets: List[Dict], similarity_threshold: float = None) -> Optional[Dict]:
    """
    Find the most similar resolved ticket to a new ticket message.
    
    This function implements similarity search to find previously resolved tickets that match
    a new ticket's message. If a similar resolved ticket exists, its solution can be reused.
    Reference: Technical Spec § 9.2 (Similarity Search)
    
    Args:
        new_message: The new ticket message to find matches for
        resolved_tickets: List of resolved ticket objects with 'message' and optionally 'response'
        similarity_threshold: Minimum similarity score to consider a match (default: 0.7)
        
    Returns:
        Dict with {"matched_text": str, "similarity_score": float} or None if no match above threshold
    """
    global _redis_client
    if not new_message or not isinstance(new_message, str):
        return None
    
    if not resolved_tickets or not isinstance(resolved_tickets, list):
        return None

    # Try cache first
    cache = _get_cache_client()
    key = _cache_key(new_message) if cache else None

    # Validate similarity_threshold parameter
    if similarity_threshold is None:
        similarity_threshold = settings.SIMILARITY_THRESHOLD
    if not isinstance(similarity_threshold, (int, float)):
        raise ValueError("similarity_threshold must be a numeric value")
    if not (0.0 <= similarity_threshold <= 1.0):
        raise ValueError("similarity_threshold must be between 0.0 and 1.0")

    # Check cache hit (threshold-independent)
    if cache and key:
        try:
            cached = cache.get(key)
            if cached is not None:
                cached_data = json.loads(cached)
                # Apply current threshold to cached raw result
                if cached_data and cached_data.get("similarity_score", 0.0) >= similarity_threshold:
                    return cached_data
                return None # Message is in cache but doesn't meet this threshold
        except Exception:
            _redis_client = None
            pass

    # Extract messages from resolved tickets
    ticket_messages = []
    for ticket in resolved_tickets:
        if isinstance(ticket, dict) and "message" in ticket:
            message = ticket["message"]
            if isinstance(message, str) and message.strip() != "":
                ticket_messages.append(message.strip())

    if not ticket_messages:
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

    for i, ticket in enumerate(resolved_tickets):
        if not isinstance(ticket, dict) or "message" not in ticket:
            continue

        ticket_message = ticket["message"]
        if not isinstance(ticket_message, str) or ticket_message.strip() == "":
            continue

        # Calculate TF-IDF for this ticket
        ticket_tf = _calculate_tf(ticket_message)
        ticket_tfidf = _apply_idf(ticket_tf, idf_scores)

        # Calculate cosine similarity
        similarity = _cosine_similarity(new_tfidf, ticket_tfidf)

        if similarity > best_similarity or (best_similarity == 0.0 and similarity == 0.0):
            best_similarity = similarity
            best_match = ticket_message
            best_ticket = ticket

    # Prepare raw result (best match found, for caching)
    raw_result = None
    if best_match:
        raw_result = {
            "matched_text": best_match,
            "similarity_score": round(best_similarity, 3),
            "ticket": best_ticket,
            "quality_score": best_ticket.get("quality_score"),
        }

    # Record raw result to cache (threshold-independent)
    if cache and key:
        try:
            # We always cache the best found match so future calls with lower thresholds can use it
            cache.setex(key, 300, json.dumps(raw_result, cls=SafeEncoder))
        except Exception:
            _redis_client = None
            pass

    # Check if raw result meets the requested threshold for THIS call
    if raw_result and raw_result["similarity_score"] >= similarity_threshold:
        return raw_result
    
    return None
