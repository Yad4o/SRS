"""
app/api/admin.py

Purpose:
--------
Defines admin-level API endpoints for system monitoring and metrics.

Owner:
------
Om (Backend / Admin APIs)

Responsibilities:
-----------------
- Provide system-level metrics
- Expose aggregated ticket statistics
- Support operational monitoring

DO NOT:
-------
- Implement ticket resolution here
- Modify AI behavior here
- Expose sensitive personal data
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer

from app.db.session import get_db
from app.models.ticket import Ticket
from app.models.feedback import Feedback

router = APIRouter()


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """
    Retrieve high-level system metrics.

    Metrics may include:
    --------------------
    - Total number of tickets
    - Auto-resolved vs escalated tickets
    - Average feedback rating
    - Resolution success rate

    Implementation:
    ---------------
    - Count total tickets
    - Count tickets by status
    - Aggregate feedback ratings
    - Return metrics in structured format
    """

    # Count total tickets
    total_tickets = db.query(Ticket).count()
    
    # Count tickets by status
    auto_resolved = db.query(Ticket).filter(Ticket.status == "auto_resolved").count()
    escalated = db.query(Ticket).filter(Ticket.status == "escalated").count()
    open_tickets = db.query(Ticket).filter(Ticket.status == "open").count()
    closed_tickets = db.query(Ticket).filter(Ticket.status == "closed").count()
    
    # Aggregate feedback ratings
    feedback_stats = db.query(
        func.avg(Feedback.rating).label("avg_rating"),
        func.count(Feedback.id).label("total_feedback"),
        func.sum(func.cast(Feedback.resolved, Integer)).label("resolved_count")
    ).first()
    
    avg_rating = float(feedback_stats.avg_rating) if feedback_stats.avg_rating else 0.0
    total_feedback = feedback_stats.total_feedback or 0
    resolved_count = feedback_stats.resolved_count or 0
    
    # Calculate resolution success rate (percentage of feedback marked as resolved)
    resolution_success_rate = (
        (resolved_count / total_feedback * 100) if total_feedback > 0 else 0.0
    )
    
    # Calculate auto-resolution rate (percentage of tickets auto-resolved)
    auto_resolution_rate = (
        (auto_resolved / total_tickets * 100) if total_tickets > 0 else 0.0
    )

    return {
        "status": "success",
        "metrics": {
            "tickets": {
                "total": total_tickets,
                "open": open_tickets,
                "auto_resolved": auto_resolved,
                "escalated": escalated,
                "closed": closed_tickets,
            },
            "feedback": {
                "total_submissions": total_feedback,
                "average_rating": round(avg_rating, 2),
                "resolved_count": resolved_count,
            },
            "performance": {
                "auto_resolution_rate": round(auto_resolution_rate, 2),
                "resolution_success_rate": round(resolution_success_rate, 2),
            },
        },
    }
