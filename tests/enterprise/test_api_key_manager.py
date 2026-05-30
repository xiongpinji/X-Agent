"""
Comprehensive test suite for API Key Management System.

Tests:
- API key creation, rotation, and revocation
- Permission checking
- Rate limiting
- IP whitelisting
- Anomaly detection
- Audit logging
- Performance benchmarks
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Optional

import pytest

from backend.app.core.api_key_manager import (
    APIKeyManager,
    AnomalyType,
    KeyStatus,
    PermissionLevel,
    RateLimitConfig,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def api_key_manager() -> APIKeyManager:
    """Create API key manager for testing."""
    return APIKeyManager()


@pytest.fixture
def sample_permissions() -> list[PermissionLevel]:
    """Sample permissions for testing."""
    return [
        PermissionLevel.AGENT_READ,
        PermissionLevel.AGENT_EXECUTE,
        PermissionLevel.WORKFLOW_READ,
    ]


# ============================================================================
# KEY LIFECYCLE TESTS
# ============================================================================

class TestKeyCreation:
    """Test API key creation."""

    def test_create_key_basic(self, api_key_manager: APIKeyManager) -> None:
        """Test basic key creation."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            tenant_id="tenant1",
        )

        assert raw_key.startswith("xag_")
        assert config.name == "test-key"
        assert config.user_id == "user123"
        assert config.tenant_id == "tenant1"
        assert config.status == KeyStatus.ACTIVE
        assert config.expires_at is not None

    def test_create_key_with_permissions(
        self,
        api_key_manager: APIKeyManager,
        sample_permissions: list[PermissionLevel],
    ) -> None:
        """Test key creation with custom permissions."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=sample_permissions,
        )

        assert config.permissions == sample_permissions

    def test_create_key_with_custom_expiry(self, api_key_manager: APIKeyManager) -> None:
        """Test key creation with custom expiry."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            expires_in_days=30,
        )

        # Check expiry is approximately 30 days
        days_until_expiry = (config.expires_at - datetime.now(UTC)).days
        assert 29 <= days_until_expiry <= 30

    def test_create_multiple_keys(self, api_key_manager: APIKeyManager) -> None:
        """Test creating multiple keys."""
        keys = []
        for i in range(5):
            raw_key, config = api_key_manager.create_key(
                name=f"key-{i}",
                user_id="user123",
            )
            keys.append((raw_key, config))

        assert len(keys) == 5
        # All keys should be unique
        raw_keys = [k[0] for k in keys]
        assert len(set(raw_keys)) == 5


class TestKeyAuthentication:
    """Test API key authentication."""

    def test_authenticate_valid_key(self, api_key_manager: APIKeyManager) -> None:
        """Test authentication with valid key."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is not None
        assert authenticated.user_id == "user123"

    def test_authenticate_invalid_key(self, api_key_manager: APIKeyManager) -> None:
        """Test authentication with invalid key."""
        authenticated = api_key_manager.authenticate("xag_invalid_key_here")
        assert authenticated is None

    def test_authenticate_revoked_key(self, api_key_manager: APIKeyManager) -> None:
        """Test authentication with revoked key."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        # Revoke the key
        api_key_manager.revoke_key(config.id, "admin", "Testing")

        # Try to authenticate
        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is None

    def test_authenticate_expired_key(self, api_key_manager: APIKeyManager) -> None:
        """Test authentication with expired key."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            expires_in_days=0,  # Expires immediately
        )

        # Wait a moment to ensure expiry
        time.sleep(0.1)

        # Try to authenticate
        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is None

    def test_authenticate_updates_last_used(self, api_key_manager: APIKeyManager) -> None:
        """Test that authentication updates last_used_at."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        assert config.last_used_at is None

        api_key_manager.authenticate(raw_key)
        updated_config = api_key_manager.get_key(config.id)

        assert updated_config.last_used_at is not None


