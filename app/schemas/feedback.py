"""
app/schemas/feedback.py

Purpose:
Defines Pydantic schemas for Feedback-related API requests and responses.

Responsibilities:
- Validate feedback submitted by users
- Define clean API input/output contracts
- Protect internal analytics logic

DO NOT:
- Store feedback in database here
- Analyze feedback here
- Modify AI confidence thresholds here
"""

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class FeedbackCreate(BaseModel):
    """
    Schema used when a user submits feedback for a resolved ticket.

    Used in:
    POST /feedback

    Fields:
    - ticket_id: ID of the ticket being rated
    - rating: User rating (1-5) for resolution quality
    - resolved: Whether the issue was actually resolved
    """

    ticket_id: int = Field(..., gt=0, description="ID of the ticket to provide feedback for")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (poor) to 5 (excellent)")
    resolved: bool = Field(..., description="Whether the user's issue was actually resolved")


class FeedbackCreateNested(BaseModel):
    """
    Schema used when submitting feedback via nested route /tickets/{ticket_id}/feedback.

    Used in:
    POST /tickets/{ticket_id}/feedback

    Fields:
    - rating: User rating (1-5) for resolution quality
    - resolved: Whether the issue was actually resolved
    """

    rating: int = Field(..., ge=1, le=5, description="Rating from 1 (poor) to 5 (excellent)")
    resolved: bool = Field(..., description="Whether the user's issue was actually resolved")


class FeedbackResponse(BaseModel):
    """
    Schema returned when fetching feedback for a ticket.

    Used in:
    GET /feedback/{ticket_id}
    GET /feedback?ticket_id=...

    Fields:
    - id: Feedback record ID
    - ticket_id: Associated ticket ID
    - rating: User rating
    - resolved: Resolution status
    - created_at: Feedback submission timestamp
    """

    id: int
    ticket_id: int
    rating: int
    resolved: bool
    quality_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Alias for FeedbackResponse as specified in deliverables



class FeedbackList(BaseModel):
    """
    Schema for a collection of feedback entries.

    Fields:
    - feedback: List of FeedbackResponse objects
    """

    feedback: list[FeedbackResponse]

