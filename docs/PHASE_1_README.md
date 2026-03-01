# Phase 1: Foundation – Detailed Implementation Breakdown

This document provides a comprehensive, line-by-line explanation of every file implemented during Phase 1 (Tasks 1.1 through 1.7). The goal of Phase 1 was to establish the core backend infrastructure: environment configuration, database session management, database models (users, tickets, feedback), and the FastAPI application factory.

---

## 1. `app/core/config.py` (Task 1.1 — Core Configuration)
**Purpose:** Serves as the single source of truth for all application settings by loading from environment variables or providing defaults.

### Detailed Breakdown:
- **`from functools import lru_cache`**: Imports `lru_cache` to cache our settings after the first load, preventing disk reads for `.env` files on every request.
- **`from pydantic_settings import BaseSettings, SettingsConfigDict`**: Imports Pydantic's settings management tools. `BaseSettings` automatically reads from env vars.
- **`from pydantic import field_validator`**: Imports the validator decorator to enforce custom rules on our configuration values.
- **`class Settings(BaseSettings):`**: Defines our configuration schema.
- **`model_config = SettingsConfigDict(env_file=".env", ...)`**: Tells Pydantic to look for a `.env` file for these variables, ignore extra variables, and be case-sensitive.
- **`APP_NAME: str = "Automated Customer Support Resolution System"`**: Default constant for the application's name.
- **`ENV: str = "development"`**: Tracks the environment (development, staging, production). Defaults to development.
- **`SECRET_KEY: str` / `DATABASE_URL: str`**: Fields without defaults. Because they have no defaults, Pydantic *requires* them to be provided in the environment or `.env` file, failing fast on startup if missing.
- **`CONFIDENCE_THRESHOLD_AUTO_RESOLVE: float = 0.75`**: The critical threshold (75% confidence) needed for the AI engine to auto-resolve a ticket instead of escalating it.
- **`@field_validator("CONFIDENCE_THRESHOLD_AUTO_RESOLVE")`**: A custom validation method that ensures the threshold number stays between `0.0` and `1.0`. `raise ValueError` is used if someone misconfigures it.
- **`@lru_cache` \\ `def get_settings() -> Settings:`**: A factory function wrapped in a cache decorator. It instantiates the `Settings` class only once.
- **`settings = get_settings()`**: A globally available configuration object for the rest of the application to import securely.

---

## 2. `app/db/session.py` (Task 1.2 — Database Management & Task 1.6 — Init DB)
**Purpose:** Configures the SQLAlchemy engine to talk to the database, sets up how sessions are created, and sets the declarative base.

### Detailed Breakdown:
- **`from collections.abc import Generator`**: Type hinting for the dependency function `get_db`.
- **`from sqlalchemy import create_engine`**: Imports the SQLAlchemy engine factory (which handles connection pooling).
- **`from sqlalchemy.orm import Session, declarative_base, sessionmaker`**: Imports ORM tools. `Session` represents the DB workspace, `declarative_base` is the parent class for all models, and `sessionmaker` is the factory.
- **`from app.core.config import settings`**: Imports the validated `settings` object to get the `DATABASE_URL`.
- **`_connect_args = {"check_same_thread": False} if "sqlite" ...`**: SQLite specifically prevents connection sharing across threads by default. This line disables that check *only* if SQLite is being used, making it compatible with async FastAPI.
- **`engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args, echo=settings.DEBUG)`**: Creates the actual engine pool using the settings. `echo=True` (when DEBUG is on) prints all raw SQL queries to the terminal.
- **`SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`**: Creates a factory for database sessions. `autocommit=False` ensures transactions only commit when we explicitly say `.commit()`. `autoflush=False` gives us more control over when data is flushed to the DB.
- **`Base = declarative_base()`**: Creates the parent class. Every database table class we make will inherit from this so SQLAlchemy knows it maps to a table.
- **`def get_db() -> Generator[Session, None, None]:`**: Our FastAPI Dependency.
- **`db = SessionLocal() \ yield db \ finally: db.close()`**: Follows the yield pattern. It opens a database session, hands it to a FastAPI route (`yield`), and guarantees it closes (`finally:`) when the route finishes, preventing connection leaks.
- **`def init_db() -> None:`**: Fulfills Task 1.6 table migrations. 
- **`from app.models import feedback, ticket, user`**: These imports happen *inside* `init_db` to avoid circular imports. Importing them registers them with `Base.metadata`.
- **`Base.metadata.create_all(bind=engine)`**: Inspects all registered models and executes `CREATE TABLE IF NOT EXISTS` commands against the database.

---

## 3. `app/models/user.py` (Task 1.3 — User Model)
**Purpose:** Defines the `users` table layout, handling authentication limits and role definitions.

