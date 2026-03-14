"""
app/models/ticket.py

Purpose:
--------
Defines the Ticket database model.

Owner:
------
Om (Backend / Data Modeling)

Responsibilities:
-----------------
- Represent customer support tickets
- Store AI classification results
- Track ticket lifecycle status

DO NOT:
-------
- Perform AI classification here
- Implement resolution logic here
- Write database queries here
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime

from app.db.session import Base


class Ticket(Base):
    """
    Ticket ORM model.

    Each ticket represents a single customer support request
    submitted by a user.
    """

    __tablename__ = "tickets"

    def __init__(self, **kwargs):
        """Initialize Ticket with default status if not provided."""
        if 'status' not in kwargs:
            kwargs['status'] = 'open'
        super().__init__(**kwargs)

    # -------------------------------------------------
    # Columns
    # -------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="Primary key identifier for the ticket",
    )

    message = Column(
        String,
        nullable=False,
        doc="Original customer message",
    )

    intent = Column(
        String,
        nullable=True,
        doc="Predicted intent (e.g., login_issue, payment, refund)",
    )

    confidence = Column(
        Float,
        nullable=True,
        doc="AI confidence score for predicted intent (0.0 - 1.0)",
    )

    status = Column(
        String,
        default="open",
        nullable=False,
        doc="Ticket status: open | auto_resolved | escalated | closed",
    )

    response = Column(
        String,
        nullable=True,
        doc="AI-generated response for auto-resolved tickets",
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when ticket was created",
    )

    # -------------------------------------------------
    # TODO (Future Enhancements)
    # -------------------------------------------------
    # - updated_at timestamp
    # - resolved_at timestamp
    # - user_id (foreign key)
