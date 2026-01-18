from functools import lru_cache
from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.
    """

    # -----------------------------
    # Application
    # -----------------------------
    APP_NAME: str = "Automated Customer Support Resolution System"
    ENV: str = "development"
    DEBUG: bool = True

    # -----------------------------
    # Security
    # -----------------------------
    SECRET_KEY: str  # TODO: generate strong key
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # -----------------------------
    # Database
    # -----------------------------
    DATABASE_URL: str  # TODO: sqlite / postgres url

    # -----------------------------
    # AI / NLP
    # -----------------------------
    AI_PROVIDER: str = "openai"  # openai | spacy
    OPENAI_API_KEY: str | None = None

    # -----------------------------
    # Cache / Queue (optional)
    # -----------------------------
    REDIS_URL: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.
    """
    return Settings()


# Export settings instance
settings = get_settings()
