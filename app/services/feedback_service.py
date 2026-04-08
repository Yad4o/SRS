import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.feedback import Feedback
from app.models.ticket import Ticket

logger = logging.getLogger(__name__)

def create_feedback_record(db: Session, ticket_id: int, rating: int, resolved: bool) -> Feedback:
    """Helper method to encapsulate shared feedback creation logic."""
    # Validate that ticket exists
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket with ID {ticket_id} not found"
        )
    
    # Check if ticket is in resolved state
    if ticket.status not in ["auto_resolved", "closed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ticket {ticket_id} is not resolved (current status: {ticket.status})"
        )
    
    # Check for existing feedback to prevent duplicates
    existing_feedback = db.query(Feedback).filter(Feedback.ticket_id == ticket_id).first()
    if existing_feedback:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feedback already exists for ticket {ticket_id}"
        )
    
    # Create feedback record
    feedback = Feedback(
        ticket_id=ticket_id,
        rating=rating,
        resolved=resolved
    )
    
    # Ensure atomic transaction for both feedback and ticket updates
    db.add(feedback)
    
    # Compute quality score for the ticket
    base_score = rating / 5.0
    resolution_boost = 0.1 if resolved else -0.1
    ticket.quality_score = max(0.0, min(1.0, base_score + resolution_boost))
    
    # Commit both operations together
    db.commit()
    db.refresh(feedback)
    
    logger.info(f"Feedback created for ticket {ticket_id}: rating={rating}, resolved={resolved}")
    return feedback
