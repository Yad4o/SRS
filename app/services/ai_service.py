"""
app/services/ai_service.py

Purpose:
Example AI service implementation with fallback handling.

Responsibilities:
- Demonstrate AI service failure handling
- Implement fallback responses for AI failures
- Show proper error logging without exposing details
- Return 200 with fallback when AI services fail

DO NOT:
- Expose AI service internal errors to clients
- Return 500 errors for AI service failures
- Skip logging AI service failures
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from app.core.exceptions import AIServiceError
from app.core.error_handlers import handle_ai_service_failure
from app.services.classifier import classify_intent

logger = logging.getLogger(__name__)


class BaseAIService(ABC):
    """Base class for AI services with fallback handling."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
    
    @abstractmethod
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response when AI service fails."""
        pass
    
    def safe_execute(
        self,
        operation: str,
        ai_function,
        fallback_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Safely execute AI function with fallback handling.
        
        Args:
            operation: Description of the AI operation
            ai_function: The AI function to execute
            fallback_data: Optional fallback data
            **kwargs: Arguments to pass to AI function
            
        Returns:
            Response with AI result or fallback
        """
        try:
            # Attempt to execute AI function
            result = ai_function(**kwargs)
            
            logger.info(f"AI service '{self.service_name}' succeeded for operation: {operation}")
            
            return {
                "data": result,
                "fallback_used": False,
                "service": self.service_name
            }
            
        except Exception as e:
            # Log the AI service failure
            error_details = {
                "service": self.service_name,
                "operation": operation,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            
            logger.warning(
                f"AI service '{self.service_name}' failed for operation '{operation}': {e}"
            )
            
            # Use provided fallback or generate one
            if fallback_data is None:
                fallback_data = self.get_fallback_response(operation, **kwargs)
            
            # Return fallback response
            return handle_ai_service_failure(
                operation=operation,
                fallback_data=fallback_data,
                error_details=error_details
            )


class TicketClassificationService(BaseAIService):
    """AI service for ticket classification with fallback."""
    
    def __init__(self):
        super().__init__("ticket_classifier")
    
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response for ticket classification."""
        return {
            "intent": "general",
            "confidence": 0.5,
            "escalate": True,
            "message": "Unable to classify ticket automatically"
        }
    
    def classify_ticket(self, message: str) -> Dict[str, Any]:
        """
        Classify ticket intent using AI.
        
        Args:
            message: Ticket message to classify
            
        Returns:
            Classification result or fallback (backwards compatible)
        """
        def ai_classify(message: str) -> Dict[str, Any]:
            # Simulate AI classification (in real implementation, this would call an AI model)
            return classify_intent(message)
        
        return self.safe_execute(
            operation="ticket_classification",
            ai_function=ai_classify,
            message=message
        )


class ResponseGenerationService(BaseAIService):
    """AI service for response generation with fallback."""
    
    def __init__(self):
        super().__init__("response_generator")
    
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response for response generation."""
        return {
            "response": "I'm sorry, I'm having trouble generating a response right now. Your ticket has been escalated to a human agent.",
            "confidence": 0.0,
            "escalate": True
        }
    
    def generate_response(self, intent: str, message: str) -> Dict[str, Any]:
        """
        Generate response using AI.
        
        Args:
            intent: Classified ticket intent
            message: Original ticket message
            
        Returns:
            Generated response or fallback
        """
        def ai_generate(intent: str, message: str) -> Dict[str, Any]:
            # Simulate AI response generation (in real implementation, this would call an AI model)
            from app.services.response_generator import generate_response
            
            response_text, response_source = generate_response(
                intent=intent,
                original_message=message,
                similar_solution=None,
                sub_intent=None,
                similar_quality_score=None
            )
            
            return {
                "response": response_text,
                "source": response_source,
                "confidence": 0.85,
                "escalate": intent == "payment_issue"
            }
        
        return self.safe_execute(
            operation="response_generation",
            ai_function=ai_generate,
            intent=intent,
            message=message
        )


class SentimentAnalysisService(BaseAIService):
    """AI service for sentiment analysis with fallback."""
    
    def __init__(self):
        super().__init__("sentiment_analyzer")
    
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response for sentiment analysis."""
        return {
            "sentiment": "neutral",
            "confidence": 0.5,
            "escalate": True
        }
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment using AI.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment analysis result or fallback
        """
        def ai_analyze(text: str) -> Dict[str, Any]:
            # Simulate AI sentiment analysis (in real implementation, this would call an AI model)
            negative_words = ["angry", "frustrated", "terrible", "awful", "hate"]
            positive_words = ["happy", "great", "excellent", "love", "wonderful"]
            
            text_lower = text.lower()
            
            if any(word in text_lower for word in negative_words):
                return {
                    "sentiment": "negative",
                    "confidence": 0.90,
                    "escalate": True
                }
            elif any(word in text_lower for word in positive_words):
                return {
                    "sentiment": "positive",
                    "confidence": 0.85,
                    "escalate": False
                }
            else:
                return {
                    "sentiment": "neutral",
                    "confidence": 0.80,
                    "escalate": False
                }
        
        return self.safe_execute(
            operation="sentiment_analysis",
            ai_function=ai_analyze,
            text=text
        )


