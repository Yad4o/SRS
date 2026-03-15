"""
app/api/tickets.py

Purpose:
--------
Defines API endpoints for managing support tickets.

Owner:
------
Om (Backend / Core API)

Responsibilities:
-----------------
- Create support tickets
- Retrieve ticket information
- Trigger automated ticket resolution workflow

DO NOT:
-------
- Implement AI classification here
- Implement resolution decision logic here
- Access external APIs directly here
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketList,
)
from app.db.session import get_db
from app.models.ticket import Ticket
from app.services.classifier import classify_intent
from app.services.similarity_search import find_similar_ticket
from app.services.decision_engine import decide_resolution
from app.services.response_generator import generate_response
from app.core.config import settings
from fastapi import status

# Configure logging
logger = logging.getLogger(__name__)


def _run_ticket_automation(ticket: Ticket, db: Session) -> Ticket:
    """
    Run the AI automation pipeline for a given ticket.

    This function encapsulates the orchestration of:
    - Intent classification
    - Similarity search against resolved tickets
    - Resolution decision (auto-resolve vs escalate)
    - Response generation for auto-resolved tickets

    It updates and persists the ticket accordingly and returns the
    refreshed instance.
    """
    # Classify intent
    classification = classify_intent(ticket.message)
    intent = classification["intent"]
    confidence = classification["confidence"]

    # Update ticket with classification results
    ticket.intent = intent
    ticket.confidence = confidence

    # Fetch resolved tickets for similarity search
    resolved_tickets = (
        db.query(Ticket)
        .filter(
            Ticket.status == "auto_resolved",
            Ticket.response.isnot(None),
        )
        .order_by(Ticket.created_at.desc())
        .limit(50)
        .all()
    )

    # Convert to list of dicts for similarity search
    resolved_tickets_data = []
    for resolved_ticket in resolved_tickets:
        resolved_tickets_data.append(
            {
                "message": resolved_ticket.message,
                "response": resolved_ticket.response,
            }
        )

    # Find similar tickets
    similar_result = find_similar_ticket(
        ticket.message,
        resolved_tickets_data,
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
    )

    # Make decision
    decision = decide_resolution(confidence)

    # Process decision
    if decision == "AUTO_RESOLVE":
        # Generate response
        similar_solution = (
            similar_result["ticket"]["response"] if similar_result else None
        )
        response = generate_response(intent, ticket.message, similar_solution)

        # Update ticket
        ticket.status = "auto_resolved"
        ticket.response = response

        logger.info(
            f"Ticket {ticket.id} auto-resolved with intent {intent} "
            f"(confidence: {confidence})"
        )
    else:  # ESCALATE
        # Update ticket
        ticket.status = "escalated"
        ticket.response = None

        logger.info(
            f"Ticket {ticket.id} escalated with intent {intent} "
            f"(confidence: {confidence})"
        )

    # Save AI results
    db.commit()
    db.refresh(ticket)

    return ticket


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
) -> TicketResponse:
    """
    Create a new support ticket with AI automation.
    
    Flow:
    -----
    1. Validate input using TicketCreate schema
    2. Store ticket in database with status = 'open'
    3. Run AI pipeline:
       - Classify intent and confidence
       - Find similar resolved tickets
       - Make auto-resolve vs escalate decision
       - Generate response if auto-resolving
    4. Update ticket with AI results
    5. Return created ticket with AI processing results
    
    Args:
        ticket_data: Ticket creation data with message field
        db: Database session dependency
        
    Returns:
        TicketResponse: Created ticket with AI processing results
        
    Raises:
        HTTPException: If database operation fails
    """
    try:
        # Step 1: Create ticket with initial status
        ticket = Ticket(
            message=ticket_data.message,
            status="open"
        )
        
        # Save to database to get ID
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        # Step 2: Run AI pipeline
        try:
            ticket = _run_ticket_automation(ticket=ticket, db=db)
            
        except Exception as ai_error:
            # AI failure: escalate for safety (never block user)
            logger.exception(f"AI pipeline failed for ticket {ticket.id}: {ai_error}")
            
            # Rollback any partial AI processing, then escalate
            db.rollback()
            
            ticket.status = "escalated"
            ticket.intent = None
            ticket.confidence = None
            ticket.response = None
            
            db.commit()
            db.refresh(ticket)
        
        return TicketResponse.model_validate(ticket)
        
    except Exception as e:
        db.rollback()
        logger.exception("Failed to create ticket")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating ticket"
        )


@router.get("/", response_model=TicketList)
def list_tickets(
    ticket_status: Optional[str] = Query(
        None,
        description="Filter tickets by status (open, auto_resolved, escalated, closed)",
        alias="status"
    ),
    db: Session = Depends(get_db),
) -> TicketList:
    """
    List all tickets with optional status filtering.
    
    Args:
        ticket_status: Optional status filter
        db: Database session dependency
        
    Returns:
        TicketList: List of tickets matching criteria
        
    Raises:
        HTTPException: If database operation fails
    """
    try:
        # Build query
        query = db.query(Ticket)
        
        # Apply status filter if provided
        if ticket_status:
            query = query.filter(Ticket.status == ticket_status)
        
        # Execute query (order by creation date, newest first)
        tickets = query.order_by(Ticket.created_at.desc()).all()
        
        # Convert to response schemas
        ticket_responses = [TicketResponse.model_validate(ticket) for ticket in tickets]
        
        return TicketList(tickets=ticket_responses)
        
    except Exception as e:
        logger.exception("Failed to retrieve tickets")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving tickets"
        )


@router.get("/health", response_model=dict)
def tickets_health():
    """
    Health check endpoint for tickets API.
    
    Returns:
        dict: Health status of tickets service
    """
    return {
        "status": "healthy",
        "service": "tickets-api",
        "version": "0.1.0",
        "endpoints": [
            "POST /tickets/",
            "GET /tickets/",
            "GET /tickets/{id}"
        ]
    }


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> TicketResponse:
    """
    Retrieve a single ticket by ID.
    
    Args:
        ticket_id: ID of the ticket to retrieve
        db: Database session dependency
        
    Returns:
        TicketResponse: The requested ticket
        
    Raises:
        HTTPException: If ticket not found (404) or database error (500)
    """
    try:
        # Query ticket by ID
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found"
            )
        
        return TicketResponse.model_validate(ticket)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.exception(f"Failed to retrieve ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving ticket"
        )


# -------------------------------------------------
# TODO (Future Enhancements - Phase 3)
# -------------------------------------------------
# 
# POST /tickets/{id}/resolve - Trigger ticket resolution
# POST /tickets/{id}/escalate - Manual escalation
# GET /tickets/{id}/history - Ticket change history
# PUT /tickets/{id} - Update ticket (if needed)
# DELETE /tickets/{id} - Soft delete tickets
#
# AI Integration (Phase 3):
# - Automatic intent classification on ticket creation
# - Similarity search for duplicate detection
# - Auto-resolution for common issues
# - Confidence scoring and threshold handling
