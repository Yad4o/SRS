"""
Migration: Add is_archived column to tickets table

This migration adds the 'is_archived' boolean column to the existing tickets
table. The column is used by the cleanup worker to mark old tickets as archived
without changing their original status, preserving metrics and similarity-search
accuracy.

Run this migration for existing installations that don't have the is_archived column.
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


def add_is_archived_column() -> bool:
    """
    Add is_archived column to tickets table if it doesn't exist.

    Uses the configured database URL from settings.DATABASE_URL.

    Returns:
        bool: True if migration was successful, False otherwise
    """
    try:
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as conn:
            # Check if column already exists using dialect-agnostic introspection
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns("tickets")]

            if "is_archived" in columns:
                logger.info("is_archived column already exists in tickets table")
                return True

            # Use dialect-aware default for BOOLEAN column
            dialect_name = engine.dialect.name
            default_value = "DEFAULT 0" if dialect_name == "sqlite" else "DEFAULT FALSE"
            
            conn.execute(
                text(f"ALTER TABLE tickets ADD COLUMN is_archived BOOLEAN NOT NULL {default_value}")
            )
            conn.commit()

            logger.info("Successfully added is_archived column to tickets table")
            return True

    except Exception as e:
        logger.error("Failed to add is_archived column: %s", e)
        return False


def run_migration() -> None:
    """Run the migration and report results."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    success = add_is_archived_column()
    if success:
        print("Migration completed successfully")
    else:
        print("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
