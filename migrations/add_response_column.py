"""
Migration: Add response column to tickets table

This migration adds the 'response' column to the existing tickets table
to support AI-generated responses for auto-resolved tickets.

Run this migration for existing installations that don't have the response column.
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def add_response_column(db_path: str = "tickets.db") -> bool:
    """
    Add response column to tickets table if it doesn't exist.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        bool: True if migration was successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if response column already exists
        cursor.execute("PRAGMA table_info(tickets)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'response' in columns:
            logger.info("Response column already exists in tickets table")
            conn.close()
            return True
        
        # Add response column
        cursor.execute("ALTER TABLE tickets ADD COLUMN response VARCHAR")
        conn.commit()
        
        logger.info("Successfully added response column to tickets table")
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Failed to add response column: {e}")
        return False


def run_migration(db_path: str = "tickets.db") -> None:
    """Run the migration and report results."""
    print(f"Running migration on database: {db_path}")
    
    if add_response_column(db_path):
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
        raise Exception("Migration failed")


if __name__ == "__main__":
    import sys
    
    # Allow database path to be passed as argument
    db_path = sys.argv[1] if len(sys.argv) > 1 else "tickets.db"
    run_migration(db_path)
