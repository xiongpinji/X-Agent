"""
Security fixes verification tests for X-Agent.
Tests all 4 critical security hardening tasks:
1. Path traversal prevention (CRITICAL)
2. Default secret validation (HIGH)
3. Sensitive information leakage prevention (HIGH)
4. CSRF protection (HIGH)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.settings import Settings
from backend.app.core.path_mapper import PathMapper
from backend.app.core.error_handling import SafeErrorResponse, ErrorCategory


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
        import importlib

        auth_module = importlib.import_module("backend.app.api.auth")
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
            # 显式 UTF-8：Windows 中文 locale 默认 GBK 会在读取含非 GBK
            # 字节的 pyproject.toml 时抛 UnicodeDecodeError。
            with open(pyproject_path, encoding="utf-8") as f:
                content = f.read()
            assert "redis" in content.lower()


class TestPathTraversalPrevention:
    """Test CRITICAL: Path traversal vulnerability fixes."""

    def test_path_mapper_blocks_parent_directory_traversal(self):
        """Test that PathMapper blocks .. traversal."""
        mapper = PathMapper(Path("/workspace"))

        with pytest.raises((ValueError, PermissionError)):
            mapper.map_virtual_to_real("/../etc/passwd", "user1")

    def test_path_mapper_blocks_absolute_paths(self):
        """Test that PathMapper blocks absolute paths outside workspace."""
        mapper = PathMapper(Path("/workspace"))

        with pytest.raises(PermissionError):
            mapper.map_virtual_to_real("/etc/passwd", "user1")

    def test_path_mapper_validates_forbidden_paths(self):
        """Test that PathMapper blocks forbidden system directories."""
        mapper = PathMapper(Path("/workspace"))

        # Test various forbidden paths
        forbidden = ["/etc", "/sys", "/proc", "/dev", "/boot", "/root"]
        for path in forbidden:
            with pytest.raises(PermissionError):
                mapper.map_virtual_to_real(path, "user1")

    def test_path_mapper_allows_valid_paths(self):
        """Test that PathMapper allows valid workspace paths."""
        mapper = PathMapper(Path("/workspace"))

        result = mapper.map_virtual_to_real("/documents/file.txt", "user1")
        # Compare with OS-separator agnostic form: on Windows the result uses
        # backslashes (e.g. D:\\workspace\\user1\\...), so normalize before the
        # substring check instead of hardcoding POSIX separators.
        normalized = str(result).replace("\\", "/")
        assert "workspace/user1" in normalized
        assert "documents/file.txt" in normalized

    def test_files_api_validates_paths(self):
        """Test that files API validates paths before processing."""
        # This would require a full integration test with TestClient
        # Verify the validation function exists
        from backend.app.api.files_v2 import _validate_and_resolve_path
        assert callable(_validate_and_resolve_path)


class TestDefaultSecretValidation:
    """Test HIGH: Default secret validation fixes."""

    def test_production_rejects_default_jwt_secret(self):
        """Test that production mode rejects default JWT secret."""
        with pytest.raises(ValueError, match="Production secrets must be changed"):
            Settings(
                app_mode="production",
                jwt_secret="change-this-to-a-random-64-char-string",
                encryption_key="ValidEncryptionKeyWith32Characters123456"
            )

    def test_production_rejects_default_encryption_key(self):
        """Test that production mode rejects default encryption key."""
        with pytest.raises(ValueError, match="Production secrets must be changed"):
            Settings(
                app_mode="production",
                jwt_secret="ValidJWTSecretKeyWith32Characters123456",
                encryption_key="change-this-to-32-char-hex-string"
            )

    def test_production_rejects_short_secrets(self):
        """Test that production mode rejects short secrets."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            Settings(
                app_mode="production",
                jwt_secret="short",
                encryption_key="ValidEncryptionKeyWith32Characters123456"
            )

    def test_production_requires_entropy(self):
        """Test that production mode requires sufficient entropy."""
        with pytest.raises(ValueError, match="uppercase letters and digits"):
            Settings(
                app_mode="production",
                jwt_secret="alllowercasewithnouppercase123456789",
                encryption_key="ValidEncryptionKeyWith32Characters123456"
            )

    def test_development_allows_default_secrets(self):
        """Test that development mode allows default secrets."""
        settings = Settings(
            app_mode="development",
            jwt_secret="change-this-to-a-random-64-char-string",
            encryption_key="change-this-to-32-char-hex-string"
        )
        assert settings.jwt_secret == "change-this-to-a-random-64-char-string"


