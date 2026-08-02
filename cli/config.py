"""CLI configuration management.

Handles loading and saving CLI configuration with support for multiple sources:
- Command-line parameters (highest priority)
- Environment variables
- Configuration file (~/.xagent/config.toml)
- Default values (lowest priority)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class CLIConfig(BaseSettings):
    """CLI configuration model with environment variable and file support."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="XAGENT_",
        extra="ignore",
    )

    api_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for X-Agent API",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for authentication (optional)",
    )
    mode: Literal["http", "local"] = Field(
        default="http",
        description="Client mode: 'http' for remote API, 'local' for direct import",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )
    output_format: Literal["rich", "json", "plain"] = Field(
        default="rich",
        description="Output format: 'rich' for formatted, 'json' for JSON, 'plain' for text",
    )

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Ensure timeout is positive."""
        if v <= 0:
            raise ValueError("timeout must be positive")
        return v

    @field_validator("api_base_url")
    @classmethod
    def validate_api_url(cls, v: str) -> str:
        """Ensure API URL is valid."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("api_base_url must start with http:// or https://")
        return v

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use only explicitly-passed init values as the settings source.

        ``load_config`` already merges file < env < CLI params and passes the
        result as init kwargs. Without this override, ``BaseSettings`` would
        additionally re-read ``XAGENT_*`` env vars (e.g. ``XAGENT_TIMEOUT``)
        and raise on values ``load_config`` intentionally discarded. Making
        init the sole source keeps ``load_config`` the single source of truth.
        """
        return (init_settings,)


def _get_config_file_path() -> Path:
    """Get the path to the CLI config file.

    Returns:
        Path to ~/.xagent/config.toml. If the home directory cannot be
        determined (e.g. environment lacks HOME/USERPROFILE), falls back to
        a ``.xagent`` directory under the current working directory so config
        loading degrades gracefully instead of raising.
    """
    try:
        home = Path.home()
    except (RuntimeError, OSError):
        home = Path.cwd()
    config_dir = home / ".xagent"
    return config_dir / "config.toml"


def _load_from_file(path: Path) -> dict[str, object]:
    """Load configuration from TOML file.

    Args:
        path: Path to config file

    Returns:
        Dictionary of configuration values
    """
    if not path.exists():
        return {}

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
            return data.get("xagent", {})
    except Exception:
        return {}


def load_config(
    api_base_url: str | None = None,
    api_key: str | None = None,
    mode: str | None = None,
    timeout: int | None = None,
    output_format: str | None = None,
) -> CLIConfig:
    """Load CLI configuration with priority order.

    Priority (highest to lowest):
    1. Command-line parameters (function arguments)
    2. Environment variables (XAGENT_*)
    3. Configuration file (~/.xagent/config.toml)
    4. Default values

    Args:
        api_base_url: Override API base URL
        api_key: Override API key
        mode: Override client mode
        timeout: Override timeout
        output_format: Override output format

    Returns:
        CLIConfig instance with merged configuration
    """
    # Load from file
    config_file = _get_config_file_path()
    file_config = _load_from_file(config_file)

    # Load from environment
    env_config = {
        "api_base_url": os.getenv("XAGENT_API_BASE_URL"),
        "api_key": os.getenv("XAGENT_API_KEY"),
        "mode": os.getenv("XAGENT_MODE"),
        "timeout": os.getenv("XAGENT_TIMEOUT"),
        "output_format": os.getenv("XAGENT_OUTPUT_FORMAT"),
    }

    # Merge: file < env < params
    merged = {**file_config}
    for key, value in env_config.items():
        if value is not None:
            merged[key] = value

    # Apply command-line overrides
    if api_base_url is not None:
        merged["api_base_url"] = api_base_url
    if api_key is not None:
        merged["api_key"] = api_key
    if mode is not None:
        merged["mode"] = mode
    if timeout is not None:
        merged["timeout"] = timeout
    if output_format is not None:
        merged["output_format"] = output_format

    # Convert timeout to int if it's a string; drop if invalid so default applies
    if isinstance(merged.get("timeout"), str):
        try:
            merged["timeout"] = int(merged["timeout"])
        except ValueError:
            merged.pop("timeout", None)

    return CLIConfig(**merged)


def save_config(config: CLIConfig) -> None:
    """Save CLI configuration to file.

    Creates ~/.xagent/config.toml with current configuration.

    Args:
        config: CLIConfig instance to save
    """
    config_file = _get_config_file_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)

    import tomli_w as toml_writer  # type: ignore

    data = {
        "xagent": {
            "api_base_url": config.api_base_url,
            # TOML has no null type; represent an unset api_key as an empty
            # string so the key is still written and the file stays valid.
            "api_key": config.api_key if config.api_key is not None else "",
            "mode": config.mode,
            "timeout": config.timeout,
            "output_format": config.output_format,
        }
    }

    with open(config_file, "wb") as f:
        toml_writer.dump(data, f)
