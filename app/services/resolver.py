"""
app/services/resolver.py

Purpose:
--------
Response generation — produces the human-readable reply for a resolved ticket.

Note:
-----
Canonical implementation lives in response_generator.py.
This module re-exports it to match the name defined in the Phase 3 spec.
"""

# Canonical implementation — delegates to response_generator.py
from app.services.response_generator import generate_response

__all__ = ["generate_response"]
