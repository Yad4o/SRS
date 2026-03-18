# SRS — Phase 5 Task Documentation
### Automated Customer Support Resolution System
**Version 1.0 · March 2026 · Om Yadav & Prajwal**

---

## What Phase 5 Is About

The system works end-to-end. Tickets get classified, similarity search runs, the decision engine fires, and a response comes back. That part is done.

The problem is quality. Right now every login message gets the same template response. Every payment message gets the same template response. The feedback ratings are stored but nothing uses them. OpenAI is configured but never called. Tickets have no owner. The database is SQLite. Rate limiting is configured but not enforced.

Phase 5 fixes all of that. There are **10 tasks** grouped into three areas. Each task has a full explanation of the problem, exactly what to change, and a ready-to-paste Windsurf prompt.

**Do them in this order:**

| # | Task | Owner | Area |
|---|------|-------|------|
| 1 | Fix known bugs | Om | Housekeeping |
| 2 | Rewrite response templates + sub-intent routing | Prajwal | AI Quality |
| 3 | Add sub_intent to classifier | Prajwal | AI Quality |
| 4 | Wire OpenAI with fallback chain | Om | AI Quality |
| 5 | Feedback quality scores | Prajwal | AI Quality |
| 6 | Add user_id to tickets + ownership | Om | Data Model |
| 7 | Agent assignment + ticket close | Om | Data Model |
| 8 | Alembic migrations + Neon PostgreSQL | Om | Production |
| 9 | Redis caching for similarity search | Om | Production |
| 10 | Rate limiting + test suite updates | Om + Prajwal | Production |

---

## Before You Start

Make sure you understand the current codebase layout. Every task references specific files. The relevant ones are:

```
app/
├── services/
│   ├── classifier.py          ← intent classification (rule-based keywords)
│   ├── similarity_search.py   ← TF-IDF cosine similarity
│   ├── decision_engine.py     ← confidence threshold gate (≥0.75 → auto-resolve)
│   ├── response_generator.py  ← produces the final response text
│   └── ai_service.py          ← AI service wrapper with fallback
├── models/
│   ├── ticket.py              ← Ticket ORM model
│   ├── user.py                ← User ORM model
│   └── feedback.py            ← Feedback ORM model
├── api/
│   └── tickets.py             ← _run_ticket_automation lives here
└── core/
    └── config.py              ← all settings including OPENAI_API_KEY
```

---

## Task 1 — Fix Known Bugs

**Priority: Do this first. These bugs affect everything else.**

### The Three Bugs

**Bug 1 — Test database leaks to project root**

The file `tests/test_ai_pipeline_integration.py` creates a SQLite database at a hardcoded path `./test_ai_pipeline.db`. Every time you run tests this file gets left behind in the project root. All other test files use a `tempfile.NamedTemporaryFile` pattern that cleans up after itself. This one does not.

**Bug 2 — Circular import in ticket.py**

`app/models/ticket.py` has this at the top:

```python
from app.models.feedback import Feedback
```

This is a direct class import at module level. If anything imports `ticket.py` before `feedback.py` is fully loaded, Python raises an `ImportError`. SQLAlchemy supports string-based relationship references specifically to avoid this. The fix is a one-line change.

**Bug 3 — similar_solution passed verbatim with no sanitization**

In `response_generator.py`, when a similar past ticket's solution is reused, it is passed directly into the response string with no length cap, no stripping of control characters, and no truncation. A past ticket with a 10,000-character response would produce a 10,000-character new response. A past ticket with weird characters would propagate them forward.

### Exactly What to Change

**Bug 1 fix** — open `tests/test_ai_pipeline_integration.py` and replace the hardcoded database setup at the top of the file. Change:

```python
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_ai_pipeline.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

Replace with the same `tempfile` + session-scoped fixture pattern used in `tests/test_automation_integration.py`. Specifically: add a `temp_db_file` session-scoped fixture that creates a `tempfile.NamedTemporaryFile` with `delete=False`, yields its name, and then calls `os.unlink` in cleanup. Use that path for the engine URL.

**Bug 2 fix** — open `app/models/ticket.py`. Remove the top-level import:

```python
from app.models.feedback import Feedback  # DELETE THIS LINE
```

The relationship definition currently reads:

```python
feedback = relationship(
    "Feedback",
    back_populates="ticket",
    uselist=False,
)
```

This already uses a string `"Feedback"` which is SQLAlchemy's lazy resolution syntax. The top-level import is completely unnecessary for this to work. Removing it eliminates the circular import.

**Bug 3 fix** — open `app/services/response_generator.py`. Find the section that uses `similar_solution` (the first priority branch). Before using it, add:

```python
if similar_solution and similar_solution.strip():
    # Sanitize: strip whitespace, cap at 500 characters
    clean_solution = similar_solution.strip()[:500]
    return f"I understand you're experiencing an issue. Based on a similar case, here's what helped: {clean_solution}"
```

### Windsurf Prompt

```
I need you to fix three specific bugs in the SRS project. Do all three in sequence.

BUG 1 — tests/test_ai_pipeline_integration.py
This file creates a SQLite database at a hardcoded path "./test_ai_pipeline.db" which 
leaks to the project root after every test run. Fix it by replacing the module-level 
database setup with a session-scoped tempfile fixture that matches the pattern used in 
tests/test_automation_integration.py. The fixture should use tempfile.NamedTemporaryFile 
with delete=False, yield the file path, and call os.unlink in cleanup wrapped in a 
try/except. The engine and TestingSessionLocal should be created inside a function-scoped 
fixture that depends on the session-scoped temp_db_file fixture.

BUG 2 — app/models/ticket.py
Line near the top has: from app.models.feedback import Feedback
Remove this import entirely. The relationship() below already uses the string "Feedback" 
which is SQLAlchemy's lazy resolution — it does not need the actual class imported. 
Removing this eliminates a circular import risk.

BUG 3 — app/services/response_generator.py
In the generate_response function, the first priority branch uses similar_solution 
directly in an f-string with no sanitization. Before using it, add:
  clean_solution = similar_solution.strip()[:500]
and use clean_solution in the f-string instead of similar_solution.

