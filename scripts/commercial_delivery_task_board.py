#!/usr/bin/env python3
"""Build a read-only commercial delivery task board.

The board is the mainline coordination artifact for commercial delivery. It
does not stage files, create commits, push tags, call external services, run
agents, or execute secondary candidates. It only reads existing evidence
reports, the secondary handoff document, and git status so the mainline thread
can resume cleanly after secondary interruptions.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-task-board.md"
SECONDARY_HANDOFF_PATH = ROOT / "docs" / "original-kernel-secondary-handoff.md"


@dataclass(frozen=True)
class TaskBoardTask:
    id: str
    title: str
    lane: str
    priority: str
    status: str
    source: str
    details: dict[str, Any] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskBoardCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CommercialDeliveryTaskBoard:
    status: str
    generated_at: str
    evidence_type: str
    mutation_performed: bool
    git_stage_performed: bool
    git_commit_performed: bool
    git_push_performed: bool
    network_mutation_performed: bool
    agent_execution_enabled: bool
    full_codex_parity_claimed: bool
    reports: dict[str, str]
    summary: dict[str, Any]
    tasks: list[TaskBoardTask]
    checks: list[TaskBoardCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tasks"] = [asdict(task) for task in self.tasks]
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["tasks_count"] = len(self.tasks)
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


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", f"file not found: {_display_path(path)}"
    except OSError as exc:
        return "", f"could not read file {_display_path(path)}: {exc}"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip('"')


def _git_status_lines() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _git_paths(lines: Sequence[str]) -> set[str]:
    paths: set[str] = set()
    for line in lines:
        if not line.strip() or line.startswith("##"):
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        paths.add(_normalize_path(path))
    return paths


def _report_status(payload: dict[str, Any]) -> str | None:
    status = payload.get("status")
    return str(status) if status is not None else None


def _read_summary_value(payload: dict[str, Any], key: str) -> object:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary.get(key)
    return None


def _read_report_status_value(payload: dict[str, Any], key: str) -> object:
    report_statuses = payload.get("report_statuses")
    if isinstance(report_statuses, dict):
        return report_statuses.get(key)
    return None


def _summary_dict(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _list_str(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _dict_list_str(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        reasons = _list_str(items)
        if reasons:
            result[str(key)] = reasons
    return result


def _report_claims_parity(payloads: Sequence[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _handoff_queue_items(text: str) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+\.\s+`([^`]+)`", line)
        if match:
            items.append(match.group(1))
    return items


def _handoff_next_queue_items(text: str) -> list[str]:
    legacy_items: list[str] = []
    latest_planned_items: list[str] = []
    in_next_planned_section = False
    for line in text.splitlines():
        match = re.match(r"\s*\d+\.\s+`([^`]+)`\s+-\s+next\b", line, re.IGNORECASE)
        if match:
            legacy_items.append(match.group(1))
        if re.match(r"\s*Next planned\b.*candidate:\s*$", line, re.IGNORECASE):
            latest_planned_items = []
            in_next_planned_section = True
            continue
        if in_next_planned_section:
            planned_match = re.match(r"\s*-\s+`([^`]+)`", line)
            if planned_match:
                latest_planned_items.append(planned_match.group(1))
                in_next_planned_section = False
                continue
            if line.strip() and not line.startswith((" ", "\t", "-")):
                in_next_planned_section = False
    return latest_planned_items or legacy_items


def _handoff_candidate_name(value: str) -> str:
    normalized = _normalize_path(value)
    if normalized.startswith("backend/app/core/") or normalized.startswith("tests/"):
        return Path(normalized).name
    return normalized


def _handoff_completed_candidate_items(text: str) -> list[str]:
    items: list[str] = []
    in_completed_section = False
    for line in text.splitlines():
        if re.match(r"\s*#{2,6}\s+.+\(#\d+\s+completed\)\s*$", line, re.IGNORECASE) or re.match(
            r"\s*#{2,6}\s+\d{4}-\d{2}-\d{2}:\s+.+\bpacket\b.*$",
            line,
            re.IGNORECASE,
        ):
            in_completed_section = True
            continue
        if in_completed_section:
            file_match = re.match(r"\s*-\s+`([^`]+)`", line)
            if file_match:
                items.append(_handoff_candidate_name(file_match.group(1)))
                in_completed_section = False
                continue
            if re.match(r"\s*#{2,6}\s+", line):
                in_completed_section = False
        completed_match = re.search(r"\bCompleted\s+`([^`]+)`\s+as\b", line, re.IGNORECASE)
        if completed_match:
            items.append(_handoff_candidate_name(completed_match.group(1)))
            continue
        queue_match = re.match(r"\s*\d+\.\s+`([^`]+)`\s+-\s+completed\b", line, re.IGNORECASE)
        if queue_match:
            items.append(_handoff_candidate_name(queue_match.group(1)))
    return list(dict.fromkeys(item for item in items if item))


def _excluded_by_scope(manifest: dict[str, Any], scope: str) -> list[str]:
    paths: list[str] = []
    for item in manifest.get("excluded_dirty_paths") or []:
        if isinstance(item, dict) and item.get("scope") == scope:
            paths.append(_normalize_path(str(item.get("path") or "")))
    return sorted(path for path in paths if path)


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> TaskBoardCheck:
    return TaskBoardCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _owner_staging_preflight_accounted_for(reports: dict[str, dict[str, Any]]) -> bool:
    if _report_status(reports.get("owner_staging_preflight", {})) == "owner_staging_preflight_ready":
        return True
    owner_packet = reports.get("owner_staging_packet", {})
    owner_stage_command_count = len(owner_packet.get("stage_commands") or [])
    post_staging_cached_count = _read_summary_value(
        reports.get("owner_post_staging_verifier", {}),
        "cached_staged_path_count",
    )
    if post_staging_cached_count is None:
        post_staging_cached_count = reports.get("owner_post_staging_verifier", {}).get("cached_staged_path_count")
    post_staging_accounted_for = (
        _report_status(reports.get("owner_post_staging_verifier", {})) == "owner_post_staging_verification_ready"
        and owner_stage_command_count > 0
        and int(post_staging_cached_count or 0) == owner_stage_command_count
    )
    return (
        post_staging_accounted_for
        and _report_status(reports.get("owner_commit_packet", {}))
        in {"owner_commit_packet_ready", "owner_commit_packet_blocked"}
    )


def _failed_check_names(report_payload: dict[str, Any]) -> set[str]:
    checks = report_payload.get("checks")
    if not isinstance(checks, list):
        return set()
    failed: set[str] = set()
    for check in checks:
        if isinstance(check, dict) and check.get("status") == "failed" and check.get("name") is not None:
            failed.add(str(check.get("name")))
    return failed


def _failed_digest_check_has_matching_present_values(
    report_payload: dict[str, Any],
    *,
    check_name: str,
    detail_key: str,
) -> bool:
    checks = report_payload.get("checks")
    if not isinstance(checks, list):
        return False
    for check in checks:
        if not isinstance(check, dict) or check.get("name") != check_name or check.get("status") != "failed":
            continue
        details = check.get("details")
        if not isinstance(details, dict):
            return False
        sources = details.get(detail_key)
        if not isinstance(sources, dict):
            return False
        present = [str(value) for value in sources.values() if isinstance(value, str) and value]
        missing_count = sum(1 for value in sources.values() if not value)
        return bool(present) and missing_count > 0 and len(set(present)) == 1
    return False


def _failed_digest_check_has_only_task_board_stale_value(
    report_payload: dict[str, Any],
    *,
    check_name: str,
    detail_key: str,
    summary_key: str,
) -> bool:
    checks = report_payload.get("checks")
    if not isinstance(checks, list):
        return False
    for check in checks:
        if not isinstance(check, dict) or check.get("name") != check_name or check.get("status") != "failed":
            continue
        details = check.get("details")
        if not isinstance(details, dict):
            return False
        sources = details.get(detail_key)
        if not isinstance(sources, dict):
            return False
        task_board_value = sources.get("task_board")
        if not isinstance(task_board_value, str) or not task_board_value:
            return False
        non_task_board_values = [
            str(value)
            for key, value in sources.items()
            if key != "task_board" and isinstance(value, str) and value
        ]
        non_task_board_missing = [key for key, value in sources.items() if key != "task_board" and not value]
        if non_task_board_missing or not non_task_board_values:
            return False
        stable_values = set(non_task_board_values)
        if len(stable_values) != 1:
            return False
        stable_value = next(iter(stable_values))
        return task_board_value != stable_value and _read_summary_value(report_payload, summary_key) == stable_value
    return False


def _pre_approval_drift_guard_accounted_for(reports: dict[str, dict[str, Any]]) -> bool:
    drift_guard = reports.get("pre_approval_drift_guard", {})
    if _report_status(drift_guard) == "pre_approval_drift_guard_ready":
        return True
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
    failed_checks = _failed_check_names(drift_guard)
    post_approval_ready = (
        _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit") == "owner_approval_payload_ready"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is True
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_ready"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_ready"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_ready"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_ready"
        and _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_complete"
        and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_complete"
        and _read_summary_value(drift_guard, "closure_delivery_complete") is True
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
    refresh_chain_receipt_ready = (
        _report_status(reports.get("refresh_chain_receipt", {})) == "commercial_delivery_refresh_chain_receipt_ready"
    )
    if _failed_digest_check_has_matching_present_values(
        drift_guard,
        check_name="stage_command_digest_stable",
        detail_key="stage_command_digest_sources",
    ) or (
        refresh_chain_receipt_ready
        and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name="stage_command_digest_stable",
            detail_key="stage_command_digest_sources",
            summary_key="stage_command_digest",
        )
    ):
        post_commit_allowed_failed_checks.add("stage_command_digest_stable")
    if _failed_digest_check_has_matching_present_values(
        drift_guard,
        check_name="stage_path_digest_stable",
        detail_key="stage_path_digest_sources",
    ) or (
        refresh_chain_receipt_ready
        and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name="stage_path_digest_stable",
            detail_key="stage_path_digest_sources",
            summary_key="stage_path_digest",
        )
    ):
        post_commit_allowed_failed_checks.add("stage_path_digest_stable")
    if _failed_digest_check_has_matching_present_values(
        drift_guard,
        check_name="expected_stage_path_set_digest_stable",
        detail_key="expected_stage_path_set_digest_sources",
    ) or (
        refresh_chain_receipt_ready
        and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name="expected_stage_path_set_digest_stable",
            detail_key="expected_stage_path_set_digest_sources",
            summary_key="expected_stage_path_set_digest",
        )
    ):
        post_commit_allowed_failed_checks.add("expected_stage_path_set_digest_stable")
    stage_path_digest = _read_summary_value(drift_guard, "stage_path_digest")
    stage_command_digest = _read_summary_value(drift_guard, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(drift_guard, "expected_stage_path_set_digest")

    def _failed_digest_is_accounted_for(check_name: str, detail_key: str, summary_key: str) -> bool:
        if check_name not in failed_checks:
            return True
        if _failed_digest_check_has_matching_present_values(
            drift_guard,
            check_name=check_name,
            detail_key=detail_key,
        ):
            return True
        return refresh_chain_receipt_ready and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name=check_name,
            detail_key=detail_key,
            summary_key=summary_key,
        )

    operator_checklist_accounted_for = (
        _read_report_status_value(drift_guard, "owner_post_approval_operator_checklist")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_operator_ready") is True
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
    ) or (
        _read_report_status_value(drift_guard, "owner_post_approval_operator_checklist")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_operator_ready") is False
        and _read_summary_value(drift_guard, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
    )
    post_commit_blocked = (
        _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(drift_guard, "owner_stage_approval_request")
        == "owner_stage_approval_request_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit") == "owner_approval_payload_blocked"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is False
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is False
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_blocked"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_blocked"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_blocked"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_blocked"
        and operator_checklist_accounted_for
        and _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_closure_blocked"
        and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_closure_blocked"
        and _read_summary_value(drift_guard, "closure_delivery_complete") is False
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and post_commit_required_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(post_commit_allowed_failed_checks)
    )
    post_approval_noop_allowed_failed_checks = {
        "real_owner_approval_absent",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "approval_gate_blocked_before_owner",
        "stage_execution_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
        "secondary_handoff_summary_stable",
        "stage_command_digest_stable",
        "stage_path_digest_stable",
        "expected_stage_path_set_digest_stable",
    }
    post_approval_pre_stage_task_board_drift_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "stage_command_digest_stable",
        "stage_path_digest_stable",
        "expected_stage_path_set_digest_stable",
        "approval_payload_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
    }
    post_approval_noop_closure_accounted_for = (
        (
            _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_closure_blocked"
            and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_closure_blocked"
            and _read_summary_value(drift_guard, "closure_delivery_complete") is False
        )
        or (
            _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_complete"
            and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_complete"
            and _read_summary_value(drift_guard, "closure_delivery_complete") is True
        )
    )
    post_approval_noop_blocked = (
        _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(drift_guard, "owner_stage_approval_request")
        == "owner_stage_approval_request_ready"
        and _read_report_status_value(drift_guard, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit") == "owner_approval_payload_ready"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is True
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_ready"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_ready"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_ready"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_ready"
        and operator_checklist_accounted_for
        and post_approval_noop_closure_accounted_for
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and _failed_digest_is_accounted_for(
            "stage_path_digest_stable",
            "stage_path_digest_sources",
            "stage_path_digest",
        )
        and _failed_digest_is_accounted_for(
            "stage_command_digest_stable",
            "stage_command_digest_sources",
            "stage_command_digest",
        )
        and _failed_digest_is_accounted_for(
            "expected_stage_path_set_digest_stable",
            "expected_stage_path_set_digest_sources",
            "expected_stage_path_set_digest",
        )
        and failed_checks.issubset(post_approval_noop_allowed_failed_checks)
    )
    post_staging_cached_count = _read_summary_value(
        reports.get("owner_post_staging_verifier", {}),
        "cached_staged_path_count",
    )
    if post_staging_cached_count is None:
        post_staging_cached_count = reports.get("owner_post_staging_verifier", {}).get("cached_staged_path_count")
    post_approval_pre_stage_task_board_drift_blocked = (
        _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _report_status(reports.get("owner_post_staging_verifier", {}))
        == "owner_post_staging_verification_ready"
        and int(post_staging_cached_count or 0) > 0
        and _read_report_status_value(drift_guard, "owner_stage_approval_request")
        == "owner_stage_approval_request_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit") == "owner_approval_payload_blocked"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is False
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is False
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_blocked"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_blocked"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_blocked"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_blocked"
        and operator_checklist_accounted_for
        and _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_closure_blocked"
        and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_closure_blocked"
        and _read_summary_value(drift_guard, "closure_delivery_complete") is False
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name="stage_path_digest_stable",
            detail_key="stage_path_digest_sources",
            summary_key="stage_path_digest",
        )
        and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name="stage_command_digest_stable",
            detail_key="stage_command_digest_sources",
            summary_key="stage_command_digest",
        )
        and _failed_digest_check_has_only_task_board_stale_value(
            drift_guard,
            check_name="expected_stage_path_set_digest_stable",
            detail_key="expected_stage_path_set_digest_sources",
            summary_key="expected_stage_path_set_digest",
        )
        and failed_checks == post_approval_pre_stage_task_board_drift_checks
    )
    post_approval_boundary_required_failed_checks = {
        "real_owner_approval_absent",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "stage_execution_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    refresh_chain_summary = _summary_dict(reports.get("refresh_chain_receipt", {}))
    refresh_expected_nonzero_steps = refresh_chain_summary.get("expected_nonzero_steps")
    refresh_accounted_allowed_failed_checks = post_commit_allowed_failed_checks | {
        "stage_command_digest_stable",
        "stage_path_digest_stable",
        "expected_stage_path_set_digest_stable",
    }
    refresh_accounted_for_drift_guard = (
        refresh_chain_receipt_ready
        and isinstance(refresh_expected_nonzero_steps, list)
        and "pre_approval_drift_guard" in {str(step) for step in refresh_expected_nonzero_steps}
        and _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(drift_guard, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit") == "owner_approval_payload_blocked"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is False
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is False
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_blocked"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_blocked"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_blocked"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_blocked"
        and operator_checklist_accounted_for
        and _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_complete"
        and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_complete"
        and _read_summary_value(drift_guard, "closure_delivery_complete") is True
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and post_commit_required_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(refresh_accounted_allowed_failed_checks)
    )
    post_approval_boundary_blocked = (
        _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(drift_guard, "owner_stage_approval_request")
        == "owner_stage_approval_request_ready"
        and _read_report_status_value(drift_guard, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit") == "owner_approval_payload_blocked"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is False
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is False
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_blocked"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_blocked"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_ready"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_ready"
        and operator_checklist_accounted_for
        and _read_report_status_value(drift_guard, "closure_snapshot") == "commercial_delivery_complete"
        and _read_summary_value(drift_guard, "closure_snapshot_status") == "commercial_delivery_complete"
        and _read_summary_value(drift_guard, "closure_delivery_complete") is True
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and post_approval_boundary_required_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(post_approval_noop_allowed_failed_checks)
    )
    post_approval_complete_required_failed_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "approval_gate_blocked_before_owner",
        "stage_execution_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    post_approval_complete_accounted_for = (
        _report_status(drift_guard) == "pre_approval_drift_guard_blocked"
        and drift_guard.get("real_owner_approval_present") is True
        and drift_guard.get("mutation_performed") is not True
        and drift_guard.get("git_stage_performed") is not True
        and drift_guard.get("git_commit_performed") is not True
        and drift_guard.get("git_push_performed") is not True
        and drift_guard.get("network_mutation_performed") is not True
        and drift_guard.get("agent_execution_enabled") is not True
        and drift_guard.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(drift_guard, "owner_approval_payload_audit")
        == "owner_approval_payload_ready"
        and _read_summary_value(drift_guard, "owner_approval_payload_present") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_valid") is True
        and _read_summary_value(drift_guard, "owner_approval_payload_ready_for_gate") is True
        and _read_report_status_value(drift_guard, "owner_stage_approval_gate") == "owner_stage_approval_ready"
        and _read_summary_value(drift_guard, "owner_stage_approval_gate_status") == "owner_stage_approval_ready"
        and _read_report_status_value(drift_guard, "owner_stage_execution_plan") == "owner_stage_execution_ready"
        and _read_summary_value(drift_guard, "owner_stage_execution_plan_status") == "owner_stage_execution_ready"
        and operator_checklist_accounted_for
        and _read_report_status_value(drift_guard, "closure_snapshot")
        in {"commercial_delivery_closure_blocked", "commercial_delivery_complete"}
        and _read_summary_value(drift_guard, "closure_snapshot_status")
        in {"commercial_delivery_closure_blocked", "commercial_delivery_complete"}
        and isinstance(_read_summary_value(drift_guard, "closure_delivery_complete"), bool)
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and post_approval_complete_required_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(post_approval_complete_required_failed_checks)
    )
    return (
        post_approval_ready
        or post_commit_blocked
        or post_approval_noop_blocked
        or post_approval_pre_stage_task_board_drift_blocked
        or post_approval_boundary_blocked
        or post_approval_complete_accounted_for
        or refresh_accounted_for_drift_guard
    )


def _build_tasks(
    *,
    reports: dict[str, dict[str, Any]],
    report_errors: dict[str, str],
    handoff_text: str,
    handoff_error: str | None,
    git_paths: set[str],
) -> list[TaskBoardTask]:
    manifest = reports.get("original_kernel_manifest", {})
    secondary_candidates = _excluded_by_scope(manifest, "secondary_integration_candidate")
    secondary_pending = _excluded_by_scope(manifest, "secondary_pending_candidate")
    handoff_queue = _handoff_queue_items(handoff_text)
    handoff_next_queue = _handoff_next_queue_items(handoff_text)
    handoff_completed_candidates = _handoff_completed_candidate_items(handoff_text)
    closure_snapshot = reports.get("closure_snapshot", {})
    closure_summary = _summary_dict(closure_snapshot)
    closure_blockers = _list_str(closure_snapshot.get("blockers"))
    closure_owner_blocking_reasons = _dict_list_str(closure_summary.get("owner_blocking_reasons_by_report"))
    owner_staging_preflight_accounted_for = _owner_staging_preflight_accounted_for(reports)
    pre_approval_drift_guard_accounted_for = _pre_approval_drift_guard_accounted_for(reports)
    secondary_status = (
        "waiting_secondary_validation"
        if secondary_pending
        else "tracking_secondary_next"
        if handoff_next_queue
        else "ready"
    )

    tasks = [
        TaskBoardTask(
            id="secondary_handoff_sync",
            title="Secondary handoff triage",
            lane="secondary",
            priority="P0",
            status=secondary_status,
            source=_display_path(SECONDARY_HANDOFF_PATH),
            details={
                "secondary_candidate_count": len(secondary_candidates),
                "secondary_pending_paths": secondary_pending,
                "handoff_queue": handoff_queue,
                "handoff_next_queue": handoff_next_queue,
                "handoff_completed_candidates": handoff_completed_candidates,
                "handoff_latest_completed_candidate": handoff_completed_candidates[-1]
                if handoff_completed_candidates
                else None,
                "handoff_error": handoff_error,
            },
            next_actions=[
                "Process only verified secondary_integration_candidate updates first.",
                "Keep pending candidates out of stage_include_paths until the secondary handoff records validation.",
                "Track handoff next queue items without blocking owner-gated commercial staging review.",
            ],
        ),
        TaskBoardTask(
            id="control_modes_preservation",
            title="Plan mode and goal-loop control surface preservation",
            lane="control",
            priority="P0",
            status=(
                "ready"
                if _report_status(reports.get("control_modes_preservation", {})) == "control_modes_preservation_ready"
                else "blocked"
            ),
            source=".xagent_runtime/reports/commercial-delivery-control-modes-preservation.json",
            details={
                "status": _report_status(reports.get("control_modes_preservation", {})),
                "owner_gated": reports.get("control_modes_preservation", {}).get("owner_gated"),
                "agent_execution_enabled": reports.get("control_modes_preservation", {}).get("agent_execution_enabled"),
                "plan_only_default": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "plan_only_default",
                ),
                "execute_true_required_for_agent_run": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "execute_true_required_for_agent_run",
                ),
                "loop_phases": _read_summary_value(reports.get("control_modes_preservation", {}), "loop_phases"),
                "stage_in_original_kernel_manifest": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "stage_in_original_kernel_manifest",
                ),
            },
            next_actions=[
                "Preserve plan mode as draft-only until explicit owner approval.",
                "Preserve goal advance as plan-only unless execute=true is supplied and gates pass.",
                "Keep control-mode API/router/CLI entrypoints owner-gated and outside original-kernel staging.",
            ],
            blocked_by=[]
            if _report_status(reports.get("control_modes_preservation", {})) == "control_modes_preservation_ready"
            else ["control_modes_preservation_not_ready"],
        ),
        TaskBoardTask(
            id="original_kernel_manifest_sync",
            title="Original-kernel delivery manifest",
            lane="integration",
            priority="P0",
            status="ready" if _report_status(manifest) == "original_kernel_delivery_manifest_ready" else "blocked",
            source=".xagent_runtime/reports/original-kernel-delivery-manifest.json",
            details={
                "status": _report_status(manifest),
                "stage_include_count": manifest.get("stage_include_count"),
                "excluded_dirty_count": manifest.get("excluded_dirty_count"),
                "secondary_candidate_count": len(secondary_candidates),
                "secondary_pending_count": len(secondary_pending),
            },
            next_actions=[
                "Use this manifest as the source of truth for selective staging.",
                "Do not stage UI/API/router/agent-loop/control-plane dirty paths with original-kernel candidates.",
            ],
            blocked_by=[] if _report_status(manifest) == "original_kernel_delivery_manifest_ready" else ["manifest_not_ready"],
        ),
        TaskBoardTask(
            id="commercial_pilot_gate",
            title="Feishu Pilot V1 commercial handoff gate",
            lane="commercial",
            priority="P0",
            status=(
                "ready"
                if _report_status(reports.get("final_gate", {})) == "final_gate_ready"
                and _report_status(reports.get("acceptance_gate", {})) == "pilot_acceptance_ready"
                else "blocked"
            ),
            source=".xagent_runtime/reports/commercial-pilot-final-gate.json",
            details={
                "final_gate_status": _report_status(reports.get("final_gate", {})),
                "acceptance_gate_status": _report_status(reports.get("acceptance_gate", {})),
                "handoff_index_status": _report_status(reports.get("handoff_index", {})),
                "rc_delivery_status": _report_status(reports.get("rc_delivery_status", {})),
                "channel_readiness_status": _report_status(reports.get("channel_readiness", {})),
            },
            next_actions=[
                "Keep Feishu as the V1 domestic pilot channel.",
                "Treat outbound Feishu send as owner-gated until the outbound live report is passed.",
            ],
        ),
        TaskBoardTask(
            id="owner_gated_staging_review",
            title="Owner-gated staging package review",
            lane="release",
            priority="P1",
            status=(
                "ready"
                if _report_status(reports.get("staging_review", {})) == "staging_review_ready"
                and _report_status(reports.get("owner_staging_packet", {})) == "owner_staging_packet_ready"
                and owner_staging_preflight_accounted_for
                else "blocked"
            ),
            source=".xagent_runtime/reports/commercial-delivery-staging-review.json",
            details={
                "stage_include_count": manifest.get("stage_include_count"),
                "staging_review_status": _report_status(reports.get("staging_review", {})),
                "owner_staging_packet_status": _report_status(reports.get("owner_staging_packet", {})),
                "owner_staging_preflight_status": _report_status(reports.get("owner_staging_preflight", {})),
                "owner_staging_preflight_accounted_for": owner_staging_preflight_accounted_for,
                "owner_post_staging_verifier_status": _report_status(reports.get("owner_post_staging_verifier", {})),
                "owner_decision_brief_status": _report_status(reports.get("owner_decision_brief", {})),
                "owner_command_audit_status": _report_status(reports.get("owner_command_audit", {})),
                "refresh_chain_receipt_status": _report_status(reports.get("refresh_chain_receipt", {})),
                "owner_pre_stage_readiness_gate_status": _report_status(reports.get("owner_pre_stage_readiness_gate", {})),
                "owner_staging_runbook_status": _report_status(reports.get("owner_staging_runbook", {})),
                "owner_post_stage_commit_gate_status": _report_status(reports.get("owner_post_stage_commit_gate", {})),
                "owner_commit_packet_status": _report_status(reports.get("owner_commit_packet", {})),
                "owner_staging_rollback_plan_status": _report_status(reports.get("owner_staging_rollback_plan", {})),
                "owner_delivery_packet_status": _report_status(reports.get("owner_delivery_packet", {})),
                "owner_stage_approval_request_status": _report_status(reports.get("owner_stage_approval_request", {})),
                "owner_approval_payload_audit_status": _report_status(reports.get("owner_approval_payload_audit", {})),
                "owner_approval_payload_present": reports.get("owner_approval_payload_audit", {}).get("approval_payload_present"),
                "owner_approval_payload_valid": reports.get("owner_approval_payload_audit", {}).get("approval_payload_valid"),
                "owner_stage_approval_brief_status": _report_status(reports.get("owner_stage_approval_brief", {})),
                "owner_approval_handoff_status": _report_status(reports.get("owner_approval_handoff", {})),
                "owner_stage_approval_gate_status": _report_status(reports.get("owner_stage_approval_gate", {})),
                "owner_stage_execution_plan_status": _report_status(reports.get("owner_stage_execution_plan", {})),
                "pre_approval_drift_guard_status": _report_status(reports.get("pre_approval_drift_guard", {})),
                "pre_approval_drift_guard_accounted_for": pre_approval_drift_guard_accounted_for,
                "owner_approval_resume_packet_status": _report_status(
                    reports.get("owner_approval_resume_packet", {})
                ),
                "owner_approval_resume_packet_waiting_for_owner": reports.get(
                    "owner_approval_resume_packet",
                    {},
                ).get("waiting_for_owner"),
                "owner_approval_resume_packet_resume_ready": reports.get("owner_approval_resume_packet", {}).get(
                    "resume_ready"
                ),
                "owner_post_approval_operator_checklist_status": _report_status(
                    reports.get("owner_post_approval_operator_checklist", {})
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": reports.get(
                    "owner_post_approval_operator_checklist",
                    {},
                ).get("waiting_for_owner"),
                "owner_post_approval_operator_checklist_operator_ready": reports.get(
                    "owner_post_approval_operator_checklist",
                    {},
                ).get("operator_ready"),
                "pre_approval_drift_guard_real_owner_approval_present": reports.get("pre_approval_drift_guard", {}).get(
                    "real_owner_approval_present"
                ),
                "pre_approval_drift_guard_stage_path_digest": _read_summary_value(
                    reports.get("pre_approval_drift_guard", {}),
                    "stage_path_digest",
                ),
                "pre_approval_drift_guard_stage_command_digest": _read_summary_value(
                    reports.get("pre_approval_drift_guard", {}),
                    "stage_command_digest",
                ),
                "closure_snapshot_status": _report_status(reports.get("closure_snapshot", {})),
                "closure_delivery_complete": closure_snapshot.get("delivery_complete"),
                "closure_blockers": closure_blockers,
                "closure_owner_action_required": closure_summary.get("owner_action_required"),
                "closure_owner_blocking_reason_count": closure_summary.get("owner_blocking_reason_count"),
                "closure_owner_blocking_reasons_by_report": closure_owner_blocking_reasons,
                "closure_stage_path_digest": closure_summary.get("stage_path_digest"),
                "closure_stage_command_digest": closure_summary.get("stage_command_digest"),
                "closure_expected_stage_path_set_digest": closure_summary.get("expected_stage_path_set_digest"),
                "closure_cached_staged_path_set_digest": closure_summary.get("cached_staged_path_set_digest"),
                "control_modes_preservation_status": _report_status(reports.get("control_modes_preservation", {})),
                "eligible_stage_count": reports.get("staging_review", {}).get("eligible_stage_count"),
                "blocked_stage_count": reports.get("staging_review", {}).get("blocked_stage_count"),
                "owner_stage_command_count": len(reports.get("owner_staging_packet", {}).get("stage_commands") or []),
                "cached_staged_path_count": reports.get("owner_staging_preflight", {}).get("cached_staged_path_count"),
                "post_staging_cached_path_count": reports.get("owner_post_staging_verifier", {}).get("cached_staged_path_count"),
                "unchanged_stage_count": reports.get("staging_review", {}).get("unchanged_stage_count"),
                "owner_gated": reports.get("staging_review", {}).get("owner_gated"),
                "git_dirty_path_count": len(git_paths),
                "git_stage_performed": manifest.get("git_stage_performed"),
                "git_commit_performed": manifest.get("git_commit_performed"),
                "git_push_performed": manifest.get("git_push_performed"),
            },
            next_actions=[
                "Review stage_include_paths before any git add.",
                "Run owner staging preflight immediately before any owner-approved git add commands.",
                "Stage only explicit paths after owner approval; never use git add .",
                "After staging, run owner post-staging verifier before commit.",
            ],
        ),
    ]
    if report_errors:
        tasks.append(
            TaskBoardTask(
                id="missing_or_unreadable_reports",
                title="Missing or unreadable commercial evidence",
                lane="evidence",
                priority="P0",
                status="blocked",
                source=".xagent_runtime/reports",
                details={"errors": report_errors},
                next_actions=["Regenerate or inspect the missing evidence reports before making delivery claims."],
                blocked_by=sorted(report_errors),
            )
        )
    return tasks


def build_task_board(
    *,
    reports_dir: Path = REPORT_DIR,
    secondary_handoff_path: Path = SECONDARY_HANDOFF_PATH,
    git_status_lines: Sequence[str] | None = None,
) -> CommercialDeliveryTaskBoard:
    report_paths = {
        "final_gate": reports_dir / "commercial-pilot-final-gate.json",
        "acceptance_gate": reports_dir / "commercial-pilot-acceptance-gate.json",
        "handoff_index": reports_dir / "commercial-pilot-handoff-index.json",
        "rc_delivery_status": reports_dir / "rc-delivery-status.json",
        "channel_readiness": reports_dir / "commercial-pilot-channel-readiness.json",
        "control_modes_preservation": reports_dir / "commercial-delivery-control-modes-preservation.json",
        "original_kernel_manifest": reports_dir / "original-kernel-delivery-manifest.json",
        "staging_review": reports_dir / "commercial-delivery-staging-review.json",
        "owner_staging_packet": reports_dir / "commercial-delivery-owner-staging-packet.json",
        "owner_staging_preflight": reports_dir / "commercial-delivery-owner-staging-preflight.json",
        "owner_post_staging_verifier": reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
    }
    optional_report_paths = {
        "owner_command_audit": reports_dir / "commercial-delivery-owner-command-audit.json",
        "owner_decision_brief": reports_dir / "commercial-delivery-owner-decision-brief.json",
        "refresh_chain_receipt": reports_dir / "commercial-delivery-refresh-chain-receipt.json",
        "owner_pre_stage_readiness_gate": reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        "owner_staging_runbook": reports_dir / "commercial-delivery-owner-staging-runbook.json",
        "owner_post_stage_commit_gate": reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        "owner_commit_packet": reports_dir / "commercial-delivery-owner-commit-packet.json",
        "owner_staging_rollback_plan": reports_dir / "commercial-delivery-owner-staging-rollback-plan.json",
        "owner_delivery_packet": reports_dir / "commercial-delivery-owner-delivery-packet.json",
        "owner_stage_approval_request": reports_dir / "commercial-delivery-owner-stage-approval-request.json",
        "owner_approval_payload_audit": reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        "owner_stage_approval_brief": reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        "owner_approval_handoff": reports_dir / "commercial-delivery-owner-approval-handoff.json",
        "owner_stage_approval_gate": reports_dir / "commercial-delivery-owner-stage-approval-gate.json",
        "owner_stage_execution_plan": reports_dir / "commercial-delivery-owner-stage-execution-plan.json",
        "closure_snapshot": reports_dir / "commercial-delivery-closure-snapshot.json",
        "pre_approval_drift_guard": reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        "owner_approval_resume_packet": reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        "owner_post_approval_operator_checklist": reports_dir
        / "commercial-delivery-owner-post-approval-operator-checklist.json",
    }
    reports: dict[str, dict[str, Any]] = {}
    report_errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            report_errors[name] = error
    for name, path in optional_report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload if error is None else {}

    handoff_text, handoff_error = _read_text(secondary_handoff_path)
    handoff_next_queue = _handoff_next_queue_items(handoff_text)
    handoff_completed_candidates = _handoff_completed_candidate_items(handoff_text)
    git_paths = _git_paths(git_status_lines if git_status_lines is not None else _git_status_lines())
    manifest = reports.get("original_kernel_manifest", {})
    payloads = list(reports.values())
    full_codex_parity_claimed = _report_claims_parity(payloads)
    secondary_pending = _excluded_by_scope(manifest, "secondary_pending_candidate")
    closure_snapshot = reports.get("closure_snapshot", {})
    closure_summary = _summary_dict(closure_snapshot)
    closure_blockers = _list_str(closure_snapshot.get("blockers"))
    closure_owner_blocking_reasons = _dict_list_str(closure_summary.get("owner_blocking_reasons_by_report"))
    owner_staging_preflight_accounted_for = _owner_staging_preflight_accounted_for(reports)
    pre_approval_drift_guard_accounted_for = _pre_approval_drift_guard_accounted_for(reports)
    tasks = _build_tasks(
        reports=reports,
        report_errors=report_errors,
        handoff_text=handoff_text,
        handoff_error=handoff_error,
        git_paths=git_paths,
    )

    checks = [
        _check(
            "commercial_gate_ready",
            _report_status(reports.get("final_gate", {})) == "final_gate_ready"
            and _report_status(reports.get("acceptance_gate", {})) == "pilot_acceptance_ready",
            details={
                "final_gate_status": _report_status(reports.get("final_gate", {})),
                "acceptance_gate_status": _report_status(reports.get("acceptance_gate", {})),
            },
            error="commercial pilot final or acceptance gate is not ready",
        ),
        _check(
            "original_kernel_manifest_ready",
            _report_status(manifest) == "original_kernel_delivery_manifest_ready",
            details={"manifest_status": _report_status(manifest)},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "control_modes_preservation_ready",
            _report_status(reports.get("control_modes_preservation", {})) == "control_modes_preservation_ready",
            details={
                "control_modes_preservation_status": _report_status(reports.get("control_modes_preservation", {})),
                "owner_gated": reports.get("control_modes_preservation", {}).get("owner_gated"),
                "agent_execution_enabled": reports.get("control_modes_preservation", {}).get("agent_execution_enabled"),
                "plan_only_default": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "plan_only_default",
                ),
                "loop_phases": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "loop_phases",
                ),
                "control_surface_file_count": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "control_surface_file_count",
                ),
                "stage_in_original_kernel_manifest": _read_summary_value(
                    reports.get("control_modes_preservation", {}),
                    "stage_in_original_kernel_manifest",
                ),
            },
            error="control mode preservation evidence is not ready",
        ),
        _check(
            "staging_review_ready",
            _report_status(reports.get("staging_review", {})) == "staging_review_ready",
            details={
                "staging_review_status": _report_status(reports.get("staging_review", {})),
                "eligible_stage_count": reports.get("staging_review", {}).get("eligible_stage_count"),
                "blocked_stage_count": reports.get("staging_review", {}).get("blocked_stage_count"),
                "owner_gated": reports.get("staging_review", {}).get("owner_gated"),
            },
            error="commercial delivery staging review is not ready",
        ),
        _check(
            "owner_staging_packet_ready",
            _report_status(reports.get("owner_staging_packet", {})) == "owner_staging_packet_ready",
            details={
                "owner_staging_packet_status": _report_status(reports.get("owner_staging_packet", {})),
                "stage_command_count": len(reports.get("owner_staging_packet", {}).get("stage_commands") or []),
                "owner_gated": reports.get("owner_staging_packet", {}).get("owner_gated"),
            },
            error="commercial delivery owner staging packet is not ready",
        ),
        _check(
            "owner_staging_preflight_accounted_for",
            owner_staging_preflight_accounted_for,
            details={
                "owner_staging_preflight_status": _report_status(reports.get("owner_staging_preflight", {})),
                "stage_command_count": reports.get("owner_staging_preflight", {}).get("stage_command_count"),
                "cached_staged_path_count": reports.get("owner_staging_preflight", {}).get("cached_staged_path_count"),
                "owner_post_staging_verifier_status": _report_status(reports.get("owner_post_staging_verifier", {})),
                "owner_post_stage_commit_gate_status": _report_status(reports.get("owner_post_stage_commit_gate", {})),
                "owner_commit_packet_status": _report_status(reports.get("owner_commit_packet", {})),
                "owner_staging_preflight_accounted_for": owner_staging_preflight_accounted_for,
                "owner_gated": reports.get("owner_staging_preflight", {}).get("owner_gated"),
            },
            error="commercial delivery owner staging preflight is not ready or accounted for by post-stage evidence",
        ),
        _check(
            "pre_approval_drift_guard_ready",
            pre_approval_drift_guard_accounted_for,
            details={
                "pre_approval_drift_guard_status": _report_status(reports.get("pre_approval_drift_guard", {})),
                "pre_approval_drift_guard_accounted_for": pre_approval_drift_guard_accounted_for,
                "real_owner_approval_present": reports.get("pre_approval_drift_guard", {}).get(
                    "real_owner_approval_present"
                ),
                "stage_path_digest": _read_summary_value(
                    reports.get("pre_approval_drift_guard", {}),
                    "stage_path_digest",
                ),
                "stage_command_digest": _read_summary_value(
                    reports.get("pre_approval_drift_guard", {}),
                    "stage_command_digest",
                ),
            },
            error="commercial delivery pre-approval drift guard is not ready",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more delivery reports claim full Codex parity",
        ),
        _check(
            "no_entrypoint_or_ui_stage_drift",
            not any(
                manifest.get(key) is True
                for key in (
                    "entrypoints_modified",
                    "api_router_modified",
                    "control_plane_modified",
                    "frontend_modified",
                    "agent_loop_modified",
                    "backend_core_init_modified",
                )
            ),
            details={
                key: manifest.get(key)
                for key in (
                    "entrypoints_modified",
                    "api_router_modified",
                    "control_plane_modified",
                    "frontend_modified",
                    "agent_loop_modified",
                    "backend_core_init_modified",
                )
            },
            error="manifest reports drift in a protected mainline entrypoint/UI surface",
        ),
        _check(
            "secondary_pending_tracked",
            True,
            details={
                "secondary_pending_paths": secondary_pending,
                "handoff_next_queue": handoff_next_queue,
                "handoff_completed_candidate_count": len(handoff_completed_candidates),
                "handoff_latest_completed_candidate": handoff_completed_candidates[-1]
                if handoff_completed_candidates
                else None,
            },
        ),
        _check(
            "no_task_board_mutation",
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
    if any(check.status == "failed" for check in checks):
        status = "commercial_delivery_blocked"
    else:
        status = "commercial_delivery_ready_for_owner_staging_review"

    return CommercialDeliveryTaskBoard(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_task_board",
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        reports={name: _display_path(path) for name, path in {**report_paths, **optional_report_paths}.items()},
        summary={
            "task_count": len(tasks),
            "blocked_task_count": sum(1 for task in tasks if task.status == "blocked"),
            "ready_task_count": sum(1 for task in tasks if task.status == "ready"),
            "secondary_pending_count": len(secondary_pending),
            "secondary_handoff_next_count": len(handoff_next_queue),
            "secondary_handoff_next_queue": handoff_next_queue,
            "secondary_handoff_completed_count": len(handoff_completed_candidates),
            "secondary_handoff_latest_completed_candidate": handoff_completed_candidates[-1]
            if handoff_completed_candidates
            else None,
            "secondary_pending_blocks_owner_staging": False,
            "git_dirty_path_count": len(git_paths),
            "stage_include_count": manifest.get("stage_include_count"),
            "eligible_stage_count": reports.get("staging_review", {}).get("eligible_stage_count"),
            "blocked_stage_count": reports.get("staging_review", {}).get("blocked_stage_count"),
            "owner_stage_command_count": len(reports.get("owner_staging_packet", {}).get("stage_commands") or []),
            "owner_staging_preflight_status": _report_status(reports.get("owner_staging_preflight", {})),
            "owner_staging_preflight_accounted_for": owner_staging_preflight_accounted_for,
            "cached_staged_path_count": reports.get("owner_staging_preflight", {}).get("cached_staged_path_count"),
            "owner_post_staging_verifier_status": _report_status(reports.get("owner_post_staging_verifier", {})),
            "post_staging_cached_path_count": reports.get("owner_post_staging_verifier", {}).get("cached_staged_path_count"),
            "owner_decision_brief_status": _report_status(reports.get("owner_decision_brief", {})),
            "owner_command_audit_status": _report_status(reports.get("owner_command_audit", {})),
            "refresh_chain_receipt_status": _report_status(reports.get("refresh_chain_receipt", {})),
            "control_modes_preservation_status": _report_status(reports.get("control_modes_preservation", {})),
            "control_modes_plan_only_default": _read_summary_value(
                reports.get("control_modes_preservation", {}),
                "plan_only_default",
            ),
            "control_modes_loop_phases": _read_summary_value(
                reports.get("control_modes_preservation", {}),
                "loop_phases",
            ),
            "control_modes_surface_file_count": _read_summary_value(
                reports.get("control_modes_preservation", {}),
                "control_surface_file_count",
            ),
            "owner_pre_stage_readiness_gate_status": _report_status(reports.get("owner_pre_stage_readiness_gate", {})),
            "owner_staging_runbook_status": _report_status(reports.get("owner_staging_runbook", {})),
            "owner_post_stage_commit_gate_status": _report_status(reports.get("owner_post_stage_commit_gate", {})),
            "owner_commit_packet_status": _report_status(reports.get("owner_commit_packet", {})),
            "owner_staging_rollback_plan_status": _report_status(reports.get("owner_staging_rollback_plan", {})),
            "owner_delivery_packet_status": _report_status(reports.get("owner_delivery_packet", {})),
            "owner_stage_approval_request_status": _report_status(reports.get("owner_stage_approval_request", {})),
            "owner_approval_payload_audit_status": _report_status(reports.get("owner_approval_payload_audit", {})),
            "owner_approval_payload_present": reports.get("owner_approval_payload_audit", {}).get("approval_payload_present"),
            "owner_approval_payload_valid": reports.get("owner_approval_payload_audit", {}).get("approval_payload_valid"),
            "owner_stage_approval_brief_status": _report_status(reports.get("owner_stage_approval_brief", {})),
            "owner_approval_handoff_status": _report_status(reports.get("owner_approval_handoff", {})),
            "owner_stage_approval_gate_status": _report_status(reports.get("owner_stage_approval_gate", {})),
            "owner_stage_execution_plan_status": _report_status(reports.get("owner_stage_execution_plan", {})),
            "owner_approval_resume_packet_status": _report_status(reports.get("owner_approval_resume_packet", {})),
            "owner_approval_resume_packet_waiting_for_owner": reports.get("owner_approval_resume_packet", {}).get(
                "waiting_for_owner"
            ),
            "owner_approval_resume_packet_resume_ready": reports.get("owner_approval_resume_packet", {}).get(
                "resume_ready"
            ),
            "owner_post_approval_operator_checklist_status": _report_status(
                reports.get("owner_post_approval_operator_checklist", {})
            ),
            "owner_post_approval_operator_checklist_waiting_for_owner": reports.get(
                "owner_post_approval_operator_checklist",
                {},
            ).get("waiting_for_owner"),
            "owner_post_approval_operator_checklist_operator_ready": reports.get(
                "owner_post_approval_operator_checklist",
                {},
            ).get("operator_ready"),
            "pre_approval_drift_guard_status": _report_status(reports.get("pre_approval_drift_guard", {})),
            "pre_approval_drift_guard_accounted_for": pre_approval_drift_guard_accounted_for,
            "pre_approval_drift_guard_real_owner_approval_present": reports.get("pre_approval_drift_guard", {}).get(
                "real_owner_approval_present"
            ),
            "pre_approval_drift_guard_stage_path_digest": _read_summary_value(
                reports.get("pre_approval_drift_guard", {}),
                "stage_path_digest",
            ),
            "pre_approval_drift_guard_stage_command_digest": _read_summary_value(
                reports.get("pre_approval_drift_guard", {}),
                "stage_command_digest",
            ),
            "pre_approval_drift_guard_expected_stage_path_set_digest": _read_summary_value(
                reports.get("pre_approval_drift_guard", {}),
                "expected_stage_path_set_digest",
            ),
            "closure_snapshot_status": _report_status(reports.get("closure_snapshot", {})),
            "closure_delivery_complete": closure_snapshot.get("delivery_complete"),
            "closure_blockers": closure_blockers,
            "closure_owner_action_required": closure_summary.get("owner_action_required"),
            "closure_owner_blocking_reason_count": closure_summary.get("owner_blocking_reason_count"),
            "closure_owner_blocking_reasons_by_report": closure_owner_blocking_reasons,
            "closure_stage_path_digest": closure_summary.get("stage_path_digest"),
            "closure_stage_command_digest": closure_summary.get("stage_command_digest"),
            "closure_expected_stage_path_set_digest": closure_summary.get("expected_stage_path_set_digest"),
            "closure_cached_staged_path_set_digest": closure_summary.get("cached_staged_path_set_digest"),
            "excluded_dirty_count": manifest.get("excluded_dirty_count"),
        },
        tasks=tasks,
        checks=checks,
        next_actions=[
            "Handle verified secondary handoff updates before changing mainline staging state.",
            "Track unverified secondary next candidates without blocking owner-gated commercial staging review.",
            "Run owner staging preflight immediately before any owner-approved git add commands.",
            "Run owner post-staging verifier after owner-approved staging and before commit.",
            "Run owner post-stage commit gate after post-staging verification is ready.",
            "Generate the owner commit packet after the post-stage commit gate is ready.",
            "Use the owner delivery packet as the single pre-stage owner review handoff.",
            "Use the owner approval handoff to create the real owner approval payload only after human review.",
            "Keep plan mode and goal-loop control surfaces preserved but owner-gated outside original-kernel staging.",
            "Use the closure snapshot as the final read-only completion gate; pre-approval blocked is expected.",
            "Require owner stage approval gate to be ready before running any stage command.",
            "Keep Feishu as the only V1 domestic channel unless the owner changes channel scope.",
        ],
        known_limits=[
            "This task board is a read-only coordination artifact.",
            "It does not claim full Codex parity.",
            "It does not execute agents, browser tasks, git operations, network calls, or secondary candidate code.",
            "Pending secondary files require a validated handoff before promotion to secondary_integration_candidate.",
            "Control-mode API/router/CLI surfaces are tracked as preservation evidence, not auto-staged original-kernel candidates.",
        ],
    )


def render_markdown_board(report: CommercialDeliveryTaskBoard) -> str:
    lines = [
        "# Commercial Delivery Task Board",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Evidence type: `{report.evidence_type}`",
        f"- Full Codex parity claimed: `{str(report.full_codex_parity_claimed).lower()}`",
        f"- Task count: `{report.summary['task_count']}`",
        f"- Secondary pending count: `{report.summary['secondary_pending_count']}`",
        f"- Stage include count: `{report.summary.get('stage_include_count')}`",
        f"- Excluded dirty count: `{report.summary.get('excluded_dirty_count')}`",
        f"- Closure snapshot status: `{report.summary.get('closure_snapshot_status')}`",
        f"- Closure delivery complete: `{report.summary.get('closure_delivery_complete')}`",
        f"- Closure blockers: `{', '.join(report.summary.get('closure_blockers') or [])}`",
        f"- Closure owner action required: `{report.summary.get('closure_owner_action_required')}`",
        f"- Closure owner blocking reason count: `{report.summary.get('closure_owner_blocking_reason_count')}`",
        f"- Pre-approval drift guard: `{report.summary.get('pre_approval_drift_guard_status')}`",
        f"- Real owner approval present: `{report.summary.get('pre_approval_drift_guard_real_owner_approval_present')}`",
        f"- Stage path digest: `{report.summary.get('closure_stage_path_digest')}`",
        f"- Stage command digest: `{report.summary.get('closure_stage_command_digest')}`",
        f"- Expected stage path set digest: `{report.summary.get('closure_expected_stage_path_set_digest')}`",
        f"- Cached staged path set digest: `{report.summary.get('closure_cached_staged_path_set_digest')}`",
        f"- Owner approval payload audit status: `{report.summary.get('owner_approval_payload_audit_status')}`",
        f"- Owner approval payload present: `{report.summary.get('owner_approval_payload_present')}`",
        f"- Owner approval resume packet: `{report.summary.get('owner_approval_resume_packet_status')}`",
        f"- Owner approval resume waiting: `{report.summary.get('owner_approval_resume_packet_waiting_for_owner')}`",
        f"- Owner post-approval operator checklist: `{report.summary.get('owner_post_approval_operator_checklist_status')}`",
        f"- Owner post-approval operator ready: `{report.summary.get('owner_post_approval_operator_checklist_operator_ready')}`",
        f"- Control modes preservation: `{report.summary.get('control_modes_preservation_status')}`",
        f"- Control modes plan-only default: `{report.summary.get('control_modes_plan_only_default')}`",
        f"- Control modes loop phases: `{', '.join(report.summary.get('control_modes_loop_phases') or [])}`",
        "",
        "## Tasks",
        "",
    ]
    for task in report.tasks:
        lines.extend(
            [
                f"### {task.id}",
                "",
                f"- Title: {task.title}",
                f"- Lane: `{task.lane}`",
                f"- Priority: `{task.priority}`",
                f"- Status: `{task.status}`",
                f"- Source: `{task.source}`",
            ]
        )
        if task.next_actions:
            lines.append("- Next actions:")
            lines.extend(f"  - {action}" for action in task.next_actions)
        if task.blocked_by:
            lines.append(f"- Blocked by: `{', '.join(task.blocked_by)}`")
        lines.append("")

    lines.extend(["## Owner Blocking Reasons", ""])
    by_report = report.summary.get("closure_owner_blocking_reasons_by_report")
    if isinstance(by_report, dict) and by_report:
        for report_name, reasons in by_report.items():
            lines.append(f"- `{report_name}`: `{', '.join(str(reason) for reason in reasons)}`")
    else:
        lines.append("- None")
    lines.append("")

    lines.extend(["## Checks", ""])
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in report.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(report: CommercialDeliveryTaskBoard, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_board(report: CommercialDeliveryTaskBoard, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_board(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--reports-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--secondary-handoff-path", type=Path, default=SECONDARY_HANDOFF_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_task_board(
        reports_dir=args.reports_dir,
        secondary_handoff_path=args.secondary_handoff_path,
    )
    write_report(report, args.output)
    write_markdown_board(report, args.markdown_output)

    print(f"Commercial delivery task board status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Tasks: {report.summary['task_count']}")
    print(f"Secondary pending: {report.summary['secondary_pending_count']}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status != "commercial_delivery_blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
