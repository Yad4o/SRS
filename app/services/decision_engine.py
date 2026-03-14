"""
Decision Engine Service

This service acts as the safety gate that determines whether a ticket should be 
auto-resolved or escalated to a human based on confidence scores.

Rule: confidence >= threshold → AUTO_RESOLVE, else ESCALATE

Reference: Technical Spec § 9.4 (Decision Engine)
Version: 3.4 - Decision Engine Implementation
"""

from typing import Literal, Optional
from enum import Enum
from numbers import Real
from app.core.config import settings


class ResolutionDecision(Enum):
    """Enum for resolution decision types."""
    AUTO_RESOLVE = "AUTO_RESOLVE"
    ESCALATE = "ESCALATE"


class DecisionEngine:
    """
    Decision engine for ticket resolution.
    
    This is pure logic only—no database operations, no HTTP requests.
    Acts as the safety gate for automated ticket resolution.
    """
    
    def __init__(self, confidence_threshold: Optional[float] = None):
        """
        Initialize the decision engine.
        
        Args:
            confidence_threshold: Minimum confidence score for auto-resolution (0.0-1.0)
                                 If None, uses settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE
            
        Raises:
            ValueError: If confidence_threshold is not between 0.0 and 1.0
        """
        if confidence_threshold is None:
            confidence_threshold = settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE
        
        if not isinstance(confidence_threshold, Real) or isinstance(confidence_threshold, bool):
            raise ValueError(
                f"confidence_threshold must be a numeric value between 0.0 and 1.0, got {confidence_threshold}"
            )
        
        if not (0.0 <= confidence_threshold <= 1.0):
            raise ValueError(
                f"confidence_threshold must be between 0.0 and 1.0, got {confidence_threshold}"
            )
        
        self.confidence_threshold = confidence_threshold
    
    def decide_resolution(self, confidence: float) -> Literal["AUTO_RESOLVE", "ESCALATE"]:
        """
        Determine whether a ticket should be auto-resolved or escalated.
        
        Rule: confidence >= threshold → AUTO_RESOLVE, else ESCALATE
        
        Args:
            confidence: Confidence score from intent classification (0.0-1.0)
            
        Returns:
            Literal["AUTO_RESOLVE", "ESCALATE"]: Resolution decision
            
        Examples:
            >>> engine = DecisionEngine(confidence_threshold=0.8)
            >>> engine.decide_resolution(0.9)
            'AUTO_RESOLVE'
            >>> engine.decide_resolution(0.7)
            'ESCALATE'
            >>> engine.decide_resolution(1.5)  # Invalid confidence
            'ESCALATE'
        """
        # Validation: confidence must be 0.0-1.0
        if not isinstance(confidence, Real) or isinstance(confidence, bool):
            return "ESCALATE"
        
        if not (0.0 <= confidence <= 1.0):
            return "ESCALATE"
        
        # Decision rule
        if confidence >= self.confidence_threshold:
            return "AUTO_RESOLVE"
        else:
            return "ESCALATE"
    
    def get_threshold(self) -> float:
        """
        Get the current confidence threshold.
        
        Returns:
            float: Current confidence threshold
        """
        return self.confidence_threshold
    
    def set_threshold(self, threshold: float) -> None:
        """
        Update the confidence threshold.
        
        Args:
            threshold: New confidence threshold (0.0-1.0)
            
        Raises:
            ValueError: If threshold is not between 0.0 and 1.0
        """
        if not isinstance(threshold, Real) or isinstance(threshold, bool):
            raise ValueError(
                f"threshold must be a numeric value between 0.0 and 1.0, got {threshold}"
            )
        
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(
                f"threshold must be between 0.0 and 1.0, got {threshold}"
            )
        
        self.confidence_threshold = threshold


# Global instance with default settings
decision_engine = DecisionEngine()


def decide_resolution(confidence: float) -> Literal["AUTO_RESOLVE", "ESCALATE"]:
    """
    Convenience function for resolution decision.
    
    Args:
        confidence: Confidence score from intent classification (0.0-1.0)
        
    Returns:
        Literal["AUTO_RESOLVE", "ESCALATE"]: Resolution decision
        
    Example:
        >>> decide_resolution(0.8)
        'AUTO_RESOLVE'
        >>> decide_resolution(0.7)
        'ESCALATE'
        >>> decide_resolution(-0.1)  # Invalid confidence
        'ESCALATE'
    """
    return decision_engine.decide_resolution(confidence)


def get_confidence_threshold() -> float:
    """
    Get the current confidence threshold.
    
    Returns:
        float: Current confidence threshold
    """
    return decision_engine.get_threshold()


def set_confidence_threshold(threshold: float) -> None:
    """
    Update the confidence threshold.
    
    Args:
        threshold: New confidence threshold (0.0-1.0)
        
    Raises:
        ValueError: If threshold is not between 0.0 and 1.0
    """
    decision_engine.set_threshold(threshold)
