# Phase 4: Feedback, Admin & Polish

**Execution order:** Must complete Phase 1, 2, and 3 before starting.

---

## Task 4.1 — Feedback API

| Field | Value |
|-------|-------|
| **Execution order** | 1 |
| **File to implement** | `app/api/feedback.py` |
| **Cannot implement before** | Task 1.5 (`app/models/feedback.py`), Task 1.4 (`app/models/ticket.py`), Task 2.3 (auth for protected routes if required) |
| **Owner** | Om |
| **Blocks** | None (terminal for feedback feature) |

### Description

Implement the feedback API so users can submit feedback after a ticket is resolved. Feedback includes rating and whether the issue was resolved. This data is used to measure quality and improve future automation.

**Deliverables:**
- Define schemas: `FeedbackCreate` (ticket_id, rating, resolved), `FeedbackResponse`
- `POST /feedback`: create feedback record for a ticket
- `GET /feedback/{ticket_id}` or `GET /feedback?ticket_id=...`: retrieve feedback for a ticket
- Use `Depends(get_db)` for database access
- Validate that ticket exists before creating feedback
- Reference: Technical Spec § 3.1 (In Scope: Feedback collection)

---

## Task 4.2 — Admin API

| Field | Value |
|-------|-------|
| **Execution order** | 2 |
| **File to implement** | `app/api/admin.py` |
| **Cannot implement before** | Task 2.3 (auth API), Task 1.3 (`app/models/user.py`) — need role check |
| **Owner** | Prajwal |
| **Blocks** | None (terminal for admin feature) |

### Description

Implement admin-only endpoints for monitoring and metrics. These endpoints must be restricted to users with `role="admin"`. Regular users and agents must receive 403 Forbidden.

**Deliverables:**
- Middleware or dependency: `require_admin(current_user)` — returns 403 if role != admin
- `GET /admin/metrics`: aggregate stats (e.g., ticket counts by status, auto-resolve rate, escalation rate)
- `GET /admin/tickets`: list all tickets (optional: filters, pagination)
- Use JWT to get current user; verify role before returning data
- Reference: Technical Spec § 10.3 (Authorization), § 3.1 (Admin monitoring APIs)

---

## Task 4.3 — Error Handling Strategy

| Field | Value |
|-------|-------|
| **Execution order** | 3 |
| **File to implement** | `app/main.py` (exception handlers), possibly `app/core/exceptions.py` |
| **Cannot implement before** | Task 1.7 (`app/main.py`) |
| **Owner** | Om |
| **Blocks** | None |

### Description

Implement a consistent error handling strategy across the API. Errors should be understandable, never leak internal details (e.g., stack traces), and return appropriate HTTP status codes.

**Deliverables:**
- Map error types to HTTP status: ValidationError → 400, AuthenticationError → 401, AuthorizationError → 403, NotFound → 404, InternalError → 500
- Register FastAPI exception handlers for `RequestValidationError`, `HTTPException`, and generic `Exception`
- For AI/service failures: return 200 with fallback (e.g., ticket escalated); log internally
- Never expose stack traces to clients; log errors server-side
- Reference: Technical Spec § 11 (Error Handling Strategy)

---

## Task 4.4 — Tests

| Field | Value |
|-------|-------|
| **Execution order** | 4 |
| **File to implement** | `tests/` directory — unit and integration tests |
| **Cannot implement before** | All prior tasks (tests cover implemented functionality) |
| **Owner** | Prajwal |
| **Blocks** | None |

### Description

Implement unit and integration tests to ensure reliability, predictability, and confidence in automation. Mock AI responses for deterministic tests.

**Deliverables:**
- Unit tests: classifier, similarity, decision engine, resolver (mock inputs/outputs)
- Integration tests: full ticket lifecycle, API endpoints (create ticket, get ticket, feedback)
- Test edge cases: confidence at threshold (0.75), invalid confidence, empty message
- Use pytest; mock AI services so tests don't depend on external APIs
- Reference: Technical Spec § 14 (Testing Strategy)

---

## Phase 4 Dependency Graph

```
4.1 feedback API (needs feedback model, ticket model)
4.2 admin API (needs auth, user model with role)
4.3 error handling (needs main.py)
4.4 tests (needs all above)
```
