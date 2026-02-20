"""
Tests for app/core/config.py

Covers:
- get_settings returns Settings instance
- Settings caching
- Default values for optional fields
- Required fields
- Decision engine threshold
"""
import pytest
from pydantic import ValidationError
from app.core.config import Settings, get_settings


class TestGetSettings:
    """Tests for get_settings()."""

    def test_returns_settings_instance(self):
        """get_settings should return a Settings object."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_returns_cached_instance(self):
        """get_settings should return the same cached instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestSettingsDefaults:
    """Tests for Settings default values (using explicit kwargs to bypass env)."""

    def test_app_name_default(self):
        """APP_NAME has expected default."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.APP_NAME == "Automated Customer Support Resolution System"

    def test_env_default(self):
        """ENV defaults to development."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.ENV == "development"

    def test_algorithm_default(self):
        """ALGORITHM defaults to HS256."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.ALGORITHM == "HS256"

    def test_access_token_expire_default(self):
        """ACCESS_TOKEN_EXPIRE_MINUTES defaults to 60."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_ai_provider_default(self):
        """AI_PROVIDER defaults to openai."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.AI_PROVIDER == "openai"

    def test_confidence_threshold_default(self):
        """CONFIDENCE_THRESHOLD_AUTO_RESOLVE defaults to 0.75 (Technical Spec § 9.4)."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.CONFIDENCE_THRESHOLD_AUTO_RESOLVE == 0.75

    def test_confidence_threshold_in_valid_range(self):
        """Confidence threshold should be between 0 and 1."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert 0.0 <= s.CONFIDENCE_THRESHOLD_AUTO_RESOLVE <= 1.0
    
    def test_confidence_threshold_out_of_range(self):
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="x",
                DATABASE_URL="sqlite:///test.db",
                CONFIDENCE_THRESHOLD_AUTO_RESOLVE=1.5,
            )

    def test_optional_openai_key_has_no_required_default(self):
        """OPENAI_API_KEY is optional; when omitted it is None or empty string."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.OPENAI_API_KEY is None or s.OPENAI_API_KEY == ""

    def test_optional_redis_url_has_no_required_default(self):
        """REDIS_URL is optional; when omitted it is None or empty string."""
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert s.REDIS_URL is None or s.REDIS_URL == ""

    def test_cors_origins_default_is_list(self):
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")
        assert isinstance(s.CORS_ORIGINS, list)

    def test_new_config_defaults_smoke(self):
        s = Settings(SECRET_KEY="x", DATABASE_URL="sqlite:///test.db")

        assert s.DATABASE_POOL_SIZE == 5
        assert s.DATABASE_MAX_OVERFLOW == 10
        assert s.SIMILARITY_THRESHOLD == 0.7
        assert s.MAX_SIMILAR_TICKETS_TO_CHECK == 100
        assert s.RATE_LIMIT_PER_MINUTE == 60

class TestSettingsRequiredFields:
    """Tests for Settings required fields."""

    def test_secret_key_is_required_field(self):
        """SECRET_KEY is defined as a required field in Settings."""
        # Pydantic marks required fields as non-optional with no default
        field_info = Settings.model_fields.get("SECRET_KEY")
        assert field_info is not None
        assert field_info.is_required()

    def test_database_url_is_required_field(self):
        """DATABASE_URL is defined as a required field in Settings."""
        field_info = Settings.model_fields.get("DATABASE_URL")
        assert field_info is not None
        assert field_info.is_required()


class TestSettingsOverride:
    """Tests for Settings override behavior."""

    def test_confidence_threshold_override(self):
        """CONFIDENCE_THRESHOLD can be overridden."""
        s = Settings(
            SECRET_KEY="x",
            DATABASE_URL="sqlite:///test.db",
            CONFIDENCE_THRESHOLD_AUTO_RESOLVE=0.9,
        )
        assert s.CONFIDENCE_THRESHOLD_AUTO_RESOLVE == 0.9
