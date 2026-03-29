from typing import Optional
import re
from app.core.config import settings


def _normalize_message(message: str) -> str:
    """
    Apply stronger normalization to improve keyword matching accuracy.
    
    Args:
        message: Raw user message
        
    Returns:
        str: Normalized message for accurate matching
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
    
    Args:
        normalized_msg: Normalized message
        keywords: List of keywords to match
        
    Returns:
        bool: True if any keyword matches as a whole word/phrase
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


def _select_template(intent: str, message: str) -> str:
    """
    Select the most relevant template index for a given intent and message.

    Args:
        intent: The classified intent string.
        message: The raw user message (will be normalized internally).

    Returns:
        str: The selected response template text.
    """
    if intent not in response_templates:
        return "I've received your message and will do my best to assist you."

    # Apply stronger normalization
    normalized_msg = _normalize_message(message)

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
            return response_templates[intent][template_index]

    # Default: last template
    return response_templates[intent][-1]


def _clean_similar_solution(solution: str) -> str:
    """
    Clean and normalize a similar solution to prevent wrapper nesting and limit length.
    
    Args:
        solution: Raw similar solution text
        
    Returns:
        str: Cleaned, bounded, and normalized solution
    """
    # Detect and remove existing wrapper prefixes - loop to remove all matches
    wrapper_prefixes = [
        "I understand you're experiencing an issue. Based on a similar case, here's what helped:",
        "Based on a similar case, here's what helped:",
        "Here's what helped in a similar case:",
        "Similar case solution:",
    ]
    
    cleaned = solution.strip()
    # Keep removing prefixes until none match
    while True:
        found_prefix = False
        for prefix in wrapper_prefixes:
            if cleaned.lower().startswith(prefix.lower()):
                # Remove prefix and any following whitespace/colon
                remainder = cleaned[len(prefix):]
                # Explicitly check for and remove exact delimiter sequence
                if remainder.startswith(': '):
                    remainder = remainder[2:]
                elif remainder.startswith(':'):
                    remainder = remainder[1:]
                cleaned = remainder.strip()
                found_prefix = True
                break
        if not found_prefix:
            break  # No more prefixes to remove
    
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Limit to safe maximum length (1000 chars)
    if len(cleaned) > 1000:
        cleaned = cleaned[:1000].rstrip()
        # Try to end at a sentence boundary
        last_period = cleaned.rfind('.')
        last_exclamation = cleaned.rfind('!')
        last_question = cleaned.rfind('?')
        
        last_sentence_end = max(last_period, last_exclamation, last_question)
        if last_sentence_end > 800:  # Only truncate if we have substantial content
            cleaned = cleaned[:last_sentence_end + 1]
        else:
            cleaned += '...'  # Indicate truncation
    
    return cleaned

_sub_intent_to_index: dict[str, int] = {
    "password_reset":    0,
    "account_locked":    1,
    "wrong_credentials": 2,
    "duplicate_charge":  0,
    "payment_declined":  1,
    "billing_question":  2,
    "delete_account":    0,
    "update_info":       1,
    "crash_error":       0,
    "performance":       1,
    "new_feature":       0,
    "improvement":       1,
    "how_to":            0,
    "pricing_plan":      1,
}


def generate_response(intent: str, original_message: str, similar_solution: Optional[str] = None, sub_intent: Optional[str] = None) -> str:
    """
    Generate a human-readable response based on intent, original message, and similar solution.

    This component only returns text; it does not update database or make decisions.
    Reference: Technical Spec § 9.3 (Response Generation)

    Args:
        intent: The classified intent (e.g., 'login_issue', 'payment_issue')
        original_message: The original user message for context
        similar_solution: Optional solution from a similar resolved ticket to reuse.
                          NOTE: This parameter is processed by _clean_similar_solution
                          which performs prefix stripping, normalization, and length bounding.
                          Callers should still sanitize/validate if stronger guarantees are needed.

    Returns:
        str: Generated response text
    """

    # Priority 1: Reuse similar solution if provided
    # NOTE: similar_solution is processed by _clean_similar_solution for safety
    if similar_solution and similar_solution.strip():
        cleaned_solution = _clean_similar_solution(similar_solution)
        return f"I understand you're experiencing an issue. Based on a similar case, here's what helped: {cleaned_solution}"

    # Priority 2: sub_intent fast-path — skip keyword detection entirely
    if sub_intent is not None:
        idx = _sub_intent_to_index.get(sub_intent)
        if idx is not None and intent in response_templates:
            templates = response_templates[intent]
            return templates[min(idx, len(templates) - 1)]

    # Priority 3: Intent-based static templates — delegate to keyword selector
    return _select_template(intent, original_message)

# ---------------------------------------------------------------------------
# Response templates — each entry addresses a distinct sub-problem
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
