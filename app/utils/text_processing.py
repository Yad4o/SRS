"""
app/utils/text_processing.py

Shared text processing utilities for TF-IDF tokenization.
"""

import math
import re
from typing import Dict, List
from collections import Counter
from app.utils.service_helpers import ValidationHelper

def tokenize(text: str) -> List[str]:
    """
    Tokenize text into lowercase words.
    
    Args:
        text: Input text to tokenize
        
    Returns:
        List of lowercase tokens
    """
    if not text or not isinstance(text, str):
        return []
    
    # Use validation helper to sanitize input
    text = ValidationHelper.sanitize_string(text)
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def compute_idf(corpus: List[str]) -> Dict[str, float]:
    """
    Precompute IDF scores for all texts in corpus.
    
    Args:
        corpus: All texts in corpus
        
    Returns:
        Dictionary of word -> IDF score
    """
    total_docs = len(corpus)
    doc_counts = Counter()
    
    # Count documents containing each word
    for doc_text in corpus:
        doc_tokens = set(tokenize(doc_text))
        for token in doc_tokens:
            doc_counts[token] += 1
    
    # Calculate IDF for each word
    idf_scores = {}
    for word in doc_counts:
        idf = math.log((total_docs + 1) / (doc_counts[word] + 1)) + 1
        idf_scores[word] = idf
    
    return idf_scores


def tf_idf_vector(text: str, idf: Dict[str, float]) -> Dict[str, float]:
    """Return the TF-IDF vector for text given precomputed idf scores."""
    tokens = tokenize(text)
    if not tokens:
        return {}
    tf = Counter(tokens)
    total = len(tokens)
    return {word: (count / total) * idf.get(word, 1.0) for word, count in tf.items()}

