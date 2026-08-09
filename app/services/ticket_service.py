"""
app/services/ticket_service.py

Purpose:
Business logic for ticket processing and automation pipeline.
Backend / Service Layer

Responsibilities:
- Run AI automation pipeline for ticket classification and resolution
- Extract user identity from optional JWT tokens
- Coordinate classifier, similarity search, decision engine, and response generator

DO NOT:
- Handle HTTP request/response here
- Access FastAPI Request/Response objects directly
"""

import json
import logging

from sqlalchemy.orm import Session

from app.constants import TicketStatus
from app.core.config import settings
from app.models.ticket import Ticket
from app.services.ai_service import SentimentAnalysisService
from app.services.classifier import classify_intent_ai
from app.services.decision_engine import decide_resolution
from app.services.response_generator import generate_response
from app.services.similarity_search import (
    find_similar_ticket,
    get_resolved_tickets,
    _get_cache_client,
    _cache_key,
)

logger = logging.getLogger(__name__)

# Stateless wrapper, safe to share across requests — see
# app/services/ai_service.py:SentimentAnalysisService.
_sentiment_service = SentimentAnalysisService()


def extract_user_id_from_token(token: str | None) -> int | None:
    """
    Safely decode an optional Bearer token and return the user_id (sub claim).

    Args:
        token: Raw JWT string, or None if the request is unauthenticated.

    Returns:
        Integer user ID extracted from the "sub" claim, or None if the token
        is absent, invalid, or does not carry a parseable subject.
    """
    if not token:
        return None
    try:
        # Import here to avoid circular imports — auth depends on models,
        # ticket_service must not depend on api.auth at module level.
        from app.core.security import decode_token  # local import avoids circular dep
        payload = decode_token(token)
        sub = payload.get("sub")
        if sub:
            return int(sub)
    except Exception:
        logger.debug("Token decode failed — treating as unauthenticated", exc_info=True)
    return None


def extract_user_id_and_role_from_token(token: str | None) -> tuple[int | None, str | None]:
    """
    Safely decode an optional Bearer token and return (user_id, role).

    Args:
        token: Raw JWT string, or None if the request is unauthenticated.

    Returns:
        Tuple of (user_id, role), both None if token is absent or invalid.
    """
    if not token:
        return None, None
    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        sub = payload.get("sub")
        role = payload.get("role")
        user_id = int(sub) if sub else None
        return user_id, role
    except Exception:
        logger.debug("Token decode failed — treating as unauthenticated", exc_info=True)
    return None, None


