"""add_ticket_sentiment_columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-28 00:00:01.000000

Adds sentiment + sentiment_confidence columns to tickets (Issue #2 —
sentiment analysis existed but was never wired into the ticket pipeline).

Reversibility:
  downgrade() drops both columns. No data-preservation concern — these
  are derived/AI-generated fields, not user-entered data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add sentiment and sentiment_confidence columns to tickets."""
    op.add_column("tickets", sa.Column("sentiment", sa.String(), nullable=True))
    op.add_column("tickets", sa.Column("sentiment_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove sentiment and sentiment_confidence columns from tickets."""
    op.drop_column("tickets", "sentiment_confidence")
    op.drop_column("tickets", "sentiment")
