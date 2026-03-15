from typing import Literal
from app.core.config import settings


def decide_resolution(confidence: float) -> Literal["AUTO_RESOLVE", "ESCALATE"]:
    """
    Decide whether a ticket should be auto-resolved or escalated to a human.
    
    This is the safety gate that determines if AI-generated responses are
    confident enough for automatic resolution or need human intervention.
    Reference: Technical Spec § 9.4 (Decision Engine)
    
    Args:
        confidence: Confidence score from intent classification (0.0-1.0)
        
    Returns:
        Literal["AUTO_RESOLVE", "ESCALATE"]: Decision string
        
    Rules:
    - confidence >= threshold → AUTO_RESOLVE
    - confidence < threshold → ESCALATE
    - invalid/missing confidence → ESCALATE (safety first)
    """
    
    # Validation: confidence must be 0.0-1.0; invalid → ESCALATE
    if not isinstance(confidence, (int, float)):
        return "ESCALATE"
    
    if isinstance(confidence, bool):  # bool is subclass of int, but we don't want it
        return "ESCALATE"
    
    if not (0.0 <= confidence <= 1.0):
        return "ESCALATE"
    
    # Rule: confidence >= threshold → AUTO_RESOLVE, else ESCALATE
    threshold = settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE
    
    if confidence >= threshold:
        return "AUTO_RESOLVE"
    else:
        return "ESCALATE"


# Convenience functions for testing and external use
def get_confidence_threshold() -> float:
    """Get the current confidence threshold for auto-resolution."""
    return settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE


def set_confidence_threshold(threshold: float) -> None:
    """
    Set the confidence threshold for auto-resolution.
    
    Note: This is for testing/configuration purposes only.
    In production, the threshold should come from settings.
    """
    if not isinstance(threshold, (int, float)):
        raise ValueError("Threshold must be a numeric value")
    
    if isinstance(threshold, bool):
        raise ValueError("Threshold must be a numeric value, not boolean")
    
    if not (0.0 <= threshold <= 1.0):
        raise ValueError("Threshold must be between 0.0 and 1.0")
    
    # Update the settings object (for testing only)
    settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE = threshold
