"""
Migration: Add response column to tickets table

This migration adds the 'response' column to the existing tickets table
to support AI-generated responses for auto-resolved tickets.

Run this migration for existing installations that don't have the response column.
"""

import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from app.core.config import settings

logger = logging.getLogger(__name__)


def add_response_column() -> bool:
    """
    Add response column to tickets table if it doesn't exist.
    
    Uses the configured database URL from settings.DATABASE_URL.
    
    Returns:
        bool: True if migration was successful, False otherwise
    """
    try:
        # Create engine using configured database URL
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if response column already exists
            result = conn.execute(text("PRAGMA table_info(tickets)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'response' in columns:
                logger.info("Response column already exists in tickets table")
                return True
            
            # Add response column
            conn.execute(text("ALTER TABLE tickets ADD COLUMN response VARCHAR"))
            conn.commit()
            
            logger.info("Successfully added response column to tickets table")
            return True
        
    except Exception as e:
        logger.error(f"Failed to add response column: {e}")
        return False


def run_migration() -> None:
    """Run the migration and report results."""
    print(f"Running migration on database: {settings.DATABASE_URL}")
    
    if add_response_column():
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        raise Exception("Migration failed")


if __name__ == "__main__":
    run_migration()
