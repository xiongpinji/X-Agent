#!/usr/bin/env python3
"""Build a read-only commercial delivery closure snapshot.

The snapshot consolidates the current owner-gated delivery state into one
evidence artifact. It does not mark delivery complete unless the owner approval,
stage execution, post-stage, and commit gates are ready. It never stages files,
creates commits, pushes, calls network services, executes tests, or runs agents.
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
DEFAULT_OWNER_DELIVERY_PACKET = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_OWNER_STAGE_APPROVAL_BRIEF = REPORT_DIR / "commercial-delivery-owner-stage-approval-brief.json"
DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_OWNER_STAGING_ROLLBACK_PLAN = REPORT_DIR / "commercial-delivery-owner-staging-rollback-plan.json"
DEFAULT_OWNER_POST_STAGING_VERIFIER = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_OWNER_POST_STAGE_COMMIT_GATE = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_OWNER_COMMIT_PACKET = REPORT_DIR / "commercial-delivery-owner-commit-packet.json"
DEFAULT_REFRESH_CHAIN = REPORT_DIR / "commercial-delivery-refresh-chain-receipt.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_PRE_APPROVAL_DRIFT_GUARD = REPORT_DIR / "commercial-delivery-pre-approval-drift-guard.json"
DEFAULT_OWNER_APPROVAL_RESUME_PACKET = REPORT_DIR / "commercial-delivery-owner-approval-resume-packet.json"
DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST = (
    REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.json"
)
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-closure-snapshot.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-closure-snapshot.md"


@dataclass(frozen=True)
class CommercialDeliveryClosureCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CommercialDeliveryClosureSnapshot:
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
    delivery_complete: bool
    stage_ready: bool
    approval_ready: bool
    stage_execution_ready: bool
    post_stage_ready: bool
    commit_ready: bool
    rollback_ready: bool
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[CommercialDeliveryClosureCheck]
    blockers: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["checks_count"] = len(self.checks)
        payload["blockers_count"] = len(self.blockers)
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


def _read_report_status_value(payload: dict[str, Any], key: str) -> object:
    report_statuses = payload.get("report_statuses")
    if isinstance(report_statuses, dict):
        return report_statuses.get(key)
    return None


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    summary = _summary(payload)
    value = summary.get(field)
    return str(value) if isinstance(value, str) and value else None


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
    failed: set[str] = set()
    for check in checks:
        if isinstance(check, dict) and check.get("status") == "failed" and check.get("name") is not None:
            failed.add(str(check.get("name")))
    return failed


REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS = {
    "task_board_before_owner_decision",
    "owner_decision_brief",
    "owner_pre_stage_readiness_gate",
    "owner_delivery_packet_before_owner_approval",
    "owner_delivery_packet",
    "owner_stage_approval_brief",
    "closure_snapshot",
    "owner_approval_handoff",
}


def _refresh_receipt_ready_or_bootstrap(refresh_chain: dict[str, Any]) -> bool:
    refresh_summary = _summary(refresh_chain)
    if _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_ready":
        return True
    failed_steps = _failed_step_names(refresh_chain)
    return (
        _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_blocked"
        and int(refresh_summary.get("failed_step_count") or 0) == 1
        and len(failed_steps) == 1
        and failed_steps[0] in REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS
    )


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> CommercialDeliveryClosureCheck:
    return CommercialDeliveryClosureCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _blocked(label: str, condition: bool) -> list[str]:
    return [] if condition else [label]


def _blocking_reasons(payload: dict[str, Any]) -> list[str]:
    reasons = _summary(payload).get("blocking_reasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons if str(reason).strip()]


def _pre_approval_drift_guard_accounted_for(pre_approval_drift_guard: dict[str, Any]) -> bool:
    if _status(pre_approval_drift_guard) == "pre_approval_drift_guard_ready":
        return True
    guard_summary = _summary(pre_approval_drift_guard)
    core_failed_checks = {
        "real_owner_approval_absent",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "approval_gate_blocked_before_owner",
        "stage_execution_blocked_before_owner",
        "closure_blocked_before_owner",
    }
    allowed_failed_checks = core_failed_checks | {
        "operator_checklist_waiting_before_owner",
        "secondary_handoff_summary_stable",
    }
    failed_checks = _failed_check_names(pre_approval_drift_guard)
    post_approval_ready = (
        _status(pre_approval_drift_guard) == "pre_approval_drift_guard_blocked"
        and pre_approval_drift_guard.get("real_owner_approval_present") is True
        and pre_approval_drift_guard.get("mutation_performed") is not True
        and pre_approval_drift_guard.get("git_stage_performed") is not True
        and pre_approval_drift_guard.get("git_commit_performed") is not True
        and pre_approval_drift_guard.get("git_push_performed") is not True
        and pre_approval_drift_guard.get("network_mutation_performed") is not True
        and pre_approval_drift_guard.get("agent_execution_enabled") is not True
        and pre_approval_drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(pre_approval_drift_guard, "owner_approval_payload_audit")
        == "owner_approval_payload_ready"
        and guard_summary.get("owner_approval_payload_present") is True
        and guard_summary.get("owner_approval_payload_valid") is True
        and guard_summary.get("owner_approval_payload_ready_for_gate") is True
        and _read_report_status_value(pre_approval_drift_guard, "owner_stage_approval_gate")
        == "owner_stage_approval_ready"
        and guard_summary.get("owner_stage_approval_gate_status") == "owner_stage_approval_ready"
        and _read_report_status_value(pre_approval_drift_guard, "owner_stage_execution_plan")
        == "owner_stage_execution_ready"
        and guard_summary.get("owner_stage_execution_plan_status") == "owner_stage_execution_ready"
        and _read_report_status_value(pre_approval_drift_guard, "closure_snapshot") == "commercial_delivery_complete"
        and guard_summary.get("closure_snapshot_status") == "commercial_delivery_complete"
        and guard_summary.get("closure_delivery_complete") is True
        and core_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(allowed_failed_checks)
    )
    post_commit_required_failed_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    post_commit_allowed_failed_checks = post_commit_required_failed_checks | {"secondary_handoff_summary_stable"}
    stage_path_digest = guard_summary.get("stage_path_digest")
    stage_command_digest = guard_summary.get("stage_command_digest")
    expected_stage_path_set_digest = guard_summary.get("expected_stage_path_set_digest")
    operator_checklist_accounted_for = (
        _read_report_status_value(pre_approval_drift_guard, "owner_post_approval_operator_checklist")
        == "owner_post_approval_operator_checklist_ready"
        and guard_summary.get("owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and guard_summary.get("owner_post_approval_operator_checklist_operator_ready") is True
        and guard_summary.get("owner_post_approval_operator_checklist_real_owner_approval_present") is True
    ) or (
        _read_report_status_value(pre_approval_drift_guard, "owner_post_approval_operator_checklist")
        == "owner_post_approval_operator_checklist_blocked"
        and guard_summary.get("owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and guard_summary.get("owner_post_approval_operator_checklist_waiting_for_owner") is False
        and guard_summary.get("owner_post_approval_operator_checklist_operator_ready") is False
        and guard_summary.get("owner_post_approval_operator_checklist_real_owner_approval_present") is True
    )
    post_commit_blocked = (
        _status(pre_approval_drift_guard) == "pre_approval_drift_guard_blocked"
        and pre_approval_drift_guard.get("real_owner_approval_present") is True
        and pre_approval_drift_guard.get("mutation_performed") is not True
        and pre_approval_drift_guard.get("git_stage_performed") is not True
        and pre_approval_drift_guard.get("git_commit_performed") is not True
        and pre_approval_drift_guard.get("git_push_performed") is not True
        and pre_approval_drift_guard.get("network_mutation_performed") is not True
        and pre_approval_drift_guard.get("agent_execution_enabled") is not True
        and pre_approval_drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(pre_approval_drift_guard, "owner_stage_approval_request")
        == "owner_stage_approval_request_blocked"
        and _read_report_status_value(pre_approval_drift_guard, "owner_approval_handoff")
        == "owner_approval_handoff_blocked"
        and _read_report_status_value(pre_approval_drift_guard, "owner_approval_payload_audit")
        == "owner_approval_payload_blocked"
        and guard_summary.get("owner_approval_payload_present") is True
        and guard_summary.get("owner_approval_payload_valid") is False
        and guard_summary.get("owner_approval_payload_ready_for_gate") is False
        and _read_report_status_value(pre_approval_drift_guard, "owner_stage_approval_gate")
        == "owner_stage_approval_blocked"
        and guard_summary.get("owner_stage_approval_gate_status") == "owner_stage_approval_blocked"
        and _read_report_status_value(pre_approval_drift_guard, "owner_stage_execution_plan")
        == "owner_stage_execution_blocked"
        and guard_summary.get("owner_stage_execution_plan_status") == "owner_stage_execution_blocked"
        and operator_checklist_accounted_for
        and _read_report_status_value(pre_approval_drift_guard, "closure_snapshot")
        == "commercial_delivery_closure_blocked"
        and guard_summary.get("closure_snapshot_status") == "commercial_delivery_closure_blocked"
        and guard_summary.get("closure_delivery_complete") is False
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and post_commit_required_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(post_commit_allowed_failed_checks)
    )
    return post_approval_ready or post_commit_blocked


def build_commercial_delivery_closure_snapshot(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    owner_stage_approval_brief_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_BRIEF,
    owner_approval_payload_audit_path: Path = DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    owner_staging_rollback_plan_path: Path = DEFAULT_OWNER_STAGING_ROLLBACK_PLAN,
    owner_post_staging_verifier_path: Path = DEFAULT_OWNER_POST_STAGING_VERIFIER,
    owner_post_stage_commit_gate_path: Path = DEFAULT_OWNER_POST_STAGE_COMMIT_GATE,
    owner_commit_packet_path: Path = DEFAULT_OWNER_COMMIT_PACKET,
    refresh_chain_path: Path = DEFAULT_REFRESH_CHAIN,
    task_board_path: Path = DEFAULT_TASK_BOARD,
    pre_approval_drift_guard_path: Path = DEFAULT_PRE_APPROVAL_DRIFT_GUARD,
    owner_approval_resume_packet_path: Path = DEFAULT_OWNER_APPROVAL_RESUME_PACKET,
    owner_post_approval_operator_checklist_path: Path = DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
) -> CommercialDeliveryClosureSnapshot:
    report_paths = {
        "manifest": manifest_path,
        "owner_delivery_packet": owner_delivery_packet_path,
        "owner_stage_approval_brief": owner_stage_approval_brief_path,
        "owner_approval_payload_audit": owner_approval_payload_audit_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
        "owner_staging_rollback_plan": owner_staging_rollback_plan_path,
        "owner_post_staging_verifier": owner_post_staging_verifier_path,
        "owner_post_stage_commit_gate": owner_post_stage_commit_gate_path,
        "owner_commit_packet": owner_commit_packet_path,
        "refresh_chain": refresh_chain_path,
        "task_board": task_board_path,
        "pre_approval_drift_guard": pre_approval_drift_guard_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error
    owner_approval_resume_packet, owner_approval_resume_packet_error = _read_json(owner_approval_resume_packet_path)
    owner_post_approval_operator_checklist, owner_post_approval_operator_checklist_error = _read_json(
        owner_post_approval_operator_checklist_path
    )

    manifest = reports["manifest"]
    delivery_packet = reports["owner_delivery_packet"]
    approval_brief = reports["owner_stage_approval_brief"]
    approval_payload_audit = reports["owner_approval_payload_audit"]
    approval_gate = reports["owner_stage_approval_gate"]
    execution_plan = reports["owner_stage_execution_plan"]
    rollback_plan = reports["owner_staging_rollback_plan"]
    post_staging = reports["owner_post_staging_verifier"]
    commit_gate = reports["owner_post_stage_commit_gate"]
    commit_packet = reports["owner_commit_packet"]
    refresh_chain = reports["refresh_chain"]
    task_board = reports["task_board"]
    pre_approval_drift_guard = reports["pre_approval_drift_guard"]
    delivery_summary = _summary(delivery_packet)
    approval_brief_summary = _summary(approval_brief)
    task_summary = _summary(task_board)
    stage_path_digest_sources = {
        "owner_delivery_packet": _digest_field(delivery_packet, "stage_path_digest"),
        "owner_stage_approval_brief": _digest_field(approval_brief, "stage_path_digest"),
        "owner_stage_approval_gate": _digest_field(approval_gate, "stage_path_digest"),
        "owner_stage_execution_plan": _digest_field(execution_plan, "stage_path_digest"),
        "owner_post_staging_verifier": _digest_field(post_staging, "stage_path_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "stage_path_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "stage_path_digest"),
    }
    stage_command_digest_sources = {
        "owner_delivery_packet": _digest_field(delivery_packet, "stage_command_digest"),
        "owner_stage_approval_brief": _digest_field(approval_brief, "stage_command_digest"),
        "owner_stage_approval_gate": _digest_field(approval_gate, "stage_command_digest"),
        "owner_stage_execution_plan": _digest_field(execution_plan, "stage_command_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "stage_command_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "stage_command_digest"),
    }
    expected_stage_path_set_digest_sources = {
        "owner_post_staging_verifier": _digest_field(post_staging, "expected_stage_path_set_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "expected_stage_path_set_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "expected_stage_path_set_digest"),
    }
    cached_staged_path_set_digest_sources = {
        "owner_post_staging_verifier": _digest_field(post_staging, "cached_staged_path_set_digest"),
        "owner_post_stage_commit_gate": _digest_field(commit_gate, "cached_staged_path_set_digest"),
        "owner_commit_packet": _digest_field(commit_packet, "cached_staged_path_set_digest"),
    }

    def _sources_match(sources: dict[str, str | None]) -> bool:
        values = list(sources.values())
        return all(values) and len(set(values)) == 1

    stage_path_digest_consistent = _sources_match(stage_path_digest_sources)
    stage_command_digest_consistent = _sources_match(stage_command_digest_sources)
    expected_stage_path_set_digest_consistent = _sources_match(expected_stage_path_set_digest_sources)
    cached_staged_path_set_digest_consistent = _sources_match(cached_staged_path_set_digest_sources)

    stage_ready = (
        _status(manifest) == "original_kernel_delivery_manifest_ready"
        and _status(delivery_packet) == "owner_delivery_packet_ready"
        and delivery_packet.get("stage_ready") is True
    )
    approval_ready = _status(approval_gate) == "owner_stage_approval_ready" and approval_gate.get("stage_allowed") is True
    stage_execution_ready = (
        _status(execution_plan) == "owner_stage_execution_ready"
        and execution_plan.get("stage_allowed") is True
    )
    post_stage_ready = _status(post_staging) == "owner_post_staging_verification_ready"
    commit_ready = (
        _status(commit_gate) == "owner_post_stage_commit_gate_ready"
        and _status(commit_packet) == "owner_commit_packet_ready"
        and commit_packet.get("commit_allowed") is True
    )
    rollback_ready = _status(rollback_plan) == "owner_staging_rollback_plan_ready"
    refresh_ready = _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_ready"
    refresh_ready_for_snapshot = _refresh_receipt_ready_or_bootstrap(refresh_chain)
    task_board_ready = _status(task_board) == "commercial_delivery_ready_for_owner_staging_review"
    pre_approval_drift_guard_ready = _status(pre_approval_drift_guard) == "pre_approval_drift_guard_ready"
    pre_approval_drift_guard_accounted_for = _pre_approval_drift_guard_accounted_for(pre_approval_drift_guard)
    owner_approval_resume_packet_post_stage_accounted_for = (
        _status(owner_approval_resume_packet) == "owner_approval_resume_packet_blocked"
        and owner_approval_resume_packet.get("real_owner_approval_present") is True
        and owner_approval_resume_packet.get("waiting_for_owner") is not True
        and owner_approval_resume_packet.get("resume_ready") is not True
        and _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_blocked"
        and _failed_step_names(refresh_chain) == ["closure_snapshot"]
        and stage_ready
        and approval_ready
        and stage_execution_ready
        and post_stage_ready
        and commit_ready
        and rollback_ready
        and task_board_ready
        and pre_approval_drift_guard_accounted_for
    )
    owner_approval_resume_packet_accounted_for = (
        owner_approval_resume_packet_error is not None
        or _status(owner_approval_resume_packet)
        in {
            "owner_approval_resume_packet_waiting_for_owner",
            "owner_approval_resume_packet_ready",
        }
        or owner_approval_resume_packet_post_stage_accounted_for
    )
    owner_post_approval_operator_checklist_accounted_for = (
        owner_post_approval_operator_checklist_error is not None
        or _status(owner_post_approval_operator_checklist)
        in {
            "owner_post_approval_operator_checklist_waiting_for_owner",
            "owner_post_approval_operator_checklist_ready",
        }
    )
    owner_post_approval_operator_checklist_post_stage_accounted_for = (
        _status(owner_post_approval_operator_checklist) == "owner_post_approval_operator_checklist_blocked"
        and owner_post_approval_operator_checklist.get("real_owner_approval_present") is True
        and owner_post_approval_operator_checklist.get("waiting_for_owner") is not True
        and owner_post_approval_operator_checklist.get("operator_ready") is not True
        and _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_blocked"
        and tuple(_failed_step_names(refresh_chain))
        in {
            ("owner_pre_stage_readiness_gate",),
            ("closure_snapshot",),
            ("owner_approval_handoff",),
        }
        and stage_ready
        and approval_ready
        and stage_execution_ready
        and post_stage_ready
        and commit_ready
        and rollback_ready
        and task_board_ready
        and pre_approval_drift_guard_accounted_for
        and owner_approval_resume_packet_accounted_for
    )
    owner_post_approval_operator_checklist_accounted_for = (
        owner_post_approval_operator_checklist_accounted_for
        or owner_post_approval_operator_checklist_post_stage_accounted_for
    )
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = (
        delivery_packet.get("owner_gated") is True
        and approval_brief.get("owner_gated") is True
        and approval_gate.get("owner_gated") is True
        and execution_plan.get("owner_gated") is True
        and rollback_plan.get("owner_gated") is True
    )
    delivery_complete = all(
        [
            stage_ready,
            approval_ready,
            stage_execution_ready,
            post_stage_ready,
            commit_ready,
            rollback_ready,
            refresh_ready_for_snapshot,
            task_board_ready,
            pre_approval_drift_guard_accounted_for,
            owner_approval_resume_packet_accounted_for,
            owner_post_approval_operator_checklist_accounted_for,
        ]
    )
    blockers = (
        _blocked("owner_stage_approval_gate_not_ready", approval_ready)
        + _blocked("owner_stage_execution_plan_not_ready", stage_execution_ready)
        + _blocked("post_staging_verifier_not_ready", post_stage_ready)
        + _blocked("owner_commit_packet_not_ready", commit_ready)
        + _blocked("cached_staged_path_set_digest_not_ready", cached_staged_path_set_digest_consistent)
    )
    owner_blocking_reasons_by_report = {
        name: reasons
        for name, reasons in {
            "owner_stage_approval_gate": _blocking_reasons(approval_gate),
            "owner_approval_payload_audit": _blocking_reasons(approval_payload_audit),
            "owner_stage_execution_plan": _blocking_reasons(execution_plan),
            "owner_post_staging_verifier": _blocking_reasons(post_staging),
            "owner_post_stage_commit_gate": _blocking_reasons(commit_gate),
            "owner_commit_packet": _blocking_reasons(commit_packet),
        }.items()
        if reasons
    }
    owner_blocking_reason_count = sum(len(reasons) for reasons in owner_blocking_reasons_by_report.values())

    checks = [
        _check("reports_readable", not errors, details={"errors": errors}, error="closure snapshot inputs are missing or unreadable"),
        _check(
            "stage_ready",
            stage_ready,
            details={"manifest_status": _status(manifest), "owner_delivery_packet_status": _status(delivery_packet)},
            error="pre-stage delivery packet is not ready",
        ),
        _check(
            "owner_approval_ready",
            approval_ready,
            details={"owner_stage_approval_gate_status": _status(approval_gate), "stage_allowed": approval_gate.get("stage_allowed")},
            error="explicit owner approval is not ready",
        ),
        _check(
            "stage_execution_ready",
            stage_execution_ready,
            details={"owner_stage_execution_plan_status": _status(execution_plan), "stage_allowed": execution_plan.get("stage_allowed")},
            error="owner stage execution plan is not ready",
        ),
        _check(
            "post_stage_ready",
            post_stage_ready,
            details={"owner_post_staging_verifier_status": _status(post_staging)},
            error="post-staging verifier is not ready",
        ),
        _check(
            "commit_ready",
            commit_ready,
            details={
                "owner_post_stage_commit_gate_status": _status(commit_gate),
                "owner_commit_packet_status": _status(commit_packet),
                "commit_allowed": commit_packet.get("commit_allowed"),
            },
            error="owner commit packet is not ready",
        ),
        _check(
            "rollback_plan_ready",
            rollback_ready,
            details={"owner_staging_rollback_plan_status": _status(rollback_plan)},
            error="owner staging rollback plan is not ready",
        ),
        _check(
            "refresh_chain_ready",
            refresh_ready_for_snapshot,
            details={
                "refresh_chain_status": _status(refresh_chain),
                "step_count": _summary(refresh_chain).get("step_count"),
                "failed_step_count": _summary(refresh_chain).get("failed_step_count"),
                "failed_steps": _failed_step_names(refresh_chain),
            },
            error="commercial delivery refresh chain is not ready",
        ),
        _check(
            "task_board_ready",
            task_board_ready,
            details={"task_board_status": _status(task_board)},
            error="commercial delivery task board is not ready",
        ),
        _check(
            "pre_approval_drift_guard_ready",
            pre_approval_drift_guard_accounted_for,
            details={
                "pre_approval_drift_guard_status": _status(pre_approval_drift_guard),
                "pre_approval_drift_guard_accounted_for": pre_approval_drift_guard_accounted_for,
                "real_owner_approval_present": pre_approval_drift_guard.get("real_owner_approval_present"),
                "stage_path_digest": _summary(pre_approval_drift_guard).get("stage_path_digest"),
                "stage_command_digest": _summary(pre_approval_drift_guard).get("stage_command_digest"),
            },
            error="commercial delivery pre-approval drift guard is not ready",
        ),
        _check(
            "owner_approval_resume_packet_accounted_for",
            owner_approval_resume_packet_accounted_for,
            details={
                "owner_approval_resume_packet_status": _status(owner_approval_resume_packet),
                "owner_approval_resume_packet_error": owner_approval_resume_packet_error,
                "waiting_for_owner": owner_approval_resume_packet.get("waiting_for_owner"),
                "resume_ready": owner_approval_resume_packet.get("resume_ready"),
                "real_owner_approval_present": owner_approval_resume_packet.get("real_owner_approval_present"),
                "post_stage_accounted_for": owner_approval_resume_packet_post_stage_accounted_for,
            },
            error="owner approval resume packet is present but neither waiting for owner nor ready",
        ),
        _check(
            "owner_post_approval_operator_checklist_accounted_for",
            owner_post_approval_operator_checklist_accounted_for,
            details={
                "owner_post_approval_operator_checklist_status": _status(owner_post_approval_operator_checklist),
                "owner_post_approval_operator_checklist_error": owner_post_approval_operator_checklist_error,
                "waiting_for_owner": owner_post_approval_operator_checklist.get("waiting_for_owner"),
                "operator_ready": owner_post_approval_operator_checklist.get("operator_ready"),
                "real_owner_approval_present": owner_post_approval_operator_checklist.get("real_owner_approval_present"),
                "post_stage_accounted_for": owner_post_approval_operator_checklist_post_stage_accounted_for,
            },
            error="owner post-approval operator checklist is present but neither waiting for owner nor ready",
        ),
        _check(
            "control_modes_preserved",
            delivery_summary.get("control_modes_preservation_status") == "control_modes_preservation_ready"
            and delivery_summary.get("control_modes_plan_only_default") is True
            and delivery_summary.get("control_modes_loop_phases") == ["explore", "plan", "edit", "verify", "deliver"]
            and approval_brief_summary.get("control_modes_preservation_status") == "control_modes_preservation_ready"
            and task_summary.get("control_modes_preservation_status") == "control_modes_preservation_ready",
            details={
                "delivery_control_modes_preservation_status": delivery_summary.get("control_modes_preservation_status"),
                "delivery_control_modes_plan_only_default": delivery_summary.get("control_modes_plan_only_default"),
                "delivery_control_modes_loop_phases": delivery_summary.get("control_modes_loop_phases"),
                "approval_brief_control_modes_preservation_status": approval_brief_summary.get(
                    "control_modes_preservation_status"
                ),
                "task_board_control_modes_preservation_status": task_summary.get("control_modes_preservation_status"),
            },
            error="control mode preservation evidence is missing from closure inputs",
        ),
        _check(
            "stage_counts_consistent",
            int(delivery_summary.get("stage_include_count") or 0) > 0
            and int(delivery_summary.get("owner_stage_command_count") or -1)
            == int(delivery_summary.get("owner_stage_execution_stage_command_count") or -2)
            == int(delivery_summary.get("rollback_reset_command_count") or -3)
            and int(delivery_summary.get("owner_stage_command_count") or 0)
            <= int(delivery_summary.get("stage_include_count") or -1),
            details={
                "stage_include_count": delivery_summary.get("stage_include_count"),
                "owner_stage_command_count": delivery_summary.get("owner_stage_command_count"),
                "owner_stage_execution_stage_command_count": delivery_summary.get("owner_stage_execution_stage_command_count"),
                "rollback_reset_command_count": delivery_summary.get("rollback_reset_command_count"),
            },
            error="owner delivery command counts are inconsistent or exceed stage include count",
        ),
        _check(
            "stage_path_digest_consistent",
            stage_path_digest_consistent,
            details={"stage_path_digest_sources": stage_path_digest_sources},
            error="stage path digest is missing or inconsistent across owner delivery evidence",
        ),
        _check(
            "stage_command_digest_consistent",
            stage_command_digest_consistent,
            details={"stage_command_digest_sources": stage_command_digest_sources},
            error="stage command digest is missing or inconsistent across owner delivery evidence",
        ),
        _check(
            "expected_stage_path_set_digest_consistent",
            expected_stage_path_set_digest_consistent,
            details={"expected_stage_path_set_digest_sources": expected_stage_path_set_digest_sources},
            error="expected stage path set digest is missing or inconsistent across post-stage evidence",
        ),
        _check(
            "cached_staged_path_set_digest_consistent",
            cached_staged_path_set_digest_consistent,
            details={"cached_staged_path_set_digest_sources": cached_staged_path_set_digest_sources},
            error="cached staged path set digest is missing or inconsistent across post-stage evidence",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more closure snapshot inputs claim full Codex parity",
        ),
        _check(
            "no_closure_snapshot_mutation",
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
    checks_passed = all(check.status == "passed" for check in checks)
    status = "commercial_delivery_complete" if delivery_complete and checks_passed else "commercial_delivery_closure_blocked"

    return CommercialDeliveryClosureSnapshot(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_closure_snapshot",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        delivery_complete=delivery_complete,
        stage_ready=stage_ready,
        approval_ready=approval_ready,
        stage_execution_ready=stage_execution_ready,
        post_stage_ready=post_stage_ready,
        commit_ready=commit_ready,
        rollback_ready=rollback_ready,
        reports={
            **{name: _display_path(path) for name, path in report_paths.items()},
            "owner_approval_resume_packet": _display_path(owner_approval_resume_packet_path),
            "owner_post_approval_operator_checklist": _display_path(owner_post_approval_operator_checklist_path),
        },
        report_statuses={
            **{name: _status(payload) for name, payload in reports.items()},
            "owner_approval_resume_packet": _status(owner_approval_resume_packet),
            "owner_post_approval_operator_checklist": _status(owner_post_approval_operator_checklist),
        },
        summary={
            "owner_action_required": bool(blockers or owner_blocking_reasons_by_report),
            "owner_blocking_reason_count": owner_blocking_reason_count,
            "owner_blocking_reasons_by_report": owner_blocking_reasons_by_report,
            "stage_include_count": delivery_summary.get("stage_include_count"),
            "owner_stage_command_count": delivery_summary.get("owner_stage_command_count"),
            "owner_stage_execution_stage_command_count": delivery_summary.get("owner_stage_execution_stage_command_count"),
            "rollback_reset_command_count": delivery_summary.get("rollback_reset_command_count"),
            "owner_approval_payload_audit_status": _status(approval_payload_audit),
            "owner_approval_payload_present": approval_payload_audit.get("approval_payload_present"),
            "owner_approval_payload_valid": approval_payload_audit.get("approval_payload_valid"),
            "owner_approval_payload_ready_for_gate": approval_payload_audit.get("ready_for_approval_gate"),
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
            "control_modes_surface_file_count": delivery_summary.get("control_modes_surface_file_count"),
            "approval_brief_control_modes_preservation_status": approval_brief_summary.get(
                "control_modes_preservation_status"
            ),
            "task_board_control_modes_preservation_status": task_summary.get("control_modes_preservation_status"),
            "pre_approval_drift_guard_status": _status(pre_approval_drift_guard),
            "pre_approval_drift_guard_accounted_for": pre_approval_drift_guard_accounted_for,
            "pre_approval_drift_guard_real_owner_approval_present": pre_approval_drift_guard.get(
                "real_owner_approval_present"
            ),
            "pre_approval_drift_guard_stage_path_digest": _summary(pre_approval_drift_guard).get("stage_path_digest"),
            "pre_approval_drift_guard_stage_command_digest": _summary(pre_approval_drift_guard).get(
                "stage_command_digest"
            ),
            "owner_approval_resume_packet_status": _status(owner_approval_resume_packet),
            "owner_approval_resume_packet_waiting_for_owner": owner_approval_resume_packet.get("waiting_for_owner"),
            "owner_approval_resume_packet_resume_ready": owner_approval_resume_packet.get("resume_ready"),
            "owner_approval_resume_packet_real_owner_approval_present": owner_approval_resume_packet.get(
                "real_owner_approval_present"
            ),
            "owner_approval_resume_packet_post_stage_accounted_for": owner_approval_resume_packet_post_stage_accounted_for,
            "owner_post_approval_operator_checklist_status": _status(owner_post_approval_operator_checklist),
            "owner_post_approval_operator_checklist_waiting_for_owner": owner_post_approval_operator_checklist.get(
                "waiting_for_owner"
            ),
            "owner_post_approval_operator_checklist_operator_ready": owner_post_approval_operator_checklist.get(
                "operator_ready"
            ),
            "owner_post_approval_operator_checklist_real_owner_approval_present": owner_post_approval_operator_checklist.get(
                "real_owner_approval_present"
            ),
            "owner_post_approval_operator_checklist_post_stage_accounted_for": (
                owner_post_approval_operator_checklist_post_stage_accounted_for
            ),
            "refresh_chain_raw_ready": refresh_ready,
            "refresh_chain_ready_for_snapshot": refresh_ready_for_snapshot,
            "refresh_chain_failed_steps": _failed_step_names(refresh_chain),
            "refresh_chain_step_count": _summary(refresh_chain).get("step_count"),
            "expected_nonzero_step_count": _summary(refresh_chain).get("expected_nonzero_step_count"),
            "stage_path_digest": next((value for value in stage_path_digest_sources.values() if value), None),
            "stage_command_digest": next((value for value in stage_command_digest_sources.values() if value), None),
            "expected_stage_path_set_digest": next(
                (value for value in expected_stage_path_set_digest_sources.values() if value),
                None,
            ),
            "cached_staged_path_set_digest": next(
                (value for value in cached_staged_path_set_digest_sources.values() if value),
                None,
            ),
        },
        checks=checks,
        blockers=blockers,
        next_actions=[
            "Do not stage until owner_stage_approval_gate and owner_stage_execution_plan are ready.",
            "After owner-approved staging, rerun post-staging verifier, commit gate, commit packet, delivery packet, and this snapshot.",
            "Use the owner approval resume packet as the sequence guide after real owner approval exists.",
            "Use the post-approval operator checklist as the executable status guide after owner approval exists.",
            "Use the rollback plan if staged paths need to be explicitly unstaged after a failed post-stage gate.",
            "Do not claim commercial delivery complete until this snapshot reports commercial_delivery_complete.",
        ],
        known_limits=[
            "This snapshot is read-only except writing local evidence files.",
            "It does not stage, reset, commit, push, call network services, run tests, or execute agents.",
            "It does not create owner approval evidence.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_snapshot(snapshot: CommercialDeliveryClosureSnapshot) -> str:
    lines = [
        "# Commercial Delivery Closure Snapshot",
        "",
        f"- Status: `{snapshot.status}`",
        f"- Generated at: `{snapshot.generated_at}`",
        f"- Delivery complete: `{str(snapshot.delivery_complete).lower()}`",
        f"- Stage ready: `{str(snapshot.stage_ready).lower()}`",
        f"- Approval ready: `{str(snapshot.approval_ready).lower()}`",
        f"- Stage execution ready: `{str(snapshot.stage_execution_ready).lower()}`",
        f"- Post-stage ready: `{str(snapshot.post_stage_ready).lower()}`",
        f"- Commit ready: `{str(snapshot.commit_ready).lower()}`",
        f"- Rollback ready: `{str(snapshot.rollback_ready).lower()}`",
        f"- Stage path digest: `{snapshot.summary.get('stage_path_digest') or '<missing>'}`",
        f"- Stage command digest: `{snapshot.summary.get('stage_command_digest') or '<missing>'}`",
        f"- Expected stage path set digest: `{snapshot.summary.get('expected_stage_path_set_digest') or '<missing>'}`",
        f"- Cached staged path set digest: `{snapshot.summary.get('cached_staged_path_set_digest') or '<missing>'}`",
        f"- Owner action required: `{str(snapshot.summary.get('owner_action_required')).lower()}`",
        f"- Owner blocking reason count: `{snapshot.summary.get('owner_blocking_reason_count')}`",
        f"- Secondary handoff completed count: `{snapshot.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{snapshot.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Secondary next queue: `{', '.join(snapshot.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Control modes preservation: `{snapshot.summary.get('control_modes_preservation_status')}`",
        f"- Control modes plan-only default: `{snapshot.summary.get('control_modes_plan_only_default')}`",
        "",
        "## Blockers",
        "",
    ]
    if snapshot.blockers:
        lines.extend(f"- `{blocker}`" for blocker in snapshot.blockers)
    else:
        lines.append("- None")
    lines.extend(["", "## Owner Blocking Reasons", ""])
    by_report = snapshot.summary.get("owner_blocking_reasons_by_report")
    if isinstance(by_report, dict) and by_report:
        for report_name, reasons in by_report.items():
            lines.append(f"- `{report_name}`: `{', '.join(str(reason) for reason in reasons)}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Checks", ""])
    for check in snapshot.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in snapshot.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(snapshot: CommercialDeliveryClosureSnapshot, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_snapshot(
    snapshot: CommercialDeliveryClosureSnapshot,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_snapshot(snapshot), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--owner-stage-approval-brief", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_BRIEF)
    parser.add_argument("--owner-approval-payload-audit", type=Path, default=DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
    parser.add_argument("--owner-staging-rollback-plan", type=Path, default=DEFAULT_OWNER_STAGING_ROLLBACK_PLAN)
    parser.add_argument("--owner-post-staging-verifier", type=Path, default=DEFAULT_OWNER_POST_STAGING_VERIFIER)
    parser.add_argument("--owner-post-stage-commit-gate", type=Path, default=DEFAULT_OWNER_POST_STAGE_COMMIT_GATE)
    parser.add_argument("--owner-commit-packet", type=Path, default=DEFAULT_OWNER_COMMIT_PACKET)
    parser.add_argument("--refresh-chain", type=Path, default=DEFAULT_REFRESH_CHAIN)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--pre-approval-drift-guard", type=Path, default=DEFAULT_PRE_APPROVAL_DRIFT_GUARD)
    parser.add_argument("--owner-approval-resume-packet", type=Path, default=DEFAULT_OWNER_APPROVAL_RESUME_PACKET)
    parser.add_argument(
        "--owner-post-approval-operator-checklist",
        type=Path,
        default=DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = build_commercial_delivery_closure_snapshot(
        manifest_path=args.manifest,
        owner_delivery_packet_path=args.owner_delivery_packet,
        owner_stage_approval_brief_path=args.owner_stage_approval_brief,
        owner_approval_payload_audit_path=args.owner_approval_payload_audit,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        owner_staging_rollback_plan_path=args.owner_staging_rollback_plan,
        owner_post_staging_verifier_path=args.owner_post_staging_verifier,
        owner_post_stage_commit_gate_path=args.owner_post_stage_commit_gate,
        owner_commit_packet_path=args.owner_commit_packet,
        refresh_chain_path=args.refresh_chain,
        task_board_path=args.task_board,
        pre_approval_drift_guard_path=args.pre_approval_drift_guard,
        owner_approval_resume_packet_path=args.owner_approval_resume_packet,
        owner_post_approval_operator_checklist_path=args.owner_post_approval_operator_checklist,
    )
    write_report(snapshot, args.output)
    write_markdown_snapshot(snapshot, args.markdown_output)
    print(f"Commercial delivery closure snapshot status: {snapshot.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Delivery complete: {snapshot.delivery_complete}")
    for check in snapshot.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if snapshot.status == "commercial_delivery_complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
