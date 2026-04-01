"""
app/services/response_generator.py

Purpose:
--------
Generates human-readable responses for customer support tickets.

Owner:
------
Om (Backend / Response Generation)

Responsibilities:
-----------------
- Generate responses based on intent and sub-intent
- Handle similarity-based responses with quality scoring
- Integrate OpenAI API with proper fallback chain
- Ensure system never fails due to AI unavailability

DO NOT:
-------
- Make decisions about ticket resolution
- Update database directly
- Access external APIs directly (except OpenAI)
"""

from typing import Optional, Tuple
import re
from app.core.config import settings


def _call_openai(intent: str, sub_intent: Optional[str], message: str) -> Optional[str]:
    """
    Call OpenAI API to generate a response.
    
    Args:
        intent: The classified intent
        sub_intent: The sub-intent if available
        message: Original customer message
        
    Returns:
        str: Generated response or None if API call fails
    """
    try:
        from openai import OpenAI
        from openai import APIError
        
        client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT
        )
        
        system_prompt = "You are a helpful customer support agent for a SaaS product. Write a clear, specific 2-3 sentence response to the customer. Give actionable steps. Do not use filler phrases like 'I understand your frustration'. Be direct and helpful."
        
        user_prompt = f"Intent: {intent}"
        if sub_intent:
            user_prompt += f"\nSub-intent: {sub_intent}"
        user_prompt += f"\nCustomer message: {message}"
        
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=0.4
        )
        
        return response.choices[0].message.content.strip()
        
    except APIError:
        # Any OpenAI-specific exception should be silently handled
        return None


def _select_template_with_sub_intent(intent: str, original_message: str, sub_intent: Optional[str]) -> Tuple[str, str]:
    """
    Select the most relevant template with sub-intent support.
    
    Args:
        intent: The classified intent
        original_message: The original user message
        sub_intent: The sub-intent for more specific routing
        
    Returns:
        Tuple[str, str]: (template_text, "template")
    """
    if intent not in response_templates:
        return "I've received your message and will do my best to assist you.", "template"

    # Apply stronger normalization
    normalized_msg = _normalize_message(original_message)

    # Check for sub-intent specific routing first
    if sub_intent and sub_intent in _sub_intent_to_index:
        template_index = _sub_intent_to_index[sub_intent]
        if template_index < len(response_templates[intent]):
            return response_templates[intent][template_index], "template"

    # Reordered keyword rules: specific billing/security keywords first
    keyword_rules = {
        "login_issue": [
            (["forgot", "reset", "remember", "lost", "recovery"], 0),
            (["locked", "lock", "blocked", "2fa", "two factor", "suspended", "attempts"], 1),
        ],
        "payment_issue": [
            (["twice", "double", "duplicate", "refund", "unexpected", "extra"], 0),
            (["declined", "failed", "rejected", "not going through"], 1),
        ],
        "account_issue": [
            (["delete", "remove", "close", "cancel", "deactivate", "gdpr"], 0),
            (["update", "change", "edit", "email", "phone", "name", "profile"], 1),
        ],
        "technical_issue": [
            (["crash", "error", "broken", "not working", "bug", "fails"], 0),
            (["slow", "loading", "performance", "lag", "freeze", "timeout"], 1),
        ],
        "feature_request": [
            (["add", "new", "build", "implement", "feature", "wish"], 0),
            (["improve", "better", "fix", "enhance", "update existing"], 1),
        ],
        "general_query": [
            # Specific billing/security keywords first
            (["price", "pricing", "cost", "plan", "upgrade", "subscribe", "billing", "renew", "subscription", "two-factor", "two factor", "login"], 1),
            # Generic question words last
            (["how", "what", "where", "when", "guide", "steps", "tutorial", "why", "new", "cancel"], 0),
        ],
    }

    rules = keyword_rules.get(intent, [])
    for keywords, template_index in rules:
        if _match_keywords(normalized_msg, keywords):
            return response_templates[intent][template_index], "template"

    # Default: last template
    return response_templates[intent][-1], "template"


