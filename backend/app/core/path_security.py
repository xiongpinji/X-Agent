"""Path security utilities for preventing directory traversal attacks.

SECURITY: All file operations must use these utilities to validate paths.
"""

import os
from pathlib import Path
from typing import Iterable, Optional, Sequence

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


class PathBoundaryError(Exception):
    """Raised when a path escapes the configured allowlist of roots.

    Carries a short, non-sensitive reason. Callers at the API layer should
    translate this into an HTTP 403 (forbidden) — escaping the workspace/
    project boundary is an authorization failure, not a validation typo.
    """

    def __init__(self, reason: str, *, path: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.path = path


def _is_within(child: Path, root: Path) -> bool:
    """Return True if ``child`` is ``root`` itself or nested under it.

    Both arguments must already be resolved (absolute, symlink-free).
    Uses ``relative_to`` so that a sibling like ``/srv/workspaces-evil`` is
    NOT considered inside ``/srv/workspaces``.
    """
    try:
        child.relative_to(root)
        return True
    except ValueError:
        return False


def _has_symlink_below_root(original: Path, resolved_root: Path) -> bool:
    """Detect a symlink on any path segment strictly below ``resolved_root``.

    SECURITY: enforces a "no symlinks inside the workspace" policy even when
    the symlink's target stays *inside* the boundary. Escapes that leave the
    boundary are already caught by the resolved-path boundary check; this is
    defense in depth.

    Robustness: we walk the *unresolved* ``original`` upward and decide where
    to stop by resolving each candidate and comparing to ``resolved_root``.
    Comparing on the resolved form means a symlinked *system ancestor* of the
    root (e.g. macOS/sandbox ``/tmp`` -> ``/private/tmp``) does not cause a
    false positive: we stop as soon as the candidate resolves to the root,
    never inspecting segments above it.

    ``original`` should be the lexically-absolute (``..``-collapsed but NOT
    symlink-resolved) path; ``resolved_root`` must be fully resolved.
    """
    candidate = original
    seen: set[Path] = set()
    while candidate not in seen:
        seen.add(candidate)
        try:
            if candidate.resolve() == resolved_root:
                # Reached the workspace root; do not inspect system-owned
                # ancestors above it.
                break
        except (OSError, RuntimeError):
            pass
        try:
            if candidate.is_symlink():
                return True
        except OSError:
            pass
        parent = candidate.parent
        if parent == candidate:  # filesystem root; stop
            break
        candidate = parent
    return False


class WorkspaceBoundary:
    """Validate that a path stays inside an allowlist of permitted roots.

    This is the reusable boundary used by the workspace API and the file
    preview API. It defends against three escape classes at once:

    1. Absolute-path escape — an attacker passes ``/etc/passwd`` or
       ``C:\\Windows\\...``; after resolution the path is not under any
       allowed root, so it is rejected.
    2. ``..`` traversal — ``resolve()`` collapses ``../../..`` and the
       result is re-checked against the roots.
    3. Symlink escape — a symlink whose target leaves the boundary resolves
       outside every root and is rejected by the boundary check; in addition
       (defense in depth) any symlink on a segment inside the workspace is
       rejected even when its target stays within the boundary.

    Roots are resolved once at construction. An empty allowlist denies
    everything (fail-closed).
    """

    def __init__(self, allowed_roots: Iterable[str | Path], *, allow_symlinks: bool = False) -> None:
        resolved: list[Path] = []
        for root in allowed_roots:
            if root is None:
                continue
            try:
                resolved.append(Path(root).expanduser().resolve())
            except OSError:
                # An unresolvable root is simply not usable; skip it rather
                # than crash boundary construction.
                continue
        self.allowed_roots: tuple[Path, ...] = tuple(resolved)
        self.allow_symlinks = allow_symlinks

    def is_allowed(self, path: str | Path) -> bool:
        """Return True if ``path`` resolves within an allowed root."""
        try:
            self.resolve_strict(path)
            return True
        except PathBoundaryError:
            return False

    def resolve_strict(self, path: str | Path) -> Path:
        """Resolve ``path`` and assert it stays inside an allowed root.

        The check is done in two complementary steps so neither symlinks nor
        ``..`` can be used to escape:

        1. Fully resolve the path (``Path.resolve()`` follows symlinks and
           collapses ``..``) and require the result to live under an allowed
           root. This alone defeats absolute-path, ``..`` and symlink-escape
           attacks, because any of them lands the resolved path *outside* the
           boundary.
        2. When symlinks are disallowed, additionally reject a symlink on any
           segment at/below the matched root — even one whose target stays
           inside the boundary — as defense in depth.

        Returns:
            The resolved, boundary-checked absolute Path.

        Raises:
            PathBoundaryError: If the path is empty, escapes every allowed
                root, or (when disallowed) traverses a symlink inside it.
        """
        raw = str(path)
        if not self.allowed_roots:
            raise PathBoundaryError("No workspace roots are allowed.", path=raw)

        try:
            original = Path(path).expanduser()
        except (OSError, ValueError) as exc:
            raise PathBoundaryError(f"Invalid path: {exc}", path=raw)

        # Step 1: fully resolve and require containment in an allowed root.
        try:
            resolved = original.resolve()
        except (OSError, RuntimeError) as exc:
            raise PathBoundaryError(f"Invalid path: {exc}", path=raw)

        matched_root = self._matching_root(resolved)
        if matched_root is None:
            raise PathBoundaryError(
                "Path is outside the allowed workspace boundary.",
                path=raw,
            )

        # Step 2 (defense in depth): forbid symlinks inside the workspace.
        if not self.allow_symlinks:
            # Use the lexically-absolute (``..``-collapsed, NOT symlink-
            # resolved) form so we inspect the user-supplied segments rather
            # than their resolved targets. The matched root is resolved, so we
            # compare against the resolved root to know when to stop.
            try:
                lexical = Path(os.path.abspath(original))
            except (OSError, ValueError) as exc:
                raise PathBoundaryError(f"Invalid path: {exc}", path=raw)
            if _has_symlink_below_root(lexical, matched_root):
                raise PathBoundaryError(
                    "Symlinks are not allowed in workspace paths.",
                    path=raw,
                )

        return resolved

    def _matching_root(self, resolved: Path) -> Optional[Path]:
        """Return the (deepest) allowed root that contains ``resolved``."""
        match: Optional[Path] = None
        for root in self.allowed_roots:
            if _is_within(resolved, root):
                if match is None or len(root.parts) > len(match.parts):
                    match = root
        return match


def enforce_path_boundary(
    path: str | Path,
    allowed_roots: Sequence[str | Path],
    *,
    allow_symlinks: bool = False,
) -> Path:
    """Validate ``path`` against ``allowed_roots`` and raise HTTP 403 on escape.

    Convenience wrapper for API handlers: builds a :class:`WorkspaceBoundary`
    and converts a :class:`PathBoundaryError` into a structured 403 error so
    that absolute-path, ``..`` and symlink escapes all surface as an
    authorization failure to the client.
    """
    boundary = WorkspaceBoundary(allowed_roots, allow_symlinks=allow_symlinks)
    try:
        return boundary.resolve_strict(path)
    except PathBoundaryError as exc:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Access to the requested path is not allowed.",
            details={"path": exc.path, "reason": exc.reason},
        )


def get_workspace_roots() -> tuple[Path, ...]:
    """Return the allowlist of roots that workspace/file APIs may touch.

    The single permitted root is ``PROJECT_ROOT/workspaces`` — the directory
    under which all per-user workspaces live. Notably this does NOT include
    the rest of ``PROJECT_ROOT`` (which holds source code and secret stores
    such as ``data/api_keys.json``), so file preview and mounting cannot be
    used to exfiltrate project secrets or arbitrary host files.
    """
    # Imported lazily to avoid a circular import at module load time
    # (settings -> ... -> path_security in some startup orderings).
    from backend.app.settings import PROJECT_ROOT

    workspace_base = (PROJECT_ROOT / "workspaces").resolve()
    return (workspace_base,)
