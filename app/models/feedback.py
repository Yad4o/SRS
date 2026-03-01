"""
app/models/feedback.py

Purpose:
--------
Defines the Feedback database model.

Owner:
------
Om (Backend / Data Modeling)

Responsibilities:
-----------------
- Store user feedback for ticket resolutions
- Track whether auto-resolution was successful
- Enable future AI improvement

DO NOT:
-------
- Analyze feedback here
- Adjust AI models here
- Implement business logic here
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class Feedback(Base):
    """
    Feedback ORM model.

    Feedback is submitted by users after a ticket
    has been resolved (auto or human).
    """

    __tablename__ = "feedback"

    def __repr__(self):
        """Return a meaningful string representation of the feedback."""
        return f"<Feedback(id={self.id}, ticket_id={self.ticket_id}, rating={self.rating}, resolved={self.resolved})>"

    # -------------------------------------------------
    # Columns
    # -------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="Primary key identifier for feedback entry",
    )

    ticket_id = Column(
        Integer,
        ForeignKey('tickets.id'),
        nullable=False,
        doc="ID of ticket this feedback belongs to",
    )

    rating = Column(
        Integer,
        nullable=False,
        doc="User rating (e.g., 1–5)",
    )

    resolved = Column(
        Boolean,
        nullable=False,
        doc="Whether the issue was actually resolved",
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when feedback was submitted",
    )

    # -------------------------------------------------
    # Relationships
    # -------------------------------------------------
    
    ticket = relationship("Ticket", backref="feedback")

    # -------------------------------------------------
    # TODO (Future Enhancements)
    # -------------------------------------------------
    # - sentiment score
