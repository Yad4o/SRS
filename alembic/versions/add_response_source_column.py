"""add_response_source_column

Revision ID: add_response_source_column
Revises: 
Create Date: 2026-04-01 11:46:33.244477

WARNING
-------
DO NOT run this migration automatically.
The `response_source` column is already defined in the ORM model
(app/models/ticket.py). This file exists as a reference for manual
schema synchronisation if a production DB needs an explicit ALTER TABLE.
Apply only when intentionally migrating an older schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_response_source_column'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add response_source column to tickets table
    op.add_column('tickets', sa.Column('response_source', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove response_source column from tickets table
    op.drop_column('tickets', 'response_source')
