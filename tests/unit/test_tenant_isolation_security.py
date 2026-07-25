"""P0-06: 租户隔离加固验证测试。

验证:
1. 中间件不信任客户端提供的 x-tenant-id 头
2. 租户上下文仅从已认证 principal 派生
3. 伪造 x-tenant-id 头不会导致跨租户访问
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.tenant_isolation import (
    TenantIsolationMiddleware,
    TenantIsolationValidator,
)
from backend.app.core.security import Principal


class TestTenantIsolationMiddleware:
    """Test TenantIsolationMiddleware security properties."""

    @pytest.mark.asyncio
    async def test_ignores_client_tenant_header(self):
        """Verify middleware ignores client-supplied x-tenant-id header."""
        middleware = TenantIsolationMiddleware(app=MagicMock())

        # Create a mock request with forged x-tenant-id header
        request = MagicMock()
        request.url.path = "/api/v1/agents"
        request.headers = {"x-tenant-id": "forged-tenant-id"}
        request.client.host = "127.0.0.1"
        request.state = MagicMock()

        # Mock principal with different tenant
        principal = Principal(
            tenant_id="real-tenant-id",
            user_id="user-123",
            authenticated=True,
            role="user",
        )

        with patch(
            "backend.app.dependencies.get_current_principal",
            return_value=principal,
        ):
            # The middleware should use principal.tenant_id, not header
            call_next = AsyncMock(return_value=MagicMock(headers={}))
            await middleware.dispatch(request, call_next)

            # Verify request.state.tenant_id is from principal, not header
            assert request.state.tenant_id == "real-tenant-id"
            assert request.state.tenant_id != "forged-tenant-id"

    @pytest.mark.asyncio
    async def test_exempt_paths_skip_isolation(self):
        """Verify exempt paths skip tenant isolation."""
        middleware = TenantIsolationMiddleware(app=MagicMock())

        request = MagicMock()
        request.url.path = "/health"

        call_next = AsyncMock(return_value=MagicMock())
        result = await middleware.dispatch(request, call_next)

        # Should call next without setting tenant context
        call_next.assert_called_once()


class TestTenantIsolationValidator:
    """Test TenantIsolationValidator access control."""

    def test_admin_can_access_any_tenant(self):
        """Admin should access resources from any tenant."""
        principal = Principal(
            tenant_id="admin-tenant",
            user_id="admin-user",
            authenticated=True,
            role="admin",
        )

        assert TenantIsolationValidator.validate_tenant_access(
            principal, "other-tenant", "resource"
        ) is True

    def test_user_cannot_access_other_tenant(self):
        """Regular user cannot access other tenant's resources."""
        principal = Principal(
            tenant_id="user-tenant",
            user_id="regular-user",
            authenticated=True,
            role="user",
        )

        assert TenantIsolationValidator.validate_tenant_access(
            principal, "other-tenant", "resource"
        ) is False

    def test_user_can_access_own_tenant(self):
        """User can access own tenant's resources."""
        principal = Principal(
            tenant_id="user-tenant",
            user_id="regular-user",
            authenticated=True,
            role="user",
        )

        assert TenantIsolationValidator.validate_tenant_access(
            principal, "user-tenant", "resource"
        ) is True

    def test_filter_by_tenant(self):
        """Test record filtering by tenant."""
        principal = Principal(
            tenant_id="tenant-a",
            user_id="user-1",
            authenticated=True,
            role="user",
        )

        records = [
            {"id": "1", "tenant_id": "tenant-a", "data": "own"},
            {"id": "2", "tenant_id": "tenant-b", "data": "other"},
            {"id": "3", "tenant_id": "tenant-a", "data": "own2"},
        ]

        filtered = TenantIsolationValidator.filter_by_tenant(records, principal)
        assert len(filtered) == 2
        assert all(r["tenant_id"] == "tenant-a" for r in filtered)

    def test_admin_sees_all_records(self):
        """Admin should see records from all tenants."""
        principal = Principal(
            tenant_id="admin-tenant",
            user_id="admin-user",
            authenticated=True,
            role="admin",
        )

        records = [
            {"id": "1", "tenant_id": "tenant-a"},
            {"id": "2", "tenant_id": "tenant-b"},
        ]

        filtered = TenantIsolationValidator.filter_by_tenant(records, principal)
        assert len(filtered) == 2


class TestTenantHeaderForgery:
    """Test that tenant header forgery is detected and ignored."""

    @pytest.mark.asyncio
    async def test_forged_header_logged_and_ignored(self):
        """Forged x-tenant-id header should be logged and ignored."""
        middleware = TenantIsolationMiddleware(app=MagicMock())

        request = MagicMock()
        request.url.path = "/api/v1/workflows"
        request.headers = {"x-tenant-id": "victim-tenant"}
        request.client.host = "10.0.0.1"
        request.state = MagicMock()

        # Attacker's principal
        principal = Principal(
            tenant_id="attacker-tenant",
            user_id="attacker-user",
            authenticated=True,
            role="user",
        )

        with patch(
            "backend.app.dependencies.get_current_principal",
            return_value=principal,
        ):
            with patch("backend.app.core.tenant_isolation.logger") as mock_logger:
                call_next = AsyncMock(return_value=MagicMock(headers={}))
                await middleware.dispatch(request, call_next)

                # Verify warning was logged about forged header
                mock_logger.warning.assert_called()
                warning_msg = str(mock_logger.warning.call_args)
                assert "Ignoring" in warning_msg or "forged" in warning_msg.lower()

                # Verify tenant is from principal, not forged header
                assert request.state.tenant_id == "attacker-tenant"
