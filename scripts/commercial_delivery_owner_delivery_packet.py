#!/usr/bin/env python3
"""Build the final owner-facing commercial delivery packet.

The packet summarizes the pre-stage and post-stage owner gates into one
handoff artifact. It never stages files, creates commits, pushes branches,
runs tests, calls external services, or executes agents.
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

DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_OWNER_STAGING_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_OWNER_STAGING_RUNBOOK = REPORT_DIR / "commercial-delivery-owner-staging-runbook.json"
DEFAULT_OWNER_PRE_STAGE_GATE = REPORT_DIR / "commercial-delivery-owner-pre-stage-readiness-gate.json"
DEFAULT_OWNER_POST_STAGE_COMMIT_GATE = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_OWNER_COMMIT_PACKET = REPORT_DIR / "commercial-delivery-owner-commit-packet.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_APPROVAL_REQUEST = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.json"
DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_OWNER_STAGING_ROLLBACK_PLAN = REPORT_DIR / "commercial-delivery-owner-staging-rollback-plan.json"
DEFAULT_REFRESH_CHAIN = REPORT_DIR / "commercial-delivery-refresh-chain-receipt.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_CONTROL_MODES_PRESERVATION = REPORT_DIR / "commercial-delivery-control-modes-preservation.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-delivery-packet.md"


@dataclass(frozen=True)
class OwnerDeliveryPacketCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerDeliveryPacketSection:
    name: str
    title: str
    commands: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnerDeliveryPacket:
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
    stage_ready: bool
    commit_ready: bool
    owner_approval_required: bool
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    sections: list[OwnerDeliveryPacketSection]
    checks: list[OwnerDeliveryPacketCheck]
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


def _failed_step_names(payload: dict[str, Any]) -> list[str]:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return []
    names: list[str] = []
    for step in steps:
        if isinstance(step, dict) and step.get("status") == "failed" and step.get("name") is not None:
            names.append(str(step.get("name")))
    return names


def _failed_check_names(payload: dict[str, Any]) -> set[str]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return set()
    names: set[str] = set()
    for check in checks:
        if isinstance(check, dict) and check.get("status") == "failed" and check.get("name") is not None:
            names.add(str(check.get("name")))
    return names


REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS = {
    "task_board_before_owner_decision",
    "owner_decision_brief",
    "owner_pre_stage_readiness_gate",
    "owner_staging_runbook",
    "owner_staging_preflight",
    "owner_staging_rollback_plan",
    "owner_delivery_packet_before_owner_approval",
    "owner_delivery_packet",
    "owner_stage_approval_request",
    "owner_approval_payload_audit",
    "owner_stage_execution_plan",
    "owner_stage_approval_brief",
    "closure_snapshot",
    "owner_approval_handoff",
    "pre_approval_drift_guard",
    "owner_approval_resume_packet",
    "owner_post_approval_operator_checklist",
    "task_board_after_owner_decision",
}


def _refresh_receipt_delivery_bootstrap(refresh_chain: dict[str, Any]) -> bool:
    summary = _summary(refresh_chain)
    failed_steps = _failed_step_names(refresh_chain)
    failed_step_count = int(summary.get("failed_step_count") or 0)
    return (
        _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_blocked"
        and failed_step_count > 0
        and len(failed_steps) == failed_step_count
        and set(failed_steps).issubset(REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS)
    )


def _refresh_receipt_ready_or_delivery_bootstrap(refresh_chain: dict[str, Any]) -> bool:
    return (
        _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_ready"
        or _refresh_receipt_delivery_bootstrap(refresh_chain)
    )


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _digest_values(values: list[str]) -> str | None:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str | None:
    return _digest_values(sorted(set(paths))) if paths else None


def _post_commit_noop_accounted_for(*payloads: dict[str, Any]) -> bool:
    return all(
        payload.get("post_commit_noop_accounted_for") is True
        or _summary(payload).get("post_commit_noop_accounted_for") is True
        for payload in payloads
    )


def _summary_digest(payload: dict[str, Any], field: str) -> str | None:
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


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerDeliveryPacketCheck:
    return OwnerDeliveryPacketCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def build_owner_delivery_packet(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    owner_staging_packet_path: Path = DEFAULT_OWNER_STAGING_PACKET,
    owner_staging_runbook_path: Path = DEFAULT_OWNER_STAGING_RUNBOOK,
    owner_pre_stage_gate_path: Path = DEFAULT_OWNER_PRE_STAGE_GATE,
    owner_post_stage_commit_gate_path: Path = DEFAULT_OWNER_POST_STAGE_COMMIT_GATE,
    owner_commit_packet_path: Path = DEFAULT_OWNER_COMMIT_PACKET,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_approval_request_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_REQUEST,
    owner_approval_payload_audit_path: Path = DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    owner_staging_rollback_plan_path: Path = DEFAULT_OWNER_STAGING_ROLLBACK_PLAN,
    refresh_chain_path: Path = DEFAULT_REFRESH_CHAIN,
    task_board_path: Path = DEFAULT_TASK_BOARD,
    control_modes_preservation_path: Path = DEFAULT_CONTROL_MODES_PRESERVATION,
) -> OwnerDeliveryPacket:
    required_report_paths = {
        "manifest": manifest_path,
        "owner_staging_packet": owner_staging_packet_path,
        "owner_staging_runbook": owner_staging_runbook_path,
        "owner_pre_stage_gate": owner_pre_stage_gate_path,
        "owner_post_stage_commit_gate": owner_post_stage_commit_gate_path,
        "owner_commit_packet": owner_commit_packet_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "refresh_chain": refresh_chain_path,
        "task_board": task_board_path,
        "control_modes_preservation": control_modes_preservation_path,
    }
    optional_report_paths = {
        "owner_stage_approval_request": owner_stage_approval_request_path,
        "owner_approval_payload_audit": owner_approval_payload_audit_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
        "owner_staging_rollback_plan": owner_staging_rollback_plan_path,
    }
    report_paths = {**required_report_paths, **optional_report_paths}
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    optional_missing: list[str] = []
    optional_errors: dict[str, str] = {}
    for name, path in required_report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error
    for name, path in optional_report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            if path.exists():
                optional_errors[name] = error
            else:
                optional_missing.append(name)

    manifest = reports["manifest"]
    staging_packet = reports["owner_staging_packet"]
    staging_runbook = reports["owner_staging_runbook"]
    pre_stage_gate = reports["owner_pre_stage_gate"]
    commit_gate = reports["owner_post_stage_commit_gate"]
    commit_packet = reports["owner_commit_packet"]
    approval_gate = reports["owner_stage_approval_gate"]
    approval_request = reports["owner_stage_approval_request"]
    approval_payload_audit = reports["owner_approval_payload_audit"]
    stage_execution_plan = reports["owner_stage_execution_plan"]
    rollback_plan = reports["owner_staging_rollback_plan"]
    refresh_chain = reports["refresh_chain"]
    task_board = reports["task_board"]
    control_modes_preservation = reports["control_modes_preservation"]
    task_summary = _summary(task_board)
    refresh_summary = _summary(refresh_chain)
    control_modes_summary = _summary(control_modes_preservation)
    refresh_receipt_ok = _refresh_receipt_ready_or_delivery_bootstrap(refresh_chain)
    refresh_delivery_bootstrap = _refresh_receipt_delivery_bootstrap(refresh_chain)

    stage_commands = _list(staging_packet.get("stage_commands"))
    pre_stage_commands = _list(staging_packet.get("pre_stage_verification_commands"))
    post_stage_commands = _list(staging_packet.get("post_stage_verification_commands"))
    commit_preview = staging_packet.get("commit_command_preview") or commit_packet.get("commit_command_preview")
    stage_path_digest = staging_packet.get("stage_path_digest")
    stage_command_digest = staging_packet.get("stage_command_digest")
    stage_paths = _list(staging_packet.get("stage_paths"))
    expected_nonzero_steps = _list(refresh_summary.get("expected_nonzero_steps"))
    stage_include_count = manifest.get("stage_include_count")
    staging_stage_include_count = staging_packet.get("stage_include_count")
    eligible_stage_count = int(staging_packet.get("eligible_stage_count") or len(stage_paths))
    owner_stage_command_count = len(stage_commands)
    empty_digest = _digest_values([])
    post_commit_noop_accounted_for = _post_commit_noop_accounted_for(
        staging_packet,
        commit_gate,
        commit_packet,
    ) and not stage_paths and not stage_commands and owner_stage_command_count == eligible_stage_count == 0
    expected_stage_path_set_digest = (
        empty_digest if post_commit_noop_accounted_for else _path_set_digest(stage_paths)
    )
    stage_command_count_accounted_for = (
        owner_stage_command_count == eligible_stage_count
        and (bool(stage_commands) or post_commit_noop_accounted_for)
        and int(staging_stage_include_count or -1) == int(stage_include_count or -2)
    )
    strict_stage_ready = (
        _status(manifest) == "original_kernel_delivery_manifest_ready"
        and _status(staging_packet) == "owner_staging_packet_ready"
        and _status(staging_runbook) == "owner_staging_runbook_ready"
        and _status(pre_stage_gate) == "owner_pre_stage_readiness_ready"
        and _status(task_board) == "commercial_delivery_ready_for_owner_staging_review"
        and _status(control_modes_preservation) == "control_modes_preservation_ready"
    )
    commit_ready = (
        _status(commit_gate) == "owner_post_stage_commit_gate_ready"
        and _status(commit_packet) == "owner_commit_packet_ready"
        and commit_packet.get("commit_allowed") is True
    )
    commit_or_noop_accounted_for = commit_ready or post_commit_noop_accounted_for
    stage_approval_ready = _status(approval_gate) == "owner_stage_approval_ready"
    stage_approval_expected_blocked = (
        _status(approval_gate) in {None, "owner_stage_approval_blocked"}
        and approval_gate.get("stage_allowed") is not True
    )
    approval_request_ready = _status(approval_request) == "owner_stage_approval_request_ready"
    approval_request_missing = "owner_stage_approval_request" in optional_missing
    approval_payload_audit_missing = "owner_approval_payload_audit" in optional_missing
    approval_request_blocked_by_delivery_bootstrap = (
        _status(approval_request) == "owner_stage_approval_request_blocked"
        and _failed_check_names(approval_request).issubset(
            {
                "owner_delivery_packet_ready",
                "owner_delivery_packet_requires_approval",
            }
        )
        and _summary(approval_request).get("stage_include_count") == stage_include_count
        and _summary(approval_request).get("eligible_stage_count") == eligible_stage_count
        and _summary(approval_request).get("owner_stage_command_count") == owner_stage_command_count
        and _summary(approval_request).get("stage_path_digest") == stage_path_digest
        and _summary(approval_request).get("stage_command_digest") == stage_command_digest
        and _summary(approval_request).get("expected_stage_path_set_digest") == expected_stage_path_set_digest
    )
    approval_request_blocked_by_post_stage_commit = (
        commit_ready
        and _status(approval_request) == "owner_stage_approval_request_blocked"
        and _failed_check_names(approval_request).issubset(
            {
                "owner_delivery_packet_ready",
                "owner_delivery_packet_requires_approval",
            }
        )
        and _summary(approval_request).get("stage_include_count") == stage_include_count
        and _summary(approval_request).get("eligible_stage_count") == eligible_stage_count
        and _summary(approval_request).get("owner_stage_command_count") == owner_stage_command_count
        and _summary(approval_request).get("stage_path_digest") == stage_path_digest
        and _summary(approval_request).get("stage_command_digest") == stage_command_digest
        and _summary(approval_request).get("expected_stage_path_set_digest") == expected_stage_path_set_digest
    )
    approval_request_post_commit_noop_accounted_for = (
        post_commit_noop_accounted_for
        and commit_or_noop_accounted_for
        and _status(approval_request) == "owner_stage_approval_request_blocked"
        and _failed_check_names(approval_request).issubset(
            {
                "owner_delivery_packet_ready",
                "owner_delivery_packet_requires_approval",
                "stage_counts_match_delivery_packet",
                "stage_command_digest_present",
                "expected_stage_path_set_digest_present",
            }
        )
        and _summary(approval_request).get("stage_include_count") == stage_include_count
        and _int_or_none(_summary(approval_request).get("eligible_stage_count")) == 0
        and _int_or_none(_summary(approval_request).get("owner_stage_command_count")) == 0
        and _summary(approval_request).get("stage_path_digest") == empty_digest
    )
    approval_request_accounted_for = (
        approval_request_ready
        or approval_request_missing
        or approval_request_blocked_by_delivery_bootstrap
        or approval_request_blocked_by_post_stage_commit
        or approval_request_post_commit_noop_accounted_for
    )
    approval_payload_audit_summary = _summary(approval_payload_audit)
    approval_payload_audit_failed_checks = _failed_check_names(approval_payload_audit)
    approval_payload_audit_has_matched_payload = (
        approval_payload_audit_summary.get("stage_include_count") == stage_include_count
        and approval_payload_audit_summary.get("owner_stage_command_count") == owner_stage_command_count
        and approval_payload_audit_summary.get("approval_stage_include_count") == stage_include_count
        and approval_payload_audit_summary.get("approval_owner_stage_command_count") == owner_stage_command_count
        and approval_payload_audit_summary.get("commit_command_preview") == commit_preview
        and approval_payload_audit_summary.get("approval_commit_command_preview") == commit_preview
        and approval_payload_audit_summary.get("stage_path_digest") == stage_path_digest
        and approval_payload_audit_summary.get("approval_stage_path_digest") == stage_path_digest
        and approval_payload_audit_summary.get("stage_command_digest") == stage_command_digest
        and approval_payload_audit_summary.get("approval_stage_command_digest") == stage_command_digest
        and approval_payload_audit_summary.get("expected_stage_path_set_digest")
        == expected_stage_path_set_digest
        and approval_payload_audit_summary.get("approval_expected_stage_path_set_digest")
        == expected_stage_path_set_digest
    )
    approval_payload_audit_blocked_by_delivery_bootstrap = (
        _status(approval_payload_audit) == "owner_approval_payload_blocked"
        and approval_payload_audit.get("approval_payload_present") is True
        and approval_payload_audit.get("ready_for_approval_gate") is False
        and approval_payload_audit.get("mutation_performed") is not True
        and approval_payload_audit.get("git_stage_performed") is not True
        and approval_payload_audit.get("git_commit_performed") is not True
        and approval_payload_audit.get("git_push_performed") is not True
        and approval_payload_audit.get("network_mutation_performed") is not True
        and approval_payload_audit.get("agent_execution_enabled") is not True
        and approval_payload_audit.get("full_codex_parity_claimed") is not True
        and approval_payload_audit_failed_checks.issubset(
            {
                "owner_delivery_packet_ready",
                "owner_stage_approval_request_ready",
            }
        )
        and "owner_delivery_packet_ready" in approval_payload_audit_failed_checks
        and approval_payload_audit_has_matched_payload
    )
    approval_payload_audit_blocked_by_post_stage_commit = (
        commit_ready
        and _status(approval_payload_audit) == "owner_approval_payload_blocked"
        and approval_payload_audit.get("approval_payload_present") is True
        and approval_payload_audit.get("ready_for_approval_gate") is False
        and approval_payload_audit.get("mutation_performed") is not True
        and approval_payload_audit.get("git_stage_performed") is not True
        and approval_payload_audit.get("git_commit_performed") is not True
        and approval_payload_audit.get("git_push_performed") is not True
        and approval_payload_audit.get("network_mutation_performed") is not True
        and approval_payload_audit.get("agent_execution_enabled") is not True
        and approval_payload_audit.get("full_codex_parity_claimed") is not True
        and approval_payload_audit_failed_checks.issubset(
            {
                "owner_delivery_packet_ready",
                "owner_stage_approval_request_ready",
            }
        )
        and "owner_delivery_packet_ready" in approval_payload_audit_failed_checks
        and approval_payload_audit_has_matched_payload
    )
    approval_payload_audit_post_commit_noop_accounted_for = (
        post_commit_noop_accounted_for
        and commit_or_noop_accounted_for
        and _status(approval_payload_audit) == "owner_approval_payload_blocked"
        and approval_payload_audit.get("approval_payload_present") is True
        and approval_payload_audit.get("ready_for_approval_gate") is False
        and approval_payload_audit.get("mutation_performed") is not True
        and approval_payload_audit.get("git_stage_performed") is not True
        and approval_payload_audit.get("git_commit_performed") is not True
        and approval_payload_audit.get("git_push_performed") is not True
        and approval_payload_audit.get("network_mutation_performed") is not True
        and approval_payload_audit.get("agent_execution_enabled") is not True
        and approval_payload_audit.get("full_codex_parity_claimed") is not True
        and approval_payload_audit_failed_checks.issubset(
            {
                "owner_delivery_packet_ready",
                "owner_stage_approval_request_ready",
                "approval_counts_match_request_and_delivery_packet",
                "approval_digests_match_request_and_delivery_packet",
            }
        )
        and approval_payload_audit_summary.get("stage_include_count") == stage_include_count
        and _int_or_none(approval_payload_audit_summary.get("owner_stage_command_count")) == 0
        and approval_payload_audit_summary.get("stage_path_digest") == empty_digest
    )
    approval_payload_audit_accounted_for = (
        _status(approval_payload_audit) == "owner_approval_payload_ready"
        or approval_payload_audit_missing
        or approval_payload_audit_blocked_by_delivery_bootstrap
        or approval_payload_audit_blocked_by_post_stage_commit
        or approval_payload_audit_post_commit_noop_accounted_for
    )
    stage_execution_ready = _status(stage_execution_plan) == "owner_stage_execution_ready"
    stage_execution_expected_blocked = (
        _status(stage_execution_plan) == "owner_stage_execution_blocked"
        and stage_execution_plan.get("stage_allowed") is not True
    )
    stage_execution_missing = "owner_stage_execution_plan" in optional_missing
    stage_execution_accounted_for = stage_execution_ready or stage_execution_expected_blocked or stage_execution_missing
    rollback_plan_ready = _status(rollback_plan) == "owner_staging_rollback_plan_ready"
    rollback_plan_missing = "owner_staging_rollback_plan" in optional_missing
    rollback_plan_accounted_for = rollback_plan_ready or rollback_plan_missing
    rollback_plan_post_commit_noop_accounted_for = (
        post_commit_noop_accounted_for
        and rollback_plan_ready
        and rollback_plan.get("rollback_available") is False
        and _int_or_none(rollback_plan.get("reset_command_count")) == 0
        and _summary(rollback_plan).get("post_commit_noop_accounted_for") is True
    )
    approval_gate_summary = _summary(approval_gate)
    stage_execution_summary = _summary(stage_execution_plan)
    rollback_summary = _summary(rollback_plan)
    post_commit_stage_approval_accounted_for = stage_approval_ready or (
        commit_or_noop_accounted_for
        and stage_approval_expected_blocked
        and approval_request_accounted_for
        and approval_payload_audit_accounted_for
        and approval_gate_summary.get("stage_path_digest") == stage_path_digest
        and (
            approval_gate_summary.get("stage_command_digest") == stage_command_digest
            or (post_commit_noop_accounted_for and approval_gate_summary.get("stage_command_digest") in {None, empty_digest})
        )
        and (
            approval_gate_summary.get("expected_stage_path_set_digest") == expected_stage_path_set_digest
            or (
                post_commit_noop_accounted_for
                and approval_gate_summary.get("expected_stage_path_set_digest") in {None, empty_digest}
            )
        )
    )
    post_commit_stage_execution_accounted_for = stage_execution_ready or (
        commit_or_noop_accounted_for
        and stage_execution_expected_blocked
        and approval_request_accounted_for
        and approval_payload_audit_accounted_for
        and (
            stage_execution_summary.get("stage_path_digest") == stage_path_digest
            or (post_commit_noop_accounted_for and stage_execution_summary.get("stage_path_digest") in {None, empty_digest})
        )
        and (
            stage_execution_summary.get("stage_command_digest") == stage_command_digest
            or (post_commit_noop_accounted_for and stage_execution_summary.get("stage_command_digest") in {None, empty_digest})
        )
        and (
            stage_execution_summary.get("expected_stage_path_set_digest") == expected_stage_path_set_digest
            or (
                post_commit_noop_accounted_for
                and stage_execution_summary.get("expected_stage_path_set_digest") in {None, empty_digest}
            )
        )
        and (
            _int_or_none(stage_execution_plan.get("stage_command_count"))
            if _int_or_none(stage_execution_plan.get("stage_command_count")) is not None
            else _int_or_none(stage_execution_summary.get("stage_command_count"))
        )
        == owner_stage_command_count
    )
    post_commit_owner_gate_accounted_for = (
        commit_or_noop_accounted_for
        and post_commit_stage_approval_accounted_for
        and post_commit_stage_execution_accounted_for
        and approval_request_accounted_for
        and approval_payload_audit_accounted_for
        and (rollback_plan_ready or rollback_plan_post_commit_noop_accounted_for)
        and (
            rollback_summary.get("owner_staging_preflight_accounted_for") is True
            or "owner_staging_preflight" not in _failed_step_names(refresh_chain)
            or post_commit_noop_accounted_for
        )
    )
    post_stage_chain_accounted_for = (
        _status(manifest) == "original_kernel_delivery_manifest_ready"
        and _status(staging_packet) == "owner_staging_packet_ready"
        and (
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review"
            or (
                post_commit_noop_accounted_for
                and _status(task_board) == "commercial_delivery_blocked"
                and task_summary.get("owner_commit_packet_status") == "owner_commit_packet_ready"
                and task_summary.get("owner_post_stage_commit_gate_status")
                == "owner_post_stage_commit_gate_ready"
            )
        )
        and _status(control_modes_preservation) == "control_modes_preservation_ready"
        and _status(staging_runbook) == "owner_staging_runbook_blocked"
        and _status(pre_stage_gate) == "owner_pre_stage_readiness_blocked"
        and (
            (
                "owner_staging_runbook" in expected_nonzero_steps
                and "owner_pre_stage_readiness_gate" in expected_nonzero_steps
            )
            or refresh_delivery_bootstrap
            or (
                post_commit_noop_accounted_for
                and set(_failed_step_names(refresh_chain)).issubset(
                    REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS
                )
            )
        )
        and commit_or_noop_accounted_for
        and post_commit_owner_gate_accounted_for
        and (rollback_plan_ready or rollback_plan_post_commit_noop_accounted_for)
    )
    pre_approval_bootstrap_accounted_for = (
        refresh_delivery_bootstrap
        and approval_request_blocked_by_delivery_bootstrap
        and approval_payload_audit_blocked_by_delivery_bootstrap
        and stage_approval_expected_blocked
        and stage_execution_expected_blocked
        and rollback_plan_ready
        and _status(manifest) == "original_kernel_delivery_manifest_ready"
        and _status(staging_packet) == "owner_staging_packet_ready"
        and _status(task_board) == "commercial_delivery_ready_for_owner_staging_review"
        and _status(control_modes_preservation) == "control_modes_preservation_ready"
    )
    stage_ready = strict_stage_ready or post_stage_chain_accounted_for or pre_approval_bootstrap_accounted_for
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = (
        staging_packet.get("owner_gated") is True
        and staging_runbook.get("owner_gated") is True
        and pre_stage_gate.get("owner_gated") is True
        and (approval_request_missing or approval_request.get("owner_gated") is True)
        and (
            approval_payload_audit_missing
            or approval_payload_audit.get("owner_gated") is True
            or approval_payload_audit_blocked_by_delivery_bootstrap
        )
        and (stage_execution_missing or stage_execution_plan.get("owner_gated") is True)
        and (rollback_plan_missing or rollback_plan.get("owner_gated") is True)
        and task_summary.get("secondary_pending_blocks_owner_staging") is False
    )

    checks = [
        _check(
            "reports_readable",
            not errors and not optional_errors,
            details={
                "errors": errors,
                "optional_errors": optional_errors,
                "optional_missing": optional_missing,
            },
            error="one or more owner delivery packet inputs are missing or unreadable",
        ),
        _check(
            "manifest_ready",
            _status(manifest) == "original_kernel_delivery_manifest_ready",
            details={"status": _status(manifest), "stage_include_count": stage_include_count},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "owner_pre_stage_chain_ready",
            stage_ready,
            details={
                "owner_staging_packet_status": _status(staging_packet),
                "owner_staging_runbook_status": _status(staging_runbook),
                "owner_pre_stage_gate_status": _status(pre_stage_gate),
                "task_board_status": _status(task_board),
                "control_modes_preservation_status": _status(control_modes_preservation),
                "strict_stage_ready": strict_stage_ready,
                "post_stage_chain_accounted_for": post_stage_chain_accounted_for,
                "pre_approval_bootstrap_accounted_for": pre_approval_bootstrap_accounted_for,
                "owner_post_stage_commit_gate_status": _status(commit_gate),
                "owner_commit_packet_status": _status(commit_packet),
                "owner_stage_approval_gate_status": _status(approval_gate),
                "owner_stage_execution_plan_status": _status(stage_execution_plan),
                "owner_staging_rollback_plan_status": _status(rollback_plan),
                "expected_nonzero_steps": expected_nonzero_steps,
                "refresh_delivery_bootstrap": refresh_delivery_bootstrap,
            },
            error="pre-stage owner delivery chain is not ready",
        ),
        _check(
            "stage_command_count_matches_manifest",
            stage_command_count_accounted_for,
            details={
                "owner_stage_command_count": owner_stage_command_count,
                "eligible_stage_count": eligible_stage_count,
                "staging_stage_include_count": staging_stage_include_count,
                "manifest_stage_include_count": stage_include_count,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner stage command count does not match eligible paths or manifest/review stage counts",
        ),
        _check(
            "stage_digests_present",
            isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64,
            details={
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner staging packet does not include stage path, command, and path-set digests",
        ),
        _check(
            "refresh_chain_ready",
            refresh_receipt_ok,
            details={
                "status": _status(refresh_chain),
                "step_count": refresh_summary.get("step_count"),
                "failed_step_count": refresh_summary.get("failed_step_count"),
                "failed_steps": _failed_step_names(refresh_chain),
                "expected_nonzero_steps": expected_nonzero_steps,
            },
            error="commercial delivery refresh chain is not ready or recoverable from a delivery-packet self-bootstrap state",
        ),
        _check(
            "post_stage_commit_packet_accounted_for",
            _status(commit_packet) in {"owner_commit_packet_ready", "owner_commit_packet_blocked"},
            details={
                "owner_post_stage_commit_gate_status": _status(commit_gate),
                "owner_commit_packet_status": _status(commit_packet),
                "commit_allowed": commit_packet.get("commit_allowed"),
            },
            error="owner commit packet is missing or in an unknown state",
        ),
        _check(
            "pre_stage_post_stage_blockers_are_expected",
            commit_ready or "owner_commit_packet" in expected_nonzero_steps or refresh_delivery_bootstrap,
            details={
                "commit_ready": commit_ready,
                "refresh_delivery_bootstrap": refresh_delivery_bootstrap,
                "expected_nonzero_steps": expected_nonzero_steps,
            },
            error="owner commit packet is blocked but not recorded as an expected pre-staging state",
        ),
        _check(
            "owner_stage_approval_gate_accounted_for",
            stage_approval_ready or stage_approval_expected_blocked,
            details={
                "owner_stage_approval_gate_status": _status(approval_gate),
                "stage_allowed": approval_gate.get("stage_allowed"),
            },
            error="owner stage approval gate is missing or in an unknown state",
        ),
        _check(
            "owner_stage_approval_request_accounted_for",
            approval_request_accounted_for,
            details={
                "owner_stage_approval_request_status": _status(approval_request),
                "owner_stage_approval_request_missing": approval_request_missing,
                "approval_request_blocked_by_delivery_bootstrap": approval_request_blocked_by_delivery_bootstrap,
                "approval_request_blocked_by_post_stage_commit": approval_request_blocked_by_post_stage_commit,
                "approval_request_post_commit_noop_accounted_for": approval_request_post_commit_noop_accounted_for,
            },
            error="owner stage approval request is present but not ready",
        ),
        _check(
            "owner_approval_payload_audit_accounted_for",
            approval_payload_audit_accounted_for,
            details={
                "owner_approval_payload_audit_status": _status(approval_payload_audit),
                "owner_approval_payload_audit_missing": approval_payload_audit_missing,
                "approval_payload_audit_blocked_by_delivery_bootstrap": (
                    approval_payload_audit_blocked_by_delivery_bootstrap
                ),
                "approval_payload_audit_blocked_by_post_stage_commit": (
                    approval_payload_audit_blocked_by_post_stage_commit
                ),
                "approval_payload_audit_post_commit_noop_accounted_for": (
                    approval_payload_audit_post_commit_noop_accounted_for
                ),
                "failed_checks": sorted(approval_payload_audit_failed_checks),
            },
            error="owner approval payload audit is present but not ready or accounted for",
        ),
        _check(
            "owner_stage_execution_plan_accounted_for",
            stage_execution_accounted_for,
            details={
                "owner_stage_execution_plan_status": _status(stage_execution_plan),
                "stage_allowed": stage_execution_plan.get("stage_allowed"),
                "owner_stage_execution_plan_missing": stage_execution_missing,
            },
            error=(
                "owner stage execution plan is present but neither ready nor in the expected "
                "pre-approval blocked state"
            ),
        ),
        _check(
            "owner_staging_rollback_plan_accounted_for",
            rollback_plan_accounted_for,
            details={
                "owner_staging_rollback_plan_status": _status(rollback_plan),
                "rollback_available": rollback_plan.get("rollback_available"),
                "owner_staging_rollback_plan_missing": rollback_plan_missing,
                "rollback_plan_post_commit_noop_accounted_for": rollback_plan_post_commit_noop_accounted_for,
            },
            error="owner staging rollback plan is present but not ready",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "owner_staging_packet_owner_gated": staging_packet.get("owner_gated"),
                "owner_staging_runbook_owner_gated": staging_runbook.get("owner_gated"),
                "owner_pre_stage_gate_owner_gated": pre_stage_gate.get("owner_gated"),
                "owner_stage_approval_request_owner_gated": approval_request.get("owner_gated"),
                "owner_approval_payload_audit_owner_gated": approval_payload_audit.get("owner_gated"),
                "owner_stage_execution_plan_owner_gated": stage_execution_plan.get("owner_gated"),
                "owner_staging_rollback_plan_owner_gated": rollback_plan.get("owner_gated"),
                "owner_stage_approval_request_missing": approval_request_missing,
                "owner_approval_payload_audit_missing": approval_payload_audit_missing,
                "approval_payload_audit_blocked_by_delivery_bootstrap": (
                    approval_payload_audit_blocked_by_delivery_bootstrap
                ),
                "owner_stage_execution_plan_missing": stage_execution_missing,
                "owner_staging_rollback_plan_missing": rollback_plan_missing,
                "secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
            },
            error="one or more owner gate markers are missing",
        ),
        _check(
            "secondary_pending_does_not_block_owner_review",
            task_summary.get("secondary_pending_blocks_owner_staging") is False,
            details={
                "secondary_pending_count": task_summary.get("secondary_pending_count"),
                "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
                "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
                "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
                "secondary_handoff_latest_completed_candidate": task_summary.get(
                    "secondary_handoff_latest_completed_candidate"
                ),
                "secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
            },
            error="secondary pending candidates are blocking owner review",
        ),
        _check(
            "control_modes_preservation_ready",
            _status(control_modes_preservation) == "control_modes_preservation_ready"
            and control_modes_summary.get("plan_only_default") is True
            and control_modes_summary.get("loop_phases") == ["explore", "plan", "edit", "verify", "deliver"],
            details={
                "control_modes_preservation_status": _status(control_modes_preservation),
                "plan_only_default": control_modes_summary.get("plan_only_default"),
                "loop_phases": control_modes_summary.get("loop_phases"),
                "control_surface_file_count": control_modes_summary.get("control_surface_file_count"),
            },
            error="control mode preservation evidence is missing or no longer preserves plan-only defaults",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more owner delivery packet inputs claim full Codex parity",
        ),
        _check(
            "no_delivery_packet_mutation",
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
    status = "owner_delivery_packet_ready" if ready else "owner_delivery_packet_blocked"

    sections = [
        OwnerDeliveryPacketSection(
            name="pre_stage_verification",
            title="Pre-stage verification",
            commands=pre_stage_commands,
            notes=[
                "Run these immediately before owner-approved staging.",
                "Stop if the cached index is not empty or any report becomes blocked.",
            ],
        ),
        OwnerDeliveryPacketSection(
            name="owner_stage_commands",
            title="Owner-approved stage commands",
            commands=stage_commands,
            notes=[
                "Run only these exact git add commands after explicit owner approval.",
                "Never replace these with git add ., git add -A, or git add --all.",
            ],
        ),
        OwnerDeliveryPacketSection(
            name="post_stage_verification",
            title="Post-stage verification",
            commands=post_stage_commands,
            notes=[
                "Run these after staging and before commit.",
                "Commit only if the owner commit packet becomes owner_commit_packet_ready.",
            ],
        ),
        OwnerDeliveryPacketSection(
            name="commit_preview",
            title="Commit preview",
            commands=[str(commit_preview or "")],
            notes=["Run only after post-stage gates are ready and the owner approves the staged diff."],
        ),
    ]

    return OwnerDeliveryPacket(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_delivery_packet",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        stage_ready=stage_ready,
        commit_ready=commit_ready,
        owner_approval_required=True,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "stage_include_count": stage_include_count,
            "eligible_stage_count": eligible_stage_count,
            "owner_stage_command_count": owner_stage_command_count,
            "pre_stage_verification_command_count": len(pre_stage_commands),
            "post_stage_verification_command_count": len(post_stage_commands),
            "refresh_chain_step_count": refresh_summary.get("step_count"),
            "expected_nonzero_steps": expected_nonzero_steps,
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "control_modes_preservation_status": _status(control_modes_preservation),
            "control_modes_plan_only_default": control_modes_summary.get("plan_only_default"),
            "control_modes_loop_phases": control_modes_summary.get("loop_phases"),
            "control_modes_surface_file_count": control_modes_summary.get("control_surface_file_count"),
            "owner_staging_runbook_status": _status(staging_runbook),
            "owner_pre_stage_gate_status": _status(pre_stage_gate),
            "owner_commit_packet_status": _status(commit_packet),
            "owner_stage_approval_gate_status": _status(approval_gate),
            "owner_stage_approval_request_status": _status(approval_request),
            "owner_approval_payload_audit_status": _status(approval_payload_audit),
            "approval_payload_audit_blocked_by_delivery_bootstrap": (
                approval_payload_audit_blocked_by_delivery_bootstrap
            ),
            "approval_payload_audit_blocked_by_post_stage_commit": (
                approval_payload_audit_blocked_by_post_stage_commit
            ),
            "approval_payload_audit_post_commit_noop_accounted_for": (
                approval_payload_audit_post_commit_noop_accounted_for
            ),
            "owner_stage_execution_plan_status": _status(stage_execution_plan),
            "owner_staging_rollback_plan_status": _status(rollback_plan),
            "owner_post_stage_commit_gate_status": _status(commit_gate),
            "commit_allowed": commit_packet.get("commit_allowed"),
            "stage_allowed": approval_gate.get("stage_allowed"),
            "owner_stage_execution_allowed": stage_execution_plan.get("stage_allowed"),
            "owner_stage_execution_stage_command_count": stage_execution_plan.get("stage_command_count"),
            "rollback_available": rollback_plan.get("rollback_available"),
            "rollback_required": rollback_plan.get("rollback_required"),
            "rollback_reset_command_count": rollback_plan.get("reset_command_count"),
            "strict_stage_ready": strict_stage_ready,
            "post_stage_chain_accounted_for": post_stage_chain_accounted_for,
            "post_commit_owner_gate_accounted_for": post_commit_owner_gate_accounted_for,
            "post_commit_stage_approval_accounted_for": post_commit_stage_approval_accounted_for,
            "post_commit_stage_execution_accounted_for": post_commit_stage_execution_accounted_for,
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "pre_approval_bootstrap_accounted_for": pre_approval_bootstrap_accounted_for,
            "refresh_delivery_bootstrap": refresh_delivery_bootstrap,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "owner_stage_approval_request_missing": approval_request_missing,
            "owner_approval_payload_audit_missing": approval_payload_audit_missing,
            "owner_stage_execution_plan_missing": stage_execution_missing,
            "owner_staging_rollback_plan_missing": rollback_plan_missing,
            "commit_command_preview": commit_preview,
        },
        sections=sections,
        checks=checks,
        next_actions=[
            "Review this owner delivery packet before any git staging.",
            "Run pre-stage verification immediately before owner-approved staging.",
            "Require owner_stage_approval_ready before executing any stage command.",
            "Run only the explicit stage commands after owner approval.",
            "After staging, regenerate post-stage verifier, commit gate, commit packet, delivery packet, and task board.",
            "Commit only after the owner commit packet reports owner_commit_packet_ready.",
        ],
        known_limits=[
            "This packet is read-only except writing local evidence files.",
            "It does not stage, reset, commit, push, run tests, call network services, or execute agents.",
            "It does not claim full Codex parity.",
            "It does not replace human owner review of the staged diff.",
        ],
    )


def render_markdown_packet(packet: OwnerDeliveryPacket) -> str:
    lines = [
        "# Commercial Delivery Owner Delivery Packet",
        "",
        f"- Status: `{packet.status}`",
        f"- Generated at: `{packet.generated_at}`",
        f"- Stage ready: `{str(packet.stage_ready).lower()}`",
        f"- Commit ready: `{str(packet.commit_ready).lower()}`",
        f"- Owner approval required: `{str(packet.owner_approval_required).lower()}`",
        f"- Stage include count: `{packet.summary.get('stage_include_count')}`",
        f"- Owner stage command count: `{packet.summary.get('owner_stage_command_count')}`",
        f"- Owner commit packet status: `{packet.summary.get('owner_commit_packet_status')}`",
        f"- Owner stage approval request status: `{packet.summary.get('owner_stage_approval_request_status')}`",
        f"- Owner stage execution plan status: `{packet.summary.get('owner_stage_execution_plan_status')}`",
        f"- Owner staging rollback plan status: `{packet.summary.get('owner_staging_rollback_plan_status')}`",
        f"- Secondary handoff next queue: `{', '.join(packet.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{packet.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{packet.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Control modes preservation: `{packet.summary.get('control_modes_preservation_status')}`",
        f"- Control modes plan-only default: `{packet.summary.get('control_modes_plan_only_default')}`",
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
        lines.extend(f"- `{command}`" for command in section.commands if command)
        if section.notes:
            lines.append("")
            lines.extend(f"- {note}" for note in section.notes)
    lines.append("")
    return "\n".join(lines)


def write_report(packet: OwnerDeliveryPacket, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_packet(packet: OwnerDeliveryPacket, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_packet(packet), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--owner-staging-packet", type=Path, default=DEFAULT_OWNER_STAGING_PACKET)
    parser.add_argument("--owner-staging-runbook", type=Path, default=DEFAULT_OWNER_STAGING_RUNBOOK)
    parser.add_argument("--owner-pre-stage-gate", type=Path, default=DEFAULT_OWNER_PRE_STAGE_GATE)
    parser.add_argument("--owner-post-stage-commit-gate", type=Path, default=DEFAULT_OWNER_POST_STAGE_COMMIT_GATE)
    parser.add_argument("--owner-commit-packet", type=Path, default=DEFAULT_OWNER_COMMIT_PACKET)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-approval-request", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_REQUEST)
    parser.add_argument("--owner-approval-payload-audit", type=Path, default=DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
    parser.add_argument("--owner-staging-rollback-plan", type=Path, default=DEFAULT_OWNER_STAGING_ROLLBACK_PLAN)
    parser.add_argument("--refresh-chain", type=Path, default=DEFAULT_REFRESH_CHAIN)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--control-modes-preservation", type=Path, default=DEFAULT_CONTROL_MODES_PRESERVATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_owner_delivery_packet(
        manifest_path=args.manifest,
        owner_staging_packet_path=args.owner_staging_packet,
        owner_staging_runbook_path=args.owner_staging_runbook,
        owner_pre_stage_gate_path=args.owner_pre_stage_gate,
        owner_post_stage_commit_gate_path=args.owner_post_stage_commit_gate,
        owner_commit_packet_path=args.owner_commit_packet,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_approval_request_path=args.owner_stage_approval_request,
        owner_approval_payload_audit_path=args.owner_approval_payload_audit,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        owner_staging_rollback_plan_path=args.owner_staging_rollback_plan,
        refresh_chain_path=args.refresh_chain,
        task_board_path=args.task_board,
        control_modes_preservation_path=args.control_modes_preservation,
    )
    write_report(packet, args.output)
    write_markdown_packet(packet, args.markdown_output)
    print(f"Commercial delivery owner delivery packet status: {packet.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage ready: {packet.stage_ready}")
    print(f"Commit ready: {packet.commit_ready}")
    for check in packet.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if packet.status == "owner_delivery_packet_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
