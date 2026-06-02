"""Unit tests for CLI configuration management.

Tests CLIConfig pydantic model, load_config priority handling,
save_config persistence, and field validation.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.config import (
    CLIConfig,
    _get_config_file_path,
    _load_from_file,
    load_config,
    save_config,
)


class TestCLIConfig:
    """Test CLIConfig pydantic model."""

    def test_default_values(self):
        """Test CLIConfig initializes with correct defaults."""
        config = CLIConfig()
        assert config.api_base_url == "http://localhost:8000"
        assert config.api_key is None
        assert config.mode == "http"
        assert config.timeout == 30
        assert config.output_format == "rich"

    def test_api_base_url_validation_http(self):
        """Test api_base_url accepts valid http URL."""
        config = CLIConfig(api_base_url="http://example.com")
        assert config.api_base_url == "http://example.com"

    def test_api_base_url_validation_https(self):
        """Test api_base_url accepts valid https URL."""
        config = CLIConfig(api_base_url="https://api.example.com:8443")
        assert config.api_base_url == "https://api.example.com:8443"

    def test_api_base_url_validation_invalid(self):
        """Test api_base_url rejects invalid URL."""
        with pytest.raises(ValueError, match="must start with http"):
            CLIConfig(api_base_url="ftp://example.com")

    def test_api_base_url_validation_no_scheme(self):
        """Test api_base_url rejects URL without scheme."""
        with pytest.raises(ValueError, match="must start with http"):
            CLIConfig(api_base_url="example.com")

    def test_timeout_validation_positive(self):
        """Test timeout accepts positive integers."""
        config = CLIConfig(timeout=60)
        assert config.timeout == 60

    def test_timeout_validation_zero(self):
        """Test timeout rejects zero value."""
        with pytest.raises(ValueError, match="must be positive"):
            CLIConfig(timeout=0)

    def test_timeout_validation_negative(self):
        """Test timeout rejects negative value."""
        with pytest.raises(ValueError, match="must be positive"):
            CLIConfig(timeout=-1)

    def test_mode_literal_http(self):
        """Test mode accepts 'http' value."""
        config = CLIConfig(mode="http")
        assert config.mode == "http"

    def test_mode_literal_local(self):
        """Test mode accepts 'local' value."""
        config = CLIConfig(mode="local")
        assert config.mode == "local"

    def test_mode_literal_invalid(self):
        """Test mode rejects invalid value."""
        with pytest.raises(ValueError):
            CLIConfig(mode="invalid")

    def test_output_format_literal_rich(self):
        """Test output_format accepts 'rich' value."""
        config = CLIConfig(output_format="rich")
        assert config.output_format == "rich"

    def test_output_format_literal_json(self):
        """Test output_format accepts 'json' value."""
        config = CLIConfig(output_format="json")
        assert config.output_format == "json"

    def test_output_format_literal_plain(self):
        """Test output_format accepts 'plain' value."""
        config = CLIConfig(output_format="plain")
        assert config.output_format == "plain"

    def test_output_format_literal_invalid(self):
        """Test output_format rejects invalid value."""
        with pytest.raises(ValueError):
            CLIConfig(output_format="markdown")

    def test_api_key_optional(self):
        """Test api_key is optional and defaults to None."""
        config = CLIConfig()
        assert config.api_key is None

    def test_api_key_set(self):
        """Test api_key can be set."""
        config = CLIConfig(api_key="test-key-12345")
        assert config.api_key == "test-key-12345"


class TestLoadFromFile:
    """Test _load_from_file function."""

    def test_load_from_nonexistent_file(self):
        """Test _load_from_file returns empty dict for non-existent file."""
        nonexistent = Path("/nonexistent/path/to/config.toml")
        result = _load_from_file(nonexistent)
        assert result == {}

    def test_load_from_valid_toml_file(self):
        """Test _load_from_file loads valid TOML configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""[xagent]
api_base_url = "http://example.com:9000"
api_key = "test-key"
mode = "local"
timeout = 60
output_format = "json"
""")
            f.flush()
            temp_path = Path(f.name)

        try:
            result = _load_from_file(temp_path)
            assert result["api_base_url"] == "http://example.com:9000"
            assert result["api_key"] == "test-key"
            assert result["mode"] == "local"
            assert result["timeout"] == 60
            assert result["output_format"] == "json"
        finally:
            temp_path.unlink()

    def test_load_from_file_without_xagent_section(self):
        """Test _load_from_file returns empty dict when [xagent] section missing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""[other]
