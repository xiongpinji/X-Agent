#!/usr/bin/env python3
"""Build the final read-only gate before owner-approved staging.

This gate aggregates the commercial delivery manifest, staging review, owner
packet, preflight, refresh-chain receipt, command audit, decision brief, and
task board. It proves whether the owner can review and run the explicit
``git add -- '<path>'`` commands. It does not stage files, create commits,
push, run tests, call network services, or execute agents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_STAGING_REVIEW = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_OWNER_PREFLIGHT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.json"
DEFAULT_OWNER_POST_STAGING = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_REFRESH_RECEIPT = REPORT_DIR / "commercial-delivery-refresh-chain-receipt.json"
DEFAULT_OWNER_COMMAND_AUDIT = REPORT_DIR / "commercial-delivery-owner-command-audit.json"
DEFAULT_OWNER_DECISION_BRIEF = REPORT_DIR / "commercial-delivery-owner-decision-brief.json"
DEFAULT_OWNER_APPROVAL_HANDOFF = REPORT_DIR / "commercial-delivery-owner-approval-handoff.json"
DEFAULT_PRE_APPROVAL_DRIFT_GUARD = REPORT_DIR / "commercial-delivery-pre-approval-drift-guard.json"
DEFAULT_OWNER_APPROVAL_RESUME_PACKET = REPORT_DIR / "commercial-delivery-owner-approval-resume-packet.json"
DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST = (
    REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.json"
)
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-pre-stage-readiness-gate.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-pre-stage-readiness-gate.md"


@dataclass(frozen=True)
class OwnerPreStageReadinessCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerPreStageReadinessGate:
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
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[OwnerPreStageReadinessCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
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


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerPreStageReadinessCheck:
    return OwnerPreStageReadinessCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _len_list(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _failed_step_names(payload: dict[str, Any]) -> list[str]:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return []
    names: list[str] = []
    for step in steps:
        if isinstance(step, dict) and step.get("status") == "failed" and step.get("name") is not None:
            names.append(str(step.get("name")))
    return names


REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS = {
    "owner_pre_stage_readiness_gate",
    "owner_delivery_packet_before_owner_approval",
    "owner_delivery_packet",
    "owner_stage_approval_brief",
    "closure_snapshot",
    "owner_approval_handoff",
}


def _refresh_receipt_ready_or_bootstrap(refresh_receipt: dict[str, Any]) -> bool:
    refresh_summary = _summary(refresh_receipt)
    if (
        _status(refresh_receipt) == "commercial_delivery_refresh_chain_receipt_ready"
        and int(refresh_summary.get("failed_step_count") or 0) == 0
    ):
        return True
    failed_steps = _failed_step_names(refresh_receipt)
    return (
        _status(refresh_receipt) == "commercial_delivery_refresh_chain_receipt_blocked"
        and int(refresh_summary.get("failed_step_count") or 0) == 1
        and len(failed_steps) == 1
        and failed_steps[0] in REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS
    )


def _secondary_pending_paths(manifest: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in manifest.get("excluded_dirty_paths") or []:
        if isinstance(item, dict) and item.get("scope") == "secondary_pending_candidate":
            path = str(item.get("path") or "").replace("\\", "/").strip()
            if path:
                paths.append(path)
    return sorted(paths)


def build_owner_pre_stage_readiness_gate(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    staging_review_path: Path = DEFAULT_STAGING_REVIEW,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    owner_preflight_path: Path = DEFAULT_OWNER_PREFLIGHT,
    owner_post_staging_path: Path = DEFAULT_OWNER_POST_STAGING,
    refresh_receipt_path: Path = DEFAULT_REFRESH_RECEIPT,
    owner_command_audit_path: Path = DEFAULT_OWNER_COMMAND_AUDIT,
    owner_decision_brief_path: Path = DEFAULT_OWNER_DECISION_BRIEF,
    owner_approval_handoff_path: Path = DEFAULT_OWNER_APPROVAL_HANDOFF,
    pre_approval_drift_guard_path: Path = DEFAULT_PRE_APPROVAL_DRIFT_GUARD,
    owner_approval_resume_packet_path: Path = DEFAULT_OWNER_APPROVAL_RESUME_PACKET,
    owner_post_approval_operator_checklist_path: Path = DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerPreStageReadinessGate:
    report_paths = {
        "manifest": manifest_path,
        "staging_review": staging_review_path,
        "owner_packet": owner_packet_path,
        "owner_preflight": owner_preflight_path,
        "owner_post_staging": owner_post_staging_path,
        "refresh_receipt": refresh_receipt_path,
        "owner_command_audit": owner_command_audit_path,
        "owner_decision_brief": owner_decision_brief_path,
        "owner_approval_handoff": owner_approval_handoff_path,
        "pre_approval_drift_guard": pre_approval_drift_guard_path,
        "owner_approval_resume_packet": owner_approval_resume_packet_path,
        "owner_post_approval_operator_checklist": owner_post_approval_operator_checklist_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    manifest = reports["manifest"]
    staging_review = reports["staging_review"]
    owner_packet = reports["owner_packet"]
    owner_preflight = reports["owner_preflight"]
    owner_post_staging = reports["owner_post_staging"]
    refresh_receipt = reports["refresh_receipt"]
    owner_command_audit = reports["owner_command_audit"]
    owner_decision_brief = reports["owner_decision_brief"]
    owner_approval_handoff = reports["owner_approval_handoff"]
    pre_approval_drift_guard = reports["pre_approval_drift_guard"]
    owner_approval_resume_packet = reports["owner_approval_resume_packet"]
    operator_checklist = reports["owner_post_approval_operator_checklist"]
    task_board = reports["task_board"]
    refresh_summary = _summary(refresh_receipt)
    task_summary = _summary(task_board)
    decision_summary = _summary(owner_decision_brief)
    handoff_summary = _summary(owner_approval_handoff)
    guard_summary = _summary(pre_approval_drift_guard)
    stage_counts = {
        "manifest_stage_include_count": manifest.get("stage_include_count"),
        "staging_review_stage_include_count": staging_review.get("stage_include_count"),
        "staging_review_eligible_stage_count": staging_review.get("eligible_stage_count"),
        "owner_packet_stage_include_count": owner_packet.get("stage_include_count"),
        "owner_packet_eligible_stage_count": owner_packet.get("eligible_stage_count"),
        "owner_packet_stage_command_count": _len_list(owner_packet.get("stage_commands")),
        "owner_preflight_stage_command_count": owner_preflight.get("stage_command_count"),
        "owner_preflight_stage_path_count": owner_preflight.get("stage_path_count"),
        "owner_command_audit_command_count": owner_command_audit.get("command_count"),
        "owner_command_audit_expected_path_count": owner_command_audit.get("expected_path_count"),
    }
    non_none_counts = [value for value in stage_counts.values() if value is not None]
    stage_counts_agree = bool(non_none_counts) and len({int(value) for value in non_none_counts}) == 1
    pending_paths = _secondary_pending_paths(manifest)
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = (
        staging_review.get("owner_gated") is True
        and owner_packet.get("owner_gated") is True
        and owner_preflight.get("owner_gated") is True
        and owner_decision_brief.get("owner_gated") is True
        and owner_approval_handoff.get("owner_gated") is True
        and pre_approval_drift_guard.get("owner_gated") is True
        and owner_approval_resume_packet.get("owner_gated") is True
        and operator_checklist.get("owner_gated") is True
    )
    report_statuses = {name: _status(payload) for name, payload in reports.items()}
    resume_packet_accounted_for = _status(owner_approval_resume_packet) in {
        "owner_approval_resume_packet_waiting_for_owner",
        "owner_approval_resume_packet_ready",
    }
    operator_checklist_accounted_for = _status(operator_checklist) in {
        "owner_post_approval_operator_checklist_waiting_for_owner",
        "owner_post_approval_operator_checklist_ready",
    }
    owner_approval_boundary_waiting_or_ready = (
        resume_packet_accounted_for
        and operator_checklist_accounted_for
        and owner_approval_resume_packet.get("resume_ready") is not True
        and operator_checklist.get("operator_ready") is not True
    ) or (
        resume_packet_accounted_for
        and operator_checklist_accounted_for
        and owner_approval_resume_packet.get("resume_ready") is True
        and operator_checklist.get("operator_ready") is True
    )

    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more required owner pre-stage reports are missing or unreadable",
        ),
        _check(
            "manifest_ready",
            _status(manifest) == "original_kernel_delivery_manifest_ready",
            details={"status": _status(manifest)},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "staging_review_ready",
            _status(staging_review) == "staging_review_ready",
            details={"status": _status(staging_review)},
            error="commercial delivery staging review is not ready",
        ),
        _check(
            "owner_packet_ready",
            _status(owner_packet) == "owner_staging_packet_ready",
            details={"status": _status(owner_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "owner_preflight_ready",
            _status(owner_preflight) == "owner_staging_preflight_ready",
            details={
                "status": _status(owner_preflight),
                "cached_staged_path_count": owner_preflight.get("cached_staged_path_count"),
            },
            error="owner staging preflight is not ready",
        ),
        _check(
            "owner_post_staging_expected_pre_stage_state",
            _status(owner_post_staging) == "owner_post_staging_verification_blocked"
            and int(owner_post_staging.get("cached_staged_path_count") or 0) == 0,
            details={
                "status": _status(owner_post_staging),
                "cached_staged_path_count": owner_post_staging.get("cached_staged_path_count"),
            },
            error="post-staging verifier is not in the expected pre-stage blocked state",
        ),
        _check(
            "refresh_chain_receipt_ready",
            _refresh_receipt_ready_or_bootstrap(refresh_receipt),
            details={
                "status": _status(refresh_receipt),
                "failed_step_count": refresh_summary.get("failed_step_count"),
                "failed_steps": _failed_step_names(refresh_receipt),
                "expected_nonzero_step_count": refresh_summary.get("expected_nonzero_step_count"),
            },
            error="commercial delivery refresh-chain receipt is not ready or recoverable from a self-bootstrap state",
        ),
        _check(
            "owner_command_audit_ready",
            _status(owner_command_audit) == "owner_command_audit_ready",
            details={"status": _status(owner_command_audit)},
            error="owner command audit is not ready",
        ),
        _check(
            "owner_decision_brief_ready",
            _status(owner_decision_brief) == "ready_for_owner_staging_decision",
            details={"status": _status(owner_decision_brief)},
            error="owner decision brief is not ready",
        ),
        _check(
            "owner_approval_handoff_ready",
            _status(owner_approval_handoff) == "owner_approval_handoff_ready",
            details={
                "status": _status(owner_approval_handoff),
                "owner_action_required": owner_approval_handoff.get("owner_action_required"),
                "stage_allowed": owner_approval_handoff.get("stage_allowed"),
            },
            error="owner approval handoff is not ready",
        ),
        _check(
            "pre_approval_drift_guard_ready",
            _status(pre_approval_drift_guard) == "pre_approval_drift_guard_ready",
            details={
                "status": _status(pre_approval_drift_guard),
                "real_owner_approval_present": pre_approval_drift_guard.get("real_owner_approval_present"),
            },
            error="pre-approval drift guard is not ready",
        ),
        _check(
            "owner_approval_resume_packet_accounted_for",
            resume_packet_accounted_for,
            details={
                "status": _status(owner_approval_resume_packet),
                "waiting_for_owner": owner_approval_resume_packet.get("waiting_for_owner"),
                "resume_ready": owner_approval_resume_packet.get("resume_ready"),
            },
            error="owner approval resume packet is neither waiting for owner nor ready",
        ),
        _check(
            "operator_checklist_accounted_for",
            operator_checklist_accounted_for,
            details={
                "status": _status(operator_checklist),
                "waiting_for_owner": operator_checklist.get("waiting_for_owner"),
                "operator_ready": operator_checklist.get("operator_ready"),
            },
            error="post-approval operator checklist is neither waiting for owner nor ready",
        ),
        _check(
            "owner_approval_boundary_waiting_or_ready",
            owner_approval_boundary_waiting_or_ready,
            details={
                "owner_approval_resume_packet_status": _status(owner_approval_resume_packet),
                "owner_approval_resume_packet_waiting_for_owner": owner_approval_resume_packet.get("waiting_for_owner"),
                "owner_approval_resume_packet_resume_ready": owner_approval_resume_packet.get("resume_ready"),
                "operator_checklist_status": _status(operator_checklist),
                "operator_checklist_waiting_for_owner": operator_checklist.get("waiting_for_owner"),
                "operator_checklist_operator_ready": operator_checklist.get("operator_ready"),
                "pre_approval_drift_guard_real_owner_approval_present": pre_approval_drift_guard.get(
                    "real_owner_approval_present"
                ),
            },
            error="owner approval resume packet and operator checklist disagree about the owner boundary",
        ),
        _check(
            "task_board_ready",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={
                "status": _status(task_board),
                "refresh_chain_receipt_status": task_summary.get("refresh_chain_receipt_status"),
            },
            error="commercial delivery task board is not ready",
        ),
        _check(
            "stage_counts_agree",
            stage_counts_agree,
            details=stage_counts,
            error="manifest, staging, owner packet, preflight, or command audit stage counts disagree",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "staging_review_owner_gated": staging_review.get("owner_gated"),
                "owner_packet_owner_gated": owner_packet.get("owner_gated"),
                "owner_preflight_owner_gated": owner_preflight.get("owner_gated"),
                "owner_decision_brief_owner_gated": owner_decision_brief.get("owner_gated"),
                "owner_approval_handoff_owner_gated": owner_approval_handoff.get("owner_gated"),
                "pre_approval_drift_guard_owner_gated": pre_approval_drift_guard.get("owner_gated"),
                "owner_approval_resume_packet_owner_gated": owner_approval_resume_packet.get("owner_gated"),
                "operator_checklist_owner_gated": operator_checklist.get("owner_gated"),
            },
            error="one or more owner gate markers are missing",
        ),
        _check(
            "git_index_empty_before_owner_stage",
            int(owner_preflight.get("cached_staged_path_count") or 0) == 0,
            details={"cached_staged_path_count": owner_preflight.get("cached_staged_path_count")},
            error="git index is not empty before owner staging",
        ),
        _check(
            "secondary_pending_does_not_block_owner_stage",
            task_summary.get("secondary_pending_blocks_owner_staging") is False
            and decision_summary.get("secondary_pending_blocks_owner_staging") is False,
            details={
                "secondary_pending_paths": pending_paths,
                "task_board_secondary_pending_count": task_summary.get("secondary_pending_count"),
                "task_board_secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
                "task_board_secondary_handoff_completed_count": task_summary.get(
                    "secondary_handoff_completed_count"
                ),
                "task_board_secondary_handoff_latest_completed_candidate": task_summary.get(
                    "secondary_handoff_latest_completed_candidate"
                ),
                "decision_brief_secondary_pending_count": decision_summary.get("secondary_pending_count"),
                "decision_brief_secondary_handoff_completed_count": decision_summary.get(
                    "secondary_handoff_completed_count"
                ),
                "decision_brief_secondary_handoff_latest_completed_candidate": decision_summary.get(
                    "secondary_handoff_latest_completed_candidate"
                ),
                "task_board_secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
                "decision_brief_secondary_pending_blocks_owner_staging": decision_summary.get("secondary_pending_blocks_owner_staging"),
            },
            error="secondary pending candidates are blocking owner staging",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more commercial delivery reports claim full Codex parity",
        ),
        _check(
            "no_pre_stage_gate_mutation",
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
    status = "owner_pre_stage_readiness_ready" if ready else "owner_pre_stage_readiness_blocked"

    return OwnerPreStageReadinessGate(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_pre_stage_readiness_gate",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        decision=status,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses=report_statuses,
        summary={
            "stage_include_count": manifest.get("stage_include_count"),
            "stage_command_count": _len_list(owner_packet.get("stage_commands")),
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "decision_brief_secondary_handoff_completed_count": decision_summary.get(
                "secondary_handoff_completed_count"
            ),
            "decision_brief_secondary_handoff_latest_completed_candidate": decision_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "secondary_pending_paths": pending_paths,
            "refresh_chain_receipt_status": _status(refresh_receipt),
            "refresh_chain_failed_step_count": refresh_summary.get("failed_step_count"),
            "refresh_chain_expected_nonzero_step_count": refresh_summary.get("expected_nonzero_step_count"),
            "owner_command_audit_status": _status(owner_command_audit),
            "owner_decision_brief_status": _status(owner_decision_brief),
            "owner_approval_handoff_status": _status(owner_approval_handoff),
            "owner_approval_handoff_owner_action_required": owner_approval_handoff.get("owner_action_required"),
            "owner_approval_handoff_stage_allowed": owner_approval_handoff.get("stage_allowed"),
            "pre_approval_drift_guard_status": _status(pre_approval_drift_guard),
            "pre_approval_drift_guard_real_owner_approval_present": pre_approval_drift_guard.get(
                "real_owner_approval_present"
            ),
            "owner_approval_resume_packet_status": _status(owner_approval_resume_packet),
            "owner_approval_resume_packet_waiting_for_owner": owner_approval_resume_packet.get("waiting_for_owner"),
            "owner_approval_resume_packet_resume_ready": owner_approval_resume_packet.get("resume_ready"),
            "owner_post_approval_operator_checklist_status": _status(operator_checklist),
            "owner_post_approval_operator_checklist_waiting_for_owner": operator_checklist.get("waiting_for_owner"),
            "owner_post_approval_operator_checklist_operator_ready": operator_checklist.get("operator_ready"),
            "handoff_owner_post_approval_operator_checklist_status": handoff_summary.get(
                "owner_post_approval_operator_checklist_status"
            ),
            "guard_owner_post_approval_operator_checklist_status": guard_summary.get(
                "owner_post_approval_operator_checklist_status"
            ),
            "task_board_status": _status(task_board),
            "owner_preflight_cached_staged_path_count": owner_preflight.get("cached_staged_path_count"),
            "owner_post_staging_status": _status(owner_post_staging),
            "owner_post_staging_cached_staged_path_count": owner_post_staging.get("cached_staged_path_count"),
        },
        checks=checks,
        next_actions=[
            "If ready, the owner may review the owner staging packet and run only its exact git add commands.",
            "Immediately rerun owner staging preflight before owner-approved staging if the worktree changes.",
            "After owner-approved staging, run owner post-staging verifier before commit.",
            "Keep secondary pending candidates out of stage_include_paths until handoff records validation.",
        ],
        known_limits=[
            "This gate is read-only and does not stage, commit, push, run tests, call network services, or execute agents.",
            "This gate proves pre-stage readiness only; post-stage verification is a separate required step.",
            "A blocked post-staging verifier is expected before owner staging when the cached index is empty.",
            "This gate does not claim full Codex parity.",
        ],
    )


def render_markdown_gate(gate: OwnerPreStageReadinessGate) -> str:
    lines = [
        "# Commercial Delivery Owner Pre-Stage Readiness Gate",
        "",
        f"- Status: `{gate.status}`",
        f"- Generated at: `{gate.generated_at}`",
        f"- Owner gated: `{str(gate.owner_gated).lower()}`",
        f"- Stage include count: `{gate.summary.get('stage_include_count')}`",
        f"- Stage command count: `{gate.summary.get('stage_command_count')}`",
        f"- Secondary pending count: `{gate.summary.get('secondary_pending_count')}`",
        f"- Secondary handoff next queue: `{', '.join(gate.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{gate.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{gate.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Refresh receipt status: `{gate.summary.get('refresh_chain_receipt_status')}`",
        f"- Owner approval handoff: `{gate.summary.get('owner_approval_handoff_status')}`",
        f"- Owner approval resume packet: `{gate.summary.get('owner_approval_resume_packet_status')}`",
        f"- Owner approval resume waiting: `{gate.summary.get('owner_approval_resume_packet_waiting_for_owner')}`",
        f"- Owner post-approval operator checklist: `{gate.summary.get('owner_post_approval_operator_checklist_status')}`",
        f"- Owner post-approval operator ready: `{gate.summary.get('owner_post_approval_operator_checklist_operator_ready')}`",
        "",
        "## Checks",
        "",
    ]
    for check in gate.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in gate.next_actions)
    return "\n".join(lines)


def write_report(gate: OwnerPreStageReadinessGate, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_gate(gate: OwnerPreStageReadinessGate, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_gate(gate), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--staging-review", type=Path, default=DEFAULT_STAGING_REVIEW)
    parser.add_argument("--owner-packet", type=Path, default=DEFAULT_OWNER_PACKET)
    parser.add_argument("--owner-preflight", type=Path, default=DEFAULT_OWNER_PREFLIGHT)
    parser.add_argument("--owner-post-staging", type=Path, default=DEFAULT_OWNER_POST_STAGING)
    parser.add_argument("--refresh-receipt", type=Path, default=DEFAULT_REFRESH_RECEIPT)
    parser.add_argument("--owner-command-audit", type=Path, default=DEFAULT_OWNER_COMMAND_AUDIT)
    parser.add_argument("--owner-decision-brief", type=Path, default=DEFAULT_OWNER_DECISION_BRIEF)
    parser.add_argument("--owner-approval-handoff", type=Path, default=DEFAULT_OWNER_APPROVAL_HANDOFF)
    parser.add_argument("--pre-approval-drift-guard", type=Path, default=DEFAULT_PRE_APPROVAL_DRIFT_GUARD)
    parser.add_argument("--owner-approval-resume-packet", type=Path, default=DEFAULT_OWNER_APPROVAL_RESUME_PACKET)
    parser.add_argument(
        "--owner-post-approval-operator-checklist",
        type=Path,
        default=DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    )
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = build_owner_pre_stage_readiness_gate(
        manifest_path=args.manifest,
        staging_review_path=args.staging_review,
        owner_packet_path=args.owner_packet,
        owner_preflight_path=args.owner_preflight,
        owner_post_staging_path=args.owner_post_staging,
        refresh_receipt_path=args.refresh_receipt,
        owner_command_audit_path=args.owner_command_audit,
        owner_decision_brief_path=args.owner_decision_brief,
        owner_approval_handoff_path=args.owner_approval_handoff,
        pre_approval_drift_guard_path=args.pre_approval_drift_guard,
        owner_approval_resume_packet_path=args.owner_approval_resume_packet,
        owner_post_approval_operator_checklist_path=args.owner_post_approval_operator_checklist,
        task_board_path=args.task_board,
    )
    write_report(gate, args.output)
    write_markdown_gate(gate, args.markdown_output)
    print(f"Commercial delivery owner pre-stage readiness gate status: {gate.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage include count: {gate.summary.get('stage_include_count')}")
    print(f"Stage command count: {gate.summary.get('stage_command_count')}")
    for check in gate.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if gate.status == "owner_pre_stage_readiness_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
