"""Completion evidence ("完成证据") for ``xagent agent run``.

Extracts a codex-exec-style evidence summary from an agent run result:

* changed files (with size-delta diff summary when available)
* verification results (backend observations + CLI-side syntax check)
* trace_id / status / iterations

Used by both the rich interactive output and the headless JSON output.
"""

from __future__ import annotations

import py_compile
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
