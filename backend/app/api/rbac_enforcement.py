"""RBAC enforcement dependencies for X-Agent API routes.

This module provides FastAPI dependencies that enforce Role-Based Access Control
(RBAC) on routes. Dependencies can be added to any route via the `dependencies`
parameter to enforce permission checks.

Permission levels follow the RBAC module hierarchy:
- admin: full system access (all permissions)
- developer: execution, task management, tool use (no security config changes)
- viewer: read-only access

Usage in any router file:

    from fastapi import APIRouter, Depends
    from backend.app.api.rbac_enforcement import (
        require_admin,
        require_developer,
        require_agent_run,
    )

    router = APIRouter()

    @router.post("/dangerous-action", dependencies=[Depends(require_admin)])
    async def dangerous_action():
        '''Only admins can call this route.'''
        ...

    @router.post("/agent/run", dependencies=[Depends(require_agent_run)])
    async def run_agent():
        '''Developers and admins can call this route.'''
        ...

    @router.get("/logs", dependencies=[Depends(require_viewer)])
    async def view_logs():
        '''Anyone authenticated can view logs (viewer level).'''
        ...
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, HTTPException, Request

from backend.app.core.rbac import has_permission

logger = logging.getLogger(__name__)


class PermissionDependency:
    """FastAPI dependency that enforces permission checks.

    This class implements a callable dependency that checks if the current
    principal has the required permission. It extracts the principal from
    the request state (typically set by authentication middleware) and
    verifies the role has the needed permission.

    If no principal is found, the dependency defaults to "viewer" role,
    treating the request as unauthenticated but accessible.

    Attributes:
        permission: Permission string to enforce (e.g., "agent:run").

    Example:
        The dependency automatically validates that the request's role has
        the permission. If not, it raises a 403 Forbidden response.
    """

    def __init__(self, permission: str) -> None:
        """Initialize the permission dependency.

        Args:
            permission: Permission string (e.g., "agent:run", "admin:*").
        """
        self.permission = permission

    async def __call__(self, request: Request) -> None:
        """Check permission and raise HTTPException if denied.

        Extracts the principal from request state or scope (set by auth middleware).
        If no principal exists, defaults to "viewer" role. Checks if the
        principal's role has the required permission using the RBAC module's
        has_permission function.

        Args:
            request: FastAPI request object.

        Raises:
            HTTPException: 403 Forbidden if permission is not granted.

        Returns:
            None (void dependency for route enforcement).
        """
        # State is used by legacy middleware; scope is used by get_current_principal.
        principal = getattr(request.state, "principal", None)
        if principal is None:
            scope = getattr(request, "scope", {})
            if isinstance(scope, dict):
                principal = scope.get("principal")
        if principal is None:
            # If no auth middleware ran, default to viewer (read-only)
            role = "viewer"
        else:
            role = getattr(principal, "role", "viewer")

        if not has_permission(role, self.permission):
            logger.warning(
                "RBAC permission denied: role=%s required_permission=%s path=%s",
                role,
                self.permission,
                request.url.path,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: requires '{self.permission}'",
            )


# Pre-built dependencies for common permission levels
# These can be used directly in route definitions via `dependencies=[Depends(...)]`

require_admin: Any = Depends(PermissionDependency("admin:*"))
"""FastAPI dependency requiring admin role (full system access).

Usage:
    @router.post("/config/update", dependencies=[Depends(require_admin)])
    async def update_config():
        ...
"""

require_developer: Any = Depends(PermissionDependency("agent:run"))
"""FastAPI dependency requiring developer role or higher.

Developers can run agents, create tasks, and execute tools, but cannot
change security configurations.

Usage:
    @router.post("/task/create", dependencies=[Depends(require_developer)])
    async def create_task():
        ...
"""

require_viewer: Any = Depends(PermissionDependency("agent:read"))
"""FastAPI dependency requiring viewer role or higher (read-only access).

Viewers can read agents, tasks, tools, and workflows, but cannot modify them.

Usage:
    @router.get("/agents", dependencies=[Depends(require_viewer)])
    async def list_agents():
        ...
"""

# Specific permission dependencies for granular control
# Use these when you need to enforce a specific permission beyond the standard tiers

require_agent_run: Any = Depends(PermissionDependency("agent:run"))
"""FastAPI dependency requiring agent:run permission.

Allows execution of agents. Required for POST /agent/run endpoints.

Usage:
    @router.post("/agent/run", dependencies=[Depends(require_agent_run)])
    async def run_agent():
        ...
"""

require_agent_read: Any = Depends(PermissionDependency("agent:read"))
"""FastAPI dependency requiring agent:read permission.