After all three fixes: run pytest tests/test_ai_pipeline_integration.py -v to confirm 
tests pass and no .db file is left in the project root.
```

---

## Task 2 — Rewrite Response Templates + Sub-Intent Routing

**Priority: Highest impact change in Phase 5. Do immediately after Task 1.**

### The Problem in Detail

Open `app/services/response_generator.py` and look at the `login_issue` templates:

```python
"login_issue": [
    "I understand you're having trouble logging in. Please try resetting your password or check your credentials.",
    "Login issues can often be resolved by clearing your browser cache or trying a different browser.",
    "For login problems, please verify your username and password, or use the 'forgot password' option if needed."
]
```

All three of these say the same thing — reset your password, check your credentials. The template selector picks between them based on whether the message contains `?` or `how` (template 1), `urgent` or `emergency` (template 2), or anything else (template 3). This means someone asking "I forgot my password" and someone saying "my account is locked after too many attempts" both get similar advice about resetting credentials.

The real difference between login sub-problems:
- **Password reset** — user forgot their password, needs reset link, check spam folder
- **Account locked** — too many attempts, 2FA issue, account suspended, needs agent
- **Wrong credentials** — typing wrong email/password, browser autofill issue, caps lock

These need genuinely different responses. Same problem exists for every intent.

### Exactly What to Change

**Step 1 — Rewrite templates in response_generator.py**

Replace the entire `response_templates` dict with this structure. Each intent gets 3 templates that address 3 genuinely different sub-problems:

```python
response_templates = {
    "login_issue": [
        # sub: password_reset — user forgot password or needs reset
        "It looks like you need to reset your password. Go to the login page, click 'Forgot Password', enter your email address, and check your inbox including spam folder. The reset link expires in 15 minutes.",
        # sub: account_locked — too many attempts, 2FA, suspended
        "Your account may be locked due to too many failed attempts or a 2FA issue. Wait 30 minutes before trying again. If you still cannot access your account, contact our support team directly and we can unlock it manually.",
        # sub: credentials — wrong email/password combination
        "Double-check that you are using the correct email address and that your password has no extra spaces. If you signed up with Google or another provider, try the 'Sign in with Google' button instead of the email/password form.",
    ],
    "payment_issue": [
        # sub: duplicate_charge — charged twice, unexpected charge
        "We can see this needs immediate attention. Please gather your transaction IDs from your bank statement and submit them through the billing portal. Our team processes duplicate charge refunds within 3-5 business days.",
        # sub: payment_declined — card rejected, payment failed
        "Your payment was declined, which is usually caused by an expired card, insufficient funds, or your bank blocking the transaction. Update your payment method in Account Settings, or contact your bank to authorize charges from us.",
        # sub: billing_question — invoice query, pricing, plan
        "For billing questions, you can view all your invoices and receipts in Account Settings under the Billing tab. If you need a specific invoice format or have a question about your plan, reply to any billing email and our finance team will assist you.",
    ],
    "account_issue": [
        # sub: delete_account — wants to close or remove data
        "To delete your account, go to Account Settings > Privacy > Delete Account. This is permanent and removes all your data within 30 days per our privacy policy. If you just need a break, consider deactivating instead which keeps your data.",
        # sub: update_info — email, phone, name, address change
        "You can update your personal information in Account Settings > Profile. Email changes require verification from your new address. If you are changing your login email, you will receive confirmation links at both your old and new email addresses.",
        # sub: account_access — cannot access, need data export, permissions
        "For account access issues or data export requests, please email support with your account email address and a description of what you need. We respond to account-level requests within 24 hours.",
    ],
    "technical_issue": [
        # sub: crash_error — app crashing, error message shown
        "Please take a screenshot of the error message and note what action triggered it. Try clearing your browser cache (Ctrl+Shift+Delete) and reloading. If the error persists, send the screenshot to support and we will investigate.",
        # sub: performance — slow, loading, not responding
        "Performance issues are often caused by browser extensions or network conditions. Try opening the app in an incognito window first. If it is faster there, a browser extension is the likely cause. Also check your internet connection speed at fast.com.",
        # sub: feature_broken — specific feature not working
        "If a specific feature is not working, check our status page at status.example.com for any ongoing incidents. If there are none, try a different browser or device to rule out local issues. Report the problem with your browser version and OS.",
    ],
    "feature_request": [
        # sub: new_feature — brand new capability requested
        "Thank you for the suggestion. We track all feature requests and review them quarterly with the product team. The most upvoted requests get prioritized first — you can add your vote and follow its progress on our public roadmap at roadmap.example.com.",
        # sub: improvement — existing feature needs to be better
        "Improving existing features is one of our highest priorities. Your feedback has been logged. If you can describe the specific friction point — what you expected vs what happened — that helps the team understand the priority and scope of the change.",
        # sub: integration — wants connection with another tool
        "We are always looking to add integrations. You can see all current and planned integrations on our integrations page. If the tool you need is not listed, submit it on the roadmap and others can vote on it to increase its priority.",
    ],
    "general_query": [
        # sub: how_to — wants instructions for something
        "I can help with that. Could you give a bit more detail about what you are trying to do? In the meantime, our help center at help.example.com has step-by-step guides for most common tasks and a search bar to find specific topics quickly.",
        # sub: pricing_plan — questions about cost or plans
        "Our pricing is available at example.com/pricing. If you are trying to decide between plans, the main differences are storage limits, team member seats, and access to advanced features. Reply with your use case and we can recommend the right plan.",
        # sub: contact_escalate — wants to speak to a human
        "You can reach our support team by email at support@example.com or use the live chat button in the bottom right corner of the app during business hours (Mon-Fri 9am-6pm EST). For urgent issues, live chat has the fastest response time.",
    ],
}
```

**Step 2 — Replace the template selection logic**

The current selector checks for `?` and `urgent` in the raw message. Replace it with keyword-based sub-intent matching for each intent. After the `response_templates` dict, add a `_select_template` function:

```python
def _select_template(intent: str, message: str) -> str:
    """Select the right template index based on keywords in the message."""
    msg = message.lower()
    
    selectors = {
        "login_issue": [
            (["forgot", "reset", "remember", "lost", "recovery", "recover"],  0),
            (["locked", "lock", "block", "blocked", "2fa", "two factor", "suspended", "banned", "attempts"], 1),
        ],
        "payment_issue": [
            (["twice", "double", "duplicate", "charged again", "extra charge", "refund", "unexpected"], 0),
            (["declined", "failed", "rejected", "not going through", "error", "unable to pay"], 1),
        ],
        "account_issue": [
            (["delete", "remove", "close", "cancel", "deactivate", "gdpr", "data"], 0),
            (["update", "change", "edit", "email", "phone", "name", "address", "profile"], 1),
        ],
        "technical_issue": [
            (["crash", "error", "broken", "not working", "bug", "fails", "failed", "exception"], 0),
            (["slow", "loading", "performance", "lag", "freeze", "frozen", "hang", "timeout"], 1),
        ],
        "feature_request": [
            (["add", "new", "build", "create", "implement", "feature", "wish", "want"], 0),
            (["improve", "better", "fix", "enhance", "update", "change how"], 1),
        ],
        "general_query": [
            (["how", "what", "where", "when", "guide", "steps", "tutorial", "help me"], 0),
            (["price", "pricing", "cost", "plan", "tier", "subscribe", "upgrade", "paid"], 1),
        ],
    }
    
    if intent in selectors:
        for keywords, index in selectors[intent]:
            if any(kw in msg for kw in keywords):
                return response_templates[intent][index]
    
    # Default: use the third template (general case for this intent)
    templates = response_templates.get(intent, [])
    if templates:
        return templates[-1]
    
    # Absolute fallback
    return "Thank you for contacting us. A support agent will review your request and respond within 24 hours."
```

**Step 3 — Update generate_response to use _select_template**

In the `generate_response` function, replace the existing template selection block (the `if "?" in original_message` logic) with a single call to `_select_template(intent, original_message)`.

### Windsurf Prompt

```
I need you to completely rewrite the response templates and selection logic in 
app/services/response_generator.py. Here is exactly what to do:

STEP 1 — Replace the response_templates dict
The current templates dict has 3 entries per intent that all say roughly the same thing.
Replace the entire dict with new templates where each of the 3 entries addresses a 
genuinely different sub-problem within that intent.

For login_issue:
- Template 0 (password forgotten/reset): Explain the forgot password flow, mention the 
  reset link expires in 15 minutes, check spam folder.
- Template 1 (account locked/2FA): Explain wait 30 minutes, mention 2FA, offer manual 
  unlock via support team.  
- Template 2 (wrong credentials/default): Check email address, check for spaces, mention 
  social sign-in option.

For payment_issue:
- Template 0 (duplicate/unexpected charge): Ask for transaction IDs, mention 3-5 business 
  day refund timeline.
- Template 1 (payment declined): List causes (expired card, insufficient funds, bank 
  block), direct to update payment method in settings.
- Template 2 (billing question/default): Direct to billing tab in account settings, 
  mention replying to billing email.

For account_issue:
- Template 0 (delete/GDPR): Explain the delete account path in settings, mention data 
  removed in 30 days, suggest deactivation as alternative.
- Template 1 (update info): Explain settings > profile path, mention email change 
  requires verification at both addresses.
- Template 2 (access/export/default): Ask to email support with account email.

For technical_issue:
- Template 0 (crash/error): Ask for screenshot, suggest clearing browser cache.
- Template 1 (slow/performance): Suggest incognito window to rule out extensions, 
  mention fast.com for connection test.
- Template 2 (broken feature/default): Mention status page, suggest different browser.

For feature_request:
- Template 0 (new feature): Mention public roadmap, upvoting system.
- Template 1 (improvement): Ask for specific friction point description.
- Template 2 (integration/default): Mention integrations page and roadmap voting.

For general_query:
- Template 0 (how-to): Ask for more detail, mention help center.
- Template 1 (pricing): Describe pricing page, offer plan recommendation.
- Template 2 (contact/default): Give email and live chat options with hours.

STEP 2 — Add a _select_template helper function
After the dict, add a function _select_template(intent: str, message: str) -> str that:
- Takes the intent string and raw message
- Lowercases the message
- For each intent, defines a list of (keyword_list, template_index) tuples
- Returns the template for the first keyword match
- Returns the last template (index -1) as the default if no keywords match
- Returns a safe fallback string if the intent is not in the dict at all

Keyword groups to use:
- login_issue: index 0 = ["forgot", "reset", "remember", "lost", "recovery"]
               index 1 = ["locked", "lock", "blocked", "2fa", "two factor", "suspended", "attempts"]
- payment_issue: index 0 = ["twice", "double", "duplicate", "refund", "unexpected", "extra"]
                 index 1 = ["declined", "failed", "rejected", "not going through"]
- account_issue: index 0 = ["delete", "remove", "close", "cancel", "deactivate", "gdpr"]
                 index 1 = ["update", "change", "edit", "email", "phone", "name", "profile"]
