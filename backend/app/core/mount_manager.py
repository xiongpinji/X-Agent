"""Mount management system for flexible directory access.

Handles mounting user-selected directories with path mapping,
mount point management, permission control, and automatic unmounting.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from threading import RLock
from typing import Optional, Literal

from pydantic import BaseModel, Field


MountMode = Literal["ro", "rw"]


@dataclass
class MountPoint:
    """Represents a mounted directory."""
    mount_id: str
    user_id: str
    host_path: Path
    mount_path: str  # Virtual mount path (e.g., "/mounts/project")
    mode: MountMode  # "ro" (read-only) or "rw" (read-write)
    created_at: datetime
    updated_at: datetime
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "mount_id": self.mount_id,
            "user_id": self.user_id,
            "host_path": str(self.host_path),
            "mount_path": self.mount_path,
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MountPoint:
        """Create from dictionary."""
        return cls(
            mount_id=data["mount_id"],
            user_id=data["user_id"],
            host_path=Path(data["host_path"]),
            mount_path=data["mount_path"],
            mode=data["mode"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )

    def is_readable(self) -> bool:
        """Check if mount is readable."""
        return self.mode in ("ro", "rw")

    def is_writable(self) -> bool:
        """Check if mount is writable."""
        return self.mode == "rw"


class MountManager:
    """Manages mounted directories for flexible file access."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        allowed_roots: Optional[list[str | Path]] = None,
    ) -> None:
        """Initialize mount manager.

        Args:
            storage_path: Path to persist mount metadata
            allowed_roots: Optional allowlist of host directories that may be
                mounted. When provided, ``mount_directory`` rejects any host
                path that does not resolve within one of these roots
                (defense against mounting arbitrary host locations such as
                ``/etc`` or ``C:\\Windows``). When omitted (None), no root
                restriction is applied — preserves backward compatibility for
                existing callers/tests that construct a plain MountManager.
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self._mounts: dict[str, MountPoint] = {}
        self._lock = RLock()
        self.allowed_roots: Optional[tuple[Path, ...]] = None
        if allowed_roots is not None:
            resolved: list[Path] = []
            for root in allowed_roots:
                if root is None:
                    continue
                try:
                    resolved.append(Path(root).expanduser().resolve())
                except OSError:
                    continue
            self.allowed_roots = tuple(resolved)
        if self.storage_path:
            self._load_from_disk()

    def _is_root_allowed(self, host_path_obj: Path) -> bool:
        """Return True if ``host_path_obj`` is within the configured allowlist.

        When no allowlist is configured (None), all roots are permitted.
        An empty allowlist (``()``) denies everything (fail-closed).
        """
        if self.allowed_roots is None:
            return True
        for root in self.allowed_roots:
            try:
                host_path_obj.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def mount_directory(
        self,
        user_id: str,
        host_path: str,
        mount_path: Optional[str] = None,
        mode: MountMode = "rw",
    ) -> MountPoint:
        """Mount a directory for user access.

        Args:
            user_id: User identifier
            host_path: Host filesystem path to mount
            mount_path: Virtual mount path (auto-generated if not provided)
            mode: Mount mode ("ro" for read-only, "rw" for read-write)

        Returns:
            Created mount point

        Raises:
            ValueError: If path is invalid or already mounted
            PermissionError: If unable to access host path
        """
        # SECURITY: resolve first (this follows symlinks), then require the
        # resolved location to fall inside the allowlist. A symlink whose
        # target escapes the allowed roots therefore resolves outside and is
        # rejected below — no separate pre-resolution symlink walk is needed,
        # and we avoid false positives on symlinked system ancestors
        # (e.g. /tmp -> /private/tmp on macOS).
        host_path_obj = Path(host_path).resolve()

        # Validate host path exists and is accessible
        if not host_path_obj.exists():
            raise ValueError(f"Host path does not exist: {host_path}")

        if not host_path_obj.is_dir():
            raise ValueError(f"Host path is not a directory: {host_path}")

        # SECURITY: only allow mounting within the configured allowlist of
        # workspace roots. Prevents mounting arbitrary host locations and
        # rejects symlink/.. escapes (the resolved path lands outside).
        if not self._is_root_allowed(host_path_obj):
            raise PermissionError(
                f"Host path is outside the allowed mount roots: {host_path}"
            )

        # Check if already mounted
        for mount in self._mounts.values():
            if mount.user_id == user_id and mount.host_path == host_path_obj:
                raise ValueError(f"Path already mounted: {host_path}")

        # Generate mount path if not provided
        if mount_path is None:
            mount_name = host_path_obj.name or "mount"
            mount_path = f"/mounts/{mount_name}"

        # Ensure mount path is unique
        counter = 1
        original_mount_path = mount_path
        while any(m.mount_path == mount_path for m in self._mounts.values()):
            base, ext = mount_path.rsplit(".", 1) if "." in mount_path else (mount_path, "")
            mount_path = f"{original_mount_path}_{counter}"
            counter += 1

        mount_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        mount = MountPoint(
            mount_id=mount_id,
            user_id=user_id,
            host_path=host_path_obj,
            mount_path=mount_path,
            mode=mode,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._mounts[mount_id] = mount
            self._persist()

        return mount

    def unmount_directory(self, mount_id: str) -> bool:
        """Unmount a directory.

        Args:
            mount_id: Mount identifier

        Returns:
            True if unmounted, False if not found
        """
        if mount_id not in self._mounts:
            return False

        with self._lock:
            del self._mounts[mount_id]
            self._persist()

        return True

    def unmount_for_user(self, user_id: str, mount_id: str) -> str:
        """Unmount a directory, enforcing that the caller owns the mount.

        Args:
            user_id: Identifier of the requesting user
            mount_id: Mount identifier

        Returns:
            "ok" if unmounted, "not_found" if the mount does not exist,
            "forbidden" if the mount belongs to another user.

        SECURITY: callers must treat "forbidden" as HTTP 403 and "not_found"
        as 404 — never reveal another tenant's mount existence beyond this.
        """
        mount = self._mounts.get(mount_id)
        if mount is None:
            return "not_found"
        if mount.user_id != user_id:
            return "forbidden"
        self.unmount_directory(mount_id)
        return "ok"

    def get_mount(self, mount_id: str) -> Optional[MountPoint]:
        """Get mount by ID.

        Args:
            mount_id: Mount identifier

        Returns:
            Mount point or None if not found
        """
        return self._mounts.get(mount_id)

    def list_mounts(self, user_id: str) -> list[MountPoint]:
        """List mounts for a user.

        Args:
            user_id: User identifier

        Returns:
            List of mount points
        """
        mounts = [m for m in self._mounts.values() if m.user_id == user_id]
        return sorted(mounts, key=lambda m: m.created_at, reverse=True)

    def find_mount_by_path(self, user_id: str, mount_path: str) -> Optional[MountPoint]:
        """Find mount by virtual path.

        Args:
            user_id: User identifier
            mount_path: Virtual mount path

        Returns:
            Mount point or None if not found
        """
        for mount in self._mounts.values():
            if mount.user_id == user_id and mount.mount_path == mount_path:
                return mount
        return None

    def resolve_mount_path(self, user_id: str, virtual_path: str) -> Optional[Path]:
        """Resolve virtual mount path to host path.

        Args:
            user_id: User identifier
            virtual_path: Virtual path (e.g., "/mounts/project/file.txt")

        Returns:
            Host filesystem path or None if not mounted

        Raises:
            PermissionError: If access is denied
        """
        # Find matching mount
        mount = None
        remaining_path = virtual_path

        for m in self.list_mounts(user_id):
            if virtual_path.startswith(m.mount_path):
                if mount is None or len(m.mount_path) > len(mount.mount_path):
                    mount = m
                    remaining_path = virtual_path[len(m.mount_path):]

        if mount is None:
            return None

        # Construct host path
        if remaining_path.startswith("/"):
            remaining_path = remaining_path[1:]

        host_path = mount.host_path / remaining_path
        return host_path.resolve()

    def check_mount_permission(
        self,
        user_id: str,
        mount_id: str,
        operation: str,
    ) -> bool:
        """Check if user has permission for mount operation.

        Args:
            user_id: User identifier
            mount_id: Mount identifier
            operation: Operation type ("read", "write", "delete")

        Returns:
            True if operation is allowed
        """
        mount = self.get_mount(mount_id)
        if mount is None or mount.user_id != user_id:
            return False

        if operation == "read":
            return mount.is_readable()
        elif operation == "write":
            return mount.is_writable()
        elif operation == "delete":
            return mount.is_writable()

        return False

    def update_mount_mode(self, mount_id: str, mode: MountMode) -> Optional[MountPoint]:
        """Update mount access mode.

        Args:
            mount_id: Mount identifier
            mode: New mode ("ro" or "rw")

        Returns:
            Updated mount point or None if not found
        """
        mount = self._mounts.get(mount_id)
        if mount is None:
            return None

        with self._lock:
            mount.mode = mode
            mount.updated_at = datetime.now(UTC)
            self._persist()

        return mount

    def update_mount_metadata(self, mount_id: str, metadata: dict) -> Optional[MountPoint]:
        """Update mount metadata.

        Args:
            mount_id: Mount identifier
            metadata: Metadata to update

        Returns:
            Updated mount point or None if not found
        """
        mount = self._mounts.get(mount_id)
        if mount is None:
            return None

        with self._lock:
            mount.metadata.update(metadata)
            mount.updated_at = datetime.now(UTC)
            self._persist()

        return mount

    def get_mount_stats(self, mount_id: str) -> Optional[dict]:
        """Get mount statistics.

        Args:
            mount_id: Mount identifier

        Returns:
            Mount statistics or None if not found
        """
        mount = self.get_mount(mount_id)
        if mount is None:
            return None

        try:
            # Calculate directory size
            total_size = sum(
                f.stat().st_size for f in mount.host_path.rglob("*")
                if f.is_file()
            )
            file_count = sum(1 for _ in mount.host_path.rglob("*") if _.is_file())

            return {
                "mount_id": mount_id,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "mode": mount.mode,
                "created_at": mount.created_at.isoformat(),
            }
        except (OSError, RuntimeError):
            return None

    def _load_from_disk(self) -> None:
        """Load mount metadata from disk."""
        if self.storage_path is None or not self.storage_path.exists():
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for mount_data in data:
                mount = MountPoint.from_dict(mount_data)
                self._mounts[mount.mount_id] = mount
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    def _persist(self) -> None:
        """Persist mount metadata to disk."""
        if self.storage_path is None:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [m.to_dict() for m in self._mounts.values()]
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
