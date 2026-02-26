#!/usr/bin/env python3
"""
Quick Database Viewer

Simple script to quickly view database contents without the full demo.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.session import engine, SessionLocal, init_db
from sqlalchemy import text


def quick_view():
    """Quick view of database tables and contents."""
    print("🗄️  QUICK DATABASE VIEW")
    print("=" * 40)
    
    # Initialize database
    init_db()
    
    session = SessionLocal()
    
    try:
        # Show all tables
        print("\n📋 Tables:")
        result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result]
        for table in tables:
            print(f"  • {table}")
        
        # Show record counts
        print("\n📊 Record Counts:")
        # Validate table names to prevent SQL injection
        allowed_tables = {'users', 'tickets', 'feedback'}
        for table in tables:
            if table not in allowed_tables:
                print(f"  • {table}: [SKIPPED - Invalid table name]")
                continue
            result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            print(f"  • {table}: {count} records")
        
        # Show sample data from each table
        print("\n📝 Sample Data:")
        for table in tables:
            if table not in allowed_tables:
                print(f"\n🔸 {table.upper()}: [SKIPPED - Invalid table name]")
                continue
            print(f"\n🔸 {table.upper()} (first 3 records):")
            try:
                result = session.execute(text(f"SELECT * FROM {table} LIMIT 3"))
                rows = result.fetchall()
                
                # Get column names
                columns = result.keys()
                print(f"   Columns: {', '.join(columns)}")
                
                for i, row in enumerate(rows, 1):
                    print(f"   {i}. {dict(zip(columns, row))}")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    quick_view()
