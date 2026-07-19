"""Path security utilities for preventing directory traversal attacks.

SECURITY: All file operations must use these utilities to validate paths.
"""

from pathlib import Path
from typing import Optional

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode


class PathSecurityValidator:
    """Validates file paths to prevent directory traversal attacks."""

    def __init__(self, sandbox_root: Optional[Path] = None):
        """Initialize path validator with optional sandbox root.

        Args:
            sandbox_root: Root directory for sandboxing file operations.
                         If set, all paths must be within this directory.
        """
        self.sandbox_root = sandbox_root.resolve() if sandbox_root else None

    def validate_path(self, path: str | Path, allow_symlinks: bool = False) -> Path:
        """Validate and normalize a file path.

        SECURITY: Prevents directory traversal attacks by:
        1. Resolving all symlinks and relative paths
        2. Checking path is within sandbox_root if configured
        3. Rejecting suspicious patterns

        Args:
            path: Path to validate
            allow_symlinks: Whether to allow symlinks (default: False for security)

        Returns:
            Validated absolute Path object

        Raises:
            api_error: If path is invalid or outside sandbox
        """
        try:
            # SECURITY: 符号链接检测必须在 resolve() 之前，针对“原始未解析路径”进行。
            # resolve() 会跟随符号链接，之后再 is_symlink() 检查的是已解析目标，
            # 永远为 False，等于检测失效（S7）。这里先用未解析路径逐段查 islink。
            if not allow_symlinks:
                original = Path(path).expanduser()
                # 候选链：原始路径本身 + 其所有祖先（均为未解析形式）
                candidates = [original, *original.parents]
                for candidate in candidates:
                    try:
                        if candidate.is_symlink():
                            raise api_error(
                                400,
                                ErrorCode.VALIDATION_ERROR,
                                "Symlinks are not allowed in file paths.",
                                details={"path": str(path)},
                            )
                    except OSError:
                        # 该段尚不存在，跳过（不存在的路径无法是符号链接）
                        continue

            # Normalize and resolve the path
            resolved = Path(path).expanduser().resolve()

            # Check if path is within sandbox_root
            if self.sandbox_root:
                try:
                    resolved.relative_to(self.sandbox_root)
                except ValueError:
                    raise api_error(
                        400,
                        ErrorCode.VALIDATION_ERROR,
                        "Path must be within the allowed directory.",
                        details={"path": str(path), "sandbox": str(self.sandbox_root)},
                    )

            return resolved

        except api_error:
            raise
        except Exception as e:
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                f"Invalid path: {str(e)}",
                details={"path": str(path)},
            )

    def validate_directory(self, path: str | Path) -> Path:
        """Validate a directory path.

        Args:
            path: Directory path to validate

        Returns:
            Validated absolute Path object

        Raises:
            api_error: If path is invalid or not a directory
        """
        validated = self.validate_path(path)

        if not validated.is_dir():
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                "Path is not a directory.",
                details={"path": str(path)},
            )

        return validated

    def validate_file(self, path: str | Path) -> Path:
        """Validate a file path.

        Args:
            path: File path to validate

        Returns:
            Validated absolute Path object

        Raises:
            api_error: If path is invalid or not a file
        """
        validated = self.validate_path(path)

        if not validated.is_file():
            raise api_error(
                400,
                ErrorCode.VALIDATION_ERROR,
                "Path is not a file.",
                details={"path": str(path)},
            )

        return validated

    def is_within_sandbox(self, path: str | Path) -> bool:
        """Check if path is within sandbox_root.

        Args:
            path: Path to check

        Returns:
            True if path is within sandbox, False otherwise
        """
        if not self.sandbox_root:
            return True

        try:
            resolved = Path(path).expanduser().resolve()
            resolved.relative_to(self.sandbox_root)
            return True
        except (ValueError, OSError):
            return False


# Global path validator instance
_path_validator: Optional[PathSecurityValidator] = None


def get_path_validator(sandbox_root: Optional[Path] = None) -> PathSecurityValidator:
    """Get or create global path validator instance.

    Args:
        sandbox_root: Optional sandbox root directory

    Returns:
        PathSecurityValidator instance
    """
    global _path_validator
    if _path_validator is None:
        _path_validator = PathSecurityValidator(sandbox_root)
    return _path_validator
