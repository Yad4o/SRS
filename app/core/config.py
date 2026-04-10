"""
app/core/config.py

Purpose:
Centralized configuration management for the application.
All environment variables and settings are defined here.

Responsibilities:
- Load environment variables
- Define application settings
- Provide a cached settings object

DO NOT:
- Write business logic here
- Access database directly
- Hardcode secrets
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# Define allowed roles for security
ALLOWED_ROLES = {"user", "agent", "admin"}

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Uses pydantic-settings to read values from a `.env` file
    or system environment. Values are loaded once and cached.

    Reference: docs/specification/TECHNICAL_SPEC.md § 12. Configuration Management
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra env vars to avoid validation errors
    )

    # -------------------------------------------------
    # Application Settings
    # -------------------------------------------------
    APP_NAME: str = "Automated Customer Support Resolution System"
    ENV: str = "development"  # development | staging | production
    DEBUG: bool = True
    APP_VERSION: str = "1.0.0"

    # -------------------------------------------------
    # Security / Authentication
    # -------------------------------------------------
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"
    CORS_ORIGINS: list[str] = []
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

    # -------------------------------------------------
    # Database
    # -------------------------------------------------
    DATABASE_URL: str
    """
    Example values:
    - SQLite: sqlite:///./support.db
    - Postgres: postgresql://user:password@localhost/dbname
    """
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # -------------------------------------------------
    # AI / NLP Configuration
    # -------------------------------------------------
    AI_PROVIDER: str = "openai"  # openai | spacy
    OPENAI_API_KEY: str | None = None
    RESEND_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 8
    OPENAI_MAX_TOKENS: int = 200
    SIMILARITY_THRESHOLD: float = 0.7
    MAX_SIMILAR_TICKETS_TO_CHECK: int = 100
    
    # -------------------------------------------------
    # Decision Engine (Technical Spec § 9.4)
    # -------------------------------------------------
    CONFIDENCE_THRESHOLD_AUTO_RESOLVE: float = 0.75
    """
    Minimum confidence score (0.0-1.0) to auto-resolve a ticket.
    Below this threshold, tickets are escalated to human agents.
    Safety-first: any uncertainty → escalate.
    """
    
    @field_validator("CONFIDENCE_THRESHOLD_AUTO_RESOLVE")
    @classmethod
    def validate_confidence_threshold(cls, v: float):
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                "CONFIDENCE_THRESHOLD_AUTO_RESOLVE must be between 0.0 and 1.0"
            )
        return v

    # -------------------------------------------------
    # Logging & Monitoring
    # -------------------------------------------------
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str | None = None
    
    # -------------------------------------------------
    # Cache / Queue (Optional)
    # -------------------------------------------------
    REDIS_URL: str | None = None

    # -------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # -------------------------------------------------
    # Support Configuration
    # -------------------------------------------------
    STATUS_PAGE_URL: str = "https://status.example.com"
    SUPPORT_EMAIL: str = "support@example.com"
    
    @field_validator("STATUS_PAGE_URL")
    @classmethod
    def validate_status_page_url(cls, v: str) -> str:
        """Validate that STATUS_PAGE_URL is a valid URL."""
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError("STATUS_PAGE_URL must be a valid HTTP/HTTPS URL")
        return v
    
    @field_validator("SUPPORT_EMAIL")
    @classmethod
    def validate_support_email(cls, v: str) -> str:
        """Validate that SUPPORT_EMAIL is a valid email address."""
        if not v or '@' not in v:
            raise ValueError("SUPPORT_EMAIL must be a valid email address")
        return v

@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    Why cache?
    - Avoid re-reading environment variables
    - Ensure consistent configuration across app

    Returns:
        Settings: Application settings object
    """
    return Settings()


# Global settings instance used across the app
settings = get_settings()

