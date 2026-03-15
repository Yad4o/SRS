"""
app/schemas/ticket.py

Purpose:
--------
Defines Pydantic schemas for Ticket-related API requests and responses.

Owner:
------
Om (Backend / API Contracts)

Responsibilities:
-----------------
- Validate ticket creation input
- Shape ticket-related API responses
- Expose ticket lifecycle safely to clients

DO NOT:
-------
- Access database here
- Implement AI classification here
- Change ticket status here
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class TicketCreate(BaseModel):
    """
    Schema used when a user creates a new support ticket.

    Used in:
    --------
    POST /tickets

    Fields:
    -------
    - message: Raw customer message describing the issue
    """

    message: str

    # TODO (Validation Enhancements):
    # - minimum message length
    # - profanity filtering (optional)


class TicketResolveRequest(BaseModel):
    """
    Schema used to trigger ticket resolution.

    Used in:
    --------
    POST /tickets/{ticket_id}/resolve

    Currently empty, but exists for future extensibility.
    """

    # TODO:
    # - force_human: bool
    pass


class TicketResponse(BaseModel):
    """
    Schema returned when fetching or resolving a ticket.

    Used in:
    --------
    GET /tickets/{id}
    POST /tickets/{id}/resolve
    """

    id: int
    message: str
    intent: Optional[str]
    confidence: Optional[float]
    status: str
    response: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Alias for TicketResponse as specified in deliverables
TicketRead = TicketResponse


class TicketList(BaseModel):
    """
    Schema returned when fetching a list of tickets.

    Used in:
    --------
    GET /tickets

    Fields:
    -------
    - tickets: List of TicketResponse objects
    """

    tickets: List[TicketResponse]
