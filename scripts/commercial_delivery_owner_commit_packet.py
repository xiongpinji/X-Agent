#!/usr/bin/env python3
"""Build the owner-facing commit packet after owner-approved staging.

The packet is intentionally read-only. It packages the post-stage evidence an
owner needs before running the commit preview command, but it never stages
files, creates commits, pushes branches, calls external services, or executes
agents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_OWNER_POST_STAGING = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_OWNER_COMMAND_AUDIT = REPORT_DIR / "commercial-delivery-owner-command-audit.json"
DEFAULT_OWNER_POST_STAGE_COMMIT_GATE = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-commit-packet.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-commit-packet.md"


@dataclass(frozen=True)
class OwnerCommitPacketCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerCommitPacketSection:
    name: str
    title: str
    commands: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnerCommitPacket:
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
    decision: str
    commit_allowed: bool
    commit_command_preview: str | None
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    expected_stage_path_set_digest: str | None
    cached_staged_path_set_digest: str | None
    stage_path_digest: str | None
    stage_command_digest: str | None
    command_path_set_digest: str | None
    gate_expected_stage_path_set_digest: str | None
    gate_cached_staged_path_set_digest: str | None
    sections: list[OwnerCommitPacketSection]
    checks: list[OwnerCommitPacketCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sections"] = [asdict(section) for section in self.sections]
        payload["checks"] = [asdict(check) for check in self.checks]
        for name, value in asdict(self).items():
            if isinstance(value, list):
                payload[f"{name}_count"] = len(value)
        return payload


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


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _path_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item).replace("\\", "/").strip().strip('"') for item in value if str(item).strip()})


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str | None:
    return _digest_values(sorted(set(paths))) if paths else None


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return str(value) if isinstance(value, str) and value else None


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerCommitPacketCheck:
    return OwnerCommitPacketCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _failed_check_names(checks: list[OwnerCommitPacketCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


def build_owner_commit_packet(
    *,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    owner_post_staging_path: Path = DEFAULT_OWNER_POST_STAGING,
    owner_command_audit_path: Path = DEFAULT_OWNER_COMMAND_AUDIT,
    owner_post_stage_commit_gate_path: Path = DEFAULT_OWNER_POST_STAGE_COMMIT_GATE,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerCommitPacket:
    report_paths = {
        "owner_packet": owner_packet_path,
        "owner_post_staging": owner_post_staging_path,
        "owner_command_audit": owner_command_audit_path,
        "owner_post_stage_commit_gate": owner_post_stage_commit_gate_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    owner_packet = reports["owner_packet"]
    owner_post_staging = reports["owner_post_staging"]
    owner_command_audit = reports["owner_command_audit"]
    commit_gate = reports["owner_post_stage_commit_gate"]
    task_board = reports["task_board"]
    gate_summary = _summary(commit_gate)
    task_summary = _summary(task_board)

    stage_paths = _path_list(owner_packet.get("stage_paths"))
    cached_paths = _path_list(owner_post_staging.get("cached_staged_paths"))
    command_paths = _path_list(owner_command_audit.get("command_paths"))
    gate_expected_paths = _path_list(commit_gate.get("expected_stage_paths"))
    gate_cached_paths = _path_list(commit_gate.get("cached_staged_paths"))
    post_stage_commands = _list(owner_packet.get("post_stage_verification_commands"))
    commit_command_preview = owner_packet.get("commit_command_preview")
    gate_commit_preview = commit_gate.get("commit_command_preview")
    commit_allowed = commit_gate.get("commit_allowed") is True
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = (
        owner_packet.get("owner_gated") is True
        and owner_post_staging.get("owner_gated") is True
        and owner_command_audit.get("owner_gated") is True
        and commit_gate.get("owner_gated") is True
    )
    staged_paths_match = bool(stage_paths) and stage_paths == cached_paths == gate_cached_paths
    command_paths_match = bool(stage_paths) and command_paths == stage_paths
    gate_paths_match = bool(stage_paths) and gate_expected_paths == stage_paths
    commit_preview_consistent = (
        isinstance(commit_command_preview, str)
        and commit_command_preview.strip().startswith("git commit ")
        and gate_commit_preview == commit_command_preview
    )
    expected_stage_path_set_digest = _path_set_digest(stage_paths)
    cached_staged_path_set_digest = _path_set_digest(cached_paths)
    command_path_set_digest = _path_set_digest(command_paths)
    gate_expected_stage_path_set_digest = _digest_field(commit_gate, "expected_stage_path_set_digest")
    gate_cached_staged_path_set_digest = _digest_field(commit_gate, "cached_staged_path_set_digest")
    gate_command_path_set_digest = _digest_field(commit_gate, "command_path_set_digest")
    owner_packet_stage_path_digest = _digest_field(owner_packet, "stage_path_digest")
    owner_packet_stage_command_digest = _digest_field(owner_packet, "stage_command_digest")
    command_audit_path_digest = _digest_field(owner_command_audit, "command_path_digest")
    command_audit_expected_path_digest = _digest_field(owner_command_audit, "expected_path_digest")
    command_audit_command_digest = _digest_field(owner_command_audit, "command_digest")
    command_audit_owner_packet_path_digest = _digest_field(owner_command_audit, "owner_packet_stage_path_digest")
    command_audit_owner_packet_command_digest = _digest_field(
        owner_command_audit, "owner_packet_stage_command_digest"
    )
    gate_stage_path_digest = _digest_field(commit_gate, "stage_path_digest")
    gate_stage_command_digest = _digest_field(commit_gate, "stage_command_digest")
    path_set_digests_match = (
        expected_stage_path_set_digest is not None
        and cached_staged_path_set_digest == expected_stage_path_set_digest
        and command_path_set_digest == expected_stage_path_set_digest
        and gate_expected_stage_path_set_digest == expected_stage_path_set_digest
        and gate_cached_staged_path_set_digest == expected_stage_path_set_digest
        and gate_command_path_set_digest == expected_stage_path_set_digest
    )
    ordered_stage_digests_match = (
        owner_packet_stage_path_digest is not None
        and owner_packet_stage_command_digest is not None
        and command_audit_path_digest == owner_packet_stage_path_digest
        and command_audit_expected_path_digest == owner_packet_stage_path_digest
        and command_audit_owner_packet_path_digest == owner_packet_stage_path_digest
        and command_audit_command_digest == owner_packet_stage_command_digest
        and command_audit_owner_packet_command_digest == owner_packet_stage_command_digest
        and gate_stage_path_digest == owner_packet_stage_path_digest
        and gate_stage_command_digest == owner_packet_stage_command_digest
    )

    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more owner commit packet inputs are missing or unreadable",
        ),
        _check(
            "owner_packet_ready",
            _status(owner_packet) == "owner_staging_packet_ready",
            details={"status": _status(owner_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "owner_post_staging_verification_ready",
            _status(owner_post_staging) == "owner_post_staging_verification_ready",
            details={
                "status": _status(owner_post_staging),
                "cached_staged_path_count": owner_post_staging.get("cached_staged_path_count"),
            },
            error="owner post-staging verifier is not ready",
        ),
        _check(
            "owner_command_audit_ready",
            _status(owner_command_audit) == "owner_command_audit_ready",
            details={"status": _status(owner_command_audit)},
            error="owner command audit is not ready",
        ),
        _check(
            "owner_post_stage_commit_gate_ready",
            _status(commit_gate) == "owner_post_stage_commit_gate_ready",
            details={"status": _status(commit_gate), "commit_allowed": commit_gate.get("commit_allowed")},
            error="owner post-stage commit gate is not ready",
        ),
        _check(
            "task_board_ready",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={"status": _status(task_board)},
            error="commercial delivery task board is not ready",
        ),
        _check(
            "commit_allowed_by_gate",
            commit_allowed,
            details={"commit_allowed": commit_allowed},
            error="post-stage commit gate does not allow commit",
        ),
        _check(
            "staged_paths_match_owner_packet",
            staged_paths_match,
            details={
                "stage_paths": stage_paths,
                "cached_staged_paths": cached_paths,
                "gate_cached_staged_paths": gate_cached_paths,
            },
            error="cached staged paths do not match the owner staging packet",
        ),
        _check(
            "command_paths_match_owner_packet",
            command_paths_match,
            details={"command_paths": command_paths, "stage_paths": stage_paths},
            error="owner command audit paths do not match the owner staging packet",
        ),
        _check(
            "commit_gate_expected_paths_match_owner_packet",
            gate_paths_match,
            details={"gate_expected_stage_paths": gate_expected_paths, "stage_paths": stage_paths},
            error="post-stage commit gate expected paths do not match the owner staging packet",
        ),
        _check(
            "path_set_digests_match_owner_packet",
            path_set_digests_match,
            details={
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "cached_staged_path_set_digest": cached_staged_path_set_digest,
                "command_path_set_digest": command_path_set_digest,
                "gate_expected_stage_path_set_digest": gate_expected_stage_path_set_digest,
                "gate_cached_staged_path_set_digest": gate_cached_staged_path_set_digest,
                "gate_command_path_set_digest": gate_command_path_set_digest,
            },
            error="owner commit packet path set digests do not match the post-stage commit gate",
        ),
        _check(
            "ordered_stage_digests_match_owner_packet",
            ordered_stage_digests_match,
            details={
                "owner_packet_stage_path_digest": owner_packet_stage_path_digest,
                "owner_packet_stage_command_digest": owner_packet_stage_command_digest,
                "command_audit_path_digest": command_audit_path_digest,
                "command_audit_expected_path_digest": command_audit_expected_path_digest,
                "command_audit_command_digest": command_audit_command_digest,
                "command_audit_owner_packet_path_digest": command_audit_owner_packet_path_digest,
                "command_audit_owner_packet_command_digest": command_audit_owner_packet_command_digest,
                "gate_stage_path_digest": gate_stage_path_digest,
                "gate_stage_command_digest": gate_stage_command_digest,
            },
            error="ordered stage path or command digests do not match the owner staging packet",
        ),
        _check(
            "commit_preview_consistent",
            commit_preview_consistent,
            details={
                "owner_packet_commit_command_preview": commit_command_preview,
                "commit_gate_commit_command_preview": gate_commit_preview,
            },
            error="commit preview is missing or inconsistent",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "owner_packet_owner_gated": owner_packet.get("owner_gated"),
                "owner_post_staging_owner_gated": owner_post_staging.get("owner_gated"),
                "owner_command_audit_owner_gated": owner_command_audit.get("owner_gated"),
                "owner_post_stage_commit_gate_owner_gated": commit_gate.get("owner_gated"),
            },
            error="one or more owner gate markers are missing",
        ),
        _check(
            "secondary_pending_does_not_block_owner_commit",
            task_summary.get("secondary_pending_blocks_owner_staging") is False,
            details={
                "secondary_pending_count": task_summary.get("secondary_pending_count"),
                "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
                "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
                "secondary_handoff_latest_completed_candidate": task_summary.get(
                    "secondary_handoff_latest_completed_candidate"
                ),
                "secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
            },
            error="secondary pending candidates are blocking owner commit readiness",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more owner commit packet inputs claim full Codex parity",
        ),
        _check(
            "no_commit_packet_mutation",
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
    ready = all(check.status == "passed" for check in checks)
    status = "owner_commit_packet_ready" if ready else "owner_commit_packet_blocked"
    decision = "ready_for_owner_commit" if ready else "blocked_before_owner_commit"
    blocking_reasons = _failed_check_names(checks)

    sections = [
        OwnerCommitPacketSection(
            name="post_stage_verification",
            title="Post-stage verification",
            commands=post_stage_commands,
            notes=[
                "Run these after owner-approved staging and before commit.",
                "Stop if any report is blocked, missing, or reports staged-path drift.",
            ],
        ),
        OwnerCommitPacketSection(
            name="commit_preview",
            title="Commit preview",
            commands=[str(commit_command_preview or "")],
            notes=[
                "Run this only when this packet status is owner_commit_packet_ready.",
                "Review the staged diff before committing.",
            ],
        ),
        OwnerCommitPacketSection(
            name="stop_conditions",
            title="Stop conditions",
            commands=[],
            notes=[
                "Do not commit if cached staged paths differ from the owner packet.",
                "Do not commit if the post-stage commit gate is blocked.",
                "Do not commit if any report claims full Codex parity.",
            ],
        ),
    ]

    return OwnerCommitPacket(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_commit_packet",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        decision=decision,
        commit_allowed=ready,
        commit_command_preview=str(commit_command_preview) if commit_command_preview is not None else None,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "blocking_reasons": blocking_reasons,
            "owner_action_required": not ready,
            "stage_path_count": len(stage_paths),
            "cached_staged_path_count": len(cached_paths),
            "gate_cached_staged_path_count": len(gate_cached_paths),
            "owner_post_staging_status": _status(owner_post_staging),
            "owner_command_audit_status": _status(owner_command_audit),
            "owner_post_stage_commit_gate_status": _status(commit_gate),
            "task_board_status": _status(task_board),
            "commit_gate_decision": commit_gate.get("decision"),
            "commit_gate_summary_cached_staged_path_count": gate_summary.get("cached_staged_path_count"),
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "commit_command_preview": commit_command_preview,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "cached_staged_path_set_digest": cached_staged_path_set_digest,
            "stage_path_digest": owner_packet_stage_path_digest,
            "stage_command_digest": owner_packet_stage_command_digest,
            "command_path_set_digest": command_path_set_digest,
            "command_audit_path_digest": command_audit_path_digest,
            "command_audit_expected_path_digest": command_audit_expected_path_digest,
            "command_audit_command_digest": command_audit_command_digest,
            "gate_stage_path_digest": gate_stage_path_digest,
            "gate_stage_command_digest": gate_stage_command_digest,
            "gate_expected_stage_path_set_digest": gate_expected_stage_path_set_digest,
            "gate_cached_staged_path_set_digest": gate_cached_staged_path_set_digest,
        },
        expected_stage_path_set_digest=expected_stage_path_set_digest,
        cached_staged_path_set_digest=cached_staged_path_set_digest,
        stage_path_digest=owner_packet_stage_path_digest,
        stage_command_digest=owner_packet_stage_command_digest,
        command_path_set_digest=command_path_set_digest,
        gate_expected_stage_path_set_digest=gate_expected_stage_path_set_digest,
        gate_cached_staged_path_set_digest=gate_cached_staged_path_set_digest,
        sections=sections,
        checks=checks,
        next_actions=[
            "If ready, review the staged diff with the owner before running the commit preview.",
            "If blocked, resolve only the reported post-stage evidence issue and regenerate this packet.",
            "Keep secondary next candidates detached until their handoff records completed validation.",
        ],
        known_limits=[
            "This packet is read-only except writing local evidence files.",
            "It does not stage, reset, commit, push, run tests, call network services, or execute agents.",
            "It validates owner commit readiness, not the semantic content of the staged diff.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_packet(packet: OwnerCommitPacket) -> str:
    lines = [
        "# Commercial Delivery Owner Commit Packet",
        "",
        f"- Status: `{packet.status}`",
        f"- Generated at: `{packet.generated_at}`",
        f"- Decision: `{packet.decision}`",
        f"- Commit allowed: `{str(packet.commit_allowed).lower()}`",
        f"- Owner gated: `{str(packet.owner_gated).lower()}`",
        f"- Cached staged path count: `{packet.summary.get('cached_staged_path_count')}`",
        f"- Owner action required: `{str(packet.summary.get('owner_action_required')).lower()}`",
        f"- Blocking reasons: `{', '.join(packet.summary.get('blocking_reasons') or [])}`",
        f"- Secondary handoff next queue: `{', '.join(packet.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{packet.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{packet.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Expected stage path set digest: `{packet.expected_stage_path_set_digest or '<missing>'}`",
        f"- Cached staged path set digest: `{packet.cached_staged_path_set_digest or '<missing>'}`",
        f"- Stage path digest: `{packet.stage_path_digest or '<missing>'}`",
        f"- Stage command digest: `{packet.stage_command_digest or '<missing>'}`",
        f"- Commit command preview: `{packet.commit_command_preview}`",
        "",
        "## Checks",
        "",
    ]
    for check in packet.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    for section in packet.sections:
        lines.extend(["", f"## {section.title}", ""])
        if section.commands:
            lines.extend(f"- `{command}`" for command in section.commands if command)
        if section.notes:
            lines.append("")
            lines.extend(f"- {note}" for note in section.notes)
    lines.append("")
    return "\n".join(lines)


def write_report(packet: OwnerCommitPacket, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_packet(packet: OwnerCommitPacket, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_packet(packet), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-packet", type=Path, default=DEFAULT_OWNER_PACKET)
    parser.add_argument("--owner-post-staging", type=Path, default=DEFAULT_OWNER_POST_STAGING)
    parser.add_argument("--owner-command-audit", type=Path, default=DEFAULT_OWNER_COMMAND_AUDIT)
    parser.add_argument("--owner-post-stage-commit-gate", type=Path, default=DEFAULT_OWNER_POST_STAGE_COMMIT_GATE)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_owner_commit_packet(
        owner_packet_path=args.owner_packet,
        owner_post_staging_path=args.owner_post_staging,
        owner_command_audit_path=args.owner_command_audit,
        owner_post_stage_commit_gate_path=args.owner_post_stage_commit_gate,
        task_board_path=args.task_board,
    )
    write_report(packet, args.output)
    write_markdown_packet(packet, args.markdown_output)
    print(f"Commercial delivery owner commit packet status: {packet.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Decision: {packet.decision}")
    print(f"Commit allowed: {packet.commit_allowed}")
    for check in packet.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if packet.status == "owner_commit_packet_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
