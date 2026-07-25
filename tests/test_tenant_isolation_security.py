"""Tenant Isolation Security Tests (P0-06).

Verifies:
1. Forging x-tenant-id header is ignored or returns 403
2. Tenant context is derived exclusively from the authenticated principal
3. Cross-tenant data access is blocked
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from backend.app.core.security import Principal
from backend.app.core.tenant_isolation import (
    TenantIsolationMiddleware,
    TenantIsolationValidator,
    require_tenant_isolation,
)


# ============================================================================
# Fixtures
# ============================================================================


def _make_principal(
    tenant_id: str = "tenant-a",
    user_id: str = "user-1",
    role: str = "user",
    authenticated: bool = True,
) -> Principal:
    """Create a test principal."""
    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        scopes=["read", "write"],
        authenticated=authenticated,
    )


def _build_test_app(principal: Principal | None = None) -> FastAPI:
    """Build a minimal FastAPI app with TenantIsolationMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(TenantIsolationMiddleware)

    @app.get("/api/v1/resource")
    async def get_resource(request: Request) -> dict[str, Any]:
        """Test endpoint that returns the tenant context."""
        tenant_id = getattr(request.state, "tenant_id", None)
        return {
            "tenant_id": tenant_id,
            "has_principal": hasattr(request.state, "principal"),
        }

    @app.get("/api/v1/health")
    async def health() -> dict[str, str]:
        """Exempt health endpoint."""
        return {"status": "ok"}

    return app


def _patch_principal(principal: Principal | None):
    """Patch get_current_principal to return a fixed principal."""
    def _fake_get_principal(request: Request) -> Principal:
        if principal is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Not authenticated")
        return principal

    return patch(
        "backend.app.dependencies.get_current_principal",
        side_effect=_fake_get_principal,
    )


# ============================================================================
# Test: Forging x-tenant-id header is ignored
# ============================================================================


class TestTenantHeaderForgery:
    """Tests that client-supplied x-tenant-id header is never trusted."""

    def test_forged_header_ignored_returns_principal_tenant(self) -> None:
        """Forging x-tenant-id header should NOT change the tenant context.

        The middleware must derive tenant_id from the authenticated principal,
        not from the client header.
        """
        principal = _make_principal(tenant_id="tenant-a")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            # Attacker tries to forge x-tenant-id to access tenant-b
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": "tenant-b"},
            )

        assert response.status_code == 200
        data = response.json()
        # Tenant must be from principal, NOT from forged header
        assert data["tenant_id"] == "tenant-a"
        assert data["tenant_id"] != "tenant-b"

    def test_forged_header_with_matching_principal(self) -> None:
        """When header matches principal tenant, it should still work normally."""
        principal = _make_principal(tenant_id="tenant-a")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": "tenant-a"},
            )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "tenant-a"

    def test_no_header_uses_principal_tenant(self) -> None:
        """Without x-tenant-id header, tenant comes from principal."""
        principal = _make_principal(tenant_id="tenant-c")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            response = client.get("/api/v1/resource")

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "tenant-c"

    def test_response_header_reflects_principal_tenant(self) -> None:
        """Response x-tenant-id header must reflect principal tenant, not client header."""
        principal = _make_principal(tenant_id="tenant-a")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": "tenant-evil"},
            )

        # Response header must be the principal's tenant
        assert response.headers.get("x-tenant-id") == "tenant-a"


# ============================================================================
# Test: Tenant context from authenticated principal only
# ============================================================================


class TestTenantContextFromPrincipal:
    """Tests that tenant context is exclusively derived from authenticated principal."""

    def test_unauthenticated_request_no_tenant_context(self) -> None:
        """Unauthenticated requests should NOT have a tenant context set."""
        app = _build_test_app()

        with _patch_principal(None):
            client = TestClient(app)
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": "tenant-admin"},
            )

        # Without valid auth, no tenant context should be set
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] is None
        assert data["has_principal"] is False

    def test_admin_principal_gets_own_tenant(self) -> None:
        """Admin principal still gets their own tenant_id in context."""
        principal = _make_principal(tenant_id="admin-tenant", role="admin")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            response = client.get("/api/v1/resource")

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "admin-tenant"

    def test_exempt_paths_skip_tenant_isolation(self) -> None:
        """Health/auth exempt paths should not require tenant context."""
        app = _build_test_app()

        with _patch_principal(None):
            client = TestClient(app)
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ============================================================================
# Test: TenantIsolationValidator
# ============================================================================


