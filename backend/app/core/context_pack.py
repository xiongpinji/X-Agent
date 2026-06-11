from __future__ import annotations

import hashlib
import inspect
from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.core.contracts import RunContext
from backend.app.core.repo_context import build_repo_context

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

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".md",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".txt",
    ".ps1",
    ".cmd",
    ".bat",
}

IMPORTANT_FILENAMES = {
    "pyproject.toml",
    "package.json",
    "README.md",
    "readme.md",
    "requirements.txt",
    "uv.lock",
    "pytest.ini",
    "tsconfig.json",
}


async def build_context_pack(
    *,
    memory: Any,
    context: RunContext,
    task: str,
    workspace_root: str | Path,
    top_k: int = 8,
    max_files: int = 80,
    max_summary_chars: int = 6_000,
) -> dict[str, Any]:
    """Build a compact task package for resume, audit, and routing."""

    root = Path(workspace_root).resolve()
    memory_hits = await _memory_hits(memory, context, task, top_k=top_k)
    workspace_index = _workspace_index(root, max_files=max_files)
    repo_context = _repo_context(root)
    summary = _context_summary(
        task=task,
        memory_hits=memory_hits,
        workspace_index=workspace_index,
        repo_context=repo_context,
        max_summary_chars=max_summary_chars,
    )
    task_fingerprint = hashlib.sha256(task.encode("utf-8")).hexdigest()[:16]
    return {
        "kind": "xagent_context_pack",
        "version": 1,
        "task": task,
        "task_fingerprint": task_fingerprint,
        "tenant_id": context.tenant_id,
        "user_id": context.user_id,
        "agent_id": context.agent_id,
        "request_id": context.request_id,
        "memory": {
            "snapshot": await _memory_snapshot(memory, context.tenant_id),
            "hit_count": len(memory_hits),
            "hits": memory_hits,
        },
        "workspace": workspace_index,
        "repo": repo_context,
        "compression": {
            "strategy": "ranked_memory_plus_workspace_index_plus_repo_context",
            "summary": summary,
            "summary_chars": len(summary),
            "max_summary_chars": max_summary_chars,
            "truncated": len(summary) >= max_summary_chars,
        },
        "resume_prompt": _resume_prompt(task, summary),
        "restore_plan": [
            {
                "id": "reload_memory",
                "status": "ready",
                "detail": f"{len(memory_hits)} ranked memory hits included.",
            },
            {
                "id": "inspect_workspace",
                "status": "ready" if workspace_index["exists"] else "missing",
                "detail": f"{workspace_index['file_count']} indexed text files.",
            },
            {
                "id": "inspect_repo_context",
                "status": "ready" if repo_context.get("available") else "missing",
                "detail": str(repo_context.get("summary") or "Repository context unavailable."),
            },
            {
                "id": "continue_task",
                "status": "ready",
                "detail": "Use the resume_prompt and workspace key files before editing.",
            },
        ],
    }


