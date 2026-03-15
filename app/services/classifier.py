import re
from typing import Dict


def _boundary_match(keyword: str, text: str) -> bool:
    """
    Check if keyword appears as a whole word/phrase in text (boundary-aware matching).
    
    Args:
        keyword: The keyword to match (can be multi-word)
        text: The text to search in
        
    Returns:
        bool: True if keyword matches as a whole word/phrase
    """
    # Escape special regex characters in keyword
    escaped_keyword = re.escape(keyword)
    # Use word boundaries to match whole words only
    # For multi-word phrases, we need to handle boundaries differently
    if ' ' in keyword:
        # Multi-word phrase - check with word boundaries around the whole phrase
        pattern = r'\b' + escaped_keyword + r'\b'
    else:
        # Single word - use standard word boundaries
        pattern = r'\b' + escaped_keyword + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def classify_intent(message: str) -> Dict[str, float]:
    """
    Classify user intent using rule-based keyword matching.
    
    This is the first step in the AI pipeline.
    Reference: Technical Spec § 9.1 (Intent Classification)

    Args:
        message (str): Raw ticket message from user

    Returns:
        dict: {
            "intent": str,
            "confidence": float (0.0-1.0)
        }
    """

    if not message or not isinstance(message, str):
        return {
            "intent": "unknown",
            "confidence": 0.0
        }

    # Normalize message
    text = message.lower().strip()
    
    # Clean text (remove special characters but keep spaces)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    
    # Handle very short messages
    if len(text) < 3:
        return {
            "intent": "unknown",
            "confidence": 0.0
        }

    # -------- Intent Classification Rules -------- #
    
    intent_patterns = {
        "login_issue": {
            "keywords": [
                "login", "signin", "sign in", "log in", "authentication", "password",
                "credentials", "access", "account access", "cant login", "unable to login",
                "forgot password", "reset password", "locked out", "account locked",
                "sign in issue", "login problem", "authentication failed"
            ],
            "confidence": 0.85
        },
        "payment_issue": {
            "keywords": [
                "payment", "billing", "charge", "charged", "transaction", "credit card",
                "debit card", "invoice", "receipt", "refund", "payment failed",
                "billing issue", "payment problem", "overcharged", "double charge",
                "payment declined", "wrong charge", "money", "cost", "price"
            ],
            "confidence": 0.9
        },
        "account_issue": {
            "keywords": [
                "account", "profile", "settings", "personal information", "email",
                "phone number", "address", "update account", "delete account",
                "account settings", "profile update", "change email", "change phone",
                "deactivate", "suspend", "close account", "personal data"
            ],
            "confidence": 0.8
        },
        "technical_issue": {
            "keywords": [
                "error", "bug", "crash", "slow", "performance", "broken", "not working",
                "glitch", "issue", "problem", "technical", "system", "server",
                "down", "unavailable", "timeout", "loading", "freeze", "frozen",
                "crashing", "fails", "failed", "malfunction"
            ],
            "confidence": 0.75
        },
        "feature_request": {
            "keywords": [
                "feature", "request", "suggestion", "improvement", "enhancement",
                "add", "implement", "new feature", "would like", "wish", "hope",
                "suggest", "recommend", "feedback", "idea", "could you", "can you",
                "would be great", "nice to have", "should have"
            ],
            "confidence": 0.8
        },
        "general_query": {
            "keywords": [
                "question", "help", "how", "what", "where", "when", "why", "information",
                "clarification", "explain", "understand", "guide", "tutorial",
                "documentation", "support", "assistance", "contact", "info"
            ],
            "patterns": [
                r"how (?:do|can|should|would)",
                r"what (?:is|are|do|can)",
                r"where (?:can|do|is)",
                r"when (?:can|do|is)",
                r"why (?:do|can|is)",
                r"explain (?:please|kindly)",
                r"help (?:me|with)",
                r"contact (?:support|you)"
            ],
            "confidence": 0.7
        }
    }

    # -------- Matching Logic -------- #
    
    best_match = None
    highest_score = 0
    
    # Priority order: more specific intents first
    intent_priority = [
        "payment_issue",
        "login_issue", 
        "account_issue",
        "technical_issue",
        "feature_request",
        "general_query"
    ]
    
    # Reorder intents by priority
    ordered_intents = {}
    for intent in intent_priority:
        if intent in intent_patterns:
            ordered_intents[intent] = intent_patterns[intent]
    
    for intent, config in ordered_intents.items():
        keywords = config["keywords"]
        base_confidence = config["confidence"]
        patterns = config.get("patterns", [])
        
        # Count keyword matches
        match_count = 0
        pattern_matches = 0
        
        for keyword in keywords:
            if _boundary_match(keyword, text):
                match_count += 1
        
        # Check pattern matches (higher weight)
        for pattern in patterns:
            if re.search(pattern, text):
                pattern_matches += 1
        
        if match_count > 0 or pattern_matches > 0:
            # Calculate confidence based on matches and base confidence
            # More keywords matched = higher confidence
            match_bonus = min(match_count * 0.1, 0.3)  # Max 30% bonus
            pattern_bonus = pattern_matches * 0.15  # 15% bonus per pattern match
            
            calculated_confidence = min(base_confidence + match_bonus + pattern_bonus, 1.0)
            
            # Adjust for message length (longer messages get slight boost)
            if len(text) > 50:
                calculated_confidence = min(calculated_confidence * 1.05, 1.0)
            elif len(text) < 10:
                calculated_confidence *= 0.9
            
            # Special handling for general queries with "explain" + billing context
            if intent == "general_query" and _boundary_match("explain", text) and _boundary_match("billing", text):
                calculated_confidence = max(calculated_confidence, 0.95)
            
            # Special handling: reduce payment_issue confidence for "explain" queries without action verbs
            if intent == "payment_issue" and _boundary_match("explain", text) and _boundary_match("billing", text):
                # Check if this is an informational query (no action verbs like charge, failed, etc.)
                action_verbs = ["charge", "charged", "failed", "declined", "debit", "refund", "transaction"]
                has_action_verb = any(_boundary_match(verb, text) for verb in action_verbs)
                if not has_action_verb:
                    calculated_confidence *= 0.7  # Reduce confidence for informational queries
            
            # Special handling: if account_issue has account keywords, give it priority
            if intent == "account_issue" and any(_boundary_match(kw, text) for kw in ["account", "delete", "profile"]):
                calculated_confidence = max(calculated_confidence, 0.9)
            
            if calculated_confidence > highest_score:
                highest_score = calculated_confidence
                best_match = intent
            elif calculated_confidence == highest_score and best_match:
                # Tie-breaker: use priority order (earlier in intent_priority wins)
                current_priority = intent_priority.index(intent) if intent in intent_priority else len(intent_priority)
                best_priority = intent_priority.index(best_match) if best_match in intent_priority else len(intent_priority)
                if current_priority < best_priority:
                    highest_score = calculated_confidence
                    best_match = intent

    # -------- Return Result -------- #
    
    if best_match:
        return {
            "intent": best_match,
            "confidence": round(highest_score, 3)
        }
    
    # -------- Fallback -------- #
    
    return {
        "intent": "unknown",
        "confidence": 0.2
    }
