"""Completion evidence ("完成证据") for ``xagent agent run``.

Extracts a codex-exec-style evidence summary from an agent run result:

* changed files (with size-delta diff summary when available)
* verification results (backend observations + CLI-side syntax check)
* trace_id / status / iterations

Also provides the Track D2 *completion contract* (证据化完成判定, modeled
after Hermes "Judgment"): a structured, machine-readable verdict on whether
a claimed-completed task is backed by verifiable evidence.

Used by both the rich interactive output and the headless JSON output.
"""

from __future__ import annotations

import json
import py_compile
import re
from pathlib import Path
from typing import Any

# Tools whose successful execution mutates files on disk.
WRITE_TOOLS = {"write_file", "apply_text_patch", "apply_batch_patch"}


def build_evidence(result: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized evidence dict from an agent run result.

    Args:
        result: Agent run result dictionary (AgentRunResponse dump shape).

    Returns:
        Evidence dictionary with trace_id, status, iterations, fast_path,
        changed_files, verification, backend_verification and tool_calls.
    """
    summary = result.get("execution_summary") or {}
    tool_calls = [tc for tc in (result.get("tool_calls") or []) if isinstance(tc, dict)]

    changed_files: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add_file(
        path: Any,
        tool: str = "",
        success: bool = True,
        previous_size: Any = None,
        current_size: Any = None,
    ) -> None:
        if not path:
            return
        path_str = str(path)
        if path_str in seen:
            # Merge size info into the existing entry when available.
            if previous_size is not None or current_size is not None:
                for entry in changed_files:
                    if entry["path"] == path_str and "size_change" not in entry:
                        entry["size_change"] = (
                            f"{previous_size if previous_size is not None else '?'} -> "
                            f"{current_size if current_size is not None else '?'} bytes"
                        )
            return
        seen.add(path_str)
        entry: dict[str, Any] = {"path": path_str, "tool": tool, "success": bool(success)}
        if previous_size is not None or current_size is not None:
            entry["size_change"] = (
                f"{previous_size if previous_size is not None else '?'} -> "
                f"{current_size if current_size is not None else '?'} bytes"
            )
        changed_files.append(entry)

    # 1) Preferred source: execution_summary.file_results / affected_files.
    for file_result in summary.get("file_results") or []:
        if isinstance(file_result, dict):
            _add_file(
                file_result.get("path"),
                tool=str(file_result.get("tool") or ""),
                success=bool(file_result.get("success", True)),
            )
    for path in summary.get("affected_files") or []:
        _add_file(path)

    # 2) Enrich with size deltas from tool call outputs (diff summary).
    for tc in tool_calls:
        output = tc.get("output")
        if isinstance(output, dict) and output.get("path"):
            if "previous_size" in output or "current_size" in output:
                _add_file(
                    output.get("path"),
                    tool=str(tc.get("tool_name") or ""),
                    success=bool(tc.get("success", True)),
                    previous_size=output.get("previous_size"),
                    current_size=output.get("current_size"),
                )

    # 3) Fallback: arguments_preview of successful write-tool calls.
    if not changed_files:
        for tc in tool_calls:
            if not tc.get("success"):
                continue
            if str(tc.get("tool_name") or "") not in WRITE_TOOLS:
                continue
            args = tc.get("arguments_preview") or {}
            if isinstance(args, dict):
                _add_file(
                    args.get("path"),
                    tool=str(tc.get("tool_name") or ""),
                    success=True,
                )

    verification = verify_changed_files(changed_files)

    # Backend-side verification signals recorded as observations.
    backend_verification = [
        obs
        for obs in (summary.get("observations") or [])
        if isinstance(obs, str) and '"verification"' in obs
    ]

    return {
        "trace_id": result.get("trace_id", ""),
        "status": result.get("status", ""),
        "iterations": result.get("iterations", 0),
        "fast_path": bool(summary.get("fast_path")),
        "changed_files": changed_files,
        "verification": verification,
        "backend_verification": backend_verification,
        "tool_calls": [
            {"tool": tc.get("tool_name", ""), "success": bool(tc.get("success", False))}
            for tc in tool_calls
        ],
    }


def verify_changed_files(changed_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verify changed files from the CLI side.

    Checks file existence for every changed file and runs a Python syntax
    check (``py_compile``) on ``*.py`` files.
    """
    results: list[dict[str, Any]] = []
    for entry in changed_files:
        path = Path(entry["path"])
        if not path.exists():
            results.append(
                {
                    "path": entry["path"],
                    "check": "exists",
                    "passed": False,
                    "detail": "file not found on disk",
                }
            )
            continue
        results.append(
            {
                "path": entry["path"],
                "check": "exists",
                "passed": True,
                "detail": f"{path.stat().st_size} bytes",
            }
        )
        if path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True)
                results.append(
                    {
                        "path": entry["path"],
                        "check": "syntax",
                        "passed": True,
                        "detail": "py_compile OK",
                    }
                )
            except py_compile.PyCompileError as e:
                results.append(
                    {
                        "path": entry["path"],
                        "check": "syntax",
                        "passed": False,
                        "detail": str(e).splitlines()[0] if str(e) else "syntax error",
                    }
                )
    return results


