# Dependency Version Audit — 2026-06-28

Tracks Issue #11 (`openai==1.3.0` very outdated) and Issue #12 (general
dependency pinning audit) from the security/production-readiness review.

## Why this mattered

`requirements.txt` previously pinned several packages 2–3 years behind
current releases (`fastapi==0.104.1`, `pydantic==2.4.0`, `openai==1.3.0`,
`bcrypt==4.1.1`, ...). Old pins accumulate known CVEs over time and fall
further from upstream support as releases age.

## Method

Every new pin was verified together, not in isolation:

1. Installed the full candidate set into a clean virtualenv and resolved
   with `pip check` (zero conflicts).
2. Booted the actual app (`create_app()`) against the candidate set.
3. Ran the full `pytest` suite against the candidate set and against the
   original pinned set, side by side, on the same machine.
4. Compared failures line-for-line between the two runs.

Result: **identical pass/fail counts in both runs** (481 passed / 14 failed
in each). The 14 failures are pre-existing test/route mismatches unrelated
to this change — see "Known pre-existing failures" below. The dependency
bump itself introduced zero regressions.

## Key compatibility checks

- **`openai` 1.3.0 → 2.44.0** — `app/services/response_generator.py` and
  the new LLM classifier/sentiment paths in `app/services/classifier.py`
  and `app/services/ai_service.py` only use the long-stable
  `client.chat.completions.create(...)` interface (`from openai import
  OpenAI`, `response.choices[0].message.content`). This surface was
  confirmed present and unchanged on 2.44.0 — no code changes were needed
  in any file beyond the requirements pin.
- **`resend` 0.8.0 → 2.5.1** — `app/core/otp.py` uses the module-level
  `resend.api_key = ...` / `resend.Emails.send({...})` pattern. Confirmed
  both attributes still exist and behave the same on 2.5.1.
- **`bcrypt` 4.1.1 → 4.2.1** (with `passlib==1.7.4`) — hashing and
  verification both confirmed working. Note: passlib 1.7.4 prints a
  harmless `"(trapped) error reading bcrypt version"` warning on bcrypt
  >= 4.1 (a known passlib/bcrypt version-probe quirk). This warning is
  **pre-existing** — it already occurs with the old `bcrypt==4.1.1` pin —
  and does not affect correctness; `pwd_context.hash()` /
  `pwd_context.verify()` both work as expected. Not addressed here as it's
  cosmetic and outside this audit's scope.

## Known pre-existing failures (not introduced by this change)

The following 14 tests fail identically on both the old and new dependency
sets — they're stale assertions against ticket-ownership/auth behavior that
predate this audit (most look related to the `GET /tickets/{id}` and
`GET /tickets/` auth fixes landing without their corresponding tests being
updated):

- `tests/api/test_tickets.py::TestListTickets::test_list_tickets_with_data`
- `tests/api/test_tickets.py::TestListTickets::test_list_tickets_multiple_tickets`
- `tests/api/test_tickets.py::TestGetTicket::test_get_ticket_success`
- `tests/api/test_tickets.py::TestGetTicket::test_get_ticket_not_found`
- `tests/api/test_tickets.py::TestGetTicket::test_get_ticket_structure`
- `tests/api/test_tickets.py::TestTicketAPIIntegration::test_complete_workflow`
- `tests/api/test_tickets.py::TestTicketAPIIntegration::test_multiple_tickets_workflow`
- `tests/api/test_tickets.py::TestTicketAccessControl::test_authenticated_create_sets_user_id`
- `tests/services/test_automation_integration.py::TestTicketLifecycle::test_full_lifecycle_auto_resolve`
- `tests/services/test_automation_integration.py::TestTicketLifecycle::test_get_ticket_after_processing`
- `tests/services/test_automation_integration.py::TestTicketLifecycle::test_list_tickets_filter_by_status`
- `tests/services/test_automation_integration.py::TestAPIValidation::test_get_nonexistent_ticket`
- `tests/services/test_similarity_search.py::test_similarity_search_db_cache_hit`
- `tests/services/test_ticket_ownership.py::test_list_tickets_without_token_returns_all_tickets`

Three test files also fail to *collect* regardless of dependency versions
(import errors / duplicate basenames), also pre-existing:
`tests/models/test_feedback.py`, `tests/services/test_automation_unit.py`,
`tests/services/test_comprehensive_suite.py`.

These are tracked separately and are out of scope for the dependency audit
and AI/security hardening fixes in this PR.
