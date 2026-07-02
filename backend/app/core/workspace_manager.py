"""Workspace management system for X-Agent.

Provides isolated workspace management for each user, supporting multiple
workspace types (project, temporary, upload) with lifecycle management,
quota limits, and automatic cleanup.
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, UTC
from pathlib import Path
from threading import RLock
from typing import Optional

from pydantic import BaseModel, Field


class WorkspaceConfig(BaseModel):
    """Configuration for workspace creation."""
    workspace_type: str = Field(..., description="Type: 'project', 'temporary', 'upload'")
    max_size_mb: int = Field(default=1000, description="Maximum size in MB")
    ttl_hours: Optional[int] = Field(default=None, description="Time to live in hours")
    read_only: bool = Field(default=False, description="Read-only workspace")


@dataclass
class Workspace:
    """Represents a user workspace."""
    workspace_id: str
    user_id: str
    workspace_type: str
    path: Path
    created_at: datetime
    updated_at: datetime
    max_size_mb: int
    ttl_hours: Optional[int]
    read_only: bool
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "workspace_type": self.workspace_type,
            "path": str(self.path),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "max_size_mb": self.max_size_mb,
            "ttl_hours": self.ttl_hours,
            "read_only": self.read_only,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Workspace:
        """Create from dictionary."""
        return cls(
            workspace_id=data["workspace_id"],
            user_id=data["user_id"],
            workspace_type=data["workspace_type"],
            path=Path(data["path"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            max_size_mb=data["max_size_mb"],
            ttl_hours=data.get("ttl_hours"),
            read_only=data.get("read_only", False),
            metadata=data.get("metadata", {}),
        )

    def is_expired(self) -> bool:
        """Check if workspace has expired."""
        if self.ttl_hours is None:
            return False
        expiry_time = self.created_at + timedelta(hours=self.ttl_hours)
        return datetime.now(UTC) > expiry_time

    def get_size_mb(self) -> float:
        """Calculate current workspace size in MB."""
        if not self.path.exists():
            return 0.0
        total_size = sum(f.stat().st_size for f in self.path.rglob("*") if f.is_file())
        return total_size / (1024 * 1024)

    def is_over_quota(self) -> bool:
        """Check if workspace exceeds size quota."""
        return self.get_size_mb() > self.max_size_mb


class WorkspaceManager:
    """Manages user workspaces with isolation and lifecycle management."""

    def __init__(self, base_path: Path, storage_path: Optional[Path] = None) -> None:
        """Initialize workspace manager.

        Args:
            base_path: Base directory for all workspaces
            storage_path: Path to persist workspace metadata
        """
        self.base_path = Path(base_path).resolve()
        self.storage_path = Path(storage_path) if storage_path else None
        self._workspaces: dict[str, Workspace] = {}
        self._lock = RLock()
        self.base_path.mkdir(parents=True, exist_ok=True)
        if self.storage_path:
            self._load_from_disk()

    def create_workspace(
        self,
        user_id: str,
        workspace_type: str,
        config: Optional[WorkspaceConfig] = None,
    ) -> Workspace:
        """Create a new workspace for a user.

        Args:
            user_id: User identifier
            workspace_type: Type of workspace ('project', 'temporary', 'upload')
            config: Optional workspace configuration

        Returns:
            Created workspace

        Raises:
            ValueError: If workspace_type is invalid
            PermissionError: If unable to create workspace directory
        """
        if workspace_type not in ("project", "temporary", "upload"):
            raise ValueError(f"Invalid workspace type: {workspace_type}")

        if config is None:
            config = WorkspaceConfig(workspace_type=workspace_type)

        workspace_id = str(uuid.uuid4())
        workspace_path = self.base_path / user_id / workspace_type / workspace_id

        try:
            workspace_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise PermissionError(f"Failed to create workspace directory: {e}")

        now = datetime.now(UTC)
        workspace = Workspace(
            workspace_id=workspace_id,
            user_id=user_id,
            workspace_type=workspace_type,
            path=workspace_path,
            created_at=now,
            updated_at=now,
            max_size_mb=config.max_size_mb,
            ttl_hours=config.ttl_hours,
            read_only=config.read_only,
        )

        with self._lock:
            self._workspaces[workspace_id] = workspace
            self._persist()

        return workspace

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Workspace or None if not found
        """
        return self._workspaces.get(workspace_id)

    def list_workspaces(self, user_id: str, workspace_type: Optional[str] = None) -> list[Workspace]:
        """List workspaces for a user.

        Args:
            user_id: User identifier
            workspace_type: Optional filter by type

        Returns:
            List of workspaces
        """
        workspaces = [
            ws for ws in self._workspaces.values()
            if ws.user_id == user_id and (workspace_type is None or ws.workspace_type == workspace_type)
        ]
        return sorted(workspaces, key=lambda ws: ws.created_at, reverse=True)

    def delete_workspace(self, workspace_id: str, force: bool = False) -> bool:
        """Delete a workspace.

        Args:
            workspace_id: Workspace identifier
            force: Force deletion even if not empty

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionError: If workspace is read-only or deletion fails
        """
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            return False

        if workspace.read_only and not force:
            raise PermissionError("Cannot delete read-only workspace")

        try:
            if workspace.path.exists():
                shutil.rmtree(workspace.path)
        except OSError as e:
            raise PermissionError(f"Failed to delete workspace directory: {e}")

        with self._lock:
            del self._workspaces[workspace_id]
            self._persist()

        return True

    def delete_workspace_for_user(self, user_id: str, workspace_id: str) -> str:
        """Delete a workspace, enforcing that the caller owns it.

        Args:
            user_id: Identifier of the requesting user
            workspace_id: Workspace identifier

        Returns:
            "ok" if deleted, "not_found" if the workspace does not exist,
            "forbidden" if the workspace belongs to another user, or
            "read_only" if the workspace is read-only.

        SECURITY: ownership is checked before existence is otherwise
        revealed. Callers map "forbidden"/"read_only" to HTTP 403 and
        "not_found" to 404.
        """
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            return "not_found"
        if workspace.user_id != user_id:
            return "forbidden"
        if workspace.read_only:
            return "read_only"
        self.delete_workspace(workspace_id)
        return "ok"

    def cleanup_expired_workspaces(self) -> list[str]:
        """Clean up expired temporary workspaces.

        Returns:
            List of deleted workspace IDs
        """
        expired_ids = [
            ws_id for ws_id, ws in self._workspaces.items()
            if ws.workspace_type == "temporary" and ws.is_expired()
        ]

        deleted = []
        for ws_id in expired_ids:
            try:
                if self.delete_workspace(ws_id, force=True):
                    deleted.append(ws_id)
            except PermissionError:
                pass

        return deleted

    def get_or_create_default_workspace(
        self,
        user_id: str,
        workspace_type: str = "project",
    ) -> Workspace:
        """Get or create default workspace for user.

        Args:
            user_id: User identifier
            workspace_type: Type of workspace

        Returns:
            Existing or newly created workspace
        """
        workspaces = self.list_workspaces(user_id, workspace_type)
        if workspaces:
            return workspaces[0]
        return self.create_workspace(user_id, workspace_type)

    def update_workspace_metadata(self, workspace_id: str, metadata: dict) -> Optional[Workspace]:
        """Update workspace metadata.

        Args:
            workspace_id: Workspace identifier
            metadata: Metadata to update

        Returns:
            Updated workspace or None if not found
        """
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            return None

        with self._lock:
            workspace.metadata.update(metadata)
            workspace.updated_at = datetime.now(UTC)
            self._persist()

        return workspace

    def _load_from_disk(self) -> None:
        """Load workspace metadata from disk."""
        if self.storage_path is None or not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for ws_data in data:
                workspace = Workspace.from_dict(ws_data)
                self._workspaces[workspace.workspace_id] = workspace
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    def _persist(self) -> None:
        """Persist workspace metadata to disk."""
        if self.storage_path is None:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [ws.to_dict() for ws in self._workspaces.values()]
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
