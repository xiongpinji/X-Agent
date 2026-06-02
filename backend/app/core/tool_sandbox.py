"""Tool execution sandbox for secure tool operations.

SECURITY: Implements sandboxing to restrict tool access to specific directories
and prevent unauthorized file operations.
"""

from pathlib import Path
from typing import Optional

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.path_security import PathSecurityValidator


class ToolSandbox:
    """Sandbox for restricting tool file operations."""

    def __init__(self, sandbox_root: Optional[Path] = None, max_file_size: int = 100 * 1024 * 1024):
        """Initialize tool sandbox.

        Args:
            sandbox_root: Root directory for sandboxing (default: current directory)
            max_file_size: Maximum file size in bytes (default: 100MB)
        """
        self.sandbox_root = (sandbox_root or Path.cwd()).resolve()
        self.max_file_size = max_file_size
        self.path_validator = PathSecurityValidator(self.sandbox_root)

    def validate_read_path(self, path: str | Path) -> Path:
        """Validate path for read operations.

        Args:
            path: Path to validate

        Returns:
            Validated absolute Path object

        Raises:
            api_error: If path is invalid or outside sandbox
        """
        validated = self.path_validator.validate_path(path)

        if not validated.exists():
            raise api_error(
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
                "File not found.",
                details={"path": str(path)},
            )

        return validated

    def validate_write_path(self, path: str | Path) -> Path:
        """Validate path for write operations.

        Args:
            path: Path to validate

        Returns:
            Validated absolute Path object

        Raises:
            api_error: If path is invalid or outside sandbox
        """
        validated = self.path_validator.validate_path(path)

        # Check if parent directory exists
        if not validated.parent.exists():
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                "Parent directory does not exist.",
                details={"path": str(path)},
            )

        return validated

    def validate_file_size(self, path: str | Path) -> int:
        """Validate file size is within limits.

        Args:
            path: Path to file

        Returns:
            File size in bytes

        Raises:
            api_error: If file is too large
        """
        validated = self.validate_read_path(path)

        if not validated.is_file():
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                "Path is not a file.",
                details={"path": str(path)},
            )

        file_size = validated.stat().st_size

        if file_size > self.max_file_size:
            raise api_error(
                413,
                ErrorCode.VALIDATION_ERROR,
                f"File is too large. Maximum size: {self.max_file_size} bytes.",
                details={"path": str(path), "size": file_size, "max": self.max_file_size},
            )

        return file_size

    def list_directory(self, path: str | Path) -> list[dict[str, object]]:
        """List directory contents safely.

        Args:
            path: Directory path

        Returns:
            List of file/directory information

        Raises:
            api_error: If path is invalid or not a directory
        """
        validated = self.path_validator.validate_directory(path)

        try:
            items = []
            for item in validated.iterdir():
                try:
                    stat = item.stat()
                    items.append({
                        "name": item.name,
                        "path": str(item.relative_to(self.sandbox_root)),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except OSError:
                    # Skip files we can't stat
                    continue

            return sorted(items, key=lambda x: x["name"])

        except Exception as e:
            raise api_error(
                500,
                ErrorCode.VALIDATION_ERROR,
                f"Failed to list directory: {str(e)}",
                details={"path": str(path)},
            )

    def get_sandbox_root(self) -> Path:
        """Get sandbox root directory.

        Returns:
            Sandbox root Path
        """
        return self.sandbox_root

    def is_within_sandbox(self, path: str | Path) -> bool:
        """Check if path is within sandbox.

        Args:
            path: Path to check

        Returns:
            True if within sandbox, False otherwise
        """
        return self.path_validator.is_within_sandbox(path)


# Global sandbox instance
_tool_sandbox: Optional[ToolSandbox] = None


def get_tool_sandbox(sandbox_root: Optional[Path] = None) -> ToolSandbox:
    """Get or create global tool sandbox instance.

    Args:
        sandbox_root: Optional sandbox root directory

    Returns:
        ToolSandbox instance
    """
    global _tool_sandbox
    if _tool_sandbox is None:
        _tool_sandbox = ToolSandbox(sandbox_root)
    return _tool_sandbox
