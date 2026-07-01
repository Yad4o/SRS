"""
app/schemas/admin.py

Purpose:
Pydantic response models for admin-level API endpoints.

Responsibilities:
- Validate and document the shape of admin metrics responses
- Validate and document the shape of admin ticket list responses
"""

from pydantic import BaseModel


class TicketStatsSchema(BaseModel):
    total: int
    by_status: dict[str, int]
    auto_resolve_rate: float
    escalation_rate: float
    open: int
    auto_resolved: int
    escalated: int
    unassigned_escalated: int


class FeedbackStatsSchema(BaseModel):
    total: int
    average_rating: float
    resolution_rate: float
    resolved_count: int


class QualityStatsSchema(BaseModel):
    low_quality_count: int
    by_intent: dict[str, float]


class SystemHealthSchema(BaseModel):
    auto_resolve_rate_status: str
    escalation_rate_status: str
    feedback_coverage: float


class MetricsResponse(BaseModel):
    """
    Response schema for GET /admin/metrics.
    """
    tickets: TicketStatsSchema
    feedback: FeedbackStatsSchema
    quality: QualityStatsSchema
    system_health: SystemHealthSchema


class AdminTicketItem(BaseModel):
    """
    Single ticket entry in the admin ticket list.

    Fields kept in sync with TicketResponse so that admin pages and
    shared components (TicketTable, StatusBadge, etc.) work correctly.
    Previously, missing fields caused the Escalations page to always show
    an empty list: assigned_agent_id was never serialized, so the frontend
    filter (t.assigned_agent_id === null) always returned an empty array
    even when unassigned escalated tickets existed in the database.
    """
    id: int
    message: str
    status: str
    intent: str | None = None
    sub_intent: str | None = None
    confidence: float | None = None
    sentiment: str | None = None
    sentiment_confidence: float | None = None
    response: str | None = None
    response_source: str | None = None
    quality_score: float | None = None
    user_id: int | None = None
    assigned_agent_id: int | None = None
    created_at: str | None = None


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class AdminAssignRequest(BaseModel):
    """Request body for POST /admin/tickets/{id}/assign."""
    agent_id: int


class AgentListItem(BaseModel):
    """Single agent entry returned by GET /admin/agents."""
    id: int
    email: str
    role: str


class FiltersMeta(BaseModel):
    status: str | None = None


class AdminTicketListResponse(BaseModel):
    """
    Response schema for GET /admin/tickets.
    """
    tickets: list[AdminTicketItem]
    pagination: PaginationMeta
    filters: FiltersMeta

