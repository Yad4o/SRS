# 🗄️ Database Demo & Documentation

This folder contains demonstration scripts and documentation for exploring the **Automated Customer Support Resolution System** database structure and functionality.

## 📁 Files Overview

### 🎭 `demo_db.py`
**Comprehensive Database Demo Script**

A complete demonstration of the database system including:
- Database connection and table creation
- Detailed table schemas and structure
- Sample data insertion with realistic examples
- Table relationships and foreign key constraints
- Useful query examples and analytics

**Usage:**
```bash
python demo/demo_db.py
```

**What it shows:**
- ✅ Database information (URL, driver, name)
- ✅ All available tables (users, tickets, feedback)
- ✅ Detailed table schemas with column types and constraints
- ✅ Sample data creation (3 users, 3 tickets, 3 feedback entries)
- ✅ Table relationships and joins
- ✅ Useful business queries (status counts, ratings, confidence scores)

---

### ⚡ `quick_view.py`
**Quick Database Overview**

A lightweight script for quickly viewing database contents without the full demo.

**Usage:**
```bash
python demo/quick_view.py
```

**What it shows:**
- ✅ List of all tables
- ✅ Record counts per table
- ✅ Sample data (first 3 records from each table)
- ✅ Column names (data types available in full demo)

---

## 🚀 Getting Started

### Prerequisites
- ✅ Python 3.11+ installed
- ✅ Virtual environment activated
- ✅ Project dependencies installed (`pip install -r requirements.txt`)

### Quick Start

1. **Activate Virtual Environment:**
   ```bash
   # Windows
   .venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

2. **Run Full Demo:**
   ```bash
   python demo/demo_db.py
   ```

3. **Run Quick View:**
   ```bash
   python demo/quick_view.py
   ```

---

## 📊 Database Structure

### 🗄️ Tables Overview

| Table | Purpose | Key Columns | Relationships |
|-------|---------|-------------|---------------|
| **users** | User authentication & roles | id, email, hashed_password, role | None |
| **tickets** | Customer support requests | id, message, intent, confidence, status | Has feedback |
| **feedback** | User feedback on resolutions | id, ticket_id, rating, resolved | Belongs to ticket |

### 🔗 Relationships

```text
users ← (implicit) → tickets ← feedback
```

- **feedback.ticket_id** → **tickets.id** (Foreign Key)
- Each ticket can have multiple feedback entries
- Users create tickets, tickets receive feedback

---

## 🎯 Sample Data

The demo creates realistic sample data:

### 👥 Users
- **admin@example.com** - System administrator
- **agent@example.com** - Support agent  
- **customer@example.com** - Regular customer

### 🎫 Tickets
- **Login Issue** - "I can't log into my account..." (confidence: 0.92)
- **Payment Issue** - "I was charged twice..." (confidence: 0.87)
- **Account Management** - "How do I cancel my subscription?" (confidence: 0.95)

### ⭐ Feedback
- **Rating 5/5** - Issue resolved successfully
- **Rating 3/5** - Issue not fully resolved
- **Rating 4/5** - Issue resolved with minor issues

---

## 🔍 Database Exploration

### Method 1: Demo Scripts (Recommended)
```bash
# Full comprehensive demo
python demo/demo_db.py

# Quick overview
python demo/quick_view.py
```

### Method 2: Direct SQLite Access
```bash
# Open database directly
sqlite3 support.db

# SQLite commands
.tables                    # Show all tables
.schema users              # Show table structure
SELECT * FROM users;       # Show data
```

### Method 3: FastAPI Application
```bash
# Start the API server
uvicorn app.main:app --reload

# Visit endpoints
http://localhost:8000/health     # Health check
http://localhost:8000/docs       # API documentation
```

---

## 📈 Business Intelligence Examples

The demo includes useful queries for business insights:

### 📊 Ticket Analytics
- **Tickets by Status**: Count of open, auto_resolved, escalated, closed
- **High Confidence Tickets**: Tickets with AI confidence > 0.9
- **Intent Distribution**: Most common customer issues

### ⭐ Feedback Analysis  
- **Average Rating**: Overall customer satisfaction
- **Resolution Rate**: Percentage of issues actually resolved
- **Rating by Intent**: Satisfaction per issue type

### 🔍 Relationship Queries
- **Feedback with Ticket Details**: Join feedback with ticket information
- **User Activity**: Tickets and feedback per user type

---

## 🛠️ Technical Details

### Database Configuration
- **Type**: SQLite (development)
- **File**: `support.db` (project root)
- **ORM**: SQLAlchemy
- **Migration**: Automatic via `init_db()`

### Key Components
- **Engine**: `app/db/session.py`
- **Models**: `app/models/` (user.py, ticket.py, feedback.py)
- **Initialization**: `init_db()` function
- **Testing**: Comprehensive test suite in `tests/`

### Connection Details
```python
from app.db.session import engine, SessionLocal

# Direct database access
session = SessionLocal()
users = session.query(User).all()
session.close()
```

---

## 🚨 Important Notes

### ⚠️ Security
- **No Real Passwords**: Demo uses placeholder hashed passwords
- **Development Data**: All data is fictional and for demonstration only
- **SQLite Only**: Demo uses SQLite; production may use PostgreSQL

### 🔄 Data Persistence
- **Sample Data**: Created once per database
- **Idempotent**: Running demo multiple times is safe
- **Clean State**: Delete `support.db` to reset completely

### 🐛 Troubleshooting

**Issue**: "Database locked" or "Permission denied"
```bash
# Solution: Close any database connections and retry
# Delete support.db file and run demo again
del support.db
python demo/demo_db.py
```

**Issue**: "Module not found"
```bash
# Solution: Ensure virtual environment is activated
.venv\Scripts\activate
python demo/demo_db.py
```

---

## 🎓 Learning Objectives

After running these demos, you'll understand:

✅ **Database Structure** - How tables are organized and related
✅ **ORM Usage** - How SQLAlchemy models work
✅ **Data Relationships** - Foreign keys and joins
✅ **AI Integration** - How intent classification is stored
✅ **Business Logic** - Ticket lifecycle and feedback system
✅ **Query Patterns** - Common database operations
✅ **Testing Approach** - How database functionality is tested

---

## 🚀 Next Steps

1. **Explore the API**: Start FastAPI and visit `/docs`
2. **Review Models**: Check `app/models/` for implementation details
3. **Run Tests**: Execute `pytest tests/` for comprehensive testing
4. **Extend Functionality**: Add new models or API endpoints
5. **Production Setup**: Configure PostgreSQL for production use

---

## 📞 Support

For questions or issues:
- 📖 Check the main project README
- 🧪 Run the test suite for verification
- 🔍 Review the SQLAlchemy documentation
- 💬 Contact the development team

---

**Happy Database Exploring! 🎉**
