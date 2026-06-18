"""API endpoints for workspace and file system management.

Provides REST API for workspace creation, mounting directories,
and managing file access.

SECURITY: every endpoint requires an authenticated principal and an
appropriate scope. File system state is isolated per principal (tenant +
user) so that no two callers ever share the ``user_id="default"`` namespace.
Mounting is restricted to the configured workspace roots, and deletion /
unmounting verify that the calling principal owns the target resource.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.filesystem_manager import create_file_system_manager, FileSystemManager
from backend.app.core.path_security import get_workspace_roots
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal


router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Scopes used by this router. Reads require ``agent:read``; state-changing
# operations require ``agent:run``. Both are granted to the user/developer/
# admin roles but withheld from ``viewer``/``anonymous`` (see ROLE_SCOPES),
# which is what produces 401 (unauthenticated) and 403 (authenticated but
# under-privileged) responses.
_SCOPE_READ = "agent:read"
_SCOPE_WRITE = "agent:run"


# Request/Response Models
class WorkspaceCreateRequest(BaseModel):
    """Request to create workspace."""
    workspace_type: str = Field(..., description="Type: 'project', 'temporary', 'upload'")
    max_size_mb: int = Field(default=1000, description="Maximum size in MB")
    ttl_hours: Optional[int] = Field(default=None, description="Time to live in hours")


class WorkspaceResponse(BaseModel):
    """Workspace information."""
    workspace_id: str
    workspace_type: str
    path: str
    created_at: str
    max_size_mb: int
    ttl_hours: Optional[int]
    size_mb: float
    is_expired: bool


class MountDirectoryRequest(BaseModel):
    """Request to mount directory."""
    host_path: str = Field(..., description="Host filesystem path")
    mount_path: Optional[str] = Field(default=None, description="Virtual mount path")
    read_only: bool = Field(default=False, description="Mount as read-only")


class MountResponse(BaseModel):
    """Mount information."""
    mount_id: str
    mount_path: str
    host_path: str
    mode: str
    created_at: str


class PathValidationRequest(BaseModel):
    """Request to validate path access."""
    path: str = Field(..., description="Virtual path")
    operation: str = Field(default="read", description="Operation: read, write, delete")


class PathValidationResponse(BaseModel):
    """Path validation result."""
    allowed: bool
    reason: Optional[str] = None


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    timestamp: str
    operation: str
    path: str
    success: bool
    reason: Optional[str] = None


def _principal_namespace(principal: Principal) -> str:
    """Build a filesystem-safe, per-principal isolation key.

    SECURITY: combines tenant and user so two tenants with the same user_id
    never collide, and so the legacy shared ``"default"`` namespace can never
    be addressed. Any character outside ``[A-Za-z0-9._-]`` is replaced to keep
    the value usable as a single path segment on every OS.
    """
    raw = f"{principal.tenant_id}__{principal.user_id}"
    safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in raw)
    # Guard against an empty or dot-only segment.
    return safe or "unknown"


def get_fs_manager(principal: PrincipalDependency) -> FileSystemManager:
    """Build a per-principal FileSystemManager.

    Authentication is enforced here (via the principal dependency); the
    manager is namespaced by tenant+user so state is never shared across
    principals. The mount manager is locked to the workspace allowlist so
    mounting cannot escape to arbitrary host locations.
    """
    if not principal.authenticated:
        raise api_error(
            401,
            ErrorCode.AUTHENTICATION_FAILED,
            "Authentication required.",
        )

    # Single source of truth: the workspace base IS the (sole) allowlisted
    # root, so per-user workspaces and the mount allowlist can never diverge.
    workspace_roots = tuple(get_workspace_roots())
    workspace_base = workspace_roots[0]
    fs_manager = create_file_system_manager(workspace_base, _principal_namespace(principal))
    # Restrict mounting to the configured workspace roots (goal 3).
    fs_manager.mount_manager.allowed_roots = workspace_roots
    return fs_manager


FsManagerDependency = Annotated[FileSystemManager, Depends(get_fs_manager)]


# Workspace Endpoints
@router.post("/create", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreateRequest,
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> WorkspaceResponse:
    """Create a new workspace for the authenticated principal."""
    enforce_scope(principal, _SCOPE_WRITE)
    try:
        from backend.app.core.workspace_manager import WorkspaceConfig

        config = WorkspaceConfig(
            workspace_type=request.workspace_type,
            max_size_mb=request.max_size_mb,
            ttl_hours=request.ttl_hours,
        )
        ws = fs_manager.workspace_manager.create_workspace(
            fs_manager.user_id,
            request.workspace_type,
            config,
        )

        return WorkspaceResponse(
            workspace_id=ws.workspace_id,
            workspace_type=ws.workspace_type,
            path=str(ws.path),
            created_at=ws.created_at.isoformat(),
            max_size_mb=ws.max_size_mb,
            ttl_hours=ws.ttl_hours,
            size_mb=ws.get_size_mb(),
            is_expired=ws.is_expired(),
        )
    except ValueError as e:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(e))
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, f"Failed to create workspace: {e}")


@router.get("/list", response_model=list[WorkspaceResponse])
async def list_workspaces(
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
    workspace_type: Optional[str] = Query(None, description="Filter by type"),
) -> list[WorkspaceResponse]:
    """List workspaces owned by the authenticated principal."""
    enforce_scope(principal, _SCOPE_READ)
    try:
        workspaces = fs_manager.workspace_manager.list_workspaces(
            fs_manager.user_id,
            workspace_type,
        )

        return [
            WorkspaceResponse(
                workspace_id=ws.workspace_id,
                workspace_type=ws.workspace_type,
                path=str(ws.path),
                created_at=ws.created_at.isoformat(),
                max_size_mb=ws.max_size_mb,
                ttl_hours=ws.ttl_hours,
                size_mb=ws.get_size_mb(),
                is_expired=ws.is_expired(),
            )
            for ws in workspaces
        ]
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> dict:
    """Delete a workspace, verifying the principal owns it.

    SECURITY: ownership (tenant+user) is checked before deletion. A request
    for a workspace owned by another principal returns 403, never deletes it.
    """
    enforce_scope(principal, _SCOPE_WRITE)
    try:
        result = fs_manager.workspace_manager.delete_workspace_for_user(
            fs_manager.user_id,
            workspace_id,
        )
    except PermissionError as e:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, str(e))
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))

    if result == "not_found":
        raise api_error(404, ErrorCode.VALIDATION_ERROR, "Workspace not found")
    if result == "forbidden":
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "You do not own this workspace.",
        )
    if result == "read_only":
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Cannot delete a read-only workspace.",
        )
    return {"success": True, "workspace_id": workspace_id}


# Mount Endpoints
@router.post("/mount", response_model=MountResponse)
async def mount_directory(
    request: MountDirectoryRequest,
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> MountResponse:
    """Mount a directory.

    SECURITY: only host paths inside the configured workspace roots may be
    mounted (allowlist enforced by MountManager). Absolute-path, ``..`` and
    symlink escapes are rejected with 403.
    """
    enforce_scope(principal, _SCOPE_WRITE)
    try:
        mount = fs_manager.mount_manager.mount_directory(
            fs_manager.user_id,
            request.host_path,
            request.mount_path,
            "ro" if request.read_only else "rw",
        )

        return MountResponse(
            mount_id=mount.mount_id,
            mount_path=mount.mount_path,
            host_path=str(mount.host_path),
            mode=mount.mode,
            created_at=mount.created_at.isoformat(),
        )
    except ValueError as e:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(e))
    except PermissionError as e:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, str(e))
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, f"Failed to mount directory: {e}")


@router.delete("/mount/{mount_id}")
async def unmount_directory(
    mount_id: str,
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> dict:
    """Unmount a directory, verifying the principal owns the mount."""
    enforce_scope(principal, _SCOPE_WRITE)
    try:
        result = fs_manager.mount_manager.unmount_for_user(fs_manager.user_id, mount_id)
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))

    if result == "not_found":
        raise api_error(404, ErrorCode.VALIDATION_ERROR, "Mount not found")
    if result == "forbidden":
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "You do not own this mount.",
        )
    return {"success": True, "mount_id": mount_id}


@router.get("/mounts", response_model=list[MountResponse])
async def list_mounts(
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> list[MountResponse]:
    """List directories mounted by the authenticated principal."""
    enforce_scope(principal, _SCOPE_READ)
    try:
        mounts = fs_manager.mount_manager.list_mounts(fs_manager.user_id)
        return [
            MountResponse(
                mount_id=m.mount_id,
                mount_path=m.mount_path,
                host_path=str(m.host_path),
                mode=m.mode,
                created_at=m.created_at.isoformat(),
            )
            for m in mounts
        ]
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))


# Path Validation Endpoints
@router.post("/validate-path", response_model=PathValidationResponse)
async def validate_path(
    request: PathValidationRequest,
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> PathValidationResponse:
    """Validate path access for the authenticated principal."""
    enforce_scope(principal, _SCOPE_READ)
    try:
        if request.operation == "read":
            allowed, reason = fs_manager.validate_read_access(request.path)
        elif request.operation == "write":
            allowed, reason = fs_manager.validate_write_access(request.path)
        elif request.operation == "delete":
            allowed, reason = fs_manager.validate_delete_access(request.path)
        else:
            raise ValueError(f"Unknown operation: {request.operation}")

        return PathValidationResponse(allowed=allowed, reason=reason)
    except ValueError as e:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(e))
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))


# Audit Endpoints
@router.get("/audit-logs", response_model=list[AuditLogEntry])
async def get_audit_logs(
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
    limit: int = Query(100, ge=1, le=1000),
) -> list[AuditLogEntry]:
    """Get the authenticated principal's file-operation audit logs."""
    enforce_scope(principal, _SCOPE_READ)
    try:
        logs = fs_manager.get_audit_logs(limit)
        return [
            AuditLogEntry(
                timestamp=log["timestamp"],
                operation=log["operation"],
                path=log["path"],
                success=log["success"],
                reason=log.get("reason"),
            )
            for log in logs
        ]
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))


# Cleanup Endpoints
@router.post("/cleanup-expired")
async def cleanup_expired_workspaces(
    principal: PrincipalDependency,
    fs_manager: FsManagerDependency,
) -> dict:
    """Clean up expired temporary workspaces for the authenticated principal."""
    enforce_scope(principal, _SCOPE_WRITE)
    try:
        deleted = fs_manager.workspace_manager.cleanup_expired_workspaces()
        return {
            "success": True,
            "deleted_count": len(deleted),
            "deleted_ids": deleted,
        }
    except Exception as e:  # noqa: BLE001
        raise api_error(500, ErrorCode.VALIDATION_ERROR, str(e))
