"""
app/services/similarity.py

Purpose:
--------
Re-export of find_similar_ticket to match the module name defined in the Phase 3 spec.
Canonical implementation lives in similarity_search.py.

Owner:
------
Prajwal (AI / NLP / Similarity Search)
"""

# Canonical implementation — delegates to similarity_search.py
from app.services.similarity_search import find_similar_ticket

__all__ = ["find_similar_ticket"]
