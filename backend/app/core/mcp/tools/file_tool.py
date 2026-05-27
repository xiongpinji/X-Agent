"""MCP file operation tools."""

from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path
import json


class FileOperationTool:
    """File operation tool for MCP."""

    def __init__(self, base_path: Optional[str] = None):
        """Initialize file operation tool.

        Args:
            base_path: Base path for file operations (for security)
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()

    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        """Read file content.

        Args:
            path: File path
            encoding: File encoding

        Returns:
            File content
        """
        file_path = self._resolve_path(path)
        return file_path.read_text(encoding=encoding)

    async def write_file(self, path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Write content to file.

        Args:
            path: File path
            content: Content to write
            encoding: File encoding

        Returns:
            Operation result
        """
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding=encoding)
        return {"success": True, "path": str(file_path), "size": len(content)}

    async def list_files(self, path: str = ".") -> Dict[str, Any]:
        """List files in directory.

        Args:
            path: Directory path

        Returns:
            List of files and directories
        """
        dir_path = self._resolve_path(path)
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        items = []
        for item in dir_path.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })

        return {"path": str(dir_path), "items": items}

    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file.

        Args:
            path: File path

        Returns:
            Operation result
        """
        file_path = self._resolve_path(path)
        if not file_path.exists():
            raise ValueError(f"File not found: {path}")

        file_path.unlink()
        return {"success": True, "path": str(file_path)}

    async def file_exists(self, path: str) -> Dict[str, Any]:
        """Check if file exists.

        Args:
            path: File path

        Returns:
            Existence check result
        """
        file_path = self._resolve_path(path)
        return {"exists": file_path.exists(), "path": str(file_path)}

    def _resolve_path(self, path: str) -> Path:
        """Resolve and validate file path.

        Args:
            path: File path

        Returns:
            Resolved path

        Raises:
            ValueError: If path is outside base path
        """
        resolved = (self.base_path / path).resolve()
        if not str(resolved).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Path outside base directory: {path}")
        return resolved
