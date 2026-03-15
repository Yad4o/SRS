from app.services.decision import decide_resolution


def test_decision_function_exists():
    """
    Ensure decision function is callable.
    """
    assert callable(decide_resolution)


def test_high_confidence_auto_resolve():
    """
    High confidence should auto-resolve.
    """
    decision = decide_resolution(0.9)
    assert decision == "AUTO_RESOLVE"


def test_low_confidence_escalate():
    """
    Low confidence should escalate.
    """
    decision = decide_resolution(0.4)
    assert decision == "ESCALATE"


def test_edge_confidence_threshold():
    """
    Edge case: exactly threshold should auto-resolve.
    """
    decision = decide_resolution(0.75)
    assert decision == "AUTO_RESOLVE"
