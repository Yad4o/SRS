"""
app/services/decision.py  [DEPRECATED]

Deprecated:
This module is a Phase 3 spec alias. Import directly from the canonical module instead:

    from app.services.decision_engine import decide_resolution, get_confidence_threshold, set_confidence_threshold

This file will be removed in a future release.
"""

import warnings

warnings.warn(
    "Importing from 'app.services.decision' is deprecated. "
    "Use 'app.services.decision_engine' instead. "
    "This alias will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from app.services.decision_engine import decide_resolution, get_confidence_threshold, set_confidence_threshold  # noqa: E402, F401

__all__ = ["decide_resolution", "get_confidence_threshold", "set_confidence_threshold"]

