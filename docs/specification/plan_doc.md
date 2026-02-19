# Implementation Plan

**Automated Customer Support Resolution System**

This document outlines the recommended implementation order for the project, aligned with the [Technical Specification](./TECHNICAL_SPEC.md).

---

## Table of Contents

- [Phase 1: Foundation](#phase-1-foundation)
- [Phase 2: Auth & Basic Ticket API](#phase-2-auth--basic-ticket-api)
- [Phase 3: AI Pipeline](#phase-3-ai-pipeline)
- [Phase 4: Feedback, Admin & Polish](#phase-4-feedback-admin--polish)
- [Summary: First Steps](#summary-first-steps)

---

## Phase 1: Foundation

*Implement these first.*

### 1. Core configuration (`app/core/config.py`)

- [ ] Environment-based config
- [ ] Centralized settings
- [ ] No other module should depend on this before it exists

### 2. Database setup (`app/db/session.py`)

- [ ] DB connection/session management
- [ ] Depends on config

### 3. Data models (`app/models/`)

| File        | Purpose                                  |
|-------------|------------------------------------------|
| `user.py`   | Auth and user management                 |
| `ticket.py` | Main entity for support tickets          |
| `feedback.py` | Schema designed now; implementation later |
- [ ] Migrations to create tables

### 4. Main entry point (`app/main.py`)

- [ ] FastAPI app initialization
- [ ] Wiring and startup/shutdown hooks

---

## Phase 2: Auth & Basic Ticket API

### 1. Security (`app/core/security.py`)

- [ ] Password hashing (bcrypt)
- [ ] JWT creation and validation

### 2. User schemas (`app/schemas/user.py`)

- [ ] Validation for login/registration
- [ ] Response schemas

### 3. Auth API (`app/api/auth.py`)

- [ ] Login endpoint
- [ ] (Optional) Registration endpoint

### 4. Ticket schemas (`app/schemas/ticket.py`)

- [ ] Create ticket payloads
- [ ] Read ticket responses

### 5. Basic ticket API (`app/api/tickets.py`)

- [ ] Create ticket
- [ ] Get ticket(s)
- [ ] *No AI yet — tickets remain `OPEN`*

---

## Phase 3: AI Pipeline

### 1. Intent classification (`app/services/classifier.py`)

- **Input:** Raw ticket message  
- **Output:** Intent label + confidence score

### 2. Similarity search (`app/services/similarity.py`)

- Compare new ticket with previously resolved tickets
- Reuse known solutions when available

### 3. Response generation (`app/services/resolver.py`)

- Generate or select reply text from:
  - Intent
  - Similar ticket solutions
  - Fallback templates

### 4. Decision engine (`app/services/decision.py`)

- Confidence threshold (e.g. ≥ 0.75 → auto-resolve)
- Pure logic only — no DB or HTTP access

### 5. Wire automation into ticket flow

- After ticket creation: `classifier` → `similarity` → `decision` → `resolver` (if auto-resolve)
- Update ticket status and store response

---

## Phase 4: Feedback, Admin & Polish

- [ ] **Feedback API** (`app/api/feedback.py`)
- [ ] **Admin API** (`app/api/admin.py`)
- [ ] **Error handling strategy** (Technical Spec § 11)
- [ ] **Tests** (Technical Spec § 14)

---

## Summary: First Steps

Start with these four items:

1. `app/core/config.py`
2. `app/db/session.py`
3. `app/models/user.py`, `ticket.py`, `feedback.py`
4. `app/main.py`

This provides the config, database, and core models required for all other work. After that:

- **Phase 2:** Security + auth, then basic ticket creation
- **Phase 3:** AI pipeline
- **Phase 4:** Feedback, admin, and polish
