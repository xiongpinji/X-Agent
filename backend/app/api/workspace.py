"""API endpoints for workspace and file system management.

Provides REST API for workspace creation, mounting directories,
and managing file access.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.filesystem_manager import FileSystemManager, create_file_system_manager
from backend.app.settings import PROJECT_ROOT

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


# Request/Response Models
class WorkspaceCreateRequest(BaseModel):
    """Request to create workspace."""
    workspace_type: str = Field(..., description="Type: 'project', 'temporary', 'upload'")
    max_size_mb: int = Field(default=1000, description="Maximum size in MB")
    ttl_hours: int | None = Field(default=None, description="Time to live in hours")


class WorkspaceResponse(BaseModel):
    """Workspace information."""
    workspace_id: str
    workspace_type: str
    path: str
    created_at: str
    max_size_mb: int
    ttl_hours: int | None
    size_mb: float
    is_expired: bool


class MountDirectoryRequest(BaseModel):
    """Request to mount directory."""
    host_path: str = Field(..., description="Host filesystem path")
    mount_path: str | None = Field(default=None, description="Virtual mount path")
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
    reason: str | None = None


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    timestamp: str
    operation: str
    path: str
    success: bool
    reason: str | None = None


# Dependency to get file system manager
def get_fs_manager(user_id: str = "default") -> FileSystemManager:
    """Get file system manager for user.

    Args:
        user_id: User identifier

    Returns:
        FileSystemManager instance
    """
    workspace_base = PROJECT_ROOT / "workspaces"
    return create_file_system_manager(workspace_base, user_id)


# Workspace Endpoints
@router.post("/create", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreateRequest,
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> WorkspaceResponse:
    """Create a new workspace.

    Args:
        request: Workspace creation request
        fs_manager: File system manager

    Returns:
        Created workspace information

    Raises:
        HTTPException: If creation fails
    """
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workspace: {e}")


@router.get("/list", response_model=list[WorkspaceResponse])
async def list_workspaces(
    workspace_type: str | None = Query(None, description="Filter by type"),
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> list[WorkspaceResponse]:
    """List workspaces for user.

    Args:
        workspace_type: Optional filter by type
        fs_manager: File system manager

    Returns:
        List of workspaces
    """
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> dict:
    """Delete a workspace.

    Args:
        workspace_id: Workspace identifier
        fs_manager: File system manager

    Returns:
        Deletion result

    Raises:
        HTTPException: If deletion fails
    """
    try:
        deleted = fs_manager.workspace_manager.delete_workspace(workspace_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"success": True, "workspace_id": workspace_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount Endpoints
@router.post("/mount", response_model=MountResponse)
async def mount_directory(
    request: MountDirectoryRequest,
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> MountResponse:
    """Mount a directory.

    Args:
        request: Mount request
        fs_manager: File system manager

    Returns:
        Mount information

    Raises:
        HTTPException: If mounting fails
    """
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
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mount directory: {e}")


@router.delete("/mount/{mount_id}")
async def unmount_directory(
    mount_id: str,
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> dict:
    """Unmount a directory.

    Args:
        mount_id: Mount identifier
        fs_manager: File system manager

    Returns:
        Unmount result

    Raises:
        HTTPException: If unmounting fails
    """
    try:
        unmounted = fs_manager.mount_manager.unmount_directory(mount_id)
        if not unmounted:
            raise HTTPException(status_code=404, detail="Mount not found")
        return {"success": True, "mount_id": mount_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mounts", response_model=list[MountResponse])
async def list_mounts(
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> list[MountResponse]:
    """List mounted directories.

    Args:
        fs_manager: File system manager

    Returns:
        List of mounts
    """
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Path Validation Endpoints
@router.post("/validate-path", response_model=PathValidationResponse)
async def validate_path(
    request: PathValidationRequest,
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> PathValidationResponse:
    """Validate path access.

    Args:
        request: Validation request
        fs_manager: File system manager

    Returns:
        Validation result
    """
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Audit Endpoints
@router.get("/audit-logs", response_model=list[AuditLogEntry])
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> list[AuditLogEntry]:
    """Get audit logs.

    Args:
        limit: Maximum records to return
        fs_manager: File system manager

    Returns:
        List of audit log entries
    """
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Cleanup Endpoints
@router.post("/cleanup-expired")
async def cleanup_expired_workspaces(
    fs_manager: FileSystemManager = Depends(get_fs_manager),
) -> dict:
    """Clean up expired temporary workspaces.

    Args:
        fs_manager: File system manager

    Returns:
        Cleanup result
    """
    try:
        deleted = fs_manager.workspace_manager.cleanup_expired_workspaces()
        return {
            "success": True,
            "deleted_count": len(deleted),
            "deleted_ids": deleted,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
