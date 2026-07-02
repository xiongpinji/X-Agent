"""MCP file operation tools with permission control and audit logging."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class AuditLog:
    """Audit log for tracking tool operations."""

    def __init__(self, max_entries: int = 1000):
        """Initialize audit log.

        Args:
            max_entries: Maximum number of log entries to keep
        """
        self.max_entries = max_entries
        self.entries: list[Dict[str, Any]] = []

    def log(
        self,
        operation: str,
        tool_name: str,
        path: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log an operation.

        Args:
            operation: Operation type (read, write, delete, list)
            tool_name: Name of the tool
            path: File path
            success: Whether operation succeeded
            details: Additional details
            error: Error message if failed
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "tool": tool_name,
            "path": path,
            "success": success,
            "details": details or {},
            "error": error,
        }
        self.entries.append(entry)

        # Keep only recent entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

        log_level = logging.INFO if success else logging.WARNING
        logger.log(log_level, f"Audit: {operation} {path} - {success}")

    def get_entries(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.entries[-limit:]

    def clear(self) -> None:
        """Clear all audit logs."""
        self.entries.clear()


class PermissionChecker:
    """Permission checker for file operations."""

    def __init__(self, allowed_operations: Optional[Dict[str, bool]] = None):
        """Initialize permission checker.

        Args:
            allowed_operations: Dict of operation -> allowed (read, write, delete, list)
        """
        self.allowed_operations = allowed_operations or {
            "read": True,
            "write": True,
            "delete": True,
            "list": True,
        }

    def check_permission(self, operation: str) -> bool:
        """Check if operation is allowed.

        Args:
            operation: Operation type

        Returns:
            True if allowed, False otherwise
        """
        return self.allowed_operations.get(operation, False)

    def set_permission(self, operation: str, allowed: bool) -> None:
        """Set permission for an operation.

        Args:
            operation: Operation type
            allowed: Whether to allow the operation
        """
        self.allowed_operations[operation] = allowed


class FileOperationTool:
    """File operation tool for MCP with permission control and audit logging."""

    def __init__(
        self,
        base_path: Optional[str] = None,
        permission_checker: Optional[PermissionChecker] = None,
        audit_log: Optional[AuditLog] = None,
    ):
        """Initialize file operation tool.

        Args:
            base_path: Base path for file operations (for security)
            permission_checker: Permission checker instance
            audit_log: Audit log instance
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.permission_checker = permission_checker or PermissionChecker()
        self.audit_log = audit_log or AuditLog()

    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """Read file content.

        Args:
            path: File path
            encoding: File encoding

        Returns:
            File content

        Raises:
            PermissionError: If read operation is not allowed
            FileNotFoundError: If file does not exist
        """
        if not self.permission_checker.check_permission("read"):
            error_msg = "Read operation not allowed"
            self.audit_log.log("read", "file_tool", path, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            file_path = self._resolve_path(path)
            content = file_path.read_text(encoding=encoding)
            self.audit_log.log(
                "read",
                "file_tool",
                path,
                True,
                details={"size": len(content), "encoding": encoding},
            )
            return content
        except Exception as e:
            self.audit_log.log("read", "file_tool", path, False, error=str(e))
            raise

    async def write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Write content to file.

        Args:
            path: File path
            content: Content to write
            encoding: File encoding

        Returns:
            Operation result

        Raises:
            PermissionError: If write operation is not allowed
        """
        if not self.permission_checker.check_permission("write"):
            error_msg = "Write operation not allowed"
            self.audit_log.log("write", "file_tool", path, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding=encoding)
            result = {"success": True, "path": str(file_path), "size": len(content)}
            self.audit_log.log(
                "write",
                "file_tool",
                path,
                True,
                details={"size": len(content), "encoding": encoding},
            )
            return result
        except Exception as e:
            self.audit_log.log("write", "file_tool", path, False, error=str(e))
            raise

    async def list_files(self, path: str = ".") -> Dict[str, Any]:
        """List files in directory.

        Args:
            path: Directory path

        Returns:
            List of files and directories

        Raises:
            PermissionError: If list operation is not allowed
            ValueError: If path is not a directory
        """
        if not self.permission_checker.check_permission("list"):
            error_msg = "List operation not allowed"
            self.audit_log.log("list", "file_tool", path, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            dir_path = self._resolve_path(path)
            if not dir_path.is_dir():
                raise ValueError(f"Not a directory: {path}")

            items = []
            for item in dir_path.iterdir():
                items.append(
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )

            result = {"path": str(dir_path), "items": items, "count": len(items)}
            self.audit_log.log(
                "list", "file_tool", path, True, details={"count": len(items)}
            )
            return result
        except Exception as e:
            self.audit_log.log("list", "file_tool", path, False, error=str(e))
            raise

    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file.

        Args:
            path: File path

        Returns:
            Operation result

        Raises:
            PermissionError: If delete operation is not allowed
            FileNotFoundError: If file does not exist
        """
        if not self.permission_checker.check_permission("delete"):
            error_msg = "Delete operation not allowed"
            self.audit_log.log("delete", "file_tool", path, False, error=error_msg)
            raise PermissionError(error_msg)

        try:
            file_path = self._resolve_path(path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            file_path.unlink()
            result = {"success": True, "path": str(file_path)}
            self.audit_log.log("delete", "file_tool", path, True)
            return result
        except Exception as e:
            self.audit_log.log("delete", "file_tool", path, False, error=str(e))
            raise

    async def file_exists(self, path: str) -> Dict[str, Any]:
        """Check if file exists.

        Args:
            path: File path

        Returns:
            Existence check result
        """
        try:
            file_path = self._resolve_path(path)
            exists = file_path.exists()
            self.audit_log.log(
                "exists", "file_tool", path, True, details={"exists": exists}
            )
            return {"exists": exists, "path": str(file_path)}
        except Exception as e:
            self.audit_log.log("exists", "file_tool", path, False, error=str(e))
            raise

    def _resolve_path(self, path: str) -> Path:
        """Resolve and validate file path.

        Args:
            path: File path

        Returns:
            Resolved path

        Raises:
            ValueError: If path is outside base path
        """
        base_path = self.base_path.resolve()
        resolved = (base_path / path).resolve()
        try:
            resolved.relative_to(base_path)
        except ValueError as exc:
            raise ValueError(f"Path outside base directory: {path}") from exc
        return resolved

    def get_audit_logs(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Get audit logs.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.audit_log.get_entries(limit)

    def set_permissions(self, permissions: Dict[str, bool]) -> None:
        """Set permissions for operations.

        Args:
            permissions: Dict of operation -> allowed
        """
        for operation, allowed in permissions.items():
            self.permission_checker.set_permission(operation, allowed)