class TestKeyRotation:
    """Test API key rotation."""

    def test_rotate_key(self, api_key_manager: APIKeyManager) -> None:
        """Test key rotation."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.AGENT_READ],
        )

        # Rotate the key
        new_raw_key, new_config = api_key_manager.rotate_key(config.id, "admin")

        assert new_raw_key != raw_key
        assert new_config.id != config.id
        assert new_config.permissions == config.permissions

        # Old key should be marked as rotated
        old_config = api_key_manager.get_key(config.id)
        assert old_config.status == KeyStatus.ROTATED

    def test_rotate_key_grace_period(self, api_key_manager: APIKeyManager) -> None:
        """Test that rotated key has grace period."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        new_raw_key, new_config = api_key_manager.rotate_key(config.id, "admin")

        # Old key should still authenticate during grace period
        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is not None

    def test_rotate_revoked_key_fails(self, api_key_manager: APIKeyManager) -> None:
        """Test that rotating revoked key fails."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        api_key_manager.revoke_key(config.id, "admin", "Testing")

        with pytest.raises(ValueError):
            api_key_manager.rotate_key(config.id, "admin")


class TestKeyRevocation:
    """Test API key revocation."""

    def test_revoke_key(self, api_key_manager: APIKeyManager) -> None:
        """Test key revocation."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        revoked = api_key_manager.revoke_key(config.id, "admin", "Testing")

        assert revoked.status == KeyStatus.REVOKED
        assert revoked.revoked_at is not None

    def test_revoked_key_cannot_authenticate(self, api_key_manager: APIKeyManager) -> None:
        """Test that revoked key cannot authenticate."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        api_key_manager.revoke_key(config.id, "admin", "Testing")

        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is None


# ============================================================================
# PERMISSION TESTS
# ============================================================================

class TestPermissions:
    """Test permission checking."""

    def test_check_permission_granted(self, api_key_manager: APIKeyManager) -> None:
        """Test permission check when granted."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.AGENT_READ],
        )

        has_permission = api_key_manager.check_permission(
            config,
            PermissionLevel.AGENT_READ,
        )
        assert has_permission is True

    def test_check_permission_denied(self, api_key_manager: APIKeyManager) -> None:
        """Test permission check when denied."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.AGENT_READ],
        )

        has_permission = api_key_manager.check_permission(
            config,
            PermissionLevel.AGENT_WRITE,
        )
        assert has_permission is False

    def test_admin_permission_grants_all(self, api_key_manager: APIKeyManager) -> None:
        """Test that admin permission grants all permissions."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.ADMIN],
        )

        # Should have all permissions
        assert api_key_manager.check_permission(config, PermissionLevel.AGENT_READ)
        assert api_key_manager.check_permission(config, PermissionLevel.WORKFLOW_WRITE)
        assert api_key_manager.check_permission(config, PermissionLevel.SECURITY_MANAGE)

    def test_resource_restriction(self, api_key_manager: APIKeyManager) -> None:
        """Test resource-level permission restrictions."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.AGENT_READ],
        )

        # Add resource restriction
        config.resource_restrictions[PermissionLevel.AGENT_READ.value] = ["agent1", "agent2"]

        # Should have permission for allowed resource
        assert api_key_manager.check_permission(
            config,
            PermissionLevel.AGENT_READ,
            "agent1",
        )

        # Should not have permission for disallowed resource
        assert not api_key_manager.check_permission(
            config,
            PermissionLevel.AGENT_READ,
            "agent3",
        )


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Test rate limiting."""

    def test_rate_limit_allows_requests_within_limit(
        self,
        api_key_manager: APIKeyManager,
    ) -> None:
        """Test that requests within limit are allowed."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        # Make requests within limit
        for i in range(10):
            authenticated = api_key_manager.authenticate(raw_key)
            assert authenticated is not None

    def test_rate_limit_blocks_excessive_requests(
        self,
        api_key_manager: APIKeyManager,
    ) -> None:
        """Test that excessive requests are blocked."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        # Update rate limit to very low
        config.rate_limit = RateLimitConfig(
            requests_per_minute=5,
            requests_per_hour=100,
            requests_per_day=1000,
        )
        api_key_manager.update_key(config.id, {"rate_limit": config.rate_limit}, "admin")

        # Make requests up to limit
        for i in range(5):
            authenticated = api_key_manager.authenticate(raw_key)
            assert authenticated is not None

        # Next request should be blocked
        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is None


# ============================================================================
# ANOMALY DETECTION TESTS
# ============================================================================

class TestAnomalyDetection:
    """Test anomaly detection."""

    def test_detect_unusual_location(self, api_key_manager: APIKeyManager) -> None:
        """Test detection of unusual location."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        # Authenticate from multiple locations (need >5 known + 1 new to trigger)
        for ip in ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5", "192.168.1.6", "10.0.0.1"]:
            api_key_manager.authenticate(raw_key, ip)

        # Check for anomalies
        alerts = api_key_manager.get_anomaly_alerts(key_id=config.id)
        assert len(alerts) > 0
        assert any(a.anomaly_type == AnomalyType.UNUSUAL_LOCATION for a in alerts)

    def test_detect_failed_auth_attempts(self, api_key_manager: APIKeyManager) -> None:
        """Test detection of failed authentication attempts."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        # Make multiple failed attempts (same prefix, wrong full key)
        # so they resolve to the real key_id and hit hash verification failure
        for i in range(10):
            api_key_manager.authenticate(raw_key + "_wrong_" + str(i))

        # Check for anomalies
        alerts = api_key_manager.get_anomaly_alerts()
        # Should have alerts for failed attempts
        assert len(alerts) > 0


# ============================================================================
# AUDIT LOGGING TESTS
# ============================================================================

