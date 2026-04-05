"""add_assigned_agent_id_column

Revision ID: add_assigned_agent_id_column
Revises: 
Create Date: 2026-04-05 09:15:00.000000

WARNING
-------
DO NOT run this migration automatically.
The `assigned_agent_id` column is already defined in the ORM model
(app/models/ticket.py). This file exists as a reference for manual
schema synchronisation if a production DB needs an explicit ALTER TABLE.
Apply only when intentionally migrating an older schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_assigned_agent_id_column'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add assigned_agent_id column to tickets table with foreign key constraint
    op.add_column(
        'tickets',
        sa.Column('assigned_agent_id', sa.Integer(), nullable=True)
    )
    # Create foreign key constraint referencing users.id
    op.create_foreign_key(
        'fk_tickets_assigned_agent_id_users',
        'tickets',
        'users',
        ['assigned_agent_id'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign key constraint first
    op.drop_constraint('fk_tickets_assigned_agent_id_users', 'tickets', type_='foreignkey')
    # Remove assigned_agent_id column from tickets table
    op.drop_column('tickets', 'assigned_agent_id')