async def _memory_hits(
    memory: Any,
    context: RunContext,
    task: str,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    if hasattr(memory, "search_with_scores"):
        hits = await memory.search_with_scores(context, task, layers=[1, 2, 3, 4], top_k=top_k)
        return [_format_scored_hit(hit) for hit in hits]
    if hasattr(memory, "search"):
        items = await memory.search(context, task, layers=[1, 2, 3, 4], top_k=top_k)
        return [_format_memory_item(item) for item in items]
    return []


async def _memory_snapshot(memory: Any, tenant_id: str) -> dict[str, Any]:
    if not hasattr(memory, "snapshot"):
        return {}
    try:
        snapshot = memory.snapshot(tenant_id)
    except TypeError:
        snapshot = memory.snapshot()
    if inspect.isawaitable(snapshot):
        snapshot = await snapshot
    return snapshot if isinstance(snapshot, dict) else {}


def _format_scored_hit(hit: Any) -> dict[str, Any]:
    item = hit.item
    metadata = getattr(item, "metadata", {}) or {}
    return {
        "id": item.id,
        "layer": item.layer,
        "importance": item.importance,
        "score": hit.score,
        "tags": item.tags,
        "content_preview": _clip(" ".join(item.content.split()), 500),
        "metadata": {
            key: value
            for key, value in metadata.items()
            if key in {"kind", "memory_role", "trace_id", "request_id", "agent_id"}
        },
    }


def _format_memory_item(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "layer": item.layer,
        "importance": item.importance,
        "score": None,
        "tags": item.tags,
        "content_preview": _clip(" ".join(item.content.split()), 500),
        "metadata": {},
    }


def _repo_context(root: Path) -> dict[str, Any]:
    try:
        context = build_repo_context(root, max_recent_files=12, max_status_entries=40)
    except ValueError as exc:
        return {"available": False, "error": str(exc), "summary": "Repository context unavailable."}
    except OSError as exc:
        return {"available": False, "error": str(exc), "summary": "Repository context unavailable."}

    git_status = context.get("git_status") if isinstance(context.get("git_status"), dict) else {}
    test_config = context.get("test_config") if isinstance(context.get("test_config"), dict) else {}
    return {
        "available": True,
        "kind": context.get("kind"),
        "version": context.get("version"),
        "git_status": git_status,
        "instruction_files": context.get("instruction_files", []),
        "recent_modified_files": context.get("recent_modified_files", []),
        "test_config": test_config,
        "summary": git_status.get("summary") or "Repository context captured.",
    }


def _workspace_index(root: Path, *, max_files: int) -> dict[str, Any]:
    exists = root.exists() and root.is_dir()
    if not exists:
        return {
            "exists": False,
            "root": str(root),
            "file_count": 0,
            "scanned_file_count": 0,
            "language_counts": {},
            "key_files": [],
            "top_directories": [],
        }
    files: list[Path] = []
    directories: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    for path in root.rglob("*"):
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        if path.is_dir():
            directories[relative_parts[0] if relative_parts else "."] += 1
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        files.append(path)
        language_counts[_language_key(path)] += 1
    ranked = sorted(files, key=lambda path: _file_rank(root, path))[:max_files]
    return {
        "exists": True,
        "root": str(root),
        "file_count": len(files),
        "scanned_file_count": len(ranked),
        "language_counts": dict(sorted(language_counts.items())),
        "key_files": [
            {
                "path": path.relative_to(root).as_posix(),
                "suffix": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "rank": index + 1,
            }
            for index, path in enumerate(ranked)
        ],
        "top_directories": [
            {"path": directory, "count": count}
            for directory, count in directories.most_common(10)
        ],
    }


def _file_rank(root: Path, path: Path) -> tuple[int, int, str]:
    relative = path.relative_to(root).as_posix()
    name = path.name
    if name in IMPORTANT_FILENAMES:
        return (0, len(relative), relative)
    if relative.startswith("source/backend/") or relative.startswith("backend/"):
        return (1, len(relative), relative)
    if relative.startswith("source/frontend/") or relative.startswith("frontend/"):
        return (2, len(relative), relative)
    if "test" in relative.lower():
        return (3, len(relative), relative)
    return (4, len(relative), relative)


def _language_key(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "text"


def _context_summary(
    *,
    task: str,
    memory_hits: list[dict[str, Any]],
    workspace_index: dict[str, Any],
    repo_context: dict[str, Any],
    max_summary_chars: int,
) -> str:
    lines = [
        "X-Agent context package",
        f"Task: {_clip(task, 500)}",
        f"Memory hits: {len(memory_hits)}",
        f"Workspace: {workspace_index.get('root')} exists={workspace_index.get('exists')}",
        f"Indexed files: {workspace_index.get('scanned_file_count')}/{workspace_index.get('file_count')}",
    ]
    if repo_context.get("available"):
        lines.append(f"Git status: {repo_context.get('summary')}")
        instruction_files = repo_context.get("instruction_files")
        if isinstance(instruction_files, list) and instruction_files:
            lines.append("Repository instructions:")
            for item in instruction_files[:5]:
                if isinstance(item, dict):
                    lines.append(f"- {item.get('path')} ({item.get('size_bytes')} bytes)")
        test_config = repo_context.get("test_config")
        suggested = test_config.get("suggested_commands") if isinstance(test_config, dict) else []
        if suggested:
            lines.append("Suggested validation commands:")
            for command in suggested[:5]:
                lines.append(f"- {command}")
    if workspace_index.get("language_counts"):
        languages = ", ".join(
            f"{key}={value}" for key, value in workspace_index["language_counts"].items()
        )
        lines.append(f"Languages: {languages}")
    if workspace_index.get("key_files"):
        lines.append("Key files:")
        for item in workspace_index["key_files"][:20]:
            lines.append(f"- {item['path']} ({item['size_bytes']} bytes)")
    if memory_hits:
        lines.append("Relevant memory:")
        for hit in memory_hits:
            lines.append(
                f"- L{hit['layer']} score={hit['score']} importance={hit['importance']}: {hit['content_preview']}"
            )
    return _clip("\n".join(lines), max_summary_chars)


def _resume_prompt(task: str, summary: str) -> str:
    return (
        "Continue the task using this compact context package. "
        "Inspect listed key files before changing code, preserve user changes, "
        "and run focused validation after edits.\n\n"
        f"Task:\n{task}\n\nContext summary:\n{summary}"
    )


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 3:
        return value[:limit]
    return value[: limit - 3].rstrip() + "..."
