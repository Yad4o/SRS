"""
app/services/similarity.py  [DEPRECATED]

Deprecated:
This module is a Phase 3 spec alias. Import directly from the canonical module instead:

    from app.services.similarity_search import find_similar_ticket

This file will be removed in a future release.
"""

import warnings

warnings.warn(
    "Importing from 'app.services.similarity' is deprecated. "
    "Use 'app.services.similarity_search' instead. "
    "This alias will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from app.services.similarity_search import find_similar_ticket  # noqa: E402, F401

__all__ = ["find_similar_ticket"]

