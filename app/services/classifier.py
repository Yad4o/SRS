import re
from typing import Dict


def classify_intent(text: str) -> Dict[str, float]:
    """
    Classify user intent using rule-based keyword matching.

    Args:
        text (str): Raw user input text

    Returns:
        dict: {
            "intent": str,
            "confidence": float
        }
    """

    if not text or not isinstance(text, str):
        return {
            "intent": "unknown",
            "confidence": 0.0
        }

    text = text.lower().strip()

    # Clean text (remove special characters)
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # -------- Intent Rules -------- #

    intent_rules = {
        "login_issue": [
            "login", "sign in", "signin", "password", "otp", "cannot access"
        ],
        "payment_issue": [
            "payment", "charged", "refund", "transaction", "money", "debit"
        ],
        "account_issue": [
            "account", "profile", "deactivate", "delete account", "suspend"
        ],
        "technical_issue": [
            "error", "bug", "crash", "not working", "issue", "problem"
        ],
        "feature_request": [
            "feature", "add", "improve", "enhancement", "request"
        ],
        "general_query": [
            "how", "what", "why", "can i", "help", "support"
        ],
    }

    # -------- Matching Logic -------- #

    for intent, keywords in intent_rules.items():
        for keyword in keywords:
            if keyword in text:
                return {
                    "intent": intent,
                    "confidence": 0.8
                }

    # -------- Fallback -------- #

    return {
        "intent": "unknown",
        "confidence": 0.3
    }
