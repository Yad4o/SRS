import re
import math
from typing import Dict, List, Optional
from collections import Counter


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
    
    # Convert to lowercase and split on non-word characters
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def _calculate_tf_idf(text: str, all_texts: List[str]) -> Dict[str, float]:
    """
    Calculate TF-IDF scores for a text against a corpus.
    
    Args:
        text: The text to calculate TF-IDF for
        all_texts: All texts in the corpus
        
    Returns:
        Dictionary of word -> TF-IDF score
    """
    tokens = _tokenize(text)
    if not tokens:
        return {}
    
    # Calculate term frequency (TF)
    tf = Counter(tokens)
    total_tokens = len(tokens)
    tf_scores = {word: count / total_tokens for word, count in tf.items()}
    
    # Calculate inverse document frequency (IDF)
    total_docs = len(all_texts)
    idf_scores = {}
    
    # Count documents containing each word
    doc_counts = Counter()
    for doc_text in all_texts:
        doc_tokens = set(_tokenize(doc_text))
        for token in doc_tokens:
            doc_counts[token] += 1
    
    # Calculate IDF for each word in our text
    for word in tf_scores:
        if doc_counts[word] > 0:
            # Use log(total_docs / doc_count) + 1 to avoid zero
            idf = math.log((total_docs + 1) / (doc_counts[word] + 1)) + 1
        else:
            idf = math.log(total_docs + 1) + 1  # Word not in any document
        idf_scores[word] = idf
    
    # Calculate TF-IDF
    tfidf_scores = {}
    for word, tf_score in tf_scores.items():
        tfidf_scores[word] = tf_score * idf_scores.get(word, 1)
    
    return tfidf_scores


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


def find_similar_ticket(new_message: str, resolved_tickets: List[Dict], similarity_threshold: float = 0.7) -> Optional[Dict]:
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
    if not new_message or not isinstance(new_message, str):
        return None
    
    if not resolved_tickets or not isinstance(resolved_tickets, list):
        return None
    
    # Extract messages from resolved tickets
    ticket_messages = []
    for ticket in resolved_tickets:
        if isinstance(ticket, dict) and 'message' in ticket:
            ticket_messages.append(ticket['message'])
    
    if not ticket_messages:
        return None
    
    # Calculate TF-IDF for new message
    new_tfidf = _calculate_tf_idf(new_message, [new_message] + ticket_messages)
    
    # Find best match
    best_match = None
    best_similarity = 0.0
    best_ticket = None
    
    for i, ticket in enumerate(resolved_tickets):
        if not isinstance(ticket, dict) or 'message' not in ticket:
            continue
            
        ticket_message = ticket['message']
        
        # Calculate TF-IDF for this ticket
        ticket_tfidf = _calculate_tf_idf(ticket_message, [new_message] + ticket_messages)
        
        # Calculate cosine similarity
        similarity = _cosine_similarity(new_tfidf, ticket_tfidf)
        
        # Update best match if this is better
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = ticket_message
            best_ticket = ticket
    
    # Check if best match meets threshold
    if best_match and best_similarity >= similarity_threshold:
        return {
            "matched_text": best_match,
            "similarity_score": round(best_similarity, 3),
            "ticket": best_ticket  # Include the original ticket for access to response/solution
        }
    
    return None