### Detailed Breakdown:
- **`from sqlalchemy import Column, Integer, String`**: Imports the SQLite/SQLAlchemy column datatypes.
- **`from app.db.session import Base`**: Imports the `Base` class so this model connects to our database metadata.
- **`class User(Base):`**: Defines the user ORM model.
- **`__tablename__ = "users"`**: Strictly defines the name of the table in the database.
- **`def __init__(self, **kwargs):`**: Constructor override. If `role` is not explicitly passed during user creation, it forcefully sets `kwargs['role'] = 'user'`, ensuring a safe default role fallback.
- **`id = Column(Integer, primary_key=True, index=True, ...)`**: Creates the standard auto-incrementing integer Primary Key. `index=True` makes searching by ID extremely fast.
- **`email = Column(String, unique=True, index=True, nullable=False, ...)`**: Uses the email as a login identifier. `unique=True` ensures no two users can share an email.
- **`hashed_password = Column(String, nullable=False, ...)`**: Stores the securely hashed version of the user's password (we never store plain text). `nullable=False` means a user cannot exist without credentials.
- **`role = Column(String, default="user", nullable=False, ...)`**: Defines authorization access control. Contains values like `user`, `agent`, or `admin`.

---

## 4. `app/models/ticket.py` (Task 1.4 — Ticket Model)
**Purpose:** Represents an incoming customer support query and its AI analysis lifecycle.

### Detailed Breakdown:
- **`class Ticket(Base):` \ `__tablename__ = "tickets"`**: Inherits from Base and names the table.
- **`def __init__(self, **kwargs):`**: Constructor override that guarantees `status` defaults to `'open'` upon creation.
- **`message = Column(String, nullable=False, ...)`**: The raw text content sent by the human customer.
- **`intent = Column(String, nullable=True, ...)`**: The string category that the AI model determines (e.g., `'refund_request'`) after analyzing the message.
- **`confidence = Column(Float, nullable=True, ...)`**: The numeric certainty (0.00 to 1.00) outputted by the AI model corresponding to the predicted intent.
- **`status = Column(String, default="open", nullable=False, ...)`**: The lifecycle state of the ticket: `open`, `auto_resolved`, `escalated`, or `closed`.
- **`created_at = Column(DateTime, default=datetime.utcnow, nullable=False, ...)`**: Tracks exactly when the user submitted the query. Uses `datetime.utcnow` as a function reference so it computes the current time at the moment of insertion.

---

## 5. `app/models/feedback.py` (Task 1.5 — Feedback Model)
**Purpose:** Maps post-resolution surveys back to tickets, measuring system success rates.

### Detailed Breakdown:
- **`from sqlalchemy import ForeignKey` / `from sqlalchemy.orm import relationship`**: Imports relational tools to link Feedback directly to Tickets.
- **`class Feedback(Base):` \ `__tablename__ = "feedback"`**: Standard inheritance.
- **`def __repr__(self):`**: Returns a developer-friendly string format (like `<Feedback(id=1, rating=5)>`) for logging and debugging purposes.
- **`ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False, ...)`**: Creates a strict database constraint. Feedback *must* belong to an existing ticket, linking to `tickets.id`.
- **`rating = Column(Integer, nullable=False, ...)`**: The numeric star-rating (e.g. 1 to 5) provided by the user.
- **`resolved = Column(Boolean, nullable=False, ...)`**: A boolean flag indicating whether the user actually felt their issue was fixed.
- **`ticket = relationship("Ticket", backref="feedback")`**: An ORM-level link. This allows us to do things like `my_feedback.ticket.message` or `my_ticket.feedback[0].rating` easily in Python without writing manual SQL JOINs.

---

## 6. `app/main.py` (Task 1.7 — Main Application Entry Point)
**Purpose:** Wires everything together so FastAPI can host the routers and interact with the database safely.

### Detailed Breakdown:
- **`from contextlib import asynccontextmanager`**: Imports the modern Python async context manager tool for handling app lifetimes.
- **`from app.core.config import settings`**: Imports environment configuration to perform logic gating (like hiding demo routes).
- **`from app.db.session import engine, init_db`**: Directly pulls the database utilities to use during startup/shutdown.
- **`@asynccontextmanager` \\ `async def lifespan(app: FastAPI) -> AsyncIterator[None]:`**: Replaces the deprecated `@app.on_event` decorators. 
- **`init_db()`**: Triggers before yielding, meaning the database and tables are created right as the server spins up.
- **`yield`**: Hands control over to the running FastAPI application to start accepting web requests.
- **`engine.dispose()`**: Executes when the server is stopped (CTRL+C), cleaning up all open database connections forcefully.
- **`def create_app() -> FastAPI:`**: Uses the Factory Design Pattern. By wrapping the app initialization in a function, we cleanly separate instances. This is heavily utilized in `tests/test_main.py` so every test gets a brand new, isolated app instance.
- **`app = FastAPI(title=..., lifespan=lifespan)`**: Bootstraps the app, mapping the context manager we wrote into the FastAPI system.
- **`app.add_middleware(CORSMiddleware, ...)`**: Allows our backend to accept cross-origin web requests from frontend interfaces running on different ports or domains.
- **`if settings.ENV != "production":` \\ `app.include_router(demo.router, tags=["Demo"])`**: Registers the `/demo/*` router to the app *only* if the server is not in full production mode, maximizing security.
- **`@app.get("/health", tags=["Health"])` \\ `def health_check() -> dict:`**: Placed inside the factory function. Returns strictly `{"status": "ok", "service": "automated-customer-support"}`. Very important for Docker containers or load balancers testing if the server is healthy.
- **`app = create_app()`**: The final line. This creates the global module-level application instance that `uvicorn` looks for when we run `uvicorn app.main:app`.
