#!/usr/bin/env python3
"""Build the read-only commit gate after owner-approved staging.

This gate is intentionally post-stage only. It expects the owner to have run
the exact ``git add -- '<path>'`` commands from the owner staging packet and
then checks whether the staged path set is ready for an owner-approved commit.
It does not stage files, reset files, create commits, push, run agents, call
network services, or mutate release gates.
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
DEFAULT_OWNER_DECISION_BRIEF = REPORT_DIR / "commercial-delivery-owner-decision-brief.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.md"


@dataclass(frozen=True)
class OwnerPostStageCommitGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerPostStageCommitGate:
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
    expected_stage_paths: list[str]
    cached_staged_paths: list[str]
    expected_stage_path_set_digest: str | None
    cached_staged_path_set_digest: str | None
    stage_path_digest: str | None
    stage_command_digest: str | None
    command_path_set_digest: str | None
    owner_packet_stage_path_set_digest: str | None
    checks: list[OwnerPostStageCommitGateCheck]
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


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerPostStageCommitGateCheck:
    return OwnerPostStageCommitGateCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _failed_check_names(checks: list[OwnerPostStageCommitGateCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


def _failed_report_check_names(payload: dict[str, Any]) -> set[str]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return set()
    failed: set[str] = set()
    for check in checks:
        if isinstance(check, dict) and check.get("status") == "failed" and check.get("name") is not None:
            failed.add(str(check.get("name")))
    return failed


def _report_check_passed(payload: dict[str, Any], name: str) -> bool:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return False
    return any(
        isinstance(check, dict)
        and check.get("name") == name
        and check.get("status") == "passed"
        for check in checks
    )


def _decision_brief_ready_or_post_staging_accounted(
    payload: dict[str, Any],
    *,
    owner_post_staging: dict[str, Any] | None = None,
) -> bool:
    allowed_failed_checks = {
        "owner_preflight_ready",
        "owner_pre_stage_readiness_gate_ready",
        "owner_approval_boundary_accounted_for",
        "stage_commands_match_manifest",
        "post_staging_not_yet_applied",
        "owner_preflight_ready",
        "task_board_ready",
    }
    summary = _summary(payload)
    post_staging_status = summary.get("post_staging_status")
    cached_staged_path_count = _int_or_none(summary.get("cached_staged_path_count"))
    post_commit_noop_accounted_for = False
    if owner_post_staging:
        post_staging_status = post_staging_status or _status(owner_post_staging)
        if cached_staged_path_count is None:
            cached_staged_path_count = _int_or_none(owner_post_staging.get("cached_staged_path_count"))
        post_commit_noop_accounted_for = (
            owner_post_staging.get("post_commit_noop_accounted_for") is True
            or _summary(owner_post_staging).get("post_commit_noop_accounted_for") is True
        )
    return _status(payload) == "ready_for_owner_staging_decision" or (
        _status(payload) == "blocked_before_owner_staging_decision"
        and post_staging_status == "owner_post_staging_verification_ready"
        and cached_staged_path_count is not None
        and (cached_staged_path_count > 0 or post_commit_noop_accounted_for)
        and payload.get("mutation_performed") is not True
        and payload.get("git_stage_performed") is not True
        and payload.get("git_commit_performed") is not True
        and payload.get("git_push_performed") is not True
        and payload.get("network_mutation_performed") is not True
        and payload.get("agent_execution_enabled") is not True
        and payload.get("full_codex_parity_claimed") is not True
        and _failed_report_check_names(payload).issubset(allowed_failed_checks)
    )


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip('"')


def _path_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({_normalize_path(str(item)) for item in value if str(item).strip()})


def _digest_values(values: list[str]) -> str:
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


def _task_board_post_commit_noop_accounted_for(
    task_board: dict[str, Any],
    task_summary: dict[str, Any],
    *,
    post_commit_noop_accounted_for: bool,
) -> bool:
    return (
        post_commit_noop_accounted_for
        and _status(task_board) == "commercial_delivery_blocked"
        and task_summary.get("secondary_pending_blocks_owner_staging") is False
        and (
            task_summary.get("staging_review_status") == "staging_review_ready"
            or _report_check_passed(task_board, "staging_review_ready")
        )
        and task_summary.get("owner_staging_packet_status") == "owner_staging_packet_ready"
        and task_summary.get("owner_staging_preflight_accounted_for") is True
        and task_summary.get("owner_post_staging_verifier_status") == "owner_post_staging_verification_ready"
        and _int_or_none(task_summary.get("eligible_stage_count")) == 0
        and _int_or_none(task_summary.get("owner_stage_command_count")) == 0
        and _int_or_none(task_summary.get("post_staging_cached_path_count")) == 0
    )


def _task_board_post_staging_accounted_for(
    task_board: dict[str, Any],
    task_summary: dict[str, Any],
) -> bool:
    eligible_stage_count = _int_or_none(task_summary.get("eligible_stage_count"))
    owner_stage_command_count = _int_or_none(task_summary.get("owner_stage_command_count"))
    post_staging_cached_path_count = _int_or_none(task_summary.get("post_staging_cached_path_count"))
    task_board_failed_checks = _failed_report_check_names(task_board)
    return (
        _status(task_board) == "commercial_delivery_blocked"
        and bool(task_board_failed_checks)
        and task_board_failed_checks.issubset({"pre_approval_drift_guard_ready"})
        and task_summary.get("secondary_pending_blocks_owner_staging") is False
        and task_summary.get("owner_staging_preflight_accounted_for") is True
        and task_summary.get("owner_post_staging_verifier_status") == "owner_post_staging_verification_ready"
        and eligible_stage_count is not None
        and owner_stage_command_count is not None
        and post_staging_cached_path_count is not None
        and eligible_stage_count > 0
        and eligible_stage_count == owner_stage_command_count == post_staging_cached_path_count
    )


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return str(value) if isinstance(value, str) and value else None


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_owner_post_stage_commit_gate(
    *,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    owner_post_staging_path: Path = DEFAULT_OWNER_POST_STAGING,
    owner_command_audit_path: Path = DEFAULT_OWNER_COMMAND_AUDIT,
    owner_decision_brief_path: Path = DEFAULT_OWNER_DECISION_BRIEF,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerPostStageCommitGate:
    report_paths = {
        "owner_packet": owner_packet_path,
        "owner_post_staging": owner_post_staging_path,
        "owner_command_audit": owner_command_audit_path,
        "owner_decision_brief": owner_decision_brief_path,
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
    owner_decision_brief = reports["owner_decision_brief"]
    task_board = reports["task_board"]
    task_summary = _summary(task_board)

    packet_paths = _path_list(owner_packet.get("stage_paths"))
    cached_paths = _path_list(owner_post_staging.get("cached_staged_paths"))
    command_paths = _path_list(owner_command_audit.get("command_paths"))
    missing_cached_paths = _path_list(owner_post_staging.get("missing_cached_paths"))
    unexpected_cached_paths = _path_list(owner_post_staging.get("unexpected_cached_paths"))
    protected_cached_paths = _path_list(owner_post_staging.get("protected_cached_paths"))
    commit_command_preview = owner_packet.get("commit_command_preview")

    stage_counts = {
        "owner_packet_stage_include_count": _int_or_none(owner_packet.get("stage_include_count")),
        "owner_packet_stage_path_count": len(packet_paths),
        "owner_post_staging_expected_stage_path_count": _int_or_none(
            owner_post_staging.get("expected_stage_path_count")
        ),
        "owner_post_staging_cached_staged_path_count": _int_or_none(
            owner_post_staging.get("cached_staged_path_count")
        ),
        "owner_command_audit_command_count": _int_or_none(owner_command_audit.get("command_count")),
        "owner_command_audit_expected_path_count": _int_or_none(owner_command_audit.get("expected_path_count")),
    }
    actual_stage_counts = [
        stage_counts["owner_packet_stage_path_count"],
        stage_counts["owner_post_staging_expected_stage_path_count"],
        stage_counts["owner_post_staging_cached_staged_path_count"],
        stage_counts["owner_command_audit_command_count"],
        stage_counts["owner_command_audit_expected_path_count"],
    ]
    actual_stage_counts_present = all(value is not None for value in actual_stage_counts)
    actual_stage_count_values = [int(value) for value in actual_stage_counts if value is not None]
    actual_stage_count = actual_stage_count_values[0] if actual_stage_count_values else None
    stage_include_count = stage_counts["owner_packet_stage_include_count"]
    post_commit_noop_accounted_for = _post_commit_noop_accounted_for(
        owner_packet,
        owner_post_staging,
        owner_command_audit,
    )
    stage_counts_agree = (
        actual_stage_counts_present
        and bool(actual_stage_count_values)
        and len(set(actual_stage_count_values)) == 1
        and actual_stage_count is not None
        and (actual_stage_count > 0 or post_commit_noop_accounted_for)
        and stage_include_count is not None
        and actual_stage_count <= stage_include_count
    )
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = (
        owner_packet.get("owner_gated") is True
        and owner_post_staging.get("owner_gated") is True
        and owner_command_audit.get("owner_gated") is True
        and owner_decision_brief.get("owner_gated") is True
    )
    empty_digest = _digest_values([])
    cached_paths_match_packet = (bool(packet_paths) and packet_paths == cached_paths) or (
        post_commit_noop_accounted_for and not packet_paths and not cached_paths
    )
    command_paths_match_packet = (bool(command_paths) and command_paths == packet_paths) or (
        post_commit_noop_accounted_for and not command_paths and not packet_paths
    )
    expected_stage_path_set_digest = (
        empty_digest if post_commit_noop_accounted_for and not packet_paths else _path_set_digest(packet_paths)
    )
    cached_staged_path_set_digest = (
        empty_digest if post_commit_noop_accounted_for and not cached_paths else _path_set_digest(cached_paths)
    )
    command_path_set_digest = (
        empty_digest if post_commit_noop_accounted_for and not command_paths else _path_set_digest(command_paths)
    )
    owner_packet_stage_path_set_digest = (
        empty_digest if post_commit_noop_accounted_for and not packet_paths else _path_set_digest(packet_paths)
    )
    task_board_ready = _status(task_board) == "commercial_delivery_ready_for_owner_staging_review"
    task_board_post_commit_noop_accounted_for = _task_board_post_commit_noop_accounted_for(
        task_board,
        task_summary,
        post_commit_noop_accounted_for=post_commit_noop_accounted_for,
    )
    task_board_post_staging_accounted_for = _task_board_post_staging_accounted_for(task_board, task_summary)
    owner_packet_stage_path_digest = _digest_field(owner_packet, "stage_path_digest")
    owner_packet_stage_command_digest = _digest_field(owner_packet, "stage_command_digest")
    command_audit_path_digest = _digest_field(owner_command_audit, "command_path_digest")
    command_audit_expected_path_digest = _digest_field(owner_command_audit, "expected_path_digest")
    command_audit_command_digest = _digest_field(owner_command_audit, "command_digest")
    command_audit_owner_packet_path_digest = _digest_field(owner_command_audit, "owner_packet_stage_path_digest")
    command_audit_owner_packet_command_digest = _digest_field(
        owner_command_audit, "owner_packet_stage_command_digest"
    )
    verifier_expected_stage_path_set_digest = _digest_field(owner_post_staging, "expected_stage_path_set_digest")
    verifier_cached_staged_path_set_digest = _digest_field(owner_post_staging, "cached_staged_path_set_digest")
    path_set_digests_match = (
        expected_stage_path_set_digest is not None
        and cached_staged_path_set_digest == expected_stage_path_set_digest
        and command_path_set_digest == expected_stage_path_set_digest
        and owner_packet_stage_path_set_digest == expected_stage_path_set_digest
        and verifier_expected_stage_path_set_digest == expected_stage_path_set_digest
        and verifier_cached_staged_path_set_digest == cached_staged_path_set_digest
    )
    ordered_stage_digests_match = (
        owner_packet_stage_path_digest is not None
        and owner_packet_stage_command_digest is not None
        and command_audit_path_digest == owner_packet_stage_path_digest
        and command_audit_expected_path_digest == owner_packet_stage_path_digest
        and command_audit_owner_packet_path_digest == owner_packet_stage_path_digest
        and command_audit_command_digest == owner_packet_stage_command_digest
        and command_audit_owner_packet_command_digest == owner_packet_stage_command_digest
    )

    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more owner post-stage commit gate inputs are missing or unreadable",
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
            "owner_decision_brief_pre_stage_ready",
            _decision_brief_ready_or_post_staging_accounted(
                owner_decision_brief,
                owner_post_staging=owner_post_staging,
            ),
            details={
                "status": _status(owner_decision_brief),
                "post_staging_status": (
                    _summary(owner_decision_brief).get("post_staging_status")
                    or _status(owner_post_staging)
                ),
                "cached_staged_path_count": (
                    _summary(owner_decision_brief).get("cached_staged_path_count")
                    or owner_post_staging.get("cached_staged_path_count")
                ),
                "failed_checks": sorted(_failed_report_check_names(owner_decision_brief)),
            },
            error="owner decision brief is not ready or accounted for after post-stage verification",
        ),
        _check(
            "task_board_ready",
            task_board_ready or task_board_post_commit_noop_accounted_for or task_board_post_staging_accounted_for,
            details={
                "status": _status(task_board),
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
                "task_board_post_commit_noop_accounted_for": task_board_post_commit_noop_accounted_for,
                "task_board_post_staging_accounted_for": task_board_post_staging_accounted_for,
                "owner_post_stage_commit_gate_status": task_summary.get("owner_post_stage_commit_gate_status"),
                "owner_commit_packet_status": task_summary.get("owner_commit_packet_status"),
            },
            error="commercial delivery task board is not ready",
        ),
        _check(
            "stage_counts_agree",
            stage_counts_agree,
            details={**stage_counts, "post_commit_noop_accounted_for": post_commit_noop_accounted_for},
            error="owner packet, post-staging verifier, and command audit stage counts disagree",
        ),
        _check(
            "cached_paths_match_owner_packet",
            cached_paths_match_packet,
            details={
                "expected_stage_paths": packet_paths,
                "cached_staged_paths": cached_paths,
                "missing_cached_paths": sorted(set(packet_paths).difference(cached_paths)),
                "unexpected_cached_paths": sorted(set(cached_paths).difference(packet_paths)),
            },
            error="cached staged paths do not exactly match the owner staging packet",
        ),
        _check(
            "command_paths_match_owner_packet",
            command_paths_match_packet,
            details={
                "command_paths": command_paths,
                "expected_stage_paths": packet_paths,
            },
            error="owner command audit paths do not match the owner staging packet",
        ),
        _check(
            "path_set_digests_match_owner_packet",
            path_set_digests_match,
            details={
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "cached_staged_path_set_digest": cached_staged_path_set_digest,
                "command_path_set_digest": command_path_set_digest,
                "owner_packet_stage_path_set_digest": owner_packet_stage_path_set_digest,
                "verifier_expected_stage_path_set_digest": verifier_expected_stage_path_set_digest,
                "verifier_cached_staged_path_set_digest": verifier_cached_staged_path_set_digest,
            },
            error="post-stage path set digests do not match the owner staging packet",
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
            },
            error="ordered stage path or command digests do not match the owner staging packet",
        ),
        _check(
            "post_staging_has_no_path_drift",
            (
                not missing_cached_paths
                and not unexpected_cached_paths
                and not protected_cached_paths
            )
            or post_commit_noop_accounted_for,
            details={
                "missing_cached_paths": missing_cached_paths,
                "unexpected_cached_paths": unexpected_cached_paths,
                "protected_cached_paths": protected_cached_paths,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="post-staging verifier reports missing, unexpected, or protected cached paths",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "owner_packet_owner_gated": owner_packet.get("owner_gated"),
                "owner_post_staging_owner_gated": owner_post_staging.get("owner_gated"),
                "owner_command_audit_owner_gated": owner_command_audit.get("owner_gated"),
                "owner_decision_brief_owner_gated": owner_decision_brief.get("owner_gated"),
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
            "commit_command_preview_present",
            isinstance(commit_command_preview, str) and commit_command_preview.strip().startswith("git commit "),
            details={"commit_command_preview": commit_command_preview},
            error="owner staging packet does not provide a git commit preview",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more owner post-stage commit gate inputs claim full Codex parity",
        ),
        _check(
            "no_commit_gate_mutation",
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
    status = "owner_post_stage_commit_gate_ready" if ready else "owner_post_stage_commit_gate_blocked"
    decision = "ready_for_owner_commit" if ready else "blocked_before_owner_commit"
    blocking_reasons = _failed_check_names(checks)

    return OwnerPostStageCommitGate(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_post_stage_commit_gate",
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
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "stage_include_count": stage_counts["owner_packet_stage_include_count"],
            "expected_stage_path_count": len(packet_paths),
            "cached_staged_path_count": len(cached_paths),
            "owner_post_staging_status": _status(owner_post_staging),
            "owner_command_audit_status": _status(owner_command_audit),
            "owner_decision_brief_status": _status(owner_decision_brief),
            "task_board_status": _status(task_board),
            "task_board_post_commit_noop_accounted_for": task_board_post_commit_noop_accounted_for,
            "task_board_post_staging_accounted_for": task_board_post_staging_accounted_for,
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
            "commit_command_preview": commit_command_preview,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "cached_staged_path_set_digest": cached_staged_path_set_digest,
            "stage_path_digest": owner_packet_stage_path_digest,
            "stage_command_digest": owner_packet_stage_command_digest,
            "command_path_set_digest": command_path_set_digest,
            "command_audit_path_digest": command_audit_path_digest,
            "command_audit_expected_path_digest": command_audit_expected_path_digest,
            "command_audit_command_digest": command_audit_command_digest,
            "verifier_expected_stage_path_set_digest": verifier_expected_stage_path_set_digest,
            "verifier_cached_staged_path_set_digest": verifier_cached_staged_path_set_digest,
        },
        expected_stage_paths=packet_paths,
        cached_staged_paths=cached_paths,
        expected_stage_path_set_digest=expected_stage_path_set_digest,
        cached_staged_path_set_digest=cached_staged_path_set_digest,
        stage_path_digest=owner_packet_stage_path_digest,
        stage_command_digest=owner_packet_stage_command_digest,
        command_path_set_digest=command_path_set_digest,
        owner_packet_stage_path_set_digest=owner_packet_stage_path_set_digest,
        checks=checks,
        next_actions=[
            "If ready, review the staged diff and commit command preview with the owner before committing.",
            "If blocked, fix only the reported staged-path drift; do not use broad reset or broad add commands without owner approval.",
            "Keep secondary pending candidates detached until their handoff records validation.",
        ],
        known_limits=[
            "This gate is read-only except writing its evidence report.",
            "It does not stage, reset, commit, push, run tests, call network services, or execute agents.",
            "The owner decision brief is treated as pre-stage evidence and should not be regenerated after staging.",
            "This gate validates staged path readiness, not the semantic content of staged diffs.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_gate(gate: OwnerPostStageCommitGate) -> str:
    lines = [
        "# Commercial Delivery Owner Post-Stage Commit Gate",
        "",
        f"- Status: `{gate.status}`",
        f"- Generated at: `{gate.generated_at}`",
        f"- Decision: `{gate.decision}`",
        f"- Commit allowed: `{str(gate.commit_allowed).lower()}`",
        f"- Owner gated: `{str(gate.owner_gated).lower()}`",
        f"- Expected stage path count: `{gate.summary.get('expected_stage_path_count')}`",
        f"- Cached staged path count: `{gate.summary.get('cached_staged_path_count')}`",
        f"- Owner action required: `{str(gate.summary.get('owner_action_required')).lower()}`",
        f"- Blocking reasons: `{', '.join(gate.summary.get('blocking_reasons') or [])}`",
        f"- Secondary handoff next queue: `{', '.join(gate.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{gate.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{gate.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Expected stage path set digest: `{gate.expected_stage_path_set_digest or '<missing>'}`",
        f"- Cached staged path set digest: `{gate.cached_staged_path_set_digest or '<missing>'}`",
        f"- Stage path digest: `{gate.stage_path_digest or '<missing>'}`",
        f"- Stage command digest: `{gate.stage_command_digest or '<missing>'}`",
        f"- Commit command preview: `{gate.commit_command_preview}`",
        "",
        "## Checks",
        "",
    ]
    for check in gate.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Cached Staged Paths", ""])
    if gate.cached_staged_paths:
        lines.extend(f"- `{path}`" for path in gate.cached_staged_paths)
    else:
        lines.append("- None")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in gate.next_actions)
    return "\n".join(lines)


def write_report(gate: OwnerPostStageCommitGate, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_gate(gate: OwnerPostStageCommitGate, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_gate(gate), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-packet", type=Path, default=DEFAULT_OWNER_PACKET)
    parser.add_argument("--owner-post-staging", type=Path, default=DEFAULT_OWNER_POST_STAGING)
    parser.add_argument("--owner-command-audit", type=Path, default=DEFAULT_OWNER_COMMAND_AUDIT)
    parser.add_argument("--owner-decision-brief", type=Path, default=DEFAULT_OWNER_DECISION_BRIEF)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = build_owner_post_stage_commit_gate(
        owner_packet_path=args.owner_packet,
        owner_post_staging_path=args.owner_post_staging,
        owner_command_audit_path=args.owner_command_audit,
        owner_decision_brief_path=args.owner_decision_brief,
        task_board_path=args.task_board,
    )
    write_report(gate, args.output)
    write_markdown_gate(gate, args.markdown_output)
    print(f"Commercial delivery owner post-stage commit gate status: {gate.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Decision: {gate.decision}")
    print(f"Expected stage paths: {gate.summary.get('expected_stage_path_count')}")
    print(f"Cached staged paths: {gate.summary.get('cached_staged_path_count')}")
    for check in gate.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if gate.status == "owner_post_stage_commit_gate_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
