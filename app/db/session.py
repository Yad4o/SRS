"""
app/db/session.py

Purpose:
--------
Database engine and session management for the application.

Owner:
------
Om (Backend / System)

Responsibilities:
-----------------
- Create SQLAlchemy engine (connection pool)
- Provide session factory (SessionLocal)
- Expose Base class for ORM models (User, Ticket, Feedback)
- Provide FastAPI dependency (get_db) for per-request DB sessions
- Provide init_db() to create tables on startup

Reference: docs/specification/TECHNICAL_SPEC.md § 5.3 Data Layer

DO NOT:
-------
- Define models here (use app/models/)
- Write business queries here (use repositories or services)
- Commit transactions in this file
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

# -------------------------------------------------
# Database Engine
# -------------------------------------------------

"""
Engine is the core interface to the database.
- Manages connection pooling
- Executes SQL via sessions

SQLite: check_same_thread=False required (SQLite default forbids shared connections)
PostgreSQL: Do NOT pass check_same_thread (not supported)
"""
_connect_args = (
    {"check_same_thread": False}
    if "sqlite" in settings.DATABASE_URL.lower()
    else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=settings.DEBUG,  # Log SQL in development only
)

# -------------------------------------------------
# Session Factory
# -------------------------------------------------

"""
SessionLocal creates a new database session per request.

- autocommit=False: You control when to commit (e.g., after successful ops)
- autoflush=False: Flush is explicit; avoids implicit writes before queries
"""
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)

# -------------------------------------------------
# Declarative Base
# -------------------------------------------------

"""
All ORM models must inherit from Base.

Usage in app/models/:
    from app.db.session import Base

    class User(Base):
        __tablename__ = "users"
        ...
"""
Base = declarative_base()

# -------------------------------------------------
# FastAPI Dependency
# -------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage in route handlers:
    -----------------------
        from fastapi import Depends
        from sqlalchemy.orm import Session

        @router.get("/tickets")
        def list_tickets(db: Session = Depends(get_db)):
            return db.query(Ticket).all()

    Lifecycle:
    ----------
    - Session created when request starts
    - Yielded to the route handler
    - Closed in `finally` when request ends (even on error)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------
# Table Initialization
# -------------------------------------------------


def init_db() -> None:
    """
    Create all tables defined in models that inherit from Base.

    Call this on application startup (e.g., in main.py on_event("startup")).
    Safe to call multiple times: creates only missing tables.
    """
    # Import models so they register with Base.metadata (side-effect imports)
    from app.models import feedback, ticket, user

    Base.metadata.create_all(bind=engine)