- technical_issue: index 0 = ["crash", "error", "broken", "not working", "bug", "fails"]
                   index 1 = ["slow", "loading", "performance", "lag", "freeze", "timeout"]
- feature_request: index 0 = ["add", "new", "build", "implement", "feature", "wish"]
                   index 1 = ["improve", "better", "fix", "enhance", "update existing"]
- general_query:   index 0 = ["how", "what", "where", "when", "guide", "steps", "tutorial"]
                   index 1 = ["price", "pricing", "cost", "plan", "upgrade", "subscribe"]

STEP 3 — Update generate_response
In the generate_response function:
- Remove the existing if/elif block that checks for "?" and "urgent" in the message
- Replace it with: return _select_template(intent, original_message)
- Keep the similar_solution priority branch exactly as it is (it runs before template selection)
- Keep the fallback responses at the bottom as the final safety net

After the change, write 3 tests in tests/test_response_generator.py that verify:
1. "I forgot my password" → login_issue returns the reset flow template (contains "Forgot Password")
2. "my account is locked" → login_issue returns the locked account template (contains "locked")
3. "I was charged twice" → payment_issue returns the duplicate charge template (contains "transaction")
```

---

## Task 3 — Add Sub-Intent to Classifier

**Do this after Task 2 so the sub-intent names match the template keywords.**

### The Problem in Detail

The classifier returns:

```python
{"intent": "login_issue", "confidence": 0.95}
```

This tells us the broad category but not the specific problem. The response generator in Task 2 re-reads the raw message to figure out the sub-problem. This works but it means the keyword logic runs twice — once in the classifier and once in the response generator. More importantly, having a `sub_intent` field stored on the ticket gives you data to analyze later: which sub-problems are most common, which get the worst feedback scores, where the AI is weakest.

### Exactly What to Change

**Step 1 — Add sub_intent detection to classifier.py**

At the end of `classify_intent`, after the `best_match` is determined, add sub-intent detection. The sub-intent keyword groups should match the groups in Task 2's `_select_template` function so they are consistent:

```python
# Sub-intent detection
sub_intent_patterns = {
    "login_issue": [
        ("password_reset",   ["forgot", "reset", "remember", "lost", "recovery", "recover"]),
        ("account_locked",   ["locked", "lock", "blocked", "2fa", "two factor", "suspended", "attempts"]),
        ("wrong_credentials",["credentials", "wrong", "invalid", "incorrect"]),
    ],
    "payment_issue": [
        ("duplicate_charge", ["twice", "double", "duplicate", "refund", "unexpected", "extra charge"]),
        ("payment_declined", ["declined", "failed", "rejected", "not going through"]),
        ("billing_question", ["invoice", "receipt", "plan", "pricing", "upgrade"]),
    ],
    "account_issue": [
        ("delete_account",   ["delete", "remove", "close", "cancel", "deactivate", "gdpr"]),
        ("update_info",      ["update", "change", "edit", "email", "phone", "name", "profile"]),
    ],
    "technical_issue": [
        ("crash_error",      ["crash", "error", "bug", "broken", "not working", "fails"]),
        ("performance",      ["slow", "loading", "lag", "freeze", "timeout", "performance"]),
    ],
    "feature_request": [
        ("new_feature",      ["add", "new", "build", "implement", "wish", "would love"]),
        ("improvement",      ["improve", "better", "enhance", "fix existing"]),
    ],
    "general_query": [
        ("how_to",           ["how", "steps", "guide", "tutorial", "instructions"]),
        ("pricing_plan",     ["price", "cost", "plan", "upgrade", "subscribe", "paid"]),
    ],
}

sub_intent = None
if best_match and best_match in sub_intent_patterns:
    for sub_name, keywords in sub_intent_patterns[best_match]:
        if any(kw in text for kw in keywords):
            sub_intent = sub_name
            break
```

Then update the return statement to include `sub_intent`:

```python
return {
    "intent": best_match,
    "confidence": round(highest_score, 3),
    "sub_intent": sub_intent,  # None if no sub-pattern matched
}
```

Also update the fallback return at the bottom:

```python
return {
    "intent": "unknown",
    "confidence": 0.2,
    "sub_intent": None,
}
```

**Step 2 — Add sub_intent column to Ticket model**

In `app/models/ticket.py`, add the column after the `intent` column:

```python
sub_intent = Column(
    String,
    nullable=True,
    doc="Sub-category of intent (e.g. password_reset, duplicate_charge)",
)
```

**Step 3 — Store sub_intent in the pipeline**

In `app/api/tickets.py`, in `_run_ticket_automation`, update the classification handling:

```python
classification = classify_intent(ticket.message)
intent = classification["intent"]
confidence = classification["confidence"]
sub_intent = classification.get("sub_intent")  # new

ticket.intent = intent
ticket.confidence = confidence
ticket.sub_intent = sub_intent  # new
```

**Step 4 — Pass sub_intent to generate_response**

Update the `generate_response` signature in `response_generator.py`:

```python
def generate_response(intent: str, original_message: str, similar_solution: Optional[str] = None, sub_intent: Optional[str] = None) -> str:
```

When `sub_intent` is provided, use it to directly select the right template index instead of running keyword detection:

```python
# If sub_intent is known, use it to select directly
if sub_intent:
    sub_intent_to_index = {
        "password_reset": 0, "account_locked": 1, "wrong_credentials": 2,
        "duplicate_charge": 0, "payment_declined": 1, "billing_question": 2,
        "delete_account": 0, "update_info": 1,
        "crash_error": 0, "performance": 1,
        "new_feature": 0, "improvement": 1,
        "how_to": 0, "pricing_plan": 1,
    }
    idx = sub_intent_to_index.get(sub_intent)
    if idx is not None:
        templates = response_templates.get(intent, [])
        if idx < len(templates):
            return templates[idx]

# Fall through to keyword-based selection
return _select_template(intent, original_message)
```

**Step 5 — Expose sub_intent in TicketResponse schema**

In `app/schemas/ticket.py`, add to `TicketResponse`:

```python
sub_intent: Optional[str] = None
```

### Windsurf Prompt

```
I need to add sub_intent detection to the SRS classifier and wire it through the pipeline.
Here is the full set of changes required across 5 files.

FILE 1 — app/services/classifier.py
At the end of classify_intent(), after best_match is determined and before the return 
statement, add sub-intent detection logic. Define a sub_intent_patterns dict where keys 
are intent strings and values are lists of (sub_intent_name, keyword_list) tuples. 

Use these sub-intent groups:
- login_issue: password_reset (forgot/reset/remember/lost/recovery), account_locked 
  (locked/lock/blocked/2fa/two factor/suspended/attempts), wrong_credentials (credentials/wrong/invalid)
- payment_issue: duplicate_charge (twice/double/duplicate/refund/unexpected), 
  payment_declined (declined/failed/rejected), billing_question (invoice/receipt/plan/pricing)
- account_issue: delete_account (delete/remove/close/cancel/deactivate/gdpr), 
  update_info (update/change/edit/email/phone/name/profile)
- technical_issue: crash_error (crash/error/bug/broken/not working/fails), 
  performance (slow/loading/lag/freeze/timeout)
- feature_request: new_feature (add/new/build/implement/wish), improvement (improve/better/enhance)
- general_query: how_to (how/steps/guide/tutorial), pricing_plan (price/cost/plan/upgrade)

Loop through the patterns for the matched intent, check if any keyword appears in the 
lowercased cleaned text (the variable already computed earlier in the function), and set 
sub_intent to the first matching sub_intent_name. Default sub_intent to None.

Update all return statements in classify_intent() to include "sub_intent": sub_intent.

FILE 2 — app/models/ticket.py
Add this column after the intent column:
sub_intent = Column(String, nullable=True, doc="Sub-category of intent (e.g. password_reset)")

FILE 3 — app/api/tickets.py
In _run_ticket_automation(), update the classification section to also read and store sub_intent:
  sub_intent = classification.get("sub_intent")
  ticket.sub_intent = sub_intent
Then pass sub_intent to generate_response() when calling it.

FILE 4 — app/services/response_generator.py
Add sub_intent: Optional[str] = None as a parameter to generate_response().
Add a sub_intent_to_index dict that maps each sub_intent name to a template index (0, 1, or 2).
At the start of the template selection section (after the similar_solution check), if 
sub_intent is provided and maps to an index, return that template directly without running 
keyword detection. Only fall through to _select_template() if sub_intent is None or 
does not match any known sub-intent.

