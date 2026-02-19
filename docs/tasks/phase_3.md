# Phase 3: AI Pipeline

**Execution order:** Must complete Phase 1 and Phase 2 before starting. Ticket creation must exist so automation can be wired.

---

## Task 3.1 — Intent Classification

| Field | Value |
|-------|-------|
| **Execution order** | 1 (first in Phase 3) |
| **File to implement** | `app/services/classifier.py` |
| **Cannot implement before** | None within Phase 3 (can use config if needed) |
| **Owner** | Om |
| **Blocks** | Task 3.4 (decision engine consumes confidence), Task 3.5 (wiring) |

### Description

Implement the intent classification service. Given a raw ticket message, the classifier returns an intent label and a confidence score (0.0–1.0). This is the first step in the AI pipeline.

**Deliverables:**
- Function: `classify_intent(message: str) -> dict` with keys `intent`, `confidence`
- Example intents: `login_issue`, `payment_issue`, `account_issue`, `technical_issue`, `feature_request`, `general_query`, `unknown`
- MVP: rule-based or keyword matching; future: NLP/ML model
- Confidence must be in range 0.0–1.0
- Reference: Technical Spec § 9.1 (Intent Classification)

---

## Task 3.2 — Similarity Search

| Field | Value |
|-------|-------|
| **Execution order** | 2 |
| **File to implement** | `app/services/similarity.py` |
| **Cannot implement before** | None within Phase 3 |
| **Owner** | Prajwal |
| **Blocks** | Task 3.3 (resolver can use similar solution), Task 3.5 (wiring) |

### Description

Implement similarity search to find previously resolved tickets that match a new ticket's message. If a similar resolved ticket exists, its solution can be reused. This improves accuracy and consistency.

**Deliverables:**
- Function: `find_similar_ticket(new_message: str, resolved_tickets: list[dict]) -> dict | None`
- Input: new ticket message, list of resolved ticket objects (with `message` and optionally `response`/solution)
- Output: `{"matched_text": str, "similarity_score": float}` or `None` if no match
- Use a similarity threshold (e.g., 0.7); return `None` if best match is below threshold
- MVP: simple text similarity (e.g., TF-IDF, cosine); future: embeddings/vector DB
- Reference: Technical Spec § 9.2 (Similarity Search)

---

## Task 3.3 — Response Generation

| Field | Value |
|-------|-------|
| **Execution order** | 3 |
| **File to implement** | `app/services/resolver.py` |
| **Cannot implement before** | None within Phase 3 (pure function, no deps) |
| **Owner** | Prajwal |
| **Blocks** | Task 3.5 (wiring) |

### Description

Implement response generation. Given intent, original message, and optionally a similar ticket's solution, produce the final human-readable reply. This component **only returns text**; it does not update the database or make decisions.

**Deliverables:**
- Function: `generate_response(intent: str, original_message: str, similar_solution: str | None = None) -> str`
- Priority order: (1) reuse `similar_solution` if provided, (2) intent-based static templates, (3) fallback
- Provide safe, polite, conservative wording
- Do NOT decide auto-resolve vs escalate; do NOT touch DB
- Reference: Technical Spec § 9.3 (Response Generation)

---

## Task 3.4 — Decision Engine

| Field | Value |
|-------|-------|
| **Execution order** | 4 |
| **File to implement** | `app/services/decision.py` |
| **Cannot implement before** | Task 1.1 (`app/core/config.py`) — uses `CONFIDENCE_THRESHOLD_AUTO_RESOLVE` |
| **Owner** | Om |
| **Blocks** | Task 3.5 (wiring) |

### Description

Implement the decision engine: the safety gate that determines whether a ticket should be auto-resolved or escalated to a human. This is pure logic only—no DB, no HTTP.

**Deliverables:**
- Function: `decide_resolution(confidence: float) -> Literal["AUTO_RESOLVE", "ESCALATE"]`
- Rule: `confidence >= threshold` → `AUTO_RESOLVE`, else `ESCALATE`
- Use `settings.CONFIDENCE_THRESHOLD_AUTO_RESOLVE` (default 0.75)
- Validation: confidence must be 0.0–1.0; invalid or missing → `ESCALATE`
- Reference: Technical Spec § 9.4 (Decision Engine)

---

## Task 3.5 — Wire Automation into Ticket Flow

| Field | Value |
|-------|-------|
| **Execution order** | 5 |
| **File to implement** | `app/api/tickets.py` (modify) |
| **Cannot implement before** | Tasks 3.1, 3.2, 3.3, 3.4 (all AI services), Task 2.5 (tickets API) |
| **Owner** | Prajwal |
| **Blocks** | Phase 4 (feedback, admin) |

### Description

Wire the full AI pipeline into ticket creation. When a ticket is created via `POST /tickets`, run: classifier → similarity search → decision engine. If `AUTO_RESOLVE`, generate response, update ticket status, store response. If `ESCALATE`, set status to `escalated`.

**Deliverables:**
- In `POST /tickets` handler, after creating ticket:
  1. Call `classify_intent(ticket.message)` → get intent, confidence
  2. Fetch resolved tickets from DB; call `find_similar_ticket(ticket.message, resolved_tickets)`
  3. Call `decide_resolution(confidence)`
  4. If `AUTO_RESOLVE`: call `generate_response(...)`, update ticket status to `auto_resolved`, store response
  5. If `ESCALATE`: update ticket status to `escalated`
- Handle AI failures gracefully: on any error, escalate (never block user)
- Reference: Technical Spec § 9.5 (End-to-End Automation Flow)

---

## Phase 3 Dependency Graph

```text
3.1 classifier.py
    |
3.2 similarity.py    3.3 resolver.py
    |                    |
    +--------+-----------+
             |
3.4 decision.py (needs config)
             |
             v
3.5 Wire into tickets.py (needs 3.1, 3.2, 3.3, 3.4)
```
