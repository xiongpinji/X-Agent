"""Integration layer for workspace management with tool system.

Provides enhanced path resolution using WorkspaceManager, PathMapper,
MountManager, and FileAccessControl while maintaining backward compatibility
with existing tools.py.
"""

from __future__ import annotations

from pathlib import Path

from backend.app.core.file_access_control import FileAccessControl
from backend.app.core.mount_manager import MountManager
from backend.app.core.path_mapper import PathMapper
from backend.app.core.workspace_manager import WorkspaceConfig, WorkspaceManager


class FileSystemManager:
    """Unified file system management for tools.

    Integrates workspace, path mapping, mount, and access control systems
    to provide flexible and secure file access.
    """

    def __init__(
        self,
        workspace_base: Path,
        user_id: str,
        workspace_storage_path: Path | None = None,
        mount_storage_path: Path | None = None,
        audit_path: Path | None = None,
    ) -> None:
        """Initialize file system manager.

        Args:
            workspace_base: Base directory for workspaces
            user_id: Current user identifier
            workspace_storage_path: Path to persist workspace metadata
            mount_storage_path: Path to persist mount metadata
            audit_path: Path to store audit logs
        """
        self.user_id = user_id
        self.workspace_base = Path(workspace_base).resolve()

        self.workspace_manager = WorkspaceManager(
            self.workspace_base,
            workspace_storage_path,
        )
        self.path_mapper = PathMapper(self.workspace_base)
        self.mount_manager = MountManager(mount_storage_path)
        self.access_control = FileAccessControl(audit_path)

        # Grant default permissions
        self.access_control.grant_permission(user_id, "read")
        self.access_control.grant_permission(user_id, "write")
        self.access_control.grant_permission(user_id, "delete")

    def resolve_path(self, path: str) -> Path:
        """Resolve virtual path to real filesystem path.

        Supports both workspace paths and mounted paths.

        Args:
            path: Virtual path (e.g., "/test/file.txt" or "/mounts/project/file.txt")

        Returns:
            Real filesystem path

        Raises:
            ValueError: If path is invalid
            PermissionError: If access is denied
        """
        # Try to resolve as mount path first
        if path.startswith("/mounts/"):
            mount_path = self.mount_manager.resolve_mount_path(self.user_id, path)
            if mount_path is not None:
                return mount_path

        # Fall back to workspace path
        return self.path_mapper.map_virtual_to_real(path, self.user_id)

    def validate_read_access(self, path: str) -> tuple[bool, str | None]:
        """Validate read access to path.

        Args:
            path: Virtual path

        Returns:
            Tuple of (allowed, reason)
        """
        try:
            real_path = self.resolve_path(path)
            return self.access_control.check_read_permission(self.user_id, real_path)
        except (ValueError, PermissionError) as e:
            return False, str(e)

    def validate_write_access(self, path: str, size_bytes: int = 0) -> tuple[bool, str | None]:
        """Validate write access to path.

        Args:
            path: Virtual path
            size_bytes: Size of data to write

        Returns:
            Tuple of (allowed, reason)
        """
        try:
            real_path = self.resolve_path(path)
            return self.access_control.check_write_permission(self.user_id, real_path, size_bytes)
        except (ValueError, PermissionError) as e:
            return False, str(e)

    def validate_delete_access(self, path: str) -> tuple[bool, str | None]:
        """Validate delete access to path.

        Args:
            path: Virtual path

        Returns:
            Tuple of (allowed, reason)
        """
        try:
            real_path = self.resolve_path(path)
            return self.access_control.check_delete_permission(self.user_id, real_path)
        except (ValueError, PermissionError) as e:
            return False, str(e)

    def audit_operation(
        self,
        operation: str,
        path: str,
        success: bool,
        reason: str | None = None,
    ) -> None:
        """Record file operation for audit.

        Args:
            operation: Operation type ("read", "write", "delete", etc.)
            path: Virtual path
            success: Whether operation succeeded
            reason: Reason if operation failed
        """
        self.access_control.audit_file_operation(
            self.user_id,
            operation,
            path,
            success,
            reason,
        )

    def get_default_workspace(self) -> Path:
        """Get default project workspace for user.

        Returns:
            Path to default workspace
        """
        ws = self.workspace_manager.get_or_create_default_workspace(
            self.user_id,
            "project",
        )
        return ws.path

    def create_temporary_workspace(self, ttl_hours: int = 24) -> Path:
        """Create temporary workspace.

        Args:
            ttl_hours: Time to live in hours

        Returns:
            Path to temporary workspace
        """
        config = WorkspaceConfig(
            workspace_type="temporary",
            ttl_hours=ttl_hours,
        )
        ws = self.workspace_manager.create_workspace(self.user_id, "temporary", config)
        return ws.path

    def mount_directory(
        self,
        host_path: str,
        mount_path: str | None = None,
        read_only: bool = False,
    ) -> str:
        """Mount external directory.

        Args:
            host_path: Host filesystem path
            mount_path: Virtual mount path (auto-generated if not provided)
            read_only: Whether to mount read-only

        Returns:
            Virtual mount path

        Raises:
            ValueError: If path is invalid
            PermissionError: If unable to access path
        """
        mode = "ro" if read_only else "rw"
        mount = self.mount_manager.mount_directory(
            self.user_id,
            host_path,
            mount_path,
            mode,
        )
        return mount.mount_path

    def unmount_directory(self, mount_path: str) -> bool:
        """Unmount directory.

        Args:
            mount_path: Virtual mount path

        Returns:
            True if unmounted
        """
        mount = self.mount_manager.find_mount_by_path(self.user_id, mount_path)
        if mount is None:
            return False
        return self.mount_manager.unmount_directory(mount.mount_id)

    def list_mounts(self) -> list[dict]:
        """List mounted directories.

        Returns:
            List of mount information
        """
        mounts = self.mount_manager.list_mounts(self.user_id)
        return [
            {
                "mount_id": m.mount_id,
                "mount_path": m.mount_path,
                "host_path": str(m.host_path),
                "mode": m.mode,
                "created_at": m.created_at.isoformat(),
            }
            for m in mounts
        ]

    def get_audit_logs(self, limit: int = 100) -> list[dict]:
        """Get audit logs for user.

        Args:
            limit: Maximum records to return

        Returns:
            List of audit records
        """
        records = self.access_control.get_audit_logs(self.user_id, limit=limit)
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "operation": r.operation,
                "path": r.path,
                "success": r.success,
                "reason": r.reason,
            }
            for r in records
        ]


def create_file_system_manager(
    workspace_base: Path,
    user_id: str,
    data_dir: Path | None = None,
) -> FileSystemManager:
    """Factory function to create file system manager.

    Args:
        workspace_base: Base directory for workspaces
        user_id: Current user identifier
        data_dir: Data directory for metadata storage

    Returns:
        Configured FileSystemManager instance
    """
    if data_dir is None:
        data_dir = workspace_base / "data"

    workspace_storage = data_dir / "workspaces.json"
    mount_storage = data_dir / "mounts.json"
    audit_path = data_dir / "audit.jsonl"

    return FileSystemManager(
        workspace_base=workspace_base,
        user_id=user_id,
        workspace_storage_path=workspace_storage,
        mount_storage_path=mount_storage,
        audit_path=audit_path,
    )
