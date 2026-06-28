"""
tests/api/test_refresh_token.py

Tests for the refresh token flow added in app/api/auth.py.

Covers:
- Login response includes a refresh_token
- POST /auth/refresh exchanges a valid refresh token for a new pair
- Refresh token rotation: the old refresh token cannot be reused
  after a successful /auth/refresh call
- POST /auth/refresh rejects unknown / malformed tokens
- POST /auth/refresh rejects an expired token
- POST /auth/logout revokes a refresh token (it can no longer be used
  to refresh afterwards)
- POST /auth/logout is idempotent / tolerant of unknown tokens
- The new access token issued by /auth/refresh is itself usable against
  a protected route
"""

import random
import string
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import init_db, SessionLocal
from app.core.security import hash_refresh_token
from app.models.refresh_token import RefreshToken


def unique_email() -> str:
    """Generate a unique email for testing to avoid conflicts."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"refresh_test_{random_str}@example.com"


@pytest.fixture
def test_client():
    """Create a test client with initialized database."""
    app = create_app()
    with TestClient(app) as client:
        init_db()
        yield client


def _register_and_login(test_client) -> tuple[str, dict]:
    """Register a fresh user and log in, returning (email, token_response_json)."""
    email = unique_email()
    test_client.post("/auth/register", json={"email": email, "password": "Password123!"})
    response = test_client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200
    return email, response.json()


class TestLoginIssuesRefreshToken:
    """Login should now hand back a refresh token alongside the access token."""

    def test_login_response_includes_refresh_token(self, test_client):
        _, token_data = _register_and_login(test_client)

        assert "refresh_token" in token_data
        assert isinstance(token_data["refresh_token"], str)
        assert len(token_data["refresh_token"]) > 20
        # access token behavior is unchanged
        assert isinstance(token_data["access_token"], str)
        assert token_data["token_type"] == "bearer"


class TestRefreshEndpoint:
    """Tests for POST /auth/refresh."""

    def test_refresh_returns_new_token_pair(self, test_client):
        _, token_data = _register_and_login(test_client)

        response = test_client.post(
            "/auth/refresh",
            json={"refresh_token": token_data["refresh_token"]},
        )

        assert response.status_code == 200
        new_data = response.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data
        assert new_data["token_type"] == "bearer"
        # Rotation: the new refresh token must differ from the old one.
        # (The access token's JWT `exp` claim has second-granularity, so it
        # *can* be byte-identical to the previous one if both are minted
        # within the same second — that's expected and not checked here.)
        assert new_data["refresh_token"] != token_data["refresh_token"]

    def test_new_access_token_works_on_protected_route(self, test_client):
        _, token_data = _register_and_login(test_client)

        refreshed = test_client.post(
            "/auth/refresh",
            json={"refresh_token": token_data["refresh_token"]},
        ).json()

        me_response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refreshed['access_token']}"},
        )
        assert me_response.status_code == 200

    def test_old_refresh_token_cannot_be_reused_after_rotation(self, test_client):
        _, token_data = _register_and_login(test_client)
        old_refresh_token = token_data["refresh_token"]

        first_refresh = test_client.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert first_refresh.status_code == 200

        # Replaying the now-rotated-away old token must fail.
        second_attempt = test_client.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh_token},
        )
        assert second_attempt.status_code == 401

    def test_refresh_rejects_unknown_token(self, test_client):
        response = test_client.post(
            "/auth/refresh",
            json={"refresh_token": "this-token-does-not-exist-anywhere"},
        )
        assert response.status_code == 401

    def test_refresh_rejects_expired_token(self, test_client):
        _, token_data = _register_and_login(test_client)

        # Manually expire the token in the DB to simulate the 30-day window
        # having passed, without needing to wait 30 days.
        db = SessionLocal()
        try:
            token_hash = hash_refresh_token(token_data["refresh_token"])
            row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
            assert row is not None
            row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            db.commit()
        finally:
            db.close()

        response = test_client.post(
            "/auth/refresh",
            json={"refresh_token": token_data["refresh_token"]},
        )
        assert response.status_code == 401

    def test_refresh_rejects_missing_field(self, test_client):
        # This app's validation_exception_handler maps RequestValidationError
        # to 400 (not FastAPI's default 422) — see app/core/error_handlers.py.
        response = test_client.post("/auth/refresh", json={})
        assert response.status_code == 400


class TestLogoutEndpoint:
    """Tests for POST /auth/logout."""

    def test_logout_revokes_refresh_token(self, test_client):
        _, token_data = _register_and_login(test_client)

        logout_response = test_client.post(
            "/auth/logout",
            json={"refresh_token": token_data["refresh_token"]},
        )
        assert logout_response.status_code == 200
        assert "message" in logout_response.json()

        # The revoked token must no longer work for refreshing.
        refresh_response = test_client.post(
            "/auth/refresh",
            json={"refresh_token": token_data["refresh_token"]},
        )
        assert refresh_response.status_code == 401

    def test_logout_is_idempotent_for_unknown_token(self, test_client):
        """Logging out with a token that doesn't exist should still succeed —
        the desired end state (not logged in) is already true."""
        response = test_client.post(
            "/auth/logout",
            json={"refresh_token": "totally-unknown-token-value"},
        )
        assert response.status_code == 200

    def test_logout_twice_with_same_token_is_safe(self, test_client):
        _, token_data = _register_and_login(test_client)

        first = test_client.post(
            "/auth/logout", json={"refresh_token": token_data["refresh_token"]}
        )
        second = test_client.post(
            "/auth/logout", json={"refresh_token": token_data["refresh_token"]}
        )
        assert first.status_code == 200
        assert second.status_code == 200


class TestRefreshTokenStorage:
    """Verify refresh tokens are never persisted in plaintext."""

    def test_stored_refresh_token_is_hashed_not_plaintext(self, test_client):
        _, token_data = _register_and_login(test_client)
        raw_token = token_data["refresh_token"]

        db = SessionLocal()
        try:
            rows = db.query(RefreshToken).all()
            assert len(rows) >= 1
            for row in rows:
                assert row.token_hash != raw_token
                assert len(row.token_hash) == 64  # hex-encoded SHA-256 digest
        finally:
            db.close()
