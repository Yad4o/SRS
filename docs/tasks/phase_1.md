# Phase 1: Foundation

**Execution order:** Must complete before Phase 2, 3, or 4.

---

## Task 1.1 — Core Configuration

| Field | Value |
|-------|-------|
| **Execution order** | 1 (first task in entire project) |
| **File to implement** | `app/core/config.py` |
| **Cannot implement before** | None — this is the root dependency |
| **Owner** | Om |
| **Blocks** | All other tasks (session, models, main, etc.) |

### Description

Implement centralized configuration management. This file is the **single source of truth** for all application settings. No other module in the project should be imported or executed before this exists, as `session.py`, `security.py`, and services will depend on it.

**Deliverables:**
- Create a `Settings` class using `pydantic-settings` (or Pydantic BaseSettings)
- Load environment variables from `.env` (development) and system env (production)
- Define: `SECRET_KEY`, `DATABASE_URL`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`, `DEBUG`, `ENV`
- Add `CONFIDENCE_THRESHOLD_AUTO_RESOLVE` (default 0.75) for the decision engine
- Provide `get_settings()` function with `@lru_cache` so config is loaded once and cached
- Ensure all secrets come from environment variables; never hardcode credentials
- Reference: Technical Spec § 12 (Configuration Management)

---

## Task 1.2 — Database Session Management

| Field | Value |
|-------|-------|
| **Execution order** | 2 |
| **File to implement** | `app/db/session.py` |
| **Cannot implement before** | Task 1.1 (`app/core/config.py`) — requires `settings.DATABASE_URL` |
| **Owner** | Om |
| **Blocks** | Tasks 1.3, 1.4, 1.5, 1.6, 1.7 (all models and main) |

### Description

Implement the database engine and session lifecycle. This module provides the SQLAlchemy engine, session factory, and `Base` class that all ORM models inherit from. It also exposes `get_db()` as a FastAPI dependency for per-request database sessions.

**Deliverables:**
- Create SQLAlchemy engine using `settings.DATABASE_URL`
- Use `check_same_thread=False` only for SQLite; omit for PostgreSQL
- Create `SessionLocal` sessionmaker with `autocommit=False`, `autoflush=False`
- Define `Base = declarative_base()` for ORM model inheritance
- Implement `get_db()` generator: yield session, close in `finally`
- Implement `init_db()` to create all tables (call `Base.metadata.create_all`)
- Reference: Technical Spec § 5.3 (Data Layer)

---

## Task 1.3 — User Model

| Field | Value |
|-------|-------|
| **Execution order** | 3 |
| **File to implement** | `app/models/user.py` |
| **Cannot implement before** | Task 1.2 (`app/db/session.py`) — requires `Base` |
| **Owner** | Prajwal |
| **Blocks** | Task 2.2 (user schemas), Task 2.3 (auth API) |

### Description

Define the User ORM model for authentication and authorization. This table stores all users (customers, agents, admins) and their credentials.

**Deliverables:**
- Inherit from `Base`; set `__tablename__ = "users"`
- Columns: `id` (Integer, PK, index), `email` (String, unique, nullable=False), `hashed_password` (String, nullable=False), `role` (String, default="user", nullable=False)
- Role values: `user`, `agent`, `admin`
- Do NOT hash passwords in this file; hashing is done in `security.py`
- Reference: Technical Spec § 7.1 (User)

---

## Task 1.4 — Ticket Model

| Field | Value |
|-------|-------|
| **Execution order** | 4 |
| **File to implement** | `app/models/ticket.py` |
| **Cannot implement before** | Task 1.2 (`app/db/session.py`) — requires `Base` |
| **Owner** | Prajwal |
| **Blocks** | Task 2.4 (ticket schemas), Task 2.5 (tickets API), Phase 3 (AI flow) |

### Description

Define the Ticket ORM model. Each ticket represents a single customer support request and stores the message, AI classification results, and lifecycle status.

**Deliverables:**
- Inherit from `Base`; set `__tablename__ = "tickets"`
- Columns: `id`, `message` (required), `intent`, `confidence` (Float), `status`, `created_at`
- Status values: `open`, `auto_resolved`, `escalated`, `closed`
- Reference: Technical Spec § 7.2 (Ticket)

---

## Task 1.5 — Feedback Model

| Field | Value |
|-------|-------|
| **Execution order** | 5 |
| **File to implement** | `app/models/feedback.py` |
| **Cannot implement before** | Task 1.2 (`app/db/session.py`) — requires `Base` |
| **Owner** | Prajwal |
| **Blocks** | Task 4.1 (feedback API) |

### Description

Define the Feedback ORM model. Feedback is collected after a ticket is resolved to measure quality and enable future AI improvement.

**Deliverables:**
- Inherit from `Base`; set `__tablename__ = "feedback"`
- Columns: `id`, `ticket_id` (FK to tickets), `rating`, `resolved` (Boolean), `created_at`
- Reference: Technical Spec § 7.3 (Feedback)

---

## Task 1.6 — Table Migrations / init_db

| Field | Value |
|-------|-------|
| **Execution order** | 6 |
| **File to implement** | `app/db/session.py` (add to `init_db`) or separate migration script |
| **Cannot implement before** | Tasks 1.2, 1.3, 1.4, 1.5 — all models must exist |
| **Owner** | Prajwal |
| **Blocks** | Main app startup (Task 1.7) |

### Description

Ensure all tables are created when the application starts. If `init_db()` in `session.py` imports all models and calls `Base.metadata.create_all(bind=engine)`, this is satisfied. Otherwise, create a migration or startup script.

**Deliverables:**
- Tables `users`, `tickets`, `feedback` must exist after running `init_db()`
- Idempotent: safe to call multiple times
- Can be triggered from `main.py` startup event

---

## Task 1.7 — Main Application Entry Point

| Field | Value |
|-------|-------|
| **Execution order** | 7 |
| **File to implement** | `app/main.py` |
| **Cannot implement before** | Tasks 1.1, 1.2, 1.6 — config, session, and tables must exist |
| **Owner** | Om |
| **Blocks** | Phase 2 API registration |

### Description

Implement the FastAPI application factory and wire startup/shutdown logic. This is the entry point for running the server (e.g., via `uvicorn app.main:app`).

**Deliverables:**
- Create FastAPI app with title, description, version
- Add CORS middleware (configure for development; restrict in production)
- Call `init_db()` on startup
- Call `engine.dispose()` on shutdown
- Health check endpoint: `GET /health` returning `{"status": "ok", "service": "automated-customer-support"}`
- Do NOT put business logic, DB queries, or AI logic here
- Reference: Technical Spec § 4 (Architecture)

---

## Phase 1 Dependency Graph

```
1.1 config.py
    |
    v
1.2 session.py
    |
    +---> 1.3 user.py
    +---> 1.4 ticket.py
    +---> 1.5 feedback.py
    |
    v
1.6 init_db (tables)
    |
    v
1.7 main.py
```
