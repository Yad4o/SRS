#!/usr/bin/env python3
"""
Database Demo Script

This script demonstrates the database structure and functionality of the
Automated Customer Support Resolution System.

Usage:
    python demo_db.py

What it shows:
- Database connection and table creation
- Table schemas and structure
- Sample data insertion
- Basic queries and relationships
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.session import engine, SessionLocal, init_db
from app.models.user import User
from app.models.ticket import Ticket
from app.models.feedback import Feedback
from sqlalchemy import text, inspect, func


def show_database_info():
    """Display basic database information."""
    print("=" * 60)
    print("🗄️  DATABASE DEMO - Automated Customer Support System")
    print("=" * 60)
    
    print(f"📍 Database URL: {engine.url.render_as_string(hide_password=True)}")
    print(f"🔧 Engine Driver: {engine.url.drivername}")
    print(f"📊 Database Name: {engine.url.database or 'N/A'}")
    print()


def show_tables():
    """Show all tables in the database."""
    print("📋 AVAILABLE TABLES:")
    print("-" * 30)
    
    # Initialize database (creates tables if they don't exist)
    init_db()
    
    # Get table names
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    for i, table in enumerate(tables, 1):
        print(f"{i}. {table}")
    
    print(f"\n✅ Total tables: {len(tables)}")
    print()


def show_table_schemas():
    """Show detailed schema for each table."""
    print("🏗️  TABLE SCHEMAS:")
    print("-" * 30)
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    for table_name in tables:
        print(f"\n📊 Table: {table_name}")
        print("─" * 40)
        
        columns = inspector.get_columns(table_name)
        for col in columns:
            nullable = "NULL" if col["nullable"] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col['default'] else ""
            print(f"  • {col['name']}: {col['type']} ({nullable}){default}")
        
        # Show foreign keys if any
        foreign_keys = inspector.get_foreign_keys(table_name)
        if foreign_keys:
            print("\n  🔗 Foreign Keys:")
            for fk in foreign_keys:
                print(f"    • {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}")
        
        print()


def create_sample_data():
    """Create sample data to demonstrate the system."""
    print("🎭 CREATING SAMPLE DATA:")
    print("-" * 30)
    
    session = SessionLocal()
    
    try:
        # Check if data already exists
        existing_users = session.query(User).count()
        if existing_users > 0:
            print("ℹ️  Sample data already exists. Skipping creation.")
            return
        
        # Create sample users
        users = [
            User(email="admin@example.com", hashed_password="hashed_admin_pass", role="admin"),
            User(email="agent@example.com", hashed_password="hashed_agent_pass", role="agent"),
            User(email="customer@example.com", hashed_password="hashed_customer_pass", role="user"),
        ]
        
        for user in users:
            session.add(user)
        
        session.commit()
        print("✅ Created 3 sample users")
        
        # Create sample tickets
        tickets = [
            Ticket(
                message="I can't log into my account. The password reset isn't working.",
                intent="login_issue",
                confidence=0.92,
                status="open"
            ),
            Ticket(
                message="I was charged twice for my subscription this month.",
                intent="payment_issue", 
                confidence=0.87,
                status="escalated"
            ),
            Ticket(
                message="How do I cancel my subscription?",
                intent="account_management",
                confidence=0.95,
                status="auto_resolved"
            ),
        ]
        
        for ticket in tickets:
            session.add(ticket)
        
        session.commit()
        print("✅ Created 3 sample tickets")
        
        # Get the actual ticket IDs from the created tickets
        created_tickets = session.query(Ticket).all()
        ticket_ids = [ticket.id for ticket in created_tickets]
        
        # Create sample feedback using actual ticket IDs
        feedback = [
            Feedback(ticket_id=ticket_ids[0], rating=5, resolved=True),
            Feedback(ticket_id=ticket_ids[1], rating=3, resolved=False),
            Feedback(ticket_id=ticket_ids[2], rating=4, resolved=True),
        ]
        
        for fb in feedback:
            session.add(fb)
        
        session.commit()
        print("✅ Created 3 sample feedback entries")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        session.rollback()
    finally:
        session.close()
    
    print()


def show_sample_data():
    """Display the sample data."""
    print("📊 SAMPLE DATA PREVIEW:")
    print("-" * 30)
    
    session = SessionLocal()
    
    try:
        # Show users
        print("\n👥 Users:")
        users = session.query(User).all()
        for user in users:
            print(f"  • ID: {user.id}, Email: {user.email}, Role: {user.role}")
        
        # Show tickets
        print("\n🎫 Tickets:")
        tickets = session.query(Ticket).all()
        for ticket in tickets:
            print(f"  • ID: {ticket.id}, Status: {ticket.status}, Intent: {ticket.intent}")
            print(f"    Message: {ticket.message[:50]}...")
        
        # Show feedback with relationships
        print("\n⭐ Feedback:")
        feedback_list = session.query(Feedback).all()
        for fb in feedback_list:
            print(f"  • Ticket ID: {fb.ticket_id}, Rating: {fb.rating}, Resolved: {fb.resolved}")
        
    except Exception as e:
        print(f"❌ Error displaying data: {e}")
    finally:
        session.close()
    
    print()


def show_relationships():
    """Demonstrate table relationships."""
    print("🔗 TABLE RELATIONSHIPS DEMO:")
    print("-" * 30)
    
    session = SessionLocal()
    
    try:
        # Show feedback with associated ticket information
        print("\n📊 Feedback with Ticket Details:")
        feedback_with_tickets = session.query(
            Feedback.id, 
            Feedback.rating, 
            Feedback.resolved,
            Ticket.message,
            Ticket.status,
            Ticket.intent
        ).join(Ticket).all()
        
        for fb_id, rating, resolved, message, status, intent in feedback_with_tickets:
            print(f"  • Feedback #{fb_id}: Rating {rating}/5, Resolved: {resolved}")
            print(f"    📝 Ticket: {message[:40]}... (Status: {status}, Intent: {intent})")
        
    except Exception as e:
        print(f"❌ Error showing relationships: {e}")
    finally:
        session.close()
    
    print()


def run_queries():
    """Demonstrate some useful queries."""
    print("🔍 USEFUL QUERY EXAMPLES:")
    print("-" * 30)
    
    session = SessionLocal()
    
    try:
        # Query 1: Count by status
        print("\n📈 Tickets by Status:")
        status_counts = session.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
        for status, count in status_counts:
            print(f"  • {status}: {count} tickets")
        
        # Query 2: Average feedback rating
        print("\n⭐ Average Feedback Rating:")
        avg_rating_result = session.query(func.avg(Feedback.rating)).scalar()
        if avg_rating_result:
            print(f"  • Average: {avg_rating_result:.2f}/5")
        else:
            print("  • No feedback data available")
        
        # Query 3: High confidence tickets
        print("\n🎯 High Confidence Tickets (>0.9):")
        high_conf = session.query(Ticket).filter(Ticket.confidence > 0.9).all()
        for ticket in high_conf:
            print(f"  • ID {ticket.id}: {ticket.confidence:.2f} confidence - {ticket.intent}")
        
    except Exception as e:
        print(f"❌ Error running queries: {e}")
    finally:
        session.close()
    
    print()


def main():
    """Run the complete demo."""
    try:
        show_database_info()
        show_tables()
        show_table_schemas()
        create_sample_data()
        show_sample_data()
        show_relationships()
        run_queries()
        
        print("=" * 60)
        print("🎉 DATABASE DEMO COMPLETE!")
        print("=" * 60)
        print("\n💡 Next steps:")
        print("  • Run the FastAPI app: uvicorn app.main:app --reload")
        print("  • Visit http://localhost:8000/docs for API documentation")
        print("  • Check /health endpoint for service status")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
