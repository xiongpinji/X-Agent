"""MCP configuration management."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPClientConfig:
    """MCP client configuration."""

    server_url: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    max_connections: int = 10
    cache_ttl_seconds: int = 300
    enable_cache: bool = True


@dataclass
class FileToolConfig:
    """File tool configuration."""

    base_path: str
    enable_audit: bool = True
    max_audit_entries: int = 1000
    permissions: dict[str, bool] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = {
                "read": True,
                "write": True,
                "delete": True,
                "list": True,
            }


@dataclass
class SearchToolConfig:
    """Search tool configuration."""

    api_key: str | None = None
    search_engine_id: str | None = None
    enable_audit: bool = True
    max_audit_entries: int = 1000
    permissions: dict[str, bool] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = {
                "web_search": True,
                "news_search": True,
            }


@dataclass
class BrowserToolConfig:
    """Browser tool configuration."""

    enable_audit: bool = True
    max_audit_entries: int = 1000
    permissions: dict[str, bool] = None

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = {
                "navigate": True,
                "click": True,
                "type": True,
                "screenshot": True,
                "scroll": True,
                "wait": True,
                "get_page_content": True,
                "execute_script": False,
            }


class MCPConfig:
    """MCP configuration manager."""

    def __init__(self, config_path: str | None = None):
        """Initialize MCP configuration.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path) if config_path else None
        self.mcp_client_config: MCPClientConfig | None = None
        self.file_tool_config: FileToolConfig | None = None
        self.search_tool_config: SearchToolConfig | None = None
        self.browser_tool_config: BrowserToolConfig | None = None
        self.created_at = datetime.now().isoformat()

        if self.config_path and self.config_path.exists():
            self.load_from_file()

    def load_from_file(self) -> None:
        """Load configuration from file."""
        if not self.config_path or not self.config_path.exists():
            logger.warning("Configuration file not found")
            return

        try:
            with open(self.config_path) as f:
                data = json.load(f)

            if "mcp_client" in data:
                self.mcp_client_config = MCPClientConfig(**data["mcp_client"])

            if "file_tool" in data:
                self.file_tool_config = FileToolConfig(**data["file_tool"])

            if "search_tool" in data:
                self.search_tool_config = SearchToolConfig(**data["search_tool"])

            if "browser_tool" in data:
                self.browser_tool_config = BrowserToolConfig(**data["browser_tool"])

            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")

    def save_to_file(self, path: str | None = None) -> None:
        """Save configuration to file.

        Args:
            path: Path to save configuration to
        """
        save_path = Path(path) if path else self.config_path
        if not save_path:
            logger.warning("No configuration path specified")
            return

        try:
            data = {}

            if self.mcp_client_config:
                data["mcp_client"] = asdict(self.mcp_client_config)

            if self.file_tool_config:
                data["file_tool"] = asdict(self.file_tool_config)

            if self.search_tool_config:
                data["search_tool"] = asdict(self.search_tool_config)

            if self.browser_tool_config:
                data["browser_tool"] = asdict(self.browser_tool_config)

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def set_mcp_client_config(self, **kwargs) -> None:
        """Set MCP client configuration.

        Args:
            **kwargs: Configuration parameters
        """
        self.mcp_client_config = MCPClientConfig(**kwargs)

    def set_file_tool_config(self, **kwargs) -> None:
        """Set file tool configuration.

        Args:
            **kwargs: Configuration parameters
        """
        self.file_tool_config = FileToolConfig(**kwargs)

    def set_search_tool_config(self, **kwargs) -> None:
        """Set search tool configuration.

        Args:
            **kwargs: Configuration parameters
        """
        self.search_tool_config = SearchToolConfig(**kwargs)

    def set_browser_tool_config(self, **kwargs) -> None:
        """Set browser tool configuration.

        Args:
            **kwargs: Configuration parameters
        """
        self.browser_tool_config = BrowserToolConfig(**kwargs)

    def get_config_dict(self) -> dict[str, Any]:
        """Get configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        config = {
            "created_at": self.created_at,
        }

        if self.mcp_client_config:
            config["mcp_client"] = asdict(self.mcp_client_config)

        if self.file_tool_config:
            config["file_tool"] = asdict(self.file_tool_config)

        if self.search_tool_config:
            config["search_tool"] = asdict(self.search_tool_config)

        if self.browser_tool_config:
            config["browser_tool"] = asdict(self.browser_tool_config)

        return config

    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration.

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []

        if not self.mcp_client_config:
            errors.append("MCP client configuration not set")
        elif not self.mcp_client_config.server_url:
            errors.append("MCP server URL not configured")

        if not self.file_tool_config:
            errors.append("File tool configuration not set")
        elif not self.file_tool_config.base_path:
            errors.append("File tool base path not configured")

        return len(errors) == 0, errors

    def __repr__(self) -> str:
        """String representation."""
        return f"MCPConfig(created_at={self.created_at})"