FILE 5 — app/schemas/ticket.py
In TicketResponse, add: sub_intent: Optional[str] = None

After all changes, write tests in tests/test_classifier.py that verify:
1. "I forgot my password" returns sub_intent="password_reset" 
2. "my account is locked after too many attempts" returns sub_intent="account_locked"
3. "I was charged twice" returns sub_intent="duplicate_charge"
4. Unknown message like "xyz random" returns sub_intent=None

Do NOT run alembic yet — we will handle migrations in Task 8. For now just add the 
column to the model definition and the app will use create_all on the next restart in 
development.
```

---

## Task 4 — Wire OpenAI with Proper Fallback Chain

**Do this after Task 3 so sub_intent is available to pass to the prompt.**

### The Problem in Detail

`app/core/config.py` has:

```python
AI_PROVIDER: str = "openai"
OPENAI_API_KEY: str | None = None
```

`app/services/response_generator.py` never checks these. The API key can be set and the provider can be configured but zero code reads them. This means you cannot get OpenAI-quality responses even when a key is available.

The integration needs to be careful about one thing: OpenAI must never be a hard dependency. If the API key is missing, if the API is down, if the request times out — the system must fall back to templates without crashing or returning an error to the user. The fallback chain defines a clear priority order.

### The Fallback Chain

```
1. Similarity match with high quality (score > 0.7 and feedback rating ≥ 4)
   → reuse the proven response from a past ticket

2. OpenAI enabled and key present
   → generate a contextual response using the intent + sub_intent as context

3. Static template with sub-intent routing (Task 2 + 3)
   → deterministic, always works, no external dependency

4. Generic fallback string
   → absolute last resort, should almost never fire
```

### Exactly What to Change

**Step 1 — Add OpenAI settings to config.py**

In `app/core/config.py`, add these fields to the `Settings` class after the existing AI fields:

```python
OPENAI_MODEL: str = "gpt-4o-mini"
OPENAI_TIMEOUT: int = 8  # seconds — never wait longer than this
OPENAI_MAX_TOKENS: int = 200  # responses should be concise
```

**Step 2 — Add openai to requirements.txt**

```
openai==1.30.0
```

**Step 3 — Rewrite generate_response with the full fallback chain**

The complete rewritten function:

```python
from typing import Optional, Tuple

def generate_response(
    intent: str,
    original_message: str,
    similar_solution: Optional[str] = None,
    sub_intent: Optional[str] = None,
    similar_quality_score: Optional[float] = None,
) -> Tuple[str, str]:
    """
    Generate a response using the priority fallback chain.
    
    Returns: (response_text, source_label)
    source_label is one of: 'similarity', 'openai', 'template', 'fallback'
    """
    
    # PRIORITY 1: High-quality similarity match
    # Only reuse if the matched ticket has good feedback OR no quality data yet
    if similar_solution and similar_solution.strip():
        quality_ok = similar_quality_score is None or similar_quality_score >= 0.6
        if quality_ok:
            clean = similar_solution.strip()[:500]
            return (
                f"I understand you're experiencing an issue. Based on a similar case, here's what helped: {clean}",
                "similarity"
            )
    
    # PRIORITY 2: OpenAI (if configured)
    from app.core.config import settings
    if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        try:
            response_text = _call_openai(intent, sub_intent, original_message)
            if response_text:
                return (response_text, "openai")
        except Exception:
            pass  # Silently fall through to template — never surface OpenAI errors
    
    # PRIORITY 3: Static template with sub-intent routing
    try:
        template_response = _select_template_with_sub_intent(intent, original_message, sub_intent)
        if template_response:
            return (template_response, "template")
    except Exception:
        pass
    
    # PRIORITY 4: Absolute fallback
    return (
        "Thank you for contacting us. A support agent will review your request and respond within 24 hours.",
        "fallback"
    )


def _call_openai(intent: str, sub_intent: Optional[str], message: str) -> Optional[str]:
    """Call OpenAI API with a timeout. Returns None on any failure."""
    from openai import OpenAI
    from app.core.config import settings
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT)
    
    context = f"{intent.replace('_', ' ')}"
    if sub_intent:
        context += f" ({sub_intent.replace('_', ' ')})"
    
    system_prompt = (
        "You are a helpful customer support agent for a SaaS product. "
        "Write a clear, specific 2-3 sentence response to the customer. "
        "Give actionable steps. Do not use filler phrases like 'I understand your frustration'. "
        "Be direct and helpful."
    )
    
    user_prompt = (
        f"Customer issue type: {context}\n"
        f"Customer message: {message}\n\n"
        "Write a support response:"
    )
    
    result = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=settings.OPENAI_MAX_TOKENS,
        temperature=0.4,
    )
    
    return result.choices[0].message.content.strip()
```

**Step 4 — Add response_source to Ticket model**

In `app/models/ticket.py`:

```python
response_source = Column(
    String,
    nullable=True,
    doc="Which path generated the response: similarity, openai, template, or fallback",
)
```

**Step 5 — Update the pipeline to unpack the tuple**

In `app/api/tickets.py`, `_run_ticket_automation`, update the generate_response call:

```python
response_text, response_source = generate_response(
    intent,
    ticket.message,
    similar_solution,
    sub_intent=ticket.sub_intent,
    similar_quality_score=None,  # Task 5 will fill this in
)
ticket.response = response_text
ticket.response_source = response_source
```

**Step 6 — Update TicketResponse schema**

```python
response_source: Optional[str] = None
```

### Windsurf Prompt

```
I need to wire OpenAI into the SRS response generator with a proper fallback chain.
The system must never fail if OpenAI is unavailable. Here are all the changes:

FILE 1 — app/core/config.py
Add to the Settings class after OPENAI_API_KEY:
  OPENAI_MODEL: str = "gpt-4o-mini"
  OPENAI_TIMEOUT: int = 8
  OPENAI_MAX_TOKENS: int = 200

FILE 2 — requirements.txt
Add: openai==1.30.0

FILE 3 — app/models/ticket.py
Add column after the response column:
  response_source = Column(String, nullable=True, 
    doc="Which path generated the response: similarity, openai, template, or fallback")

FILE 4 — app/services/response_generator.py
Rewrite generate_response() completely. New signature:
  def generate_response(intent, original_message, similar_solution=None, 
                        sub_intent=None, similar_quality_score=None) -> tuple[str, str]

It must return a tuple of (response_text, source_label) where source_label is one of:
"similarity", "openai", "template", "fallback"

Implement this exact priority chain:
1. If similar_solution exists and is not empty, and (similar_quality_score is None OR 
   >= 0.6): sanitize to 500 chars, return it with source "similarity"
2. If settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY is set: call a 
   private _call_openai(intent, sub_intent, message) function wrapped in try/except. 
   On success return (response_text, "openai"). On ANY exception, silently continue.
3. Call _select_template_with_sub_intent(intent, original_message, sub_intent) — this 
   is the function from Task 2 renamed to accept sub_intent. Return with source "template".
4. Return the hardcoded fallback string with source "fallback".

The _call_openai function:
- Creates an OpenAI client with the API key and timeout from settings
- Sends a system prompt: "You are a helpful customer support agent for a SaaS product. 
  Write a clear, specific 2-3 sentence response to the customer. Give actionable steps. 
  Do not use filler phrases like 'I understand your frustration'. Be direct and helpful."
- Sends a user prompt that includes the intent, sub_intent, and customer message
- Uses model=settings.OPENAI_MODEL, max_tokens=settings.OPENAI_MAX_TOKENS, temperature=0.4
- Returns the response text or None if anything goes wrong

FILE 5 — app/api/tickets.py
In _run_ticket_automation, update the generate_response call to:
- Unpack the tuple: response_text, response_source = generate_response(...)
- Pass sub_intent=ticket.sub_intent
- Pass similar_quality_score=None (will be wired in Task 5)
- Set ticket.response = response_text
- Set ticket.response_source = response_source

FILE 6 — app/schemas/ticket.py
Add to TicketResponse: response_source: Optional[str] = None

FILE 7 — app/services/resolver.py and app/services/ai_service.py
Update any imports or calls to generate_response to handle the new tuple return type.

After changes, write two tests in tests/test_response_generator.py:
1. Mock openai to fail with an exception — verify the function returns a template 
   response (not an error) with source "template"
2. Mock openai to return "Test OpenAI response" — verify the function returns that 
   text with source "openai"

