"""
Migration: Add password reset OTP columns to users table

This migration adds the following columns to the existing users table:
- reset_otp: 6-character string for storing password reset OTP
- reset_otp_expires_at: Timestamp for OTP expiration
- reset_otp_attempts: Integer counter for OTP verification attempts

NOTE: This file intentionally remains in migrations/ because the OTP columns
(reset_otp, reset_otp_expires_at, reset_otp_attempts) are present in the
User model but are NOT covered by any Alembic revision yet.  Fresh installs
created via `alembic upgrade head` will be missing these columns.

TODO: Port this into a new Alembic revision so that `alembic upgrade head`
      handles the full schema, then delete this file.
      See: alembic/versions/ for existing revisions.

Run this migration for existing installations that don't have the OTP columns.
"""

import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

logger = logging.getLogger(__name__)


def add_otp_columns() -> bool:
    """
    Add OTP-related columns to users table if they don't exist.

    Uses the configured database URL from settings.DATABASE_URL.

    Returns:
        bool: True if migration was successful, False otherwise
    """
    try:
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as conn:
            # Check if columns already exist using dialect-agnostic introspection
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns("users")]

            # Track if any changes were made
            changes_made = False

            # Add reset_otp column
            if "reset_otp" not in columns:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN reset_otp VARCHAR(6)")
                )
                changes_made = True
                logger.info("Added reset_otp column to users table")
            else:
                logger.info("reset_otp column already exists in users table")

            # Add reset_otp_expires_at column
            if "reset_otp_expires_at" not in columns:
                # Use dialect-appropriate datetime type
                dialect_name = engine.dialect.name
                if dialect_name == "sqlite":
                    datetime_type = "DATETIME"
                elif dialect_name == "postgresql":
                    datetime_type = "TIMESTAMP WITH TIME ZONE"
                else:
                    datetime_type = "TIMESTAMP"
                
                conn.execute(
                    text(f"ALTER TABLE users ADD COLUMN reset_otp_expires_at {datetime_type}")
                )
                changes_made = True
                logger.info("Added reset_otp_expires_at column to users table")
            else:
                logger.info("reset_otp_expires_at column already exists in users table")

            # Add reset_otp_attempts column
            if "reset_otp_attempts" not in columns:
                # Use dialect-aware default for INTEGER column
                dialect_name = engine.dialect.name
                default_value = "DEFAULT 0" if dialect_name == "sqlite" else "DEFAULT 0"
                
                conn.execute(
                    text(f"ALTER TABLE users ADD COLUMN reset_otp_attempts INTEGER NOT NULL {default_value}")
                )
                changes_made = True
                logger.info("Added reset_otp_attempts column to users table")
            else:
                logger.info("reset_otp_attempts column already exists in users table")

            if changes_made:
                conn.commit()
                logger.info("Successfully added OTP columns to users table")
            else:
                logger.info("All OTP columns already exist in users table")

            return True

    except Exception as e:
        logger.error("Failed to add OTP columns: %s", e)
        return False


def run_migration() -> None:
    """Run the migration and report results."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    success = add_otp_columns()
    if success:
        print("Migration completed successfully")
    else:
        print("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