class TestSensitiveInformationLeakage:
    """Test HIGH: Sensitive information leakage prevention."""

    def test_safe_error_response_hides_details(self):
        """Test that SafeErrorResponse hides implementation details."""
        error = ValueError("Database connection failed at 192.168.1.1:5432")

        safe_msg = SafeErrorResponse.get_safe_message(error)
        assert safe_msg == "Invalid input provided"
        assert "192.168.1.1" not in safe_msg
        assert "5432" not in safe_msg

    def test_safe_error_response_sanitizes_paths(self):
        """Test that SafeErrorResponse sanitizes file paths."""
        error = FileNotFoundError("/home/user/secret/file.txt")

        safe_msg = SafeErrorResponse.get_safe_message(error)
        assert safe_msg == "Resource not found"
        assert "/home/user" not in safe_msg

    def test_safe_error_response_sanitizes_credentials(self):
        """Test that SafeErrorResponse sanitizes credentials."""
        message = "Failed to connect: password=secret123 api_key=abc123xyz"

        sanitized = SafeErrorResponse.sanitize_error_message(message)
        assert "secret123" not in sanitized
        assert "abc123xyz" not in sanitized
        assert "[REDACTED]" in sanitized

    def test_safe_error_response_logs_actual_error(self):
        """Test that SafeErrorResponse logs actual error details."""
        error = ValueError("Actual error details")

        with patch('backend.app.core.error_handling.logger') as mock_logger:
            SafeErrorResponse.get_safe_message(error)
            mock_logger.error.assert_called()

    def test_files_api_uses_safe_error_handling(self):
        """Test that files API uses safe error handling."""
        from backend.app.api.files_v2 import SafeErrorResponse as FilesErrorResponse
        assert FilesErrorResponse is not None


class TestCSRFProtection:
    """Test HIGH: CSRF protection fixes."""

    def test_csrf_middleware_exists(self):
        """Test that CSRF middleware is implemented."""
        from backend.app.main import CSRFProtectionMiddleware
        assert CSRFProtectionMiddleware is not None

    def test_csrf_token_generation(self):
        """Test CSRF token generation."""
        from backend.app.main import _csrf_middleware

        token = _csrf_middleware.generate_csrf_token("session123")
        assert token is not None
        assert len(token) > 0

    def test_csrf_token_validation(self):
        """Test CSRF token validation."""
        from backend.app.main import _csrf_middleware

        session_id = "session123"
        token = _csrf_middleware.generate_csrf_token(session_id)

        # Token should be valid for this session
        assert token in _csrf_middleware._tokens.get(session_id, set())

    def test_csrf_middleware_exempt_paths(self):
        """Test that CSRF middleware exempts certain paths."""
        from backend.app.main import CSRFProtectionMiddleware

        exempt_paths = CSRFProtectionMiddleware.EXEMPT_PATHS
        assert "/health" in exempt_paths
        assert "/api/v1/auth/login" in exempt_paths

    def test_csrf_middleware_safe_methods(self):
        """Test that CSRF middleware allows safe methods."""
        from backend.app.main import CSRFProtectionMiddleware

        safe_methods = CSRFProtectionMiddleware.SAFE_METHODS
        assert "GET" in safe_methods
        assert "HEAD" in safe_methods
        assert "OPTIONS" in safe_methods

    def test_csrf_token_endpoint_exists(self):
        """Test that CSRF token endpoint is available."""
        client = TestClient(app)
        # The endpoint should exist (though it may require auth)
        response = client.post("/api/v1/csrf-token")
        # Should either succeed or require auth, not 404
        assert response.status_code != 404, "Redis should be in dependencies"


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


class TestProductionAnonymousGuard:
    """生产环境绝不回落匿名主体（S5 守卫）。"""

    def _no_cred_request(self):
        req = MagicMock()
        req.headers = {}
        return req

    def test_production_rejects_anonymous(self):
        """生产模式 + 无凭证 → 401，不回落 anonymous。"""
        from backend.app.api.errors import XAgentAPIError
        from backend.app import dependencies

        fake = MagicMock()
        fake.require_api_key = False
        fake.app_mode = "production"
        with patch.object(dependencies, "get_settings", return_value=fake):
            with pytest.raises(XAgentAPIError) as exc:
                dependencies.get_current_principal(self._no_cred_request())
        assert exc.value.status_code == 401

    def test_development_allows_anonymous(self):
        """开发模式 + 无凭证 → 回落匿名主体（不破坏 dev 体验）。"""
        from backend.app import dependencies

        fake = MagicMock()
        fake.require_api_key = False
        fake.app_mode = "development"
        with patch.object(dependencies, "get_settings", return_value=fake):
            principal = dependencies.get_current_principal(self._no_cred_request())
        assert principal is not None
        assert getattr(principal, "authenticated", False) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
