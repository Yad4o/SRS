from enum import Enum


class ResolutionDecision(str, Enum):
    AUTO_RESOLVE = "auto_resolve"
    ESCALATE = "escalate"


# Confidence threshold
AUTO_RESOLVE_CONFIDENCE_THRESHOLD = 0.75


def decide_resolution(
    confidence: float,
    similar_solution_found: bool = False,
):
    """
    Decide whether a ticket should be auto-resolved or escalated.

    Rules (as per tests):
    - confidence < 0.75  -> ESCALATE
    - confidence == 0.75 -> AUTO_RESOLVE
    - confidence > 0.75  -> AUTO_RESOLVE
    """

    # Low confidence → escalate
    if confidence < AUTO_RESOLVE_CONFIDENCE_THRESHOLD:
        return ResolutionDecision.ESCALATE

    # Edge case & high confidence → auto resolve
    return ResolutionDecision.AUTO_RESOLVE