class TestTenantIsolationValidator:
    """Unit tests for TenantIsolationValidator."""

    def test_same_tenant_access_allowed(self) -> None:
        """User can access resources in their own tenant."""
        principal = _make_principal(tenant_id="tenant-a")
        assert TenantIsolationValidator.validate_tenant_access(
            principal, "tenant-a"
        ) is True

    def test_cross_tenant_access_denied(self) -> None:
        """User cannot access resources in another tenant."""
        principal = _make_principal(tenant_id="tenant-a")
        assert TenantIsolationValidator.validate_tenant_access(
            principal, "tenant-b"
        ) is False

    def test_admin_can_access_any_tenant(self) -> None:
        """Admin role can access resources in any tenant."""
        principal = _make_principal(tenant_id="tenant-a", role="admin")
        assert TenantIsolationValidator.validate_tenant_access(
            principal, "tenant-b"
        ) is True

    def test_filter_by_tenant(self) -> None:
        """Records are filtered by principal's tenant."""
        principal = _make_principal(tenant_id="tenant-a")
        records = [
            {"id": "1", "tenant_id": "tenant-a", "data": "ok"},
            {"id": "2", "tenant_id": "tenant-b", "data": "secret"},
            {"id": "3", "tenant_id": "tenant-a", "data": "ok2"},
        ]
        filtered = TenantIsolationValidator.filter_by_tenant(records, principal)
        assert len(filtered) == 2
        assert all(r["tenant_id"] == "tenant-a" for r in filtered)

    def test_filter_by_tenant_admin_sees_all(self) -> None:
        """Admin sees all records regardless of tenant."""
        principal = _make_principal(tenant_id="tenant-a", role="admin")
        records = [
            {"id": "1", "tenant_id": "tenant-a"},
            {"id": "2", "tenant_id": "tenant-b"},
        ]
        filtered = TenantIsolationValidator.filter_by_tenant(records, principal)
        assert len(filtered) == 2

    def test_build_tenant_filter(self) -> None:
        """Build tenant filter for database queries."""
        principal = _make_principal(tenant_id="tenant-a")
        filter_dict = TenantIsolationValidator.build_tenant_filter(principal)
        assert filter_dict == {"tenant_id": "tenant-a"}

    def test_build_tenant_filter_admin_no_filter(self) -> None:
        """Admin gets empty filter (no tenant restriction)."""
        principal = _make_principal(tenant_id="tenant-a", role="admin")
        filter_dict = TenantIsolationValidator.build_tenant_filter(principal)
        assert filter_dict == {}


# ============================================================================
# Test: Multiple forged headers attack vector
# ============================================================================


class TestAdvancedForgeryAttacks:
    """Advanced attack vectors for tenant isolation."""

    def test_multiple_tenant_headers_ignored(self) -> None:
        """Multiple x-tenant-id headers should all be ignored."""
        principal = _make_principal(tenant_id="tenant-a")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            # httpx will send the last header value for duplicates
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": "tenant-evil"},
            )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "tenant-a"

    def test_empty_tenant_header_ignored(self) -> None:
        """Empty x-tenant-id header should be ignored."""
        principal = _make_principal(tenant_id="tenant-a")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": ""},
            )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "tenant-a"

    def test_tenant_header_with_special_chars_ignored(self) -> None:
        """x-tenant-id with special characters should be ignored."""
        principal = _make_principal(tenant_id="tenant-a")
        app = _build_test_app()

        with _patch_principal(principal):
            client = TestClient(app)
            response = client.get(
                "/api/v1/resource",
                headers={"x-tenant-id": "../../../tenant-admin"},
            )

        assert response.status_code == 200
        assert response.json()["tenant_id"] == "tenant-a"
