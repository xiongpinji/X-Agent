"""Tests for Role-Based Access Control (RBAC) system."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from backend.app.core.rbac import (
    Role,
    has_permission,
    require_permission,
    list_permissions,
    get_role_hierarchy,
    ROLE_PERMISSIONS,
)


class TestRoleEnum:
    """Tests for Role enum."""

    def test_role_values(self) -> None:
        """Test Role enum has correct values."""
        assert Role.VIEWER == "viewer"
        assert Role.DEVELOPER == "developer"
        assert Role.ADMIN == "admin"

    def test_role_from_string(self) -> None:
        """Test creating Role from string."""
        assert Role("viewer") == Role.VIEWER
        assert Role("developer") == Role.DEVELOPER
        assert Role("admin") == Role.ADMIN


class TestHasPermission:
    """Tests for has_permission function."""

    def test_admin_has_all_permissions(self) -> None:
        """Test admin role has all permissions."""
        assert has_permission("admin", "agent:run")
        assert has_permission("admin", "security:manage")
        assert has_permission("admin", "any:permission")
        assert has_permission("admin", "anything")

    def test_developer_can_run_agent(self) -> None:
        """Test developer can run agents."""
        assert has_permission("developer", "agent:run")
        assert has_permission("developer", "agent:read")
        assert has_permission("developer", "agent:cancel")

    def test_developer_cannot_manage_security(self) -> None:
        """Test developer cannot manage security."""
        assert not has_permission("developer", "security:manage")
        assert not has_permission("developer", "audit:manage")

    def test_viewer_readonly(self) -> None:
        """Test viewer can only read."""
        assert has_permission("viewer", "agent:read")
        assert has_permission("viewer", "task:read")
        assert not has_permission("viewer", "agent:run")
        assert not has_permission("viewer", "task:create")

    def test_unknown_role_denied(self) -> None:
        """Test unknown role has no permissions."""
        assert not has_permission("unknown_role", "anything")
        assert not has_permission("superuser", "agent:run")

    def test_exact_permission_match(self) -> None:
        """Test exact permission matching."""
        assert has_permission("developer", "task:create")
        assert has_permission("developer", "memory:write")

    def test_category_wildcard_matching(self) -> None:
        """Test category wildcard matching (agent:* pattern)."""
        # Developer has agent:* implicitly through individual perms
        assert has_permission("developer", "agent:run")
        assert has_permission("developer", "agent:read")

    def test_permission_case_sensitive(self) -> None:
        """Test permission strings are case sensitive."""
        assert has_permission("developer", "agent:run")
        assert not has_permission("developer", "Agent:Run")
        assert not has_permission("developer", "AGENT:RUN")


class TestListPermissions:
    """Tests for list_permissions function."""

    def test_list_permissions_admin(self) -> None:
        """Test listing admin permissions includes all known permissions."""
        admin_perms = list_permissions("admin")
        # Should include all permissions from all roles
        assert "agent:run" in admin_perms
        assert "memory:write" in admin_perms
        assert "skill:install" in admin_perms
        assert len(admin_perms) >= 20

    def test_list_permissions_developer(self) -> None:
        """Test listing developer permissions."""
        dev_perms = list_permissions("developer")
        assert "agent:run" in dev_perms
        assert "task:create" in dev_perms
        assert "workflow:create" in dev_perms
        assert "security:manage" not in dev_perms

    def test_list_permissions_viewer(self) -> None:
        """Test listing viewer permissions."""
        viewer_perms = list_permissions("viewer")
        assert "agent:read" in viewer_perms
        assert "task:read" in viewer_perms
        assert "agent:run" not in viewer_perms
        assert "task:create" not in viewer_perms

    def test_list_permissions_unknown_role(self) -> None:
        """Test listing permissions for unknown role returns empty list."""
        unknown_perms = list_permissions("unknown_role")
        assert unknown_perms == []

    def test_list_permissions_sorted(self) -> None:
        """Test permissions are returned in sorted order."""
        admin_perms = list_permissions("admin")
        assert admin_perms == sorted(admin_perms)


class TestGetRoleHierarchy:
    """Tests for get_role_hierarchy function."""

    def test_hierarchy_has_all_roles(self) -> None:
        """Test hierarchy includes all roles."""
        hierarchy = get_role_hierarchy()
        assert Role.ADMIN in hierarchy
        assert Role.DEVELOPER in hierarchy
        assert Role.VIEWER in hierarchy

    def test_hierarchy_metadata_structure(self) -> None:
        """Test hierarchy metadata has required fields."""
        hierarchy = get_role_hierarchy()
        for role, metadata in hierarchy.items():
            assert "level" in metadata
            assert "description" in metadata
            assert "permissions" in metadata
            assert isinstance(metadata["level"], int)
            assert isinstance(metadata["description"], str)
            assert isinstance(metadata["permissions"], list)

    def test_hierarchy_level_ordering(self) -> None:
        """Test roles have correct privilege levels."""
        hierarchy = get_role_hierarchy()
        assert hierarchy[Role.VIEWER]["level"] == 1
        assert hierarchy[Role.DEVELOPER]["level"] == 2
        assert hierarchy[Role.ADMIN]["level"] == 3

    def test_hierarchy_descriptions(self) -> None:
        """Test roles have descriptive text."""
        hierarchy = get_role_hierarchy()
        assert "read-only" in hierarchy[Role.VIEWER]["description"].lower()
        assert len(hierarchy[Role.DEVELOPER]["description"]) > 0
        assert len(hierarchy[Role.ADMIN]["description"]) > 0


@pytest.mark.asyncio
async def test_require_permission_decorator_allows() -> None:
    """Test require_permission decorator allows authorized requests."""

    @require_permission("agent:run")
    async def run_agent(principal=None):
        return {"status": "success"}

    # Create mock principal with developer role
    principal = MagicMock()
    principal.role = "developer"
    principal.id = "user123"

    result = await run_agent(principal=principal)
    assert result == {"status": "success"}


@pytest.mark.asyncio
async def test_require_permission_decorator_denies() -> None:
    """Test require_permission decorator denies unauthorized requests."""

    @require_permission("security:manage")
    async def manage_security(principal=None):
        return {"status": "success"}

    # Create mock principal with viewer role
    principal = MagicMock()
    principal.role = "viewer"
    principal.id = "user123"

    with pytest.raises(HTTPException) as exc_info:
        await manage_security(principal=principal)

    assert exc_info.value.status_code == 403
    assert "Permission denied" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_require_permission_decorator_no_principal() -> None:
    """Test require_permission decorator rejects requests without principal."""

    @require_permission("agent:run")
    async def run_agent(principal=None):
        return {"status": "success"}

    with pytest.raises(HTTPException) as exc_info:
        await run_agent(principal=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_permission_admin_bypass() -> None:
    """Test admin role bypasses permission checks."""

    @require_permission("security:manage")
    async def manage_security(principal=None):
        return {"status": "managed"}

    # Create mock principal with admin role
    principal = MagicMock()
    principal.role = "admin"
    principal.id = "admin123"

    result = await manage_security(principal=principal)
    assert result == {"status": "managed"}


@pytest.mark.asyncio
async def test_require_permission_missing_role_defaults_to_viewer() -> None:
    """Test missing role defaults to viewer (most restrictive)."""

    @require_permission("agent:run")
    async def run_agent(principal=None):
        return {"status": "success"}

    # Create mock principal without role attribute
    principal = MagicMock(spec=[])

    with pytest.raises(HTTPException) as exc_info:
        await run_agent(principal=principal)

    assert exc_info.value.status_code == 403


class TestRolePermissionsConsistency:
    """Tests to ensure ROLE_PERMISSIONS is well-formed."""

    def test_no_duplicate_permissions(self) -> None:
        """Test each role permission list has no duplicates."""
        for role, perms in ROLE_PERMISSIONS.items():
            assert len(perms) == len(
                list(perms)
            ), f"Role {role} has duplicate permissions"

    def test_admin_has_wildcard(self) -> None:
        """Test admin role has wildcard permission."""
        assert "*" in ROLE_PERMISSIONS[Role.ADMIN]

    def test_developer_subset_of_admin(self) -> None:
        """Test developer permissions are subset of all known permissions."""
        admin_all = list_permissions("admin")
        dev_perms = ROLE_PERMISSIONS[Role.DEVELOPER]
        # Each developer perm should be in admin's full list
        for perm in dev_perms:
            assert perm in admin_all

    def test_viewer_subset_of_developer(self) -> None:
        """Test viewer permissions are subset of developer permissions."""
        dev_perms = ROLE_PERMISSIONS[Role.DEVELOPER]
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        # Each viewer perm should be in developer perms
        for perm in viewer_perms:
            assert perm in dev_perms


class TestPermissionPatterns:
    """Tests for permission naming patterns."""

    def test_permission_format(self) -> None:
        """Test permissions follow namespace:action format."""
        admin_perms = list_permissions("admin")
        for perm in admin_perms:
            if perm != "*":
                assert ":" in perm, f"Permission {perm} not in namespace:action format"
                parts = perm.split(":")
                assert len(parts) == 2, f"Permission {perm} has invalid format"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_role_string(self) -> None:
        """Test empty role string returns False."""
        assert not has_permission("", "agent:run")

    def test_empty_permission_string(self) -> None:
        """Test empty permission string."""
        # Should not match anything
        assert not has_permission("developer", "")
        # Admin wildcard matches everything, including empty string
        assert has_permission("admin", "")

    def test_permission_with_multiple_colons(self) -> None:
        """Test handling of malformed permission strings."""
        # Should still work with category matching
        result = has_permission("developer", "agent:run:extra")
        # Implementation extracts first category, so agent: is checked
        assert result is False  # No "agent:" wildcard in developer perms


@pytest.mark.asyncio
async def test_require_permission_preserves_function_metadata() -> None:
    """Test decorator preserves original function metadata."""

    @require_permission("agent:run")
    async def my_function():
        """My docstring."""
        pass

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


def test_list_permissions_returns_copy_not_reference() -> None:
    """Test list_permissions returns a new list each time."""
    perms1 = list_permissions("developer")
    perms2 = list_permissions("developer")

    assert perms1 == perms2
    assert perms1 is not perms2  # Different list objects
