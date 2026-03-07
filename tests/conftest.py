"""
pytest configuration and shared fixtures.

Sets up test environment before any app imports.
Uses file-based SQLite for database tests to ensure table persistence.
"""
import os
import sys
import tempfile
from pathlib import Path

# Ensure this project's app is loaded (not a parent directory's)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Create a temporary database file for tests
temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
temp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{temp_db.name}"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"

# Clean up the temp database file after tests
def pytest_sessionfinish(session, exitstatus):
    """Clean up temporary database file after test session."""
    try:
        os.unlink(temp_db.name)
    except (OSError, PermissionError) as e:
        # Log the error but don't fail the test session
        print(f"Warning: Could not clean up temporary database file {temp_db.name}: {e}")
