#!/usr/bin/env python3
"""Validate the original-kernel repo context and context-pack contracts.

This is a module-level integration probe. It reads local workspace metadata and
git status, builds a compact context package with a fake memory adapter, and
writes a JSON evidence report only when explicitly invoked.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.context_pack import build_context_pack
from backend.app.core.contracts import RunContext
from backend.app.core.repo_context import build_repo_context
from backend.app.core.storage import atomic_write_json

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-context-integration.json"
DEFAULT_TASK = "Validate original-kernel repo_context and context_pack module contracts."


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class _MemoryItem:
    id: str
    layer: int
    importance: float
    tags: list[str]
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _ScoredHit:
    item: _MemoryItem
    score: float


class _ContractMemory:
    def __init__(self) -> None:
        self._hits = [
            _ScoredHit(
                item=_MemoryItem(
                    id="context-contract-1",
                    layer=3,
                    importance=0.91,
                    tags=["original-kernel", "context"],
                    content=(
                        "repo_context and context_pack are imported as module-level "
                        "contracts before any mainline agent execution is wired."
                    ),
                    metadata={
                        "kind": "integration_probe",
                        "trace_id": "trace-context-contract",
                    },
                ),
                score=0.98,
            )
        ]

    async def search_with_scores(
        self,
        context: RunContext,
        query: str,
        *,
        layers: list[int],
        top_k: int,
    ) -> list[_ScoredHit]:
        return self._hits[:top_k]

    def snapshot(self, tenant_id: str) -> dict[str, Any]:
        return {
            "tenant_id": tenant_id,
            "record_count": len(self._hits),
            "source": "contract_fake_memory",
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_context_check(repo_context: dict[str, Any], workspace_root: Path) -> IntegrationCheck:
    git_status = repo_context.get("git_status") if isinstance(repo_context.get("git_status"), dict) else {}
    test_config = repo_context.get("test_config") if isinstance(repo_context.get("test_config"), dict) else {}
    instruction_files = repo_context.get("instruction_files")
    recent_files = repo_context.get("recent_modified_files")

    passed = all(
        [
            repo_context.get("kind") == "xagent_repo_context",
            repo_context.get("version") == 1,
            repo_context.get("workspace_path") == str(workspace_root.resolve()),
            isinstance(git_status, dict),
            isinstance(test_config, dict),
            isinstance(instruction_files, list),
            isinstance(recent_files, list),
        ]
    )

    return IntegrationCheck(
        name="repo_context_contract",
        status="passed" if passed else "failed",
        details={
            "kind": repo_context.get("kind"),
            "version": repo_context.get("version"),
            "workspace_path": repo_context.get("workspace_path"),
            "git_available": git_status.get("available"),
            "git_is_repo": git_status.get("is_repo"),
            "git_dirty": git_status.get("dirty"),
            "git_entry_count": git_status.get("entry_count"),
            "instruction_file_count": len(instruction_files) if isinstance(instruction_files, list) else None,
            "recent_file_count": len(recent_files) if isinstance(recent_files, list) else None,
            "suggested_command_count": len(test_config.get("suggested_commands", []))
            if isinstance(test_config.get("suggested_commands"), list)
            else 0,
        },
        error=None if passed else "repo_context did not return the expected read-only summary contract",
    )


def _context_pack_check(context_pack: dict[str, Any], workspace_root: Path) -> IntegrationCheck:
    memory = context_pack.get("memory") if isinstance(context_pack.get("memory"), dict) else {}
    workspace = context_pack.get("workspace") if isinstance(context_pack.get("workspace"), dict) else {}
    repo = context_pack.get("repo") if isinstance(context_pack.get("repo"), dict) else {}
    compression = context_pack.get("compression") if isinstance(context_pack.get("compression"), dict) else {}
    restore_plan = context_pack.get("restore_plan")

    passed = all(
        [
            context_pack.get("kind") == "xagent_context_pack",
            context_pack.get("version") == 1,
            context_pack.get("tenant_id") == "tenant-original-kernel",
            memory.get("hit_count") == 1,
            workspace.get("exists") is True,
            workspace.get("root") == str(workspace_root.resolve()),
            repo.get("available") is True,
            compression.get("strategy") == "ranked_memory_plus_workspace_index_plus_repo_context",
            isinstance(context_pack.get("resume_prompt"), str),
            "Continue the task" in context_pack.get("resume_prompt", ""),
            isinstance(restore_plan, list),
            len(restore_plan) >= 4,
        ]
    )

    return IntegrationCheck(
        name="context_pack_contract",
        status="passed" if passed else "failed",
        details={
            "kind": context_pack.get("kind"),
            "version": context_pack.get("version"),
            "task_fingerprint_present": bool(context_pack.get("task_fingerprint")),
            "memory_hit_count": memory.get("hit_count"),
            "workspace_exists": workspace.get("exists"),
            "workspace_file_count": workspace.get("file_count"),
            "workspace_scanned_file_count": workspace.get("scanned_file_count"),
            "repo_available": repo.get("available"),
            "compression_strategy": compression.get("strategy"),
            "summary_chars": compression.get("summary_chars"),
            "restore_step_count": len(restore_plan) if isinstance(restore_plan, list) else None,
        },
        error=None if passed else "context_pack did not return the expected compact context contract",
    )


async def build_report(
    *,
    workspace_root: str | Path = ROOT,
    task: str = DEFAULT_TASK,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    repo_context = build_repo_context(workspace, max_recent_files=8, max_status_entries=20)
    context = RunContext(
        tenant_id="tenant-original-kernel",
        user_id="owner-verifier",
        agent_id="context-contract-probe",
        request_id="original-kernel-context-integration",
    )
    context_pack = await build_context_pack(
        memory=_ContractMemory(),
        context=context,
        task=task,
        workspace_root=workspace,
        top_k=3,
        max_files=24,
        max_summary_chars=4_000,
    )

    checks = [
        _repo_context_check(repo_context, workspace),
        _context_pack_check(context_pack, workspace),
    ]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_context_integration_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_context_integration",
        "modules": ["repo_context", "context_pack"],
        "workspace_root": str(workspace),
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "local_workspace_read_performed": True,
        "local_git_status_read_performed": True,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "command_execution_enabled": False,
        "write_runner_invoked": False,
        "checks": [asdict(check) for check in checks],
        "artifacts": {
            "repo_context": {
                "kind": repo_context.get("kind"),
                "version": repo_context.get("version"),
                "git_summary": repo_context.get("git_status", {}).get("summary")
                if isinstance(repo_context.get("git_status"), dict)
                else None,
                "instruction_files": [
                    item.get("path")
                    for item in repo_context.get("instruction_files", [])
                    if isinstance(item, dict)
                ],
            },
            "context_pack": {
                "kind": context_pack.get("kind"),
                "version": context_pack.get("version"),
                "task_fingerprint": context_pack.get("task_fingerprint"),
                "restore_plan": [
                    item.get("id")
                    for item in context_pack.get("restore_plan", [])
                    if isinstance(item, dict)
                ],
            },
        },
        "known_limits": [
            "This report proves module-level repo_context and context_pack contracts only.",
            "Local git status is read for repository context; no arbitrary command execution is enabled.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No full Codex parity claim is made by this report.",
        ],
        "next_actions": [
            "After review, stage only the context integration files explicitly.",
            "Use agent_run_closure as the next isolated module-level integration slice.",
        ],
    }


async def write_report(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    workspace_root: str | Path = ROOT,
    task: str = DEFAULT_TASK,
) -> dict[str, Any]:
    report = await build_report(workspace_root=workspace_root, task=task)
    report["report_file_written"] = True
    report["report_path"] = str(output_path)
    atomic_write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=ROOT,
        help="Workspace root to summarize with repo_context and context_pack.",
    )
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK,
        help="Task text to include in the generated context pack.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON integration evidence report.",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    report = await write_report(args.output, workspace_root=args.workspace_root, task=args.task)

    print(f"Original kernel context integration status: {report['status']}")
    print(f"Report written to {args.output}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_context_integration_ready" else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
