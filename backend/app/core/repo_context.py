from __future__ import annotations

import configparser
import subprocess
import tomllib
from pathlib import Path
from typing import Any

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".xagent_runtime",
    "dist",
    "build",
}

INSTRUCTION_FILENAMES = ("AGENTS.md", "CLAUDE.md", "README.md", "pyproject.toml")
TEST_CONFIG_FILENAMES = ("pyproject.toml", "pytest.ini", "tox.ini", "noxfile.py")
TEXT_PREVIEW_BYTES = 4096


def build_repo_context(
    workspace_path: str | Path,
    *,
    max_recent_files: int = 20,
    max_status_entries: int = 80,
) -> dict[str, Any]:
    """Build a read-only repository context summary for a workspace."""

    workspace = _resolve_workspace(workspace_path)
    git_status = _git_status_summary(workspace, max_entries=max_status_entries)
    instruction_files = _candidate_instruction_files(workspace)
    recent_files = _recent_modified_files(workspace, max_files=max_recent_files)
    test_config = _test_config_summary(workspace)

    return {
        "kind": "xagent_repo_context",
        "version": 1,
        "workspace_path": str(workspace),
        "git_status": git_status,
        "instruction_files": instruction_files,
        "recent_modified_files": recent_files,
        "test_config": test_config,
    }


def _resolve_workspace(workspace_path: str | Path) -> Path:
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Workspace does not exist or is not a directory: {workspace}")
    return workspace


def _safe_child(workspace: Path, path: Path) -> Path | None:
    try:
        resolved = path.resolve()
        resolved.relative_to(workspace)
    except (OSError, ValueError):
        return None
    return resolved


def _relative_path(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace).as_posix()


def _git_status_summary(workspace: Path, *, max_entries: int) -> dict[str, Any]:
    result = _run_git(workspace, ["status", "--short", "--branch"])
    if result is None:
        return {
            "available": False,
            "is_repo": False,
            "branch": "",
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "entry_count": 0,
            "entries": [],
            "summary": "git command unavailable",
        }
    if result.returncode != 0:
        return {
            "available": True,
            "is_repo": False,
            "branch": "",
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "entry_count": 0,
            "entries": [],
            "summary": _clip(result.stderr.strip() or result.stdout.strip(), 500),
        }

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    branch_line = lines[0] if lines and lines[0].startswith("## ") else ""
    entries = [_parse_status_entry(line) for line in lines if not line.startswith("## ")]
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    branch, ahead, behind = _parse_branch_line(branch_line)
    return {
        "available": True,
        "is_repo": True,
        "branch": branch,
        "dirty": bool(entries),
        "ahead": ahead,
        "behind": behind,
        "entry_count": len(entries),
        "status_counts": dict(sorted(counts.items())),
        "entries": entries[:max_entries],
        "truncated": len(entries) > max_entries,
        "summary": _format_status_summary(branch, entries, ahead=ahead, behind=behind),
    }


