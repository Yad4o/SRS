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
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging

from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketList,
)
from app.models.ticket import Ticket
from app.services.classifier import classify_intent
from app.services.response_generator import generate_response
from app.db.session import get_db
from app.core.config import settings
from fastapi import status
from app.services.similarity_search import find_similar_ticket
from app.services.decision_engine import decide_resolution
from app.api.auth import decode_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["Tickets"])

# Optional OAuth2 scheme for user identification (token is optional)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

# ---------------------------------------------------------------------------
# Internal automation helper
# ---------------------------------------------------------------------------
 
def _run_ticket_automation(ticket: Ticket, db: Session) -> Ticket:
    """
    Run the AI automation pipeline for a given ticket.
    - Intent classification
    - Similarity search against resolved tickets
    - Resolution decision (auto-resolve vs escalate)
    - Response generation for auto-resolved tickets
    """
    # Classify intent
    classification = classify_intent(ticket.message)
    intent = classification["intent"]
    confidence = classification["confidence"]
    sub_intent = classification.get("sub_intent")

    # Update ticket with classification results
    ticket.intent = intent
    ticket.confidence = confidence
    ticket.sub_intent = sub_intent

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
    resolved_tickets_data = [
        {"message": t.message, "response": t.response, "quality_score": t.quality_score}
        for t in resolved_tickets
    ]

    # Find similar tickets
    similar_result = find_similar_ticket(
        ticket.message,
        resolved_tickets_data,
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
    )

    # Extract similar quality score
    similar_quality_score = similar_result.get("quality_score") if similar_result else None

    # Make decision
    decision = decide_resolution(confidence)

    # Process decision
    if decision == "AUTO_RESOLVE":
        similar_solution = (
            similar_result["ticket"]["response"] if similar_result else None
        )
        response_text, response_source = generate_response(
            intent,
            ticket.message,
            similar_solution=similar_solution,
            sub_intent=sub_intent,
            similar_quality_score=similar_quality_score,
        )
        ticket.response = response_text
        ticket.response_source = response_source
        ticket.status = "auto_resolved"
        logger.info(
            f"Ticket {ticket.id} {decision.lower()} with intent {intent} "
            f"(confidence: {confidence})"
        )
    else:  # ESCALATE
        ticket.status = "escalated"
        ticket.response = None
        logger.info(
            f"Ticket {ticket.id} escalated with intent {intent} "
            f"(confidence: {confidence})"
        )

    # Save AI results
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

  


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional),
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
        # Extract user_id from optional token
        user_id = None
        if token:
            try:
                payload = decode_token(token)
                sub = payload.get("sub")
                if sub:
                    user_id = int(sub)
            except Exception as e:
                logger.debug("Token decode failed — treating as unauthenticated", exc_info=True)
                pass  # Invalid token — treat as unauthenticated

        # Step 1: Create ticket with initial status
        ticket = Ticket(
            message=ticket_data.message,
            status="open",
            user_id=user_id
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
            ticket.sub_intent = None 
            ticket.response = None
            
            db.commit()
            db.refresh(ticket)
        
        return TicketResponse.model_validate(ticket)
        
    except HTTPException:
        # Re-raise HTTP exceptions (including 401 from token validation)
        raise
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
    token: Optional[str] = Depends(oauth2_scheme_optional),
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
        # Extract user_id and role from optional token
        user_id = None
        user_role = None
        if token:
            try:
                payload = decode_token(token)
                sub = payload.get("sub")
                if sub:
                    user_id = int(sub)
                    user_role = payload.get("role")
            except Exception as e:
                logger.debug("Failed to decode token, showing all tickets", exc_info=True)
                pass  # Invalid token — show all tickets

        # Build query
        query = db.query(Ticket)
        
        # Apply status filter if provided
        if ticket_status:
            query = query.filter(Ticket.status == ticket_status)
        
        # Apply user filter for non-admin/agent users
        if user_id and user_role not in ["admin", "agent"]:
            query = query.filter(Ticket.user_id == user_id)
        
        # Execute query (order by creation date, newest first)
        tickets = query.order_by(Ticket.created_at.desc()).all()
        
        # Convert to response schemas
        ticket_responses = [TicketResponse.model_validate(ticket) for ticket in tickets]
        
        return TicketList(tickets=ticket_responses)
        
    except HTTPException:
        # Re-raise HTTP exceptions (including 401 from token validation)
        raise
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



