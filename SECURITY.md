# Security Policy

## Supported Versions

This project is developed on a single rolling `main` branch. Only the latest
commit on `main` is supported with security fixes.

| Version | Supported |
|---------|-----------|
| `main`  | ✅ |
| Older commits / forks | ❌ |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report it privately by emailing **omyadao1706@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal repro is very helpful)
- Any relevant logs, stack traces, or PoC code

You should expect an initial response within a few days. Once a fix is
prepared, we'll credit you in the release notes unless you'd prefer to stay
anonymous.

## Scope

Examples of in-scope reports:

- Authentication / authorization bypass (e.g. accessing another user's
  tickets, privilege escalation between `user` / `agent` / `admin` roles)
- Injection vulnerabilities (SQL injection, etc.)
- Broken access control on any endpoint under `app/api/`
- Secrets or credentials exposed in logs, error responses, or committed to
  the repo
- Denial-of-service vectors beyond the existing rate limiting

Out of scope:

- Vulnerabilities requiring physical access to a user's device
- Social engineering
- Issues in third-party dependencies — please report those upstream, though
  we'd appreciate a heads-up so we can bump the pin

## Past Fixes

For transparency: a previous audit (PR #89/#90) found and fixed a real
access-control bug (CWE-284) where `GET /tickets` translated an
unauthenticated caller's `user_id == None` into a SQL `IS NULL` filter,
returning every ownerless ticket to anonymous requests. That kind of report
is exactly what this policy is for — thank you in advance for taking the
time to look.
