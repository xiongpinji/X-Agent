"""Unit tests for MCP Configuration module.

Tests cover:
- Configuration dataclass creation and validation
- Configuration file loading and saving
- Configuration setters and getters
- Configuration validation
- Error handling and edge cases
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from backend.app.core.mcp.config import (
    MCPClientConfig,
    FileToolConfig,
    SearchToolConfig,
    BrowserToolConfig,
    MCPConfig,
)


class TestMCPClientConfig:
    """Test MCPClientConfig dataclass."""

    def test_mcp_client_config_creation(self):
        """Test creating MCP client configuration."""
        config = MCPClientConfig(server_url="http://localhost:8000")

        assert config.server_url == "http://localhost:8000"
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_backoff_factor == 2.0
        assert config.max_connections == 10
        assert config.cache_ttl_seconds == 300
        assert config.enable_cache is True

    def test_mcp_client_config_custom_values(self):
        """Test creating MCP client config with custom values."""
        config = MCPClientConfig(
            server_url="http://example.com:9000",
            timeout=60.0,
            max_retries=5,
            retry_backoff_factor=3.0,
            max_connections=20,
            cache_ttl_seconds=600,
            enable_cache=False,
        )

        assert config.server_url == "http://example.com:9000"
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.retry_backoff_factor == 3.0
        assert config.max_connections == 20
        assert config.cache_ttl_seconds == 600
        assert config.enable_cache is False


class TestFileToolConfig:
    """Test FileToolConfig dataclass."""

    def test_file_tool_config_creation(self):
        """Test creating file tool configuration."""
        config = FileToolConfig(base_path="/home/user/documents")

        assert config.base_path == "/home/user/documents"
        assert config.enable_audit is True
        assert config.max_audit_entries == 1000
        assert config.permissions["read"] is True
        assert config.permissions["write"] is True
        assert config.permissions["delete"] is True
        assert config.permissions["list"] is True

    def test_file_tool_config_custom_permissions(self):
        """Test file tool config with custom permissions."""
        config = FileToolConfig(
            base_path="/data",
            enable_audit=False,
            max_audit_entries=500,
            permissions={
                "read": True,
                "write": False,
                "delete": False,
                "list": True,
            },
        )

        assert config.base_path == "/data"
        assert config.enable_audit is False
        assert config.max_audit_entries == 500
        assert config.permissions["write"] is False
        assert config.permissions["delete"] is False

    def test_file_tool_config_default_permissions(self):
        """Test that file tool config has default permissions."""
        config = FileToolConfig(base_path="/tmp")

        assert isinstance(config.permissions, dict)
        assert len(config.permissions) == 4
        assert all(isinstance(v, bool) for v in config.permissions.values())


class TestSearchToolConfig:
    """Test SearchToolConfig dataclass."""

    def test_search_tool_config_creation(self):
        """Test creating search tool configuration."""
        config = SearchToolConfig()

        assert config.api_key is None
        assert config.search_engine_id is None
        assert config.enable_audit is True
        assert config.max_audit_entries == 1000
        assert config.permissions["web_search"] is True
        assert config.permissions["news_search"] is True

    def test_search_tool_config_with_credentials(self):
        """Test search tool config with API credentials."""
        config = SearchToolConfig(
            api_key="test_api_key",
            search_engine_id="test_engine_id",
        )

        assert config.api_key == "test_api_key"
        assert config.search_engine_id == "test_engine_id"

    def test_search_tool_config_custom_permissions(self):
        """Test search tool config with custom permissions."""
        config = SearchToolConfig(
            permissions={
                "web_search": True,
                "news_search": False,
            }
        )

        assert config.permissions["web_search"] is True
        assert config.permissions["news_search"] is False

    def test_search_tool_config_default_permissions(self):
        """Test that search tool config has default permissions."""
        config = SearchToolConfig()

        assert isinstance(config.permissions, dict)
        assert len(config.permissions) == 2


class TestBrowserToolConfig:
    """Test BrowserToolConfig dataclass."""

    def test_browser_tool_config_creation(self):
        """Test creating browser tool configuration."""
        config = BrowserToolConfig()

        assert config.enable_audit is True
        assert config.max_audit_entries == 1000
        assert config.permissions["navigate"] is True
        assert config.permissions["click"] is True
        assert config.permissions["type"] is True
        assert config.permissions["screenshot"] is True
        assert config.permissions["scroll"] is True
        assert config.permissions["wait"] is True
        assert config.permissions["get_page_content"] is True
        assert config.permissions["execute_script"] is False

    def test_browser_tool_config_custom_permissions(self):
        """Test browser tool config with custom permissions."""
        config = BrowserToolConfig(
            permissions={
                "navigate": True,
                "click": True,
                "type": False,
                "screenshot": True,
                "scroll": True,
                "wait": True,
                "get_page_content": True,
                "execute_script": False,
            }
        )

        assert config.permissions["type"] is False

    def test_browser_tool_config_default_permissions(self):
        """Test that browser tool config has default permissions."""
        config = BrowserToolConfig()

        assert isinstance(config.permissions, dict)
        assert len(config.permissions) == 8


class TestMCPConfigCreation:
    """Test MCPConfig initialization."""

    def test_mcp_config_creation_no_path(self):
        """Test creating MCPConfig without path."""
        config = MCPConfig()

        assert config.config_path is None
        assert config.mcp_client_config is None
        assert config.file_tool_config is None
        assert config.search_tool_config is None
        assert config.browser_tool_config is None
        assert config.created_at is not None

    def test_mcp_config_creation_with_path(self, tmp_path):
        """Test creating MCPConfig with path."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        config = MCPConfig(str(config_file))

        assert config.config_path == config_file

    def test_mcp_config_auto_load_existing_file(self, tmp_path):
        """Test that MCPConfig auto-loads existing file."""
        config_data = {
            "mcp_client": {
                "server_url": "http://localhost:8000",
                "timeout": 45.0,
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        config = MCPConfig(str(config_file))

        assert config.mcp_client_config is not None
        assert config.mcp_client_config.server_url == "http://localhost:8000"
        assert config.mcp_client_config.timeout == 45.0

    def test_mcp_config_no_auto_load_nonexistent_file(self):
        """Test that MCPConfig doesn't fail for non-existent file."""
        config = MCPConfig("/nonexistent/path.json")

        assert config.config_path is not None
        assert config.mcp_client_config is None


class TestLoadFromFile:
    """Test loading configuration from file."""

    def test_load_from_file_success(self, tmp_path):
        """Test successfully loading configuration from file."""
        config_data = {
            "mcp_client": {
                "server_url": "http://localhost:8000",
                "timeout": 30.0,
            },
            "file_tool": {
                "base_path": "/home/user",
                "enable_audit": True,
            },
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        config = MCPConfig()
        config.config_path = config_file
        config.load_from_file()

        assert config.mcp_client_config is not None
        assert config.file_tool_config is not None

    def test_load_from_file_not_found(self):
        """Test loading from non-existent file."""
        config = MCPConfig()
        config.config_path = Path("/nonexistent/config.json")

        config.load_from_file()

        assert config.mcp_client_config is None

    def test_load_from_file_no_path(self):
        """Test loading when no path is set."""
        config = MCPConfig()

        config.load_from_file()

        assert config.mcp_client_config is None

    def test_load_from_file_invalid_json(self, tmp_path):
        """Test loading invalid JSON file."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("invalid json content {")

        config = MCPConfig()
        config.config_path = config_file

        config.load_from_file()

        assert config.mcp_client_config is None

    def test_load_from_file_all_configs(self, tmp_path):
        """Test loading all configuration types."""
        config_data = {
            "mcp_client": {
                "server_url": "http://localhost:8000",
            },
            "file_tool": {
                "base_path": "/data",
            },
            "search_tool": {
                "api_key": "test_key",
            },
            "browser_tool": {
                "enable_audit": False,
            },
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        config = MCPConfig()
        config.config_path = config_file
        config.load_from_file()

        assert config.mcp_client_config is not None
        assert config.file_tool_config is not None
        assert config.search_tool_config is not None
        assert config.browser_tool_config is not None


class TestSaveToFile:
    """Test saving configuration to file."""

    def test_save_to_file_success(self, tmp_path):
        """Test successfully saving configuration to file."""
        config_file = tmp_path / "config.json"

        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.set_file_tool_config(base_path="/data")

        config.save_to_file(str(config_file))

        assert config_file.exists()

        saved_data = json.loads(config_file.read_text())
        assert "mcp_client" in saved_data
        assert "file_tool" in saved_data

    def test_save_to_file_no_path(self):
        """Test saving when no path is specified."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")

        config.save_to_file()

        # Should not raise exception

    def test_save_to_file_creates_directory(self, tmp_path):
        """Test that save_to_file creates parent directories."""
        config_file = tmp_path / "subdir" / "config.json"

        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")

        config.save_to_file(str(config_file))

        assert config_file.exists()

    def test_save_to_file_overwrites_existing(self, tmp_path):
        """Test that save_to_file overwrites existing file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"old": "data"}')

        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")

        config.save_to_file(str(config_file))

        saved_data = json.loads(config_file.read_text())
        assert "old" not in saved_data
        assert "mcp_client" in saved_data

    def test_save_to_file_all_configs(self, tmp_path):
        """Test saving all configuration types."""
        config_file = tmp_path / "config.json"

        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.set_file_tool_config(base_path="/data")
        config.set_search_tool_config(api_key="test_key")
        config.set_browser_tool_config(enable_audit=False)

        config.save_to_file(str(config_file))

        saved_data = json.loads(config_file.read_text())
        assert "mcp_client" in saved_data
        assert "file_tool" in saved_data
        assert "search_tool" in saved_data
        assert "browser_tool" in saved_data


class TestConfigSetters:
    """Test configuration setters."""

    def test_set_mcp_client_config(self):
        """Test setting MCP client configuration."""
        config = MCPConfig()

        config.set_mcp_client_config(
            server_url="http://localhost:8000",
            timeout=60.0,
        )

        assert config.mcp_client_config is not None
        assert config.mcp_client_config.server_url == "http://localhost:8000"
        assert config.mcp_client_config.timeout == 60.0

    def test_set_file_tool_config(self):
        """Test setting file tool configuration."""
        config = MCPConfig()

        config.set_file_tool_config(
            base_path="/data",
            enable_audit=False,
        )

        assert config.file_tool_config is not None
        assert config.file_tool_config.base_path == "/data"
        assert config.file_tool_config.enable_audit is False

    def test_set_search_tool_config(self):
        """Test setting search tool configuration."""
        config = MCPConfig()

        config.set_search_tool_config(
            api_key="test_key",
            search_engine_id="test_engine",
        )

        assert config.search_tool_config is not None
        assert config.search_tool_config.api_key == "test_key"
        assert config.search_tool_config.search_engine_id == "test_engine"

    def test_set_browser_tool_config(self):
        """Test setting browser tool configuration."""
        config = MCPConfig()

        config.set_browser_tool_config(enable_audit=False)

        assert config.browser_tool_config is not None
        assert config.browser_tool_config.enable_audit is False

    def test_set_config_overwrites_previous(self):
        """Test that setting config overwrites previous value."""
        config = MCPConfig()

        config.set_mcp_client_config(server_url="http://localhost:8000")
        assert config.mcp_client_config.server_url == "http://localhost:8000"

        config.set_mcp_client_config(server_url="http://example.com:9000")
        assert config.mcp_client_config.server_url == "http://example.com:9000"


class TestGetConfigDict:
    """Test getting configuration as dictionary."""

    def test_get_config_dict_empty(self):
        """Test getting config dict when no configs are set."""
        config = MCPConfig()

        config_dict = config.get_config_dict()

        assert "created_at" in config_dict
        assert "mcp_client" not in config_dict

    def test_get_config_dict_with_configs(self):
        """Test getting config dict with all configs set."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.set_file_tool_config(base_path="/data")
        config.set_search_tool_config(api_key="test_key")
        config.set_browser_tool_config(enable_audit=False)

        config_dict = config.get_config_dict()

        assert "created_at" in config_dict
        assert "mcp_client" in config_dict
        assert "file_tool" in config_dict
        assert "search_tool" in config_dict
        assert "browser_tool" in config_dict

    def test_get_config_dict_partial(self):
        """Test getting config dict with partial configs."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.set_file_tool_config(base_path="/data")

        config_dict = config.get_config_dict()

        assert "mcp_client" in config_dict
        assert "file_tool" in config_dict
        assert "search_tool" not in config_dict
        assert "browser_tool" not in config_dict


class TestValidateConfig:
    """Test configuration validation."""

    def test_validate_empty_config(self):
        """Test validating empty configuration."""
        config = MCPConfig()

        is_valid, errors = config.validate()

        assert is_valid is False
        assert len(errors) > 0

    def test_validate_missing_mcp_client(self):
        """Test validation when MCP client config is missing."""
        config = MCPConfig()
        config.set_file_tool_config(base_path="/data")

        is_valid, errors = config.validate()

        assert is_valid is False
        assert any("MCP client" in error for error in errors)

    def test_validate_missing_file_tool(self):
        """Test validation when file tool config is missing."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")

        is_valid, errors = config.validate()

        assert is_valid is False
        assert any("File tool" in error for error in errors)

    def test_validate_missing_server_url(self):
        """Test validation when server URL is missing."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="")
        config.set_file_tool_config(base_path="/data")

        is_valid, errors = config.validate()

        assert is_valid is False
        assert any("server URL" in error for error in errors)

    def test_validate_missing_base_path(self):
        """Test validation when base path is missing."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.set_file_tool_config(base_path="")

        is_valid, errors = config.validate()

        assert is_valid is False
        assert any("base path" in error for error in errors)

    def test_validate_valid_config(self):
        """Test validating a valid configuration."""
        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.set_file_tool_config(base_path="/data")

        is_valid, errors = config.validate()

        assert is_valid is True
        assert len(errors) == 0


class TestConfigRepr:
    """Test configuration string representation."""

    def test_config_repr(self):
        """Test string representation of MCPConfig."""
        config = MCPConfig()

        repr_str = repr(config)

        assert "MCPConfig" in repr_str
        assert "created_at" in repr_str

    def test_config_repr_contains_timestamp(self):
        """Test that repr contains timestamp."""
        config = MCPConfig()

        repr_str = repr(config)

        assert config.created_at in repr_str


class TestConfigIntegration:
    """Integration tests for configuration."""

    def test_config_roundtrip(self, tmp_path):
        """Test saving and loading configuration."""
        config_file = tmp_path / "config.json"

        # Create and save config
        config1 = MCPConfig()
        config1.set_mcp_client_config(
            server_url="http://localhost:8000",
            timeout=45.0,
        )
        config1.set_file_tool_config(
            base_path="/data",
            enable_audit=False,
        )
        config1.save_to_file(str(config_file))

        # Load config
        config2 = MCPConfig(str(config_file))

        # Verify
        assert config2.mcp_client_config.server_url == "http://localhost:8000"
        assert config2.mcp_client_config.timeout == 45.0
        assert config2.file_tool_config.base_path == "/data"
        assert config2.file_tool_config.enable_audit is False

    def test_config_modification_and_save(self, tmp_path):
        """Test modifying and saving configuration."""
        config_file = tmp_path / "config.json"

        config = MCPConfig()
        config.set_mcp_client_config(server_url="http://localhost:8000")
        config.save_to_file(str(config_file))

        # Modify
        config.set_mcp_client_config(server_url="http://example.com:9000")
        config.save_to_file(str(config_file))

        # Load and verify
        config2 = MCPConfig(str(config_file))
        assert config2.mcp_client_config.server_url == "http://example.com:9000"
