"""
app/api/feedback.py

Purpose:
--------
Defines API endpoints for collecting user feedback.

Owner:
------
Om (Backend / API Layer)

Responsibilities:
-----------------
- Accept feedback for resolved tickets
- Store feedback in database
- Retrieve feedback for tickets
- Keep feedback collection simple and reliable

DO NOT:
-------
- Analyze feedback here
- Modify AI logic here
- Change ticket resolution status here
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.db.session import get_db
from app.models.feedback import Feedback
from app.models.ticket import Ticket

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"]
)


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


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=FeedbackResponse)
def create_feedback(
    feedback_data: FeedbackCreate,
    db: Session = Depends(get_db),
):
    """
    Create feedback for a resolved ticket.
    
    Flow:
    -----
    1. Validate feedback input using FeedbackCreate schema
    2. Ensure ticket exists
    3. Store feedback in database
    4. Return created feedback record
    
    Args:
        feedback_data: Feedback creation data with ticket_id, rating, resolved
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Created feedback record
        
    Raises:
        HTTPException: If ticket not found or database operation fails
    """
    try:
        feedback = create_feedback_record(
            db=db,
            ticket_id=feedback_data.ticket_id,
            rating=feedback_data.rating,
            resolved=feedback_data.resolved
        )
        return FeedbackResponse.model_validate(feedback)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for missing ticket)
        raise
    except IntegrityError as e:
        db.rollback()
        # This IntegrityError handler is effectively a defensive backup for a concurrent-insert race 
        # condition because create_feedback_record already pre-checks for existing feedback
        if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e).lower():
            logger.exception(f"Concurrent insert race detected: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Feedback already exists for ticket {feedback_data.ticket_id}"
            )
        else:
            logger.exception("Database integrity error while creating feedback")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error occurred while creating feedback"
            )
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating feedback"
        )


@router.get("/{ticket_id}", response_model=FeedbackResponse)
def get_feedback_by_ticket_id(
    ticket_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve feedback for a specific ticket by ticket ID.
    
    Args:
        ticket_id: ID of the ticket to get feedback for
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Feedback record for the ticket
        
    Raises:
        HTTPException: If feedback not found or database operation fails
    """
    try:
        # Get feedback for the ticket
        feedback = db.query(Feedback).filter(Feedback.ticket_id == ticket_id).first()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No feedback found for ticket with ID {ticket_id}"
            )
        
        return FeedbackResponse.model_validate(feedback)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve feedback for ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving feedback"
        )


@router.get("/", response_model=FeedbackResponse)
def get_feedback_by_query(
    ticket_id: int = Query(..., description="ID of the ticket to get feedback for"),
    db: Session = Depends(get_db),
):
    """
    Retrieve feedback for a ticket using query parameter.
    
    Alternative endpoint to /{ticket_id} for flexibility.
    
    Args:
        ticket_id: Query parameter for ticket ID
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Feedback record for the ticket
        
    Raises:
        HTTPException: If feedback not found or database operation fails
    """
    # Delegate to the path-parameter endpoint to keep behavior and error handling consistent
    return get_feedback_by_ticket_id(ticket_id=ticket_id, db=db)