def generate_response(intent: str, original_message: str, similar_solution: Optional[str] = None, 
                        sub_intent: Optional[str] = None, similar_quality_score: Optional[float] = None) -> Tuple[str, str]:
    """
    Generate a human-readable response based on intent, message, and available solutions.
    
    This function implements a robust fallback chain:
    1. Similar solution (if high quality)
    2. OpenAI API (if configured)
    3. Template-based response
    4. Hardcoded fallback
    
    Args:
        intent: The classified intent (e.g., 'login_issue', 'payment_issue')
        original_message: The original user message for context
        similar_solution: Optional solution from a similar resolved ticket
        sub_intent: Optional sub-intent for more specific routing
        similar_quality_score: Optional quality score (0.0-1.0) for similar solution
        
    Returns:
        Tuple[str, str]: (response_text, source_label)
        source_label is one of: "similarity", "openai", "template", "fallback"
    """
    
    # Priority 1: Similar solution with quality threshold
    if similar_solution and similar_solution.strip() and (similar_quality_score is None or similar_quality_score >= 0.6):
        # Sanitize to 500 chars to prevent overly long responses
        sanitized_solution = similar_solution.strip()[:500]
        return f"I understand you're experiencing an issue. Based on a similar case, here's what helped: {sanitized_solution}", "similarity"
    
    # Priority 2: OpenAI API
    if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        openai_response = _call_openai(intent, sub_intent, original_message)
        if openai_response:
            return openai_response, "openai"
        # If OpenAI fails, silently continue to next priority
    
    # Priority 3: Template-based response
    template_response, _ = _select_template_with_sub_intent(intent, original_message, sub_intent)
    return template_response, "template"


# ---------------------------------------------------------------------------
# Helper functions (unchanged from original)
# ---------------------------------------------------------------------------

def _normalize_message(message: str) -> str:
    """
    Apply stronger normalization to improve keyword matching accuracy.
    """
    # Convert to lowercase
    normalized = message.lower()
    
    # Strip and normalize punctuation (replace with spaces)
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # Normalize hyphens to spaces
    normalized = normalized.replace('-', ' ')
    
    # Collapse multiple spaces to single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip leading/trailing whitespace
    normalized = normalized.strip()
    
    return normalized


def _match_keywords(normalized_msg: str, keywords: list[str]) -> bool:
    """
    Match keywords using word boundaries for more accurate matching.
    """
    for keyword in keywords:
        # Normalize keyword the same way
        norm_keyword = keyword.lower().replace('-', ' ')
        norm_keyword = re.sub(r'[^\w\s]', ' ', norm_keyword)
        norm_keyword = re.sub(r'\s+', ' ', norm_keyword).strip()
        
        # Use word boundary matching for single words
        if ' ' not in norm_keyword:
            pattern = r'\b' + re.escape(norm_keyword) + r'\b'
            if re.search(pattern, normalized_msg):
                return True
        # For phrases, use substring matching on normalized text
        else:
            if norm_keyword in normalized_msg:
                return True
    
    return False


# ---------------------------------------------------------------------------
# Response templates (unchanged from original)
# ---------------------------------------------------------------------------

