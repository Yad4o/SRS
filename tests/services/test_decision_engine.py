import pytest
from app.services.decision_engine import decide_resolution, get_confidence_threshold, set_confidence_threshold
from app.core.config import settings


def test_decide_resolution_auto_resolve():
    """Test confidence >= threshold returns AUTO_RESOLVE."""
    # Above threshold
    result = decide_resolution(0.8)
    assert result == "AUTO_RESOLVE"
    
    # Exactly at threshold
    result = decide_resolution(0.75)
    assert result == "AUTO_RESOLVE"
    
    # High confidence
    result = decide_resolution(1.0)
    assert result == "AUTO_RESOLVE"


def test_decide_resolution_escalate():
    """Test confidence < threshold returns ESCALATE."""
    # Below threshold
    result = decide_resolution(0.7)
    assert result == "ESCALATE"
    
    # Very low confidence
    result = decide_resolution(0.0)
    assert result == "ESCALATE"
    
    # Just below threshold
    result = decide_resolution(0.749)
    assert result == "ESCALATE"


def test_decide_resolution_invalid_confidence():
    """Test invalid confidence returns ESCALATE (safety first)."""
    # Non-numeric types
    result = decide_resolution("invalid")
    assert result == "ESCALATE"
    
    result = decide_resolution(None)
    assert result == "ESCALATE"
    
    result = decide_resolution([])
    assert result == "ESCALATE"
    
    # Boolean (should be rejected even though bool is subclass of int)
    result = decide_resolution(True)
    assert result == "ESCALATE"
    
    result = decide_resolution(False)
    assert result == "ESCALATE"
    
    # Out of range values
    result = decide_resolution(-0.1)
    assert result == "ESCALATE"
    
    result = decide_resolution(1.1)
    assert result == "ESCALATE"
    
    result = decide_resolution(float('inf'))
    assert result == "ESCALATE"
    
    result = decide_resolution(float('-inf'))
    assert result == "ESCALATE"
    
    result = decide_resolution(float('nan'))
    assert result == "ESCALATE"


def test_decide_resolution_edge_cases():
    """Test edge cases around threshold."""
    threshold = get_confidence_threshold()
    
    # Just at threshold
    result = decide_resolution(threshold)
    assert result == "AUTO_RESOLVE"
    
    # Just below threshold
    result = decide_resolution(threshold - 0.001)
    assert result == "ESCALATE"
    
    # Just above threshold
    result = decide_resolution(threshold + 0.001)
    assert result == "AUTO_RESOLVE"


def test_get_confidence_threshold():
    """Test getting the confidence threshold."""
    threshold = get_confidence_threshold()
    assert isinstance(threshold, float)
    assert 0.0 <= threshold <= 1.0
    assert threshold == settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE


def test_set_confidence_threshold():
    """Test setting the confidence threshold."""
    original_threshold = get_confidence_threshold()
    
    try:
        # Set new threshold
        set_confidence_threshold(0.8)
        assert get_confidence_threshold() == 0.8
        
        # Test decision with new threshold
        result = decide_resolution(0.75)  # Should now escalate
        assert result == "ESCALATE"
        
        result = decide_resolution(0.85)  # Should now auto-resolve
        assert result == "AUTO_RESOLVE"
    
    finally:
        # Always restore original threshold
        set_confidence_threshold(original_threshold)
        assert get_confidence_threshold() == original_threshold


def test_set_confidence_threshold_validation():
    """Test validation when setting confidence threshold."""
    original_threshold = get_confidence_threshold()
    
    try:
        # Valid thresholds
        set_confidence_threshold(0.0)
        set_confidence_threshold(0.5)
        set_confidence_threshold(1.0)
        
        # Invalid thresholds
        with pytest.raises(ValueError, match="Threshold must be a numeric value"):
            set_confidence_threshold("invalid")
        
        with pytest.raises(ValueError, match="Threshold must be a numeric value"):
            set_confidence_threshold(None)
        
        with pytest.raises(ValueError, match="Threshold must be a numeric value, not boolean"):
            set_confidence_threshold(True)
        
        with pytest.raises(ValueError, match="Threshold must be between 0.0 and 1.0"):
            set_confidence_threshold(-0.1)
        
        with pytest.raises(ValueError, match="Threshold must be between 0.0 and 1.0"):
            set_confidence_threshold(1.1)
    
    finally:
        # Always restore original threshold
        set_confidence_threshold(original_threshold)


def test_decide_resolution_function():
    """Test the function signature and return types."""
    # Test that function returns correct literal types
    result = decide_resolution(0.8)
    assert result in ["AUTO_RESOLVE", "ESCALATE"]
    
    result = decide_resolution(0.7)
    assert result in ["AUTO_RESOLVE", "ESCALATE"]
    
    # Test with various numeric types
    result = decide_resolution(0.75)  # float
    assert result == "AUTO_RESOLVE"
    
    result = decide_resolution(1)    # int
    assert result == "AUTO_RESOLVE"


def test_decide_resolution_pure_logic():
    """Test that function is pure logic only (no DB, no HTTP)."""
    # Multiple calls with same input should return same result
    result1 = decide_resolution(0.8)
    result2 = decide_resolution(0.8)
    assert result1 == result2
    
    result3 = decide_resolution(0.7)
    result4 = decide_resolution(0.7)
    assert result3 == result4
    
    # Results should be deterministic
    assert result1 != result3  # Different inputs should give different outputs


def test_decide_resolution_safety_first():
    """Test that invalid inputs default to ESCALATE (safety first)."""
    # All these should escalate for safety
    unsafe_inputs = [
        None, "invalid", [], {}, True, False,
        -1.0, 2.0, float('inf'), float('-inf'), float('nan')
    ]
    
    for unsafe_input in unsafe_inputs:
        result = decide_resolution(unsafe_input)
        assert result == "ESCALATE", f"Input {unsafe_input} should ESCALATE for safety"
