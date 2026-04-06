"""phase5_columns

Revision ID: 8564907ee88e
Revises: e31c076df125
Create Date: 2026-04-06 14:01:48.783565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8564907ee88e'
down_revision: Union[str, Sequence[str], None] = 'e31c076df125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sub_intent', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('response_source', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('quality_score', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('assigned_agent_id', sa.Integer(), nullable=True))
        
        # NOTE: FK constraints are no-ops on SQLite (batch mode). Always verify against PostgreSQL.
        batch_op.create_foreign_key('fk_tickets_assigned_agent_id', 'users', ['assigned_agent_id'], ['id'])
        batch_op.create_foreign_key('fk_tickets_user_id', 'users', ['user_id'], ['id'])
        
        # Added indexes for performance on frequently queried foreign keys
        batch_op.create_index('ix_tickets_user_id', ['user_id'])
        batch_op.create_index('ix_tickets_assigned_agent_id', ['assigned_agent_id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index('ix_tickets_assigned_agent_id')
        batch_op.drop_index('ix_tickets_user_id')
        batch_op.drop_constraint('fk_tickets_user_id', type_='foreignkey')
        batch_op.drop_constraint('fk_tickets_assigned_agent_id', type_='foreignkey')
        batch_op.drop_column('assigned_agent_id')
        batch_op.drop_column('user_id')
        batch_op.drop_column('quality_score')
        batch_op.drop_column('response_source')
        batch_op.drop_column('sub_intent')