Do NOT run alembic. Just update the model definition.
```

---

## Task 5 — Feedback Quality Scores
### SRS Phase 5 · Owner: Prajwal

---

## What This Task Is About

Every resolved ticket can receive feedback with a rating from 1 to 5 and a `resolved` boolean. This data is stored. Nothing uses it.

The similarity search currently picks the ticket with the highest cosine similarity score. But a 0.80 similarity match that users rated 2/5 is a worse choice than a 0.72 similarity match that users consistently rated 5/5. Quality data should influence which past solutions get reused.

This task closes that loop in two directions:

1. **Pipeline direction** — when a new ticket comes in, the similarity search now knows which past tickets were rated well and prefers them
2. **Analytics direction** — the `feedback_analyzer` worker already reads the database and produces a JSON report, but it currently ignores `quality_score`. After this task is done, it needs to also report average quality scores per intent so you can see which intent categories have the weakest responses

---

## Files Changed in This Task

| File | What Changes |
|------|-------------|
| `app/models/ticket.py` | Add `quality_score` Float column |
| `app/api/feedback.py` | Compute and save `quality_score` after feedback is submitted |
| `app/api/tickets.py` | Pass `quality_score` through resolved_tickets_data → similarity result → generate_response |
| `app/services/similarity_search.py` | Include `quality_score` in the return dict |
| `app/api/admin.py` | Add quality metrics section to GET /admin/metrics |
| `workers/feedback_analyzer.py` | Add `quality_score` to fetch query and include avg quality per intent in analysis output |

---

## Step 1 — Add quality_score Column to Ticket Model

In `app/models/ticket.py`, add after the `response_source` column (which was added in Task 4):

```python
quality_score = Column(
    Float,
    nullable=True,
    doc="Normalized quality score from feedback (0.0-1.0). None if no feedback received yet.",
)
```

The value is `None` until the ticket receives feedback. Once feedback is submitted, it gets computed and stored here permanently. It does not update if feedback is edited because the current feedback model enforces one-feedback-per-ticket.

---

## Step 2 — Compute quality_score When Feedback Is Submitted

Open `app/api/feedback.py`. In the `create_feedback` endpoint, the ticket variable is already fetched earlier in the function to validate it exists. After the `db.commit()` that saves the feedback record, add:

```python
# Compute and persist quality score on the ticket
# base_score: rating 1-5 normalizes to 0.2-1.0
# resolution_boost: +0.1 if user confirms resolved, -0.1 if not
base_score = feedback_data.rating / 5.0
resolution_boost = 0.1 if feedback_data.resolved else -0.1
ticket.quality_score = max(0.0, min(1.0, base_score + resolution_boost))
db.commit()
```

The math:
- Rating 5, resolved True → 1.0 + 0.1 = 1.1, capped to **1.0**
- Rating 5, resolved False → 1.0 - 0.1 = **0.9**
- Rating 3, resolved True → 0.6 + 0.1 = **0.7**
- Rating 1, resolved False → 0.2 - 0.1 = **0.1**
- Rating 1, resolved True → 0.2 + 0.1 = **0.3**

---

## Step 3 — Pass quality_score Through the Pipeline

There are three places in `app/api/tickets.py` to update, all inside `_run_ticket_automation`.

**In the resolved_tickets_data list construction**, add `quality_score` to each dict:

```python
resolved_tickets_data.append({
    "message": resolved_ticket.message,
    "response": resolved_ticket.response,
    "quality_score": resolved_ticket.quality_score,  # add this line
})
```

**After `find_similar_ticket` returns**, extract the quality score:

```python
similar_quality_score = similar_result.get("quality_score") if similar_result else None
```

**In the `generate_response` call**, pass it through (Task 4 already added the parameter, it was set to None — now wire it for real):

```python
response_text, response_source = generate_response(
    intent,
    ticket.message,
    similar_solution,
    sub_intent=ticket.sub_intent,
    similar_quality_score=similar_quality_score,  # was None before, now real
)
```

---

## Step 4 — Include quality_score in Similarity Search Return

In `app/services/similarity_search.py`, at the end of `find_similar_ticket`, the return dict currently is:

```python
return {
    "matched_text": best_match,
    "similarity_score": round(best_similarity, 3),
    "ticket": best_ticket
}
```

Add the quality score:

```python
return {
    "matched_text": best_match,
    "similarity_score": round(best_similarity, 3),
    "ticket": best_ticket,
    "quality_score": best_ticket.get("quality_score"),  # None if ticket has no feedback yet
}
```

---

## Step 5 — Add Quality Metrics to Admin Endpoint

In `app/api/admin.py`, in `get_metrics()`, add a `"quality"` key to the `metrics` dict before the return:

```python
# Quality metrics
low_quality_tickets = db.query(Ticket).filter(
    Ticket.quality_score != None,
    Ticket.quality_score < 0.5
).count()

quality_by_intent = (
    db.query(Ticket.intent, func.avg(Ticket.quality_score))
    .filter(Ticket.quality_score != None)
    .group_by(Ticket.intent)
    .all()
)

metrics["quality"] = {
    "low_quality_count": low_quality_tickets,
    "by_intent": {
        intent: round(float(score), 2)
        for intent, score in quality_by_intent
        if intent  # skip rows where intent is None
    }
}
```

This lets the admin dashboard see which intents are getting the worst feedback scores — the most actionable data from this entire task.

---

## Step 6 — Update feedback_analyzer Worker

This is the new step that was missing from the original task description.

The `workers/feedback_analyzer.py` worker is already fully implemented. It reads all feedback records, joins them with tickets, and produces a JSON report with per-intent breakdowns. But it currently does not read `quality_score` from the tickets table, and its output does not report it. After this task adds `quality_score` to the Ticket model and computes it on feedback submission, the worker should include it.

**In `fetch_feedback_with_tickets`**, add `quality_score` to the returned dict for each row. The function currently does a join between `Feedback` and `Ticket`. Update the return dict:

```python
return [
    {
        "feedback_id": fb.id,
        "ticket_id": fb.ticket_id,
        "rating": fb.rating,
        "resolved": fb.resolved,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
        "intent": ticket.intent,
        "ticket_status": ticket.status,
        "quality_score": ticket.quality_score,  # add this line
    }
    for fb, ticket in rows
]
```

**In `analyze_feedback`**, add average quality score to the overall summary and to the per-intent breakdown.

In the overall summary section, add:

```python
all_quality_scores = [r["quality_score"] for r in records if r.get("quality_score") is not None]
```

And include it in the return dict:

```python
"average_quality_score": _safe_avg(all_quality_scores),
```

In the per-intent aggregation loop, add quality scores to the per-intent tracking:

```python
by_intent: Dict[str, Dict] = defaultdict(lambda: {"ratings": [], "resolved": [], "quality_scores": []})
for rec in records:
    intent_key = rec.get("intent") or "unknown"
    if rec["rating"] is not None:
        by_intent[intent_key]["ratings"].append(rec["rating"])
    if rec["resolved"] is not None:
        by_intent[intent_key]["resolved"].append(rec["resolved"])
    if rec.get("quality_score") is not None:  # add this block
        by_intent[intent_key]["quality_scores"].append(rec["quality_score"])
```

And include it in the `intent_summary` dict:

```python
intent_summary = {
    intent: {
        "count": len(vals["ratings"]),
        "average_rating": _safe_avg(vals["ratings"]),
        "resolution_rate": round(sum(vals["resolved"]) / len(vals["resolved"]), 3)
            if vals["resolved"] else 0.0,
        "average_quality_score": _safe_avg(vals["quality_scores"]),  # add this line
    }
    for intent, vals in by_intent.items()
}
```

The final worker output for a typical intent will now look like:

```json
{
  "total_feedback": 42,
  "average_rating": 3.8,
  "average_quality_score": 0.71,
  "resolution_rate": 0.76,
  "by_intent": {
    "login_issue": {
      "count": 18,
      "average_rating": 4.1,
      "resolution_rate": 0.83,
      "average_quality_score": 0.78
    },
    "payment_issue": {
      "count": 12,
      "average_rating": 3.2,
      "resolution_rate": 0.58,
      "average_quality_score": 0.54
    }
  }
}
```

This tells you immediately that `payment_issue` responses are underperforming — exactly the kind of signal that feeds back into Task 2's template rewrites.

---

## Windsurf Prompt

```
I need to implement feedback quality scores in the SRS project. This involves 6 files.
Read each instruction carefully before making changes.

FILE 1 — app/models/ticket.py
Add this column after the response_source column:
  quality_score = Column(Float, nullable=True,
    doc="Normalized quality score from feedback (0.0-1.0). None if no feedback yet.")

