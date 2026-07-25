"""Base configuration module with environment detection and common settings."""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Application environment enumeration."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class BaseConfig(BaseSettings):
    """Base configuration class with common settings for all environments."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="XAGENT_",
        case_sensitive=False,
    )

    # Application metadata
    app_name: str = Field(default="X-Agent", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment (development/test/production)",
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # Project paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4],
        description="Project root directory",
    )
    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4] / "data",
        description="Data directory for storage",
    )
    logs_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[4] / "logs",
        description="Logs directory",
    )

    # API configuration
    api_title: str = Field(default="X-Agent API", description="API title")
    api_version: str = Field(default="0.1.0", description="API version")
    api_description: str = Field(default="X-Agent Core API", description="API description")

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> Environment:
        """Validate and normalize environment value."""
        if isinstance(v, Environment):
            return v
        try:
            return Environment(v.lower())
        except ValueError:
            raise ValueError(
                f"Invalid environment: {v}. Must be one of: "
                f"{', '.join([e.value for e in Environment])}"
            )

    @field_validator("project_root", "data_dir", "logs_dir", mode="before")
    @classmethod
    def ensure_path_exists(cls, v: Path) -> Path:
        """Ensure path exists and is a directory."""
        if isinstance(v, str):
            v = Path(v)
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    def is_test(self) -> bool:
        """Check if running in test environment."""
        return self.environment == Environment.TEST
