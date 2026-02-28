"""
Demo API endpoints for viewing database data.

This module provides endpoints to explore the demo data
through the FastAPI application.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.db.session import get_db
from app.models.user import User
from app.models.ticket import Ticket
from app.models.feedback import Feedback
from sqlalchemy import func, text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/tables", response_model=Dict[str, Any])
def get_table_info(db: Session = Depends(get_db)):
    """Get overview of all tables and record counts."""
    try:
        # Get table names
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]
        
        # Get record counts
        table_info = {}
        for table in ['users', 'tickets', 'feedback']:
            if table in tables:
                count_result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()
                table_info[table] = count
        
        return {
            "tables": tables,
            "record_counts": table_info,
            "total_records": sum(table_info.values())
        }
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/users", response_model=List[Dict[str, Any]])
def get_users(db: Session = Depends(get_db)):
    """Get all users with their details."""
    try:
        users = db.query(User).all()
        return [
            {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
            for user in users
        ]
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/tickets", response_model=List[Dict[str, Any]])
def get_tickets(db: Session = Depends(get_db)):
    """Get all tickets with AI classification details."""
    try:
        tickets = db.query(Ticket).all()
        return [
            {
                "id": ticket.id,
                "message": ticket.message,
                "intent": ticket.intent,
                "confidence": ticket.confidence,
                "status": ticket.status,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None
            }
            for ticket in tickets
        ]
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/feedback", response_model=List[Dict[str, Any]])
def get_feedback(db: Session = Depends(get_db)):
    """Get all feedback with ticket relationships."""
    try:
        feedback_list = db.query(Feedback).all()
        return [
            {
                "id": fb.id,
                "ticket_id": fb.ticket_id,
                "rating": fb.rating,
                "resolved": fb.resolved,
                "created_at": fb.created_at.isoformat() if fb.created_at else None
            }
            for fb in feedback_list
        ]
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/analytics", response_model=Dict[str, Any])
def get_analytics(db: Session = Depends(get_db)):
    """Get business intelligence analytics from demo data."""
    try:
        # Tickets by status
        status_counts = db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
        tickets_by_status = {status: count for status, count in status_counts}
        
        # Average feedback rating
        avg_rating = db.query(func.avg(Feedback.rating)).scalar()
        
        # High confidence tickets
        high_conf_count = db.query(Ticket).filter(Ticket.confidence > 0.9).count()
        
        # Resolution rate from feedback
        total_feedback = db.query(Feedback).count()
        resolved_feedback = db.query(Feedback).filter(Feedback.resolved == True).count()
        resolution_rate = (resolved_feedback / total_feedback * 100) if total_feedback > 0 else 0
        
        return {
            "tickets_by_status": tickets_by_status,
            "average_feedback_rating": round(avg_rating, 2) if avg_rating else 0,
            "high_confidence_tickets": high_conf_count,
            "total_tickets": db.query(Ticket).count(),
            "total_feedback": total_feedback,
            "resolution_rate": round(resolution_rate, 2)
        }
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/relationships", response_model=List[Dict[str, Any]])
def get_feedback_with_tickets(db: Session = Depends(get_db)):
    """Get feedback with associated ticket details (shows relationships)."""
    try:
        feedback_with_tickets = db.query(
            Feedback.id,
            Feedback.rating,
            Feedback.resolved,
            Ticket.message,
            Ticket.status,
            Ticket.intent,
            Ticket.confidence
        ).join(Ticket).all()
        
        return [
            {
                "feedback_id": fb_id,
                "rating": rating,
                "resolved": resolved,
                "ticket_message": (
                    ((message or "")[:100] + "...") if len(message or "") > 100 else (message or "")
                ),
                "ticket_status": status,
                "ticket_intent": intent,
                "ticket_confidence": confidence
            }
            for fb_id, rating, resolved, message, status, intent, confidence in feedback_with_tickets
        ]
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/summary", response_model=Dict[str, Any])
def get_demo_summary(db: Session = Depends(get_db)):
    """Get complete demo data summary in one endpoint."""
    try:
        return {
            "database_info": get_table_info(db),
            "users": get_users(db),
            "tickets": get_tickets(db),
            "feedback": get_feedback(db),
            "analytics": get_analytics(db),
            "relationships": get_feedback_with_tickets(db)
        }
    except SQLAlchemyError:
        logger.exception("Database operation failed")
        raise HTTPException(status_code=500, detail="Database error")
