"""add_otp_columns_to_users

Revision ID: a1b2c3d4e5f6
Revises: 8564907ee88e
Create Date: 2026-04-08 10:22:00.000000

Ports the standalone migrations/add_password_reset_otp_columns.py script into
the Alembic chain so that `alembic upgrade head` produces a fully correct schema
on fresh installs.

Columns added to the 'users' table:
- reset_otp          VARCHAR(6)   nullable
- reset_otp_expires_at DATETIME  nullable
- reset_otp_attempts INTEGER      not null, default 0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8564907ee88e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add password-reset OTP columns to the users table."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('reset_otp', sa.String(length=6), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                'reset_otp_expires_at',
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                'reset_otp_attempts',
                sa.Integer(),
                nullable=False,
                server_default='0',
            )
        )


def downgrade() -> None:
    """Remove password-reset OTP columns from the users table."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('reset_otp_attempts')
        batch_op.drop_column('reset_otp_expires_at')
        batch_op.drop_column('reset_otp')
