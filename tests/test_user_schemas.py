"""
tests/test_user_schemas.py

Tests for app/schemas/user.py

Covers:
- UserLogin schema: field presence, email validation, types
- UserCreate schema: field presence, email validation, types
- UserResponse schema: field presence, ORM mode, no password fields
- Token schema: default token_type, field presence, types
"""
# ruff: noqa: S105,S106
import pytest
from pydantic import ValidationError

from app.schemas.user import Token, UserCreate, UserLogin, UserResponse


# =============================================================================
# UserLogin Tests
# =============================================================================


class TestUserLogin:
    """Tests for UserLogin schema."""

    def test_userlogin_valid(self):
        """Should create a valid UserLogin with email and password."""
        schema = UserLogin(email="user@example.com", password="Password123!")
        assert schema.email == "user@example.com"
        assert schema.password == "Password123!"

    def test_userlogin_email_is_validated(self):
        """Invalid email should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserLogin(email="not-an-email", password="secret123")

    def test_userlogin_email_required(self):
        """Missing email should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserLogin(password="secret123")

    def test_userlogin_password_required(self):
        """Missing password should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserLogin(email="user@example.com")

    def test_userlogin_email_field_type(self):
        """Email field should be stored as a string (EmailStr serialises to str)."""
        schema = UserLogin(email="user@example.com", password="pass")
        assert isinstance(schema.email, str)

    def test_userlogin_password_can_be_any_string(self):
        """Password accepts any non-null string (no length restriction at schema level)."""
        schema = UserLogin(email="user@example.com", password="")
        assert schema.password == ""

    def test_userlogin_has_only_expected_fields(self):
        """UserLogin should only expose email and password."""
        schema = UserLogin(email="user@example.com", password="pass")
        fields = set(schema.model_fields.keys())
        assert fields == {"email", "password"}

    def test_userlogin_accepts_mixed_case_email(self):
        """Pydantic v2 EmailStr validates format but normalizes domain case."""
        schema = UserLogin(email="User@Example.COM", password="pass")
        # EmailStr normalizes domain to lowercase but preserves local part case
        assert str(schema.email) == "User@example.com"


# =============================================================================
# UserCreate Tests
# =============================================================================


class TestUserCreate:
    """Tests for UserCreate schema."""

    def test_usercreate_valid(self):
        """Should create a valid UserCreate with email and password."""
        schema = UserCreate(email="newuser@example.com", password="Password123!")
        assert schema.email == "newuser@example.com"
        assert schema.password == "Password123!"

    def test_usercreate_invalid_email_raises(self):
        """Invalid email should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserCreate(email="invalid-email", password="mypassword")

    def test_usercreate_missing_email_raises(self):
        """Missing email should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserCreate(password="mypassword")

    def test_usercreate_missing_password_raises(self):
        """Missing password should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserCreate(email="newuser@example.com")

    def test_usercreate_has_only_expected_fields(self):
        """UserCreate should only expose email and password."""
        schema = UserCreate(email="newuser@example.com", password="Password123!")
        fields = set(schema.model_fields.keys())
        assert fields == {"email", "password"}

    def test_usercreate_accepts_mixed_case_email(self):
        """Pydantic v2 EmailStr validates format but normalizes domain case."""
        schema = UserCreate(email="New@Example.COM", password="Pass123!")
        # EmailStr normalizes domain to lowercase but preserves local part case
        assert str(schema.email) == "New@example.com"


class TestUserCreateComplexity:
    """Tests for UserCreate password complexity validation."""

    def test_password_min_length(self):
        """Password must be at least 8 characters."""
        with pytest.raises(ValidationError, match="at least 8 characters"):
            UserCreate(email="u@e.com", password="P1a!567")

    def test_password_uppercase_required(self):
        """Password must have at least one uppercase letter."""
        with pytest.raises(ValidationError, match="at least one uppercase"):
            UserCreate(email="u@e.com", password="p1a!5678")

    def test_password_lowercase_required(self):
        """Password must have at least one lowercase letter."""
        with pytest.raises(ValidationError, match="at least one lowercase"):
            UserCreate(email="u@e.com", password="P1A!5678")

    def test_password_digit_required(self):
        """Password must have at least one digit."""
        with pytest.raises(ValidationError, match="at least one digit"):
            UserCreate(email="u@e.com", password="Paa!bcde")

    def test_password_special_char_required(self):
        """Password must have at least one special character."""
        with pytest.raises(ValidationError, match="at least one special character"):
            UserCreate(email="u@e.com", password="P1abcde2")

    def test_password_valid_complexity(self):
        """Should accept a password that meets all complexity rules."""
        schema = UserCreate(email="u@e.com", password="Password123!")
        assert schema.password == "Password123!"


