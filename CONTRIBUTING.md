# Contributing to SRS (Smart Resolution System)

Thanks for taking the time to contribute! This guide covers how to get set
up, the expectations for pull requests, and how the project is tested.

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## Getting Started

1. Fork the repo and clone your fork:
   ```bash
   git clone https://github.com/<your-username>/SRS.git
   cd SRS
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
3. Copy the environment template and fill in the required values:
   ```bash
   cp .env.example .env
   ```
4. Run the app locally:
   ```bash
   uvicorn app.main:app --reload
   ```

## Running the Test Suite

The full suite currently sits at 654 passing tests with 80% coverage — please
keep it green.

```bash
# Full suite
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# A single file or test
pytest tests/services/test_automation_unit.py -v
```

If you touch anything in the AI automation pipeline
(`app/services/ticket_service.py`, `classifier.py`, `decision_engine.py`,
`response_generator.py`), also re-run the standalone benchmark scripts and
mention any change in measured numbers in your PR description:

```bash
python eval_classifier.py
python load_test.py --url http://127.0.0.1:8000/tickets/ --n 150 --concurrency 10
```

## Branching & Commits

- Branch from `main`: `git checkout -b feat/short-description`
- Keep commits focused; write commit messages that explain *why*, not just
  *what*
- Rebase on `main` before opening a PR if your branch has drifted

## Pull Request Checklist

- [ ] Tests pass locally (`pytest`)
- [ ] New behavior has test coverage — no new untested code paths in the AI
      pipeline or auth logic
- [ ] No secrets, API keys, or tokens committed (check `.env` is gitignored)
- [ ] README / docstrings updated if public behavior changed
- [ ] If you renamed or moved a function, grep the test suite for the old
      name — mock `patch()` targets reference module paths directly and
      silently stop working if a function moves without the test being
      updated (this exact issue caused a real 15-test regression in this
      repo previously)

## Reporting Bugs

Open a GitHub issue with:
- What you expected vs. what happened
- Steps to reproduce
- Python version and OS

For security vulnerabilities, do **not** open a public issue — see
[SECURITY.md](SECURITY.md).

## Style

- Follow existing patterns in the module you're editing (service-layer
  functions live in `app/services/`, HTTP concerns stay in `app/api/`)
- Prefer explicit, readable code over cleverness — this is a system other
  people will need to safely extend
