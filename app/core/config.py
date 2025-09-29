"""Application configuration."""

import os
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    All settings can be overridden with environment variables.
    """

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "OpChat"

    # Critical settings (must be provided)
    JWT_SECRET_KEY: str
    APP_DATABASE_URL: str
    REDIS_URL: str

    # Database URLs
    ADMIN_DATABASE_URL: str = os.getenv("ADMIN_DATABASE_URL", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    APP_DB_PASSWORD: str = os.getenv("APP_DB_PASSWORD", "")

    # JWT
    ALGORITHM: str = os.getenv("ALGORITHM", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "0")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "0"))

    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "")
    API_PORT: int = int(os.getenv("API_PORT", "0"))
    API_RELOAD: bool = os.getenv("API_RELOAD", "").lower() == "true"

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "")
    DEBUG: bool = os.getenv("DEBUG", "").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "")

    # Caching
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "0"))
    REDIS_TTL_SECONDS: int = int(os.getenv("REDIS_TTL_SECONDS", "0"))

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0"))
    AUTH_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("AUTH_RATE_LIMIT_PER_MINUTE", "0"))

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables
    )

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

        # Validate critical settings
        critical_settings = [
            ("JWT_SECRET_KEY", self.JWT_SECRET_KEY),
            ("APP_DATABASE_URL", self.APP_DATABASE_URL),
            ("REDIS_URL", self.REDIS_URL),
        ]

        missing_settings = [name for name, value in critical_settings if not value]
        if missing_settings:
            raise ValueError(
                f"Critical settings missing: {', '.join(missing_settings)}"
            )


# Create global settings instance
settings = Settings()

# Validate required settings in production
if os.getenv("ENVIRONMENT") == "production":
    assert settings.JWT_SECRET_KEY, "JWT_SECRET_KEY must be set in production"
    # Additional production validations can be added here
