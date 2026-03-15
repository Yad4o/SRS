"""
Migration: Add unique constraint on feedback.ticket_id

Enforces one-feedback-per-ticket at the database level by creating a unique
index on the ticket_id column of the feedback table.

Run this migration for existing installations that were created before this
constraint was introduced.
"""

import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from app.core.config import settings

logger = logging.getLogger(__name__)


def add_unique_constraint() -> bool:
    """
    Add a unique index on feedback.ticket_id if it doesn't already exist.

    Uses the configured database URL from settings.DATABASE_URL.

    Returns:
        bool: True if migration was successful, False otherwise
    """
    try:
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as conn:
            # Check whether the unique index already exists (SQLite-compatible)
            result = conn.execute(text("PRAGMA index_list(feedback)"))
            existing_indexes = [row[1] for row in result.fetchall()]

            if 'uq_feedback_ticket_id' in existing_indexes:
                logger.info("Unique constraint on feedback.ticket_id already exists")
                return True

            # Create the unique index
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_feedback_ticket_id "
                    "ON feedback (ticket_id)"
                )
            )
            conn.commit()

            logger.info(
                "Successfully added unique constraint on feedback.ticket_id"
            )
            return True

    except Exception as e:
        logger.error(f"Failed to add unique constraint on feedback.ticket_id: {e}")
        return False


def run_migration() -> None:
    """Run the migration and report results."""
    print(f"Running migration on database: {settings.DATABASE_URL}")

    if add_unique_constraint():
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        raise Exception("Migration failed")


if __name__ == "__main__":
    run_migration()
