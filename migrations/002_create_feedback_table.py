"""
Database migration to create feedback table.

Migration: 002_create_feedback_table.py
Purpose: Create feedback table with foreign key to tickets
Author: Automated migration system
"""

import sqlite3
import sys
from pathlib import Path


def create_feedback_table(db_path: str) -> bool:
    """
    Create feedback table with foreign key to tickets.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        bool: True if migration successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'")
        if cursor.fetchone():
            print("Feedback table already exists")
            return True
        
        # Create feedback table
        cursor.execute("""
            CREATE TABLE feedback (
                id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                resolved BOOLEAN NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets (id)
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX idx_feedback_ticket_id ON feedback(ticket_id)")
        
        conn.commit()
        print("Successfully created feedback table")
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


def drop_feedback_table(db_path: str) -> bool:
    """
    Drop feedback table (rollback).
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        bool: True if rollback successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Drop table
        cursor.execute("DROP TABLE IF EXISTS feedback")
        
        conn.commit()
        print("Successfully dropped feedback table")
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
        success = drop_feedback_table(db_path)
    else:
        success = create_feedback_table(db_path)
    
    if success:
        print("Migration completed successfully")
        sys.exit(0)
    else:
        print("Migration failed")
        sys.exit(1)
