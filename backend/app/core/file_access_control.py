"""File access control system for security and audit.

Provides permission checking, path validation, file type restrictions,
size limits, and operation auditing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal

OperationType = Literal["read", "write", "delete", "execute", "list"]


@dataclass
class AuditRecord:
    """Record of a file operation."""
    timestamp: datetime
    user_id: str
    operation: OperationType
    path: str
    success: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "operation": self.operation,
            "path": self.path,
            "success": self.success,
            "reason": self.reason,
        }


class FileAccessControl:
    """Controls file access with permissions and auditing."""

    # Default forbidden file extensions
    _FORBIDDEN_EXTENSIONS = {
        ".exe", ".dll", ".so", ".dylib",
        ".bat", ".cmd", ".sh", ".bash",
        ".com", ".scr", ".vbs", ".js",
        ".jar", ".class", ".pyc",
    }

    # Default forbidden file patterns
    _FORBIDDEN_PATTERNS = {
        ".*", "~*", "*.tmp", "*.lock",
    }

    def __init__(
        self,
        audit_path: Path | None = None,
        max_file_size_mb: int = 100,
        max_total_size_mb: int = 1000,
    ) -> None:
        """Initialize file access control.

        Args:
            audit_path: Path to store audit logs
            max_file_size_mb: Maximum single file size in MB
            max_total_size_mb: Maximum total workspace size in MB
        """
        self.audit_path = Path(audit_path) if audit_path else None
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_total_size_bytes = max_total_size_mb * 1024 * 1024
        self._audit_records: list[AuditRecord] = []
        self._lock = RLock()
        self._user_permissions: dict[str, set[str]] = {}
        if self.audit_path:
            self._load_audit_logs()

    def check_read_permission(self, user_id: str, path: Path) -> tuple[bool, str | None]:
        """Check if user can read file.

        Args:
            user_id: User identifier
            path: File path

        Returns:
            Tuple of (allowed, reason)
        """
        # Check if path exists
        if not path.exists():
            return False, "Path does not exist"

        # Check if file is forbidden
        if self._is_forbidden_file(path):
            return False, "File type is forbidden"

        # Check permissions
        if not self._has_permission(user_id, "read"):
            return False, "User lacks read permission"

        return True, None

    def check_write_permission(self, user_id: str, path: Path, size_bytes: int = 0) -> tuple[bool, str | None]:
        """Check if user can write file.

        Args:
            user_id: User identifier
            path: File path
            size_bytes: Size of file to write

        Returns:
            Tuple of (allowed, reason)
        """
        # Check if file is forbidden
        if self._is_forbidden_file(path):
            return False, "File type is forbidden"

        # Check file size
        if size_bytes > self.max_file_size_bytes:
            return False, f"File exceeds maximum size of {self.max_file_size_bytes / (1024*1024):.0f}MB"

        # Check permissions
        if not self._has_permission(user_id, "write"):
            return False, "User lacks write permission"

        return True, None

    def check_delete_permission(self, user_id: str, path: Path) -> tuple[bool, str | None]:
        """Check if user can delete file.

        Args:
            user_id: User identifier
            path: File path

        Returns:
            Tuple of (allowed, reason)
        """
        # Check if path exists
        if not path.exists():
            return False, "Path does not exist"

        # Check permissions
        if not self._has_permission(user_id, "delete"):
            return False, "User lacks delete permission"

        return True, None

    def check_list_permission(self, user_id: str, path: Path) -> tuple[bool, str | None]:
        """Check if user can list directory.

        Args:
            user_id: User identifier
            path: Directory path

        Returns:
            Tuple of (allowed, reason)
        """
        if not path.is_dir():
            return False, "Path is not a directory"

        if not self._has_permission(user_id, "read"):
            return False, "User lacks read permission"

        return True, None

    def audit_file_operation(
        self,
        user_id: str,
        operation: OperationType,
        path: str,
        success: bool,
        reason: str | None = None,
    ) -> None:
        """Record file operation for audit.

        Args:
            user_id: User identifier
            operation: Operation type
            path: File path
            success: Whether operation succeeded
            reason: Reason if operation failed
        """
        record = AuditRecord(
            timestamp=datetime.now(UTC),
            user_id=user_id,
            operation=operation,
            path=path,
            success=success,
            reason=reason,
        )

        with self._lock:
            self._audit_records.append(record)
            if self.audit_path:
                self._persist_audit_log(record)

    def get_audit_logs(
        self,
        user_id: str | None = None,
        operation: OperationType | None = None,
        limit: int = 100,
    ) -> list[AuditRecord]:
        """Get audit logs.

        Args:
            user_id: Filter by user (optional)
            operation: Filter by operation (optional)
            limit: Maximum records to return

        Returns:
            List of audit records
        """
        records = self._audit_records

        if user_id:
            records = [r for r in records if r.user_id == user_id]

        if operation:
            records = [r for r in records if r.operation == operation]

        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]

    def grant_permission(self, user_id: str, permission: str) -> None:
        """Grant permission to user.

        Args:
            user_id: User identifier
            permission: Permission to grant (e.g., "read", "write", "delete")
        """
        with self._lock:
            if user_id not in self._user_permissions:
                self._user_permissions[user_id] = set()
            self._user_permissions[user_id].add(permission)

    def revoke_permission(self, user_id: str, permission: str) -> None:
        """Revoke permission from user.

        Args:
            user_id: User identifier
            permission: Permission to revoke
        """
        with self._lock:
            if user_id in self._user_permissions:
                self._user_permissions[user_id].discard(permission)

    def has_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission.

        Args:
            user_id: User identifier
            permission: Permission to check

        Returns:
            True if user has permission
        """
        return self._has_permission(user_id, permission)

    def set_forbidden_extensions(self, extensions: set[str]) -> None:
        """Set forbidden file extensions.

        Args:
            extensions: Set of forbidden extensions (e.g., {".exe", ".dll"})
        """
        self._FORBIDDEN_EXTENSIONS.clear()
        self._FORBIDDEN_EXTENSIONS.update(extensions)

    def add_forbidden_extension(self, extension: str) -> None:
        """Add forbidden file extension.

        Args:
            extension: Extension to forbid (e.g., ".exe")
        """
        self._FORBIDDEN_EXTENSIONS.add(extension.lower())

    def remove_forbidden_extension(self, extension: str) -> None:
        """Remove forbidden file extension.

        Args:
            extension: Extension to allow
        """
        self._FORBIDDEN_EXTENSIONS.discard(extension.lower())

    def _is_forbidden_file(self, path: Path) -> bool:
        """Check if file is forbidden.

        Args:
            path: File path

        Returns:
            True if file is forbidden
        """
        name = path.name.lower()
        suffix = path.suffix.lower()

        # Check extension
        if suffix in self._FORBIDDEN_EXTENSIONS:
            return True

        # Check patterns
        return any(self._matches_pattern(name, pattern) for pattern in self._FORBIDDEN_PATTERNS)

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches pattern.

        Args:
            name: File name
            pattern: Pattern (supports * and ?)

        Returns:
            True if matches
        """
        import fnmatch
        return fnmatch.fnmatch(name, pattern)

    def _has_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission.

        Args:
            user_id: User identifier
            permission: Permission to check

        Returns:
            True if user has permission
        """
        # Default permissions for all users
        default_permissions = {"read", "list"}

        user_perms = self._user_permissions.get(user_id, default_permissions)
        return permission in user_perms

    def _load_audit_logs(self) -> None:
        """Load audit logs from disk."""
        if self.audit_path is None or not self.audit_path.exists():
            return

        try:
            with self.audit_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        record = AuditRecord(
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            user_id=data["user_id"],
                            operation=data["operation"],
                            path=data["path"],
                            success=data["success"],
                            reason=data.get("reason"),
                        )
                        self._audit_records.append(record)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        pass
        except OSError:
            pass

    def _persist_audit_log(self, record: AuditRecord) -> None:
        """Persist single audit record to disk."""
        if self.audit_path is None:
            return

        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass
