"""Role-Based Access Control for X-Agent.

Three-role model:
- admin: full access to all operations
- developer: can execute agents, create tasks, use tools (no security config changes)
- viewer: read-only access

Usage:
    @require_permission("agent:run")
    async def run_agent(principal: Principal, ...):
        ...
"""
from __future__ import annotations

import logging
import sys
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Python 3.10 compatibility: StrEnum was added in 3.11
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """String Enum for Python 3.10 compatibility."""

        pass


class Role(StrEnum):
    """User roles with increasing privilege."""

    VIEWER = "viewer"
    DEVELOPER = "developer"
    ADMIN = "admin"


# Permission definitions per role
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {"*"},  # wildcard = all permissions
    Role.DEVELOPER: {
        "agent:run",
        "agent:read",
        "agent:cancel",
        "task:create",
        "task:read",
        "task:cancel",
        "tool:execute",
        "tool:read",
        "workflow:run",
        "workflow:read",
        "workflow:create",
        "memory:read",
        "memory:write",
        "skill:run",
        "skill:read",
        "skill:install",
        "sandbox:run",
        "sandbox:read",
        "chat:send",
        "chat:read",
    },
    Role.VIEWER: {
        "agent:read",
        "task:read",
        "tool:read",
        "workflow:read",
        "memory:read",
        "skill:read",
        "sandbox:read",
        "chat:read",
    },
}


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission.

    Supports wildcard matching:
    - "*" matches everything
    - "agent:*" matches all agent permissions

    Args:
        role: Role name (e.g., "admin", "developer", "viewer").
        permission: Permission to check (e.g., "agent:run").

    Returns:
        True if role has the permission, False otherwise.
    """
    try:
        role_enum = Role(role)
    except ValueError:
        return False

    perms = ROLE_PERMISSIONS.get(role_enum, set())

    # Wildcard check
    if "*" in perms:
        return True

    # Exact match
    if permission in perms:
        return True

    # Category wildcard (e.g., "agent:*" in perms matches "agent:run")
    category = permission.split(":")[0] + ":*"
    if category in perms:
        return True

    return False


def require_permission(permission: str) -> Callable:
    """FastAPI route decorator that enforces permission check.

    The decorated function MUST accept a `principal` parameter
    that has a `.role` attribute.

    Args:
        permission: Permission string (e.g., "agent:run").

    Returns:
        Decorator function.

    Raises:
        HTTPException: 401 if no principal, 403 if permission denied.

    Example:
        @router.post("/agent/run")
        @require_permission("agent:run")
        async def run_agent(principal: Principal = Depends(get_principal)):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            principal = kwargs.get("principal")
            if principal is None:
                # Try positional args (shouldn't happen with FastAPI DI)
                raise HTTPException(status_code=401, detail="Authentication required")

            role = getattr(principal, "role", None) or "viewer"
            if not has_permission(role, permission):
                logger.warning(
                    "Permission denied: role=%s permission=%s principal=%s",
                    role,
                    permission,
                    getattr(principal, "id", "unknown"),
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: requires '{permission}'",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def list_permissions(role: str) -> list[str]:
    """List all permissions for a given role.

    Args:
        role: Role name (e.g., "admin", "developer", "viewer").

    Returns:
        Sorted list of permission strings.
    """
    try:
        role_enum = Role(role)
    except ValueError:
        return []

    perms = ROLE_PERMISSIONS.get(role_enum, set())
    if "*" in perms:
        # Collect all known permissions
        all_perms = set()
        for p_set in ROLE_PERMISSIONS.values():
            all_perms.update(p for p in p_set if p != "*")
        return sorted(all_perms)
    return sorted(perms)


def get_role_hierarchy() -> dict[str, dict[str, Any]]:
    """Get role hierarchy with metadata.

    Returns:
        Dictionary mapping role names to role metadata including level,
        description, and permissions list.
    """
    return {
        Role.ADMIN: {
            "level": 3,
            "description": "Full system access",
            "permissions": list_permissions(Role.ADMIN),
        },
        Role.DEVELOPER: {
            "level": 2,
            "description": "Execute agents, manage tasks, use tools",
            "permissions": list_permissions(Role.DEVELOPER),
        },
        Role.VIEWER: {
            "level": 1,
            "description": "Read-only access",
            "permissions": list_permissions(Role.VIEWER),
        },
    }
