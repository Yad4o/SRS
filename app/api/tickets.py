"""
app/api/tickets.py

Purpose:
Defines API endpoints for managing support tickets.

Responsibilities:
- Create support tickets
- Retrieve ticket information
- Trigger automated ticket resolution workflow

DO NOT:
- Implement AI classification here
- Implement resolution decision logic here
- Access external APIs directly here
"""


from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import update
from sqlalchemy.orm import Session
from typing import Annotated
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
from app.constants import TicketStatus, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, UserRole
from app.services.ticket_service import run_ticket_automation, extract_user_id_from_token, extract_user_id_and_role_from_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["Tickets"])

# Optional OAuth2 scheme for user identification (token is optional)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


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
        user_id = extract_user_id_from_token(token)

        # Step 1: Create ticket with initial status
        ticket = Ticket(
            message=ticket_data.message,
            status=TicketStatus.OPEN.value,
            user_id=user_id
        )
        
        # Save to database to get ID
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        # Step 2: Run AI pipeline
        try:
            ticket = run_ticket_automation(ticket=ticket, db=db)
            
        except Exception as ai_error:
            # AI failure: escalate for safety (never block user)
            logger.exception(f"AI pipeline failed for ticket {ticket.id}")
            
            # Rollback any partial AI processing, then escalate
            db.rollback()
            
            ticket.status = TicketStatus.ESCALATED.value
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
        description=f"Filter tickets by status ({TicketStatus.OPEN.value}, {TicketStatus.AUTO_RESOLVED.value}, {TicketStatus.ESCALATED.value}, {TicketStatus.CLOSED.value})",
        alias="status"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
) -> TicketList:
    """
    List tickets visible to the authenticated caller.

    Access rules
    ------------
    - Unauthenticated callers receive an empty list so anonymous-submitted
      tickets are not exposed to arbitrary internet requests.
    - Regular users see only their own tickets (user_id == caller).
    - Agents and admins see all tickets.

    Background on the original bug
    --------------------------------
    The previous code applied ``Ticket.user_id == user_id`` even when
    user_id was None.  SQLAlchemy translates ``Column == None`` to
    ``IS NULL``, so unauthenticated callers silently received every ticket
    with no owner (CWE-284 / improper access control).

    Args:
        ticket_status: Optional status filter
        limit: Page size (1–100)
        offset: Pagination offset
        db: Database session dependency
        token: Optional Bearer token

    Returns:
        TicketList: Tickets scoped to the caller's access level

    Raises:
        HTTPException 500 – database error
    """
    try:
        user_id, user_role = extract_user_id_and_role_from_token(token)

        is_privileged = user_role in (UserRole.ADMIN.value, UserRole.AGENT.value)

        # Unauthenticated callers receive an empty list.
        # Returning all user_id=NULL tickets to anonymous requests would
        # expose tickets submitted by other unauthenticated users.
        if user_id is None and not is_privileged:
            return TicketList(tickets=[], total=0)

        query = db.query(Ticket)

        # Apply status filter if provided
        if ticket_status:
            query = query.filter(Ticket.status == ticket_status)

        # Scope to caller's own tickets unless they are an agent or admin
        if not is_privileged:
            query = query.filter(Ticket.user_id == user_id)

        total = query.count()
        tickets = query.order_by(Ticket.created_at.desc()).limit(limit).offset(offset).all()

        ticket_responses = [TicketResponse.model_validate(ticket) for ticket in tickets]
        return TicketList(tickets=ticket_responses, total=total)

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to retrieve tickets")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving tickets",
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


