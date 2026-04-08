"""
app/schemas/admin.py

Purpose:
--------
Pydantic response models for admin-level API endpoints.

Owner:
------
Om (Backend / API Contracts)

Responsibilities:
-----------------
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
    """Single ticket entry in the admin ticket list."""
    id: int
    message: str
    status: str
    intent: str | None = None
    confidence: float | None = None
    response: str | None = None
    created_at: str | None = None


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class FiltersMeta(BaseModel):
    status: str | None = None


class AdminTicketListResponse(BaseModel):
    """
    Response schema for GET /admin/tickets.
    """
    tickets: list[AdminTicketItem]
    pagination: PaginationMeta
    filters: FiltersMeta
