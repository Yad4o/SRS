"""hash_otp_column

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6g7
Create Date: 2026-06-28 00:00:00.000000

Widens the reset_otp column from VARCHAR(6) to VARCHAR(64) so it can
store a SHA-256 hex digest instead of the raw plaintext OTP.

Why:
  Storing a plain 6-digit OTP in the database means a read-access DB
  compromise (e.g. a SQL injection or a stolen backup) instantly exposes
  all pending password-reset tokens.  Hashing the OTP with SHA-256 before
  persistence provides the same protection as hashed passwords — the hash
  is useless to an attacker without the original value.

Migration strategy:
  - Any in-flight reset_otp values (6-char plain digits) become invalid
    after this migration because the verification code now compares
    against hashes.  This is acceptable: OTPs have a 10-minute TTL and
    the UX path is simply "request a new OTP".
  - The column is NULLed out during upgrade to eliminate stale plaintext
    rows (defence-in-depth).

Reversibility:
  downgrade() shrinks the column back to VARCHAR(6) and NULLs the column
  again, since we cannot recover plaintext from a hash.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen reset_otp to hold a SHA-256 hex digest and clear stale plain OTPs."""
    # 1. Clear all existing plaintext OTP values before the schema change so
    #    no plaintext survives in the column after this migration runs.
    op.execute("UPDATE users SET reset_otp = NULL, reset_otp_attempts = 0")

    # 2. Widen the column.  batch_alter_table is required for SQLite support
    #    (SQLite does not support ALTER COLUMN directly).
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "reset_otp",
            existing_type=sa.String(length=6),
            type_=sa.String(length=64),
            existing_nullable=True,
            nullable=True,
        )


def downgrade() -> None:
    """Shrink reset_otp back to VARCHAR(6) and clear hashed values."""
    # Hashes cannot be reversed to plaintext, so clear the column first.
    op.execute("UPDATE users SET reset_otp = NULL, reset_otp_attempts = 0")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "reset_otp",
            existing_type=sa.String(length=64),
            type_=sa.String(length=6),
            existing_nullable=True,
            nullable=True,
        )
