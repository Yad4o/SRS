"""add_refresh_tokens_table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-28 00:00:00.000000

Adds the refresh_tokens table (Issue #4 — no refresh token / JWT
rotation). Stores only the HMAC-SHA256 hash of each refresh token, never
the raw value, mirroring the existing OTP-hashing pattern on users.reset_otp.

Reversibility:
  downgrade() drops the table outright — there is no data worth
  preserving on rollback (refresh tokens are short-lived, opaque
  credentials, not business data).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the refresh_tokens table."""
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop the refresh_tokens table."""
    op.drop_table("refresh_tokens")
