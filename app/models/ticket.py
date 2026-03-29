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
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship

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

    sub_intent = Column(
        String,
        nullable=True,
        doc="Sub-category of intent (e.g. password_reset)",
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

    is_archived = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="Whether the ticket has been archived by the cleanup worker",
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
        doc="Timestamp when the ticket was created",
    )

    # -------------------------------------------------
    # Relationships
    # -------------------------------------------------

    feedback = relationship(
        "Feedback",
        back_populates="ticket",
        uselist=False,
        doc="Feedback record for this ticket (one-to-one)",
    )
