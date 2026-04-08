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


from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import update
from sqlalchemy.orm import Session
import logging

from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketList,
)
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackCreateNested
from app.models.ticket import Ticket
from app.models.user import User
from app.models.feedback import Feedback
from app.services.feedback_service import create_feedback_record
from app.services.classifier import classify_intent
from app.services.response_generator import generate_response
from app.services.decision_engine import decide_resolution
from app.api.auth import decode_token, get_current_user
from app.api.dependencies import require_agent_or_admin
from app.core.config import settings
from app.db.session import get_db
from app.services.similarity_search import (
    find_similar_ticket,
    get_resolved_tickets,
    _get_cache_client,
    _cache_key
)
import json
from app.core.limiter import limiter

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
    # Check cache first to avoid DB query (Issue #10)
    cache = _get_cache_client()
    key = _cache_key(ticket.message) if cache else None
    similar_result = None
    
    if cache and key:
        try:
            cached = cache.get(key)
            if cached:
                similar_result = json.loads(cached)
                logger.info(f"Similarity cache hit for ticket {ticket.id}")
        except Exception:
            pass

    if similar_result is None:
        resolved_tickets = get_resolved_tickets(db)

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
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
def create_ticket(
    request: Request,
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
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
    ticket_status: str | None = Query(
        None,
        description="Filter tickets by status (open, auto_resolved, escalated, closed)",
        alias="status"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
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
        
        # Get total before pagination
        total = query.count()

        # Execute query with pagination (order by creation date, newest first)
        tickets = query.order_by(Ticket.created_at.desc()).limit(limit).offset(offset).all()
        
        # Convert to response schemas
        ticket_responses = [TicketResponse.model_validate(ticket) for ticket in tickets]
        
        return TicketList(tickets=ticket_responses, total=total)
        
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


@router.post("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin)
) -> TicketResponse:
    """
    Assign an escalated ticket to the current agent/admin.

    The atomic UPDATE is the sole concurrency gate — there is no pre-fetch race.
    All branching is driven by rowcount + a single post-update refresh.

    Args:
        ticket_id: ID of the ticket to assign
        db: Database session dependency
        current_user: Current authenticated agent/admin user

    Returns:
        TicketResponse: The updated ticket with assigned agent

    Raises:
        HTTPException: 404 if ticket not found, 409 on conflict, 403 if not agent/admin
    """
    try:
        # Single atomic UPDATE: only succeeds when the ticket exists, is escalated,
        # and has no assigned agent yet.  No pre-fetch → no TOCTOU window.
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.assigned_agent_id.is_(None),
                Ticket.status == "escalated",
            )
            .values(assigned_agent_id=current_user.id)
        )

        if result.rowcount == 0:
            # WHERE clause matched nothing — nothing was written, so no commit
            # is needed.  Read current DB state within this open transaction
            # to diagnose why and return the appropriate error.
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

            if not ticket:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ticket {ticket_id} not found",
                )

            # Self-race guard: same agent fired two concurrent assign requests;
            # the first succeeded (rowcount=1, now committed by peer), the second
            # lands here (rowcount=0) and finds the ticket already theirs.
            # Return 200 idempotently — nothing to commit.
            if ticket.assigned_agent_id == current_user.id and ticket.status == "escalated":
                logger.info(f"Ticket {ticket_id} already assigned to user {current_user.id} (self-race)")
                return TicketResponse.model_validate(ticket)

            if ticket.assigned_agent_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ticket already assigned to agent {ticket.assigned_agent_id}",
                )
            if ticket.status != "escalated":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ticket status changed to '{ticket.status}', cannot assign",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to assign ticket due to concurrent update",
            )

        # rowcount == 1: UPDATE succeeded.  Commit, then fetch for the response.
        db.commit()
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} not found",
            )

        logger.info(f"Ticket {ticket_id} assigned to user {current_user.id}")
        return TicketResponse.model_validate(ticket)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to assign ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while assigning ticket",
        ) from e


@router.post("/{ticket_id}/close", response_model=TicketResponse)
def close_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin)
) -> TicketResponse:
    """
    Close an escalated or auto_resolved ticket.

    The atomic UPDATE is the sole concurrency gate — there is no pre-fetch race.
    rowcount is checked before db.commit() so the commit only happens when a
    row was actually modified.  On the rowcount==0 path nothing was written, so
    the open transaction is read-only and will be rolled back automatically when
    the session closes.

    Args:
        ticket_id: ID of the ticket to close
        db: Database session dependency
        current_user: Current authenticated agent/admin user

    Returns:
        TicketResponse: The updated closed ticket

    Raises:
        HTTPException: 404 if ticket not found, 409 on conflict, 403 if not agent/admin
    """
    try:
        # Single atomic UPDATE: only succeeds when the ticket exists and is in
        # a closeable state.  No pre-fetch → no TOCTOU window.
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.status.in_(["escalated", "auto_resolved"]),
            )
            .values(status="closed")
        )

        if result.rowcount == 0:
            # WHERE clause matched nothing — nothing was written, no commit needed.
            # Read current state to diagnose why.
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

            if not ticket:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ticket {ticket_id} not found",
                )

            if ticket.status == "closed":
                # Idempotent: already closed (e.g. duplicate concurrent request).
                logger.info(f"Ticket {ticket_id} already closed, returning current state")
                return TicketResponse.model_validate(ticket)

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ticket status changed to '{ticket.status}', cannot close",
            )

        # rowcount == 1: UPDATE succeeded.  Commit, then fetch for the response.
        db.commit()
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} not found",
            )

        logger.info(f"Ticket {ticket_id} closed by user {current_user.id}")
        return TicketResponse.model_validate(ticket)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to close ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while closing ticket",
        ) from e


@router.post("/{ticket_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_ticket_feedback(
    ticket_id: int,
    feedback_data: FeedbackCreateNested,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """
    Create feedback for a resolved ticket.
    
    This endpoint allows users to submit feedback for tickets that have been
    resolved (either auto_resolved or closed). The feedback includes a rating
    and whether the issue was actually resolved.
    
    Args:
        ticket_id: ID of the ticket to provide feedback for
        feedback_data: Feedback data including rating and resolution status
        db: Database session dependency
        
    Returns:
        FeedbackResponse: Created feedback record
        
    Raises:
        HTTPException: If ticket not found, not resolved, or feedback already exists
    """
    try:
        feedback = create_feedback_record(
            db=db,
            ticket_id=ticket_id,
            rating=feedback_data.rating,
            resolved=feedback_data.resolved
        )
        return FeedbackResponse.model_validate(feedback)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404 for missing ticket)
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create feedback for ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating feedback"
        ) from e



