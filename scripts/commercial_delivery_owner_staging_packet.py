#!/usr/bin/env python3
"""Build an owner-gated staging command packet for commercial delivery.

The packet converts a ready staging review into explicit owner-review
commands. It does not run git add, create commits, push branches, execute
tests, call agents, or call external services.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_STAGING_REVIEW = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-packet.md"

SECONDARY_SUMMARY_FIELDS = (
    "secondary_pending_count",
    "secondary_handoff_next_count",
    "secondary_handoff_next_queue",
    "secondary_handoff_completed_count",
    "secondary_handoff_latest_completed_candidate",
)


@dataclass(frozen=True)
class OwnerStagingPacketCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStagingPacket:
    status: str
    generated_at: str
    evidence_type: str
    owner_gated: bool
    mutation_performed: bool
    git_stage_performed: bool
    git_commit_performed: bool
    git_push_performed: bool
    network_mutation_performed: bool
    agent_execution_enabled: bool
    full_codex_parity_claimed: bool
    staging_review_status: str | None
    manifest_status: str | None
    stage_include_count: int
    eligible_stage_count: int
    blocked_stage_count: int
    unchanged_stage_count: int
    stage_paths: list[str]
    blocked_paths: list[str]
    excluded_dirty_paths: list[dict[str, Any]]
    stage_path_digest: str
    stage_commands: list[str]
    stage_command_digest: str
    pre_stage_verification_commands: list[str]
    post_stage_verification_commands: list[str]
    verification_commands: list[str]
    commit_command_preview: str
    summary: dict[str, Any]
    checks: list[OwnerStagingPacketCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        for name, value in asdict(self).items():
            if isinstance(value, list):
                payload[f"{name}_count"] = len(value)
        return payload


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"report not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerStagingPacketCheck:
    return OwnerStagingPacketCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _path_rows(staging_review: dict[str, Any]) -> list[dict[str, Any]]:
    rows = staging_review.get("paths")
    if not isinstance(rows, list):
        return []
    return [dict(item) for item in rows if isinstance(item, dict)]


def _paths_by_status(staging_review: dict[str, Any], status: str) -> list[str]:
    paths: list[str] = []
    for item in _path_rows(staging_review):
        if item.get("status") == status and item.get("path"):
            paths.append(str(item["path"]).replace("\\", "/"))
    return paths


def _excluded_dirty_paths(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("excluded_dirty_paths")
    if not isinstance(rows, list):
        return []
    excluded: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict):
            excluded.append(
                {
                    "path": str(item.get("path") or ""),
                    "scope": str(item.get("scope") or ""),
                    "reason": item.get("reason"),
                }
            )
    return excluded


def _task_board_summary(
    task_board: dict[str, Any],
    *,
    task_board_path: Path,
    task_board_error: str | None,
) -> dict[str, Any]:
    source = task_board.get("summary")
    if not isinstance(source, dict):
        source = task_board

    summary: dict[str, Any] = {
        "task_board_path": _display_path(task_board_path),
        "task_board_readable": task_board_error is None,
    }
    if task_board_error is not None:
        summary["task_board_error"] = task_board_error

    for field_name in SECONDARY_SUMMARY_FIELDS:
        value = source.get(field_name)
        if field_name == "secondary_handoff_next_queue":
            summary[field_name] = [str(item) for item in value] if isinstance(value, list) else []
        else:
            summary[field_name] = value
    return summary


def _quote_path(path: str) -> str:
    return "'" + path.replace("'", "''") + "'"


def _stage_commands(paths: list[str]) -> list[str]:
    return [f"git add -- {_quote_path(path)}" for path in paths]


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pre_stage_verification_commands() -> list[str]:
    return [
        "python scripts\\commercial_delivery_refresh_chain_receipt.py",
        "python scripts\\commercial_delivery_task_board.py",
        "python scripts\\commercial_delivery_owner_pre_stage_readiness_gate.py",
        "python scripts\\commercial_delivery_owner_stage_approval_request.py",
        "python scripts\\commercial_delivery_owner_stage_approval_brief.py",
        "python scripts\\commercial_delivery_owner_stage_approval_gate.py",
        "python scripts\\commercial_delivery_owner_stage_execution_plan.py",
        "python scripts\\commercial_delivery_owner_staging_rollback_plan.py",
        "python scripts\\commercial_delivery_owner_staging_preflight.py",
        "git diff --cached --name-only",
    ]


def _post_stage_verification_commands() -> list[str]:
    return [
        "git diff --cached --name-only",
        "python scripts\\commercial_delivery_owner_command_audit.py",
        "python scripts\\commercial_delivery_owner_post_staging_verifier.py",
        "python scripts\\commercial_delivery_owner_post_stage_commit_gate.py",
        "python scripts\\commercial_delivery_owner_commit_packet.py",
        "python scripts\\commercial_delivery_owner_staging_rollback_plan.py",
        "python scripts\\commercial_delivery_owner_delivery_packet.py",
        "python scripts\\commercial_delivery_owner_stage_approval_brief.py",
        "python scripts\\commercial_delivery_owner_staging_packet.py",
        "python scripts\\commercial_delivery_task_board.py",
        'python -m pytest tests/test_commercial_delivery_owner_delivery_packet.py tests/test_commercial_delivery_owner_commit_packet.py tests/test_commercial_delivery_owner_post_stage_commit_gate.py tests/test_commercial_delivery_task_board.py tests/test_commercial_delivery_owner_staging_packet.py tests/test_commercial_delivery_owner_post_staging_verifier.py tests/test_commercial_delivery_owner_command_audit.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short',
    ]


def build_owner_staging_packet(
    *,
    staging_review_path: Path = DEFAULT_STAGING_REVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerStagingPacket:
    staging_review, staging_error = _read_json(staging_review_path)
    manifest, manifest_error = _read_json(manifest_path)
    task_board, task_board_error = _read_json(task_board_path)
    summary = _task_board_summary(
        task_board,
        task_board_path=task_board_path,
        task_board_error=task_board_error,
    )
    stage_paths = _paths_by_status(staging_review, "eligible")
    blocked_paths = _paths_by_status(staging_review, "blocked")
    unchanged_paths = _paths_by_status(staging_review, "unchanged")
    expected_eligible = staging_review.get("eligible_stage_count")
    manifest_stage_count = manifest.get("stage_include_count")
    staging_stage_count = staging_review.get("stage_include_count")
    full_codex_parity_claimed = (
        staging_review.get("full_codex_parity_claimed") is True
        or manifest.get("full_codex_parity_claimed") is True
    )
    owner_gated = staging_review.get("owner_gated") is True

    checks = [
        _check(
            "staging_review_readable",
            staging_error is None,
            details={"staging_review_path": _display_path(staging_review_path)},
            error=staging_error,
        ),
        _check(
            "manifest_readable",
            manifest_error is None,
            details={"manifest_path": _display_path(manifest_path)},
            error=manifest_error,
        ),
        _check(
            "staging_review_ready",
            staging_review.get("status") == "staging_review_ready",
            details={"staging_review_status": staging_review.get("status")},
            error="commercial delivery staging review is not ready",
        ),
        _check(
            "manifest_ready",
            manifest.get("status") == "original_kernel_delivery_manifest_ready",
            details={"manifest_status": manifest.get("status")},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={"owner_gated": owner_gated},
            error="staging review is not owner gated",
        ),
        _check(
            "eligible_paths_present",
            bool(stage_paths),
            details={"eligible_stage_count": len(stage_paths)},
            error="no eligible stage paths are available",
        ),
        _check(
            "no_blocked_stage_paths",
            not blocked_paths and int(staging_review.get("blocked_stage_count") or 0) == 0,
            details={
                "blocked_stage_count": staging_review.get("blocked_stage_count"),
                "blocked_paths": blocked_paths,
            },
            error="staging review contains blocked paths",
        ),
        _check(
            "stage_path_count_matches_review",
            len(stage_paths) == int(expected_eligible or -1),
            details={"eligible_stage_count": expected_eligible, "stage_path_count": len(stage_paths)},
            error="eligible stage path count does not match staging review",
        ),
        _check(
            "manifest_stage_count_matches_review",
            manifest_stage_count == staging_stage_count,
            details={
                "manifest_stage_include_count": manifest_stage_count,
                "staging_review_stage_include_count": staging_stage_count,
            },
            error="manifest and staging review stage counts do not match",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="delivery reports claim full Codex parity",
        ),
        _check(
            "no_packet_mutation",
            True,
            details={
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
                "network_mutation_performed": False,
                "agent_execution_enabled": False,
            },
        ),
    ]
    status = (
        "owner_staging_packet_ready"
        if all(check.status == "passed" for check in checks)
        else "owner_staging_packet_blocked"
    )

    pre_stage_verification_commands = _pre_stage_verification_commands()
    post_stage_verification_commands = _post_stage_verification_commands()
    stage_commands = _stage_commands(stage_paths)

    return OwnerStagingPacket(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_staging_packet",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        staging_review_status=str(staging_review.get("status")) if staging_review.get("status") is not None else None,
        manifest_status=str(manifest.get("status")) if manifest.get("status") is not None else None,
        stage_include_count=int(staging_stage_count or 0),
        eligible_stage_count=len(stage_paths),
        blocked_stage_count=len(blocked_paths),
        unchanged_stage_count=len(unchanged_paths),
        stage_paths=stage_paths,
        blocked_paths=blocked_paths,
        excluded_dirty_paths=_excluded_dirty_paths(manifest),
        stage_path_digest=_digest_values(stage_paths),
        stage_commands=stage_commands,
        stage_command_digest=_digest_values(stage_commands),
        pre_stage_verification_commands=pre_stage_verification_commands,
        post_stage_verification_commands=post_stage_verification_commands,
        verification_commands=post_stage_verification_commands,
        commit_command_preview='git commit -m "chore: prepare X-Agent commercial delivery package"',
        summary=summary,
        checks=checks,
        next_actions=[
            "Owner reviews this packet before any git staging.",
            "Run pre_stage_verification_commands immediately before owner-approved staging.",
            "Run only the listed git add commands after explicit owner approval.",
            "Run post_stage_verification_commands after staging and before commit.",
            "Regenerate staging review, owner packet, and task board after any secondary handoff update.",
        ],
        known_limits=[
            "This packet is a dry-run owner review artifact.",
            "It does not run git add, commit, push, tests, agents, browser tasks, network calls, or secondary candidate code.",
            "It does not claim full Codex parity.",
            "Excluded dirty paths are intentionally not part of the owner staging commands.",
        ],
    )


def render_markdown_packet(packet: OwnerStagingPacket) -> str:
    lines = [
        "# Commercial Delivery Owner Staging Packet",
        "",
        f"- Status: `{packet.status}`",
        f"- Generated at: `{packet.generated_at}`",
        f"- Owner gated: `{str(packet.owner_gated).lower()}`",
        f"- Stage include count: `{packet.stage_include_count}`",
        f"- Eligible stage count: `{packet.eligible_stage_count}`",
        f"- Blocked stage count: `{packet.blocked_stage_count}`",
        f"- Stage path digest: `{packet.stage_path_digest}`",
        f"- Stage command digest: `{packet.stage_command_digest}`",
        f"- Secondary handoff next queue: `{', '.join(packet.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{packet.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{packet.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Full Codex parity claimed: `{str(packet.full_codex_parity_claimed).lower()}`",
        "",
        "## Checks",
        "",
    ]
    for check in packet.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Stage Commands", ""])
    lines.extend(f"- `{command}`" for command in packet.stage_commands)
    lines.extend(["", "## Pre-Stage Verification Commands", ""])
    lines.extend(f"- `{command}`" for command in packet.pre_stage_verification_commands)
    lines.extend(["", "## Post-Stage Verification Commands", ""])
    lines.extend(f"- `{command}`" for command in packet.post_stage_verification_commands)
    lines.extend(["", "## Verification Commands", ""])
    lines.extend(f"- `{command}`" for command in packet.verification_commands)
    lines.extend(["", "## Commit Preview", "", f"- `{packet.commit_command_preview}`", ""])
    return "\n".join(lines)


def write_report(packet: OwnerStagingPacket, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(packet.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown_packet(packet: OwnerStagingPacket, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_packet(packet), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-review", type=Path, default=DEFAULT_STAGING_REVIEW)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_owner_staging_packet(
        staging_review_path=args.staging_review,
        manifest_path=args.manifest,
        task_board_path=args.task_board,
    )
    write_report(packet, args.output)
    write_markdown_packet(packet, args.markdown_output)
    print(f"Commercial delivery owner staging packet status: {packet.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage commands: {len(packet.stage_commands)}")
    print(f"Verification commands: {len(packet.verification_commands)}")
    for check in packet.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if packet.status == "owner_staging_packet_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
