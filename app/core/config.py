"""
app/core/config.py

Purpose:
--------
Centralized configuration management for the application.
All environment variables and settings are defined here.

Owner:
------
Om (Backend / System)

Responsibilities:
-----------------
- Load environment variables
- Define application settings
- Provide a cached settings object

DO NOT:
-------
- Write business logic here
- Access database directly
- Hardcode secrets
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # -------------------------------------------------
    # Security / Authentication
    # -------------------------------------------------
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # -------------------------------------------------
    # Database
    # -------------------------------------------------
    DATABASE_URL: str
    """
    Example values:
    - SQLite: sqlite:///./support.db
    - Postgres: postgresql://user:password@localhost/dbname
    """

    # -------------------------------------------------
    # AI / NLP Configuration
    # -------------------------------------------------
    AI_PROVIDER: str = "openai"  # openai | spacy
    OPENAI_API_KEY: str | None = None

    # -------------------------------------------------
    # Decision Engine (Technical Spec § 9.4)
    # -------------------------------------------------
    CONFIDENCE_THRESHOLD_AUTO_RESOLVE: float = 0.75
    """
    Minimum confidence score (0.0–1.0) to auto-resolve a ticket.
    Below this threshold, tickets are escalated to human agents.
    Safety-first: any uncertainty → escalate.
    """

    # -------------------------------------------------
    # Cache / Queue (Optional)
    # -------------------------------------------------
    REDIS_URL: str | None = None


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.

    Why cache?
    ----------
    - Avoid re-reading environment variables
    - Ensure consistent configuration across app

    Returns:
        Settings: Application settings object
    """
    return Settings()


# Global settings instance used across the app
settings = get_settings()
