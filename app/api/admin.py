"""
app/api/admin.py

Purpose:
Defines admin-level API endpoints for system monitoring and metrics.

Responsibilities:
- Provide system-level metrics
- Expose aggregated ticket statistics
- Support operational monitoring
- Restrict access to admin users only

DO NOT:
- Implement ticket resolution here
- Modify AI behavior here
- Expose sensitive personal data
- Allow non-admin access
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from typing import Annotated, Any
import logging

from app.db.session import get_db
from app.models.ticket import Ticket
from app.models.feedback import Feedback
from app.models.user import User
from app.api.auth import get_current_user
from app.constants import UserRole, TicketStatus
from app.schemas.admin import MetricsResponse, AdminTicketListResponse, AdminTicketItem, FiltersMeta, PaginationMeta
from app.core.exceptions import (
    AuthorizationError,
    ValidationError,
    InternalError
)

# Configure logger
logger = logging.getLogger(__name__)

# Allowed ticket statuses for validation
ALLOWED_TICKET_STATUSES = {
    TicketStatus.OPEN.value,
    TicketStatus.AUTO_RESOLVED.value,
    TicketStatus.ESCALATED.value,
    TicketStatus.CLOSED.value
}

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """
    Dependency to ensure current user has admin role.
    
    Args:
        current_user: Current authenticated user from JWT token
        
    Returns:
        Current user if admin
        
    Raises:
        AuthorizationError: If user is not admin
    """
    if current_user.role != UserRole.ADMIN.value:
        raise AuthorizationError("Access denied. Admin role required.")
    return current_user


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    current_user: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db)
):
    """
    Retrieve high-level system metrics.
    
    This endpoint provides aggregated statistics about the system performance
    and is restricted to admin users only.
    
    Args:
        current_user: Admin user (from require_admin dependency)
        db: Database session dependency
        
    Returns:
        Dictionary containing system metrics:
        - total_tickets: Total number of tickets
        - tickets_by_status: Count of tickets grouped by status
        - auto_resolve_rate: Percentage of tickets auto-resolved
        - escalation_rate: Percentage of tickets escalated
        - total_feedback: Total number of feedback entries
        - average_rating: Average feedback rating (1-5)
        - feedback_resolution_rate: Percentage of feedback indicating resolution
        
    Raises:
        AuthorizationError: 403 if not admin, 500 for database errors
    """
    try:
        # Ticket statistics
        total_tickets = db.query(Ticket).count()
        
        tickets_by_status = (
            db.query(Ticket.status, func.count(Ticket.id))
            .group_by(Ticket.status)
            .all()
        )
        
        status_counts = {status: count for status, count in tickets_by_status}
        
        auto_resolved = status_counts.get(TicketStatus.AUTO_RESOLVED.value, 0)
        escalated = status_counts.get(TicketStatus.ESCALATED.value, 0)
        open_tickets = status_counts.get(TicketStatus.OPEN.value, 0)
        
        # Calculate rates (avoid division by zero)
        auto_resolve_rate = (auto_resolved / total_tickets * 100) if total_tickets > 0 else 0
        escalation_rate = (escalated / total_tickets * 100) if total_tickets > 0 else 0
        
        # Count unassigned escalated tickets
        unassigned_escalated = db.query(Ticket).filter(
            Ticket.status == TicketStatus.ESCALATED.value,
            Ticket.assigned_agent_id.is_(None)
        ).count()
        
        # Feedback statistics
        total_feedback = db.query(Feedback).count()
        
        # Use a simpler approach for counting resolved feedback
        resolved_feedback_count = db.query(Feedback).filter(Feedback.resolved.is_(True)).count()
        avg_rating_result = db.query(func.avg(Feedback.rating)).scalar()
        average_rating = float(avg_rating_result) if avg_rating_result else 0.0
        
        feedback_resolution_rate = (resolved_feedback_count / total_feedback * 100) if total_feedback > 0 else 0
        
        # Quality metrics
        low_quality_tickets = db.query(Ticket).filter(
            Ticket.quality_score.isnot(None),
            Ticket.quality_score < 0.5
        ).count()
        
        quality_by_intent = (
            db.query(Ticket.intent, func.avg(Ticket.quality_score))
            .filter(Ticket.quality_score.isnot(None))
            .group_by(Ticket.intent)
            .all()
        )
        
        metrics = {
            "tickets": {
                "total": total_tickets,
                "by_status": status_counts,
                "auto_resolve_rate": round(auto_resolve_rate, 2),
                "escalation_rate": round(escalation_rate, 2),
                "open": open_tickets,
                "auto_resolved": auto_resolved,
                "escalated": escalated,
                "unassigned_escalated": unassigned_escalated
            },
            "feedback": {
                "total": total_feedback,
                "average_rating": round(average_rating, 2),
                "resolution_rate": round(feedback_resolution_rate, 2),
                "resolved_count": resolved_feedback_count
            },
            "quality": {
                "low_quality_count": low_quality_tickets,
                "by_intent": {intent: round(float(score), 2) for intent, score in quality_by_intent if intent}
            },
            "system_health": {
                "auto_resolve_rate_status": "good" if auto_resolve_rate >= 70 else "needs_improvement",
                "escalation_rate_status": "good" if escalation_rate <= 30 else "needs_improvement",
                "feedback_coverage": round((total_feedback / total_tickets * 100), 2) if total_tickets > 0 else 0
            }
        }
        
        logger.info(f"Admin metrics retrieved by user {current_user.id}")
        return metrics
        
    except Exception as e:
        logger.exception("Failed to retrieve admin metrics")
        raise InternalError("Failed to retrieve metrics") from e


@router.get("/tickets", response_model=AdminTicketListResponse)
def list_all_tickets(
    current_user: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
    status_filter: str | None = Query(None, alias="status", description="Filter by ticket status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page")
):
    """
    List all tickets with optional filtering and pagination.
    
    This endpoint provides access to all tickets in the system
    and is restricted to admin users only.
    
    Args:
        current_user: Admin user (from require_admin dependency)
        db: Database session dependency
        status_filter: Optional filter for ticket status (from query parameter "status")
        page: Page number for pagination
        limit: Number of items per page
        
    Returns:
        Dictionary containing:
        - tickets: List of tickets
        - pagination: Pagination metadata
        - filters: Applied filters
        
    Raises:
        AuthorizationError: 403 if not admin, ValidationError for invalid status, 500 for database errors
    """
    # Validate status filter if provided
    if status_filter is not None and status_filter not in ALLOWED_TICKET_STATUSES:
        raise ValidationError(
            f"Invalid status '{status_filter}'. Allowed statuses: {', '.join(sorted(ALLOWED_TICKET_STATUSES))}"
        )
    
    try:
        # Build base query
        query = db.query(Ticket)
        
        # Apply status filter if provided
        if status_filter:
            query = query.filter(Ticket.status == status_filter)
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        tickets = query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()
        
        # Convert to response format
        ticket_list = []
        for ticket in tickets:
            ticket_data = {
                "id": ticket.id,
                "message": ticket.message,
                "status": ticket.status,
                "intent": ticket.intent,
                "confidence": ticket.confidence,
                "response": ticket.response,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None
            }
            ticket_list.append(ticket_data)
        
        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit
        has_next = page < total_pages
        has_prev = page > 1
        
        response = {
            "tickets": ticket_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            },
            "filters": {
                "status": status_filter
            }
        }
        
        logger.info(f"Admin tickets list retrieved by user {current_user.id}: page={page}, filter={status_filter}")
        return response
        
    except Exception as e:
        logger.exception("Failed to retrieve admin tickets list")
        raise InternalError("Failed to retrieve tickets") from e