FILE 2 — app/api/feedback.py
In create_feedback(), the ticket variable is already fetched earlier in the function to 
validate existence. After the db.commit() that saves the feedback record, add code to 
compute quality_score on that same ticket object:
  base_score = feedback_data.rating / 5.0
  resolution_boost = 0.1 if feedback_data.resolved else -0.1
  ticket.quality_score = max(0.0, min(1.0, base_score + resolution_boost))
  db.commit()
Note: the ticket variable was fetched as:
  ticket = db.query(Ticket).filter(Ticket.id == feedback_data.ticket_id).first()
Use that same variable, do not query again.

FILE 3 — app/api/tickets.py
In _run_ticket_automation(), make three changes:
1. In the loop that builds resolved_tickets_data, add to each dict:
   "quality_score": resolved_ticket.quality_score
2. After find_similar_ticket() returns, extract:
   similar_quality_score = similar_result.get("quality_score") if similar_result else None
3. In the generate_response() call, change similar_quality_score=None to:
   similar_quality_score=similar_quality_score

FILE 4 — app/services/similarity_search.py
In find_similar_ticket(), in the return dict where best match is returned, add:
  "quality_score": best_ticket.get("quality_score")

FILE 5 — app/api/admin.py
In get_metrics(), before the return statement, add a "quality" key to the metrics dict:
  low_quality_tickets = count of Ticket rows where quality_score IS NOT NULL and < 0.5
  quality_by_intent = db query grouping by Ticket.intent, averaging Ticket.quality_score,
    filtered to rows where quality_score IS NOT NULL
  metrics["quality"] = {
    "low_quality_count": low_quality_tickets,
    "by_intent": {intent: round(float(score), 2) for intent, score in query_result if intent}
  }
Use func.avg() from sqlalchemy for the average.

FILE 6 — workers/feedback_analyzer.py
This file is already implemented but needs two updates.

In fetch_feedback_with_tickets(), add "quality_score": ticket.quality_score to the 
returned dict for each row.

In analyze_feedback(), make these changes:
1. Change the defaultdict lambda in the by_intent section from:
     lambda: {"ratings": [], "resolved": []}
   to:
     lambda: {"ratings": [], "resolved": [], "quality_scores": []}
2. In the loop that populates by_intent, add:
     if rec.get("quality_score") is not None:
         by_intent[intent_key]["quality_scores"].append(rec["quality_score"])
3. In intent_summary, add to each intent's dict:
     "average_quality_score": _safe_avg(vals["quality_scores"])
4. Before the return statement, compute:
     all_quality_scores = [r["quality_score"] for r in records if r.get("quality_score") is not None]
5. Add to the top-level return dict:
     "average_quality_score": _safe_avg(all_quality_scores)

After all changes, write these tests in tests/test_feedback_api.py:

TEST 1 — test_quality_score_high_rating:
  Create a ticket with status="auto_resolved"
  POST /feedback with rating=5, resolved=True for that ticket
  Query the ticket directly from the DB
  Assert ticket.quality_score == 1.0  (5/5 + 0.1 = 1.1, capped to 1.0)

TEST 2 — test_quality_score_low_rating:
  Create a ticket with status="auto_resolved"
  POST /feedback with rating=1, resolved=False for that ticket
  Query the ticket directly from the DB
  Assert ticket.quality_score == 0.1  (1/5 - 0.1 = 0.1)

TEST 3 — test_quality_score_none_before_feedback:
  Create a ticket with status="auto_resolved"
  Query it directly without submitting any feedback
  Assert ticket.quality_score is None

Write these tests in tests/test_worker_feedback_analyzer.py:

TEST 4 — test_analyze_feedback_includes_quality_score_in_output:
  Create records list with _make_record() calls, adding quality_score key to each:
    [_make_record(rating=5, resolved=True) | {"quality_score": 0.9},
     _make_record(rating=3, resolved=False) | {"quality_score": 0.5}]
  Call analyze_feedback(records)
  Assert "average_quality_score" is in the result
  Assert result["by_intent"]["login_issue"]["average_quality_score"] is not None

TEST 5 — test_fetch_feedback_includes_quality_score:
  Use db_session fixture
  Create a ticket with a quality_score set (e.g., 0.8)
  Create feedback for that ticket
  Call fetch_feedback_with_tickets(db_session)
  Assert "quality_score" is in the first result
  Assert result[0]["quality_score"] == 0.8

Do NOT run alembic. Just update the model definition — the column will be created on 
next startup in development. Do NOT modify any other files beyond these 6.
```

---

## Task 6 — Add user_id to Tickets + Ownership

**This is a data model change. The system currently has no concept of ticket ownership.**

### The Problem in Detail

Every ticket is anonymous. Any user can call `GET /tickets/` and see every ticket in the system. There is no concept of "my tickets". Agents have no way to see which tickets belong to which user. The JWT infrastructure is already there — user ID is in the token — but it is never used to tag tickets.

### Exactly What to Change

**Step 1 — Add user_id to Ticket model**

```python
user_id = Column(
    Integer,
    ForeignKey('users.id'),
    nullable=True,  # nullable because existing tickets have no owner
    doc="ID of the user who submitted this ticket. Null for tickets submitted without auth.",
)

# Add relationship
user = relationship("User", foreign_keys=[user_id])
```

**Step 2 — Set user_id on ticket creation**

In `app/api/tickets.py`, make authentication optional on `POST /tickets`. The endpoint currently has no auth dependency — keep it optional so unauthenticated users can still submit tickets:

```python
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.auth import get_current_user
from fastapi.security import OAuth2PasswordBearer

# Optional auth — does not fail if no token provided
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional),
) -> TicketResponse:
    # Extract user_id from token if present
    user_id = None
    if token:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            user_id = int(payload.get("sub", 0)) or None
        except Exception:
            pass  # Invalid token — treat as unauthenticated
    
    ticket = Ticket(message=ticket_data.message, status="open", user_id=user_id)
    # ... rest of the function unchanged
```

**Step 3 — Filter GET /tickets by user when authenticated**

Update `list_tickets` to accept optional auth and filter:

```python
@router.get("/", response_model=TicketList)
def list_tickets(
    ticket_status: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional),
) -> TicketList:
    query = db.query(Ticket)
    
    # If authenticated, only show the user's own tickets
    if token:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            user_id = int(payload.get("sub", 0))
            role = payload.get("role", "user")
            if role not in ("admin", "agent"):
                query = query.filter(Ticket.user_id == user_id)
        except Exception:
            pass
    
    if ticket_status:
        query = query.filter(Ticket.status == ticket_status)
    
    tickets = query.order_by(Ticket.created_at.desc()).all()
    return TicketList(tickets=[TicketResponse.model_validate(t) for t in tickets])
```

**Step 4 — Add user_id to TicketResponse schema**

```python
user_id: Optional[int] = None
```

### Windsurf Prompt

```
I need to add ticket ownership to the SRS system. Tickets should be linked to the user 
who submitted them when a JWT token is provided. The endpoint must remain accessible 
to unauthenticated users (the token is optional).

FILE 1 — app/models/ticket.py
Add after the existing columns:
  user_id = Column(Integer, ForeignKey('users.id'), nullable=True,
    doc="ID of the submitting user. Null for unauthenticated submissions.")
Add relationship:
  user = relationship("User", foreign_keys=[user_id])

FILE 2 — app/api/tickets.py
Create an optional OAuth2 scheme at the module level:
  from fastapi.security import OAuth2PasswordBearer
  oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

Update the create_ticket endpoint signature to add:
  token: Optional[str] = Depends(oauth2_scheme_optional)

Before creating the Ticket object, extract user_id:
  user_id = None
  if token:
    try:
      payload = decode_token(token)
      user_id = int(payload.get("sub") or 0) or None
    except Exception:
      pass

Pass user_id=user_id to the Ticket constructor.

Update the list_tickets endpoint similarly — add optional token parameter.
After building the base query, if a valid token is present and the role is not 
"admin" or "agent", add .filter(Ticket.user_id == user_id) to restrict results 
to the authenticated user's tickets.

FILE 3 — app/schemas/ticket.py
Add to TicketResponse: user_id: Optional[int] = None

