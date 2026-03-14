"""
Response Generation Service

This service generates human-readable responses based on intent, original message,
and optionally a similar ticket's solution.

Priority order:
1. Reuse similar_solution if provided
2. Intent-based static templates  
3. Fallback response

Reference: Technical Spec § 9.3 (Response Generation)
Version: 3.3 - Response Generation Implementation
"""

from typing import Optional


class ResponseGenerator:
    """
    Response generation service for customer support tickets.
    
    This component only returns text; it does not update the database 
    or make decisions about auto-resolve vs escalate.
    """
    
    def __init__(self):
        """Initialize the response generator with static response templates."""
        self.response_templates = {
            "login_issue": {
                "primary": "I understand you're having trouble logging in. {similar_solution}",
                "fallback": "I understand you're having trouble logging in. Please try resetting your password using the 'Forgot Password' link on the login page. If you continue to have issues, please contact our support team with your account details."
            },
            "payment_issue": {
                "primary": "I see you're experiencing a payment problem. {similar_solution}",
                "fallback": "I understand you're experiencing a payment problem. Please check that your payment method is valid and has sufficient funds. If the issue persists, contact your bank or try a different payment method. For billing disputes, please reach out to our support team."
            },
            "account_issue": {
                "primary": "I can help with your account request. {similar_solution}",
                "fallback": "I understand you need help with your account. For account changes like email updates or profile modifications, please visit your account settings. For account deletion or sensitive changes, please contact our support team for assistance."
            },
            "technical_issue": {
                "primary": "I'm sorry you're experiencing technical difficulties. {similar_solution}",
                "fallback": "I'm sorry you're experiencing technical difficulties. Please try clearing your browser cache and cookies, then restart your device. If the problem continues, please provide details about when and how the issue occurs so we can investigate further."
            },
            "feature_request": {
                "primary": "Thank you for your suggestion. {similar_solution}",
                "fallback": "Thank you for your suggestion. We appreciate feedback on how to improve our service. Your request has been forwarded to our product team for consideration in future updates. While we can't promise implementation, we value your input."
            },
            "general_query": {
                "primary": "I can help with your question. {similar_solution}",
                "fallback": "I'd be happy to help with your question. Please provide more specific details about what information you need, and I'll do my best to assist you. For common topics, you might also find answers in our FAQ section."
            },
            "unknown": {
                "primary": "I'll do my best to help you. {similar_solution}",
                "fallback": "I'll do my best to help you. Could you please provide more details about your question or issue? This will help me understand how to assist you better."
            }
        }
    
    def generate_response(
        self, 
        intent: str, 
        original_message: str, 
        similar_solution: Optional[str] = None
    ) -> str:
        """
        Generate a human-readable response based on intent and context.
        
        Priority order:
        1. Reuse similar_solution if provided
        2. Intent-based static templates
        3. Fallback response
        
        Args:
            intent: Classified intent of the ticket
            original_message: Original user message
            similar_solution: Optional solution from a similar resolved ticket
            
        Returns:
            str: Generated human-readable response
        """
        # Priority 1: Use similar solution if provided
        if similar_solution and similar_solution.strip():
            template = self.response_templates.get(intent, self.response_templates["unknown"])
            similar_response = template.get("primary", template["fallback"])
            return similar_response.format(similar_solution=similar_solution)
        
        # Priority 2: Use intent-based static template
        template = self.response_templates.get(intent, self.response_templates["unknown"])
        fallback_response = template.get("fallback", self.response_templates["unknown"]["fallback"])
        
        # Priority 3: Fallback (handled by the get method above)
        return fallback_response


# Global instance for easy access
response_generator = ResponseGenerator()


def generate_response(
    intent: str, 
    original_message: str, 
    similar_solution: Optional[str] = None
) -> str:
    """
    Convenience function for response generation.
    
    Args:
        intent: Classified intent of the ticket
        original_message: Original user message  
        similar_solution: Optional solution from a similar resolved ticket
        
    Returns:
        str: Generated human-readable response
        
    Example:
        >>> # With similar solution
        >>> generate_response("login_issue", "can't login", "Try resetting your password")
        "I understand you're having trouble logging in. Try resetting your password"
        
        >>> # Without similar solution
        >>> generate_response("login_issue", "can't login")
        "I understand you're having trouble logging in. Please try resetting your password using the 'Forgot Password' link on the login page. If you continue to have issues, please contact our support team with your account details."
    """
    return response_generator.generate_response(intent, original_message, similar_solution)
