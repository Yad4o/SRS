"""
pytest configuration and shared fixtures.

Sets up test environment before any app imports.
Uses in-memory SQLite for database tests to isolate from development data.
"""
import os
import sys
from pathlib import Path

# Ensure this project's app is loaded (not a parent directory's)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Set test environment before any app modules are imported.
# Uses in-memory SQLite so tests don't touch the development database.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"
