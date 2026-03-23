#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.response_generator import generate_response, _normalize_message, _match_keywords, _clean_similar_solution

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
    
    # Test 2: Wrapper prefix loop removal
    print("Test 2 - Wrapper prefix loop removal:")
    nested_wrapped = "I understand you're experiencing an issue. Based on a similar case, here's what helped: I understand you're experiencing an issue. Based on a similar case, here's what helped: Reset password"
    cleaned = _clean_similar_solution(nested_wrapped)
    print(f'Original: "{nested_wrapped}"')
    print(f'Cleaned: "{cleaned}"')
    expected = "Reset password"
    assert cleaned == expected, f"Expected '{expected}', got '{cleaned}'"
    print("✅ PASS (nested wrapper removal)\n")
    
    # Test 3: Login keyword specificity
    print("Test 3 - Login keyword specificity:")
    result1 = generate_response('login_issue', 'Cannot login')
    result2 = generate_response('login_issue', 'I forgot my password')
    print(f'"Cannot login" -> {result1}')
    print(f'"I forgot my password" -> {result2}')
    
    # "Cannot login" should fall through to default template (no "login" keyword)
    assert "reset your password" not in result1.lower(), "Should fall through to default template"
    # "I forgot my password" should match password reset template
    assert "reset your password" in result2.lower(), "Should match password reset template"
    print("✅ PASS (login keyword specificity)\n")
    
    # Test 4: All fixes work together
    print("Test 4 - All fixes integration:")
    nested_wrapper = "I understand you're experiencing an issue. Based on a similar case, here's what helped: I understand you're experiencing an issue. Based on a similar case, here's what helped: Clear cache and restart"
    result_with_solution = generate_response('technical_issue', 'app broken', nested_wrapper)
    print(f'Integrated result with solution: {result_with_solution}')
    
    # Should use cleaned similar solution with exact casing and no duplicate wrapper content
    assert "Clear cache and restart" in result_with_solution, "Should contain cleaned solution with correct casing"
    assert result_with_solution.count("Clear cache and restart") == 1, "Solution should appear exactly once (no duplicates)"
    assert result_with_solution.count("I understand") == 1, "Wrapper prefix should appear exactly once (no duplicates)"
    assert settings.STATUS_PAGE_URL not in result_with_solution, "Should not contain configurable status URL when similar solution provided"
    
    result_without_solution = generate_response('general_query', 'random question', None)
    print(f'Integrated result without solution: {result_without_solution}')
    
    # Should use configurable support email (no similar solution) - STATUS_PAGE_URL not in general_query template 2
    assert settings.SUPPORT_EMAIL in result_without_solution, "Should use configurable support email"
    print("✅ PASS (all fixes integrated)\n")
    
    print("🎉 All nitpick fixes are working correctly!")

if __name__ == "__main__":
    test_response_generator_fixes()