key = "value"
""")
            f.flush()
            temp_path = Path(f.name)

        try:
            result = _load_from_file(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()

    def test_load_from_invalid_toml(self):
        """Test _load_from_file returns empty dict for invalid TOML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("invalid [[ toml syntax")
            f.flush()
            temp_path = Path(f.name)

        try:
            result = _load_from_file(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()


class TestLoadConfig:
    """Test load_config priority handling."""

    def test_load_config_defaults(self):
        """Test load_config returns defaults when no args or env."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
            assert config.api_base_url == "http://localhost:8000"
            assert config.mode == "http"
            assert config.timeout == 30

    def test_load_config_cli_overrides_all(self):
        """Test CLI parameters override environment and file."""
        with patch.dict(
            os.environ,
            {
                "XAGENT_API_BASE_URL": "http://env-url:8000",
                "XAGENT_MODE": "local",
            },
        ):
            config = load_config(
                api_base_url="http://cli-url:9000",
                mode="http",
            )
            assert config.api_base_url == "http://cli-url:9000"
            assert config.mode == "http"

    def test_load_config_env_overrides_file(self):
        """Test environment variables override file config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""[xagent]
api_base_url = "http://file-url:8000"
mode = "local"
timeout = 40
""")
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch(
                "cli.config._get_config_file_path",
                return_value=temp_path,
            ):
                with patch.dict(
                    os.environ,
                    {"XAGENT_API_BASE_URL": "http://env-url:8000"},
                ):
                    config = load_config()
                    assert config.api_base_url == "http://env-url:8000"
                    assert config.mode == "local"
                    assert config.timeout == 40
        finally:
            temp_path.unlink()

    def test_load_config_converts_timeout_from_env_string(self):
        """Test load_config converts timeout from env string to int."""
        with patch.dict(os.environ, {"XAGENT_TIMEOUT": "120"}):
            config = load_config()
            assert config.timeout == 120
            assert isinstance(config.timeout, int)

    def test_load_config_api_key_from_env(self):
        """Test api_key loads from environment variable."""
        with patch.dict(os.environ, {"XAGENT_API_KEY": "env-key-secret"}):
            config = load_config()
            assert config.api_key == "env-key-secret"

    def test_load_config_cli_api_key_overrides_env(self):
        """Test CLI api_key parameter overrides environment."""
        with patch.dict(os.environ, {"XAGENT_API_KEY": "env-key"}):
            config = load_config(api_key="cli-key")
            assert config.api_key == "cli-key"

    def test_load_config_output_format_from_env(self):
        """Test output_format loads from environment variable."""
        with patch.dict(os.environ, {"XAGENT_OUTPUT_FORMAT": "json"}):
            config = load_config()
            assert config.output_format == "json"

    def test_load_config_mode_from_env(self):
        """Test mode loads from environment variable."""
        with patch.dict(os.environ, {"XAGENT_MODE": "local"}):
            config = load_config()
            assert config.mode == "local"

    def test_load_config_cli_none_does_not_override_env(self):
        """Test that passing None for CLI param doesn't override env."""
        with patch.dict(os.environ, {"XAGENT_MODE": "local"}):
            config = load_config(mode=None)
            assert config.mode == "local"

    def test_load_config_invalid_timeout_from_env_keeps_default(self):
        """Test invalid timeout string from env keeps default."""
        with patch.dict(os.environ, {"XAGENT_TIMEOUT": "not-a-number"}):
            config = load_config()
            assert config.timeout == 30

    def test_load_config_all_parameters(self):
        """Test load_config with all parameters specified."""
        config = load_config(
            api_base_url="http://api.example.com:9000",
            api_key="secret-key",
            mode="local",
            timeout=120,
            output_format="json",
        )
        assert config.api_base_url == "http://api.example.com:9000"
        assert config.api_key == "secret-key"
        assert config.mode == "local"
        assert config.timeout == 120
        assert config.output_format == "json"


class TestSaveConfig:
    """Test save_config persistence."""

    def test_save_config_creates_file(self):
        """Test save_config creates config file and parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".xagent"
            config_file = config_dir / "config.toml"

            with patch(
                "cli.config._get_config_file_path",
                return_value=config_file,
            ):
                config = CLIConfig(
                    api_base_url="http://test:8000",
                    api_key="test-key",
                    mode="http",
                    timeout=45,
                    output_format="json",
                )
                save_config(config)

                assert config_file.exists()
                content = config_file.read_text()
                assert "http://test:8000" in content
                assert "test-key" in content
                assert "http" in content
                assert "45" in content

    def test_save_config_roundtrip(self):
        """Test save_config followed by load preserves values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".xagent" / "config.toml"

            with patch(
                "cli.config._get_config_file_path",
                return_value=config_file,
            ):
                original = CLIConfig(
                    api_base_url="https://prod.example.com:9000",
                    api_key="my-secret-key",
                    mode="local",
                    timeout=90,
                    output_format="plain",
                )
                save_config(original)

                loaded_data = _load_from_file(config_file)
                restored = CLIConfig(**loaded_data)

                assert restored.api_base_url == original.api_base_url
                assert restored.api_key == original.api_key
                assert restored.mode == original.mode
                assert restored.timeout == original.timeout
                assert restored.output_format == original.output_format

    def test_save_config_without_api_key(self):
        """Test save_config with api_key=None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / ".xagent" / "config.toml"

            with patch(
                "cli.config._get_config_file_path",
                return_value=config_file,
            ):
                config = CLIConfig(api_base_url="http://localhost:8000")
                save_config(config)

                assert config_file.exists()
                content = config_file.read_text()
                assert "api_base_url" in content
                assert "api_key" in content
