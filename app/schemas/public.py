"""
app/schemas/public.py

Purpose:
Request/response schemas for the public, unauthenticated resolution API
(app/api/public.py). Kept separate from schemas/ticket.py because this
API is intentionally decoupled from the ticket/agent/admin data model —
it takes a message and returns an answer, nothing else.
"""

from pydantic import BaseModel, Field


class ResolveRequest(BaseModel):
    """Body for POST /resolve. Just the message — no auth, no ticket ID."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The customer's question or issue, as plain text.",
        examples=["I was charged twice for my last order, can I get a refund?"],
    )


class ResolveResponse(BaseModel):
    """Result of running the AI pipeline against a message."""

    intent: str | None = Field(None, description="Classified intent, e.g. 'billing'.")
    sub_intent: str | None = Field(None, description="More specific sub-category, if detected.")
    confidence: float | None = Field(None, description="Classifier confidence, 0.0-1.0.")
    sentiment: str | None = Field(None, description="Detected sentiment, e.g. 'negative'.")
    sentiment_confidence: float | None = Field(None, description="Sentiment confidence, 0.0-1.0.")
    decision: str = Field(..., description="'AUTO_RESOLVE' or 'ESCALATE'.")
    response: str | None = Field(
        None,
        description="AI-generated answer, present only when decision is AUTO_RESOLVE.",
    )
    response_source: str | None = Field(
        None, description="Where the response came from, e.g. 'template' or 'similar_ticket'."
    )
