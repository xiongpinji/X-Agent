"""
X-Agent Local Configuration Management

Handles configuration for local endpoint, sync, encryption, and caching.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LocalConfig:
    """Local endpoint configuration."""

    # Database
    db_path: str = "~/.xagent/local.db"
    db_timeout: float = 30.0
    db_enable_wal: bool = True
    db_enable_foreign_keys: bool = True

    # Sync
    sync_enabled: bool = True
    sync_interval_seconds: int = 300  # 5 minutes
    sync_batch_size: int = 100
    sync_max_retries: int = 3
    sync_retry_delay_seconds: int = 60
    sync_timeout_seconds: int = 30
    sync_default_strategy: str = "last_write_wins"

    # Encryption
    encryption_enabled: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    encryption_key_size: int = 32
    encryption_iterations: int = 100000

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size_mb: int = 100
    cache_cleanup_interval_seconds: int = 600

    # Offline
    offline_queue_enabled: bool = True
    offline_queue_max_size: int = 10000

    # Preload
    preload_enabled: bool = True
    preload_batch_size: int = 50
    preload_priority_threshold: float = 0.5

    # Monitoring
    monitoring_enabled: bool = True
    monitoring_log_level: str = "INFO"
    monitoring_metrics_enabled: bool = True

    # Cloud API
    cloud_api_url: str = "http://localhost:8000"
    cloud_api_timeout: int = 30
    cloud_api_retry_count: int = 3

    # Security
    security_enable_tls: bool = True
    security_verify_ssl: bool = True
    security_api_key_encryption: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Configuration dictionary
        """
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocalConfig:
        """Create from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            LocalConfig instance
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, json_str: str) -> LocalConfig:
        """Create from JSON string.

        Args:
            json_str: JSON string

        Returns:
            LocalConfig instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, file_path: str | Path) -> LocalConfig:
        """Load from file.

        Args:
            file_path: Path to configuration file

        Returns:
            LocalConfig instance
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning(f"Config file not found: {file_path}, using defaults")
            return cls()

        with open(file_path, "r") as f:
            if file_path.suffix == ".json":
                return cls.from_json(f.read())
            else:
                raise ValueError(f"Unsupported config format: {file_path.suffix}")

    def save_to_file(self, file_path: str | Path) -> None:
        """Save to file.

        Args:
            file_path: Path to save configuration
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            f.write(self.to_json())

        logger.info(f"Configuration saved to {file_path}")


class ConfigManager:
    """Manages local configuration."""

    _instance: Optional[ConfigManager] = None
    _config: Optional[LocalConfig] = None

    def __new__(cls) -> ConfigManager:
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize config manager."""
        if self._config is None:
            self._config = LocalConfig()

    @classmethod
    def initialize(cls, config: Optional[LocalConfig] = None) -> None:
        """Initialize configuration.

        Args:
            config: Configuration instance
        """
        manager = cls()
        if config:
            manager._config = config
        else:
            manager._config = LocalConfig()

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> None:
        """Load configuration from file.

        Args:
            file_path: Path to configuration file
        """
        manager = cls()
        manager._config = LocalConfig.from_file(file_path)
        logger.info(f"Configuration loaded from {file_path}")

    @classmethod
    def get_config(cls) -> LocalConfig:
        """Get current configuration.

        Returns:
            LocalConfig instance
        """
        manager = cls()
        if manager._config is None:
            manager._config = LocalConfig()
        return manager._config

    @classmethod
    def update_config(cls, **kwargs: Any) -> None:
        """Update configuration.

        Args:
            **kwargs: Configuration updates
        """
        manager = cls()
        config = manager.get_config()

        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                logger.warning(f"Unknown configuration key: {key}")

    @classmethod
    def save_config(cls, file_path: str | Path) -> None:
        """Save configuration to file.

        Args:
            file_path: Path to save configuration
        """
        manager = cls()
        config = manager.get_config()
        config.save_to_file(file_path)


# Default configuration file locations
DEFAULT_CONFIG_PATHS = [
    Path.home() / ".xagent" / "config.json",
    Path.cwd() / "xagent.config.json",
    Path("/etc/xagent/config.json"),
]


def load_default_config() -> LocalConfig:
    """Load default configuration from standard locations.

    Returns:
        LocalConfig instance
    """
    for config_path in DEFAULT_CONFIG_PATHS:
        if config_path.exists():
            logger.info(f"Loading configuration from {config_path}")
            return LocalConfig.from_file(config_path)

    logger.info("No configuration file found, using defaults")
    return LocalConfig()