response_templates = {
    "login_issue": [
        # 0 — password forgotten/reset
        "It looks like you need to reset your password. Click 'Forgot Password' on the login page "
        "and follow the instructions. Note that the reset link expires in 15 minutes, so act quickly. "
        "If the email doesn't arrive, please check your spam or junk folder.",

        # 1 — account locked / 2FA
        "Your account may be temporarily locked after too many failed attempts. Please wait 30 minutes "
        "before trying again. If you have two-factor authentication (2FA) enabled, make sure you're "
        "entering the latest code from your authenticator app. If you're still locked out, our support "
        "team can unlock your account manually — just reach out.",

        # 2 — wrong credentials / default
        "Please double-check the email address you're signing in with — it's easy to mix up similar "
        "addresses. Also check for any accidental leading or trailing spaces in your password field. "
        "If you originally signed up via Google or another social provider, try that sign-in option "
        "instead of entering a password directly.",
    ],

    "payment_issue": [
        # 0 — duplicate / unexpected charge
        "We're sorry to hear about an unexpected charge. Please share the transaction ID(s) from your "
        "bank statement so we can investigate. If a duplicate charge is confirmed, refunds are typically "
        "processed within 3-5 business days back to your original payment method.",

        # 1 — payment declined
        "Payments can be declined for several reasons: an expired card, insufficient funds, or your bank "
        "blocking the transaction as a precaution. Please verify your card details and expiry date in "
        "Settings > Billing > Payment Methods. If the card looks correct, a quick call to your bank "
        "usually resolves any blocks on their end.",

        # 2 — billing question / default
        "For a full overview of your charges, invoices, and plan details, head to the Billing tab in "
        "your account settings. If you received a billing email from us, you can also reply directly "
        "to that email and it will reach our billing team.",
    ],

    "account_issue": [
        # 0 — delete / GDPR
        "To delete your account, go to Settings > Account > Delete Account and follow the confirmation "
        "steps. Your personal data will be permanently removed within 30 days in line with GDPR. "
        "If you'd prefer a less permanent option, you can deactivate your account instead — this hides "
        "your profile without deleting your data.",

        # 1 — update info
        "To update your profile details, go to Settings > Profile. Most fields save instantly. "
        "Note that changing your email address requires a verification link sent to both your old "
        "and new addresses, so keep an eye on both inboxes.",

        # 2 — access / export / default
        "For account access or data export requests, please email our support team with the email "
        "address associated with your account and a brief description of what you need. We'll get "
        "back to you as quickly as possible.",
    ],

    "technical_issue": [
        # 0 — crash / error
        "Sorry you're hitting an error. Could you send a screenshot or copy the exact error message? "
        "That helps us pinpoint the cause quickly. In the meantime, try clearing your browser cache "
        "and cookies (Settings > Privacy > Clear browsing data) and reload the page.",

        # 1 — slow / performance
        "Performance problems are often caused by browser extensions. Try opening the app in an "
        "incognito/private window — extensions are usually disabled there — to see if that helps. "
        "It's also worth running a quick speed test at fast.com to rule out a connection issue on "
        "your end.",

        # 2 — broken feature / default
        f"First, check our status page ({settings.STATUS_PAGE_URL}) to see if there's a known outage or "
        "ongoing incident. If everything looks fine there, try switching to a different browser — "
        "this rules out a browser-specific compatibility issue. If the problem persists, let us know "
        "and we'll dig deeper.",
    ],

    "feature_request": [
        # 0 — new feature
        "Thanks for the idea! You can check our public roadmap to see what's already planned, and "
        "use the upvoting system to support features you'd like to see prioritised. The more votes "
        "a request gets, the more visibility it receives with our product team.",

        # 1 — improvement to existing feature
        "We'd love to make this better — could you describe the specific friction point you're running "
        "into? For example, what step feels slow, confusing, or incomplete? That detail helps our team "
        "understand the real-world impact and prioritise the right fix.",

        # 2 — integration / default
        "You can browse our current integrations and vote on upcoming ones on our Integrations page. "
        "We also track integration requests on the public roadmap — adding your vote there is the "
        "best way to signal demand to the team.",
    ],

    "general_query": [
        # 0 — how-to
        "Happy to help! Could you give a bit more detail about what you're trying to do? In the "
        "meantime, our Help Center has step-by-step guides covering most common tasks — it's "
        "searchable and usually the fastest way to find an answer.",

        # 1 — pricing
        "You can find a full breakdown of our plans and pricing on the Pricing page. If you're unsure "
        "which plan fits your needs, feel free to describe how you'd use the product and we can "
        "suggest the best fit.",

        # 2 — contact / default
        f"You can reach our support team by emailing {settings.SUPPORT_EMAIL} or using the live chat in "
        "the bottom-right corner of the app. Live chat is available Monday-Friday, 9 am-6 pm UTC.",
    ],
}

# Sub-intent to template index mapping for more specific routing
_sub_intent_to_index: dict[str, int] = {
    "password_reset":    0,
    "account_locked":    1,
    "wrong_credentials": 2,
    "duplicate_charge": 0,
    "payment_declined": 1,
    "billing_question": 2,
    "delete_account":    0,
    "update_info":       1,
    "crash_error":       0,
    "performance":       1,
    "new_feature":       0,
    "improvement":       1,
    "how_to":            0,
    "pricing_plan":      1,
}
