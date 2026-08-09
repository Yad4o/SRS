"""
app/api/public.py

Purpose:
The public-facing API. One endpoint, no login, nothing stored.

Send a message, get back an intent classification and (when confident
enough) an AI-generated answer — instantly. This is the endpoint meant
to be embedded in other people's apps/repos: no API key, no signup, no
session to manage. Point a client at POST /resolve and you're integrated.

Responsibilities:
- Accept a raw message and return the AI pipeline's result
- Stay stateless: no ticket is created, nothing is written to the DB

DO NOT:
- Add auth requirements here — that defeats the point of this router
- Persist anything here — see app/api/tickets.py if you need ticket history
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.public import ResolveRequest, ResolveResponse
from app.services.ticket_service import resolve_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Public API"])


@router.post(
    "/resolve",
    response_model=ResolveResponse,
    summary="Classify + answer a message — no login required",
)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
def resolve(
    request: Request,
    payload: ResolveRequest,
    db: Session = Depends(get_db),
) -> ResolveResponse:
    """
    The one endpoint you need.

    Send `{"message": "..."}`, get back a classification and, when the
    model is confident enough, a ready-to-use answer. No auth header,
    no ticket record, no side effects — safe to call from a browser,
    a script, or another backend.

    Example:
        curl -X POST https://<your-deployment>/resolve \\
          -H "Content-Type: application/json" \\
          -d '{"message": "How do I reset my password?"}'
    """
    result = resolve_message(payload.message, db, log_ref="public-resolve")
    return ResolveResponse(**result)
