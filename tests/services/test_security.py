"""
tests/test_security.py

Tests for app/core/security.py

Covers:
- Password hashing with bcrypt (hash_password, verify_password)
- JWT token creation and decoding (create_access_token, decode_token)
- Correct error handling for invalid/expired/malformed tokens
"""
import time
from datetime import timedelta

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


# =============================================================================
# Password Hashing Tests
# =============================================================================


class TestPasswordHashing:
    """Tests for hash_password and verify_password utilities."""

    def test_hash_password_returns_string(self):
        """hash_password should return a string."""
        result = hash_password("mysecretpassword")
        assert isinstance(result, str)

    def test_hash_password_not_plain_text(self):
        """The returned hash must not equal the original plain-text password."""
        plain = "mysecretpassword"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_hash_password_different_each_time(self):
        """
        Two calls with the same password must produce different hashes.
        bcrypt generates a unique random salt per call — this is expected and
        essential for security.
        """
        plain = "samepassword"
        hash1 = hash_password(plain)
        hash2 = hash_password(plain)
        assert hash1 != hash2

    def test_hash_is_bcrypt_format(self):
        """
        bcrypt hashes start with '$2b$', '$2a$', or '$2y$'.
        The prefix encodes the algorithm and cost factor.
        """
        hashed = hash_password("anypassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$")
        assert verify_password("anypassword", hashed) is True

    def test_hash_password_empty_string(self):
        """Should be able to hash an empty string without raising."""
        hashed = hash_password("")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """verify_password returns True when the plain password matches the hash."""
        plain = "correctpassword"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_password_wrong(self):
        """verify_password returns False when the plain password does not match."""
        hashed = hash_password("originalpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty_string_does_not_match(self):
        """An empty string must not verify against a real-password hash."""
        hashed = hash_password("realpassword")
        assert verify_password("", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Password verification must be case-sensitive."""
        plain = "Password123"
        hashed = hash_password(plain)
        assert verify_password("password123", hashed) is False
        assert verify_password("PASSWORD123", hashed) is False

    def test_verify_password_returns_bool(self):
        """verify_password must return a bool, not a truthy/falsy value."""
        plain = "testpassword"
        hashed = hash_password(plain)
        result_true = verify_password(plain, hashed)
        result_false = verify_password("wrongpassword", hashed)
        assert isinstance(result_true, bool)
        assert isinstance(result_false, bool)

    def test_verify_password_malformed_hash_returns_false(self):
        """verify_password must fail-closed (return False) instead of raising an exception on malformed hashes."""
        plain = "testpassword"
        malformed_hash = "not-a-bcrypt-hash"
        # Should return False without raising any exceptions
        assert verify_password(plain, malformed_hash) is False


# =============================================================================
# JWT Token Tests
# =============================================================================


class TestJWTToken:
    """Tests for create_access_token and decode_token utilities."""

    def test_create_access_token_returns_string(self):
        """create_access_token should return a non-empty string."""
        token = create_access_token(data={"sub": "user123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_has_three_parts(self):
        """A valid JWT consists of three Base64-encoded parts separated by dots."""
        token = create_access_token(data={"sub": "user123"})
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have exactly 3 dot-separated segments"

    def test_decode_token_valid(self):
        """A freshly created token should decode without errors."""
        data = {"sub": "user42", "role": "admin"}
        token = create_access_token(data=data)
        payload = decode_token(token)
        assert payload is not None
        assert isinstance(payload, dict)

    def test_decode_token_payload_contains_sub(self):
        """The decoded payload must contain the 'sub' claim we encoded."""
        token = create_access_token(data={"sub": "user99"})
        payload = decode_token(token)
        assert payload["sub"] == "user99"

    def test_decode_token_payload_preserves_extra_claims(self):
        """All extra claims in the data dict should survive the encode/decode."""
        token = create_access_token(data={"sub": "user1", "role": "agent"})
        payload = decode_token(token)
        assert payload["sub"] == "user1"
        assert payload["role"] == "agent"

    def test_token_contains_expiry_claim(self):
        """The decoded payload must include the 'exp' (expiry) claim."""
        token = create_access_token(data={"sub": "user1"})
        payload = decode_token(token)
        assert "exp" in payload

    def test_create_access_token_default_expiry_uses_settings(self):
        """
        When no expires_delta is supplied, the token expiry should be
        approximately ACCESS_TOKEN_EXPIRE_MINUTES from now.
        Allow a 5-second tolerance for test execution time.
        """
        import time as _time
        from datetime import datetime, timezone
        from app.core.config import settings

        before = _time.time()
        token = create_access_token(data={"sub": "user1"})
        payload = decode_token(token)
        after = _time.time()

        expected_exp_min = before + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expected_exp_max = after + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        assert expected_exp_min - 5 <= payload["exp"] <= expected_exp_max + 5

    def test_create_access_token_does_not_mutate_input(self):
        """
        create_access_token must not modify the caller's data dict.
        Internally it uses data.copy() before appending 'exp'.
        """
        data = {"sub": "user1", "role": "user"}
        original_data = data.copy()
        create_access_token(data=data)
        assert data == original_data, "create_access_token must not mutate the input dict"
        assert "exp" not in data, "'exp' claim should not be injected into the caller's dict"

    def test_create_access_token_custom_expiry(self):
        """
        When expires_delta is supplied it must be used instead of the default.
        """
        import time as _time

        delta = timedelta(seconds=30)
        before = _time.time()
        token = create_access_token(data={"sub": "user1"}, expires_delta=delta)
        payload = decode_token(token)
        after = _time.time()

        # Token should expire roughly 30 seconds from now
        assert before + 25 <= payload["exp"] <= after + 35

    def test_decode_token_expired_raises(self):
        """
        A token with a negative expires_delta is already expired.
        decode_token must raise JWTError.
        """
        token = create_access_token(
            data={"sub": "user1"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_decode_token_invalid_signature_raises(self):
        """
        A token with a tampered signature must raise JWTError.
        We replace the entire signature segment with a clearly wrong value.
        """
        token = create_access_token(data={"sub": "user1"})
        header, payload, _ = token.split(".")
        # Replace signature with a fixed bogus segment
        tampered_token = f"{header}.{payload}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        with pytest.raises(JWTError):
            decode_token(tampered_token)

    def test_decode_token_malformed_raises(self):
        """
        Garbage strings must raise JWTError, not crash with another exception.
        """
        with pytest.raises(JWTError):
            decode_token("this.is.notajwt")

    def test_decode_token_empty_string_raises(self):
        """An empty string is not a valid JWT and must raise JWTError."""
        with pytest.raises(JWTError):
            decode_token("")

    def test_decode_token_wrong_secret_raises(self):
        """
        A token signed with a different key must fail signature verification.
        """
        from jose import jwt as _jwt
        from app.core.config import settings

        # Sign with a different secret
        fake_token = _jwt.encode(
            {"sub": "hacker", "exp": 9999999999},
            "completely-different-secret",
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(JWTError):
            decode_token(fake_token)
