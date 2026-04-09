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
import random
import string

from app.main import create_app
from app.core.security import create_access_token, decode_token
from app.models.user import User
from app.schemas.user import UserCreate
from app.db.session import init_db


def unique_email() -> str:
    """Generate a unique email for testing to avoid conflicts."""
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{random_str}@example.com"


@pytest.fixture
def test_client():
    """Create a test client with initialized database."""
    app = create_app()
    with TestClient(app) as client:
        # Initialize database for this test client
        init_db()
        yield client


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_register_success(self, test_client):
        """Test successful user registration."""
        email = unique_email()
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["role"] == "user"
        assert "id" in data
        assert "password" not in data  # Should never return password

    def test_register_valid_email_formats(self, test_client):
        """Test registration with various valid email formats."""
        valid_emails = [
            "test@example.com",                # Standard format
            "test.email@domain.co.uk",        # Multi-level TLD
            "test+tag@domain.com",            # Plus sign in local part
            "test_email@sub.domain.com",      # Subdomain
            "123@domain.com",                 # Numbers in local part
            "a@b.co",                         # Minimal valid email
        ]
        
        for email in valid_emails:
            response = test_client.post(
                "/auth/register",
                json={"email": email, "password": "Password123!"}
            )
            assert response.status_code == 200
            assert response.json()["email"] == email.lower()

    def test_login_invalid_email_formats(self, test_client):
        """Test login with empty email (should be caught by EmailStr validation)."""
        # Test with empty email - this should be caught by EmailStr validation
        response = test_client.post(
            "/auth/login",
            json={"email": "", "password": "Password123!"}
        )
        assert response.status_code == 400  # EmailStr validation error

    def test_register_whitespace_emails(self, test_client):
        """Test registration with emails gets normalized correctly."""
        # Test that emails are normalized to lowercase
        email_uppercase = "TEST@NORMALIZATION.COM"
        response = test_client.post(
            "/auth/register",
            json={"email": email_uppercase, "password": "Password123!"}
        )
        assert response.status_code == 200
        # Should be stored in lowercase
        assert response.json()["email"] == email_uppercase.lower()

    def test_register_whitespace_only_email(self, test_client):
        """Test registration with whitespace-only email fails."""
        response = test_client.post(
            "/auth/register",
            json={"email": "   ", "password": "Password123!"}
        )
        # Should fail at EmailStr validation level
        assert response.status_code == 400

    def test_register_leading_trailing_whitespace_email(self, test_client):
        """Test registration with leading/trailing whitespace in email."""
        email_with_spaces = f"  test{unique_email().split('@')[0]}@example.com  "
        expected_email = email_with_spaces.strip().lower()
        response = test_client.post(
            "/auth/register",
            json={"email": email_with_spaces, "password": "Password123!"}
        )
        assert response.status_code == 200
        # Should be stored without whitespace and in lowercase
        assert response.json()["email"] == expected_email

    def test_register_whitespace_only_password(self, test_client):
        """Test registration with whitespace-only password fails."""
        response = test_client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "   "}
        )
        # Should fail at schema validation level
        assert response.status_code == 400

    def test_register_existing_email_improved_message(self, test_client):
        """Test registration with existing email returns specific message."""
        email = unique_email()
        # Register first user
        test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )

        # Try to register with same email
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )

        assert response.status_code == 400
        assert "error" in response.json()
        assert "Email already registered" in response.json()["error"]["message"]

    def test_register_weak_password(self, test_client):
        """Test registration with weak password fails validation."""
        response = test_client.post(
            "/auth/register",
            json={"email": "weak@example.com", "password": "weak"}
        )

        # Should fail at schema validation level
        assert response.status_code == 400

    def test_register_long_password(self, test_client):
        """Test registration with very long password (over 72 bytes)."""
        # Create a password that exceeds 72 bytes when UTF-8 encoded
        # but still meets complexity requirements
        long_password = "a" * 51 + "A" * 20 + "1!"  # 73 bytes (ASCII), exercises truncation path
        email = unique_email()
        
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": long_password}
        )
        
        # Should still work (password gets truncated)
        assert response.status_code == 200
        
        # Should be able to login with the same long password
        login_response = test_client.post(
            "/auth/login",
            json={"email": email, "password": long_password}
        )
        assert login_response.status_code == 200

    def test_register_unicode_password(self, test_client):
        """Test registration with Unicode characters in password."""
        unicode_password = "🔐Password123!测试"  # Mix of emoji and Chinese characters
        email = unique_email()
        
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": unicode_password}
        )
        
        assert response.status_code == 200
        
        # Should be able to login with the same Unicode password
        login_response = test_client.post(
            "/auth/login",
            json={"email": email, "password": unicode_password}
        )
        assert login_response.status_code == 200

    def test_register_long_unicode_password(self, test_client):
        """Test registration with Unicode password that exceeds 72-byte limit."""
        # Create a password with multibyte characters that exceeds 72 bytes when UTF-8 encoded
        # 10 emojis (40 bytes) + 5 Chinese phrases (30 bytes) + "Password123!" (12 bytes) = 82 bytes total
        long_unicode_password = "🔐" * 10 + "测试" * 5 + "Password123!"  # 82+ bytes with complexity
        email = unique_email()
        
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": long_unicode_password}
        )
        
        assert response.status_code == 200
        
        # Should be able to login with the same long Unicode password
        login_response = test_client.post(
            "/auth/login",
            json={"email": email, "password": long_unicode_password}
        )
        assert login_response.status_code == 200

    def test_password_truncation_info(self, test_client):
        """Test password truncation checking functionality."""
        from app.core.security import check_password_truncation
        
        # Test short password (no truncation)
        short_password = "Password123!"
        info = check_password_truncation(short_password)
        assert not info["would_be_truncated"]
        assert info["original_bytes"] < 72
        assert info["max_bytes"] == 72
        
        # Test long password (would be truncated)
        long_password = "a" * 100  # 100 characters
        info = check_password_truncation(long_password)
        assert info["would_be_truncated"]
        assert info["original_bytes"] > 72
        assert info["max_bytes"] == 72
        
        # Test multibyte password that exceeds 72 bytes when UTF-8 encoded
        # Each 🔐 emoji is 4 bytes in UTF-8, so 20 emojis = 80 bytes
        multibyte_password = "🔐" * 20 + "A1!"  # 80+ bytes with complexity
        info = check_password_truncation(multibyte_password)
        assert info["would_be_truncated"]
        assert info["original_bytes"] > 72
        assert info["max_bytes"] == 72

    def test_jwt_token_no_email_payload(self, test_client):
        """Test that JWT token no longer contains email in payload."""
        email = unique_email()
        # Register and login to get token
        test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )
        login_response = test_client.post(
            "/auth/login",
            json={"email": email, "password": "Password123!"}
        )
        token = login_response.json()["access_token"]
        
        # Decode token and check payload
        payload = decode_token(token)
        
        # Should contain sub and role but NOT email
        assert "sub" in payload
        assert "role" in payload
        assert "email" not in payload
        assert payload["role"] == "user"

    def test_login_success(self, test_client):
        """Test successful login returns valid JWT token."""
        email = unique_email()
        # First register a user
        register_response = test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )
        assert register_response.status_code == 200

        # Test login
        response = test_client.post(
            "/auth/login",
            json={"email": email, "password": "Password123!"}
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
        assert "email" not in payload  # Email should not be in token for security
        assert payload["role"] == "user"

    def test_login_invalid_email(self, test_client):
        """Test login with non-existent email returns 401."""
        response = test_client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "password"}
        )

        assert response.status_code == 401
        assert "error" in response.json()
        assert "Incorrect email or password" in response.json()["error"]["message"]

    def test_login_invalid_password(self, test_client):
        """Test login with wrong password returns 401."""
        email = unique_email()
        # First register a user
        test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )

        # Test login with wrong password
        response = test_client.post(
            "/auth/login",
            json={"email": email, "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "error" in response.json()
        assert "Incorrect email or password" in response.json()["error"]["message"]

    def test_protected_route_without_token(self, test_client):
        """Test accessing protected route without token returns 401."""
        response = test_client.get("/auth/me")
        assert response.status_code == 401

    def test_protected_route_with_valid_token(self, test_client):
        """Test accessing protected route with valid token."""
        email = unique_email()
        # Register and login to get token
        test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )
        login_response = test_client.post(
            "/auth/login",
            json={"email": email, "password": "Password123!"}
        )
        token = login_response.json()["access_token"]

        # Test protected route
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["role"] == "user"
        assert "id" in data

    def test_protected_route_with_invalid_token(self, test_client):
        """Test accessing protected route with invalid token returns 401."""
        response = test_client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401


class TestTokenValidation:
    """Tests for JWT token validation."""

    def test_token_contains_required_claims(self):
        """Test JWT token contains required claims."""
        token = create_access_token({"sub": "123", "role": "user"})
        payload = decode_token(token)

        assert "sub" in payload
        assert "exp" in payload
        assert payload["sub"] == "123"
        assert "role" in payload
        assert payload["role"] == "user"
        assert "email" not in payload  # Email should not be in token

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

    def test_login_response_structure(self, test_client):
        """Test login endpoint returns correct structure."""
        email = unique_email()
        # Register a user first
        test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )

        # Test login
        response = test_client.post(
            "/auth/login",
            json={"email": email, "password": "Password123!"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["access_token"], str)
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 50  # JWT tokens are typically long

    def test_register_response_structure(self, test_client):
        """Test register endpoint returns correct structure."""
        email = unique_email()
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": "Password123!"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["id"], int)
        assert isinstance(data["email"], str)
        assert isinstance(data["role"], str)
        assert "password" not in data
        assert data["role"] == "user"  # Default role

    def test_multiple_login_same_user(self, test_client):
        """Test that same user can login multiple times."""
        email = unique_email()
        password = "Password123!"

        # Register user
        test_client.post(
            "/auth/register",
            json={"email": email, "password": password}
        )

        # Login multiple times
        for i in range(3):
            response = test_client.post(
                "/auth/login",
                json={"email": email, "password": password}
            )
            assert response.status_code == 200
            assert "access_token" in response.json()

    def test_login_case_insensitive_email(self, test_client):
        """Test that email login works with case-insensitive email matching."""
        email = "CaseSensitive@Test.COM"
        password = "Password123!"

        # Register with mixed case
        response = test_client.post(
            "/auth/register",
            json={"email": email, "password": password}
        )
        assert response.status_code == 200
        # Email should be stored in lowercase
        registered_email = response.json()["email"]
        assert registered_email == email.lower()

        # Login should work with any case variation due to normalization
        test_cases = [
            email,                    # Original case
            email.lower(),            # All lowercase
            email.upper(),            # All uppercase
            "CaseSensitive@test.com", # Mixed case
            "  CaseSensitive@Test.COM  ", # Leading/trailing whitespace
        ]
        
        for login_email in test_cases:
            response = test_client.post(
                "/auth/login",
                json={"email": login_email, "password": password}
            )
            assert response.status_code == 200
            assert "access_token" in response.json()
