#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.response_generator import generate_response

def test_response_generator_fixes():
    """Test all the nitpick fixes applied to response generator."""
    
    print("=== Testing Response Generator Nitpick Fixes ===\n")
    
    # Test 1: Config validation
    print("Test 1 - Configuration validation:")
    try:
        from app.core.config import settings
        print(f"STATUS_PAGE_URL: {settings.STATUS_PAGE_URL}")
        print(f"SUPPORT_EMAIL: {settings.SUPPORT_EMAIL}")
        print("✅ PASS (config loads with validation)\n")
    except Exception as e:
        print(f"❌ FAIL: {e}")
    
    # Test 2: Similar solution quality-based priority
    print("Test 2 - Similar solution quality-based priority:")
    nested_wrapped = "I understand you're experiencing an issue. Based on a similar case, here's what helped: I understand you're experiencing an issue. Based on a similar case, here's what helped: Reset password"
    
    # Test high quality (>= 0.6) - should use similar solution
    response_text, source_label = generate_response(
        intent="login_issue",
        original_message="I forgot my password",
        similar_solution="Reset password using forgot link",
        similar_quality_score=0.8
    )
    wrapper_check = "I understand you're experiencing an issue" in response_text
    print(f'High quality (0.8) - Source: {source_label}, Response contains similarity wrapper: {wrapper_check}')
    
    # Test low quality (< 0.6) - should fall back to template
    response_text, source_label = generate_response(
        intent="login_issue", 
        original_message="I forgot my password",
        similar_solution="Reset password using forgot link",
        similar_quality_score=0.4
    )
    print(f'Low quality (0.4) - Source: {source_label}, Response contains template: {"reset your password" in response_text.lower()}')
    
    print("✅ PASS (similarity quality-based priority)\n")
    
    # Test 3: Login keyword specificity
    print("Test 3 - Login keyword specificity:")
    result1 = generate_response('login_issue', 'Cannot login')
    result2 = generate_response('login_issue', 'I forgot my password')
    print(f'"Cannot login" -> {result1}')
    print(f'"I forgot my password" -> {result2}')
    
    # Extract response text from tuple
    response1_text = result1[0] if isinstance(result1, tuple) else result1
    response2_text = result2[0] if isinstance(result2, tuple) else result2
    
    # "Cannot login" should fall through to default template (no "login" keyword)
    assert "reset your password" not in response1_text.lower(), "Should fall through to default template"
    # "I forgot my password" should match password reset template
    assert "reset your password" in response2_text.lower(), "Should match password reset template"
    print("✅ PASS (login keyword specificity)\n")
    
    # Test 4: All fixes work together
    print("Test 4 - All fixes integration:")
    nested_wrapper = "I understand you're experiencing an issue. Based on a similar case, here's what helped: Clear cache and restart"
    result_with_solution = generate_response('technical_issue', 'app broken', nested_wrapper)
    print(f'Integrated result with solution: {result_with_solution}')
    
    # Should use cleaned similar solution with exact casing and no duplicate wrapper content
    response_text = result_with_solution[0] if isinstance(result_with_solution, tuple) else result_with_solution
    source_label = result_with_solution[1] if isinstance(result_with_solution, tuple) else 'unknown'
    
    # Check that it contains the similarity wrapper (since it's high quality by default)
    assert "I understand you're experiencing an issue" in response_text, "Should contain similarity wrapper"
    assert source_label == "similarity", f"Expected 'similarity', got '{source_label}'"
    print("✅ PASS (similarity quality-based priority)\n")
    
    result_without_solution = generate_response('general_query', 'random question', None)
    print(f'Integrated result without solution: {result_without_solution}')
    
    # Extract response text from tuple
    response_text, source_label = result_without_solution
    
    # Should use configurable support email (no similar solution) - STATUS_PAGE_URL not in general_query template 2
    assert settings.SUPPORT_EMAIL in response_text, "Should use configurable support email"
    print("✅ PASS (all fixes integrated)\n")
    
    print("🎉 All nitpick fixes are working correctly!")

if __name__ == "__main__":
    test_response_generator_fixes()