def resolve_message(message: str, db: Session, *, log_ref: str = "message") -> dict:
    """
    Run the full AI resolution pipeline for a raw message and return the
    result as a plain dict — no Ticket row is created or modified.

    This is the core logic shared by:
    - The public, unauthenticated ``POST /resolve`` endpoint (stateless).
    - ``run_ticket_automation`` below (persists the result onto a Ticket).

    Steps:
        1. Classify intent via classifier service (LLM-first, rule-based fallback)
        1b. Analyze sentiment (LLM-first, keyword-heuristic fallback)
        2. Check similarity cache; fall back to DB query + similarity search
        3. Make auto-resolve vs. escalate decision, with a safety override:
           negative sentiment forces escalation even at high intent confidence
        4. Generate a response when auto-resolving

    Args:
        message: Raw customer message to classify and (maybe) answer.
        db: Active SQLAlchemy session (used read-only, for the similarity
            corpus of previously-resolved tickets).
        log_ref: Short label used in log lines to identify the caller
            (e.g. a ticket ID, or "public-resolve") — purely cosmetic.

    Returns:
        dict with keys: intent, sub_intent, confidence, sentiment,
        sentiment_confidence, decision ("AUTO_RESOLVE" | "ESCALATE"),
        response, response_source.
    """
    # --- Step 1: Classify intent ---
    # classify_intent_ai tries the configured LLM first and transparently
    # falls back to the deterministic rule-based classifier on any
    # failure or missing config (Issue #1 — classifier was rule-based only).
    classification = classify_intent_ai(message)
    intent = classification["intent"]
    confidence = classification["confidence"]
    sub_intent = classification.get("sub_intent")

    # --- Step 1b: Sentiment analysis ---
    # Issue #2 — sentiment analysis existed in ai_service.py but was never
    # called from the actual pipeline. analyze_sentiment() is already
    # wrapped in BaseAIService.safe_execute(), so it cannot raise; the
    # try/except here is an extra safety net around our own extraction
    # logic, consistent with "AI pipeline failure must never block a
    # response" elsewhere in this function.
    sentiment = None
    sentiment_confidence = None
    sentiment_escalate = False
    try:
        sentiment_outcome = _sentiment_service.analyze_sentiment(message)
        sentiment_data = sentiment_outcome.get("data") or {}
        sentiment = sentiment_data.get("sentiment")
        sentiment_confidence = sentiment_data.get("confidence")
        sentiment_escalate = bool(sentiment_data.get("escalate", False))
    except Exception:
        logger.warning(
            f"Sentiment analysis failed for {log_ref}; continuing without it",
            exc_info=True,
        )

    # --- Step 2: Similarity search (cache-first) ---
    cache = _get_cache_client()
    key = _cache_key(message) if cache else None
    similar_result = None

    if cache and key:
        try:
            cached = cache.get(key)
            if cached:
                similar_result = json.loads(cached)
                logger.info(f"Similarity cache hit for {log_ref}")
        except Exception:
            pass  # Cache failure is non-fatal; fall through to DB

    if similar_result is None:
        resolved_tickets = get_resolved_tickets(db)
        resolved_tickets_data = [
            {"message": t.message, "response": t.response, "quality_score": t.quality_score}
            for t in resolved_tickets
        ]
        similar_result = find_similar_ticket(
            message,
            resolved_tickets_data,
            similarity_threshold=settings.SIMILARITY_THRESHOLD,
        )

    similar_quality_score = similar_result.get("quality_score") if similar_result else None

    # --- Step 3: Resolution decision ---
    decision = decide_resolution(confidence)

    # Safety override: an upset customer shouldn't get a robotic
    # auto-reply just because the intent classifier was confident about
    # *what* they're asking — route to a human instead. This mirrors the
    # codebase's existing "any uncertainty -> escalate" philosophy
    # (see app/services/decision_engine.py), applied to sentiment instead
    # of intent confidence.
    if decision == "AUTO_RESOLVE" and sentiment_escalate:
        decision = "ESCALATE"
        logger.info(
            f"{log_ref} overridden to escalate due to negative sentiment "
            f"(sentiment={sentiment}, sentiment_confidence={sentiment_confidence})"
        )

    # --- Step 4: Generate response or escalate ---
    response_text: str | None = None
    response_source: str | None = None
    if decision == "AUTO_RESOLVE":
        similar_solution = (
            similar_result["ticket"]["response"] if similar_result else None
        )
        response_text, response_source = generate_response(
            intent,
            message,
            similar_solution=similar_solution,
            sub_intent=sub_intent,
            similar_quality_score=similar_quality_score,
        )
        logger.info(f"{log_ref} auto_resolved with intent {intent} (confidence: {confidence})")
    else:  # ESCALATE
        logger.info(f"{log_ref} escalated with intent {intent} (confidence: {confidence})")

    return {
        "intent": intent,
        "sub_intent": sub_intent,
        "confidence": confidence,
        "sentiment": sentiment,
        "sentiment_confidence": sentiment_confidence,
        "decision": decision,
        "response": response_text,
        "response_source": response_source,
    }


def run_ticket_automation(ticket: Ticket, db: Session) -> Ticket:
    """
    Run the AI automation pipeline for a given ticket and persist the result.

    Thin wrapper around :func:`resolve_message` that maps the pipeline
    result onto a Ticket row, sets its status, and commits.

    Args:
        ticket: Ticket ORM instance (already persisted with an ID).
        db: Active SQLAlchemy session.

    Returns:
        Updated Ticket instance with intent, confidence, status, and response set.
    """
    result = resolve_message(ticket.message, db, log_ref=f"Ticket {ticket.id}")

    ticket.intent = result["intent"]
    ticket.sub_intent = result["sub_intent"]
    ticket.confidence = result["confidence"]
    ticket.sentiment = result["sentiment"]
    ticket.sentiment_confidence = result["sentiment_confidence"]

    if result["decision"] == "AUTO_RESOLVE":
        ticket.response = result["response"]
        ticket.response_source = result["response_source"]
        ticket.status = TicketStatus.AUTO_RESOLVED.value
    else:
        ticket.status = TicketStatus.ESCALATED.value
        ticket.response = None

    # --- Persist ---
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

