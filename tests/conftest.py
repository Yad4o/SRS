"""
tests/conftest.py

Pytest configuration and shared fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.db.session import Base, get_db
from app.models.ticket import Ticket  # noqa: F401
from app.models.feedback import Feedback  # noqa: F401
from app.api.admin import router


# Use in-memory SQLite for testing with StaticPool to share connection
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Share the same connection across threads
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """
    Override database dependency for testing.
    """
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Create all tables at the start of the test session.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function", autouse=True)
def clean_tables():
    """
    Clean all data from tables before each test.
    """
    yield
    # Clean up after test
    db = TestingSessionLocal()
    try:
        db.query(Feedback).delete()
        db.query(Ticket).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    """
    Provide a database session for test data setup.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """
    Create a test client with overridden database dependency.
    """
    app = create_app()
    app.include_router(router, prefix="/admin", tags=["Admin"])
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()