class TestAuditLogging:
    """Test audit logging."""

    def test_audit_log_key_creation(self, api_key_manager: APIKeyManager) -> None:
        """Test that key creation is logged."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        entries = api_key_manager.get_audit_log(key_id=config.id)
        assert len(entries) > 0
        assert entries[0].event_type == "create"

    def test_audit_log_key_rotation(self, api_key_manager: APIKeyManager) -> None:
        """Test that key rotation is logged."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        api_key_manager.rotate_key(config.id, "admin")

        entries = api_key_manager.get_audit_log(key_id=config.id)
        assert any(e.event_type == "rotate" for e in entries)

    def test_audit_log_key_revocation(self, api_key_manager: APIKeyManager) -> None:
        """Test that key revocation is logged."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        api_key_manager.revoke_key(config.id, "admin", "Testing")

        entries = api_key_manager.get_audit_log(key_id=config.id)
        assert any(e.event_type == "revoke" for e in entries)

    def test_audit_log_authentication(self, api_key_manager: APIKeyManager) -> None:
        """Test that authentication is logged."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        api_key_manager.authenticate(raw_key)

        entries = api_key_manager.get_audit_log(key_id=config.id)
        assert any(e.event_type == "use" for e in entries)


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance characteristics."""

    def test_key_rotation_performance(self, api_key_manager: APIKeyManager) -> None:
        """Test that key rotation completes in <1 second."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        start = time.time()
        api_key_manager.rotate_key(config.id, "admin")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Key rotation took {elapsed}s, expected <1s"

    def test_permission_check_performance(self, api_key_manager: APIKeyManager) -> None:
        """Test that permission check completes in <10ms."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.AGENT_READ],
        )

        start = time.time()
        for _ in range(100):
            api_key_manager.check_permission(config, PermissionLevel.AGENT_READ)
        elapsed = time.time() - start

        avg_time = (elapsed / 100) * 1000  # Convert to ms
        assert avg_time < 10, f"Permission check took {avg_time}ms, expected <10ms"

    def test_authentication_performance(self, api_key_manager: APIKeyManager) -> None:
        """Test that authentication completes in <500ms (bcrypt is intentionally slow)."""
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
        )

        start = time.time()
        for _ in range(10):
            api_key_manager.authenticate(raw_key)
        elapsed = time.time() - start

        avg_time = (elapsed / 10) * 1000  # Convert to ms
        assert avg_time < 500, f"Authentication took {avg_time}ms, expected <500ms"

    def test_list_keys_performance(self, api_key_manager: APIKeyManager) -> None:
        """Test that listing keys is performant."""
        # Create many keys
        for i in range(100):
            api_key_manager.create_key(
                name=f"key-{i}",
                user_id="user123",
            )

        start = time.time()
        keys = api_key_manager.list_keys(user_id="user123")
        elapsed = time.time() - start

        assert len(keys) == 100
        assert elapsed < 0.5, f"Listing 100 keys took {elapsed}s, expected <0.5s"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests."""

    def test_full_key_lifecycle(self, api_key_manager: APIKeyManager) -> None:
        """Test complete key lifecycle."""
        # Create
        raw_key, config = api_key_manager.create_key(
            name="test-key",
            user_id="user123",
            permissions=[PermissionLevel.AGENT_READ, PermissionLevel.AGENT_EXECUTE],
        )

        # Authenticate
        authenticated = api_key_manager.authenticate(raw_key)
        assert authenticated is not None

        # Check permissions
        assert api_key_manager.check_permission(config, PermissionLevel.AGENT_READ)
        assert api_key_manager.check_permission(config, PermissionLevel.AGENT_EXECUTE)
        assert not api_key_manager.check_permission(config, PermissionLevel.AGENT_WRITE)

        # Rotate
        new_raw_key, new_config = api_key_manager.rotate_key(config.id, "admin")
        assert new_raw_key != raw_key

        # Revoke
        revoked = api_key_manager.revoke_key(new_config.id, "admin", "Testing")
        assert revoked.status == KeyStatus.REVOKED

        # Verify audit log
        entries = api_key_manager.get_audit_log(key_id=config.id)
        assert len(entries) >= 3  # create, rotate, revoke

    def test_multi_tenant_isolation(self, api_key_manager: APIKeyManager) -> None:
        """Test that keys are isolated by tenant."""
        # Create keys for different tenants
        raw_key1, config1 = api_key_manager.create_key(
            name="key1",
            user_id="user1",
            tenant_id="tenant1",
        )

        raw_key2, config2 = api_key_manager.create_key(
            name="key2",
            user_id="user2",
            tenant_id="tenant2",
        )

        # List keys for each tenant
        keys1 = api_key_manager.list_keys(tenant_id="tenant1")
        keys2 = api_key_manager.list_keys(tenant_id="tenant2")

        assert len(keys1) == 1
        assert len(keys2) == 1
        assert keys1[0].id == config1.id
        assert keys2[0].id == config2.id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