def _run_git(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _parse_branch_line(line: str) -> tuple[str, int, int]:
    if not line:
        return "", 0, 0
    value = line[3:].strip()
    branch = value.split("...", 1)[0].strip()
    ahead = _parse_tracking_count(value, "ahead")
    behind = _parse_tracking_count(value, "behind")
    return branch, ahead, behind


def _parse_tracking_count(value: str, label: str) -> int:
    marker = f"{label} "
    if marker not in value:
        return 0
    try:
        tail = value.split(marker, 1)[1]
        number = tail.split("]", 1)[0].split(",", 1)[0].strip()
        return int(number)
    except (IndexError, ValueError):
        return 0


def _parse_status_entry(line: str) -> dict[str, str]:
    status = line[:2]
    path = line[3:].strip() if len(line) > 3 else ""
    original_path = ""
    if " -> " in path:
        original_path, path = path.split(" -> ", 1)
    return {
        "status": status,
        "path": path,
        "original_path": original_path,
    }


def _format_status_summary(branch: str, entries: list[dict[str, str]], *, ahead: int, behind: int) -> str:
    relation = []
    if ahead:
        relation.append(f"ahead {ahead}")
    if behind:
        relation.append(f"behind {behind}")
    relation_text = f" ({', '.join(relation)})" if relation else ""
    if not entries:
        return f"{branch or 'unknown branch'}{relation_text}: clean"
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    count_text = ", ".join(f"{status.strip() or status}={count}" for status, count in sorted(counts.items()))
    return f"{branch or 'unknown branch'}{relation_text}: {len(entries)} changed ({count_text})"


def _candidate_instruction_files(workspace: Path) -> list[dict[str, Any]]:
    files = []
    for filename in INSTRUCTION_FILENAMES:
        path = _safe_child(workspace, workspace / filename)
        if path is None or not path.exists() or not path.is_file():
            continue
        files.append(
            {
                "path": _relative_path(workspace, path),
                "size_bytes": path.stat().st_size,
                "preview": _read_text_preview(path),
            }
        )
    return files


def _recent_modified_files(workspace: Path, *, max_files: int) -> list[dict[str, Any]]:
    files: list[Path] = []
    for path in workspace.rglob("*"):
        relative_parts = path.relative_to(workspace).parts
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        safe_path = _safe_child(workspace, path)
        if safe_path is None or not safe_path.is_file():
            continue
        files.append(safe_path)

    ranked = sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)[:max_files]
    return [
        {
            "path": _relative_path(workspace, path),
            "size_bytes": path.stat().st_size,
            "mtime": path.stat().st_mtime,
        }
        for path in ranked
    ]


def _test_config_summary(workspace: Path) -> dict[str, Any]:
    files = []
    for filename in TEST_CONFIG_FILENAMES:
        path = _safe_child(workspace, workspace / filename)
        if path is None or not path.exists() or not path.is_file():
            continue
        files.append(
            {
                "path": _relative_path(workspace, path),
                "size_bytes": path.stat().st_size,
            }
        )

    pytest_options = _pytest_options(workspace)
    discovered_test_dirs = [
        _relative_path(workspace, path)
        for path in sorted((workspace / name for name in ("tests", "test")), key=lambda item: item.name)
        if (safe_path := _safe_child(workspace, path)) is not None and safe_path.is_dir()
    ]
    commands = _suggested_test_commands(workspace, pytest_options=pytest_options)

    return {
        "config_files": files,
        "pytest": pytest_options,
        "discovered_test_dirs": discovered_test_dirs,
        "suggested_commands": commands,
    }


def _pytest_options(workspace: Path) -> dict[str, Any]:
    pyproject = _safe_child(workspace, workspace / "pyproject.toml")
    if pyproject is not None and pyproject.exists() and pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            options = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
            if isinstance(options, dict):
                return {"source": "pyproject.toml", "options": options}
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError):
            return {"source": "pyproject.toml", "options": {}, "error": "unreadable"}

    pytest_ini = _safe_child(workspace, workspace / "pytest.ini")
    if pytest_ini is not None and pytest_ini.exists() and pytest_ini.is_file():
        parser = configparser.ConfigParser()
        try:
            parser.read(pytest_ini, encoding="utf-8")
            if parser.has_section("pytest"):
                return {"source": "pytest.ini", "options": dict(parser.items("pytest"))}
        except (OSError, configparser.Error, UnicodeDecodeError):
            return {"source": "pytest.ini", "options": {}, "error": "unreadable"}

    return {"source": "", "options": {}}


def _suggested_test_commands(workspace: Path, *, pytest_options: dict[str, Any]) -> list[str]:
    commands = []
    if (workspace / "pyproject.toml").exists() or (workspace / "pytest.ini").exists():
        testpaths = pytest_options.get("options", {}).get("testpaths")
        if isinstance(testpaths, list) and testpaths:
            commands.append(f"pytest {' '.join(str(item) for item in testpaths)}")
        else:
            commands.append("pytest")
    if (workspace / "package.json").exists():
        commands.append("npm test")
    return commands


def _read_text_preview(path: Path) -> str:
    try:
        return _clip(path.read_text(encoding="utf-8", errors="replace"), TEXT_PREVIEW_BYTES)
    except OSError:
        return ""


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."
