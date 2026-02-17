"""
tests/test_admin.py

Purpose:
--------
Comprehensive tests for admin API endpoints.

Coverage:
---------
- Test metrics endpoint with various data scenarios
- Test empty database edge cases
- Test partial data scenarios
- Test calculation accuracy
- Test null safety

Owner:
------
Om (Backend / Testing)
"""

import pytest
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.models.feedback import Feedback


# -------------------------------------------------
# Helper Functions
# -------------------------------------------------

def create_ticket(db: Session, message: str, intent: str = None, 
                  confidence: float = None, status: str = "open") -> Ticket:
    """
    Helper function to create a test ticket.
    """
    ticket = Ticket(
        message=message,
        intent=intent,
        confidence=confidence,
        status=status,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def create_feedback(db: Session, ticket_id: int, rating: int, 
                    resolved: bool) -> Feedback:
    """
    Helper function to create test feedback.
    """
    feedback = Feedback(
        ticket_id=ticket_id,
        rating=rating,
        resolved=resolved,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


# -------------------------------------------------
# Test Cases: Empty Database
# -------------------------------------------------

def test_metrics_empty_database(client):
    """
    Test metrics endpoint with no data in database.
    Should return zero values without errors.
    """
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    assert data["metrics"]["tickets"]["total"] == 0
    assert data["metrics"]["tickets"]["open"] == 0
    assert data["metrics"]["tickets"]["auto_resolved"] == 0
    assert data["metrics"]["tickets"]["escalated"] == 0
    assert data["metrics"]["tickets"]["closed"] == 0
    assert data["metrics"]["feedback"]["total_submissions"] == 0
    assert data["metrics"]["feedback"]["average_rating"] == 0.0
    assert data["metrics"]["feedback"]["resolved_count"] == 0
    assert data["metrics"]["performance"]["auto_resolution_rate"] == 0.0
    assert data["metrics"]["performance"]["resolution_success_rate"] == 0.0


# -------------------------------------------------
# Test Cases: Ticket Counting
# -------------------------------------------------

def test_metrics_ticket_counts(client, test_db):
    """
    Test accurate counting of tickets by status.
    """
    # Create tickets with different statuses
    create_ticket(test_db, "Login issue", status="open")
    create_ticket(test_db, "Payment problem", status="open")
    create_ticket(test_db, "Account question", status="auto_resolved")
    create_ticket(test_db, "Bug report", status="auto_resolved")
    create_ticket(test_db, "Feature request", status="auto_resolved")
    create_ticket(test_db, "Complex issue", status="escalated")
    create_ticket(test_db, "Closed ticket", status="closed")
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 7
    assert data["metrics"]["tickets"]["open"] == 2
    assert data["metrics"]["tickets"]["auto_resolved"] == 3
    assert data["metrics"]["tickets"]["escalated"] == 1
    assert data["metrics"]["tickets"]["closed"] == 1


def test_metrics_only_open_tickets(client, test_db):
    """
    Test metrics when all tickets are open.
    """
    create_ticket(test_db, "Issue 1", status="open")
    create_ticket(test_db, "Issue 2", status="open")
    create_ticket(test_db, "Issue 3", status="open")
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 3
    assert data["metrics"]["tickets"]["open"] == 3
    assert data["metrics"]["tickets"]["auto_resolved"] == 0
    assert data["metrics"]["tickets"]["escalated"] == 0
    assert data["metrics"]["performance"]["auto_resolution_rate"] == 0.0


def test_metrics_all_auto_resolved(client, test_db):
    """
    Test metrics when all tickets are auto-resolved.
    """
    create_ticket(test_db, "Issue 1", status="auto_resolved")
    create_ticket(test_db, "Issue 2", status="auto_resolved")
    create_ticket(test_db, "Issue 3", status="auto_resolved")
    create_ticket(test_db, "Issue 4", status="auto_resolved")
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 4
    assert data["metrics"]["tickets"]["auto_resolved"] == 4
    assert data["metrics"]["performance"]["auto_resolution_rate"] == 100.0


# -------------------------------------------------
# Test Cases: Feedback Aggregation
# -------------------------------------------------

def test_metrics_feedback_average_rating(client, test_db):
    """
    Test accurate calculation of average feedback rating.
    """
    ticket1 = create_ticket(test_db, "Issue 1", status="auto_resolved")
    ticket2 = create_ticket(test_db, "Issue 2", status="auto_resolved")
    ticket3 = create_ticket(test_db, "Issue 3", status="auto_resolved")
    
    create_feedback(test_db, ticket1.id, rating=5, resolved=True)
    create_feedback(test_db, ticket2.id, rating=4, resolved=True)
    create_feedback(test_db, ticket3.id, rating=3, resolved=False)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Average: (5 + 4 + 3) / 3 = 4.0
    assert data["metrics"]["feedback"]["total_submissions"] == 3
    assert data["metrics"]["feedback"]["average_rating"] == 4.0
    assert data["metrics"]["feedback"]["resolved_count"] == 2


def test_metrics_feedback_all_resolved(client, test_db):
    """
    Test resolution success rate when all feedback is positive.
    """
    ticket1 = create_ticket(test_db, "Issue 1", status="auto_resolved")
    ticket2 = create_ticket(test_db, "Issue 2", status="auto_resolved")
    
    create_feedback(test_db, ticket1.id, rating=5, resolved=True)
    create_feedback(test_db, ticket2.id, rating=5, resolved=True)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["feedback"]["resolved_count"] == 2
    assert data["metrics"]["performance"]["resolution_success_rate"] == 100.0


def test_metrics_feedback_none_resolved(client, test_db):
    """
    Test resolution success rate when no feedback is positive.
    """
    ticket1 = create_ticket(test_db, "Issue 1", status="auto_resolved")
    ticket2 = create_ticket(test_db, "Issue 2", status="auto_resolved")
    
    create_feedback(test_db, ticket1.id, rating=1, resolved=False)
    create_feedback(test_db, ticket2.id, rating=2, resolved=False)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["feedback"]["resolved_count"] == 0
    assert data["metrics"]["performance"]["resolution_success_rate"] == 0.0


def test_metrics_feedback_partial_resolution(client, test_db):
    """
    Test resolution success rate with mixed feedback.
    """
    ticket1 = create_ticket(test_db, "Issue 1", status="auto_resolved")
    ticket2 = create_ticket(test_db, "Issue 2", status="auto_resolved")
    ticket3 = create_ticket(test_db, "Issue 3", status="auto_resolved")
    ticket4 = create_ticket(test_db, "Issue 4", status="auto_resolved")
    
    create_feedback(test_db, ticket1.id, rating=5, resolved=True)
    create_feedback(test_db, ticket2.id, rating=4, resolved=True)
    create_feedback(test_db, ticket3.id, rating=3, resolved=True)
    create_feedback(test_db, ticket4.id, rating=2, resolved=False)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # 3 out of 4 resolved = 75%
    assert data["metrics"]["feedback"]["total_submissions"] == 4
    assert data["metrics"]["feedback"]["resolved_count"] == 3
    assert data["metrics"]["performance"]["resolution_success_rate"] == 75.0


# -------------------------------------------------
# Test Cases: Performance Metrics
# -------------------------------------------------

def test_metrics_auto_resolution_rate_calculation(client, test_db):
    """
    Test accurate calculation of auto-resolution rate.
    """
    # 6 auto-resolved out of 10 total = 60%
    create_ticket(test_db, "Issue 1", status="auto_resolved")
    create_ticket(test_db, "Issue 2", status="auto_resolved")
    create_ticket(test_db, "Issue 3", status="auto_resolved")
    create_ticket(test_db, "Issue 4", status="auto_resolved")
    create_ticket(test_db, "Issue 5", status="auto_resolved")
    create_ticket(test_db, "Issue 6", status="auto_resolved")
    create_ticket(test_db, "Issue 7", status="escalated")
    create_ticket(test_db, "Issue 8", status="escalated")
    create_ticket(test_db, "Issue 9", status="open")
    create_ticket(test_db, "Issue 10", status="closed")
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 10
    assert data["metrics"]["tickets"]["auto_resolved"] == 6
    assert data["metrics"]["performance"]["auto_resolution_rate"] == 60.0


def test_metrics_resolution_success_rate_calculation(client, test_db):
    """
    Test accurate calculation of resolution success rate.
    """
    # Create 10 tickets and 8 feedback entries
    tickets = []
    for i in range(10):
        ticket = create_ticket(test_db, f"Issue {i+1}", status="auto_resolved")
        tickets.append(ticket)
    
    # 6 out of 8 feedback marked as resolved = 75%
    create_feedback(test_db, tickets[0].id, rating=5, resolved=True)
    create_feedback(test_db, tickets[1].id, rating=5, resolved=True)
    create_feedback(test_db, tickets[2].id, rating=4, resolved=True)
    create_feedback(test_db, tickets[3].id, rating=4, resolved=True)
    create_feedback(test_db, tickets[4].id, rating=4, resolved=True)
    create_feedback(test_db, tickets[5].id, rating=3, resolved=True)
    create_feedback(test_db, tickets[6].id, rating=2, resolved=False)
    create_feedback(test_db, tickets[7].id, rating=1, resolved=False)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["feedback"]["total_submissions"] == 8
    assert data["metrics"]["feedback"]["resolved_count"] == 6
    assert data["metrics"]["performance"]["resolution_success_rate"] == 75.0


# -------------------------------------------------
# Test Cases: Edge Cases
# -------------------------------------------------

def test_metrics_tickets_without_feedback(client, test_db):
    """
    Test metrics when tickets exist but no feedback submitted.
    """
    create_ticket(test_db, "Issue 1", status="auto_resolved")
    create_ticket(test_db, "Issue 2", status="escalated")
    create_ticket(test_db, "Issue 3", status="open")
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 3
    assert data["metrics"]["feedback"]["total_submissions"] == 0
    assert data["metrics"]["feedback"]["average_rating"] == 0.0
    assert data["metrics"]["performance"]["resolution_success_rate"] == 0.0


def test_metrics_feedback_without_tickets_visible(client, test_db):
    """
    Test that feedback can exist even if tickets are deleted/archived.
    Note: In production, this would use foreign key constraints.
    """
    # Create and then rely on feedback alone
    ticket = create_ticket(test_db, "Issue 1", status="auto_resolved")
    create_feedback(test_db, ticket.id, rating=5, resolved=True)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 1
    assert data["metrics"]["feedback"]["total_submissions"] == 1


def test_metrics_decimal_precision(client, test_db):
    """
    Test that metrics are rounded to 2 decimal places.
    """
    # Create scenario with non-round percentages
    # 5 auto-resolved out of 10 total = 50.0%
    create_ticket(test_db, "Issue 1", status="auto_resolved")
    create_ticket(test_db, "Issue 2", status="auto_resolved")
    create_ticket(test_db, "Issue 3", status="escalated")
    create_ticket(test_db, "Issue 4", status="escalated")
    create_ticket(test_db, "Issue 5", status="open")
    create_ticket(test_db, "Issue 6", status="open")
    create_ticket(test_db, "Issue 7", status="closed")
    
    ticket1 = create_ticket(test_db, "Issue 8", status="auto_resolved")
    ticket2 = create_ticket(test_db, "Issue 9", status="auto_resolved")
    ticket3 = create_ticket(test_db, "Issue 10", status="auto_resolved")
    
    # Average: (5 + 4 + 2) / 3 = 3.666... → 3.67
    create_feedback(test_db, ticket1.id, rating=5, resolved=True)
    create_feedback(test_db, ticket2.id, rating=4, resolved=True)
    create_feedback(test_db, ticket3.id, rating=2, resolved=False)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Average rating: (5 + 4 + 2) / 3 = 3.666... → 3.67
    assert isinstance(data["metrics"]["feedback"]["average_rating"], float)
    assert data["metrics"]["feedback"]["average_rating"] == 3.67
    
    # Auto resolution: 5 auto-resolved out of 10 total = 50.0%
    assert data["metrics"]["performance"]["auto_resolution_rate"] == 50.0
    
    # Resolution success: 2/3 = 66.666... → 66.67%
    assert data["metrics"]["performance"]["resolution_success_rate"] == 66.67


# -------------------------------------------------
# Test Cases: Response Structure
# -------------------------------------------------

def test_metrics_response_structure(client):
    """
    Test that response has correct structure and keys.
    """
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Top-level keys
    assert "status" in data
    assert "metrics" in data
    
    # Metrics sub-keys
    assert "tickets" in data["metrics"]
    assert "feedback" in data["metrics"]
    assert "performance" in data["metrics"]
    
    # Ticket keys
    assert "total" in data["metrics"]["tickets"]
    assert "open" in data["metrics"]["tickets"]
    assert "auto_resolved" in data["metrics"]["tickets"]
    assert "escalated" in data["metrics"]["tickets"]
    assert "closed" in data["metrics"]["tickets"]
    
    # Feedback keys
    assert "total_submissions" in data["metrics"]["feedback"]
    assert "average_rating" in data["metrics"]["feedback"]
    assert "resolved_count" in data["metrics"]["feedback"]
    
    # Performance keys
    assert "auto_resolution_rate" in data["metrics"]["performance"]
    assert "resolution_success_rate" in data["metrics"]["performance"]


def test_metrics_data_types(client, test_db):
    """
    Test that all metrics return correct data types.
    """
    # Create some test data
    ticket = create_ticket(test_db, "Test issue", status="auto_resolved")
    create_feedback(test_db, ticket.id, rating=4, resolved=True)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check data types
    assert isinstance(data["status"], str)
    assert isinstance(data["metrics"]["tickets"]["total"], int)
    assert isinstance(data["metrics"]["tickets"]["open"], int)
    assert isinstance(data["metrics"]["tickets"]["auto_resolved"], int)
    assert isinstance(data["metrics"]["tickets"]["escalated"], int)
    assert isinstance(data["metrics"]["tickets"]["closed"], int)
    assert isinstance(data["metrics"]["feedback"]["total_submissions"], int)
    assert isinstance(data["metrics"]["feedback"]["average_rating"], float)
    assert isinstance(data["metrics"]["feedback"]["resolved_count"], int)
    assert isinstance(data["metrics"]["performance"]["auto_resolution_rate"], float)
    assert isinstance(data["metrics"]["performance"]["resolution_success_rate"], float)


# -------------------------------------------------
# Test Cases: Large Dataset
# -------------------------------------------------

def test_metrics_large_dataset(client, test_db):
    """
    Test metrics with a large number of tickets and feedback.
    """
    # Create 100 tickets with various statuses
    for i in range(100):
        if i < 50:
            status = "auto_resolved"
        elif i < 75:
            status = "escalated"
        elif i < 90:
            status = "open"
        else:
            status = "closed"
        
        ticket = create_ticket(test_db, f"Issue {i+1}", status=status)
        
        # Add feedback for auto-resolved tickets
        if status == "auto_resolved":
            resolved = i % 3 != 0  # 2 out of 3 resolved
            rating = 5 if resolved else 2
            create_feedback(test_db, ticket.id, rating=rating, resolved=resolved)
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 100
    assert data["metrics"]["tickets"]["auto_resolved"] == 50
    assert data["metrics"]["tickets"]["escalated"] == 25
    assert data["metrics"]["tickets"]["open"] == 15
    assert data["metrics"]["tickets"]["closed"] == 10
    assert data["metrics"]["feedback"]["total_submissions"] == 50
    assert data["metrics"]["performance"]["auto_resolution_rate"] == 50.0


# -------------------------------------------------
# Test Cases: Null Safety
# -------------------------------------------------

def test_metrics_null_intent_confidence(client, test_db):
    """
    Test that tickets with null intent/confidence are counted correctly.
    """
    create_ticket(test_db, "Issue 1", intent=None, confidence=None, status="open")
    create_ticket(test_db, "Issue 2", intent="login_issue", confidence=0.8, status="auto_resolved")
    
    response = client.get("/admin/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["metrics"]["tickets"]["total"] == 2
    assert data["metrics"]["tickets"]["open"] == 1
    assert data["metrics"]["tickets"]["auto_resolved"] == 1
