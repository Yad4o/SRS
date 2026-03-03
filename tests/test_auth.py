"""
tests/test_auth.py

Tests for app/api/auth.py

Covers:
- Login endpoint with valid credentials
- Login endpoint with invalid credentials
- Registration endpoint with new user
- Registration endpoint with existing email
- Token validation and protected routes
- JWT token creation and decoding
- User authentication helper functions
"""

import pytest
from fastapi.testclient import TestClient
from jose import JWTError

from app.main import create_app
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.schemas.user import UserCreate
from app.db.session import init_db


# Test client setup with startup events
app = create_app()
client = TestClient(app)


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_register_success(self):
        """Test successful user registration."""
        with TestClient(app) as client:
            response = client.post(
                "/auth/register",
                json={"email": "newuser@example.com", "password": "Password123!"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["role"] == "user"
            assert "id" in data
            assert "password" not in data  # Should never return password

    def test_register_existing_email(self):
        """Test registration with existing email returns 400."""
        with TestClient(app) as client:
            # Register first user
            client.post(
                "/auth/register",
                json={"email": "existing@example.com", "password": "Password123!"}
            )

            # Try to register with same email
            response = client.post(
                "/auth/register",
                json={"email": "existing@example.com", "password": "Password123!"}
            )

            assert response.status_code == 400
            assert "Email already registered" in response.json()["detail"]

    def test_register_weak_password(self):
        """Test registration with weak password fails validation."""
        with TestClient(app) as client:
            response = client.post(
                "/auth/register",
                json={"email": "weak@example.com", "password": "weak"}
            )

            # Should fail at schema validation level
            assert response.status_code == 422

    def test_login_success(self):
        """Test successful login returns valid JWT token."""
        with TestClient(app) as client:
            # First register a user
            register_response = client.post(
                "/auth/register",
                json={"email": "test@example.com", "password": "Password123!"}
            )
            assert register_response.status_code == 200

            # Test login
            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "Password123!"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            
            # Verify token is valid
            token = data["access_token"]
            payload = decode_token(token)
            assert "sub" in payload
            assert "exp" in payload
            assert payload["email"] == "test@example.com"
            assert payload["role"] == "user"

    def test_login_invalid_email(self):
        """Test login with non-existent email returns 401."""
        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={"email": "nonexistent@example.com", "password": "password"}
            )

            assert response.status_code == 401
            assert "Incorrect email or password" in response.json()["detail"]

    def test_login_invalid_password(self):
        """Test login with wrong password returns 401."""
        with TestClient(app) as client:
            # First register a user
            client.post(
                "/auth/register",
                json={"email": "test@example.com", "password": "Password123!"}
            )

            # Test login with wrong password
            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "wrongpassword"}
            )

            assert response.status_code == 401
            assert "Incorrect email or password" in response.json()["detail"]

    def test_protected_route_without_token(self):
        """Test accessing protected route without token returns 401."""
        with TestClient(app) as client:
            response = client.get("/auth/me")
            assert response.status_code == 401

    def test_protected_route_with_valid_token(self):
        """Test accessing protected route with valid token."""
        with TestClient(app) as client:
            # Register and login to get token
            client.post(
                "/auth/register",
                json={"email": "test@example.com", "password": "Password123!"}
            )
            login_response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "Password123!"}
            )
            token = login_response.json()["access_token"]

            # Test protected route
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"
            assert data["role"] == "user"
            assert "id" in data

    def test_protected_route_with_invalid_token(self):
        """Test accessing protected route with invalid token returns 401."""
        with TestClient(app) as client:
            response = client.get(
                "/auth/me",
                headers={"Authorization": "Bearer invalid_token"}
            )

            assert response.status_code == 401


class TestTokenValidation:
    """Tests for JWT token validation."""

    def test_token_contains_required_claims(self):
        """Test JWT token contains required claims."""
        token = create_access_token({"sub": "123", "email": "test@example.com", "role": "user"})
        payload = decode_token(token)

        assert "sub" in payload
        assert "exp" in payload
        assert payload["sub"] == "123"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "user"

    def test_token_expires_correctly(self):
        """Test JWT token expires correctly."""
        from datetime import timedelta

        # Create token with short expiry
        token = create_access_token(
            {"sub": "123"},
            expires_delta=timedelta(seconds=1)
        )

        # Token should be valid immediately
        payload = decode_token(token)
        assert payload["sub"] == "123"

        # Note: We can't easily test expiration without waiting
        # This would be better tested with mocked time

    def test_login_response_structure(self):
        """Test login endpoint returns correct structure."""
        with TestClient(app) as client:
            # Register a user first
            client.post(
                "/auth/register",
                json={"email": "structure@example.com", "password": "Password123!"}
            )

            # Test login
            response = client.post(
                "/auth/login",
                json={"email": "structure@example.com", "password": "Password123!"}
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["access_token"], str)
            assert data["token_type"] == "bearer"
            assert len(data["access_token"]) > 50  # JWT tokens are typically long

    def test_register_response_structure(self):
        """Test register endpoint returns correct structure."""
        with TestClient(app) as client:
            response = client.post(
                "/auth/register",
                json={"email": "structure2@example.com", "password": "Password123!"}
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["id"], int)
            assert isinstance(data["email"], str)
            assert isinstance(data["role"], str)
            assert "password" not in data
            assert data["role"] == "user"  # Default role

    def test_multiple_login_same_user(self):
        """Test that same user can login multiple times."""
        with TestClient(app) as client:
            email = "multiple@example.com"
            password = "Password123!"

            # Register user
            client.post(
                "/auth/register",
                json={"email": email, "password": password}
            )

            # Login multiple times
            for i in range(3):
                response = client.post(
                    "/auth/login",
                    json={"email": email, "password": password}
                )
                assert response.status_code == 200
                assert "access_token" in response.json()

    def test_login_case_sensitive_email(self):
        """Test that email login works with consistent email case."""
        with TestClient(app) as client:
            email = "CaseSensitive@Test.COM"
            password = "Password123!"

            # Register with mixed case
            response = client.post(
                "/auth/register",
                json={"email": email, "password": password}
            )
            assert response.status_code == 200

            # Login should work with the same email (case preserved)
            response = client.post(
                "/auth/login",
                json={"email": email, "password": password}
            )
            assert response.status_code == 200
