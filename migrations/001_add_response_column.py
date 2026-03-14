"""
Database migration to add response column to tickets table.

Migration: 001_add_response_column.py
Purpose: Add nullable String "response" column to tickets table
Author: Automated migration system
"""

import sqlite3
import sys
from pathlib import Path


def add_response_column(db_path: str) -> bool:
    """
    Add response column to tickets table.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        bool: True if migration successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(tickets)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'response' in columns:
            print("Response column already exists in tickets table")
            return True
        
        # Add the response column
        cursor.execute("""
            ALTER TABLE tickets 
            ADD COLUMN response TEXT
        """)
        
        conn.commit()
        print("Successfully added response column to tickets table")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def remove_response_column(db_path: str) -> bool:
    """
    Remove response column from tickets table (rollback).
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        bool: True if rollback successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate table
        cursor.execute("""
            CREATE TABLE tickets_new (
                id INTEGER PRIMARY KEY,
                message TEXT NOT NULL,
                intent TEXT,
                confidence REAL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO tickets_new (id, message, intent, confidence, status, created_at)
            SELECT id, message, intent, confidence, status, created_at FROM tickets
        """)
        
        # Drop old table and rename new table
        cursor.execute("DROP TABLE tickets")
        cursor.execute("ALTER TABLE tickets_new RENAME TO tickets")
        
        conn.commit()
        print("Successfully removed response column from tickets table")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default to support.db in project root
        project_root = Path(__file__).parent.parent
        db_path = project_root / "support.db"
    
    db_path = str(db_path)
    
    if len(sys.argv) > 2 and sys.argv[2] == "rollback":
        success = remove_response_column(db_path)
    else:
        success = add_response_column(db_path)
    
    if success:
        print("Migration completed successfully")
        sys.exit(0)
    else:
        print("Migration failed")
        sys.exit(1)
