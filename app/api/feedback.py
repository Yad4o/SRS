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
- Keep feedback collection simple and reliable

DO NOT:
-------
- Analyze feedback here
- Modify AI logic here
- Change ticket resolution status here
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.schemas.ticket import FeedbackCreate as TicketFeedbackCreate, FeedbackResponse as TicketFeedbackResponse
from app.db.session import get_db
from app.models.feedback import Feedback
from app.models.ticket import Ticket

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"]
)


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_feedback(
    feedback_data: TicketFeedbackCreate,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """
    Create feedback record for a ticket.
    
    Flow:
    -----
    1. Validate feedback input using TicketFeedbackCreate schema
    2. Ensure ticket exists before creating feedback
    3. Store feedback in database
    4. Return created feedback record
    
    Args:
        feedback_data: Feedback creation data with ticket_id, rating, resolved
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Created feedback record
        
    Raises:
        HTTPException: If ticket not found (404) or database error (500)
    """
    try:
        # Validate that ticket exists
        ticket = db.query(Ticket).filter(Ticket.id == feedback_data.ticket_id).first()
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {feedback_data.ticket_id} not found"
            )
        
        # Validate rating range (1-5)
        if not (1 <= feedback_data.rating <= 5):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 1 and 5"
            )
        
        # Create feedback record
        feedback = Feedback(
            ticket_id=feedback_data.ticket_id,
            rating=feedback_data.rating,
            resolved=feedback_data.resolved
        )
        
        # Save to database
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        logger.info(f"Feedback created for ticket {feedback_data.ticket_id}: rating={feedback_data.rating}, resolved={feedback_data.resolved}")
        
        return FeedbackResponse.model_validate(feedback)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404, 400)
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create feedback for ticket {feedback_data.ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating feedback"
        )


@router.get("/health", response_model=dict)
def feedback_health():
    """
    Health check endpoint for feedback API.
    
    Returns:
        dict: Health status of feedback service
    """
    return {
        "status": "healthy",
        "service": "feedback-api",
        "version": "0.1.0",
        "endpoints": [
            "POST /feedback/",
            "GET /feedback/{ticket_id}",
            "GET /feedback/?ticket_id=..."
        ]
    }


@router.get("/{ticket_id}", response_model=FeedbackResponse)
def get_feedback_by_ticket_id(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """
    Retrieve feedback for a specific ticket by ID.
    
    Args:
        ticket_id: ID of the ticket to retrieve feedback for
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Feedback record for the ticket
        
    Raises:
        HTTPException: If feedback not found (404) or database error (500)
    """
    try:
        # Query feedback by ticket_id
        feedback = db.query(Feedback).filter(Feedback.ticket_id == ticket_id).first()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback for ticket {ticket_id} not found"
            )
        
        return FeedbackResponse.model_validate(feedback)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve feedback for ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving feedback"
        )


@router.get("/", response_model=FeedbackResponse)
def get_feedback_by_query(
    ticket_id: int = Query(..., description="ID of the ticket to retrieve feedback for"),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """
    Retrieve feedback for a ticket using query parameter.
    
    Alternative to GET /feedback/{ticket_id} using query parameter.
    
    Args:
        ticket_id: ID of the ticket to retrieve feedback for (query parameter)
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Feedback record for the ticket
        
    Raises:
        HTTPException: If feedback not found (404) or database error (500)
    """
    try:
        # Query feedback by ticket_id
        feedback = db.query(Feedback).filter(Feedback.ticket_id == ticket_id).first()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback for ticket {ticket_id} not found"
            )
        
        return FeedbackResponse.model_validate(feedback)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve feedback for ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving feedback"
        )


@router.get("/health", response_model=dict)
def feedback_health():
    """
    Health check endpoint for feedback API.
    
    Returns:
        dict: Health status of feedback service
    """
    return {
        "status": "healthy",
        "service": "feedback-api",
        "version": "0.1.0",
        "endpoints": [
            "POST /feedback/",
            "GET /feedback/{ticket_id}",
            "GET /feedback/?ticket_id=..."
        ]
    }
