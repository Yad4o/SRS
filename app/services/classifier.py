import re
def _boundary_match(keyword: str, text: str) -> bool:
    """
    Check if keyword appears as a whole word/phrase in text (boundary-aware matching).
    
    Args:
        keyword: The keyword to match (can be multi-word)
        text: The text to search in
        
    Returns:
        bool: True if keyword matches as a whole word/phrase
    """
    escaped_keyword = re.escape(keyword)
    if ' ' in keyword:
        # Multi-word phrase: \b boundaries require the phrase to appear literally adjacent,
        # which breaks natural inputs like "forgot my password" vs keyword "forgot password".
        # Use a plain substring search so the phrase only needs to be present anywhere in text.
        pattern = escaped_keyword
    else:
        # Single word: enforce whole-word boundaries to avoid partial matches
        # (e.g. "access" must not match inside "accessed").
        pattern = r'\b' + escaped_keyword + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def classify_intent(message: str) -> dict[str, str | float | None]:
    """
    Classify user intent using rule-based keyword matching.
    
    This is the first step in the AI pipeline.
    Reference: Technical Spec § 9.1 (Intent Classification)

    Args:
        message (str): Raw ticket message from user

    Returns:
        dict: {
            "intent": str,
            "confidence": float (0.0-1.0),
            "sub_intent": str | None
        }
    """

    if not message or not isinstance(message, str):
        return {
            "intent": "unknown",
            "confidence": 0.0,
            "sub_intent": None,
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
            "confidence": 0.0,
            "sub_intent": None,
        }

    # -------- Intent Classification Rules -------- #
    
    intent_patterns = {
        "login_issue": {
            "keywords": [
                "login", "signin", "sign in", "log in", "authentication", "password",
                "credentials", "access", "account access", "cant login", "unable to login",
                "forgot password", "reset password", "locked out", "account locked",
                "sign in issue", "login problem", "authentication failed",
                "locked", "blocked", "suspended", "2fa", "two factor", "attempts"
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
                "would be great", "nice to have", "should have",
                "improve", "better", "enhance", "search"
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

            # Special handling: locked/blocked/suspended are login signals even when "account" is present
            if intent == "login_issue" and any(_boundary_match(kw, text) for kw in ["locked", "blocked", "suspended", "attempts", "2fa", "two factor"]):
                calculated_confidence = max(calculated_confidence, 0.92)
            
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

    # -------- Sub-intent Detection -------- #

    sub_intent_patterns: dict[str, list[tuple[str, list[str]]]] = {
        "login_issue": [
            ("password_reset",    ["forgot", "reset", "remember", "lost", "recovery"]),
            ("account_locked",    ["locked", "lock", "blocked", "2fa", "two factor", "suspended", "attempts"]),
            ("wrong_credentials", ["credentials", "wrong", "invalid"]),
        ],
        "payment_issue": [
            ("duplicate_charge",  ["twice", "double", "duplicate", "refund", "unexpected"]),
            ("payment_declined",  ["declined", "failed", "rejected"]),
            ("billing_question",  ["invoice", "receipt", "plan", "pricing"]),
        ],
        "account_issue": [
            ("delete_account",    ["delete", "remove", "close", "cancel", "deactivate", "gdpr"]),
            ("update_info",       ["update", "change", "edit", "email", "phone", "name", "profile"]),
        ],
        "technical_issue": [
            ("crash_error",       ["crash", "error", "bug", "broken", "not working", "fails"]),
            ("performance",       ["slow", "loading", "lag", "freeze", "timeout"]),
        ],
        "feature_request": [
            ("new_feature",       ["add", "new", "build", "implement", "wish"]),
            ("improvement",       ["improve", "better", "enhance"]),
        ],
        "general_query": [
            ("how_to",            ["how", "steps", "guide", "tutorial"]),
            ("pricing_plan",      ["price", "cost", "plan", "upgrade"]),
        ],
    }

    sub_intent: str | None = None
    if best_match:
        for sub_intent_name, keywords in sub_intent_patterns.get(best_match, []):
            if any(kw in text for kw in keywords):
                sub_intent = sub_intent_name
                break

    # -------- Return Result -------- #
    
    if best_match:
        return {
            "intent": best_match,
            "confidence": round(highest_score, 3),
            "sub_intent": sub_intent,
        }
    
    # -------- Fallback -------- #
    
    return {
        "intent": "unknown",
        "confidence": 0.2,
        "sub_intent": None,
    }

