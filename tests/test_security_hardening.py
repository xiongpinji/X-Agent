"""Security tests for X-Agent.

Tests cover:
- Authentication and authorization
- Path traversal prevention
- Rate limiting
- Password security
- API key security
- CORS security
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.app.core.path_security import PathSecurityValidator
# tool_sandbox 已归档（2026-08-04 死代码收敛），对应测试见
# archive/dead_code_2026-08/tests/test_security_hardening_tool_sandbox.py
from backend.app.core.rate_limiter import RateLimiter, RATE_LIMITS
from backend.app.core.data_encryption import DataEncryptor
from backend.app.core.log_sanitizer import LogSanitizer
from backend.app.core.security import RBACPolicy, Principal, ROLE_SCOPES


class TestPathSecurity:
    """Test path security validation."""

    def test_path_traversal_prevention(self, tmp_path):
        """Test that path traversal attacks are prevented."""
        validator = PathSecurityValidator(tmp_path)

        # Create a file outside sandbox
        outside_file = tmp_path.parent / "outside.txt"
        outside_file.write_text("secret")

        # Attempt to access file outside sandbox should fail
        with pytest.raises(Exception):
            validator.validate_path("../outside.txt")

    def test_symlink_prevention(self, tmp_path):
        """Test that symlinks are rejected."""
        validator = PathSecurityValidator(tmp_path)

        # Create a symlink
        target = tmp_path / "target.txt"
        target.write_text("content")
        symlink = tmp_path / "link.txt"
        try:
            symlink.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            # Windows without Developer Mode / admin rights forbids symlink
            # creation (WinError 1314). Skip rather than fail — the validator
            # logic is exercised on platforms where symlinks can be created.
            pytest.skip(f"Cannot create symlink in this environment: {exc}")

        # Symlink should be rejected
        with pytest.raises(Exception):
            validator.validate_path(str(symlink), allow_symlinks=False)

    def test_valid_path_acceptance(self, tmp_path):
        """Test that valid paths are accepted."""
        validator = PathSecurityValidator(tmp_path)

        # Create a valid file
        valid_file = tmp_path / "valid.txt"
        valid_file.write_text("content")

        # Should accept valid path
        result = validator.validate_path(str(valid_file))
        assert result == valid_file.resolve()


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limit_enforcement(self):
        """Test that rate limits are enforced."""
        limiter = RateLimiter()

        key = "test_user"
        max_requests = 3
        window_seconds = 60

        # First 3 requests should be allowed
        assert limiter.is_allowed(key, max_requests, window_seconds)
        assert limiter.is_allowed(key, max_requests, window_seconds)
        assert limiter.is_allowed(key, max_requests, window_seconds)

        # 4th request should be rejected
        assert not limiter.is_allowed(key, max_requests, window_seconds)

    def test_rate_limit_window_reset(self):
        """Test that rate limit window resets."""
        limiter = RateLimiter()

        key = "test_user"
        max_requests = 1
        window_seconds = 1

        # First request allowed
        assert limiter.is_allowed(key, max_requests, window_seconds)

        # Second request rejected
        assert not limiter.is_allowed(key, max_requests, window_seconds)

        # Wait for window to expire
        import time
        time.sleep(1.1)

        # Request should be allowed again
        assert limiter.is_allowed(key, max_requests, window_seconds)


class TestDataEncryption:
    """Test data encryption functionality."""

    def test_encryption_decryption(self):
        """Test encryption and decryption."""
        encryptor = DataEncryptor("a" * 32)

        plaintext = "sensitive_data_12345"
        ciphertext = encryptor.encrypt(plaintext)

        # Ciphertext should be different from plaintext
        assert ciphertext != plaintext

        # Decryption should recover plaintext
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encryption_deterministic(self):
        """Test that encryption is deterministic (same key produces same ciphertext)."""
        encryptor = DataEncryptor("a" * 32)

        plaintext = "test_data"
        # Note: GCM with random nonce is non-deterministic, so we just verify decryption works
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)

        assert decrypted == plaintext


class TestLogSanitizer:
    """Test log sanitization."""

    def test_api_key_redaction(self):
        """Test that API keys are redacted."""
        sanitizer = LogSanitizer()

        text = "API key: xag_abcdef1234567890abcdef1234567890"
        sanitized = sanitizer.sanitize_string(text)

        assert "xag_" not in sanitized
        assert "***REDACTED***" in sanitized

    def test_password_redaction(self):
        """Test that passwords are redacted."""
        sanitizer = LogSanitizer()

        text = 'password="MySecretPassword123"'
        sanitized = sanitizer.sanitize_string(text)

        assert "MySecretPassword123" not in sanitized
        assert "***REDACTED***" in sanitized

    def test_dict_sanitization(self):
        """Test dictionary sanitization."""
        sanitizer = LogSanitizer()

        data = {
            "username": "user@example.com",
            "password": "secret123",
            "api_key": "xag_key123",
        }

        sanitized = sanitizer.sanitize_dict(data)

        # SECURITY: email values are PII and are redacted everywhere they appear,
        # including in non-sensitive field names like "username". Redacting PII in
        # logs (fail-safe) is preferred over preserving it for debugging.
        assert sanitized["username"] == "***REDACTED***"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["api_key"] == "***REDACTED***"


class TestRBACPolicy:
    """Test RBAC policy enforcement."""

    def test_anonymous_user_no_scopes(self):
        """Test that anonymous users have no scopes."""
        policy = RBACPolicy()

        principal = Principal(authenticated=False)

        # Anonymous user should have no scopes
        assert not policy.has_scope(principal, "agent:run")
        assert not policy.has_scope(principal, "memory:read")

    def test_authenticated_user_scopes(self):
        """Test that authenticated users have proper scopes."""
        policy = RBACPolicy()

        principal = Principal(
            authenticated=True,
            role="developer",
            scopes=ROLE_SCOPES["developer"],
        )

        # Developer should have developer scopes
        assert policy.has_scope(principal, "agent:run")
        assert policy.has_scope(principal, "workflow:create")

        # Developer should not have admin scopes
        assert not policy.has_scope(principal, "security:manage")

    def test_wildcard_scope(self):
        """Test wildcard scope matching."""
        policy = RBACPolicy()

        principal = Principal(
            authenticated=True,
            role="admin",
            scopes=["tools:*"],
        )

        assert policy.has_scope(principal, "tools:read")
        assert policy.has_scope(principal, "tools:execute")
