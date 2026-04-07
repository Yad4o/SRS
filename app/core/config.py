"""
 =============================================================================
 SRS (Support Request System) - Configuration Management
 =============================================================================

Purpose:
--------
Centralized configuration management for the application.
All environment variables and settings are defined here with validation.

Responsibilities:
-----------------
- Load environment variables from .env files
- Define application settings with validation
- Provide type-safe configuration access
- Environment-aware configuration management
- Security validation for sensitive settings

Owner:
------
Backend Team

DO NOT:
-------
- Write business logic here
- Access database directly
- Hardcode secrets or credentials
"""

from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# -----------------------------------------------------------------------------
# Constants and Validation
# -----------------------------------------------------------------------------
ALLOWED_ROLES = {"user", "agent", "admin"}
ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}
ALLOWED_AI_PROVIDERS = {"openai", "anthropic", "local"}

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses pydantic-settings for type safety, validation, and environment
    variable loading. Values are cached for performance.
    
    Environment Priority:
    1. System environment variables
    2. .env file (if present)
    3. Default values (defined below)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra env vars to avoid validation errors
        validate_assignment=True,  # Validate on assignment
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    APP_NAME: str = "SRS Support System"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @field_validator("ENV")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is in allowed values."""
        if v not in ALLOWED_ENVIRONMENTS:
            raise ValueError(
                f"ENV must be one of {ALLOWED_ENVIRONMENTS}, got '{v}'"
            )
        return v

    # -------------------------------------------------------------------------
    # Security Settings
    # -------------------------------------------------------------------------
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: List[str] = []
    DEFAULT_USER_ROLE: str = "user"

    @field_validator("DEFAULT_USER_ROLE")
    @classmethod
    def validate_default_user_role(cls, v: str) -> str:
        """Validate that DEFAULT_USER_ROLE is in the allowed roles."""
        if v not in ALLOWED_ROLES:
            raise ValueError(
                f"DEFAULT_USER_ROLE must be one of {ALLOWED_ROLES}, got '{v}'"
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key meets minimum security requirements."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    # -------------------------------------------------------------------------
    # Database Configuration
    # -------------------------------------------------------------------------
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 30

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        
        # Basic URL format validation
        parsed = urlparse(v)
        if not parsed.scheme in ["sqlite", "postgresql", "mysql"]:
            raise ValueError(
                "DATABASE_URL must use sqlite, postgresql, or mysql scheme"
            )
        return v

    # -------------------------------------------------------------------------
    # AI/ML Configuration
    # -------------------------------------------------------------------------
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS: int = 1000
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_TIMEOUT: int = 30

    # Alternative AI providers
    ANTHROPIC_API_KEY: Optional[str] = None

    @field_validator("AI_PROVIDER")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        """Validate AI provider is supported."""
        if v not in ALLOWED_AI_PROVIDERS:
            raise ValueError(
                f"AI_PROVIDER must be one of {ALLOWED_AI_PROVIDERS}, got '{v}'"
            )
        return v

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is within valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("OPENAI_TEMPERATURE must be between 0.0 and 2.0")
        return v

    # -------------------------------------------------------------------------
    # Decision Engine Settings
    # -------------------------------------------------------------------------
    CONFIDENCE_THRESHOLD_AUTO_RESOLVE: float = 0.75
    CONFIDENCE_THRESHOLD_ESCALATE: float = 0.5
    MAX_SIMILAR_TICKETS: int = 5
    SIMILARITY_THRESHOLD: float = 0.8

    @field_validator("CONFIDENCE_THRESHOLD_AUTO_RESOLVE", "CONFIDENCE_THRESHOLD_ESCALATE")
    @classmethod
    def validate_confidence_thresholds(cls, v: float) -> float:
        """Validate confidence thresholds are within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence thresholds must be between 0.0 and 1.0")
        return v

    @field_validator("SIMILARITY_THRESHOLD")
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        """Validate similarity threshold is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("SIMILARITY_THRESHOLD must be between 0.0 and 1.0")
        return v

    # -------------------------------------------------------------------------
    # Cache Configuration (Redis)
    # -------------------------------------------------------------------------
    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 3600
    CACHE_PREFIX: str = "srs:"

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate Redis URL format if provided."""
        if v and not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v

    # -------------------------------------------------------------------------
    # Logging Configuration
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is supported."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()

    # -------------------------------------------------------------------------
    # Monitoring & Metrics
    # -------------------------------------------------------------------------
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = False
    METRICS_PORT: int = 9090

    @field_validator("SENTRY_DSN")
    @classmethod
    def validate_sentry_dsn(cls, v: Optional[str]) -> Optional[str]:
        """Validate Sentry DSN format if provided."""
        if v and not v.startswith(("https://", "http://")):
            raise ValueError("SENTRY_DSN must be a valid URL")
        return v

    # -------------------------------------------------------------------------
    # Email Configuration
    # -------------------------------------------------------------------------
    RESEND_API_KEY: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    @field_validator("FROM_EMAIL")
    @classmethod
    def validate_from_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format if provided."""
        if v and "@" not in v:
            raise ValueError("FROM_EMAIL must be a valid email address")
        return v

    # -------------------------------------------------------------------------
    # External Services
    # -------------------------------------------------------------------------
    WEBHOOK_URL: Optional[str] = None
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_CHANNEL: str = "#support"

    # -------------------------------------------------------------------------
    # Performance Settings
    # -------------------------------------------------------------------------
    WORKERS: int = 4
    MAX_CONNECTIONS: int = 20
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("WORKERS", "MAX_CONNECTIONS")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate integer is positive."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    # -------------------------------------------------------------------------
    # Support Configuration
    # -------------------------------------------------------------------------
    STATUS_PAGE_URL: str = "https://status.example.com"
    SUPPORT_EMAIL: str = "support@example.com"

    @field_validator("STATUS_PAGE_URL")
    @classmethod
    def validate_status_page_url(cls, v: str) -> str:
        """Validate that STATUS_PAGE_URL is a valid URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("STATUS_PAGE_URL must be a valid HTTP/HTTPS URL")
        return v

    @field_validator("SUPPORT_EMAIL")
    @classmethod
    def validate_support_email(cls, v: str) -> str:
        """Validate that SUPPORT_EMAIL is a valid email address."""
        if "@" not in v:
            raise ValueError("SUPPORT_EMAIL must be a valid email address")
        return v

    # -------------------------------------------------------------------------
    # Development Tools
    # -------------------------------------------------------------------------
    RELOAD: bool = True
    PROFILING_ENABLED: bool = False


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    
    Benefits of caching:
    - Avoid re-reading environment variables
    - Ensure consistent configuration across app
    - Performance optimization for frequent access
    
    Returns:
        Settings: Application settings object
    """
    return Settings()


# Global settings instance used across the app
settings = get_settings()
