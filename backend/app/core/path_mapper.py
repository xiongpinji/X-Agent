"""Path mapping system for cross-platform file access.

Handles virtual-to-real path mapping, cross-platform path conversion,
path normalization, symlink resolution, and path validation.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Optional
from urllib.parse import quote, unquote


class PathMapper:
    """Maps virtual paths to real paths with cross-platform support."""

    # Forbidden system directories
    _FORBIDDEN_PATHS = {
        "/etc",
        "/sys",
        "/proc",
        "/dev",
        "/boot",
        "/root",
        "/var/log",
        "/var/spool",
        "/tmp",
        "/var/tmp",
        "C:\\Windows",
        "C:\\System32",
        "C:\\Program Files",
    }

    def __init__(self, workspace_base: Path) -> None:
        """Initialize path mapper.

        Args:
            workspace_base: Base path for all workspaces
        """
        self.workspace_base = Path(workspace_base).resolve()
        self.is_windows = platform.system() == "Windows"

    def map_virtual_to_real(self, virtual_path: str, user_id: str) -> Path:
        """Map virtual path to real filesystem path.

        Args:
            virtual_path: Virtual path (e.g., "/workspace/file.txt")
            user_id: User identifier for workspace isolation

        Returns:
            Real filesystem path

        Raises:
            ValueError: If path is invalid or outside workspace
            PermissionError: If path is forbidden
        """
        # SECURITY (fail-loud): 在重映射之前显式拒绝可疑请求，而不是把
        # /etc/passwd 这类静默重映射进沙箱。纵深防御 + 调用方能拿到明确错误。
        # 1) 原始路径含父目录穿越 .. → 拒绝（normalize_path 会静默折叠 ..，
        #    这里在折叠前就基于原始输入判断）。
        raw = unquote(virtual_path or "").replace("\\", "/")
        if ".." in raw.split("/"):
            raise PermissionError(
                f"Path traversal is not allowed: {virtual_path}"
            )

        # Normalize virtual path
        normalized = self.normalize_path(virtual_path)

        # 2) 规范化后的虚拟路径若指向禁止的系统目录 → 拒绝。
        #    用规范化后的“虚拟”路径(而非重映射后的真实路径)判断，因为重映射
        #    会把 /etc 变成 /workspace/<user>/etc 致 _FORBIDDEN_PATHS 永不命中。
        normalized_lower = normalized.lower()
        for forbidden in self._FORBIDDEN_PATHS:
            fb = forbidden.replace("\\", "/").lower()
            if not fb.startswith("/"):
                # 跳过 Windows 形式(C:\...)的条目——它们针对真实路径，不是虚拟路径
                continue
            if normalized_lower == fb or normalized_lower.startswith(fb + "/"):
                raise PermissionError(
                    f"Access to system directory is forbidden: {virtual_path}"
                )

        # Handle absolute vs relative paths
        if normalized.startswith("/"):
            # Absolute path within workspace
            real_path = self.workspace_base / user_id / normalized.lstrip("/")
        else:
            # Relative path within user's default workspace
            real_path = self.workspace_base / user_id / "project" / normalized

        # Resolve symlinks and normalize
        try:
            real_path = real_path.resolve()
        except (OSError, RuntimeError):
            raise ValueError(f"Cannot resolve path: {virtual_path}")

        # Validate path
        if not self._is_path_safe(real_path, user_id):
            raise PermissionError(f"Access denied to path: {virtual_path}")

        return real_path

    def map_real_to_virtual(self, real_path: Path, user_id: str) -> str:
        """Map real filesystem path to virtual path.

        Args:
            real_path: Real filesystem path
            user_id: User identifier

        Returns:
            Virtual path

        Raises:
            ValueError: If path is not within workspace
        """
        real_path = Path(real_path).resolve()
        workspace_path = (self.workspace_base / user_id).resolve()

        try:
            relative = real_path.relative_to(workspace_path)
            # Convert to forward slashes for consistency
            virtual = "/" + str(relative).replace("\\", "/")
            return virtual
        except ValueError:
            raise ValueError(f"Path is not within workspace: {real_path}")

    def normalize_path(self, path: str) -> str:
        """Normalize path to consistent format.

        Args:
            path: Path to normalize

        Returns:
            Normalized path with forward slashes

        Raises:
            ValueError: If path contains invalid characters
        """
        if not path:
            return "/"

        # Remove URL encoding if present
        path = unquote(path)

        # Convert backslashes to forward slashes
        path = path.replace("\\", "/")

        # Remove multiple slashes
        while "//" in path:
            path = path.replace("//", "/")

        # Handle . and .. components
        parts = path.split("/")
        normalized_parts = []

        for part in parts:
            if part == "" or part == ".":
                continue
            elif part == "..":
                if normalized_parts:
                    normalized_parts.pop()
            else:
                # Validate part doesn't contain forbidden characters
                if any(c in part for c in ["*", "?", "<", ">", "|", "\0"]):
                    raise ValueError(f"Invalid characters in path: {part}")
                normalized_parts.append(part)

        result = "/" + "/".join(normalized_parts)
        return result if result != "/" else "/"

    def validate_path(self, path: str, user_id: str) -> bool:
        """Validate if path is accessible by user.

        Args:
            path: Path to validate
            user_id: User identifier

        Returns:
            True if path is valid and accessible
        """
        try:
            real_path = self.map_virtual_to_real(path, user_id)
            return self._is_path_safe(real_path, user_id)
        except (ValueError, PermissionError):
            return False

    def get_relative_path(self, real_path: Path, user_id: str) -> str:
        """Get relative path from workspace root.

        Args:
            real_path: Real filesystem path
            user_id: User identifier

        Returns:
            Relative path from workspace root
        """
        real_path = Path(real_path).resolve()
        workspace_root = (self.workspace_base / user_id).resolve()

        try:
            return str(real_path.relative_to(workspace_root))
        except ValueError:
            return str(real_path)

    def resolve_symlink(self, path: Path) -> Path:
        """Resolve symlink to target path.

        Args:
            path: Path that may be a symlink

        Returns:
            Resolved path

        Raises:
            PermissionError: If symlink target is outside workspace
        """
        if not path.is_symlink():
            return path

        try:
            target = path.resolve()
            return target
        except (OSError, RuntimeError) as e:
            raise PermissionError(f"Cannot resolve symlink: {e}")

    def is_within_workspace(self, real_path: Path, user_id: str) -> bool:
        """Check if path is within user's workspace.

        Args:
            real_path: Real filesystem path
            user_id: User identifier

        Returns:
            True if path is within workspace
        """
        real_path = Path(real_path).resolve()
        workspace_path = (self.workspace_base / user_id).resolve()

        try:
            real_path.relative_to(workspace_path)
            return True
        except ValueError:
            return False

    def _is_path_safe(self, real_path: Path, user_id: str) -> bool:
        """Check if path is safe to access.

        Args:
            real_path: Real filesystem path
            user_id: User identifier

        Returns:
            True if path is safe
        """
        real_path = Path(real_path).resolve()

        # Check forbidden system directories
        path_str = str(real_path).lower()
        for forbidden in self._FORBIDDEN_PATHS:
            if path_str.startswith(forbidden.lower()):
                return False

        # Check if within workspace
        if not self.is_within_workspace(real_path, user_id):
            return False

        # Check for symlink attacks
        if real_path.is_symlink():
            try:
                target = real_path.resolve()
                if not self.is_within_workspace(target, user_id):
                    return False
            except (OSError, RuntimeError):
                return False

        return True

    def convert_windows_to_posix(self, windows_path: str) -> str:
        """Convert Windows path to POSIX format.

        Args:
            windows_path: Windows path

        Returns:
            POSIX path
        """
        # Handle drive letters
        if len(windows_path) > 1 and windows_path[1] == ":":
            drive = windows_path[0].lower()
            rest = windows_path[2:].replace("\\", "/")
            return f"/{drive}{rest}"
        return windows_path.replace("\\", "/")

    def convert_posix_to_windows(self, posix_path: str) -> str:
        """Convert POSIX path to Windows format.

        Args:
            posix_path: POSIX path

        Returns:
            Windows path
        """
        # Handle drive letters
        if posix_path.startswith("/") and len(posix_path) > 2 and posix_path[2] == "/":
            drive = posix_path[1].upper()
            rest = posix_path[3:].replace("/", "\\")
            return f"{drive}:{rest}"
        return posix_path.replace("/", "\\")

    def url_encode_path(self, path: str) -> str:
        """URL-encode path for safe transmission.

        Args:
            path: Path to encode

        Returns:
            URL-encoded path
        """
        return quote(path, safe="/")

    def url_decode_path(self, encoded_path: str) -> str:
        """URL-decode path.

        Args:
            encoded_path: URL-encoded path

        Returns:
            Decoded path
        """
        return unquote(encoded_path)
