"""Configuration management for X-Agent.

This module provides centralized configuration management using Pydantic settings,
supporting environment variables, configuration files, and validation.

Usage:
    from backend.app.core.config import Settings, get_settings

    settings = get_settings()
    print(settings.api_key)
    print(settings.log_level)
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class LogSettings(BaseSettings):
    """Logging configuration.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Log format (plain or json)
        directory: Directory for log files
    """

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="plain", description="Log format (plain or json)")
    directory: Optional[str] = Field(default=None, description="Log directory")

    class Config:
        """Pydantic config."""

        env_prefix = "LOG_"


class DatabaseSettings(BaseSettings):
    """Database configuration.

    Attributes:
        url: Database connection URL
        pool_size: Connection pool size
        max_overflow: Maximum overflow connections
        echo: Enable SQL echo
    """

    url: str = Field(default="postgresql://localhost/xagent", description="Database URL")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    echo: bool = Field(default=False, description="Enable SQL echo")

    class Config:
        """Pydantic config."""

        env_prefix = "DB_"

    @field_validator("pool_size")
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        """Validate pool size."""
        if v < 1:
            raise ValueError("pool_size must be >= 1")
        return v


class CacheSettings(BaseSettings):
    """Cache configuration.

    Attributes:
        enabled: Enable caching
        backend: Cache backend (redis or memory)
        ttl: Default cache TTL in seconds
        redis_url: Redis connection URL
    """

    enabled: bool = Field(default=True, description="Enable caching")
    backend: str = Field(default="redis", description="Cache backend")
    ttl: int = Field(default=3600, description="Default cache TTL")
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")

    class Config:
        """Pydantic config."""

        env_prefix = "CACHE_"

    @field_validator("ttl")
    @classmethod
    def validate_ttl(cls, v: int) -> int:
        """Validate TTL."""
        if v < 0:
            raise ValueError("ttl must be >= 0")
        return v


class ExecutionSettings(BaseSettings):
    """Execution configuration.

    Attributes:
        max_iterations: Maximum execution iterations
        timeout: Execution timeout in seconds
        max_retries: Maximum retry attempts
        backoff_factor: Exponential backoff factor
    """

    max_iterations: int = Field(default=4, description="Max iterations")
    timeout: int = Field(default=300, description="Execution timeout")
    max_retries: int = Field(default=3, description="Max retries")
    backoff_factor: float = Field(default=2.0, description="Backoff factor")

    class Config:
        """Pydantic config."""

        env_prefix = "EXEC_"

    @field_validator("max_iterations", "timeout", "max_retries")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Validate positive values."""
        if v < 1:
            raise ValueError("Value must be >= 1")
        return v

    @field_validator("backoff_factor")
    @classmethod
    def validate_backoff(cls, v: float) -> float:
        """Validate backoff factor."""
        if v < 1.0:
            raise ValueError("backoff_factor must be >= 1.0")
        return v


class SecuritySettings(BaseSettings):
    """Security configuration.

    Attributes:
        api_key: API key for authentication
        secret_key: Secret key for encryption
        enable_cors: Enable CORS
        cors_origins: Allowed CORS origins
    """

    api_key: str = Field(default="", description="API key")
    secret_key: str = Field(default="", description="Secret key")
    enable_cors: bool = Field(default=True, description="Enable CORS")
    cors_origins: list[str] = Field(
        default=["*"], description="Allowed CORS origins"
    )

    class Config:
        """Pydantic config."""

        env_prefix = "SECURITY_"


class Settings(BaseSettings):
    """Main application settings.

    Combines all configuration sections and provides centralized access
    to application configuration.

    Attributes:
        app_name: Application name
        app_version: Application version
        debug: Debug mode
        environment: Environment (development, staging, production)
        log: Logging settings
        database: Database settings
        cache: Cache settings
        execution: Execution settings
        security: Security settings
    """

    app_name: str = Field(default="X-Agent", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment")

    log: LogSettings = Field(default_factory=LogSettings, description="Log settings")
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings, description="Database settings"
    )
    cache: CacheSettings = Field(
        default_factory=CacheSettings, description="Cache settings"
    )
    execution: ExecutionSettings = Field(
        default_factory=ExecutionSettings, description="Execution settings"
    )
    security: SecuritySettings = Field(
        default_factory=SecuritySettings, description="Security settings"
    )

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment."""
        valid_envs = {"development", "staging", "production"}
        if v not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v

    def is_production(self) -> bool:
        """Check if running in production.

        Returns:
            True if environment is production
        """
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development.

        Returns:
            True if environment is development
        """
        return self.environment == "development"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment.

    Returns:
        New Settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
