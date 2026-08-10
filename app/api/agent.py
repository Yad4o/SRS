"""
app/api/agent.py

Purpose:
Agent-only ticket-queue actions: claiming, working, and closing escalated
tickets. Split out from app/api/tickets.py so the agent workflow lives in
its own place, separate from the public/basic ticket endpoints.

Responsibilities:
- List the current agent's assigned queue
- Assign / accept / close tickets

Everything here requires an authenticated agent or admin
(app.api.dependencies.require_agent_or_admin). Nothing in this file is
reachable without a valid token.

DO NOT:
- Implement AI classification or resolution logic here
- Add endpoints reachable without agent/admin auth
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.dependencies import require_agent_or_admin
from app.constants import TicketStatus
from app.db.session import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import TicketList, TicketResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])


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


@router.post("/tickets/{ticket_id}/assign", response_model=TicketResponse)
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


@router.post("/tickets/{ticket_id}/accept", response_model=TicketResponse)
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


@router.post("/tickets/{ticket_id}/close", response_model=TicketResponse)
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
