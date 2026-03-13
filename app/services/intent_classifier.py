"""
Intent Classification Service

This service classifies ticket messages into intent categories with confidence scores.
MVP implementation uses rule-based keyword matching.
Future enhancement: NLP/ML model integration.

Reference: Technical Spec § 9.1 (Intent Classification)
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str
    confidence: float


class IntentClassifier:
    """
    Intent classification service for ticket messages.
    
    MVP: Rule-based keyword matching
    Future: NLP/ML model integration
    """
    
    # Define intent categories with associated keywords and patterns
    INTENT_PATTERNS = {
        "login_issue": {
            "keywords": [
                "login", "signin", "sign in", "log in", "authentication", "password",
                "credentials", "access", "account access", "can't login", "unable to login",
                "forgot password", "reset password", "locked out", "account locked"
            ],
            "patterns": [
                r"(?:can't|cannot|unable to).*(?:login|sign in|log in)",
                r"(?:forgot|reset).*(?:password|credential)",
                r"(?:account|access).*(?:locked|disabled|suspended)",
                r"(?:invalid|incorrect).*(?:credentials|password|login)",
                r"(?:login|sign in).*(?:failed|error|issues)"
            ],
            "base_confidence": 0.9
        },
        "payment_issue": {
            "keywords": [
                "payment", "billing", "charge", "charged", "transaction", "credit card",
                "debit card", "invoice", "receipt", "refund", "payment failed",
                "billing issue", "payment problem", "overcharged", "double charge"
            ],
            "patterns": [
                r"(?:payment|billing|transaction).*(?:failed|declined|error)",
                r"(?:charge|charged).*(?:wrong|incorrect|double)",
                r"(?:refund|refundable|reimbursement)"
            ],
            "base_confidence": 0.9
        },
        "account_issue": {
            "keywords": [
                "account", "profile", "settings", "personal information", "email",
                "phone number", "address", "update account", "delete account",
                "account settings", "profile update", "change email", "change phone"
            ],
            "patterns": [
                r"(?:update|change|modify).*(?:account|profile|settings)",
                r"(?:delete|remove|close).*(?:account|profile)",
                r"(?:personal|contact).*(?:information|details)",
                r"(?:update|change).*(?:email|email address|phone|address)"
            ],
            "base_confidence": 0.8
        },
        "technical_issue": {
            "keywords": [
                "error", "bug", "crash", "slow", "performance", "broken", "not working",
                "glitch", "issue", "problem", "technical", "system", "server",
                "down", "unavailable", "timeout", "loading", "freeze"
            ],
            "patterns": [
                r"(?:error|bug|issue).*(?:occur|happen|appear|getting|message)",
                r"(?:system|server|app|website).*(?:down|unavailable|crashed|crashing)",
                r"(?:slow|performance|loading).*(?:issue|problem)",
                r"(?:crashing|keeps crashing|crashed).*(?:when|when I|when trying)",
                r"(?:very slow|slow performance|too slow)",
                r"(?:getting|receiving|seeing).*(?:error|bug|issue)"
            ],
            "base_confidence": 0.7
        },
        "feature_request": {
            "keywords": [
                "feature", "request", "suggestion", "improvement", "enhancement",
                "add", "implement", "new feature", "would like", "wish", "hope",
                "suggest", "recommend", "feedback", "idea"
            ],
            "patterns": [
                r"(?:would|could).*(?:you|we).*(?:add|implement|provide)",
                r"(?:suggest|recommend|request).*(?:feature|improvement)",
                r"(?:wish|hope).*(?:had|have).*(?:feature|option)"
            ],
            "base_confidence": 0.8
        },
        "general_query": {
            "keywords": [
                "question", "help", "how", "what", "where", "when", "why", "information",
                "clarification", "explain", "understand", "guide", "tutorial",
                "documentation", "support", "assistance"
            ],
            "patterns": [
                r"(?:how|what|where|when|why).*(?:do|can|should|would)",
                r"(?:question|help|support).*(?:need|require)",
                r"(?:explain|understand|clarify).*(?:please|kindly)",
                r"(?:what are|what is|where can|how do).*(?:your|the|to)"
            ],
            "base_confidence": 0.6
        }
    }
    
    def __init__(self):
        """Initialize the intent classifier."""
        # Pre-compile regex patterns for better performance
        self._compiled_patterns = {}
        for intent, config in self.INTENT_PATTERNS.items():
            self._compiled_patterns[intent] = [
                re.compile(pattern, re.IGNORECASE) 
                for pattern in config["patterns"]
            ]
    
    def classify_intent(self, message: str) -> Dict[str, float]:
        """
        Classify the intent of a ticket message.
        
        Args:
            message: Raw ticket message from user
            
        Returns:
            Dictionary with keys:
            - intent: Classified intent label
            - confidence: Confidence score (0.0-1.0)
            
        Example:
            >>> classifier = IntentClassifier()
            >>> result = classifier.classify_intent("I can't login to my account")
            >>> print(result)
            {'intent': 'login_issue', 'confidence': 0.9}
        """
        if not message or not isinstance(message, str):
            return {"intent": "unknown", "confidence": 0.0}
        
        # Normalize message
        normalized_message = message.lower().strip()
        
        if len(normalized_message) < 3:
            return {"intent": "unknown", "confidence": 0.0}
        
        # Calculate scores for each intent
        intent_scores = []
        
        for intent, config in self.INTENT_PATTERNS.items():
            score_data = self._calculate_intent_score(normalized_message, intent, config)
            if score_data["total_matches"] > 0:
                intent_scores.append((intent, score_data))
        
        # Sort by comprehensive ranking:
        # 1. Number of pattern matches (strongest signal)
        # 2. Total score with specificity weighting
        # 3. Base confidence (tie-breaker)
        intent_scores.sort(key=lambda x: (
            x[1]["pattern_matches"],           # Primary: pattern matches
            x[1]["score"],                     # Secondary: weighted score
            x[1]["multi_word_matches"],        # Tertiary: specificity
            self.INTENT_PATTERNS[x[0]]["base_confidence"]  # Final: base confidence
        ), reverse=True)
        
        if not intent_scores:
            return {"intent": "unknown", "confidence": 0.0}
        
        # Get the best match
        best_intent, best_score_data = intent_scores[0]
        raw_confidence = best_score_data["score"]
        
        # Apply confidence normalization (removed 0.4 floor)
        normalized_confidence = self._normalize_confidence(raw_confidence, len(normalized_message))
        
        # If confidence is too low, classify as unknown
        if normalized_confidence < 0.15:
            return {"intent": "unknown", "confidence": normalized_confidence}
        
        return {
            "intent": best_intent,
            "confidence": min(normalized_confidence, 1.0)  # Ensure max 1.0
        }
    
    def _calculate_intent_score(self, message: str, intent: str, config: Dict) -> Dict:
        """Calculate intent score based on keyword and pattern matching."""
        import re
        
        # Tokenize message for word boundary matching
        tokens = re.findall(r'\b\w+\b', message.lower())
        token_set = set(tokens)
        
        # Pattern matching (strongest signal)
        pattern_matches = 0
        for pattern in self._compiled_patterns[intent]:
            if pattern.search(message):
                pattern_matches += 1
        
        # Keyword matching with word boundaries
        keyword_matches = 0
        multi_word_matches = 0
        single_word_matches = 0
        
        for keyword in config["keywords"]:
            keyword_lower = keyword.lower()
            
            if len(keyword.split()) > 1:
                # Multi-word keywords: use substring matching
                if keyword_lower in message.lower():
                    multi_word_matches += 1
                    keyword_matches += 1
            else:
                # Single-word keywords: use exact token matching
                if keyword_lower in token_set:
                    single_word_matches += 1
                    keyword_matches += 1
        
        # Calculate base score with specificity weighting
        base_score = 0.0
        
        # Pattern matches are the strongest signal (highest weight)
        base_score += pattern_matches * 1.0
        
        # Multi-word keywords are stronger than single-word
        base_score += multi_word_matches * 0.6
        
        # Single-word keywords (word-boundary matched)
        base_score += single_word_matches * 0.3
        
        # Apply base confidence multiplier
        if keyword_matches > 0 or pattern_matches > 0:
            base_score *= config["base_confidence"]
        
        # Bonus for multiple matches
        if keyword_matches + pattern_matches > 1:
            base_score *= 1.2  # 20% bonus for multiple indicators
        
        return {
            "score": base_score,
            "pattern_matches": pattern_matches,
            "multi_word_matches": multi_word_matches,
            "single_word_matches": single_word_matches,
            "total_matches": keyword_matches + pattern_matches
        }
    
    def _normalize_confidence(self, raw_score: float, message_length: int) -> float:
        """Normalize confidence score based on message characteristics."""
        # Adjust confidence based on message length
        if message_length < 10:
            # Very short messages get slight reduction
            return raw_score * 0.8
        elif message_length < 30:
            # Short messages get minimal reduction
            return raw_score * 0.9
        else:
            # Normal to long messages get full confidence
            return raw_score
    
    def get_supported_intents(self) -> List[str]:
        """Get list of supported intent categories."""
        return list(self.INTENT_PATTERNS.keys()) + ["unknown"]
    
    def get_intent_examples(self) -> Dict[str, List[str]]:
        """Get example messages for each intent (useful for testing/documentation)."""
        return {
            "login_issue": [
                "I can't login to my account",
                "Forgot my password and need to reset it",
                "Account is locked and I can't access it"
            ],
            "payment_issue": [
                "My payment was declined",
                "I was charged twice for the same order",
                "Need a refund for my recent purchase"
            ],
            "account_issue": [
                "I need to update my email address",
                "How do I delete my account?",
                "Want to change my profile information"
            ],
            "technical_issue": [
                "The app keeps crashing when I open it",
                "Website is very slow and unresponsive",
                "Getting an error message when trying to save"
            ],
            "feature_request": [
                "Would be great to have a dark mode option",
                "I suggest adding a bulk export feature",
                "Hope you can implement two-factor authentication"
            ],
            "general_query": [
                "What are your business hours?",
                "Can you explain how the billing works?",
                "Where can I find the documentation?",
                "How do I contact support?",
                "What services do you offer?"
            ],
            "unknown": [
                "asdfghjkl",  # Gibberish
                "hello",       # Too vague
                ""             # Empty
            ]
        }


# Global instance for easy access
intent_classifier = IntentClassifier()


def classify_intent(message: str) -> Dict[str, float]:
    """
    Convenience function for intent classification.
    
    Args:
        message: Raw ticket message
        
    Returns:
        Dictionary with intent and confidence keys
    """
    return intent_classifier.classify_intent(message)
