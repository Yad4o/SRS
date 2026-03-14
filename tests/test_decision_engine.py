"""
Tests for decision engine service.

Tests cover all decision logic, validation, edge cases, and settings.
Version: 3.4 - Decision Engine Tests
"""

import pytest
from app.services.decision_engine import DecisionEngine, ResolutionDecision, decide_resolution, get_confidence_threshold, set_confidence_threshold
from app.core.config import settings


class TestDecisionEngine:
    """Test cases for decision engine service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = DecisionEngine()
    
    def test_initialization_default_threshold(self):
        """Test initialization with default threshold."""
        engine = DecisionEngine()
        assert engine.confidence_threshold == settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE
    
    def test_initialization_custom_threshold(self):
        """Test initialization with custom threshold."""
        engine = DecisionEngine(confidence_threshold=0.8)
        assert engine.confidence_threshold == 0.8
    
    def test_initialization_invalid_threshold(self):
        """Test initialization with invalid threshold."""
        with pytest.raises(ValueError) as exc_info:
            DecisionEngine(confidence_threshold=1.5)
        assert "confidence_threshold must be between 0.0 and 1.0" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            DecisionEngine(confidence_threshold=-0.1)
        assert "confidence_threshold must be between 0.0 and 1.0" in str(exc_info.value)
        
        # Boolean values should be rejected
        with pytest.raises(ValueError) as exc_info:
            DecisionEngine(confidence_threshold=True)
        assert "confidence_threshold must be a numeric value between 0.0 and 1.0" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            DecisionEngine(confidence_threshold=False)
        assert "confidence_threshold must be a numeric value between 0.0 and 1.0" in str(exc_info.value)
    
    def test_decide_resolution_auto_resolve(self):
        """Test auto-resolve decision."""
        engine = DecisionEngine(confidence_threshold=0.8)
        
        # High confidence should auto-resolve
        assert engine.decide_resolution(0.9) == "AUTO_RESOLVE"
        assert engine.decide_resolution(0.8) == "AUTO_RESOLVE"
        assert engine.decide_resolution(1.0) == "AUTO_RESOLVE"
    
    def test_decide_resolution_escalate(self):
        """Test escalate decision."""
        engine = DecisionEngine(confidence_threshold=0.8)
        
        # Low confidence should escalate
        assert engine.decide_resolution(0.7) == "ESCALATE"
        assert engine.decide_resolution(0.5) == "ESCALATE"
        assert engine.decide_resolution(0.0) == "ESCALATE"
    
    def test_decide_resolution_boundary_conditions(self):
        """Test boundary conditions around threshold."""
        engine = DecisionEngine(confidence_threshold=0.75)
        
        # Exactly at threshold should auto-resolve
        assert engine.decide_resolution(0.75) == "AUTO_RESOLVE"
        
        # Just below threshold should escalate
        assert engine.decide_resolution(0.7499) == "ESCALATE"
        
        # Just above threshold should auto-resolve
        assert engine.decide_resolution(0.7501) == "AUTO_RESOLVE"
    
    def test_decide_resolution_invalid_confidence_types(self):
        """Test invalid confidence types."""
        engine = DecisionEngine()
        
        # Non-numeric types should escalate
        assert engine.decide_resolution(None) == "ESCALATE"
        assert engine.decide_resolution("high") == "ESCALATE"
        assert engine.decide_resolution([]) == "ESCALATE"
        assert engine.decide_resolution({}) == "ESCALATE"
        
        # Boolean types should escalate (bool is subclass of int but should be rejected)
        assert engine.decide_resolution(True) == "ESCALATE"
        assert engine.decide_resolution(False) == "ESCALATE"
    
    def test_decide_resolution_invalid_confidence_values(self):
        """Test invalid confidence values."""
        engine = DecisionEngine()
        
        # Out of range values should escalate
        assert engine.decide_resolution(-0.1) == "ESCALATE"
        assert engine.decide_resolution(-1.0) == "ESCALATE"
        assert engine.decide_resolution(1.1) == "ESCALATE"
        assert engine.decide_resolution(2.0) == "ESCALATE"
        assert engine.decide_resolution(float('inf')) == "ESCALATE"
        assert engine.decide_resolution(float('-inf')) == "ESCALATE"
    
    def test_decide_resolution_edge_numeric_values(self):
        """Test edge numeric values."""
        engine = DecisionEngine(confidence_threshold=0.5)
        
        # Zero should escalate unless threshold is 0
        assert engine.decide_resolution(0.0) == "ESCALATE"
        
        # One should always auto-resolve
        assert engine.decide_resolution(1.0) == "AUTO_RESOLVE"
        
        # Very small positive numbers
        assert engine.decide_resolution(0.0001) == "ESCALATE"
        
        # Very close to 1
        assert engine.decide_resolution(0.9999) == "AUTO_RESOLVE"
    
    def test_get_threshold(self):
        """Test getting the current threshold."""
        engine = DecisionEngine(confidence_threshold=0.85)
        assert engine.get_threshold() == 0.85
    
    def test_set_threshold_valid(self):
        """Test setting a valid threshold."""
        engine = DecisionEngine()
        
        engine.set_threshold(0.9)
        assert engine.get_threshold() == 0.9
        
        engine.set_threshold(0.0)
        assert engine.get_threshold() == 0.0
        
        engine.set_threshold(1.0)
        assert engine.get_threshold() == 1.0
    
    def test_set_threshold_invalid(self):
        """Test setting an invalid threshold."""
        engine = DecisionEngine()
        
        with pytest.raises(ValueError) as exc_info:
            engine.set_threshold(1.5)
        assert "threshold must be between 0.0 and 1.0" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            engine.set_threshold(-0.1)
        assert "threshold must be between 0.0 and 1.0" in str(exc_info.value)
        
        # Boolean values should be rejected
        with pytest.raises(ValueError) as exc_info:
            engine.set_threshold(True)
        assert "threshold must be a numeric value between 0.0 and 1.0" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            engine.set_threshold(False)
        assert "threshold must be a numeric value between 0.0 and 1.0" in str(exc_info.value)
    
    def test_threshold_affects_decisions(self):
        """Test that changing threshold affects decisions."""
        engine = DecisionEngine(confidence_threshold=0.5)
        
        # With low threshold, 0.6 should auto-resolve
        assert engine.decide_resolution(0.6) == "AUTO_RESOLVE"
        
        # Change to higher threshold
        engine.set_threshold(0.8)
        
        # Now 0.6 should escalate
        assert engine.decide_resolution(0.6) == "ESCALATE"
        
        # But 0.9 should still auto-resolve
        assert engine.decide_resolution(0.9) == "AUTO_RESOLVE"


class TestSettings:
    """Test cases for settings configuration."""
    
    def test_default_settings_threshold(self):
        """Test default settings threshold."""
        assert settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE == 0.75
    
    def test_global_engine_uses_settings(self):
        """Test that global engine uses default settings."""
        from app.services.decision_engine import decision_engine
        assert decision_engine.get_threshold() == settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_decide_resolution_function(self):
        """Test the convenience function."""
        # Should use default confidence_threshold of 0.75
        assert decide_resolution(0.8) == "AUTO_RESOLVE"
        assert decide_resolution(0.7) == "ESCALATE"
        assert decide_resolution(0.75) == "AUTO_RESOLVE"
    
    def test_get_threshold_function(self):
        """Test get threshold convenience function."""
        threshold = get_confidence_threshold()
        assert isinstance(threshold, float)
        assert 0.0 <= threshold <= 1.0
        assert threshold == settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE
    
    def test_set_threshold_function(self):
        """Test the set threshold convenience function."""
        original_threshold = get_confidence_threshold()
        
        try:
            # Set new threshold
            set_confidence_threshold(0.9)
            assert get_confidence_threshold() == 0.9
            
            # Verify decisions use new threshold
            assert decide_resolution(0.8) == "ESCALATE"
            assert decide_resolution(0.95) == "AUTO_RESOLVE"
        finally:
            # Always restore original threshold
            set_confidence_threshold(original_threshold)
            assert get_confidence_threshold() == original_threshold
    
    def test_set_threshold_function_invalid(self):
        """Test setting invalid threshold via convenience function."""
        with pytest.raises(ValueError) as exc_info:
            set_confidence_threshold(1.5)
        assert "threshold must be between 0.0 and 1.0" in str(exc_info.value)
        
        # Boolean values should be rejected
        with pytest.raises(ValueError) as exc_info:
            set_confidence_threshold(True)
        assert "threshold must be a numeric value between 0.0 and 1.0" in str(exc_info.value)


class TestDecisionEngineEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_floating_point_precision(self):
        """Test floating point precision handling."""
        engine = DecisionEngine(confidence_threshold=0.3333333333)
        
        # Should handle floating point comparisons correctly
        assert engine.decide_resolution(0.3333333333) == "AUTO_RESOLVE"
        assert engine.decide_resolution(0.3333333332) == "ESCALATE"
    
    def test_multiple_decisions_consistency(self):
        """Test that multiple decisions are consistent."""
        engine = DecisionEngine(confidence_threshold=0.7)
        confidence = 0.8
        
        # Multiple calls should return same result
        for _ in range(10):
            assert engine.decide_resolution(confidence) == "AUTO_RESOLVE"
    
    def test_state_isolation(self):
        """Test that different engines maintain separate state."""
        engine1 = DecisionEngine(confidence_threshold=0.5)
        engine2 = DecisionEngine(confidence_threshold=0.9)
        
        confidence = 0.7
        assert engine1.decide_resolution(confidence) == "AUTO_RESOLVE"
        assert engine2.decide_resolution(confidence) == "ESCALATE"
        
        # Changing one shouldn't affect the other
        engine1.set_threshold(0.8)
        assert engine1.decide_resolution(confidence) == "ESCALATE"
        assert engine2.decide_resolution(confidence) == "ESCALATE"  # Still uses 0.9
    
    def test_return_type_literal(self):
        """Test that return types are correct literals."""
        engine = DecisionEngine()
        
        result1 = engine.decide_resolution(0.9)
        result2 = engine.decide_resolution(0.5)
        
        assert isinstance(result1, str)
        assert isinstance(result2, str)
        assert result1 == "AUTO_RESOLVE"
        assert result2 == "ESCALATE"
    
    def test_resolution_decision_enum(self):
        """Test the ResolutionDecision enum."""
        assert ResolutionDecision.AUTO_RESOLVE.value == "AUTO_RESOLVE"
        assert ResolutionDecision.ESCALATE.value == "ESCALATE"
        
        # Can create enum instances
        auto = ResolutionDecision.AUTO_RESOLVE
        escalate = ResolutionDecision.ESCALATE
        
        assert auto.value == "AUTO_RESOLVE"
        assert escalate.value == "ESCALATE"


class TestDecisionEngineIntegration:
    """Integration tests for decision engine."""
    
    def test_integration_with_settings(self):
        """Test integration with settings module."""
        # Create engine with settings
        engine = DecisionEngine(settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE)
        
        # Test decisions align with settings
        assert engine.decide_resolution(settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE) == "AUTO_RESOLVE"
        assert engine.decide_resolution(settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE - 0.01) == "ESCALATE"
    
    def test_full_workflow_simulation(self):
        """Test a full workflow simulation."""
        # Simulate different confidence scores from intent classifier
        confidence_scores = [0.9, 0.8, 0.75, 0.7, 0.6, 0.5]
        engine = DecisionEngine(confidence_threshold=0.75)
        
        decisions = []
        for confidence in confidence_scores:
            decision = engine.decide_resolution(confidence)
            decisions.append((confidence, decision))
        
        # Verify expected pattern
        expected = [
            (0.9, "AUTO_RESOLVE"),
            (0.8, "AUTO_RESOLVE"),
            (0.75, "AUTO_RESOLVE"),
            (0.7, "ESCALATE"),
            (0.6, "ESCALATE"),
            (0.5, "ESCALATE")
        ]
        
        assert decisions == expected
    
    def test_performance_considerations(self):
        """Test that the engine is efficient for repeated calls."""
        engine = DecisionEngine()
        
        # Many rapid calls should work efficiently
        for i in range(1000):
            confidence = i % 100 / 100.0  # 0.0 to 0.99
            decision = engine.decide_resolution(confidence)
            assert decision in ["AUTO_RESOLVE", "ESCALATE"]