# =============================================================================
# UserResponse Tests
# =============================================================================


class TestUserResponse:
    """Tests for UserResponse schema."""

    def test_userresponse_valid(self):
        """Should create a valid UserResponse with id, email, role."""
        schema = UserResponse(id=1, email="admin@example.com", role="admin")
        assert schema.id == 1
        assert schema.email == "admin@example.com"
        assert schema.role == "admin"

    def test_userresponse_missing_id_raises(self):
        """Missing id should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserResponse(email="admin@example.com", role="admin")

    def test_userresponse_missing_email_raises(self):
        """Missing email should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserResponse(id=1, role="admin")

    def test_userresponse_missing_role_raises(self):
        """Missing role should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserResponse(id=1, email="admin@example.com")

    def test_userresponse_has_no_password_field(self):
        """UserResponse must NOT expose hashed_password or password."""
        schema = UserResponse(id=1, email="user@example.com", role="user")
        fields = set(schema.model_fields.keys())
        assert "hashed_password" not in fields
        assert "password" not in fields

    def test_userresponse_has_exactly_expected_fields(self):
        """UserResponse should only expose id, email, role."""
        schema = UserResponse(id=1, email="user@example.com", role="user")
        fields = set(schema.model_fields.keys())
        assert fields == {"id", "email", "role"}

    def test_userresponse_id_must_be_int(self):
        """id field should be coerced to int."""
        schema = UserResponse(id="5", email="user@example.com", role="user")
        assert schema.id == 5
        assert isinstance(schema.id, int)

    def test_userresponse_invalid_email_raises(self):
        """Invalid email should raise ValidationError."""
        with pytest.raises(ValidationError):
            UserResponse(id=1, email="not-an-email", role="user")

    def test_userresponse_orm_mode_enabled(self):
        """
        UserResponse must have from_attributes enabled (Pydantic v2)
        so SQLAlchemy models can be serialised directly.
        """
        config = UserResponse.model_config
        assert config.get("from_attributes") is True

    def test_userresponse_from_orm_object(self):
        """
        UserResponse should be constructable from an ORM-like object
        when from_attributes is enabled (orm_mode = True).
        """
        from types import SimpleNamespace
        orm_obj = SimpleNamespace(id=7, email="orm@example.com", role="agent")
        # Pydantic v2: model_validate with from_attributes=True
        schema = UserResponse.model_validate(orm_obj, from_attributes=True)
        assert schema.id == 7
        assert schema.email == "orm@example.com"
        assert schema.role == "agent"

    def test_userresponse_serialises_to_dict(self):
        """model_dump() should return a clean dict without password fields."""
        schema = UserResponse(id=2, email="user@example.com", role="user")
        data = schema.model_dump()
        assert data == {"id": 2, "email": "user@example.com", "role": "user"}
        assert "hashed_password" not in data
        assert "password" not in data


# =============================================================================
# Token Tests
# =============================================================================


class TestToken:
    """Tests for Token schema."""

    def test_token_valid(self):
        """Should create a valid Token with access_token and default token_type."""
        token = Token(access_token="someJWT")
        assert token.access_token == "someJWT"
        assert token.token_type == "bearer"

    def test_token_default_token_type_is_bearer(self):
        """token_type must default to 'bearer' when not supplied."""
        token = Token(access_token="abc.def.ghi")
        assert token.token_type == "bearer"

    def test_token_explicit_token_type(self):
        """token_type can be overridden explicitly."""
        token = Token(access_token="abc.def.ghi", token_type="Bearer")
        assert token.token_type == "Bearer"

    def test_token_missing_access_token_raises(self):
        """Missing access_token should raise ValidationError."""
        with pytest.raises(ValidationError):
            Token()

    def test_token_access_token_must_be_string(self):
        """access_token must serialise to a string."""
        token = Token(access_token="my.jwt.token")
        assert isinstance(token.access_token, str)

    def test_token_has_exactly_expected_fields(self):
        """Token should only expose access_token and token_type."""
        token = Token(access_token="x")
        fields = set(token.model_fields.keys())
        assert fields == {"access_token", "token_type"}

    def test_token_serialises_to_dict(self):
        """model_dump() should return the correct dict shape."""
        token = Token(access_token="abc.def.ghi")
        data = token.model_dump()
        assert data == {"access_token": "abc.def.ghi", "token_type": "bearer"}

    def test_token_with_real_jwt_string(self):
        """Token should accept a real 3-part JWT string without issues."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMSJ9.SIGNATURE"
        token = Token(access_token=jwt)
        assert token.access_token == jwt
        assert token.token_type == "bearer"