@router.get("/my-assignments", response_model=TicketList)
def get_my_assignments(
    ticket_status: str | None = Query(
        None,
        description="Filter by status: escalated (unacknowledged) or in_progress (active)",
        alias="status",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin),
) -> TicketList:
    """
    List tickets assigned to the current agent.

    Returns tickets where ``assigned_agent_id`` matches the authenticated
    caller.  Agents see their own queue; admins calling this endpoint see
    tickets assigned specifically to themselves (not all agents).

    Status filter semantics
    -----------------------
    - ``escalated``   — assigned but not yet accepted (agent has not clicked Accept)
    - ``in_progress`` — agent has accepted and is actively working the ticket
    - ``closed``      — tickets the agent resolved / closed
    - omitted         — all statuses (escalated + in_progress + closed)

    Args:
        ticket_status: Optional status filter
        limit: Page size (1–100)
        offset: Pagination offset
        current_user: Authenticated agent/admin user

    Returns:
        TicketList: Tickets assigned to the current user
    """
    try:
        allowed = {
            TicketStatus.ESCALATED.value,
            TicketStatus.IN_PROGRESS.value,
            TicketStatus.CLOSED.value,
        }
        if ticket_status and ticket_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{ticket_status}'. Allowed: {', '.join(sorted(allowed))}",
            )

        query = (
            db.query(Ticket)
            .filter(Ticket.assigned_agent_id == current_user.id)
        )

        if ticket_status:
            query = query.filter(Ticket.status == ticket_status)

        total = query.count()
        tickets = query.order_by(Ticket.created_at.desc()).limit(limit).offset(offset).all()
        ticket_responses = [TicketResponse.model_validate(t) for t in tickets]

        logger.info(
            f"Agent {current_user.id} fetched my-assignments: "
            f"count={len(ticket_responses)}, filter={ticket_status}"
        )
        return TicketList(tickets=ticket_responses, total=total)

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to retrieve assignments for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while retrieving assignments",
        )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
) -> TicketResponse:
    """
    Retrieve a single ticket by ID.

    Access rules
    ------------
    - Unauthenticated callers receive 401 (tickets always belong to someone).
    - Regular users may only fetch their own tickets (404 otherwise, to avoid
      confirming ticket existence to unauthorised callers).
    - Agents and admins may fetch any ticket.

    Args:
        ticket_id: ID of the ticket to retrieve
        db: Database session dependency
        token: Optional Bearer token (unauthenticated → 401)

    Returns:
        TicketResponse: The requested ticket

    Raises:
        HTTPException 401 - no valid token supplied
        HTTPException 404 - ticket not found or not visible to the authenticated user
        HTTPException 500 - database error
    """
    try:
        # --- Auth gate -------------------------------------------------------
        # Resolve caller identity; unauthenticated requests are rejected so
        # users cannot probe arbitrary ticket IDs without a valid session.
        user_id, user_role = extract_user_id_and_role_from_token(token)

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access ticket details",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # --- Fetch -----------------------------------------------------------
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found",
            )

        # --- Ownership check -------------------------------------------------
        # Agents and admins can view any ticket; regular users are restricted
        # to their own submissions.
        is_privileged = user_role in (UserRole.ADMIN.value, UserRole.AGENT.value)
        if not is_privileged and ticket.user_id != user_id:
            # Return 404 instead of 403 to avoid confirming ticket existence
            # to unauthorised callers (OWASP IDOR guidance).
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket with ID {ticket_id} not found",
            )

        return TicketResponse.model_validate(ticket)

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to retrieve ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving ticket",
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
                Ticket.status == TicketStatus.ESCALATED.value,
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
            if ticket.assigned_agent_id == current_user.id and ticket.status == TicketStatus.ESCALATED.value:
                logger.info(f"Ticket {ticket_id} already assigned to user {current_user.id} (self-race)")
                return TicketResponse.model_validate(ticket)

            if ticket.assigned_agent_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ticket already assigned to agent {ticket.assigned_agent_id}",
                )
            if ticket.status != TicketStatus.ESCALATED.value:
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
                Ticket.status.in_([TicketStatus.ESCALATED.value, TicketStatus.AUTO_RESOLVED.value]),
            )
            .values(status=TicketStatus.CLOSED.value)
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






@router.post("/{ticket_id}/accept", response_model=TicketResponse)
def accept_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin)
) -> TicketResponse:
    """
    Accept an escalated ticket that has been assigned to the current agent.

    Transitions the ticket from ``escalated`` → ``in_progress``, signalling
    that the assigned agent has acknowledged the ticket and is actively
    working it.  Only the assigned agent (or an admin) may accept.

    The atomic UPDATE is the sole concurrency gate — there is no pre-fetch race.

    Args:
        ticket_id: ID of the ticket to accept
        db: Database session dependency
        current_user: Authenticated agent/admin user

    Returns:
        TicketResponse: The updated ticket with status=in_progress

    Raises:
        HTTPException 403 – caller is not the assigned agent
        HTTPException 404 – ticket not found
        HTTPException 409 – ticket not in an acceptable state
    """
    try:
        result = db.execute(
            update(Ticket)
            .where(
                Ticket.id == ticket_id,
                Ticket.assigned_agent_id == current_user.id,
                Ticket.status == TicketStatus.ESCALATED.value,
            )
            .values(status=TicketStatus.IN_PROGRESS.value)
        )

        if result.rowcount == 0:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

            if not ticket:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ticket {ticket_id} not found",
                )

            # Idempotent: already accepted by this agent
            if ticket.assigned_agent_id == current_user.id and ticket.status == TicketStatus.IN_PROGRESS.value:
                logger.info(f"Ticket {ticket_id} already in_progress for user {current_user.id} (idempotent)")
                return TicketResponse.model_validate(ticket)

            if ticket.assigned_agent_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the assigned agent may accept this ticket",
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ticket status is '{ticket.status}', cannot accept",
            )

        db.commit()
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        logger.info(f"Ticket {ticket_id} accepted (in_progress) by user {current_user.id}")
        return TicketResponse.model_validate(ticket)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to accept ticket {ticket_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while accepting ticket",
        ) from e
