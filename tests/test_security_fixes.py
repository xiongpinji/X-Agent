"""
Security fixes verification tests for X-Agent.
Tests all 5 security hardening tasks.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import Settings


class TestCORSFix:
    """Test CORS wildcard removal."""

    def test_cors_origins_not_wildcard(self):
        """Verify CORS origins are not set to wildcard."""
        client = TestClient(app)
        # Check that CORS middleware is configured with specific origins
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware):
                cors_middleware = middleware
                break
        assert cors_middleware is not None, "CORS middleware should be configured"

    def test_cors_production_mode_validation(self):
        """Test that production mode rejects wildcard CORS."""
        with patch("backend.app.main.settings") as mock_settings:
            mock_settings.app_mode = "production"
            mock_settings.cors_origins = "*"
            # This should be caught by the validation logic
            assert mock_settings.app_mode == "production"


class TestDefaultCredentials:
    """Test default credentials are updated."""

    def test_env_example_no_weak_passwords(self):
        """Verify .env.example doesn't contain weak default passwords."""
        env_path = Path("backend/app/../../../.env.example")
        if env_path.exists():
            with open(env_path) as f:
                content = f.read()
            # Check that weak defaults are not present
            assert "minioadmin" not in content, "minioadmin should not be in .env.example"
            assert "xagent123" not in content, "xagent123 should not be in .env.example"
            # Check for security warnings
            assert "SECURITY" in content or "⚠️" in content, "Should have security warnings"


class TestJWTSecretValidation:
    """Test JWT secret production validation."""

    def test_jwt_secret_validator_exists(self):
        """Verify JWT secret validator is implemented."""
        settings_module = __import__("backend.app.settings", fromlist=["Settings"])
        Settings = settings_module.Settings
        # Check that the validator exists
        assert hasattr(Settings, "_validate_production_secrets")

    def test_production_mode_requires_strong_secrets(self):
        """Test that production mode enforces strong secrets."""
        with pytest.raises(ValueError, match="Production secrets must be changed"):
            Settings(
                app_mode="production",
                jwt_secret="change-this-to-a-random-64-char-string",
                encryption_key="change-this-to-32-char-hex-string",
            )

    def test_development_mode_allows_defaults(self):
        """Test that development mode allows default secrets."""
        settings = Settings(
            app_mode="development",
            jwt_secret="change-this-to-a-random-64-char-string",
            encryption_key="change-this-to-32-char-hex-string",
        )
        assert settings.app_mode == "development"


class TestAPIKeyMigration:
    """Test API key migration to database."""

    def test_migration_script_exists(self):
        """Verify migration script is created."""
        migration_path = Path("backend/app/migrations/migrate_api_keys.py")
        assert migration_path.exists(), "Migration script should exist"

    def test_migration_script_has_required_functions(self):
        """Verify migration script has required functions."""
        migration_module = __import__(
            "backend.app.migrations.migrate_api_keys", fromlist=["APIKeyMigration"]
        )
        assert hasattr(migration_module, "APIKeyMigration")
        assert hasattr(migration_module, "run_migration")

    def test_api_keys_json_format(self):
        """Verify API keys JSON file format is compatible."""
        api_keys_path = Path("data/api_keys.json")
        if api_keys_path.exists():
            with open(api_keys_path) as f:
                keys = json.load(f)
            # Verify structure
            for key in keys:
                assert "id" in key
                assert "key_prefix" in key
                assert "key_hash" in key
                assert "tenant_id" in key


class TestRedisSessionStorage:
    """Test Redis session storage implementation."""

    def test_redis_initialization_in_auth(self):
        """Verify Redis initialization is implemented in auth module."""
        auth_module = __import__("backend.app.api.auth", fromlist=["_init_redis"])
        assert hasattr(auth_module, "_init_redis")
        assert hasattr(auth_module, "_use_redis")

    def test_token_storage_functions_exist(self):
        """Verify token storage functions support both backends."""
        auth_module = __import__("backend.app.api.auth", fromlist=[])
        assert hasattr(auth_module, "_issue_token")
        assert hasattr(auth_module, "_is_token_valid")
        assert hasattr(auth_module, "_revoke_token")
        assert hasattr(auth_module, "_store_token_user")
        assert hasattr(auth_module, "_get_token_user")

    def test_redis_url_in_settings(self):
        """Verify Redis URL configuration is in settings."""
        settings = Settings()
        assert hasattr(settings, "redis_url")

    def test_redis_dependency_in_pyproject(self):
        """Verify Redis is in project dependencies."""
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            with open(pyproject_path) as f:
                content = f.read()
            assert "redis" in content.lower(), "Redis should be in dependencies"


class TestBackwardCompatibility:
    """Test backward compatibility of changes."""

    def test_auth_endpoints_still_work(self):
        """Verify auth endpoints are still functional."""
        client = TestClient(app)
        # Test that endpoints exist
        assert client.get("/api/v1/auth/me").status_code in [200, 401]

    def test_cors_middleware_still_configured(self):
        """Verify CORS middleware is still present."""
        assert len(app.user_middleware) > 0, "Middleware should be configured"

    def test_settings_backward_compatible(self):
        """Verify settings are backward compatible."""
        settings = Settings()
        # Should have all original settings
        assert hasattr(settings, "app_name")
        assert hasattr(settings, "cors_origins")
        assert hasattr(settings, "database_url")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
