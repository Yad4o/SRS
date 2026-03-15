"""
app/services/decision.py

Purpose:
--------
Decision engine — determines whether a ticket should be auto-resolved or escalated.

Note:
-----
Canonical implementation lives in decision_engine.py.
This module re-exports it to match the name defined in the Phase 3 spec.
"""

# Canonical implementation — delegates to decision_engine.py
from app.services.decision_engine import decide_resolution, get_confidence_threshold, set_confidence_threshold

__all__ = ["decide_resolution", "get_confidence_threshold", "set_confidence_threshold"]
