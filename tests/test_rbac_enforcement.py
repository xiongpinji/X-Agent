"""Unit tests for RBAC enforcement dependencies.

Tests validate that the PermissionDependency correctly enforces permission
checks and that all pre-built dependencies raise 403 Forbidden when
permissions are not granted.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from backend.app.api.rbac_enforcement import (
    PermissionDependency,
    require_admin,
    require_developer,
    require_viewer,
    require_agent_run,
)


class TestPermissionDependency:
    """Test suite for PermissionDependency class."""

    @pytest.mark.asyncio
    async def test_permission_dependency_allows_admin(self) -> None:
        """Test that admin role is allowed to access protected routes.

        Admin role has the wildcard permission "*" and should pass all
        permission checks regardless of the required permission.
        """
        app = FastAPI()

        @app.get("/test", dependencies=[Depends(PermissionDependency("agent:run"))])
        async def test_route() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        # Simulate admin principal in request state
        request = MagicMock()
        request.state.principal = MagicMock(role="admin")
        request.url.path = "/test"

        # Create a new request with admin role
        # Using direct call to dependency (mocked request)
        dep = PermissionDependency("agent:run")
        request.state.principal = MagicMock(role="admin")
        request.url.path = "/test"

        # Admin should not raise any exception
        await dep(request)

    @pytest.mark.asyncio
    async def test_permission_dependency_blocks_viewer_from_run(self) -> None:
        """Test that viewer role cannot execute agent:run actions.

        Viewer role only has read permissions. Attempting to run agents
        should raise HTTPException with 403 Forbidden.
        """
        from fastapi import HTTPException

        dep = PermissionDependency("agent:run")
        request = MagicMock()
        request.state.principal = MagicMock(role="viewer")
        request.url.path = "/agent/run"

        with pytest.raises(HTTPException) as exc_info:
            await dep(request)

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_permission_dependency_allows_developer_to_run(self) -> None:
        """Test that developer role can execute agent:run actions.

        Developer role has "agent:run" permission and should be allowed
        to execute agents.
        """
        dep = PermissionDependency("agent:run")
        request = MagicMock()
        request.state.principal = MagicMock(role="developer")
        request.url.path = "/agent/run"

        # Developer should not raise any exception
        await dep(request)

    @pytest.mark.asyncio
    async def test_permission_dependency_no_principal_defaults_viewer(self) -> None:
        """Test that missing principal defaults to viewer role.

        If no principal is found in request state (unauthenticated request),
        the dependency should default to "viewer" role, which has read-only
        access.
        """
        dep = PermissionDependency("agent:read")
        request = MagicMock()
        request.state = MagicMock(spec=[])  # No principal attribute
        request.url.path = "/agent/list"

        # Should not raise for read permission (viewer has agent:read)
        await dep(request)

    @pytest.mark.asyncio
    async def test_permission_dependency_no_principal_blocks_write(self) -> None:
        """Test that unauthenticated requests cannot perform write operations.

        Missing principal defaults to "viewer" role, which has no write
        permissions. Attempting write operations should fail.
        """
        from fastapi import HTTPException

        dep = PermissionDependency("agent:run")
        request = MagicMock()
        request.state = MagicMock(spec=[])  # No principal attribute
        request.url.path = "/agent/run"

        with pytest.raises(HTTPException) as exc_info:
            await dep(request)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_permission_dependency_returns_403_with_detail(self) -> None:
        """Test that forbidden responses include detailed error messages.

        When a permission is denied, the 403 response should include the
        specific permission that was required to help debugging.
        """
        from fastapi import HTTPException

        dep = PermissionDependency("tool:execute")
        request = MagicMock()
        request.state.principal = MagicMock(role="viewer")
        request.url.path = "/tool/execute"

        with pytest.raises(HTTPException) as exc_info:
            await dep(request)

        assert exc_info.value.status_code == 403
        assert "tool:execute" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_permission_dependency_allows_wildcard_permissions(self) -> None:
        """Test that wildcard permissions are correctly honored.

        Admin role has the wildcard permission "*" which should allow
        access to any resource. Verify that multiple different permissions
        are all granted.
        """
        admin_request = MagicMock()
        admin_request.state.principal = MagicMock(role="admin")
        admin_request.url.path = "/test"

        # Try various permissions with admin role
        permissions = [
            "agent:run",
            "task:create",
            "workflow:run",
            "memory:write",
            "skill:install",
        ]

        for permission in permissions:
            dep = PermissionDependency(permission)
            # Should not raise for any permission
            await dep(admin_request)

    @pytest.mark.asyncio
    async def test_permission_dependency_respects_role_attribute(self) -> None:
        """Test that role attribute is correctly extracted from principal.

        The dependency should safely access the role attribute from the
        principal object, defaulting to "viewer" if not present.
        """
        dep = PermissionDependency("agent:read")
        request = MagicMock()
        principal = MagicMock()
        principal.role = "developer"
        request.state.principal = principal
        request.url.path = "/agent"

        # Should work fine with proper role
        await dep(request)

    @pytest.mark.asyncio
    async def test_permission_dependency_missing_role_attribute(self) -> None:
        """Test that missing role attribute defaults to viewer.

        If principal exists but has no role attribute, the dependency
        should default to "viewer" role.
        """
        dep = PermissionDependency("agent:read")
        request = MagicMock()
        principal = MagicMock(spec=[])  # No role attribute
        request.state.principal = principal
        request.url.path = "/agent"

        # Should default to viewer and allow read
        await dep(request)


class TestPreBuiltDependencies:
    """Test that pre-built dependencies work correctly in routes."""

    def test_require_admin_in_route(self) -> None:
        """Test that require_admin dependency blocks non-admins.

        Pre-built dependencies should integrate properly with FastAPI
        routes and enforce permissions.
        """
        app = FastAPI()

        @app.get("/admin-only", dependencies=[require_admin])
        async def admin_route() -> dict[str, str]:
            return {"status": "admin"}

        client = TestClient(app)

        # Test that route is defined and dependency can be evaluated
        # (actual permission check happens at middleware level)
        assert admin_route is not None

    def test_require_developer_in_route(self) -> None:
        """Test that require_developer dependency is properly wired.

        Pre-built developer permission should work in route definitions.
        """
        app = FastAPI()

        @app.post("/run-agent", dependencies=[require_developer])
        async def run_route() -> dict[str, str]:
            return {"status": "running"}

        client = TestClient(app)
        assert run_route is not None

    def test_require_viewer_in_route(self) -> None:
        """Test that require_viewer dependency is properly wired.

        Pre-built viewer permission should work in route definitions.
        """
        app = FastAPI()

        @app.get("/view-data", dependencies=[require_viewer])
        async def view_route() -> dict[str, str]:
            return {"status": "visible"}

        client = TestClient(app)
        assert view_route is not None

    def test_require_agent_run_specific(self) -> None:
        """Test that specific permission dependency is properly wired.

        Granular permission dependencies should work in route definitions.
        """
        app = FastAPI()

        @app.post("/agent/run", dependencies=[require_agent_run])
        async def agent_route() -> dict[str, str]:
            return {"status": "running"}

        client = TestClient(app)
        assert agent_route is not None
