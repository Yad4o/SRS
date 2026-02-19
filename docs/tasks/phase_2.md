# Phase 2: Auth & Basic Ticket API

**Execution order:** Must complete Phase 1 before starting this phase.

---

## Task 2.1 — Security Utilities

| Field | Value |
|-------|-------|
| **Execution order** | 1 (first in Phase 2) |
| **File to implement** | `app/core/security.py` |
| **Cannot implement before** | Task 1.1 (`app/core/config.py`) — requires `settings.SECRET_KEY`, `settings.ALGORITHM` |
| **Owner** | Om |
| **Blocks** | Task 2.2 (user schemas may use verification), Task 2.3 (auth API) |

### Description

Implement password hashing and JWT token creation/validation. This module provides the security primitives used by the auth API. Passwords must never be stored in plain text; use bcrypt for hashing. JWT tokens are stateless and contain user ID and role.

**Deliverables:**
- Password hashing: use `passlib` with `bcrypt` context
  - `hash_password(plain_password: str) -> str`
  - `verify_password(plain_password: str, hashed_password: str) -> bool`
- JWT: use `python-jose`
  - `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str`
  - `decode_token(token: str) -> dict` (returns payload or raises)
- Read `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` from `settings`
- Reference: Technical Spec § 10.1 (Authentication), § 10.2 (Password Handling)

---

## Task 2.2 — User Schemas

| Field | Value |
|-------|-------|
| **Execution order** | 2 |
| **File to implement** | `app/schemas/user.py` |
| **Cannot implement before** | Task 1.3 (`app/models/user.py`) — schema should align with model |
| **Owner** | Om |
| **Blocks** | Task 2.3 (auth API uses these schemas) |

### Description

Define Pydantic schemas for user-related API validation and responses. These schemas validate incoming login/registration data and shape outgoing responses. Never include `hashed_password` in response schemas.

**Deliverables:**
- `UserLogin`: `email`, `password`
- `UserCreate` (optional, for registration): `email`, `password`
- `UserResponse`: `id`, `email`, `role` — no password fields
- `Token`: `access_token`, `token_type` (default "bearer")
- Reference: Technical Spec § 5.4 (Schema Layer)

---

## Task 2.3 — Auth API

| Field | Value |
|-------|-------|
| **Execution order** | 3 |
| **File to implement** | `app/api/auth.py` |
| **Cannot implement before** | Task 2.1 (`app/core/security.py`), Task 2.2 (`app/schemas/user.py`), Task 1.3 (`app/models/user.py`) |
| **Owner** | Om |
| **Blocks** | Protected routes in tickets, feedback, admin |

### Description

Implement authentication endpoints. Users log in with email and password; the API returns a JWT access token. Optional: registration endpoint for new users.

**Deliverables:**
- `POST /auth/login`: accepts `UserLogin`, validates credentials, returns `Token`
- `POST /auth/register` (optional): accepts `UserCreate`, hashes password, creates user, returns `UserResponse`
- Use `get_db` dependency for database access
- Verify password with `verify_password`; create token with `create_access_token`
- Return 401 on invalid credentials
- Reference: Technical Spec § 10.1 (Authentication)

---

## Task 2.4 — Ticket Schemas

| Field | Value |
|-------|-------|
| **Execution order** | 4 |
| **File to implement** | `app/schemas/ticket.py` |
| **Cannot implement before** | Task 1.4 (`app/models/ticket.py`) |
| **Owner** | Prajwal |
| **Blocks** | Task 2.5 (tickets API) |

### Description

Define Pydantic schemas for ticket-related API validation and responses. These schemas define the structure of create-ticket payloads and ticket list/detail responses.

**Deliverables:**
- `TicketCreate`: `message` (required string)
- `TicketResponse` / `TicketRead`: `id`, `message`, `intent`, `confidence`, `status`, `created_at`
- `TicketList`: list of `TicketResponse`
- Reference: Technical Spec § 5.4 (Schema Layer), § 7.2 (Ticket)

---

## Task 2.5 — Basic Tickets API

| Field | Value |
|-------|-------|
| **Execution order** | 5 |
| **File to implement** | `app/api/tickets.py` |
| **Cannot implement before** | Task 2.4 (`app/schemas/ticket.py`), Task 1.4 (`app/models/ticket.py`), Task 1.2 (`get_db`) |
| **Owner** | Prajwal |
| **Blocks** | Phase 3 (wiring automation into ticket creation) |

### Description

Implement basic ticket creation and retrieval endpoints. At this stage, tickets are created with status `OPEN` and no AI processing. No automation is wired yet.

**Deliverables:**
- `POST /tickets`: accepts `TicketCreate`, creates ticket with `status="open"`, returns `TicketResponse`
- `GET /tickets`: returns list of tickets (optional: filter by status)
- `GET /tickets/{id}`: returns single ticket or 404
- Use `Depends(get_db)` for database session
- Do NOT implement intent classification, similarity search, or auto-resolution yet
- Reference: Technical Spec § 5.1 (API Layer)

---

## Phase 2 Dependency Graph

```
Phase 1 complete
    |
2.1 security.py (needs config)
    |
2.2 user schemas (needs user model)
    |
2.3 auth API (needs security + user schemas + user model)
    |
2.4 ticket schemas (needs ticket model)
    |
2.5 tickets API (needs ticket schemas + ticket model + get_db)
```
