#!/usr/bin/env python3
"""Build a read-only owner approval resume packet.

The packet captures the exact sequence to resume commercial delivery after a
human owner creates the real stage approval payload. It never writes approval
evidence, stages files, commits, pushes, calls network services, runs tests, or
executes agents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_APPROVAL_HANDOFF = REPORT_DIR / "commercial-delivery-owner-approval-handoff.json"
DEFAULT_PRE_APPROVAL_DRIFT_GUARD = REPORT_DIR / "commercial-delivery-pre-approval-drift-guard.json"
DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_OWNER_STAGING_RUNBOOK = REPORT_DIR / "commercial-delivery-owner-staging-runbook.json"
DEFAULT_OWNER_STAGING_ROLLBACK_PLAN = REPORT_DIR / "commercial-delivery-owner-staging-rollback-plan.json"
DEFAULT_OWNER_POST_STAGING_VERIFIER = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_OWNER_POST_STAGE_COMMIT_GATE = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_OWNER_COMMIT_PACKET = REPORT_DIR / "commercial-delivery-owner-commit-packet.json"
DEFAULT_OWNER_DELIVERY_PACKET = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-approval-resume-packet.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-approval-resume-packet.md"


@dataclass(frozen=True)
class OwnerApprovalResumePacketCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerApprovalResumeCommandGroup:
    name: str
    title: str
    commands: list[str]
    executable_now: bool
    prerequisites: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnerApprovalResumePacket:
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
    real_owner_approval_present: bool
    real_owner_approval_written: bool
    full_codex_parity_claimed: bool
    waiting_for_owner: bool
    resume_ready: bool
    stage_allowed: bool
    stage_execution_ready: bool
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    approval_payload_path: str
    stage_path_digest: str | None
    stage_command_digest: str | None
    expected_stage_path_set_digest: str | None
    summary: dict[str, Any]
    command_groups: list[OwnerApprovalResumeCommandGroup]
    checks: list[OwnerApprovalResumePacketCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command_groups"] = [asdict(group) for group in self.command_groups]
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["command_groups_count"] = len(self.command_groups)
        payload["checks_count"] = len(self.checks)
        payload["next_actions_count"] = len(self.next_actions)
        payload["known_limits_count"] = len(self.known_limits)
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


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    value = _summary(payload).get(field)
    return str(value) if isinstance(value, str) and value else None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _section_commands(payload: dict[str, Any], section_name: str) -> list[str]:
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return []
    for section in sections:
        if isinstance(section, dict) and section.get("name") == section_name:
            return _list(section.get("commands"))
    return []


def _blocking_reasons(payload: dict[str, Any]) -> list[str]:
    reasons = _summary(payload).get("blocking_reasons")
    return _list(reasons)


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerApprovalResumePacketCheck:
    return OwnerApprovalResumePacketCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _nonempty_values_match(values: dict[str, str | None]) -> bool:
    present = [value for value in values.values() if value]
    return bool(present) and len(present) == len(values) and len(set(present)) == 1


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _failed_check_names(checks: list[OwnerApprovalResumePacketCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


def _count_values_match(values: dict[str, int | None]) -> bool:
    present = [value for value in values.values() if value is not None]
    return bool(present) and len(present) == len(values) and len(set(present)) == 1


def build_owner_approval_resume_packet(
    *,
    owner_approval_handoff_path: Path = DEFAULT_OWNER_APPROVAL_HANDOFF,
    pre_approval_drift_guard_path: Path = DEFAULT_PRE_APPROVAL_DRIFT_GUARD,
    owner_approval_payload_audit_path: Path = DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    owner_staging_runbook_path: Path = DEFAULT_OWNER_STAGING_RUNBOOK,
    owner_staging_rollback_plan_path: Path = DEFAULT_OWNER_STAGING_ROLLBACK_PLAN,
    owner_post_staging_verifier_path: Path = DEFAULT_OWNER_POST_STAGING_VERIFIER,
    owner_post_stage_commit_gate_path: Path = DEFAULT_OWNER_POST_STAGE_COMMIT_GATE,
    owner_commit_packet_path: Path = DEFAULT_OWNER_COMMIT_PACKET,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    task_board_path: Path = DEFAULT_TASK_BOARD,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
) -> OwnerApprovalResumePacket:
    report_paths = {
        "owner_approval_handoff": owner_approval_handoff_path,
        "pre_approval_drift_guard": pre_approval_drift_guard_path,
        "owner_approval_payload_audit": owner_approval_payload_audit_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
        "owner_staging_runbook": owner_staging_runbook_path,
        "owner_staging_rollback_plan": owner_staging_rollback_plan_path,
        "owner_post_staging_verifier": owner_post_staging_verifier_path,
        "owner_post_stage_commit_gate": owner_post_stage_commit_gate_path,
        "owner_commit_packet": owner_commit_packet_path,
        "owner_delivery_packet": owner_delivery_packet_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    handoff = reports["owner_approval_handoff"]
    guard = reports["pre_approval_drift_guard"]
    payload_audit = reports["owner_approval_payload_audit"]
    approval_gate = reports["owner_stage_approval_gate"]
    execution_plan = reports["owner_stage_execution_plan"]
    runbook = reports["owner_staging_runbook"]
    rollback_plan = reports["owner_staging_rollback_plan"]
    post_staging = reports["owner_post_staging_verifier"]
    commit_gate = reports["owner_post_stage_commit_gate"]
    commit_packet = reports["owner_commit_packet"]
    delivery_packet = reports["owner_delivery_packet"]
    task_board = reports["task_board"]
    handoff_summary = _summary(handoff)
    delivery_summary = _summary(delivery_packet)
    task_summary = _summary(task_board)

    real_owner_approval_present = owner_approval_path.exists()
    approval_payload_ready = (
        _status(payload_audit) == "owner_approval_payload_ready"
        and payload_audit.get("approval_payload_present") is True
        and payload_audit.get("approval_payload_valid") is True
        and payload_audit.get("ready_for_approval_gate") is True
    )
    approval_payload_waiting = (
        _status(payload_audit) == "owner_approval_payload_blocked"
        and payload_audit.get("approval_payload_present") is False
        and payload_audit.get("ready_for_approval_gate") is not True
    )
    stage_allowed = (
        _status(approval_gate) == "owner_stage_approval_ready"
        and approval_gate.get("stage_allowed") is True
    )
    approval_gate_waiting = (
        _status(approval_gate) == "owner_stage_approval_blocked"
        and approval_gate.get("stage_allowed") is not True
    )
    stage_execution_ready = (
        _status(execution_plan) == "owner_stage_execution_ready"
        and execution_plan.get("stage_allowed") is True
    )
    stage_execution_waiting = (
        _status(execution_plan) == "owner_stage_execution_blocked"
        and execution_plan.get("stage_allowed") is not True
    )
    waiting_for_owner = (
        not real_owner_approval_present
        and approval_payload_waiting
        and approval_gate_waiting
        and stage_execution_waiting
    )
    resume_ready = (
        real_owner_approval_present
        and approval_payload_ready
        and stage_allowed
        and stage_execution_ready
    )
    post_staging_accounted_for = _status(post_staging) in {
        "owner_post_staging_verification_blocked",
        "owner_post_staging_verification_ready",
    }
    commit_gate_accounted_for = _status(commit_gate) in {
        "owner_post_stage_commit_gate_blocked",
        "owner_post_stage_commit_gate_ready",
    }
    commit_packet_accounted_for = _status(commit_packet) in {
        "owner_commit_packet_blocked",
        "owner_commit_packet_ready",
    }
    post_stage_resume_evidence_ready = (
        resume_ready
        and _status(delivery_packet) == "owner_delivery_packet_ready"
        and delivery_packet.get("stage_ready") is True
        and _status(rollback_plan) == "owner_staging_rollback_plan_ready"
        and _status(post_staging) == "owner_post_staging_verification_ready"
        and _status(commit_gate) == "owner_post_stage_commit_gate_ready"
        and _status(commit_packet) == "owner_commit_packet_ready"
        and _status(task_board) == "commercial_delivery_ready_for_owner_staging_review"
    )
    owner_approval_handoff_post_stage_accounted_for = (
        _status(handoff) == "owner_approval_handoff_blocked"
        and post_stage_resume_evidence_ready
    )
    owner_staging_runbook_post_stage_accounted_for = (
        _status(runbook) == "owner_staging_runbook_blocked"
        and post_stage_resume_evidence_ready
    )
    owner_approval_handoff_accounted_for = (
        _status(handoff) == "owner_approval_handoff_ready"
        or owner_approval_handoff_post_stage_accounted_for
    )
    owner_staging_runbook_accounted_for = (
        _status(runbook) == "owner_staging_runbook_ready"
        or owner_staging_runbook_post_stage_accounted_for
    )
    stage_path_digest_sources = {
        "owner_approval_handoff": _digest_field(handoff, "stage_path_digest"),
        "pre_approval_drift_guard": _digest_field(guard, "stage_path_digest"),
        "owner_stage_approval_gate": _digest_field(approval_gate, "stage_path_digest"),
        "owner_stage_execution_plan": _digest_field(execution_plan, "stage_path_digest"),
        "owner_post_staging_verifier": _digest_field(post_staging, "stage_path_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "stage_path_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "stage_path_digest"),
        "owner_delivery_packet": _digest_field(delivery_packet, "stage_path_digest"),
    }
    stage_command_digest_sources = {
        "owner_approval_handoff": _digest_field(handoff, "stage_command_digest"),
        "pre_approval_drift_guard": _digest_field(guard, "stage_command_digest"),
        "owner_stage_approval_gate": _digest_field(approval_gate, "stage_command_digest"),
        "owner_stage_execution_plan": _digest_field(execution_plan, "stage_command_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "stage_command_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "stage_command_digest"),
        "owner_delivery_packet": _digest_field(delivery_packet, "stage_command_digest"),
    }
    expected_stage_path_set_digest_sources = {
        "owner_approval_handoff": _digest_field(handoff, "expected_stage_path_set_digest"),
        "pre_approval_drift_guard": _digest_field(guard, "expected_stage_path_set_digest"),
        "owner_delivery_packet": _digest_field(delivery_packet, "expected_stage_path_set_digest"),
        "owner_post_staging_verifier": _digest_field(post_staging, "expected_stage_path_set_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "expected_stage_path_set_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "expected_stage_path_set_digest"),
    }
    stage_counts = {
        "handoff_stage_include_count": _int_or_none(handoff_summary.get("stage_include_count")),
        "delivery_stage_include_count": _int_or_none(delivery_summary.get("stage_include_count")),
        "delivery_owner_stage_command_count": _int_or_none(delivery_summary.get("owner_stage_command_count")),
        "runbook_stage_command_count": _int_or_none(_summary(runbook).get("stage_command_count")),
        "execution_plan_stage_command_count": _int_or_none(execution_plan.get("stage_command_count")),
    }
    common_owner_gated = (
        handoff.get("owner_gated") is True
        and delivery_packet.get("owner_gated") is True
        and runbook.get("owner_gated") is True
        and rollback_plan.get("owner_gated") is True
        and approval_gate.get("owner_gated") is True
        and execution_plan.get("owner_gated") is True
    )
    full_codex_parity_claimed = _claims_parity(list(reports.values()))

    checks = [
        _check("reports_readable", not errors, details={"errors": errors}, error="one or more resume packet inputs are missing"),
        _check(
            "owner_approval_handoff_ready",
            owner_approval_handoff_accounted_for,
            details={
                "status": _status(handoff),
                "post_stage_accounted_for": owner_approval_handoff_post_stage_accounted_for,
                "post_stage_resume_evidence_ready": post_stage_resume_evidence_ready,
            },
            error="owner approval handoff is not ready or accounted for by post-stage evidence",
        ),
        _check(
            "owner_delivery_packet_ready",
            _status(delivery_packet) == "owner_delivery_packet_ready" and delivery_packet.get("stage_ready") is True,
            details={"status": _status(delivery_packet), "stage_ready": delivery_packet.get("stage_ready")},
            error="owner delivery packet is not ready",
        ),
        _check(
            "owner_staging_runbook_ready",
            owner_staging_runbook_accounted_for,
            details={
                "status": _status(runbook),
                "post_stage_accounted_for": owner_staging_runbook_post_stage_accounted_for,
                "post_stage_resume_evidence_ready": post_stage_resume_evidence_ready,
            },
            error="owner staging runbook is not ready or accounted for by post-stage evidence",
        ),
        _check(
            "owner_staging_rollback_plan_ready",
            _status(rollback_plan) == "owner_staging_rollback_plan_ready",
            details={"status": _status(rollback_plan)},
            error="owner staging rollback plan is not ready",
        ),
        _check(
            "task_board_ready",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={"status": _status(task_board), "secondary_pending_count": task_summary.get("secondary_pending_count")},
            error="commercial delivery task board is not ready",
        ),
        _check(
            "pre_approval_guard_ready_or_superseded",
            real_owner_approval_present or _status(guard) == "pre_approval_drift_guard_ready",
            details={
                "status": _status(guard),
                "real_owner_approval_present": real_owner_approval_present,
                "guard_real_owner_approval_present": guard.get("real_owner_approval_present"),
            },
            error="pre-approval drift guard is not ready before owner approval",
        ),
        _check(
            "owner_approval_boundary_accounted_for",
            waiting_for_owner or resume_ready,
            details={
                "real_owner_approval_present": real_owner_approval_present,
                "owner_approval_payload_audit_status": _status(payload_audit),
                "approval_payload_present": payload_audit.get("approval_payload_present"),
                "ready_for_approval_gate": payload_audit.get("ready_for_approval_gate"),
                "owner_stage_approval_gate_status": _status(approval_gate),
                "stage_allowed": approval_gate.get("stage_allowed"),
                "owner_stage_execution_plan_status": _status(execution_plan),
                "execution_stage_allowed": execution_plan.get("stage_allowed"),
            },
            error="owner approval state is neither waiting for owner nor ready to resume",
        ),
        _check(
            "stage_counts_consistent",
            _count_values_match(stage_counts),
            details={"stage_counts": stage_counts},
            error="stage counts differ across handoff, delivery, runbook, and execution plan",
        ),
        _check(
            "stage_path_digest_consistent",
            _nonempty_values_match(stage_path_digest_sources),
            details={"stage_path_digest_sources": stage_path_digest_sources},
            error="stage path digest is missing or inconsistent across resume inputs",
        ),
        _check(
            "stage_command_digest_consistent",
            _nonempty_values_match(stage_command_digest_sources),
            details={"stage_command_digest_sources": stage_command_digest_sources},
            error="stage command digest is missing or inconsistent across resume inputs",
        ),
        _check(
            "expected_stage_path_set_digest_consistent",
            _nonempty_values_match(expected_stage_path_set_digest_sources),
            details={"expected_stage_path_set_digest_sources": expected_stage_path_set_digest_sources},
            error="expected stage path set digest is missing or inconsistent across resume inputs",
        ),
        _check(
            "post_stage_sequence_accounted_for",
            post_staging_accounted_for and commit_gate_accounted_for and commit_packet_accounted_for,
            details={
                "owner_post_staging_verifier_status": _status(post_staging),
                "owner_post_stage_commit_gate_status": _status(commit_gate),
                "owner_commit_packet_status": _status(commit_packet),
            },
            error="post-stage verifier, commit gate, or commit packet is in an unknown state",
        ),
        _check(
            "owner_gate_present",
            common_owner_gated,
            details={
                "owner_approval_handoff_owner_gated": handoff.get("owner_gated"),
                "owner_delivery_packet_owner_gated": delivery_packet.get("owner_gated"),
                "owner_staging_runbook_owner_gated": runbook.get("owner_gated"),
                "owner_staging_rollback_plan_owner_gated": rollback_plan.get("owner_gated"),
                "owner_stage_approval_gate_owner_gated": approval_gate.get("owner_gated"),
                "owner_stage_execution_plan_owner_gated": execution_plan.get("owner_gated"),
            },
            error="one or more resume packet inputs are missing owner-gated markers",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more resume packet inputs claim full Codex parity",
        ),
        _check(
            "no_resume_packet_mutation",
            True,
            details={
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
                "network_mutation_performed": False,
                "agent_execution_enabled": False,
                "real_owner_approval_written": False,
            },
        ),
    ]
    checks_passed = all(check.status == "passed" for check in checks)
    if checks_passed and resume_ready:
        status = "owner_approval_resume_packet_ready"
    elif checks_passed and waiting_for_owner:
        status = "owner_approval_resume_packet_waiting_for_owner"
    else:
        status = "owner_approval_resume_packet_blocked"

    planned_stage_commands = _list(execution_plan.get("planned_stage_commands"))
    runbook_stage_commands = _section_commands(runbook, "owner_stage_commands")
    stage_commands = planned_stage_commands if resume_ready and planned_stage_commands else runbook_stage_commands
    pre_stage_commands = _section_commands(runbook, "pre_stage_verification")
    post_stage_commands = _section_commands(runbook, "post_stage_verification")
    commit_preview = delivery_summary.get("commit_command_preview") or _summary(runbook).get("commit_command_preview")
    command_groups = [
        OwnerApprovalResumeCommandGroup(
            name="owner_create_approval_payload",
            title="Owner creates real approval payload",
            commands=[],
            executable_now=not real_owner_approval_present,
            prerequisites=["owner_approval_handoff_ready", "human_owner_review"],
            notes=[
                f"Create the real approval payload at {_display_path(owner_approval_path)} using the handoff template.",
                "This packet never writes the real approval payload.",
            ],
        ),
        OwnerApprovalResumeCommandGroup(
            name="approval_payload_audit",
            title="Audit the real approval payload",
            commands=["python scripts\\commercial_delivery_owner_approval_payload_audit.py"],
            executable_now=real_owner_approval_present,
            prerequisites=["real_owner_approval_present"],
        ),
        OwnerApprovalResumeCommandGroup(
            name="approval_gate",
            title="Validate owner stage approval gate",
            commands=["python scripts\\commercial_delivery_owner_stage_approval_gate.py"],
            executable_now=approval_payload_ready,
            prerequisites=["owner_approval_payload_ready"],
        ),
        OwnerApprovalResumeCommandGroup(
            name="stage_execution_plan",
            title="Regenerate owner stage execution plan",
            commands=["python scripts\\commercial_delivery_owner_stage_execution_plan.py"],
            executable_now=stage_allowed,
            prerequisites=["owner_stage_approval_ready"],
        ),
        OwnerApprovalResumeCommandGroup(
            name="pre_stage_verification",
            title="Run pre-stage verification",
            commands=pre_stage_commands,
            executable_now=resume_ready,
            prerequisites=["owner_stage_execution_ready"],
            notes=["Run immediately before any git add command."],
        ),
        OwnerApprovalResumeCommandGroup(
            name="owner_stage_commands",
            title="Run owner-approved stage commands",
            commands=stage_commands,
            executable_now=resume_ready,
            prerequisites=["pre_stage_verification_passed", "owner_stage_execution_ready"],
            notes=["Run only these exact git add commands; do not use git add ., git add -A, or git add --all."],
        ),
        OwnerApprovalResumeCommandGroup(
            name="post_stage_verification",
            title="Run post-stage verification",
            commands=post_stage_commands,
            executable_now=False,
            prerequisites=["owner_stage_commands_completed"],
            notes=["Run after staging and before any commit gate."],
        ),
        OwnerApprovalResumeCommandGroup(
            name="commit_gate_and_packet",
            title="Regenerate commit gate and commit packet",
            commands=[
                "python scripts\\commercial_delivery_owner_post_stage_commit_gate.py",
                "python scripts\\commercial_delivery_owner_commit_packet.py",
            ],
            executable_now=_status(post_staging) == "owner_post_staging_verification_ready",
            prerequisites=["owner_post_staging_verification_ready"],
        ),
        OwnerApprovalResumeCommandGroup(
            name="post_commit_evidence_refresh",
            title="Refresh final delivery evidence",
            commands=[
                "python scripts\\commercial_delivery_owner_delivery_packet.py",
                "python scripts\\commercial_delivery_closure_snapshot.py",
                "python scripts\\commercial_delivery_task_board.py",
            ],
            executable_now=_status(commit_packet) == "owner_commit_packet_ready",
            prerequisites=["owner_commit_packet_ready"],
            notes=[f"Commit preview: {commit_preview}"],
        ),
    ]
    blocking_reasons = _failed_check_names(checks)
    stage_path_digest = next((value for value in stage_path_digest_sources.values() if value), None)
    stage_command_digest = next((value for value in stage_command_digest_sources.values() if value), None)
    expected_stage_path_set_digest = next(
        (value for value in expected_stage_path_set_digest_sources.values() if value),
        None,
    )

    if status == "owner_approval_resume_packet_ready":
        next_actions = [
            "Run pre-stage verification immediately before staging.",
            "Run only the executable owner_stage_commands listed in this packet.",
            "After staging, rerun post-stage verification before commit gates.",
        ]
    elif status == "owner_approval_resume_packet_waiting_for_owner":
        next_actions = [
            "Wait for the human owner to create the real owner approval payload.",
            "After the payload exists, rerun approval payload audit, approval gate, stage execution plan, and this packet.",
            "Do not stage while this packet is waiting_for_owner.",
        ]
    else:
        next_actions = [
            "Refresh the commercial delivery report chain and fix failed checks before owner approval resume.",
            "Do not stage, commit, or push while this packet is blocked.",
        ]

    return OwnerApprovalResumePacket(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_approval_resume_packet",
        owner_gated=common_owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        real_owner_approval_present=real_owner_approval_present,
        real_owner_approval_written=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        waiting_for_owner=status == "owner_approval_resume_packet_waiting_for_owner",
        resume_ready=status == "owner_approval_resume_packet_ready",
        stage_allowed=stage_allowed,
        stage_execution_ready=stage_execution_ready,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        approval_payload_path=_display_path(owner_approval_path),
        stage_path_digest=stage_path_digest,
        stage_command_digest=stage_command_digest,
        expected_stage_path_set_digest=expected_stage_path_set_digest,
        summary={
            "blocking_reasons": blocking_reasons,
            "owner_action_required": status != "owner_approval_resume_packet_ready",
            "stage_include_count": stage_counts["delivery_stage_include_count"],
            "owner_stage_command_count": stage_counts["delivery_owner_stage_command_count"],
            "runbook_stage_command_count": stage_counts["runbook_stage_command_count"],
            "execution_plan_stage_command_count": stage_counts["execution_plan_stage_command_count"],
            "planned_stage_commands_count": len(planned_stage_commands),
            "stage_commands_preview_count": len(stage_commands),
            "pre_stage_verification_command_count": len(pre_stage_commands),
            "post_stage_verification_command_count": len(post_stage_commands),
            "owner_approval_payload_audit_status": _status(payload_audit),
            "owner_stage_approval_gate_status": _status(approval_gate),
            "owner_stage_execution_plan_status": _status(execution_plan),
            "owner_post_staging_verifier_status": _status(post_staging),
            "owner_post_stage_commit_gate_status": _status(commit_gate),
            "owner_commit_packet_status": _status(commit_packet),
            "post_stage_resume_evidence_ready": post_stage_resume_evidence_ready,
            "owner_approval_handoff_post_stage_accounted_for": owner_approval_handoff_post_stage_accounted_for,
            "owner_staging_runbook_post_stage_accounted_for": owner_staging_runbook_post_stage_accounted_for,
            "owner_staging_rollback_plan_status": _status(rollback_plan),
            "owner_delivery_packet_status": _status(delivery_packet),
            "task_board_status": _status(task_board),
            "pre_approval_drift_guard_status": _status(guard),
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "control_modes_preservation_status": delivery_summary.get("control_modes_preservation_status"),
            "control_modes_plan_only_default": delivery_summary.get("control_modes_plan_only_default"),
            "control_modes_loop_phases": delivery_summary.get("control_modes_loop_phases"),
            "commit_command_preview": commit_preview,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
        },
        command_groups=command_groups,
        checks=checks,
        next_actions=next_actions,
        known_limits=[
            "This packet is read-only except writing local evidence files.",
            "It does not write or infer real owner approval evidence.",
            "It does not stage files, reset files, commit, push, call network services, run tests, or execute agents.",
            "It does not claim full Codex parity or commercial delivery completion.",
        ],
    )


def render_markdown_packet(packet: OwnerApprovalResumePacket) -> str:
    lines = [
        "# Commercial Delivery Owner Approval Resume Packet",
        "",
        f"- Status: `{packet.status}`",
        f"- Generated at: `{packet.generated_at}`",
        f"- Waiting for owner: `{str(packet.waiting_for_owner).lower()}`",
        f"- Resume ready: `{str(packet.resume_ready).lower()}`",
        f"- Real owner approval present: `{str(packet.real_owner_approval_present).lower()}`",
        f"- Stage allowed: `{str(packet.stage_allowed).lower()}`",
        f"- Stage execution ready: `{str(packet.stage_execution_ready).lower()}`",
        f"- Stage path digest: `{packet.stage_path_digest or '<missing>'}`",
        f"- Stage command digest: `{packet.stage_command_digest or '<missing>'}`",
        f"- Expected stage path set digest: `{packet.expected_stage_path_set_digest or '<missing>'}`",
        f"- Secondary handoff completed count: `{packet.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{packet.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Secondary next queue: `{', '.join(packet.summary.get('secondary_handoff_next_queue') or [])}`",
        "",
        "## Checks",
        "",
    ]
    for check in packet.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Command Sequence", ""])
    for group in packet.command_groups:
        lines.extend(
            [
                f"### {group.name}",
                "",
                f"- Title: {group.title}",
                f"- Executable now: `{str(group.executable_now).lower()}`",
                f"- Prerequisites: `{', '.join(group.prerequisites)}`",
            ]
        )
        if group.commands:
            lines.append("- Commands:")
            lines.extend(f"  - `{command}`" for command in group.commands)
        if group.notes:
            lines.append("- Notes:")
            lines.extend(f"  - {note}" for note in group.notes)
        lines.append("")
    lines.extend(["## Next Actions", ""])
    lines.extend(f"- {action}" for action in packet.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(packet: OwnerApprovalResumePacket, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_packet(packet: OwnerApprovalResumePacket, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_packet(packet), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-approval-handoff", type=Path, default=DEFAULT_OWNER_APPROVAL_HANDOFF)
    parser.add_argument("--pre-approval-drift-guard", type=Path, default=DEFAULT_PRE_APPROVAL_DRIFT_GUARD)
    parser.add_argument("--owner-approval-payload-audit", type=Path, default=DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
    parser.add_argument("--owner-staging-runbook", type=Path, default=DEFAULT_OWNER_STAGING_RUNBOOK)
    parser.add_argument("--owner-staging-rollback-plan", type=Path, default=DEFAULT_OWNER_STAGING_ROLLBACK_PLAN)
    parser.add_argument("--owner-post-staging-verifier", type=Path, default=DEFAULT_OWNER_POST_STAGING_VERIFIER)
    parser.add_argument("--owner-post-stage-commit-gate", type=Path, default=DEFAULT_OWNER_POST_STAGE_COMMIT_GATE)
    parser.add_argument("--owner-commit-packet", type=Path, default=DEFAULT_OWNER_COMMIT_PACKET)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--owner-approval", type=Path, default=DEFAULT_OWNER_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_owner_approval_resume_packet(
        owner_approval_handoff_path=args.owner_approval_handoff,
        pre_approval_drift_guard_path=args.pre_approval_drift_guard,
        owner_approval_payload_audit_path=args.owner_approval_payload_audit,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        owner_staging_runbook_path=args.owner_staging_runbook,
        owner_staging_rollback_plan_path=args.owner_staging_rollback_plan,
        owner_post_staging_verifier_path=args.owner_post_staging_verifier,
        owner_post_stage_commit_gate_path=args.owner_post_stage_commit_gate,
        owner_commit_packet_path=args.owner_commit_packet,
        owner_delivery_packet_path=args.owner_delivery_packet,
        task_board_path=args.task_board,
        owner_approval_path=args.owner_approval,
    )
    write_report(packet, args.output)
    write_markdown_packet(packet, args.markdown_output)
    print(f"Commercial delivery owner approval resume packet status: {packet.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Waiting for owner: {packet.waiting_for_owner}")
    print(f"Resume ready: {packet.resume_ready}")
    for check in packet.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if packet.status in {
        "owner_approval_resume_packet_ready",
        "owner_approval_resume_packet_waiting_for_owner",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