def print_evidence(evidence: dict[str, Any], config: Any = None) -> None:
    """Render the evidence section ("完成证据") to the terminal."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    lines: list[str] = []
    status = evidence.get("status", "")
    lines.append(f"status: {status}    iterations: {evidence.get('iterations', 0)}")
    if evidence.get("fast_path"):
        lines.append("(fast path: 任务被判定为简单问答，未执行工具调用)")

    console.print()
    console.print(Panel("\n".join(lines), title="完成证据 (Completion Evidence)", border_style="cyan"))

    # ─── Changed files (diff summary) ────────────────────────────────────
    changed = evidence.get("changed_files") or []
    if changed:
        table = Table(title="变更文件 (Changed Files)")
        table.add_column("File", style="cyan")
        table.add_column("Tool")
        table.add_column("Result")
        table.add_column("Diff 摘要")
        for entry in changed:
            table.add_row(
                entry.get("path", ""),
                entry.get("tool", ""),
                "✓ written" if entry.get("success") else "✗ failed",
                entry.get("size_change", "-"),
            )
        console.print(table)
    else:
        console.print("[dim]变更文件: 无（未发生文件写入）[/dim]")

    # ─── Verification ────────────────────────────────────────────────────
    verification = evidence.get("verification") or []
    backend_verification = evidence.get("backend_verification") or []
    if verification or backend_verification:
        table = Table(title="验证结果 (Verification)")
        table.add_column("Target", style="cyan")
        table.add_column("Check")
        table.add_column("Result")
        table.add_column("Detail")
        for item in verification:
            table.add_row(
                item.get("path", ""),
                item.get("check", ""),
                "[green]✓ pass[/green]" if item.get("passed") else "[red]✗ fail[/red]",
                item.get("detail", ""),
            )
        for obs in backend_verification:
            table.add_row("(backend)", "verification", "[green]✓[/green]", obs[:120])
        console.print(table)
    else:
        console.print("[dim]验证结果: 无可验证的文件变更[/dim]")

    console.print(f"[dim]trace_id: {evidence.get('trace_id', 'N/A')}[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# Track D2: Completion Contract (证据化完成判定)
# ─────────────────────────────────────────────────────────────────────────────

_SIZE_CHANGE_RE = re.compile(r"^(?P<before>\d+|\?)\s*->\s*(?P<after>\d+|\?)\s*bytes$")


def _parse_size_change(size_change: Any) -> tuple[Any, Any]:
    """Parse a ``"0 -> 42 bytes"`` size-delta string into (before, after).

    ``"?"`` (unknown) maps to ``None``.
    """
    if not isinstance(size_change, str):
        return None, None
    match = _SIZE_CHANGE_RE.match(size_change.strip())
    if not match:
        return None, None
    before = match.group("before")
    after = match.group("after")
    return (
        int(before) if before != "?" else None,
        int(after) if after != "?" else None,
    )


def build_completion_contract(result: dict[str, Any], task: str | None = None) -> dict[str, Any]:
    """Build a structured completion contract from an agent run result.

    The contract is the machine-readable "judgment" of whether a task that
    claims to be done is actually backed by verifiable evidence::

        {
            "task": str,
            "trace_id": str,
            "status": str,
            "files_changed": [
                {"path", "action", "bytes_before", "bytes_after", "syntax_check"}
            ],
            "verifications": [{"path", "check", "passed", "detail"}],
            "evidence_complete": bool,
            "missing_evidence": [str],
        }

    Semantics of ``evidence_complete``:

    * fast-path / pure Q&A runs (no tool calls) do not require file evidence
      — a simple question answered is complete as-is.
    * runs with file changes require every changed file to exist on disk and
      (for ``*.py``) to pass the syntax check.
    * write-tool calls without any captured file-change evidence count as
      missing evidence.
    * a non-``completed`` status is always incomplete evidence.
    """
    evidence = build_evidence(result)
    status = str(evidence.get("status", ""))
    fast_path = bool(evidence.get("fast_path"))
    tool_calls = evidence.get("tool_calls") or []
    changed_files = evidence.get("changed_files") or []
    verification = evidence.get("verification") or []

    # ─── files_changed with action / byte deltas / syntax verdict ──────────
    files_changed: list[dict[str, Any]] = []
    for entry in changed_files:
        path = str(entry.get("path", ""))
        bytes_before, bytes_after = _parse_size_change(entry.get("size_change"))
        disk_path = Path(path)
        exists = disk_path.exists()
        if bytes_after is None and exists:
            bytes_after = disk_path.stat().st_size

        if not exists:
            action = "missing"
        elif bytes_before in (None, 0):
            action = "created"
        else:
            action = "modified"

        syntax_check = "skipped"
        if path.endswith(".py"):
            syntax_results = [
                v for v in verification if v.get("path") == path and v.get("check") == "syntax"
            ]
            if syntax_results:
                syntax_check = "pass" if all(v.get("passed") for v in syntax_results) else "fail"
            elif not exists:
                syntax_check = "fail"

        files_changed.append(
            {
                "path": path,
                "action": action,
                "bytes_before": bytes_before,
                "bytes_after": bytes_after,
                "syntax_check": syntax_check,
            }
        )

    # ─── verifications (CLI-side checks + backend observations) ────────────
    verifications: list[dict[str, Any]] = [dict(v) for v in verification]
    for obs in evidence.get("backend_verification") or []:
        verifications.append(
            {
                "path": "(backend)",
                "check": "verification",
                "passed": True,
                "detail": str(obs),
            }
        )

    # ─── missing-evidence judgment ──────────────────────────────────────────
    missing: list[str] = []

    if status != "completed":
        missing.append(f"任务状态为 '{status or 'unknown'}'，而非 'completed'")

    if not fast_path and tool_calls:
        write_calls = [tc for tc in tool_calls if str(tc.get("tool", "")) in WRITE_TOOLS]
        if write_calls and not files_changed:
            missing.append("检测到写工具调用，但未捕获到任何文件变更证据")
        failed_calls = [tc for tc in tool_calls if not tc.get("success")]
        for tc in failed_calls:
            missing.append(f"工具调用失败且无成功证据: {tc.get('tool', '?')}")

    for file_entry in files_changed:
        if file_entry["action"] == "missing":
            missing.append(f"变更文件在磁盘上不存在: {file_entry['path']}")
        if file_entry["syntax_check"] == "fail":
            missing.append(f"语法检查未通过: {file_entry['path']}")

    return {
        "task": task if task is not None else str(result.get("task", "")),
        "trace_id": evidence.get("trace_id", ""),
        "status": status,
        "files_changed": files_changed,
        "verifications": verifications,
        "evidence_complete": not missing,
        "missing_evidence": missing,
    }


def save_completion_contract(contract: dict[str, Any], path: str | Path) -> Path:
    """Persist a completion contract as JSON; returns the written path."""
    target = Path(path)
    if target.parent and str(target.parent) not in ("", "."):
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def print_completion_verdict(contract: dict[str, Any], config: Any = None) -> None:
    """Render the evidence-completeness verdict line (证据段末尾判定行)."""
    from rich.console import Console

    console = Console()
    if contract.get("evidence_complete"):
        console.print("[bold green]evidence_complete: ✓ true — 完成证据齐全，可验证[/bold green]")
    else:
        console.print(
            "[bold red]evidence_complete: ✗ false — 任务声明完成但缺少验证证据[/bold red]"
        )
        for item in contract.get("missing_evidence") or []:
            console.print(f"    [red]- {item}[/red]")
