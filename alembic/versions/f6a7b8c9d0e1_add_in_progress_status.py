"""add_in_progress_status

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-01 10:00:00.000000

Background
----------
The ticket lifecycle was missing the ``in_progress`` status that sits
between ``escalated`` (unassigned) and ``closed``.  The frontend had
the status designed (StatusBadge, TicketStatus type) and the UI wired
(AgentQueue Active tab, TicketView Accept button) but the backend never
implemented it.

This migration is a no-op at the database level because ``status`` is a
plain VARCHAR with no CHECK constraint.  It exists to document the change,
serve as a marker for the new endpoints that consume this status
(POST /tickets/{id}/accept, GET /tickets/my-assignments), and allow
future migrations to reference this revision.
"""
from typing import Sequence, Union
from alembic import op


# revision identifiers
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    No schema change required — status is VARCHAR, not a native ENUM.
    New valid value 'in_progress' is enforced at the application layer
    via TicketStatus enum in app/constants.py.
    """
    pass


def downgrade() -> None:
    """
    Revert any in_progress tickets to escalated on downgrade so the
    previous app version sees a valid status for those rows.
    """
    op.execute(
        "UPDATE tickets SET status = 'escalated' WHERE status = 'in_progress'"
    )
