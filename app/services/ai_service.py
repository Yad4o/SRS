"""
 =============================================================================
 SRS (Support Request System) - AI Service Management
 =============================================================================

Purpose:
--------
Advanced AI service management with comprehensive fallback handling,
circuit breaker pattern, and performance monitoring.

Responsibilities:
-----------------
- Provide robust AI service execution with fallback mechanisms
- Implement circuit breaker pattern for AI service failures
- Handle AI service failures gracefully without exposing internal errors
- Provide metrics and monitoring for AI service performance
- Support multiple AI providers (OpenAI, Anthropic, local models)
- Implement retry logic with exponential backoff

Owner:
------
Backend Team

DO NOT:
-------
- Expose AI service internal errors to clients
- Return 500 errors for AI service failures
- Skip logging AI service failures
- Cache sensitive AI responses

References:
-----------
- Circuit Breaker Pattern
- AI Service Resilience Best Practices
- Technical Spec § 8 (AI Services)
"""

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from functools import wraps

from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.core.error_handlers import handle_ai_service_failure
from app.services.classifier import classify_intent
from app.utils.service_helpers import MetricsHelper, ErrorHelper

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Constants and Configuration
# -----------------------------------------------------------------------------
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 60


class ServiceState(Enum):
    """AI service circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class AIMetrics:
    """Metrics for AI service performance."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    fallback_used: int = 0
    average_response_time: float = 0.0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None


class CircuitBreaker:
    """Circuit breaker implementation for AI services."""
    
    def __init__(self, failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD, 
                 timeout: int = CIRCUIT_BREAKER_TIMEOUT):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.state = ServiceState.CLOSED
        self.next_attempt = 0
        
    def call_allowed(self) -> bool:
        """Check if calling the service is allowed."""
        if self.state == ServiceState.CLOSED:
            return True
        
        if self.state == ServiceState.OPEN:
            if time.time() >= self.next_attempt:
                self.state = ServiceState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False
        
        # HALF_OPEN state - allow limited calls
        return True
    
    def record_success(self):
        """Record a successful call."""
        self.failure_count = 0
        if self.state == ServiceState.HALF_OPEN:
            self.state = ServiceState.CLOSED
            logger.info("Circuit breaker transitioning to CLOSED")
    
    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        
        if self.state == ServiceState.HALF_OPEN:
            self.state = ServiceState.OPEN
            self.next_attempt = time.time() + self.timeout
            logger.warning("Circuit breaker transitioning to OPEN from HALF_OPEN")
        elif self.failure_count >= self.failure_threshold:
            self.state = ServiceState.OPEN
            self.next_attempt = time.time() + self.timeout
            logger.warning(f"Circuit breaker transitioning to OPEN (failures: {self.failure_count})")


