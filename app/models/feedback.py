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
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.session import Base


class Feedback(Base):
    """
    Feedback ORM model.

    Feedback is submitted by users after a ticket
    has been resolved (auto or human).
    """

    __tablename__ = "feedback"

    # NOTE:
    # -----
    # This UniqueConstraint is only created automatically for new databases.
    # The app's init_db() path uses Base.metadata.create_all(), which does NOT
    # apply ALTERs to existing tables. For existing deployments (or a checked-in
    # SQLite database), you MUST run an explicit migration or fully recreate the
    # database schema to ensure this uniqueness is enforced at the DB level.
    __table_args__ = (
        UniqueConstraint('ticket_id', name='uq_feedback_ticket_id'),
    )

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
    
    ticket = relationship("Ticket", back_populates="feedback")

    # -------------------------------------------------
    # TODO (Future Enhancements)
    # -------------------------------------------------
    # - sentiment score
