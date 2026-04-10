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
from app.services.classifier import classify_intent
from app.services.decision_engine import decide_resolution
from app.services.response_generator import generate_response
from app.services.similarity_search import (
    find_similar_ticket,
    get_resolved_tickets,
    _get_cache_client,
    _cache_key,
)

logger = logging.getLogger(__name__)


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


def run_ticket_automation(ticket: Ticket, db: Session) -> Ticket:
    """
    Run the AI automation pipeline for a given ticket.

    Steps:
        1. Classify intent via classifier service
        2. Check similarity cache; fall back to DB query + similarity search
        3. Make auto-resolve vs. escalate decision
        4. Generate a response for auto-resolved tickets
        5. Persist results and return the updated ticket

    Args:
        ticket: Ticket ORM instance (already persisted with an ID).
        db: Active SQLAlchemy session.

    Returns:
        Updated Ticket instance with intent, confidence, status, and response set.
    """
    # --- Step 1: Classify intent ---
    classification = classify_intent(ticket.message)
    intent = classification["intent"]
    confidence = classification["confidence"]
    sub_intent = classification.get("sub_intent")

    ticket.intent = intent
    ticket.confidence = confidence
    ticket.sub_intent = sub_intent

    # --- Step 2: Similarity search (cache-first) ---
    cache = _get_cache_client()
    key = _cache_key(ticket.message) if cache else None
    similar_result = None

    if cache and key:
        try:
            cached = cache.get(key)
            if cached:
                similar_result = json.loads(cached)
                logger.info(f"Similarity cache hit for ticket {ticket.id}")
        except Exception:
            pass  # Cache failure is non-fatal; fall through to DB

    if similar_result is None:
        resolved_tickets = get_resolved_tickets(db)
        resolved_tickets_data = [
            {"message": t.message, "response": t.response, "quality_score": t.quality_score}
            for t in resolved_tickets
        ]
        similar_result = find_similar_ticket(
            ticket.message,
            resolved_tickets_data,
            similarity_threshold=settings.SIMILARITY_THRESHOLD,
        )

    similar_quality_score = similar_result.get("quality_score") if similar_result else None

    # --- Step 3: Resolution decision ---
    decision = decide_resolution(confidence)

    # --- Step 4: Generate response or escalate ---
    if decision == "AUTO_RESOLVE":
        similar_solution = (
            similar_result["ticket"]["response"] if similar_result else None
        )
        response_text, response_source = generate_response(
            intent,
            ticket.message,
            similar_solution=similar_solution,
            sub_intent=sub_intent,
            similar_quality_score=similar_quality_score,
        )
        ticket.response = response_text
        ticket.response_source = response_source
        ticket.status = TicketStatus.AUTO_RESOLVED.value
        logger.info(
            f"Ticket {ticket.id} auto_resolved with intent {intent} "
            f"(confidence: {confidence})"
        )
    else:  # ESCALATE
        ticket.status = TicketStatus.ESCALATED.value
        ticket.response = None
        logger.info(
            f"Ticket {ticket.id} escalated with intent {intent} "
            f"(confidence: {confidence})"
        )

    # --- Step 5: Persist ---
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