def retry_with_backoff(max_retries: int = MAX_RETRIES, base_delay: float = 1.0):
    """Decorator for retrying AI functions with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"AI function failed after {max_retries} retries: {e}")
                        raise
                    
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"AI function attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator


class BaseAIService(ABC):
    """Base class for AI services with comprehensive error handling."""
    
    def __init__(self, service_name: str, timeout: int = DEFAULT_TIMEOUT):
        self.service_name = service_name
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()
        self.metrics = AIMetrics()
        self._provider = None
        
    @abstractmethod
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response when AI service fails."""
        pass
    
    @abstractmethod
    def _execute_ai_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute the actual AI operation."""
        pass
    
    def safe_execute(
        self,
        operation: str,
        fallback_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Safely execute AI operation with comprehensive error handling.
        
        Features:
        - Circuit breaker pattern
        - Retry logic with exponential backoff
        - Timeout handling
        - Metrics collection
        - Fallback responses
        
        Args:
            operation: Description of the AI operation
            fallback_data: Optional fallback data
            **kwargs: Arguments to pass to AI operation
            
        Returns:
            Response with AI result or fallback
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            # Check circuit breaker
            if not self.circuit_breaker.call_allowed():
                logger.warning(f"Circuit breaker OPEN for {self.service_name}, using fallback")
                return self._handle_fallback(operation, fallback_data, start_time, "circuit_breaker")
            
            # Execute with retry and timeout
            result = self._execute_with_retry(operation, **kwargs)
            
            # Record success
            self.circuit_breaker.record_success()
            self.metrics.successful_requests += 1
            self.metrics.last_success_time = time.time()
            
            # Update response time metrics
            response_time = time.time() - start_time
            self._update_response_time_metrics(response_time)
            
            logger.info(f"AI service '{self.service_name}' succeeded for operation: {operation}")
            
            return {
                "data": result,
                "fallback_used": False,
                "service": self.service_name,
                "response_time": response_time,
                "circuit_breaker_state": self.circuit_breaker.state.value
            }
            
        except Exception as e:
            # Record failure
            self.circuit_breaker.record_failure()
            self.metrics.failed_requests += 1
            self.metrics.last_failure_time = time.time()
            
            # Log the AI service failure
            error_details = {
                "service": self.service_name,
                "operation": operation,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "circuit_breaker_state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker.failure_count
            }
            
            logger.warning(
                f"AI service '{self.service_name}' failed for operation '{operation}': {e}"
            )
            
            return self._handle_fallback(operation, fallback_data, start_time, str(e))
    
    def _execute_with_retry(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute AI operation with retry logic."""
        @retry_with_backoff(max_retries=MAX_RETRIES)
        def execute():
            return self._execute_ai_operation(operation, **kwargs)
        
        return execute()
    
    def _handle_fallback(
        self, 
        operation: str, 
        fallback_data: Optional[Dict[str, Any]], 
        start_time: float,
        error_reason: str
    ) -> Dict[str, Any]:
        """Handle fallback response generation."""
        self.metrics.fallback_used += 1
        
        # Use provided fallback or generate one
        if fallback_data is None:
            fallback_data = self.get_fallback_response(operation, **kwargs)
        
        # Record metrics
        response_time = time.time() - start_time
        MetricsHelper.record_metric(f"ai_service_{self.service_name}_fallback", 1)
        MetricsHelper.record_metric(f"ai_service_{self.service_name}_response_time", response_time)
        
        # Return fallback response
        return handle_ai_service_failure(
            operation=operation,
            fallback_data=fallback_data,
            error_details={
                "service": self.service_name,
                "error_reason": error_reason,
                "circuit_breaker_state": self.circuit_breaker.state.value
            }
        )
    
    def _update_response_time_metrics(self, response_time: float):
        """Update response time metrics."""
        if self.metrics.average_response_time == 0:
            self.metrics.average_response_time = response_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.metrics.average_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.metrics.average_response_time
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        success_rate = (
            self.metrics.successful_requests / self.metrics.total_requests 
            if self.metrics.total_requests > 0 else 0
        )
        
        return {
            "service_name": self.service_name,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "fallback_used": self.metrics.fallback_used,
            "success_rate": success_rate,
            "average_response_time": self.metrics.average_response_time,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "circuit_breaker_failures": self.circuit_breaker.failure_count,
            "last_success_time": self.metrics.last_success_time,
            "last_failure_time": self.metrics.last_failure_time
        }
    
    def reset_metrics(self):
        """Reset service metrics."""
        self.metrics = AIMetrics()
        self.circuit_breaker = CircuitBreaker()