After changes, write tests that verify:
1. POST /tickets without a token creates a ticket with user_id=None
2. POST /tickets with a valid token creates a ticket with the correct user_id
3. GET /tickets with a valid user token only returns that user's tickets
4. GET /tickets with an admin token returns all tickets
```

---

## Task 7 — Agent Assignment + Ticket Close

**Gives agents something to do with escalated tickets.**

### The Problem in Detail

Escalated tickets go nowhere. There is a `role="agent"` in the system but no endpoints for agents to act. An agent cannot claim a ticket, cannot mark it resolved, cannot see which tickets are assigned to them. The admin metrics show escalation counts but agents have no workflow.

### Exactly What to Change

**Step 1 — Add assigned_agent_id to Ticket model**

```python
assigned_agent_id = Column(
    Integer,
    ForeignKey('users.id'),
    nullable=True,
    doc="ID of the agent assigned to handle this ticket when escalated.",
)
assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])
```

**Step 2 — Add POST /tickets/{id}/assign endpoint**

```python
@router.post("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketResponse:
    """Assign an escalated ticket to the current agent or admin."""
    if current_user.role not in ("agent", "admin"):
        raise HTTPException(status_code=403, detail="Only agents and admins can assign tickets")
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    if ticket.status != "escalated":
        raise HTTPException(status_code=400, detail="Only escalated tickets can be assigned")
    
    ticket.assigned_agent_id = current_user.id
    db.commit()
    db.refresh(ticket)
    return TicketResponse.model_validate(ticket)
```

**Step 3 — Add POST /tickets/{id}/close endpoint**

```python
@router.post("/{ticket_id}/close", response_model=TicketResponse)
def close_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketResponse:
    """Mark a ticket as closed after human resolution."""
    if current_user.role not in ("agent", "admin"):
        raise HTTPException(status_code=403, detail="Only agents and admins can close tickets")
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    if ticket.status not in ("escalated", "auto_resolved"):
        raise HTTPException(status_code=400, detail="Ticket must be escalated or auto_resolved to close")
    
    ticket.status = "closed"
    db.commit()
    db.refresh(ticket)
    return TicketResponse.model_validate(ticket)
```

**Step 4 — Add unassigned escalated count to admin metrics**

```python
unassigned_escalated = db.query(Ticket).filter(
    Ticket.status == "escalated",
    Ticket.assigned_agent_id == None
).count()
metrics["tickets"]["unassigned_escalated"] = unassigned_escalated
```

**Step 5 — Add assigned_agent_id to TicketResponse schema**

```python
assigned_agent_id: Optional[int] = None
```

### Windsurf Prompt

```
I need to add agent assignment and ticket close endpoints to the SRS tickets API.

FILE 1 — app/models/ticket.py
Add after user_id:
  assigned_agent_id = Column(Integer, ForeignKey('users.id'), nullable=True,
    doc="Agent assigned to handle this ticket.")
  assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])

FILE 2 — app/api/tickets.py
Add two new endpoints. Both require authentication via Depends(get_current_user) and 
both check that the current user's role is "agent" or "admin", returning 403 otherwise.

Endpoint 1: POST /{ticket_id}/assign
- Fetches ticket by ID, returns 404 if not found
- Returns 400 if ticket.status != "escalated" with message "Only escalated tickets can be assigned"
- Sets ticket.assigned_agent_id = current_user.id
- Commits and returns the updated TicketResponse

Endpoint 2: POST /{ticket_id}/close  
- Fetches ticket by ID, returns 404 if not found
- Returns 400 if ticket.status not in ("escalated", "auto_resolved")
- Sets ticket.status = "closed"
- Commits and returns the updated TicketResponse

FILE 3 — app/api/admin.py
In get_metrics(), add to the tickets section of the metrics dict:
  "unassigned_escalated": count of tickets where status="escalated" and 
  assigned_agent_id IS NULL

FILE 4 — app/schemas/ticket.py
Add to TicketResponse: assigned_agent_id: Optional[int] = None

After all changes, write tests that verify:
1. An agent can assign an escalated ticket to themselves
2. A regular user gets 403 when trying to assign a ticket
3. Trying to assign an auto_resolved ticket returns 400
4. An agent can close an escalated ticket
5. The closed ticket has status "closed" in the response
```

---

## Task 8 — Alembic Migrations + Neon PostgreSQL

**This converts the project from a local SQLite demo to a production-ready database setup.**

### The Problem in Detail

The project uses `Base.metadata.create_all()` on startup. This works for the initial table creation but cannot add columns to existing tables. Every new column added in Tasks 2–7 (sub_intent, quality_score, response_source, user_id, assigned_agent_id) has been added to model definitions only. On a fresh database they will be created. On an existing database they will be missing, causing runtime errors.

Alembic is already in the project's README and requirements but the `alembic/` directory and `alembic.ini` do not exist. This task creates them and writes the migration files.

### Exactly What to Change

**Step 1 — Initialize Alembic**

```bash
cd your-project-root
alembic init alembic
```

**Step 2 — Configure alembic.ini and env.py**

In `alembic.ini`, set:
```
sqlalchemy.url = sqlite:///./support.db
```

In `alembic/env.py`, import the app's Base and configure target_metadata:
```python
from app.db.session import Base
from app.models import user, ticket, feedback  # import models to register them

target_metadata = Base.metadata
```

Also update `run_migrations_online()` to read DATABASE_URL from settings:
```python
from app.core.config import settings
configuration = config.get_section(config.config_ini_section)
configuration["sqlalchemy.url"] = settings.DATABASE_URL
```

**Step 3 — Create the initial migration**

```bash
alembic revision --autogenerate -m "initial_tables"
alembic upgrade head
```

**Step 4 — Create Phase 5 migration**

```bash
alembic revision --autogenerate -m "phase5_columns"
```

Verify the generated migration includes all the new columns from Tasks 2–7. It should add: `sub_intent`, `quality_score`, `response_source`, `user_id`, `assigned_agent_id` to the tickets table.

**Step 5 — Switch to Neon PostgreSQL**

1. Create a project at neon.tech (free tier)
2. Copy the connection string which looks like: `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`
3. In `.env`, set `DATABASE_URL=postgresql://...`
4. Run `alembic upgrade head` — this creates all tables in Neon
5. Start the server and verify it connects: `uvicorn app.main:app --reload`

**Step 6 — Update .env.example**

```
# Development (SQLite — no setup needed)
DATABASE_URL=sqlite:///./support.db

# Production (PostgreSQL via Neon)
# DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

### Windsurf Prompt

```
I need to set up Alembic for database migrations in the SRS project. The project 
currently uses Base.metadata.create_all() which cannot add columns to existing tables.

STEP 1 — Initialize Alembic
Run: alembic init alembic
This creates alembic.ini and the alembic/ directory.

STEP 2 — Configure alembic/env.py
Replace the target_metadata line. Import:
  from app.db.session import Base
  from app.models import user, ticket, feedback
Set: target_metadata = Base.metadata

In the run_migrations_online() function, before creating the engine, add:
  from app.core.config import settings
  configuration = config.get_section(config.config_ini_section)
  configuration["sqlalchemy.url"] = settings.DATABASE_URL
  connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

STEP 3 — Create initial migration
Run: alembic revision --autogenerate -m "initial_tables"
Then: alembic upgrade head
Verify the alembic_version table exists in the database.

STEP 4 — Create Phase 5 migration  
The following columns were added to the Ticket model in Phase 5 but have not been 
migrated: sub_intent (String nullable), quality_score (Float nullable), response_source 
(String nullable), user_id (Integer nullable FK to users.id), assigned_agent_id 
(Integer nullable FK to users.id).

Run: alembic revision --autogenerate -m "phase5_columns"
Review the generated migration file and verify it adds all 5 columns.
Run: alembic upgrade head

STEP 5 — Verify the migrations work on a clean database
Delete support.db, run alembic upgrade head, and verify all tables and columns exist 
using: python -c "from app.db.session import engine; from sqlalchemy import inspect; 
print(inspect(engine).get_columns('tickets'))"

STEP 6 — Update .env.example
Add a comment showing both SQLite and PostgreSQL DATABASE_URL formats. Keep the default 
as SQLite for development.

After completing this task, the project should work with both SQLite (by default) and 
PostgreSQL (by setting DATABASE_URL in .env). Do not change any application code — only 
migration and configuration files.
```

---

## Task 9 — Redis Caching for Similarity Search

**Optional but high value. Do this after Task 8 confirms the DB is stable.**

### The Problem in Detail

Every ticket creation runs the full similarity search: query the last 50 resolved tickets from the database, vectorize all of them, compute cosine similarity scores for all of them, find the best match. If 100 users submit tickets in the same minute, this runs 100 times pulling largely the same 50 resolved tickets each time.

`REDIS_URL` is already defined in `Settings` and defaults to `None`. Caching the similarity result per message hash would eliminate redundant DB queries during high-traffic periods. The cache key needs to be the hash of the message so similar (but not identical) messages get different cache entries.

### Exactly What to Change

**Step 1 — Add redis to requirements.txt**

```
redis==5.0.4
```

**Step 2 — Add cache helper to similarity_search.py**

```python
import hashlib
import json
from typing import Optional

