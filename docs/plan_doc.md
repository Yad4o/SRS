Recommended implementation order
Phase 1: Foundation (implement first)
Core configuration (app/core/config.py)
Environment-based config
Centralized settings
No other module should depend on this before it exists
Database setup (app/db/session.py)
DB connection/session management
Depends on config
Data models (app/models/)
user.py – for auth
ticket.py – main entity
feedback.py – later, but schema should be designed now
Migrations to create tables
Main entry point (app/main.py)
FastAPI app initialization
Wiring and startup/shutdown hooks
Phase 2: Auth & basic ticket API
Security (app/core/security.py)
Password hashing (bcrypt)
JWT creation and validation
User schemas (app/schemas/user.py)
Validation for login/registration and responses
Auth API (app/api/auth.py)
Login
(Optional) registration
Ticket schemas (app/schemas/ticket.py)
Create/read ticket payloads and responses
Basic ticket API (app/api/tickets.py)
Create ticket
Get ticket(s)
No AI yet – tickets stay OPEN
Phase 3: AI pipeline
Intent classification (app/services/classifier.py)
Input: ticket message → output: intent + confidence
Similarity search (app/services/similarity.py)
Compare new ticket with resolved tickets
Response generation (app/services/resolver.py)
Generate/select reply text from intent and similar solutions
Decision engine (app/services/decision.py)
Confidence threshold (e.g. ≥0.75 → auto-resolve)
Pure logic, no DB/HTTP
Wire automation into ticket flow
After ticket creation: classifier → similarity → decision → resolver (if auto-resolve)
Update ticket status and store response
Phase 4: Feedback, admin, and polish
Feedback API (app/api/feedback.py)
Admin API (app/api/admin.py)
Error handling strategy (Section 11)
Tests (Section 14)
Summary: first to implement
Start with:
app/core/config.py
app/db/session.py
app/models/user.py, ticket.py, feedback.py
app/main.py
That gives you the config, DB, and core models needed for everything else. After that, security + auth, then basic ticket creation, then the AI pipeline.
If you tell me your current project layout and what you already have (e.g. FastAPI app, DB), I can suggest concrete next steps or file-level tasks.