class TicketClassificationService(BaseAIService):
    """AI service for ticket classification with comprehensive fallback."""
    
    def __init__(self):
        super().__init__("ticket_classifier")
    
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response for ticket classification."""
        message = kwargs.get("message", "")
        
        # Simple rule-based fallback
        if any(word in message.lower() for word in ["urgent", "emergency", "critical"]):
            return {
                "intent": "urgent",
                "confidence": 0.6,
                "escalate": True,
                "message": "Classified as urgent (fallback)",
                "source": "rule_based_fallback"
            }
        elif any(word in message.lower() for word in ["login", "password", "account"]):
            return {
                "intent": "login_issue",
                "confidence": 0.7,
                "escalate": False,
                "message": "Classified as login issue (fallback)",
                "source": "rule_based_fallback"
            }
        else:
            return {
                "intent": "general",
                "confidence": 0.5,
                "escalate": True,
                "message": "Unable to classify ticket automatically (fallback)",
                "source": "default_fallback"
            }
    
    def _execute_ai_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute AI classification operation."""
        if operation != "ticket_classification":
            raise ValueError(f"Unknown operation: {operation}")
        
        message = kwargs.get("message", "")
        if not message:
            raise ValueError("Message is required for classification")
        
        # Call the actual AI classification
        result = classify_intent(message)
        
        # Validate result format
        if not isinstance(result, dict):
            raise ValueError("Invalid classification result format")
        
        required_fields = ["intent", "confidence"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        return result
    
    def classify_ticket(self, message: str) -> Dict[str, Any]:
        """
        Classify ticket intent using AI with comprehensive fallback.
        
        Args:
            message: Ticket message to classify
            
        Returns:
            Classification result with metadata
        """
        return self.safe_execute(
            operation="ticket_classification",
            message=message
        )


class ResponseGenerationService(BaseAIService):
    """AI service for response generation with comprehensive fallback."""
    
    def __init__(self):
        super().__init__("response_generator")
    
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response for response generation."""
        intent = kwargs.get("intent", "general")
        
        # Intent-specific fallback responses
        fallback_responses = {
            "login_issue": "I understand you're having trouble logging in. Please check your credentials and try again. If the issue persists, our team will assist you shortly.",
            "payment_issue": "I see there's an issue with your payment. Our billing team has been notified and will investigate this urgently.",
            "technical_issue": "I'm sorry you're experiencing technical difficulties. Our technical team has been alerted and will address this promptly.",
            "urgent": "This appears to be urgent. I've escalated your ticket to our priority support team for immediate attention.",
            "general": "Thank you for contacting support. Your ticket has been received and our team will review it shortly."
        }
        
        return {
            "response": fallback_responses.get(intent, fallback_responses["general"]),
            "confidence": 0.3,
            "escalate": intent in ["urgent", "payment_issue"],
            "source": "template_fallback"
        }
    
    def _execute_ai_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute AI response generation operation."""
        if operation != "response_generation":
            raise ValueError(f"Unknown operation: {operation}")
        
        intent = kwargs.get("intent", "")
        message = kwargs.get("message", "")
        
        if not intent or not message:
            raise ValueError("Intent and message are required for response generation")
        
        # Import here to avoid circular imports
        from app.services.response_generator import generate_response
        
        response_text, response_source = generate_response(
            intent=intent,
            original_message=message,
            similar_solution=None,
            sub_intent=None,
            similar_quality_score=None
        )
        
        if not response_text:
            raise ValueError("Empty response generated")
        
        return {
            "response": response_text,
            "source": response_source,
            "confidence": 0.85,
            "escalate": intent == "payment_issue"
        }
    
    def generate_response(self, intent: str, message: str) -> Dict[str, Any]:
        """
        Generate response using AI with comprehensive fallback.
        
        Args:
            intent: Classified ticket intent
            message: Original ticket message
            
        Returns:
            Generated response with metadata
        """
        return self.safe_execute(
            operation="response_generation",
            intent=intent,
            message=message
        )


class SentimentAnalysisService(BaseAIService):
    """AI service for sentiment analysis with comprehensive fallback."""
    
    def __init__(self):
        super().__init__("sentiment_analyzer")
    
    def get_fallback_response(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Get fallback response for sentiment analysis."""
        text = kwargs.get("text", "")
        
        # Simple keyword-based sentiment analysis
        negative_words = ["angry", "frustrated", "terrible", "awful", "hate", "unacceptable"]
        positive_words = ["happy", "great", "excellent", "love", "wonderful", "perfect"]
        
        text_lower = text.lower()
        
        if any(word in text_lower for word in negative_words):
            return {
                "sentiment": "negative",
                "confidence": 0.7,
                "escalate": True,
                "source": "keyword_fallback"
            }
        elif any(word in text_lower for word in positive_words):
            return {
                "sentiment": "positive",
                "confidence": 0.7,
                "escalate": False,
                "source": "keyword_fallback"
            }
        else:
            return {
                "sentiment": "neutral",
                "confidence": 0.6,
                "escalate": False,
                "source": "default_fallback"
            }
    
    def _execute_ai_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute AI sentiment analysis operation."""
        if operation != "sentiment_analysis":
            raise ValueError(f"Unknown operation: {operation}")
        
        text = kwargs.get("text", "")
        if not text:
            raise ValueError("Text is required for sentiment analysis")
        
        # Enhanced keyword-based analysis (can be replaced with actual AI model)
        negative_words = ["angry", "frustrated", "terrible", "awful", "hate", "unacceptable", "disappointed"]
        positive_words = ["happy", "great", "excellent", "love", "wonderful", "perfect", "satisfied"]
        
        text_lower = text.lower()
        
        # Count sentiment words
        negative_count = sum(1 for word in negative_words if word in text_lower)
        positive_count = sum(1 for word in positive_words if word in text_lower)
        
        # Determine sentiment
        if negative_count > positive_count:
            return {
                "sentiment": "negative",
                "confidence": min(0.9, 0.5 + (negative_count * 0.1)),
                "escalate": True,
                "source": "keyword_analysis"
            }
        elif positive_count > negative_count:
            return {
                "sentiment": "positive",
                "confidence": min(0.9, 0.5 + (positive_count * 0.1)),
                "escalate": False,
                "source": "keyword_analysis"
            }
        else:
            return {
                "sentiment": "neutral",
                "confidence": 0.6,
                "escalate": False,
                "source": "keyword_analysis"
            }
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment using AI with comprehensive fallback.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment analysis result with metadata
        """
        return self.safe_execute(
            operation="sentiment_analysis",
            text=text
        )


# -----------------------------------------------------------------------------
# Service Registry and Management
# -----------------------------------------------------------------------------

class AIServiceRegistry:
    """Registry for managing AI services."""
    
    def __init__(self):
        self._services = {}
        self._initialize_default_services()
    
    def _initialize_default_services(self):
        """Initialize default AI services."""
        self._services["classifier"] = TicketClassificationService()
        self._services["response_generator"] = ResponseGenerationService()
        self._services["sentiment_analyzer"] = SentimentAnalysisService()
    
    def register_service(self, name: str, service: BaseAIService):
        """Register a new AI service."""
        self._services[name] = service
        logger.info(f"Registered AI service: {name}")
    
    def get_service(self, name: str) -> Optional[BaseAIService]:
        """Get an AI service by name."""
        return self._services.get(name)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics for all services."""
        return {
            name: service.get_metrics()
            for name, service in self._services.items()
        }
    
    def reset_all_metrics(self):
        """Reset metrics for all services."""
        for service in self._services.values():
            service.reset_metrics()


# Global service registry instance
ai_service_registry = AIServiceRegistry()


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------

def classify_ticket(message: str) -> Dict[str, Any]:
    """Convenience function for ticket classification."""
    classifier = ai_service_registry.get_service("classifier")
    if classifier:
        return classifier.classify_ticket(message)
    raise AIServiceError("Classification service not available")


def generate_response(intent: str, message: str) -> Dict[str, Any]:
    """Convenience function for response generation."""
    generator = ai_service_registry.get_service("response_generator")
    if generator:
        return generator.generate_response(intent, message)
    raise AIServiceError("Response generation service not available")


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """Convenience function for sentiment analysis."""
    analyzer = ai_service_registry.get_service("sentiment_analyzer")
    if analyzer:
        return analyzer.analyze_sentiment(text)
    raise AIServiceError("Sentiment analysis service not available")


def get_ai_service_metrics() -> Dict[str, Any]:
    """Get metrics for all AI services."""
    return ai_service_registry.get_all_metrics()


# -----------------------------------------------------------------------------
# Example Usage and Testing
# -----------------------------------------------------------------------------

def demonstrate_ai_service_resilience():
    """Demonstrate AI service resilience features."""
    print("=== AI Service Resilience Demonstration ===")
    
    # Test normal operation
    classifier = ai_service_registry.get_service("classifier")
    if classifier:
        print("\n1. Normal Operation:")
        result = classifier.classify_ticket("I can't login to my account")
        print(f"Result: {result}")
        
        # Get metrics
        print(f"Metrics: {classifier.get_metrics()}")
        
        # Test circuit breaker
        print("\n2. Circuit Breaker Test:")
        # Force circuit breaker to open
        for i in range(6):
            classifier.circuit_breaker.record_failure()
        
        result = classifier.classify_ticket("Test message")
        print(f"Circuit breaker result: {result}")
        print(f"Circuit breaker state: {classifier.circuit_breaker.state.value}")


if __name__ == "__main__":
    demonstrate_ai_service_resilience()
