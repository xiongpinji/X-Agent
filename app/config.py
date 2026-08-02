"""Application configuration settings.

Centralizes environment-based configuration for the REST API. Values are
loaded from environment variables with sensible defaults for local
development and testing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from the environment."""

    app_name: str = "auth-api"
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )
    api_prefix: str = "/api/v1"

    # Security settings
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-me")
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///./auth_api.db"
        )
    )

    # CORS
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
            if origin.strip()
        ]
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Caching avoids re-parsing environment variables on every call.
    """
    return Settings()