def _get_cache_client():
    """Return a Redis client if REDIS_URL is configured, else None."""
    from app.core.config import settings
    if not settings.REDIS_URL:
        return None
    try:
        import redis
        return redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1)
    except Exception:
        return None

def _cache_key(message: str) -> str:
    """Generate a cache key from the message content."""
    return f"srs:similarity:{hashlib.sha256(message.encode()).hexdigest()[:16]}"
```

**Step 3 — Wrap find_similar_ticket with cache logic**

At the start of `find_similar_ticket`, before any DB work:

```python
# Try cache first
cache = _get_cache_client()
if cache:
    key = _cache_key(new_message)
    try:
        cached = cache.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass  # Cache miss or error — continue normally
```

At the end, before returning the result:

```python
# Cache the result for 5 minutes
if cache and result is not None:
    try:
        cache.setex(_cache_key(new_message), 300, json.dumps(result))
    except Exception:
        pass  # Cache write failure is not a problem
```

Also cache `None` results (no match found) to avoid repeated DB queries:

```python
if cache:
    try:
        cache.setex(_cache_key(new_message), 120, json.dumps(None))
    except Exception:
        pass
return None
```

### Windsurf Prompt

```
I need to add optional Redis caching to the similarity search in 
app/services/similarity_search.py. Redis must be completely optional — if REDIS_URL is 
not set or Redis is unavailable, the function must work exactly as before with no errors.

FILE 1 — requirements.txt
Add: redis==5.0.4

FILE 2 — app/services/similarity_search.py
Add two helper functions at the top of the file (after imports):

_get_cache_client(): reads settings.REDIS_URL, returns a redis.from_url client with 
decode_responses=True and socket_timeout=1, or returns None if REDIS_URL is not set 
or if any exception occurs during client creation.

_cache_key(message: str) -> str: returns "srs:similarity:" + first 16 chars of the 
sha256 hex digest of the message encoded as utf-8.

In find_similar_ticket(), add cache logic at two points:

At the start (after input validation, before the DB query section):
  cache = _get_cache_client()
  if cache:
    key = _cache_key(new_message)
    try:
      cached = cache.get(key)
      if cached is not None:
        return json.loads(cached)
    except Exception:
      pass

At the end, just before each return statement:
  if cache:
    try: cache.setex(key, 300, json.dumps(result_or_none))
    except Exception: pass

Use TTL of 300 seconds for matched results and 120 seconds for None results.
Use json.dumps/loads for serialization. The result dict contains only strings and 
floats so it is JSON-safe.

After changes, write a test that mocks redis.from_url to return a mock client, calls 
find_similar_ticket twice with the same message, and verifies that the DB query (via 
mock) is only called once — the second call hits the cache.
```

---

## Task 10 — Rate Limiting + Test Suite Updates

**Final task. Enforce the config value that exists but does nothing, and write all the missing tests.**

### Rate Limiting

`RATE_LIMIT_PER_MINUTE: int = 60` is in `Settings` but nothing in the code enforces it. The library `slowapi` integrates directly with FastAPI.

**Step 1** — Add to requirements.txt: `slowapi==0.1.9`

**Step 2** — In `app/main.py`, add to `create_app()`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

**Step 3** — In `app/api/tickets.py`, add the decorator to `create_ticket`:

```python
from app.main import limiter  # import from main where limiter is defined
from app.core.config import settings

@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
def create_ticket(request: Request, ticket_data: TicketCreate, db: Session = Depends(get_db), ...):
```

Note: `slowapi` requires the `request: Request` parameter to be present in the function signature.

### Test Suite Updates

Every new behavior added in Tasks 1–9 needs a corresponding test. This is a checklist:

| Test | File | What to verify |
|------|------|----------------|
| Template variation | test_response_generator.py | "I forgot my password" gets reset template, "account locked" gets lockout template |
| Sub-intent in classifier | test_classifier.py | "forgot my password" → sub_intent="password_reset" |
| OpenAI fallback | test_response_generator.py | mock OpenAI to fail → still returns template response |
| OpenAI success | test_response_generator.py | mock OpenAI → returns "openai" as source |
| Quality score on feedback | test_feedback_api.py | rating=5, resolved=True → quality_score=1.0 |
| Ticket ownership | test_tickets_api.py | authenticated POST sets user_id; GET filters by user |
| Agent assign | test_tickets_api.py | agent can assign escalated ticket, regular user gets 403 |
| Ticket close | test_tickets_api.py | agent can close escalated ticket, result is "closed" |
| Rate limit | test_tickets_api.py | 61 POSTs in sequence → last one returns 429 |
| Cache hit | test_similarity_search.py | second call with same message uses cache, DB not queried twice |

### Windsurf Prompt

```
I need to implement rate limiting on POST /tickets and write tests for all Phase 5 
features. Do the rate limiting first, then the tests.

RATE LIMITING:

FILE 1 — requirements.txt
Add: slowapi==0.1.9

FILE 2 — app/main.py
In create_app():
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address
  from slowapi.errors import RateLimitExceeded
  from slowapi.middleware import SlowAPIMiddleware
  
  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  app.add_middleware(SlowAPIMiddleware)
  
Make the limiter accessible by putting it at module level (before create_app).

FILE 3 — app/api/tickets.py
Import: from slowapi import Limiter; from fastapi import Request
Add @limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute") decorator above 
@router.post on create_ticket.
Add request: Request as the first parameter of create_ticket.

TEST UPDATES:

Write the following tests. For each test, use the appropriate existing test file and 
follow the same fixture patterns already in those files.

tests/test_response_generator.py — add:
1. test_login_forgot_password_gets_reset_template: "I forgot my password" with intent 
   "login_issue" → response contains "Forgot Password"
2. test_login_locked_gets_lockout_template: "my account is locked" → contains "locked"
3. test_openai_failure_falls_back_to_template: mock openai.OpenAI to raise an exception, 
   verify response is still a string and source is "template"
4. test_openai_success_returns_openai_source: patch settings.AI_PROVIDER="openai" and 
   settings.OPENAI_API_KEY="test", mock openai client to return "Test response", 
   verify source is "openai"

tests/test_classifier.py — add:
5. test_sub_intent_password_reset: "I forgot my password" → sub_intent="password_reset"
6. test_sub_intent_account_locked: "my account is locked" → sub_intent="account_locked"  
7. test_sub_intent_none_for_unknown: "xyz random text" → sub_intent=None

tests/test_feedback_api.py — add:
8. test_quality_score_high_rating: rate 5 with resolved=True → ticket.quality_score == 1.0
9. test_quality_score_low_rating: rate 1 with resolved=False → ticket.quality_score == 0.1

tests/test_tickets_api.py — add:
10. test_authenticated_ticket_sets_user_id: POST /tickets with valid JWT → ticket.user_id matches token sub
11. test_unauthenticated_ticket_has_no_user_id: POST /tickets without token → ticket.user_id is None
12. test_agent_can_assign_escalated_ticket: create agent user, get token, POST assign → 200
13. test_user_cannot_assign_ticket: regular user token, POST assign → 403
14. test_agent_can_close_ticket: create agent user, POST close on escalated ticket → status "closed"
15. test_rate_limit_returns_429: send RATE_LIMIT_PER_MINUTE + 1 requests → last returns 429

Run all tests after: pytest -v --tb=short
All should pass. If any existing tests break due to the tuple return from 
generate_response, update them to unpack the tuple.
```

---

## Summary

Ten tasks. All of them are improvements to things that already exist — no new systems from scratch.

The order matters because Tasks 3 and 4 depend on Task 2, Task 5 depends on Task 4, and Task 8 must come after all model changes are final. Tasks 9 and 10 are independent and can be done any time after Task 8.

```
Task 1 (bugs)
    ↓
Task 2 (templates) ──→ Task 3 (sub_intent) ──→ Task 4 (openai) ──→ Task 5 (quality)
                                                                           ↓
Task 6 (user_id) ──→ Task 7 (agent assign)                         Task 8 (alembic)
                                                                           ↓
                                                               Task 9 (redis) + Task 10 (rate limit + tests)
```

Each Windsurf prompt is self-contained — you can paste it directly without extra context. The prompts tell the AI exactly which files to touch, what to add, and what tests to write to verify it worked.