Allows reading agent status and details. Required for GET /agent/* endpoints.

Usage:
    @router.get("/agent/{agent_id}", dependencies=[Depends(require_agent_read)])
    async def get_agent(agent_id: str):
        ...
"""

require_agent_cancel: Any = Depends(PermissionDependency("agent:cancel"))
"""FastAPI dependency requiring agent:cancel permission.

Allows canceling running agent executions. Required for DELETE /agent/{run_id} endpoints.

Usage:
    @router.delete("/agent/{run_id}", dependencies=[Depends(require_agent_cancel)])
    async def cancel_agent_run(run_id: str):
        ...
"""

require_task_create: Any = Depends(PermissionDependency("task:create"))
"""FastAPI dependency requiring task:create permission.

Allows creating new tasks. Required for POST /task endpoints.

Usage:
    @router.post("/task", dependencies=[Depends(require_task_create)])
    async def create_task():
        ...
"""

require_task_read: Any = Depends(PermissionDependency("task:read"))
"""FastAPI dependency requiring task:read permission.

Allows reading task details and status. Required for GET /task/* endpoints.

Usage:
    @router.get("/task/{task_id}", dependencies=[Depends(require_task_read)])
    async def get_task(task_id: str):
        ...
"""

require_task_cancel: Any = Depends(PermissionDependency("task:cancel"))
"""FastAPI dependency requiring task:cancel permission.

Allows canceling running tasks. Required for DELETE /task/{task_id} endpoints.

Usage:
    @router.delete("/task/{task_id}", dependencies=[Depends(require_task_cancel)])
    async def cancel_task(task_id: str):
        ...
"""

require_tool_execute: Any = Depends(PermissionDependency("tool:execute"))
"""FastAPI dependency requiring tool:execute permission.

Allows executing tools directly. Required for POST /tool/execute endpoints.

Usage:
    @router.post("/tool/execute", dependencies=[Depends(require_tool_execute)])
    async def execute_tool():
        ...
"""

require_tool_read: Any = Depends(PermissionDependency("tool:read"))
"""FastAPI dependency requiring tool:read permission.

Allows listing and reading tool details. Required for GET /tool/* endpoints.

Usage:
    @router.get("/tools", dependencies=[Depends(require_tool_read)])
    async def list_tools():
        ...
"""

require_workflow_run: Any = Depends(PermissionDependency("workflow:run"))
"""FastAPI dependency requiring workflow:run permission.

Allows executing workflows. Required for POST /workflow/run endpoints.

Usage:
    @router.post("/workflow/run", dependencies=[Depends(require_workflow_run)])
    async def run_workflow():
        ...
"""

require_workflow_create: Any = Depends(PermissionDependency("workflow:create"))
"""FastAPI dependency requiring workflow:create permission.

Allows creating new workflows. Required for POST /workflow endpoints.

Usage:
    @router.post("/workflow", dependencies=[Depends(require_workflow_create)])
    async def create_workflow():
        ...
"""

require_workflow_read: Any = Depends(PermissionDependency("workflow:read"))
"""FastAPI dependency requiring workflow:read permission.

Allows reading workflow definitions and status. Required for GET /workflow/* endpoints.

Usage:
    @router.get("/workflow/{workflow_id}", dependencies=[Depends(require_workflow_read)])
    async def get_workflow(workflow_id: str):
        ...
"""

require_memory_read: Any = Depends(PermissionDependency("memory:read"))
"""FastAPI dependency requiring memory:read permission.

Allows querying memory and context data. Required for GET /memory/* endpoints.

Usage:
    @router.get("/memory/{session_id}", dependencies=[Depends(require_memory_read)])
    async def query_memory(session_id: str):
        ...
"""

require_memory_write: Any = Depends(PermissionDependency("memory:write"))
"""FastAPI dependency requiring memory:write permission.

Allows modifying memory and context data. Required for POST/PUT /memory/* endpoints.

Usage:
    @router.post("/memory", dependencies=[Depends(require_memory_write)])
    async def store_memory():
        ...
"""

require_skill_run: Any = Depends(PermissionDependency("skill:run"))
"""FastAPI dependency requiring skill:run permission.

Allows executing skills. Required for POST /skill/run endpoints.

Usage:
    @router.post("/skill/run", dependencies=[Depends(require_skill_run)])
    async def run_skill():
        ...
"""

require_skill_install: Any = Depends(PermissionDependency("skill:install"))
"""FastAPI dependency requiring skill:install permission.

Allows installing new skills. Required for POST /skill/install endpoints.

Usage:
    @router.post("/skill/install", dependencies=[Depends(require_skill_install)])
    async def install_skill():
        ...
"""

require_skill_read: Any = Depends(PermissionDependency("skill:read"))
"""FastAPI dependency requiring skill:read permission.

Allows listing and reading skill definitions. Required for GET /skill/* endpoints.

Usage:
    @router.get("/skills", dependencies=[Depends(require_skill_read)])
    async def list_skills():
        ...
"""

require_sandbox_run: Any = Depends(PermissionDependency("sandbox:run"))
"""FastAPI dependency requiring sandbox:run permission.

Allows executing code in sandboxed environments. Required for POST /sandbox/run endpoints.

Usage:
    @router.post("/sandbox/run", dependencies=[Depends(require_sandbox_run)])
    async def run_sandbox():
        ...
"""

require_sandbox_read: Any = Depends(PermissionDependency("sandbox:read"))
"""FastAPI dependency requiring sandbox:read permission.

Allows reading sandbox results and logs. Required for GET /sandbox/* endpoints.

Usage:
    @router.get("/sandbox/{run_id}", dependencies=[Depends(require_sandbox_read)])
    async def get_sandbox_result(run_id: str):
        ...
"""

require_chat_send: Any = Depends(PermissionDependency("chat:send"))
"""FastAPI dependency requiring chat:send permission.

Allows sending messages in chat channels. Required for POST /chat/message endpoints.

Usage:
    @router.post("/chat/message", dependencies=[Depends(require_chat_send)])
    async def send_message():
        ...
"""

require_chat_read: Any = Depends(PermissionDependency("chat:read"))
"""FastAPI dependency requiring chat:read permission.

Allows reading chat history and messages. Required for GET /chat/* endpoints.

Usage:
    @router.get("/chat/history", dependencies=[Depends(require_chat_read)])
    async def get_chat_history():
        ...
"""
