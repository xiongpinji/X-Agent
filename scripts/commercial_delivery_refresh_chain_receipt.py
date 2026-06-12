#!/usr/bin/env python3
"""Refresh commercial delivery reports and write an auditable receipt.

The commercial delivery reports have ordering dependencies: the manifest feeds
the staging review, the staging review feeds the owner packet, and the owner
decision brief depends on the command audit and task board. This script runs
that read-only refresh chain in order and records a receipt. It does not stage
files, create commits, push branches, execute agents, or call network services.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-refresh-chain-receipt.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-refresh-chain-receipt.md"

SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")


@dataclass(frozen=True)
class CommandRunResult:
    command: list[str]
    returncode: int
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class RefreshChainStep:
    name: str
    command: list[str]
    status: str
    returncode: int | None
    duration_seconds: float | None = None
    report_path: str | None = None
    report_status: str | None = None
    expected_nonzero_accepted: bool = False
    stdout_tail: list[str] = field(default_factory=list)
    stderr_tail: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class RefreshChainReceiptCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class RefreshChainReceipt:
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
    dry_run: bool
    stop_on_failure: bool
    reports_dir: str
    steps: list[RefreshChainStep]
    checks: list[RefreshChainReceiptCheck]
    summary: dict[str, Any]
    final_report_statuses: dict[str, str | None]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["steps_count"] = len(self.steps)
        payload["checks_count"] = len(self.checks)
        payload["next_actions_count"] = len(self.next_actions)
        payload["known_limits_count"] = len(self.known_limits)
        return payload


CommandRunner = Callable[[list[str], float], CommandRunResult]


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _sanitize_output_line(line: str) -> str:
    line = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", line)
    return SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", line)


def _tail_lines(value: str | bytes | None, *, limit: int = 20) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    return [_sanitize_output_line(line) for line in text.splitlines()[-limit:]]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> RefreshChainReceiptCheck:
    return RefreshChainReceiptCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _step_commands() -> list[tuple[str, list[str]]]:
    return [
        ("original_kernel_manifest", ["python", "scripts\\original_kernel_delivery_manifest.py"]),
        ("control_modes_preservation", ["python", "scripts\\commercial_delivery_control_modes_preservation.py"]),
        ("staging_review", ["python", "scripts\\commercial_delivery_staging_review.py"]),
        ("owner_staging_packet", ["python", "scripts\\commercial_delivery_owner_staging_packet.py"]),
        ("owner_staging_preflight", ["python", "scripts\\commercial_delivery_owner_staging_preflight.py"]),
        ("owner_post_staging_verifier", ["python", "scripts\\commercial_delivery_owner_post_staging_verifier.py"]),
        ("task_board_before_owner_decision", ["python", "scripts\\commercial_delivery_task_board.py"]),
        ("owner_command_audit", ["python", "scripts\\commercial_delivery_owner_command_audit.py"]),
        ("owner_decision_brief", ["python", "scripts\\commercial_delivery_owner_decision_brief.py"]),
        ("owner_pre_stage_readiness_gate", ["python", "scripts\\commercial_delivery_owner_pre_stage_readiness_gate.py"]),
        ("owner_staging_runbook", ["python", "scripts\\commercial_delivery_owner_staging_runbook.py"]),
        ("owner_post_stage_commit_gate", ["python", "scripts\\commercial_delivery_owner_post_stage_commit_gate.py"]),
        ("owner_commit_packet", ["python", "scripts\\commercial_delivery_owner_commit_packet.py"]),
        ("owner_staging_rollback_plan", ["python", "scripts\\commercial_delivery_owner_staging_rollback_plan.py"]),
        ("owner_delivery_packet_before_owner_approval", ["python", "scripts\\commercial_delivery_owner_delivery_packet.py"]),
        ("owner_stage_approval_request", ["python", "scripts\\commercial_delivery_owner_stage_approval_request.py"]),
        ("owner_approval_payload_audit", ["python", "scripts\\commercial_delivery_owner_approval_payload_audit.py"]),
        ("owner_stage_approval_gate", ["python", "scripts\\commercial_delivery_owner_stage_approval_gate.py"]),
        ("owner_stage_approval_brief", ["python", "scripts\\commercial_delivery_owner_stage_approval_brief.py"]),
        ("owner_stage_execution_plan", ["python", "scripts\\commercial_delivery_owner_stage_execution_plan.py"]),
        ("owner_delivery_packet", ["python", "scripts\\commercial_delivery_owner_delivery_packet.py"]),
        ("closure_snapshot", ["python", "scripts\\commercial_delivery_closure_snapshot.py"]),
        ("owner_approval_handoff", ["python", "scripts\\commercial_delivery_owner_approval_handoff.py"]),
        ("pre_approval_drift_guard", ["python", "scripts\\commercial_delivery_pre_approval_drift_guard.py"]),
        ("owner_approval_resume_packet", ["python", "scripts\\commercial_delivery_owner_approval_resume_packet.py"]),
        (
            "owner_post_approval_operator_checklist",
            ["python", "scripts\\commercial_delivery_owner_post_approval_operator_checklist.py"],
        ),
        ("task_board_after_owner_decision", ["python", "scripts\\commercial_delivery_task_board.py"]),
        (
            "commercial_delivery_report_count_alias_normalization",
            [
                "python",
                "scripts\\normalize_report_count_aliases.py",
                "--include-glob",
                "commercial-delivery-*.json",
                "--output",
                ".xagent_runtime\\reports\\commercial-delivery-report-count-alias-normalization.json",
            ],
        ),
        (
            "commercial_delivery_report_hygiene",
            [
                "python",
                "scripts\\check_report_hygiene.py",
                "--include-glob",
                "commercial-delivery-*.json",
                "--output",
                ".xagent_runtime\\reports\\commercial-delivery-report-hygiene.json",
            ],
        ),
    ]


def _step_report_paths(reports_dir: Path) -> dict[str, Path]:
    return {
        "original_kernel_manifest": reports_dir / "original-kernel-delivery-manifest.json",
        "control_modes_preservation": reports_dir / "commercial-delivery-control-modes-preservation.json",
        "staging_review": reports_dir / "commercial-delivery-staging-review.json",
        "owner_staging_packet": reports_dir / "commercial-delivery-owner-staging-packet.json",
        "owner_staging_preflight": reports_dir / "commercial-delivery-owner-staging-preflight.json",
        "owner_post_staging_verifier": reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        "task_board_before_owner_decision": reports_dir / "commercial-delivery-task-board.json",
        "owner_command_audit": reports_dir / "commercial-delivery-owner-command-audit.json",
        "owner_decision_brief": reports_dir / "commercial-delivery-owner-decision-brief.json",
        "owner_pre_stage_readiness_gate": reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        "owner_staging_runbook": reports_dir / "commercial-delivery-owner-staging-runbook.json",
        "owner_stage_approval_gate": reports_dir / "commercial-delivery-owner-stage-approval-gate.json",
        "owner_post_stage_commit_gate": reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        "owner_commit_packet": reports_dir / "commercial-delivery-owner-commit-packet.json",
        "owner_staging_rollback_plan": reports_dir / "commercial-delivery-owner-staging-rollback-plan.json",
        "owner_delivery_packet_before_owner_approval": reports_dir / "commercial-delivery-owner-delivery-packet.json",
        "owner_delivery_packet": reports_dir / "commercial-delivery-owner-delivery-packet.json",
        "owner_stage_approval_request": reports_dir / "commercial-delivery-owner-stage-approval-request.json",
        "owner_approval_payload_audit": reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        "owner_stage_approval_brief": reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        "owner_stage_execution_plan": reports_dir / "commercial-delivery-owner-stage-execution-plan.json",
        "owner_approval_handoff": reports_dir / "commercial-delivery-owner-approval-handoff.json",
        "closure_snapshot": reports_dir / "commercial-delivery-closure-snapshot.json",
        "pre_approval_drift_guard": reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        "owner_approval_resume_packet": reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        "owner_post_approval_operator_checklist": reports_dir
        / "commercial-delivery-owner-post-approval-operator-checklist.json",
        "task_board_after_owner_decision": reports_dir / "commercial-delivery-task-board.json",
        "commercial_delivery_report_count_alias_normalization": reports_dir
        / "commercial-delivery-report-count-alias-normalization.json",
        "commercial_delivery_report_hygiene": reports_dir / "commercial-delivery-report-hygiene.json",
    }


def _final_report_paths(reports_dir: Path) -> dict[str, Path]:
    return {
        "original_kernel_manifest": reports_dir / "original-kernel-delivery-manifest.json",
        "control_modes_preservation": reports_dir / "commercial-delivery-control-modes-preservation.json",
        "staging_review": reports_dir / "commercial-delivery-staging-review.json",
        "owner_staging_packet": reports_dir / "commercial-delivery-owner-staging-packet.json",
        "owner_staging_preflight": reports_dir / "commercial-delivery-owner-staging-preflight.json",
        "owner_post_staging_verifier": reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        "task_board": reports_dir / "commercial-delivery-task-board.json",
        "owner_command_audit": reports_dir / "commercial-delivery-owner-command-audit.json",
        "owner_decision_brief": reports_dir / "commercial-delivery-owner-decision-brief.json",
        "owner_pre_stage_readiness_gate": reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        "owner_staging_runbook": reports_dir / "commercial-delivery-owner-staging-runbook.json",
        "owner_stage_approval_gate": reports_dir / "commercial-delivery-owner-stage-approval-gate.json",
        "owner_post_stage_commit_gate": reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        "owner_commit_packet": reports_dir / "commercial-delivery-owner-commit-packet.json",
        "owner_staging_rollback_plan": reports_dir / "commercial-delivery-owner-staging-rollback-plan.json",
        "owner_delivery_packet": reports_dir / "commercial-delivery-owner-delivery-packet.json",
        "owner_stage_approval_request": reports_dir / "commercial-delivery-owner-stage-approval-request.json",
        "owner_approval_payload_audit": reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        "owner_stage_approval_brief": reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        "owner_stage_execution_plan": reports_dir / "commercial-delivery-owner-stage-execution-plan.json",
        "owner_approval_handoff": reports_dir / "commercial-delivery-owner-approval-handoff.json",
        "closure_snapshot": reports_dir / "commercial-delivery-closure-snapshot.json",
        "pre_approval_drift_guard": reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        "owner_approval_resume_packet": reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        "owner_post_approval_operator_checklist": reports_dir
        / "commercial-delivery-owner-post-approval-operator-checklist.json",
        "commercial_delivery_report_count_alias_normalization": reports_dir
        / "commercial-delivery-report-count-alias-normalization.json",
        "commercial_delivery_report_hygiene": reports_dir / "commercial-delivery-report-hygiene.json",
    }


def _run_command(command: list[str], timeout_seconds: float) -> CommandRunResult:
    actual_command = [sys.executable, *command[1:]] if command and command[0] == "python" else command
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            actual_command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandRunResult(
            command=command,
            returncode=124,
            duration_seconds=round(time.perf_counter() - started, 3),
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            timed_out=True,
        )
    return CommandRunResult(
        command=command,
        returncode=completed.returncode,
        duration_seconds=round(time.perf_counter() - started, 3),
        stdout=completed.stdout,
        stderr=completed.stderr,
        timed_out=False,
    )


def _is_expected_pre_staging_post_verifier_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "owner_post_staging_verifier"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_post_staging_verification_blocked"
        and int(report_payload.get("cached_staged_path_count") or 0) == 0
    )


def _is_expected_pre_staging_commit_gate_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "owner_post_stage_commit_gate"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_post_stage_commit_gate_blocked"
        and int(_read_summary_value(report_payload, "cached_staged_path_count") or 0) == 0
    )


def _is_expected_pre_staging_commit_packet_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "owner_commit_packet"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_commit_packet_blocked"
        and int(_read_summary_value(report_payload, "cached_staged_path_count") or 0) == 0
    )


def _is_expected_pre_staging_approval_gate_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "owner_stage_approval_gate"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_stage_approval_blocked"
        and report_payload.get("stage_allowed") is not True
    )


def _is_expected_pre_staging_approval_payload_audit_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "owner_approval_payload_audit"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_approval_payload_blocked"
        and report_payload.get("approval_payload_present") is False
        and report_payload.get("ready_for_approval_gate") is not True
    )


def _is_expected_post_commit_approval_payload_audit_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    failed_checks = _failed_check_names(report_payload)
    post_commit_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
        "approval_counts_match_request_and_delivery_packet",
        "approval_digests_match_request_and_delivery_packet",
    }
    pre_approval_bootstrap_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
    }
    pre_approval_digest_delta_failed_checks = pre_approval_bootstrap_failed_checks | {
        "approval_digests_match_request_and_delivery_packet",
    }
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    approval_stage_include_count = int(_read_summary_value(report_payload, "approval_stage_include_count") or 0)
    approval_owner_stage_command_count = int(
        _read_summary_value(report_payload, "approval_owner_stage_command_count") or 0
    )
    historical_approval_payload_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
        "approval_counts_match_request_and_delivery_packet",
        "approval_digests_match_request_and_delivery_packet",
    }
    post_commit_noop_approval_delta_checks = {
        "approval_counts_match_request_and_delivery_packet",
        "approval_digests_match_request_and_delivery_packet",
    }
    historical_approval_count_delta_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
        "approval_counts_match_request_and_delivery_packet",
    }
    historical_approval_count_and_digest_delta_failed_checks = historical_approval_count_delta_failed_checks | {
        "approval_digests_match_request_and_delivery_packet",
    }
    return (
        (
            step_name == "owner_approval_payload_audit"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_payload_blocked"
            and report_payload.get("approval_payload_present") is True
            and report_payload.get("ready_for_approval_gate") is False
            and report_payload.get("mutation_performed") is not True
            and report_payload.get("git_stage_performed") is not True
            and report_payload.get("git_commit_performed") is not True
            and report_payload.get("git_push_performed") is not True
            and report_payload.get("network_mutation_performed") is not True
            and report_payload.get("agent_execution_enabled") is not True
            and report_payload.get("full_codex_parity_claimed") is not True
            and stage_include_count > 0
            and owner_stage_command_count > 0
            and owner_stage_command_count <= stage_include_count
            and approval_stage_include_count == stage_include_count
            and approval_owner_stage_command_count == owner_stage_command_count
            and _read_summary_value(report_payload, "commit_command_preview")
            == _read_summary_value(report_payload, "approval_commit_command_preview")
            and isinstance(_read_summary_value(report_payload, "approval_stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"))) == 64
            and (
                failed_checks == post_commit_failed_checks
                or failed_checks == pre_approval_bootstrap_failed_checks
            )
        )
        or (
            step_name == "owner_approval_payload_audit"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_payload_blocked"
            and report_payload.get("approval_payload_present") is True
            and report_payload.get("ready_for_approval_gate") is False
            and _is_post_commit_noop_context(report_payload)
            and approval_stage_include_count == stage_include_count
            and approval_owner_stage_command_count > owner_stage_command_count
            and isinstance(_read_summary_value(report_payload, "approval_stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"))) == 64
            and _read_summary_value(report_payload, "approval_stage_path_digest") != _read_summary_value(
                report_payload,
                "stage_path_digest",
            )
            and failed_checks == historical_approval_payload_failed_checks
        )
        or (
            step_name == "owner_approval_payload_audit"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_payload_blocked"
            and report_payload.get("approval_payload_present") is True
            and report_payload.get("ready_for_approval_gate") is False
            and _has_no_mutation_side_effects(report_payload)
            and stage_include_count > 0
            and owner_stage_command_count > 0
            and owner_stage_command_count <= stage_include_count
            and approval_stage_include_count == stage_include_count
            and approval_owner_stage_command_count > 0
            and approval_owner_stage_command_count < owner_stage_command_count
            and _read_summary_value(report_payload, "commit_command_preview")
            == _read_summary_value(report_payload, "approval_commit_command_preview")
            and isinstance(_read_summary_value(report_payload, "stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "expected_stage_path_set_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"))) == 64
            and (
                failed_checks == historical_approval_count_delta_failed_checks
                or (
                    failed_checks == historical_approval_count_and_digest_delta_failed_checks
                    and (
                        _read_summary_value(report_payload, "approval_stage_path_digest")
                        != _read_summary_value(report_payload, "stage_path_digest")
                        or _read_summary_value(report_payload, "approval_stage_command_digest")
                        != _read_summary_value(report_payload, "stage_command_digest")
                        or _read_summary_value(report_payload, "approval_expected_stage_path_set_digest")
                        != _read_summary_value(report_payload, "expected_stage_path_set_digest")
                    )
                )
            )
        )
        or (
            step_name == "owner_approval_payload_audit"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_payload_blocked"
            and report_payload.get("approval_payload_present") is True
            and report_payload.get("ready_for_approval_gate") is False
            and _has_no_mutation_side_effects(report_payload)
            and stage_include_count > 0
            and owner_stage_command_count > 0
            and owner_stage_command_count <= stage_include_count
            and approval_stage_include_count == stage_include_count
            and approval_owner_stage_command_count == owner_stage_command_count
            and _read_summary_value(report_payload, "commit_command_preview")
            == _read_summary_value(report_payload, "approval_commit_command_preview")
            and isinstance(_read_summary_value(report_payload, "stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "expected_stage_path_set_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"))) == 64
            and (
                _read_summary_value(report_payload, "approval_stage_path_digest")
                != _read_summary_value(report_payload, "stage_path_digest")
                or _read_summary_value(report_payload, "approval_stage_command_digest")
                != _read_summary_value(report_payload, "stage_command_digest")
                or _read_summary_value(report_payload, "approval_expected_stage_path_set_digest")
                != _read_summary_value(report_payload, "expected_stage_path_set_digest")
            )
            and failed_checks == pre_approval_digest_delta_failed_checks
        )
        or (
            step_name == "owner_approval_payload_audit"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_payload_blocked"
            and report_payload.get("approval_payload_present") is True
            and report_payload.get("ready_for_approval_gate") is False
            and _has_no_mutation_side_effects(report_payload)
            and stage_include_count > 0
            and owner_stage_command_count > 0
            and owner_stage_command_count <= stage_include_count
            and approval_stage_include_count == stage_include_count
            and approval_owner_stage_command_count > owner_stage_command_count
            and _read_summary_value(report_payload, "commit_command_preview")
            == _read_summary_value(report_payload, "approval_commit_command_preview")
            and isinstance(_read_summary_value(report_payload, "stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "expected_stage_path_set_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"))) == 64
            and (
                _read_summary_value(report_payload, "approval_stage_path_digest")
                != _read_summary_value(report_payload, "stage_path_digest")
                or _read_summary_value(report_payload, "approval_stage_command_digest")
                != _read_summary_value(report_payload, "stage_command_digest")
                or _read_summary_value(report_payload, "approval_expected_stage_path_set_digest")
                != _read_summary_value(report_payload, "expected_stage_path_set_digest")
            )
            and failed_checks == historical_approval_payload_failed_checks
        )
        or (
            step_name == "owner_approval_payload_audit"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_payload_blocked"
            and report_payload.get("approval_payload_present") is True
            and report_payload.get("ready_for_approval_gate") is False
            and _is_post_commit_noop_context(report_payload)
            and approval_stage_include_count == stage_include_count
            and approval_owner_stage_command_count > owner_stage_command_count
            and isinstance(_read_summary_value(report_payload, "approval_stage_path_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_path_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_stage_command_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_stage_command_digest"))) == 64
            and isinstance(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"), str)
            and len(str(_read_summary_value(report_payload, "approval_expected_stage_path_set_digest"))) == 64
            and failed_checks == post_commit_noop_approval_delta_checks
        )
    )


def _summary_int(payload: dict[str, Any], key: str) -> int:
    try:
        return int(_read_summary_value(payload, key) or 0)
    except (TypeError, ValueError):
        return 0


def _has_no_mutation_side_effects(payload: dict[str, Any]) -> bool:
    return (
        payload.get("mutation_performed") is not True
        and payload.get("git_stage_performed") is not True
        and payload.get("git_commit_performed") is not True
        and payload.get("git_push_performed") is not True
        and payload.get("network_mutation_performed") is not True
        and payload.get("agent_execution_enabled") is not True
        and payload.get("full_codex_parity_claimed") is not True
    )


def _post_approval_resume_ready(report_payload: dict[str, Any]) -> bool:
    return (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_ready"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is True
    )


def _post_approval_operator_ready(report_payload: dict[str, Any]) -> bool:
    return (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is True
    )


def _post_approval_resume_accounted_for(report_payload: dict[str, Any]) -> bool:
    return _post_approval_resume_ready(report_payload) or (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
    )


def _post_approval_operator_accounted_for(report_payload: dict[str, Any]) -> bool:
    return _post_approval_operator_ready(report_payload) or (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
    )


def _is_post_commit_noop_context(report_payload: dict[str, Any]) -> bool:
    stage_path_digest = _read_summary_value(report_payload, "stage_path_digest")
    stage_command_digest = _read_summary_value(report_payload, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(report_payload, "expected_stage_path_set_digest")
    return (
        _has_no_mutation_side_effects(report_payload)
        and _summary_int(report_payload, "stage_include_count") > 0
        and _summary_int(report_payload, "owner_stage_command_count") == 0
        and (
            _summary_int(report_payload, "eligible_stage_count") == 0
            or _read_summary_value(report_payload, "post_commit_noop_accounted_for") is True
            or _read_summary_value(report_payload, "post_commit_noop_resume_ready") is True
        )
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
    )


def _is_post_commit_noop_count_context(
    report_payload: dict[str, Any],
    *,
    command_count_key: str = "owner_stage_command_count",
) -> bool:
    return (
        _has_no_mutation_side_effects(report_payload)
        and _summary_int(report_payload, "stage_include_count") > 0
        and _summary_int(report_payload, command_count_key) == 0
    )


def _historical_approval_payload_present(report_payload: dict[str, Any]) -> bool:
    return (
        _read_summary_value(report_payload, "owner_approval_payload_present") is True
        or report_payload.get("approval_payload_present") is True
    )


def _post_commit_noop_owner_approval_boundary_blocked(report_payload: dict[str, Any]) -> bool:
    return (
        _is_post_commit_noop_context(report_payload)
        and _historical_approval_payload_present(report_payload)
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        in {"owner_stage_approval_blocked", "owner_stage_approval_ready"}
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        in {"owner_stage_execution_blocked", "owner_stage_execution_ready"}
    )


def _post_commit_noop_task_board_guard_bootstrap(report_payload: dict[str, Any]) -> bool:
    return (
        _is_post_commit_noop_count_context(report_payload)
        and (
            _status(report_payload) == "commercial_delivery_blocked"
            or _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
        )
        and (
            _historical_approval_payload_present(report_payload)
            or _read_summary_value(report_payload, "owner_approval_handoff_status")
            == "owner_approval_handoff_blocked"
            or _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            in {"owner_approval_payload_blocked", "owner_approval_payload_ready"}
            or _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
        )
        and (
            _read_summary_value(report_payload, "pre_approval_drift_guard_status")
            in {None, "pre_approval_drift_guard_blocked"}
        )
    )


def _post_commit_noop_stale_operator_boundary(report_payload: dict[str, Any]) -> bool:
    return (
        _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
        and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
        is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
    )


def _post_commit_noop_owner_approval_stale_task_board_state(report_payload: dict[str, Any]) -> bool:
    failed_checks = _failed_check_names(report_payload)
    task_board_blocked = (
        _status(report_payload) == "commercial_delivery_blocked"
        or _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
        or "task_board_ready" in failed_checks
        or "task_board_ready_for_owner_review" in failed_checks
    )
    return (
        _is_post_commit_noop_count_context(report_payload)
        and task_board_blocked
        and _historical_approval_payload_present(report_payload)
        and _read_summary_value(report_payload, "post_commit_noop_accounted_for") is True
        and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
        == "pre_approval_drift_guard_blocked"
        and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
        and _post_commit_noop_stale_operator_boundary(report_payload)
    )


def _is_expected_refresh_bootstrap_task_board_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name in {"task_board_before_owner_decision", "task_board_after_owner_decision"}
        and command_result.returncode != 0
        and _status(report_payload) == "commercial_delivery_blocked"
        and _has_no_mutation_side_effects(report_payload)
        and _read_summary_value(report_payload, "refresh_chain_receipt_status")
        in {
            "commercial_delivery_refresh_chain_receipt_blocked",
            "commercial_delivery_refresh_chain_receipt_ready",
        }
        and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
        == "pre_approval_drift_guard_blocked"
        and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
        and _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for")
        in {False, True}
        and (
            (
                _summary_int(report_payload, "stage_include_count") > 0
                and _summary_int(report_payload, "owner_stage_command_count") > 0
            )
            or (
                _is_post_commit_noop_context(report_payload)
                and _post_approval_resume_accounted_for(report_payload)
                and _post_approval_operator_accounted_for(report_payload)
            )
            or (
                _post_commit_noop_task_board_guard_bootstrap(report_payload)
                and _post_approval_resume_accounted_for(report_payload)
                and _post_approval_operator_accounted_for(report_payload)
            )
        )
        and _failed_check_names(report_payload) == {"pre_approval_drift_guard_ready"}
    )


def _is_expected_post_commit_stage_approval_brief_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    failed_checks = _failed_check_names(report_payload)
    allowed_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
        "approval_request_counts_match_delivery_packet",
        "refresh_chain_ready",
        "task_board_ready_for_owner_review",
    }
    required_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
    }
    noop_refresh_bootstrap_checks = {"refresh_chain_ready"}
    task_board_bootstrap_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
        "task_board_ready_for_owner_review",
    }
    refresh_ready_bootstrap_checks = {"refresh_chain_ready"}
    post_commit_noop_blocked_checks = {
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
    }
    post_commit_noop_task_board_blocked_checks = {
        "task_board_ready_for_owner_review",
        "refresh_chain_ready",
    }
    return (
        (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_blocked"
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            in {
                "owner_stage_execution_ready",
                "owner_stage_execution_blocked",
            }
            and _read_summary_value(report_payload, "stage_allowed") is False
            and _read_summary_value(report_payload, "approval_required") is True
            and _read_summary_value(report_payload, "control_modes_preservation_status")
            == "control_modes_preservation_ready"
            and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
            and _read_summary_value(report_payload, "control_modes_loop_phases")
            == ["explore", "plan", "edit", "verify", "deliver"]
            and isinstance(_read_summary_value(report_payload, "approval_payload_path"), str)
            and isinstance(_read_summary_value(report_payload, "template_output_path"), str)
            and _summary_int(report_payload, "stage_include_count") > 0
            and _summary_int(report_payload, "owner_stage_command_count") > 0
            and _read_summary_value(report_payload, "stage_path_digest")
            == _read_summary_value(report_payload, "request_stage_path_digest")
            and _read_summary_value(report_payload, "stage_command_digest")
            == _read_summary_value(report_payload, "request_stage_command_digest")
            and _read_summary_value(report_payload, "expected_stage_path_set_digest")
            == _read_summary_value(report_payload, "request_expected_stage_path_set_digest")
            and required_failed_checks.issubset(failed_checks)
            and failed_checks.issubset(allowed_failed_checks)
        )
        or (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_ready"
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_ready"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_ready"
            and _read_summary_value(report_payload, "stage_allowed") is True
            and _read_summary_value(report_payload, "approval_required") is True
            and _read_summary_value(report_payload, "control_modes_preservation_status")
            == "control_modes_preservation_ready"
            and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
            and _read_summary_value(report_payload, "control_modes_loop_phases")
            == ["explore", "plan", "edit", "verify", "deliver"]
            and isinstance(_read_summary_value(report_payload, "approval_payload_path"), str)
            and isinstance(_read_summary_value(report_payload, "template_output_path"), str)
            and _summary_int(report_payload, "stage_include_count") > 0
            and _summary_int(report_payload, "owner_stage_command_count") == 0
            and _read_summary_value(report_payload, "stage_path_digest")
            == _read_summary_value(report_payload, "request_stage_path_digest")
            and _read_summary_value(report_payload, "stage_command_digest")
            == _read_summary_value(report_payload, "request_stage_command_digest")
            and _read_summary_value(report_payload, "expected_stage_path_set_digest")
            == _read_summary_value(report_payload, "request_expected_stage_path_set_digest")
            and failed_checks == noop_refresh_bootstrap_checks
        )
        or (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_blocked"
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and _read_summary_value(report_payload, "stage_allowed") is False
            and _summary_int(report_payload, "stage_include_count") > 0
            and _summary_int(report_payload, "owner_stage_command_count") > 0
            and failed_checks == task_board_bootstrap_checks
        )
        or (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_ready"
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_ready"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            in {"owner_stage_execution_ready", "owner_stage_execution_blocked"}
            and _read_summary_value(report_payload, "stage_allowed") is True
            and _summary_int(report_payload, "stage_include_count") > 0
            and _summary_int(report_payload, "owner_stage_command_count") > 0
            and failed_checks == refresh_ready_bootstrap_checks
        )
        or (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _post_commit_noop_owner_approval_boundary_blocked(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_blocked"
            and _read_summary_value(report_payload, "stage_allowed") is False
            and _read_summary_value(report_payload, "stage_path_digest")
            == _read_summary_value(report_payload, "request_stage_path_digest")
            and _read_summary_value(report_payload, "stage_command_digest")
            == _read_summary_value(report_payload, "request_stage_command_digest")
            and _read_summary_value(report_payload, "expected_stage_path_set_digest")
            == _read_summary_value(report_payload, "request_expected_stage_path_set_digest")
            and _read_summary_value(report_payload, "control_modes_preservation_status")
            == "control_modes_preservation_ready"
            and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
            and _read_summary_value(report_payload, "control_modes_loop_phases")
            == ["explore", "plan", "edit", "verify", "deliver"]
            and failed_checks == post_commit_noop_blocked_checks
        )
        or (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_ready"
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            in {"owner_stage_execution_ready", "owner_stage_execution_blocked"}
            and _read_summary_value(report_payload, "stage_allowed") is False
            and _read_summary_value(report_payload, "approval_required") is True
            and _summary_int(report_payload, "stage_include_count") > 0
            and _summary_int(report_payload, "owner_stage_command_count") == 0
            and _read_summary_value(report_payload, "stage_path_digest")
            == _read_summary_value(report_payload, "request_stage_path_digest")
            and _read_summary_value(report_payload, "stage_command_digest")
            == _read_summary_value(report_payload, "request_stage_command_digest")
            and _read_summary_value(report_payload, "expected_stage_path_set_digest")
            == _read_summary_value(report_payload, "request_expected_stage_path_set_digest")
            and _read_summary_value(report_payload, "control_modes_preservation_status")
            == "control_modes_preservation_ready"
            and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
            and _read_summary_value(report_payload, "control_modes_loop_phases")
            == ["explore", "plan", "edit", "verify", "deliver"]
            and failed_checks == post_commit_noop_task_board_blocked_checks
        )
        or (
            step_name == "owner_stage_approval_brief"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_brief_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and _is_post_commit_noop_context(report_payload)
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            == "owner_stage_approval_request_blocked"
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and _read_summary_value(report_payload, "stage_allowed") is False
            and _read_summary_value(report_payload, "approval_required") is True
            and _read_summary_value(report_payload, "stage_path_digest")
            == _read_summary_value(report_payload, "request_stage_path_digest")
            and _read_summary_value(report_payload, "stage_command_digest")
            == _read_summary_value(report_payload, "request_stage_command_digest")
            and _read_summary_value(report_payload, "expected_stage_path_set_digest")
            == _read_summary_value(report_payload, "request_expected_stage_path_set_digest")
            and _read_summary_value(report_payload, "control_modes_preservation_status")
            == "control_modes_preservation_ready"
            and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
            and _read_summary_value(report_payload, "control_modes_loop_phases")
            == ["explore", "plan", "edit", "verify", "deliver"]
            and failed_checks == post_commit_noop_blocked_checks
        )
    )


def _is_expected_pre_staging_stage_execution_plan_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "owner_stage_execution_plan"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_stage_execution_blocked"
        and report_payload.get("stage_allowed") is not True
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


def _failed_check_details(report_payload: dict[str, Any], check_name: str) -> dict[str, Any]:
    checks = report_payload.get("checks")
    if not isinstance(checks, list):
        return {}
    for check in checks:
        if (
            isinstance(check, dict)
            and check.get("status") == "failed"
            and check.get("name") == check_name
            and isinstance(check.get("details"), dict)
        ):
            return check["details"]
    return {}


def _is_expected_post_staging_preflight_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {"no_cached_staged_paths_before_owner_staging"}
    return (
        step_name == "owner_staging_preflight"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_staging_preflight_blocked"
        and int(report_payload.get("cached_staged_path_count") or 0) > 0
        and report_payload.get("full_codex_parity_claimed") is not True
        and _failed_check_names(report_payload).issubset(allowed_failed_checks)
    )


def _is_expected_post_staging_decision_brief_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "owner_preflight_ready",
        "owner_pre_stage_readiness_gate_ready",
        "owner_approval_boundary_accounted_for",
        "post_staging_not_yet_applied",
    }
    return (
        step_name == "owner_decision_brief"
        and command_result.returncode != 0
        and _status(report_payload) == "blocked_before_owner_staging_decision"
        and _read_summary_value(report_payload, "post_staging_status") == "owner_post_staging_verification_ready"
        and int(_read_summary_value(report_payload, "cached_staged_path_count") or 0) > 0
        and _read_summary_value(report_payload, "owner_pre_stage_readiness_gate_status")
        in {None, "owner_pre_stage_readiness_blocked", "owner_pre_stage_readiness_ready"}
        and report_payload.get("full_codex_parity_claimed") is not True
        and _failed_check_names(report_payload).issubset(allowed_failed_checks)
    )


def _is_expected_post_commit_decision_brief_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "owner_pre_stage_readiness_gate_ready",
        "owner_approval_boundary_accounted_for",
        "stage_commands_match_manifest",
    }
    required_failed_checks = {
        "owner_pre_stage_readiness_gate_ready",
        "owner_approval_boundary_accounted_for",
    }
    failed_checks = _failed_check_names(report_payload)
    resume_packet_accounted_for = (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_ready"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is True
    ) or (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
    )
    operator_checklist_accounted_for = (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is True
    ) or (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
        and _read_summary_value(report_payload, "owner_approval_handoff_status") == "owner_approval_handoff_blocked"
        and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
    )
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    owner_command_audit_command_count = int(_read_summary_value(report_payload, "owner_command_audit_command_count") or 0)
    owner_command_audit_expected_path_count = int(
        _read_summary_value(report_payload, "owner_command_audit_expected_path_count") or 0
    )
    command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count > 0
        and owner_stage_command_count == owner_command_audit_command_count == owner_command_audit_expected_path_count
        and owner_stage_command_count <= stage_include_count
    )
    noop_command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count == owner_command_audit_command_count == owner_command_audit_expected_path_count == 0
    )
    noop_failed_checks = {
        "owner_pre_stage_readiness_gate_ready",
        "owner_approval_boundary_accounted_for",
        "stage_commands_match_manifest",
        "post_staging_not_yet_applied",
    }
    task_board_bootstrap_failed_checks = {
        "owner_pre_stage_readiness_gate_ready",
        "owner_approval_boundary_accounted_for",
        "task_board_ready",
    }
    post_commit_noop_task_board_bootstrap_checks = task_board_bootstrap_failed_checks | {
        "stage_commands_match_manifest",
        "post_staging_not_yet_applied",
    }
    return (
        step_name == "owner_decision_brief"
        and command_result.returncode != 0
        and _status(report_payload) == "blocked_before_owner_staging_decision"
        and _has_no_mutation_side_effects(report_payload)
        and int(_read_summary_value(report_payload, "cached_staged_path_count") or 0) == 0
        and _read_summary_value(report_payload, "owner_pre_stage_readiness_gate_status")
        == "owner_pre_stage_readiness_blocked"
        and resume_packet_accounted_for
        and operator_checklist_accounted_for
        and (
            (
                command_counts_accounted_for
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and required_failed_checks.issubset(failed_checks)
                and failed_checks.issubset(allowed_failed_checks)
            )
            or (
                noop_command_counts_accounted_for
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and failed_checks == noop_failed_checks
            )
            or (
                command_counts_accounted_for
                and _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and failed_checks == task_board_bootstrap_failed_checks
            )
            or (
                noop_command_counts_accounted_for
                and _post_commit_noop_task_board_guard_bootstrap(report_payload)
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and failed_checks == post_commit_noop_task_board_bootstrap_checks
            )
        )
    )


def _is_expected_post_staging_pre_stage_readiness_gate_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "owner_preflight_ready",
        "owner_post_staging_expected_pre_stage_state",
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "owner_approval_resume_packet_accounted_for",
        "operator_checklist_accounted_for",
        "owner_approval_boundary_waiting_or_ready",
        "git_index_empty_before_owner_stage",
    }
    return (
        step_name == "owner_pre_stage_readiness_gate"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_pre_stage_readiness_blocked"
        and _read_summary_value(report_payload, "owner_post_staging_status")
        == "owner_post_staging_verification_ready"
        and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) > 0
        and int(_read_summary_value(report_payload, "owner_preflight_cached_staged_path_count") or 0) > 0
        and report_payload.get("full_codex_parity_claimed") is not True
        and _failed_check_names(report_payload).issubset(allowed_failed_checks)
    )


def _is_expected_post_commit_pre_stage_readiness_gate_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "owner_approval_resume_packet_accounted_for",
        "operator_checklist_accounted_for",
        "owner_approval_boundary_waiting_or_ready",
        "stage_counts_agree",
    }
    required_failed_checks = {
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
    }
    failed_checks = _failed_check_names(report_payload)
    resume_packet_accounted_for = (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_ready"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is True
    ) or (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
    )
    operator_checklist_accounted_for = (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is True
    ) or (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
    )
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    stage_command_count = int(_read_summary_value(report_payload, "stage_command_count") or 0)
    command_counts_accounted_for = (
        stage_include_count > 0 and stage_command_count > 0 and stage_command_count <= stage_include_count
    )
    noop_command_counts_accounted_for = stage_include_count > 0 and stage_command_count == 0
    noop_failed_checks = {
        "owner_post_staging_expected_pre_stage_state",
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "stage_counts_agree",
    }
    task_board_bootstrap_failed_checks = {
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "owner_approval_resume_packet_accounted_for",
        "operator_checklist_accounted_for",
        "owner_approval_boundary_waiting_or_ready",
        "task_board_ready",
    }
    task_board_ready_bootstrap_failed_checks = task_board_bootstrap_failed_checks - {
        "refresh_chain_receipt_ready"
    }
    post_commit_task_board_blocked_checks = {
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "task_board_ready",
    }
    post_commit_noop_task_board_blocked_checks = {
        "owner_post_staging_expected_pre_stage_state",
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "task_board_ready",
        "stage_counts_agree",
    }
    post_commit_noop_failed_checks = {
        "owner_post_staging_expected_pre_stage_state",
        "refresh_chain_receipt_ready",
        "owner_decision_brief_ready",
        "owner_approval_handoff_ready",
        "pre_approval_drift_guard_ready",
        "owner_approval_resume_packet_accounted_for",
        "operator_checklist_accounted_for",
        "owner_approval_boundary_waiting_or_ready",
        "stage_counts_agree",
    }
    post_commit_noop_stale_task_board_checks = (
        post_commit_noop_failed_checks - {"refresh_chain_receipt_ready"}
    ) | {"task_board_ready"}
    return (
        step_name == "owner_pre_stage_readiness_gate"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_pre_stage_readiness_blocked"
        and _has_no_mutation_side_effects(report_payload)
        and int(_read_summary_value(report_payload, "owner_preflight_cached_staged_path_count") or 0) == 0
        and resume_packet_accounted_for
        and operator_checklist_accounted_for
        and (
            (
                _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_blocked"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and command_counts_accounted_for
                and required_failed_checks.issubset(failed_checks)
                and failed_checks.issubset(allowed_failed_checks)
            )
            or (
                _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_blocked"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and command_counts_accounted_for
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_ready"
                and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
                and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_ready"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
                and failed_checks == {"owner_decision_brief_ready"}
            )
            or (
                _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_ready"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and noop_command_counts_accounted_for
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
                and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
                and failed_checks == noop_failed_checks
            )
            or (
                command_counts_accounted_for
                and _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
                and _read_summary_value(report_payload, "refresh_chain_receipt_status")
                == "commercial_delivery_refresh_chain_receipt_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
                and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
                == "owner_approval_resume_packet_blocked"
                and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
                and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
                == "owner_post_approval_operator_checklist_blocked"
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
                is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready")
                is False
                and failed_checks == task_board_bootstrap_failed_checks
            )
            or (
                command_counts_accounted_for
                and _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
                and _read_summary_value(report_payload, "refresh_chain_receipt_status")
                == "commercial_delivery_refresh_chain_receipt_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present")
                is True
                and failed_checks == post_commit_task_board_blocked_checks
            )
            or (
                command_counts_accounted_for
                and _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
                and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
                == "owner_approval_resume_packet_blocked"
                and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
                and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
                == "owner_post_approval_operator_checklist_blocked"
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
                is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready")
                is False
                and failed_checks == task_board_ready_bootstrap_failed_checks
            )
        or (
            noop_command_counts_accounted_for
            and _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_ready"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present")
                is True
                and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
                == "owner_approval_resume_packet_blocked"
                and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
                and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
                == "owner_post_approval_operator_checklist_blocked"
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
                is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready")
                is False
                and failed_checks == post_commit_noop_failed_checks
            )
            or (
                noop_command_counts_accounted_for
                and _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_ready"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_ready"
                and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
                and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present")
                is True
                and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
                == "owner_approval_resume_packet_ready"
                and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
                and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is True
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
                == "owner_post_approval_operator_checklist_ready"
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
                is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready")
                is True
                and failed_checks == (noop_failed_checks - {"owner_approval_handoff_ready"})
            )
            or (
                noop_command_counts_accounted_for
                and _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_ready"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
                and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is False
                and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present")
                is True
                and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
                == "owner_approval_resume_packet_ready"
                and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
                and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is True
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
                == "owner_post_approval_operator_checklist_ready"
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
                is False
                and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready")
                is True
                and failed_checks == noop_failed_checks
            )
            or (
                noop_command_counts_accounted_for
                and _read_summary_value(report_payload, "owner_post_staging_status")
                == "owner_post_staging_verification_ready"
                and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
                and _post_commit_noop_task_board_guard_bootstrap(report_payload)
                and _read_summary_value(report_payload, "owner_approval_handoff_status")
                == "owner_approval_handoff_blocked"
                and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
                and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is False
            and failed_checks == post_commit_noop_task_board_blocked_checks
        )
        or (
            noop_command_counts_accounted_for
            and _read_summary_value(report_payload, "owner_post_staging_status")
            == "owner_post_staging_verification_ready"
            and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
            and _read_summary_value(report_payload, "task_board_status")
            == "commercial_delivery_ready_for_owner_staging_review"
            and _read_summary_value(report_payload, "owner_approval_handoff_status")
            == "owner_approval_handoff_blocked"
            and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
            and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is False
            and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
            == "pre_approval_drift_guard_blocked"
            and _post_commit_noop_stale_operator_boundary(report_payload)
            and _read_summary_value(report_payload, "post_commit_noop_stage_counts_agree") is True
            and failed_checks == (post_commit_noop_failed_checks - {"refresh_chain_receipt_ready"})
        )
        or (
            noop_command_counts_accounted_for
            and _read_summary_value(report_payload, "owner_post_staging_status")
            == "owner_post_staging_verification_ready"
            and int(_read_summary_value(report_payload, "owner_post_staging_cached_staged_path_count") or 0) == 0
            and _read_summary_value(report_payload, "owner_approval_handoff_status")
            == "owner_approval_handoff_blocked"
            and _read_summary_value(report_payload, "owner_approval_handoff_owner_action_required") is True
            and _read_summary_value(report_payload, "owner_approval_handoff_stage_allowed") is False
            and _post_commit_noop_owner_approval_stale_task_board_state(report_payload)
            and _read_summary_value(report_payload, "post_commit_noop_stage_counts_agree") is True
            and failed_checks == post_commit_noop_stale_task_board_checks
        )
    )
    )


def _is_expected_post_staging_runbook_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {"pre_stage_gate_ready"}
    return (
        step_name == "owner_staging_runbook"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_staging_runbook_blocked"
        and _read_summary_value(report_payload, "pre_stage_gate_status") == "owner_pre_stage_readiness_blocked"
        and int(_read_summary_value(report_payload, "stage_command_count") or 0) > 0
        and report_payload.get("mutation_performed") is not True
        and report_payload.get("git_stage_performed") is not True
        and report_payload.get("git_commit_performed") is not True
        and report_payload.get("git_push_performed") is not True
        and report_payload.get("network_mutation_performed") is not True
        and report_payload.get("agent_execution_enabled") is not True
        and report_payload.get("full_codex_parity_claimed") is not True
        and _failed_check_names(report_payload).issubset(allowed_failed_checks)
    )


def _is_expected_post_commit_runbook_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "pre_stage_gate_ready",
        "stage_command_count_matches_gate",
    }
    noop_failed_checks = allowed_failed_checks | {"stage_commands_are_explicit_path_adds"}
    task_board_bootstrap_failed_checks = allowed_failed_checks | {"task_board_ready"}
    failed_checks = _failed_check_names(report_payload)
    stage_command_count = int(_read_summary_value(report_payload, "stage_command_count") or 0)
    pre_stage_gate_status = _read_summary_value(report_payload, "pre_stage_gate_status")
    return (
        step_name == "owner_staging_runbook"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_staging_runbook_blocked"
        and _has_no_mutation_side_effects(report_payload)
        and isinstance(_read_summary_value(report_payload, "commit_command_preview"), str)
        and (
            (
                pre_stage_gate_status == "owner_pre_stage_readiness_blocked"
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and stage_command_count > 0
                and {"pre_stage_gate_ready", "stage_command_count_matches_gate"}.issubset(failed_checks)
                and failed_checks.issubset(allowed_failed_checks)
            )
            or (
                pre_stage_gate_status == "owner_pre_stage_readiness_blocked"
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and stage_command_count == 0
                and failed_checks == noop_failed_checks
            )
            or (
                pre_stage_gate_status == "owner_pre_stage_readiness_ready"
                and _read_summary_value(report_payload, "task_board_status")
                == "commercial_delivery_ready_for_owner_staging_review"
                and stage_command_count == 0
                and failed_checks == {"stage_command_count_matches_gate", "stage_commands_are_explicit_path_adds"}
            )
            or (
                pre_stage_gate_status == "owner_pre_stage_readiness_blocked"
                and stage_command_count > 0
                and _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
                and failed_checks == task_board_bootstrap_failed_checks
            )
            or (
                pre_stage_gate_status == "owner_pre_stage_readiness_blocked"
                and stage_command_count == 0
                and _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
                and failed_checks == task_board_bootstrap_failed_checks | {"stage_commands_are_explicit_path_adds"}
            )
        )
    )


def _is_expected_post_commit_delivery_packet_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "owner_pre_stage_chain_ready",
        "stage_command_count_matches_manifest",
        "refresh_chain_ready",
        "pre_stage_post_stage_blockers_are_expected",
        "owner_stage_approval_request_accounted_for",
        "owner_approval_payload_audit_accounted_for",
    }
    required_failed_checks = {
        "owner_pre_stage_chain_ready",
    }
    failed_checks = _failed_check_names(report_payload)
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    eligible_stage_count = int(_read_summary_value(report_payload, "eligible_stage_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    owner_stage_execution_stage_command_count = int(
        _read_summary_value(report_payload, "owner_stage_execution_stage_command_count") or 0
    )
    rollback_reset_command_count = int(_read_summary_value(report_payload, "rollback_reset_command_count") or 0)
    expected_nonzero_steps = _read_summary_value(report_payload, "expected_nonzero_steps")
    expected_nonzero_step_names = (
        {str(step) for step in expected_nonzero_steps}
        if isinstance(expected_nonzero_steps, list)
        else set()
    )
    self_bootstrap_gate_accounted_for = (
        failed_checks == required_failed_checks
        and _failed_check_details(report_payload, "owner_pre_stage_chain_ready").get(
            "refresh_delivery_bootstrap"
        )
        is True
        and _read_summary_value(report_payload, "owner_stage_approval_request_status")
        == "owner_stage_approval_request_blocked"
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        == "owner_stage_execution_blocked"
        and owner_stage_command_count > 0
        and owner_stage_command_count
        == eligible_stage_count
        == owner_stage_execution_stage_command_count
        == rollback_reset_command_count
        and owner_stage_command_count <= stage_include_count
    )
    post_commit_noop_delivery_packet_accounted_for = (
        _is_post_commit_noop_context(report_payload)
        and _read_summary_value(report_payload, "post_commit_noop_accounted_for") is True
        and _read_summary_value(report_payload, "post_stage_chain_accounted_for") is True
        and _read_summary_value(report_payload, "commit_allowed") is True
        and _read_summary_value(report_payload, "owner_post_stage_commit_gate_status")
        == "owner_post_stage_commit_gate_ready"
        and _read_summary_value(report_payload, "owner_commit_packet_status") == "owner_commit_packet_ready"
        and _read_summary_value(report_payload, "owner_stage_approval_request_status")
        == "owner_stage_approval_request_blocked"
        and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
        == "owner_approval_payload_blocked"
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        == "owner_stage_approval_blocked"
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        == "owner_stage_execution_blocked"
    )
    pre_approval_bootstrap_delivery_packet_accounted_for = (
        step_name == "owner_delivery_packet_before_owner_approval"
        and _read_summary_value(report_payload, "refresh_delivery_bootstrap") is True
        and _read_summary_value(report_payload, "owner_stage_approval_request_status")
        in {
            "owner_stage_approval_request_ready",
            "owner_stage_approval_request_blocked",
        }
        and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
        == "owner_approval_payload_blocked"
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        == "owner_stage_approval_blocked"
        and (
            (
                _read_summary_value(report_payload, "owner_stage_execution_plan_status")
                == "owner_stage_execution_blocked"
                and _read_summary_value(report_payload, "owner_stage_execution_allowed") is False
                and owner_stage_execution_stage_command_count == eligible_stage_count
            )
            or (
                _read_summary_value(report_payload, "owner_stage_execution_plan_status")
                == "owner_stage_execution_ready"
                and _read_summary_value(report_payload, "owner_stage_execution_allowed") is False
                and owner_stage_execution_stage_command_count == 0
            )
        )
        and owner_stage_command_count > 0
        and owner_stage_command_count
        == eligible_stage_count
        == rollback_reset_command_count
        and owner_stage_command_count <= stage_include_count
    )
    historical_approval_payload_delta_delivery_packet_accounted_for = (
        step_name == "owner_delivery_packet_before_owner_approval"
        and _has_no_mutation_side_effects(report_payload)
        and _read_summary_value(report_payload, "owner_stage_approval_request_status")
        == "owner_stage_approval_request_blocked"
        and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
        == "owner_approval_payload_blocked"
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        == "owner_stage_approval_blocked"
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        == "owner_stage_execution_blocked"
        and _read_summary_value(report_payload, "approval_payload_audit_blocked_by_post_stage_commit") is False
        and _read_summary_value(report_payload, "approval_payload_audit_post_commit_noop_accounted_for") is False
        and owner_stage_command_count > 0
        and owner_stage_command_count <= stage_include_count
        and owner_stage_execution_stage_command_count == 0
        and rollback_reset_command_count > 0
    )
    approval_gate_status = _read_summary_value(report_payload, "owner_stage_approval_gate_status")
    stage_allowed = _read_summary_value(report_payload, "stage_allowed")
    approval_gate_accounted_for = (
        approval_gate_status == "owner_stage_approval_ready" and stage_allowed is True
    ) or (
        approval_gate_status == "owner_stage_approval_blocked"
        and stage_allowed is False
        and (
            step_name == "owner_delivery_packet_before_owner_approval"
            or
            "owner_stage_approval_gate" in expected_nonzero_step_names
            or (
                _read_summary_value(report_payload, "owner_stage_approval_request_status")
                == "owner_stage_approval_request_blocked"
                and "owner_stage_approval_request_accounted_for" in failed_checks
            )
            or (
                _read_summary_value(report_payload, "owner_stage_approval_request_status")
                == "owner_stage_approval_request_blocked"
                and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
                == "owner_stage_execution_blocked"
                and "refresh_chain_ready" in failed_checks
            )
            or self_bootstrap_gate_accounted_for
        )
    )
    stage_execution_status = _read_summary_value(report_payload, "owner_stage_execution_plan_status")
    stage_execution_accounted_for = (
        stage_execution_status == "owner_stage_execution_ready"
        and _read_summary_value(report_payload, "owner_stage_execution_allowed") is True
    ) or (
        stage_execution_status == "owner_stage_execution_blocked"
        and _read_summary_value(report_payload, "owner_stage_execution_allowed") is False
        and (
            step_name == "owner_delivery_packet_before_owner_approval"
            or "owner_stage_execution_plan" in expected_nonzero_step_names
            or owner_stage_execution_stage_command_count == eligible_stage_count
        )
    )
    stage_execution_count_accounted_for = (
        owner_stage_execution_stage_command_count == eligible_stage_count
        or (
            stage_execution_status == "owner_stage_execution_blocked"
            and (
                step_name == "owner_delivery_packet_before_owner_approval"
                or "owner_stage_execution_plan" in expected_nonzero_step_names
            )
        )
    )
    stage_path_digest = _read_summary_value(report_payload, "stage_path_digest")
    stage_command_digest = _read_summary_value(report_payload, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(report_payload, "expected_stage_path_set_digest")
    return (
        (
            step_name
            in {
                "owner_delivery_packet_before_owner_approval",
                "owner_delivery_packet",
            }
            and command_result.returncode != 0
            and _status(report_payload) == "owner_delivery_packet_blocked"
            and report_payload.get("mutation_performed") is not True
            and report_payload.get("git_stage_performed") is not True
            and report_payload.get("git_commit_performed") is not True
            and report_payload.get("git_push_performed") is not True
            and report_payload.get("network_mutation_performed") is not True
            and report_payload.get("agent_execution_enabled") is not True
            and report_payload.get("full_codex_parity_claimed") is not True
            and _read_summary_value(report_payload, "owner_staging_runbook_status")
            == "owner_staging_runbook_blocked"
            and _read_summary_value(report_payload, "owner_pre_stage_gate_status")
            == "owner_pre_stage_readiness_blocked"
            and _read_summary_value(report_payload, "owner_post_stage_commit_gate_status")
            == "owner_post_stage_commit_gate_blocked"
            and _read_summary_value(report_payload, "owner_commit_packet_status") == "owner_commit_packet_blocked"
            and approval_gate_accounted_for
            and _read_summary_value(report_payload, "owner_stage_approval_request_status")
            in {
                "owner_stage_approval_request_ready",
                "owner_stage_approval_request_blocked",
            }
            and stage_execution_accounted_for
            and _read_summary_value(report_payload, "owner_staging_rollback_plan_status")
            == "owner_staging_rollback_plan_ready"
            and _read_summary_value(report_payload, "commit_allowed") is False
            and _read_summary_value(report_payload, "rollback_available") is True
            and _read_summary_value(report_payload, "rollback_required") is False
            and _read_summary_value(report_payload, "strict_stage_ready") is False
            and _read_summary_value(report_payload, "post_stage_chain_accounted_for") is False
            and stage_include_count > 0
            and eligible_stage_count > 0
            and stage_execution_count_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and required_failed_checks.issubset(failed_checks)
            and failed_checks.issubset(allowed_failed_checks)
        )
        or (
            step_name == "owner_delivery_packet_before_owner_approval"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_delivery_packet_blocked"
            and post_commit_noop_delivery_packet_accounted_for
            and failed_checks
            == {
                "owner_pre_stage_chain_ready",
                "owner_stage_approval_request_accounted_for",
                "owner_approval_payload_audit_accounted_for",
            }
        )
        or (
            step_name == "owner_delivery_packet_before_owner_approval"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_delivery_packet_blocked"
            and post_commit_noop_delivery_packet_accounted_for
            and failed_checks == {"owner_pre_stage_chain_ready"}
        )
        or (
            command_result.returncode != 0
            and _status(report_payload) == "owner_delivery_packet_blocked"
            and _has_no_mutation_side_effects(report_payload)
            and pre_approval_bootstrap_delivery_packet_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and (
                failed_checks
                == {
                    "owner_pre_stage_chain_ready",
                    "owner_approval_payload_audit_accounted_for",
                }
                or failed_checks
                == {
                    "owner_pre_stage_chain_ready",
                    "owner_approval_payload_audit_accounted_for",
                    "owner_stage_approval_request_accounted_for",
                }
            )
        )
        or (
            command_result.returncode != 0
            and _status(report_payload) == "owner_delivery_packet_blocked"
            and historical_approval_payload_delta_delivery_packet_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and failed_checks
            == {
                "owner_pre_stage_chain_ready",
                "stage_command_count_matches_manifest",
                "pre_stage_post_stage_blockers_are_expected",
                "owner_approval_payload_audit_accounted_for",
            }
        )
    )


def _is_expected_post_commit_stage_approval_request_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_delivery_packet_requires_approval",
        "stage_counts_match_delivery_packet",
    }
    required_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_delivery_packet_requires_approval",
    }
    failed_checks = _failed_check_names(report_payload)
    approval_gate_report_status = _read_report_status_value(report_payload, "owner_stage_approval_gate")
    approval_gate_summary_status = _read_summary_value(report_payload, "owner_stage_approval_gate_status")
    stage_allowed = _read_summary_value(report_payload, "stage_allowed")
    approval_gate_accounted_for = (
        approval_gate_report_status == "owner_stage_approval_ready"
        and approval_gate_summary_status == "owner_stage_approval_ready"
        and stage_allowed is True
    ) or (
        approval_gate_report_status == "owner_stage_approval_blocked"
        and approval_gate_summary_status == "owner_stage_approval_blocked"
        and stage_allowed is False
    )
    stage_path_digest = _read_summary_value(report_payload, "stage_path_digest")
    stage_command_digest = _read_summary_value(report_payload, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(report_payload, "expected_stage_path_set_digest")
    post_commit_noop_failed_checks = {
        "owner_delivery_packet_ready",
        "owner_delivery_packet_requires_approval",
        "stage_counts_match_delivery_packet",
    }
    return (
        (
            step_name == "owner_stage_approval_request"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_request_blocked"
            and report_payload.get("owner_gated") is True
            and report_payload.get("approval_required") is True
            and report_payload.get("mutation_performed") is not True
            and report_payload.get("git_stage_performed") is not True
            and report_payload.get("git_commit_performed") is not True
            and report_payload.get("git_push_performed") is not True
            and report_payload.get("network_mutation_performed") is not True
            and report_payload.get("agent_execution_enabled") is not True
            and report_payload.get("full_codex_parity_claimed") is not True
            and _read_report_status_value(report_payload, "owner_delivery_packet")
            in {"owner_delivery_packet_blocked", "owner_delivery_packet_ready"}
            and approval_gate_accounted_for
            and _read_summary_value(report_payload, "template_identity_placeholders_present") is True
            and isinstance(_read_summary_value(report_payload, "approval_payload_path"), str)
            and isinstance(_read_summary_value(report_payload, "template_output_path"), str)
            and int(_read_summary_value(report_payload, "stage_include_count") or 0) > 0
            and int(_read_summary_value(report_payload, "owner_stage_command_count") or 0) > 0
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and required_failed_checks.issubset(failed_checks)
            and failed_checks.issubset(allowed_failed_checks)
        )
        or (
            step_name == "owner_stage_approval_request"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_stage_approval_request_blocked"
            and report_payload.get("owner_gated") is True
            and report_payload.get("approval_required") is True
            and _is_post_commit_noop_context(report_payload)
            and _read_report_status_value(report_payload, "owner_delivery_packet")
            == "owner_delivery_packet_blocked"
            and approval_gate_report_status == "owner_stage_approval_blocked"
            and approval_gate_summary_status == "owner_stage_approval_blocked"
            and stage_allowed is False
            and failed_checks == post_commit_noop_failed_checks
        )
    )


def _is_expected_pre_staging_closure_snapshot_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    expected_blockers = {
        "owner_stage_approval_gate_not_ready",
        "owner_stage_execution_plan_not_ready",
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    }
    post_approval_expected_blockers = {
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    }
    blockers = report_payload.get("blockers")
    blocker_set = {str(item) for item in blockers} if isinstance(blockers, list) else set()
    allowed_failed_checks = {
        "owner_approval_ready",
        "stage_execution_ready",
        "post_stage_ready",
        "commit_ready",
        "cached_staged_path_set_digest_consistent",
        "pre_approval_drift_guard_ready",
    }
    return (
        step_name == "closure_snapshot"
        and command_result.returncode != 0
        and _status(report_payload) == "commercial_delivery_closure_blocked"
        and report_payload.get("delivery_complete") is False
        and report_payload.get("stage_ready") is True
        and report_payload.get("full_codex_parity_claimed") is not True
        and (expected_blockers.issubset(blocker_set) or post_approval_expected_blockers.issubset(blocker_set))
        and _failed_check_names(report_payload).issubset(allowed_failed_checks)
    )


def _is_expected_post_commit_closure_snapshot_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    expected_blockers = {
        "owner_stage_approval_gate_not_ready",
        "owner_stage_execution_plan_not_ready",
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    }
    post_approval_expected_blockers = {
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    }
    blockers = report_payload.get("blockers")
    blocker_set = {str(item) for item in blockers} if isinstance(blockers, list) else set()
    allowed_failed_checks = {
        "stage_ready",
        "owner_approval_ready",
        "stage_execution_ready",
        "post_stage_ready",
        "commit_ready",
        "task_board_ready",
        "pre_approval_drift_guard_ready",
        "stage_counts_consistent",
        "cached_staged_path_set_digest_consistent",
        "owner_approval_resume_packet_accounted_for",
        "owner_post_approval_operator_checklist_accounted_for",
    }
    failed_checks = _failed_check_names(report_payload)
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    owner_stage_execution_stage_command_count = int(
        _read_summary_value(report_payload, "owner_stage_execution_stage_command_count") or 0
    )
    rollback_reset_command_count = int(_read_summary_value(report_payload, "rollback_reset_command_count") or 0)
    command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count > 0
        and owner_stage_command_count == owner_stage_execution_stage_command_count == rollback_reset_command_count
        and owner_stage_command_count <= stage_include_count
    )
    noop_command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count == owner_stage_execution_stage_command_count == rollback_reset_command_count == 0
        and _read_summary_value(report_payload, "post_commit_noop_accounted_for") is True
    )
    resume_packet_accounted_for = (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_ready"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is True
    ) or (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_real_owner_approval_present") is True
        and _read_summary_value(report_payload, "owner_approval_resume_packet_post_stage_accounted_for") is False
    )
    operator_checklist_accounted_for = (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is True
    ) or (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_post_stage_accounted_for")
        is False
    )
    refresh_bootstrap_accounted_for = (
        _read_summary_value(report_payload, "refresh_chain_ready_for_snapshot") is True
        and _read_summary_value(report_payload, "pre_approval_drift_guard_status")
        == "pre_approval_drift_guard_blocked"
        and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
        and _read_summary_value(report_payload, "task_board_post_commit_accounted_for") is False
    )
    return (
        step_name == "closure_snapshot"
        and command_result.returncode != 0
        and _status(report_payload) == "commercial_delivery_closure_blocked"
        and report_payload.get("delivery_complete") is False
        and report_payload.get("stage_ready") is False
        and _has_no_mutation_side_effects(report_payload)
        and (
            expected_blockers.issubset(blocker_set)
            or post_approval_expected_blockers.issubset(blocker_set)
            or noop_command_counts_accounted_for
        )
        and failed_checks.issubset(allowed_failed_checks)
        and (command_counts_accounted_for or noop_command_counts_accounted_for)
        and (
            (
                {"stage_ready", "owner_approval_ready", "stage_execution_ready", "post_stage_ready", "commit_ready"}.issubset(
                    failed_checks
                )
                and (
                    (
                        _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for") is True
                        and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present")
                        is True
                    )
                    or refresh_bootstrap_accounted_for
                )
                and resume_packet_accounted_for
                and operator_checklist_accounted_for
            )
            or (
                {"stage_ready", "post_stage_ready", "commit_ready"}.issubset(failed_checks)
                and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
                == "owner_approval_payload_ready"
                and _read_report_status_value(report_payload, "owner_approval_payload_audit")
                == "owner_approval_payload_ready"
                and _read_report_status_value(report_payload, "owner_stage_approval_gate")
                == "owner_stage_approval_ready"
                and _read_report_status_value(report_payload, "owner_stage_execution_plan")
                == "owner_stage_execution_ready"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for") is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
                and resume_packet_accounted_for
                and operator_checklist_accounted_for
            )
            or (
                report_payload.get("stage_ready") is True
                and failed_checks == {"task_board_ready"}
                and _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for") is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
                and resume_packet_accounted_for
                and operator_checklist_accounted_for
            )
        )
        and _read_summary_value(report_payload, "refresh_chain_ready_for_snapshot") is True
        and _read_summary_value(report_payload, "control_modes_preservation_status")
        == "control_modes_preservation_ready"
        and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
        and _read_summary_value(report_payload, "control_modes_loop_phases")
        == ["explore", "plan", "edit", "verify", "deliver"]
    )


def _is_expected_post_commit_noop_closure_snapshot_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    return (
        step_name == "closure_snapshot"
        and command_result.returncode != 0
        and _status(report_payload) == "commercial_delivery_closure_blocked"
        and report_payload.get("delivery_complete") is False
        and report_payload.get("stage_ready") is True
        and report_payload.get("commit_ready") is True
        and _has_no_mutation_side_effects(report_payload)
        and _is_post_commit_noop_context(report_payload)
        and _read_summary_value(report_payload, "post_commit_closure_accounted_for") is True
        and _read_summary_value(report_payload, "closure_gate_evidence_ready") is True
        and _read_summary_value(report_payload, "delivery_post_stage_chain_accounted_for") is True
        and _read_summary_value(report_payload, "delivery_post_commit_owner_gate_accounted_for") is True
        and _read_summary_value(report_payload, "delivery_post_commit_stage_approval_accounted_for") is True
        and _read_summary_value(report_payload, "delivery_post_commit_stage_execution_accounted_for") is True
        and _read_summary_value(report_payload, "post_commit_noop_accounted_for") is True
        and _read_summary_value(report_payload, "delivery_noop_stage_counts_accounted_for") is True
        and _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for") is True
        and _post_commit_noop_stale_operator_boundary(report_payload)
        and _read_summary_value(report_payload, "refresh_chain_ready_for_snapshot") is True
        and _read_summary_value(report_payload, "control_modes_preservation_status")
        == "control_modes_preservation_ready"
        and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
        and _read_summary_value(report_payload, "control_modes_loop_phases")
        == ["explore", "plan", "edit", "verify", "deliver"]
        and _failed_check_names(report_payload)
        == {
            "owner_approval_resume_packet_accounted_for",
            "owner_post_approval_operator_checklist_accounted_for",
        }
    )


def _is_expected_owner_approved_pre_stage_closure_snapshot_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    expected_blockers = {
        "owner_stage_approval_gate_not_ready",
        "owner_stage_execution_plan_not_ready",
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    }
    blockers = report_payload.get("blockers")
    blocker_set = {str(item) for item in blockers} if isinstance(blockers, list) else set()
    allowed_failed_checks = {
        "owner_approval_ready",
        "stage_execution_ready",
        "post_stage_ready",
        "commit_ready",
        "pre_approval_drift_guard_ready",
        "owner_approval_resume_packet_accounted_for",
        "owner_post_approval_operator_checklist_accounted_for",
        "cached_staged_path_set_digest_consistent",
    }
    failed_checks = _failed_check_names(report_payload)
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    owner_stage_execution_stage_command_count = int(
        _read_summary_value(report_payload, "owner_stage_execution_stage_command_count") or 0
    )
    rollback_reset_command_count = int(_read_summary_value(report_payload, "rollback_reset_command_count") or 0)
    command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count > 0
        and owner_stage_command_count == owner_stage_execution_stage_command_count == rollback_reset_command_count
        and owner_stage_command_count <= stage_include_count
    )
    resume_packet_stale_blocked = (
        _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_approval_resume_packet_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_resume_ready") is False
        and _read_summary_value(report_payload, "owner_approval_resume_packet_real_owner_approval_present") is True
        and _read_summary_value(report_payload, "owner_approval_resume_packet_post_stage_accounted_for") is False
    )
    operator_checklist_stale_blocked = (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_post_stage_accounted_for")
        is False
    )
    return (
        step_name == "closure_snapshot"
        and command_result.returncode != 0
        and _status(report_payload) == "commercial_delivery_closure_blocked"
        and report_payload.get("delivery_complete") is False
        and report_payload.get("stage_ready") is True
        and report_payload.get("approval_ready") is False
        and report_payload.get("stage_execution_ready") is False
        and report_payload.get("post_stage_ready") is False
        and report_payload.get("commit_ready") is False
        and report_payload.get("rollback_ready") is True
        and report_payload.get("mutation_performed") is not True
        and report_payload.get("git_stage_performed") is not True
        and report_payload.get("git_commit_performed") is not True
        and report_payload.get("git_push_performed") is not True
        and report_payload.get("network_mutation_performed") is not True
        and report_payload.get("agent_execution_enabled") is not True
        and report_payload.get("full_codex_parity_claimed") is not True
        and expected_blockers.issubset(blocker_set)
        and {
            "owner_approval_ready",
            "stage_execution_ready",
            "post_stage_ready",
            "commit_ready",
            "cached_staged_path_set_digest_consistent",
        }.issubset(failed_checks)
        and failed_checks.issubset(allowed_failed_checks)
        and command_counts_accounted_for
        and (
            (
                _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for") is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present") is True
            )
            or (
                _read_summary_value(report_payload, "pre_approval_drift_guard_status")
                == "pre_approval_drift_guard_blocked"
                and _read_summary_value(report_payload, "pre_approval_drift_guard_real_owner_approval_present")
                is True
                and _read_summary_value(report_payload, "pre_approval_drift_guard_accounted_for") is False
            )
        )
        and _read_summary_value(report_payload, "refresh_chain_ready_for_snapshot") is True
        and resume_packet_stale_blocked
        and operator_checklist_stale_blocked
        and _read_summary_value(report_payload, "control_modes_preservation_status")
        == "control_modes_preservation_ready"
        and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
        and _read_summary_value(report_payload, "control_modes_loop_phases")
        == ["explore", "plan", "edit", "verify", "deliver"]
    )


def _is_expected_post_approval_handoff_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    allowed_failed_checks = {
        "approval_payload_audit_pre_approval_blocked",
        "real_owner_approval_not_written_by_handoff",
        "stage_not_allowed_before_owner_approval",
        "operator_checklist_accounted_for",
        "owner_delivery_packet_ready",
        "approval_brief_ready",
        "pre_approval_blockers_accounted_for",
    }
    failed_checks = _failed_check_names(report_payload)
    return (
        step_name == "owner_approval_handoff"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_approval_handoff_blocked"
        and report_payload.get("stage_allowed") is True
        and _has_no_mutation_side_effects(report_payload)
        and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
        == "owner_approval_payload_ready"
        and _read_summary_value(report_payload, "owner_approval_payload_present") is True
        and _read_summary_value(report_payload, "owner_approval_payload_valid") is True
        and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is True
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        == "owner_stage_approval_ready"
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        == "owner_stage_execution_ready"
        and failed_checks.issubset(allowed_failed_checks)
        and (
            (
                report_payload.get("delivery_complete") is True
                and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
            )
            or (
                report_payload.get("delivery_complete") is False
                and _read_summary_value(report_payload, "closure_snapshot_status")
                == "commercial_delivery_closure_blocked"
                and _summary_int(report_payload, "stage_include_count") > 0
                and _summary_int(report_payload, "owner_stage_command_count") > 0
                and _summary_int(report_payload, "owner_stage_command_count")
                == _summary_int(report_payload, "rollback_reset_command_count")
                and {
                    "owner_delivery_packet_ready",
                    "approval_payload_audit_pre_approval_blocked",
                    "real_owner_approval_not_written_by_handoff",
                    "pre_approval_blockers_accounted_for",
                    "stage_not_allowed_before_owner_approval",
                }.issubset(failed_checks)
            )
        )
    )


def _is_expected_post_commit_approval_handoff_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    required_failed_checks = {
        "approval_request_ready",
        "approval_brief_ready",
        "approval_payload_audit_pre_approval_blocked",
        "real_owner_approval_not_written_by_handoff",
    }
    allowed_failed_checks = required_failed_checks | {
        "owner_delivery_packet_ready",
        "operator_checklist_accounted_for",
        "task_board_ready",
        "pre_approval_blockers_accounted_for",
        "stage_not_allowed_before_owner_approval",
    }
    post_commit_noop_historical_approval_checks = {
        "approval_request_ready",
        "approval_brief_ready",
        "approval_payload_audit_pre_approval_blocked",
        "real_owner_approval_not_written_by_handoff",
    }
    post_approval_boundary_historical_approval_checks = post_commit_noop_historical_approval_checks | {
        "owner_delivery_packet_ready",
    }
    failed_checks = _failed_check_names(report_payload)
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    rollback_reset_command_count = int(_read_summary_value(report_payload, "rollback_reset_command_count") or 0)
    command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count > 0
        and owner_stage_command_count == rollback_reset_command_count
        and owner_stage_command_count <= stage_include_count
    )
    noop_command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count == rollback_reset_command_count == 0
        and (
            _read_summary_value(report_payload, "post_approval_noop_accounted_for") is True
            or _post_commit_noop_task_board_guard_bootstrap(report_payload)
        )
    )
    stage_path_digest = _read_summary_value(report_payload, "stage_path_digest")
    stage_command_digest = _read_summary_value(report_payload, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(report_payload, "expected_stage_path_set_digest")
    operator_checklist_accounted_for = (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is True
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
    ) or (
        _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
    )
    return (
        (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is False
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_present") is True
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_closure_blocked"
            and operator_checklist_accounted_for
            and command_counts_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and required_failed_checks.issubset(failed_checks)
            and failed_checks.issubset(allowed_failed_checks)
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is True
            and report_payload.get("delivery_complete") is True
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_ready"
            and _read_summary_value(report_payload, "owner_approval_payload_present") is True
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is True
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is True
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_ready"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_ready"
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
            and operator_checklist_accounted_for
            and noop_command_counts_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and failed_checks == {"approval_brief_ready"}
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is False
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_present") is True
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_closure_blocked"
            and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
            == "owner_post_approval_operator_checklist_blocked"
            and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner")
            is False
            and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
            and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
            is True
            and command_counts_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and {
                "owner_delivery_packet_ready",
                "approval_request_ready",
                "approval_brief_ready",
                "approval_payload_audit_pre_approval_blocked",
                "real_owner_approval_not_written_by_handoff",
                "task_board_ready",
            }.issubset(failed_checks)
            and failed_checks.issubset(allowed_failed_checks)
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is True
            and _has_no_mutation_side_effects(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_present") is True
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
            and operator_checklist_accounted_for
            and command_counts_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and failed_checks == post_approval_boundary_historical_approval_checks
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is True
            and _post_commit_noop_owner_approval_boundary_blocked(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
            and operator_checklist_accounted_for
            and failed_checks == post_commit_noop_historical_approval_checks
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is False
            and _post_commit_noop_task_board_guard_bootstrap(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            in {"owner_stage_execution_ready", "owner_stage_execution_blocked"}
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_closure_blocked"
            and operator_checklist_accounted_for
            and noop_command_counts_accounted_for
            and isinstance(stage_path_digest, str)
            and len(stage_path_digest) == 64
            and isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and isinstance(expected_stage_path_set_digest, str)
            and len(expected_stage_path_set_digest) == 64
            and {
                "approval_brief_ready",
                "approval_payload_audit_pre_approval_blocked",
                "real_owner_approval_not_written_by_handoff",
                "pre_approval_blockers_accounted_for",
                "stage_not_allowed_before_owner_approval",
                "task_board_ready",
            }.issubset(failed_checks)
            and failed_checks.issubset(allowed_failed_checks)
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is False
            and _has_no_mutation_side_effects(report_payload)
            and _is_post_commit_noop_context(report_payload)
            and _historical_approval_payload_present(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and _read_summary_value(report_payload, "closure_snapshot_status")
            == "commercial_delivery_closure_blocked"
            and operator_checklist_accounted_for
            and failed_checks
            == {
                "approval_request_ready",
                "approval_brief_ready",
                "approval_payload_audit_pre_approval_blocked",
                "real_owner_approval_not_written_by_handoff",
                "pre_approval_blockers_accounted_for",
            }
        )
        or (
            step_name == "owner_approval_handoff"
            and command_result.returncode != 0
            and _status(report_payload) == "owner_approval_handoff_blocked"
            and report_payload.get("stage_allowed") is False
            and report_payload.get("delivery_complete") is True
            and _has_no_mutation_side_effects(report_payload)
            and _is_post_commit_noop_context(report_payload)
            and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
            == "owner_approval_payload_blocked"
            and _read_summary_value(report_payload, "owner_approval_payload_present") is True
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_ready"
            and _read_summary_value(report_payload, "closure_snapshot_status")
            == "commercial_delivery_complete"
            and operator_checklist_accounted_for
            and failed_checks
            == {
                "approval_payload_audit_pre_approval_blocked",
                "real_owner_approval_not_written_by_handoff",
                "stage_not_allowed_before_owner_approval",
            }
        )
    )


def _is_expected_post_approval_pre_approval_drift_guard_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
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
    failed_checks = _failed_check_names(report_payload)
    return (
        step_name == "pre_approval_drift_guard"
        and command_result.returncode != 0
        and _status(report_payload) == "pre_approval_drift_guard_blocked"
        and report_payload.get("real_owner_approval_present") is True
        and report_payload.get("mutation_performed") is not True
        and report_payload.get("git_stage_performed") is not True
        and report_payload.get("git_commit_performed") is not True
        and report_payload.get("git_push_performed") is not True
        and report_payload.get("network_mutation_performed") is not True
        and report_payload.get("agent_execution_enabled") is not True
        and report_payload.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(report_payload, "owner_approval_payload_audit")
        == "owner_approval_payload_ready"
        and _read_summary_value(report_payload, "owner_approval_payload_present") is True
        and _read_summary_value(report_payload, "owner_approval_payload_valid") is True
        and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is True
        and _read_report_status_value(report_payload, "owner_stage_approval_gate") == "owner_stage_approval_ready"
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status") == "owner_stage_approval_ready"
        and _read_report_status_value(report_payload, "owner_stage_execution_plan") == "owner_stage_execution_ready"
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        == "owner_stage_execution_ready"
        and _read_report_status_value(report_payload, "closure_snapshot") == "commercial_delivery_complete"
        and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
        and _read_summary_value(report_payload, "closure_delivery_complete") is True
        and core_failed_checks.issubset(failed_checks)
        and failed_checks.issubset(allowed_failed_checks)
    )


def _is_expected_post_commit_pre_approval_drift_guard_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    required_failed_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    owner_approved_bootstrap_failed_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
    }
    owner_approved_ready_gate_failed_checks = {
        "real_owner_approval_absent",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "approval_gate_blocked_before_owner",
        "stage_execution_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    post_commit_noop_ready_execution_checks = {
        "real_owner_approval_absent",
        "approval_handoff_ready",
        "approval_payload_blocked_before_owner",
        "stage_execution_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    post_commit_noop_historical_approval_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "stage_path_digest_stable",
        "stage_command_digest_stable",
        "expected_stage_path_set_digest_stable",
        "approval_payload_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
        "closure_blocked_before_owner",
    }
    post_approval_pre_stage_task_board_drift_checks = {
        "real_owner_approval_absent",
        "approval_request_ready",
        "approval_handoff_ready",
        "stage_path_digest_stable",
        "stage_command_digest_stable",
        "expected_stage_path_set_digest_stable",
        "approval_payload_blocked_before_owner",
        "operator_checklist_waiting_before_owner",
    }
    allowed_failed_checks = (
        required_failed_checks
        | owner_approved_ready_gate_failed_checks
        | post_commit_noop_historical_approval_checks
        | post_approval_pre_stage_task_board_drift_checks
        | {"secondary_handoff_summary_stable"}
    )
    failed_checks = _failed_check_names(report_payload)
    stage_path_digest = _read_summary_value(report_payload, "stage_path_digest")
    stage_command_digest = _read_summary_value(report_payload, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(report_payload, "expected_stage_path_set_digest")
    operator_checklist_accounted_for = (
        _read_report_status_value(report_payload, "owner_post_approval_operator_checklist")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_ready"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is True
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
    ) or (
        _read_report_status_value(report_payload, "owner_post_approval_operator_checklist")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_status")
        == "owner_post_approval_operator_checklist_blocked"
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_waiting_for_owner") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_operator_ready") is False
        and _read_summary_value(report_payload, "owner_post_approval_operator_checklist_real_owner_approval_present")
        is True
    )
    common = (
        step_name == "pre_approval_drift_guard"
        and command_result.returncode != 0
        and _status(report_payload) == "pre_approval_drift_guard_blocked"
        and report_payload.get("real_owner_approval_present") is True
        and _has_no_mutation_side_effects(report_payload)
        and _read_report_status_value(report_payload, "owner_stage_approval_request")
        in {"owner_stage_approval_request_blocked", "owner_stage_approval_request_ready"}
        and _read_report_status_value(report_payload, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(report_payload, "owner_approval_payload_audit")
        in {"owner_approval_payload_blocked", "owner_approval_payload_ready"}
        and _read_summary_value(report_payload, "owner_approval_payload_present") is True
        and _read_report_status_value(report_payload, "owner_stage_approval_gate")
        in {"owner_stage_approval_blocked", "owner_stage_approval_ready"}
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        in {"owner_stage_approval_blocked", "owner_stage_approval_ready"}
        and _read_report_status_value(report_payload, "owner_stage_execution_plan")
        in {"owner_stage_execution_blocked", "owner_stage_execution_ready"}
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        in {"owner_stage_execution_blocked", "owner_stage_execution_ready"}
        and operator_checklist_accounted_for
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and failed_checks.issubset(allowed_failed_checks)
    )
    return common and (
        (
            _read_report_status_value(report_payload, "closure_snapshot") == "commercial_delivery_closure_blocked"
            and _read_summary_value(report_payload, "closure_snapshot_status")
            == "commercial_delivery_closure_blocked"
            and _read_summary_value(report_payload, "closure_delivery_complete") is False
            and (
                required_failed_checks.issubset(failed_checks)
                or failed_checks == owner_approved_bootstrap_failed_checks
                or failed_checks == owner_approved_ready_gate_failed_checks
                or failed_checks == post_approval_pre_stage_task_board_drift_checks
            )
        )
        or (
            _read_report_status_value(report_payload, "closure_snapshot") == "commercial_delivery_complete"
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
            and _read_summary_value(report_payload, "closure_delivery_complete") is True
            and _read_summary_value(report_payload, "owner_approval_payload_valid") is False
            and _read_summary_value(report_payload, "owner_approval_payload_ready_for_gate") is False
            and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
            == "owner_stage_approval_blocked"
            and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
            == "owner_stage_execution_blocked"
            and failed_checks == required_failed_checks
        )
        or (
            _read_report_status_value(report_payload, "closure_snapshot") == "commercial_delivery_complete"
            and _read_summary_value(report_payload, "closure_snapshot_status") == "commercial_delivery_complete"
            and _read_summary_value(report_payload, "closure_delivery_complete") is True
            and _post_commit_noop_owner_approval_boundary_blocked(report_payload)
            and failed_checks == post_commit_noop_historical_approval_checks
        )
        or (
            _read_report_status_value(report_payload, "closure_snapshot") == "commercial_delivery_closure_blocked"
            and _read_summary_value(report_payload, "closure_snapshot_status")
            == "commercial_delivery_closure_blocked"
            and _read_summary_value(report_payload, "closure_delivery_complete") is False
            and _post_commit_noop_owner_approval_boundary_blocked(report_payload)
            and failed_checks == post_commit_noop_ready_execution_checks
        )
    )


def _is_expected_post_commit_owner_approval_resume_packet_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    required_failed_checks = {
        "owner_approval_handoff_ready",
        "owner_delivery_packet_ready",
        "owner_staging_runbook_ready",
        "owner_approval_boundary_accounted_for",
        "stage_counts_consistent",
    }
    pre_approval_boundary_failed_checks = required_failed_checks - {"stage_counts_consistent"}
    delivery_ready_bootstrap_failed_checks = {
        "owner_approval_handoff_ready",
        "owner_staging_runbook_ready",
        "owner_approval_boundary_accounted_for",
    }
    owner_approved_ready_gate_failed_checks = {
        "owner_approval_handoff_ready",
        "owner_delivery_packet_ready",
        "owner_staging_runbook_ready",
    }
    task_board_bootstrap_failed_checks = (
        required_failed_checks - {"stage_counts_consistent"}
    ) | {"task_board_ready"}
    allowed_failed_checks = required_failed_checks | {"task_board_ready"}
    failed_checks = _failed_check_names(report_payload)
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    owner_stage_command_count = int(_read_summary_value(report_payload, "owner_stage_command_count") or 0)
    runbook_stage_command_count = int(_read_summary_value(report_payload, "runbook_stage_command_count") or 0)
    execution_plan_stage_command_count = int(
        _read_summary_value(report_payload, "execution_plan_stage_command_count") or 0
    )
    stage_commands_preview_count = int(_read_summary_value(report_payload, "stage_commands_preview_count") or 0)
    command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count > 0
        and owner_stage_command_count
        == runbook_stage_command_count
        == execution_plan_stage_command_count
        == stage_commands_preview_count
        and owner_stage_command_count <= stage_include_count
    )
    noop_command_counts_accounted_for = (
        stage_include_count > 0
        and owner_stage_command_count
        == runbook_stage_command_count
        == execution_plan_stage_command_count
        == stage_commands_preview_count
        == 0
        and _read_summary_value(report_payload, "post_commit_noop_accounted_for") is True
    )
    stage_path_digest = _read_summary_value(report_payload, "stage_path_digest")
    stage_command_digest = _read_summary_value(report_payload, "stage_command_digest")
    expected_stage_path_set_digest = _read_summary_value(report_payload, "expected_stage_path_set_digest")
    return (
        step_name == "owner_approval_resume_packet"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_approval_resume_packet_blocked"
        and report_payload.get("real_owner_approval_present") is True
        and report_payload.get("waiting_for_owner") is False
        and report_payload.get("resume_ready") is False
        and report_payload.get("stage_allowed") in {False, True}
        and report_payload.get("stage_execution_ready") in {False, True}
        and report_payload.get("mutation_performed") is not True
        and report_payload.get("git_stage_performed") is not True
        and report_payload.get("git_commit_performed") is not True
        and report_payload.get("git_push_performed") is not True
        and report_payload.get("network_mutation_performed") is not True
        and report_payload.get("agent_execution_enabled") is not True
        and report_payload.get("full_codex_parity_claimed") is not True
        and _read_report_status_value(report_payload, "owner_approval_handoff") == "owner_approval_handoff_blocked"
        and _read_report_status_value(report_payload, "pre_approval_drift_guard")
        == "pre_approval_drift_guard_blocked"
        and _read_report_status_value(report_payload, "owner_approval_payload_audit")
        in {"owner_approval_payload_blocked", "owner_approval_payload_ready"}
        and _read_report_status_value(report_payload, "owner_stage_approval_gate")
        in {"owner_stage_approval_blocked", "owner_stage_approval_ready"}
        and _read_report_status_value(report_payload, "owner_stage_execution_plan")
        in {"owner_stage_execution_blocked", "owner_stage_execution_ready"}
        and _read_report_status_value(report_payload, "owner_staging_runbook") == "owner_staging_runbook_blocked"
        and _read_report_status_value(report_payload, "owner_staging_rollback_plan")
        == "owner_staging_rollback_plan_ready"
        and _read_report_status_value(report_payload, "owner_post_staging_verifier")
        in {"owner_post_staging_verification_blocked", "owner_post_staging_verification_ready"}
        and _read_report_status_value(report_payload, "owner_post_stage_commit_gate")
        == "owner_post_stage_commit_gate_blocked"
        and _read_report_status_value(report_payload, "owner_commit_packet") == "owner_commit_packet_blocked"
        and _read_report_status_value(report_payload, "owner_delivery_packet")
        in {"owner_delivery_packet_blocked", "owner_delivery_packet_ready"}
        and (
            _read_report_status_value(report_payload, "task_board")
            == "commercial_delivery_ready_for_owner_staging_review"
            or _read_summary_value(report_payload, "task_board_status") == "commercial_delivery_blocked"
        )
        and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
        in {"owner_approval_payload_blocked", "owner_approval_payload_ready"}
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        in {"owner_stage_approval_blocked", "owner_stage_approval_ready"}
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        in {"owner_stage_execution_blocked", "owner_stage_execution_ready"}
        and _read_summary_value(report_payload, "post_stage_resume_evidence_ready") is False
        and _read_summary_value(report_payload, "owner_approval_handoff_post_stage_accounted_for") is False
        and _read_summary_value(report_payload, "owner_staging_runbook_post_stage_accounted_for") is False
        and (command_counts_accounted_for or noop_command_counts_accounted_for)
        and isinstance(stage_path_digest, str)
        and len(stage_path_digest) == 64
        and isinstance(stage_command_digest, str)
        and len(stage_command_digest) == 64
        and isinstance(expected_stage_path_set_digest, str)
        and len(expected_stage_path_set_digest) == 64
        and (
            required_failed_checks.issubset(failed_checks)
            or failed_checks == delivery_ready_bootstrap_failed_checks
            or failed_checks == owner_approved_ready_gate_failed_checks
            or failed_checks == task_board_bootstrap_failed_checks
            or failed_checks == pre_approval_boundary_failed_checks
            or (
                failed_checks == {"task_board_ready"}
                and _post_commit_noop_owner_approval_stale_task_board_state(report_payload)
            )
        )
        and failed_checks.issubset(allowed_failed_checks)
        and (
            report_payload.get("stage_allowed") is False
            or (
                report_payload.get("stage_allowed") is True
                and _read_summary_value(report_payload, "owner_approval_payload_audit_status")
                == "owner_approval_payload_ready"
                and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
                == "owner_stage_approval_ready"
                and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
                == "owner_stage_execution_ready"
            )
        )
    )


def _is_expected_post_commit_owner_post_approval_operator_checklist_state(
    *,
    step_name: str,
    command_result: CommandRunResult,
    report_payload: dict[str, Any],
) -> bool:
    required_failed_checks = {
        "resume_packet_accounted_for",
        "approval_gate_matches_resume",
        "stage_execution_matches_resume",
        "operator_state_accounted_for",
    }
    post_commit_noop_failed_checks = required_failed_checks | {"operator_sequence_present"}
    failed_checks = _failed_check_names(report_payload)
    blocking_reasons = _read_summary_value(report_payload, "blocking_reasons")
    blocking_reason_names = (
        {str(reason) for reason in blocking_reasons}
        if isinstance(blocking_reasons, list)
        else set()
    )
    stage_include_count = int(_read_summary_value(report_payload, "stage_include_count") or 0)
    stage_command_count = int(_read_summary_value(report_payload, "stage_command_count") or 0)
    pre_stage_verification_command_count = int(
        _read_summary_value(report_payload, "pre_stage_verification_command_count") or 0
    )
    post_stage_verification_command_count = int(
        _read_summary_value(report_payload, "post_stage_verification_command_count") or 0
    )
    cached_staged_path_count = _read_summary_value(
        report_payload,
        "owner_staging_preflight_cached_staged_path_count",
    )
    return (
        step_name == "owner_post_approval_operator_checklist"
        and command_result.returncode != 0
        and _status(report_payload) == "owner_post_approval_operator_checklist_blocked"
        and report_payload.get("real_owner_approval_present") is True
        and report_payload.get("waiting_for_owner") is False
        and report_payload.get("operator_ready") is False
        and report_payload.get("mutation_performed") is not True
        and report_payload.get("git_stage_performed") is not True
        and report_payload.get("git_commit_performed") is not True
        and report_payload.get("git_push_performed") is not True
        and report_payload.get("network_mutation_performed") is not True
        and report_payload.get("agent_execution_enabled") is not True
        and report_payload.get("full_codex_parity_claimed") is not True
        and stage_include_count > 0
        and (
            stage_command_count > 0
            or (
                stage_command_count == 0
                and _read_summary_value(report_payload, "commit_gate_noop_accounted_for") is True
                and _read_summary_value(report_payload, "commit_packet_noop_accounted_for") is True
            )
        )
        and stage_command_count <= stage_include_count
        and pre_stage_verification_command_count > 0
        and post_stage_verification_command_count > 0
        and _read_summary_value(report_payload, "owner_approval_resume_packet_status")
        == "owner_approval_resume_packet_blocked"
        and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
        in {"owner_stage_approval_blocked", "owner_stage_approval_ready"}
        and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
        in {"owner_stage_execution_blocked", "owner_stage_execution_ready"}
        and _read_summary_value(report_payload, "owner_staging_preflight_status")
        == "owner_staging_preflight_ready"
        and cached_staged_path_count == 0
        and _read_summary_value(report_payload, "owner_post_staging_verifier_status")
        in {"owner_post_staging_verification_blocked", "owner_post_staging_verification_ready"}
        and _read_summary_value(report_payload, "owner_post_stage_commit_gate_status")
        == "owner_post_stage_commit_gate_blocked"
        and _read_summary_value(report_payload, "owner_commit_packet_status") == "owner_commit_packet_blocked"
        and _read_summary_value(report_payload, "pre_stage_ready") is False
        and _read_summary_value(report_payload, "post_stage_sequence_accounted_for") is False
        and _read_summary_value(report_payload, "control_modes_preservation_status")
        == "control_modes_preservation_ready"
        and _read_summary_value(report_payload, "control_modes_plan_only_default") is True
        and _read_summary_value(report_payload, "control_modes_loop_phases")
        == ["explore", "plan", "edit", "verify", "deliver"]
        and (
            (
                failed_checks == required_failed_checks
                and required_failed_checks.issubset(blocking_reason_names)
            )
            or (
                failed_checks == {"resume_packet_accounted_for", "operator_state_accounted_for"}
                and _read_summary_value(report_payload, "owner_stage_approval_gate_status")
                == "owner_stage_approval_ready"
                and _read_summary_value(report_payload, "owner_stage_execution_plan_status")
                == "owner_stage_execution_ready"
            )
            or (
                stage_command_count == 0
                and failed_checks == post_commit_noop_failed_checks
                and post_commit_noop_failed_checks.issubset(blocking_reason_names)
            )
        )
    )


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


def _ready_status_for_step(name: str) -> str | None:
    return {
        "original_kernel_manifest": "original_kernel_delivery_manifest_ready",
        "control_modes_preservation": "control_modes_preservation_ready",
        "staging_review": "staging_review_ready",
        "owner_staging_packet": "owner_staging_packet_ready",
        "owner_staging_preflight": "owner_staging_preflight_ready",
        "owner_post_staging_verifier": "owner_post_staging_verification_ready",
        "task_board_before_owner_decision": "commercial_delivery_ready_for_owner_staging_review",
        "owner_command_audit": "owner_command_audit_ready",
        "owner_decision_brief": "ready_for_owner_staging_decision",
        "owner_pre_stage_readiness_gate": "owner_pre_stage_readiness_ready",
        "owner_staging_runbook": "owner_staging_runbook_ready",
        "owner_stage_approval_gate": "owner_stage_approval_ready",
        "owner_approval_payload_audit": "owner_approval_payload_ready",
        "owner_post_stage_commit_gate": "owner_post_stage_commit_gate_ready",
        "owner_commit_packet": "owner_commit_packet_ready",
        "owner_staging_rollback_plan": "owner_staging_rollback_plan_ready",
        "owner_delivery_packet_before_owner_approval": "owner_delivery_packet_ready",
        "owner_delivery_packet": "owner_delivery_packet_ready",
        "owner_stage_approval_request": "owner_stage_approval_request_ready",
        "owner_stage_approval_brief": "owner_stage_approval_brief_ready",
        "owner_approval_handoff": "owner_approval_handoff_ready",
        "pre_approval_drift_guard": "pre_approval_drift_guard_ready",
        "owner_approval_resume_packet": "owner_approval_resume_packet_ready",
        "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_ready",
        "owner_stage_execution_plan": "owner_stage_execution_ready",
        "closure_snapshot": "commercial_delivery_complete",
        "task_board_after_owner_decision": "commercial_delivery_ready_for_owner_staging_review",
        "commercial_delivery_report_count_alias_normalization": "passed",
        "commercial_delivery_report_hygiene": "passed",
    }.get(name)


def _build_step(
    *,
    name: str,
    command: list[str],
    command_result: CommandRunResult | None,
    report_path: Path,
    dry_run: bool,
) -> RefreshChainStep:
    if dry_run:
        return RefreshChainStep(
            name=name,
            command=command,
            status="planned",
            returncode=None,
            report_path=_display_path(report_path),
        )

    assert command_result is not None
    report_payload = _read_json(report_path)
    report_status = _status(report_payload)
    expected_nonzero = _is_expected_pre_staging_post_verifier_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_refresh_bootstrap_task_board_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_staging_preflight_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_staging_decision_brief_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_decision_brief_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_staging_pre_stage_readiness_gate_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_pre_stage_readiness_gate_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_staging_runbook_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_runbook_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_delivery_packet_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_stage_approval_request_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_pre_staging_commit_gate_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_pre_staging_commit_packet_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_pre_staging_approval_gate_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_pre_staging_approval_payload_audit_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_approval_payload_audit_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_stage_approval_brief_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_pre_staging_stage_execution_plan_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_pre_staging_closure_snapshot_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_closure_snapshot_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_noop_closure_snapshot_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_owner_approved_pre_stage_closure_snapshot_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_approval_handoff_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_approval_handoff_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_approval_pre_approval_drift_guard_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_pre_approval_drift_guard_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_owner_approval_resume_packet_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    ) or _is_expected_post_commit_owner_post_approval_operator_checklist_state(
        step_name=name,
        command_result=command_result,
        report_payload=report_payload,
    )
    expected_ready_status = _ready_status_for_step(name)
    if name == "owner_approval_resume_packet":
        report_ready = report_status in {
            "owner_approval_resume_packet_ready",
            "owner_approval_resume_packet_waiting_for_owner",
        }
    elif name == "owner_post_approval_operator_checklist":
        report_ready = report_status in {
            "owner_post_approval_operator_checklist_ready",
            "owner_post_approval_operator_checklist_waiting_for_owner",
        }
    else:
        report_ready = expected_ready_status is None or report_status == expected_ready_status
    passed = command_result.returncode == 0 and not command_result.timed_out and report_ready
    status = "passed" if passed else "expected_nonzero_accepted" if expected_nonzero else "failed"
    error = None
    if status == "failed":
        if command_result.timed_out:
            error = "command timed out"
        elif command_result.returncode != 0:
            error = f"command exited {command_result.returncode}"
        else:
            error = f"report status {report_status!r} did not match expected {expected_ready_status!r}"
    return RefreshChainStep(
        name=name,
        command=command,
        status=status,
        returncode=command_result.returncode,
        duration_seconds=command_result.duration_seconds,
        report_path=_display_path(report_path),
        report_status=report_status,
        expected_nonzero_accepted=expected_nonzero,
        stdout_tail=_tail_lines(command_result.stdout),
        stderr_tail=_tail_lines(command_result.stderr),
        error=error,
    )


def build_refresh_chain_receipt(
    *,
    reports_dir: Path = REPORT_DIR,
    timeout_seconds: float = 180.0,
    dry_run: bool = False,
    stop_on_failure: bool = True,
    command_runner: CommandRunner | None = None,
) -> RefreshChainReceipt:
    reports_dir = reports_dir.resolve()
    report_paths = _step_report_paths(reports_dir)
    runner = command_runner or _run_command
    steps: list[RefreshChainStep] = []

    for name, command in _step_commands():
        command_result = None if dry_run else runner(command, timeout_seconds)
        step = _build_step(
            name=name,
            command=command,
            command_result=command_result,
            report_path=report_paths[name],
            dry_run=dry_run,
        )
        steps.append(step)
        if stop_on_failure and step.status == "failed":
            break

    failed_steps = [step for step in steps if step.status == "failed"]
    expected_nonzero_steps = [step for step in steps if step.status == "expected_nonzero_accepted"]
    planned_steps = [step for step in steps if step.status == "planned"]
    passed_steps = [step for step in steps if step.status == "passed"]
    final_statuses = {
        name: _status(_read_json(path))
        for name, path in _final_report_paths(reports_dir).items()
    }
    final_task_board = _read_json(_final_report_paths(reports_dir)["task_board"])
    final_closure_snapshot = _read_json(_final_report_paths(reports_dir)["closure_snapshot"])
    closure_refresh_chain_step_count = _read_summary_value(final_closure_snapshot, "refresh_chain_step_count")
    full_codex_parity_claimed = any(
        _read_json(path).get("full_codex_parity_claimed") is True
        for path in _final_report_paths(reports_dir).values()
    )

    checks = [
        _check(
            "all_refresh_steps_accounted_for",
            dry_run or len(steps) == len(_step_commands()) or bool(failed_steps),
            details={"step_count": len(steps), "expected_step_count": len(_step_commands())},
            error="refresh chain did not record all expected steps",
        ),
        _check(
            "no_unexpected_refresh_failures",
            not failed_steps,
            details={"failed_steps": [step.name for step in failed_steps]},
            error="one or more refresh steps failed unexpectedly",
        ),
        _check(
            "owner_staging_preflight_accounted_for",
            dry_run
            or any(step.name == "owner_staging_preflight" for step in expected_nonzero_steps)
            or final_statuses.get("owner_staging_preflight") == "owner_staging_preflight_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_staging_preflight_status": final_statuses.get("owner_staging_preflight"),
            },
            error="owner staging preflight did not reach a ready or expected post-staging blocked state",
        ),
        _check(
            "post_staging_expected_nonzero_accounted_for",
            dry_run
            or any(step.name == "owner_post_staging_verifier" for step in expected_nonzero_steps)
            or final_statuses.get("owner_post_staging_verifier") == "owner_post_staging_verification_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_post_staging_verifier_status": final_statuses.get("owner_post_staging_verifier"),
            },
            error="post-staging verifier did not reach a ready or expected pre-staging blocked state",
        ),
        _check(
            "post_stage_commit_gate_accounted_for",
            dry_run
            or any(step.name == "owner_post_stage_commit_gate" for step in expected_nonzero_steps)
            or final_statuses.get("owner_post_stage_commit_gate") == "owner_post_stage_commit_gate_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_post_stage_commit_gate_status": final_statuses.get("owner_post_stage_commit_gate"),
            },
            error="post-stage commit gate did not reach a ready or expected pre-staging blocked state",
        ),
        _check(
            "owner_commit_packet_accounted_for",
            dry_run
            or any(step.name == "owner_commit_packet" for step in expected_nonzero_steps)
            or final_statuses.get("owner_commit_packet") == "owner_commit_packet_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_commit_packet_status": final_statuses.get("owner_commit_packet"),
            },
            error="owner commit packet did not reach a ready or expected pre-staging blocked state",
        ),
        _check(
            "owner_staging_rollback_plan_ready",
            dry_run or final_statuses.get("owner_staging_rollback_plan") == "owner_staging_rollback_plan_ready",
            details={"owner_staging_rollback_plan_status": final_statuses.get("owner_staging_rollback_plan")},
            error="owner staging rollback plan is not ready after refresh",
        ),
        _check(
            "owner_stage_approval_gate_accounted_for",
            dry_run
            or any(step.name == "owner_stage_approval_gate" for step in expected_nonzero_steps)
            or final_statuses.get("owner_stage_approval_gate") == "owner_stage_approval_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_stage_approval_gate_status": final_statuses.get("owner_stage_approval_gate"),
            },
            error="owner stage approval gate did not reach a ready or expected pre-staging blocked state",
        ),
        _check(
            "owner_approval_payload_audit_accounted_for",
            dry_run
            or any(step.name == "owner_approval_payload_audit" for step in expected_nonzero_steps)
            or final_statuses.get("owner_approval_payload_audit") == "owner_approval_payload_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_approval_payload_audit_status": final_statuses.get("owner_approval_payload_audit"),
            },
            error="owner approval payload audit did not reach a ready or expected pre-approval blocked state",
        ),
        _check(
            "task_board_refreshed",
            dry_run
            or any(step.name in {"task_board_before_owner_decision", "task_board_after_owner_decision"} for step in expected_nonzero_steps)
            or final_statuses.get("task_board") == "commercial_delivery_ready_for_owner_staging_review",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "task_board_status": final_statuses.get("task_board"),
            },
            error="commercial delivery task board is not ready after refresh",
        ),
        _check(
            "control_modes_preservation_ready",
            dry_run or final_statuses.get("control_modes_preservation") == "control_modes_preservation_ready",
            details={"control_modes_preservation_status": final_statuses.get("control_modes_preservation")},
            error="control mode preservation evidence is not ready after refresh",
        ),
        _check(
            "owner_command_audit_ready",
            dry_run or final_statuses.get("owner_command_audit") == "owner_command_audit_ready",
            details={"owner_command_audit_status": final_statuses.get("owner_command_audit")},
            error="owner command audit is not ready after refresh",
        ),
        _check(
            "owner_decision_brief_ready",
            dry_run
            or any(step.name == "owner_decision_brief" for step in expected_nonzero_steps)
            or final_statuses.get("owner_decision_brief") == "ready_for_owner_staging_decision",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_decision_brief_status": final_statuses.get("owner_decision_brief"),
            },
            error="owner decision brief is not ready or accounted for after refresh",
        ),
        _check(
            "owner_pre_stage_readiness_gate_accounted_for",
            dry_run
            or any(step.name == "owner_pre_stage_readiness_gate" for step in expected_nonzero_steps)
            or final_statuses.get("owner_pre_stage_readiness_gate") == "owner_pre_stage_readiness_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_pre_stage_readiness_gate_status": final_statuses.get("owner_pre_stage_readiness_gate"),
            },
            error="owner pre-stage readiness gate is not ready or accounted for after refresh",
        ),
        _check(
            "owner_staging_runbook_accounted_for",
            dry_run
            or any(step.name == "owner_staging_runbook" for step in expected_nonzero_steps)
            or final_statuses.get("owner_staging_runbook") == "owner_staging_runbook_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_staging_runbook_status": final_statuses.get("owner_staging_runbook"),
            },
            error="owner staging runbook is not ready or accounted for after refresh",
        ),
        _check(
            "owner_delivery_packet_ready",
            dry_run
            or any(
                step.name
                in {
                    "owner_delivery_packet_before_owner_approval",
                    "owner_delivery_packet",
                }
                for step in expected_nonzero_steps
            )
            or final_statuses.get("owner_delivery_packet") == "owner_delivery_packet_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_delivery_packet_status": final_statuses.get("owner_delivery_packet"),
            },
            error="owner delivery packet is not ready or accounted for after refresh",
        ),
        _check(
            "owner_stage_approval_request_ready",
            dry_run
            or any(step.name == "owner_stage_approval_request" for step in expected_nonzero_steps)
            or final_statuses.get("owner_stage_approval_request") == "owner_stage_approval_request_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_stage_approval_request_status": final_statuses.get("owner_stage_approval_request"),
            },
            error="owner stage approval request is not ready or accounted for after refresh",
        ),
        _check(
            "owner_stage_approval_brief_ready",
            dry_run
            or any(step.name == "owner_stage_approval_brief" for step in expected_nonzero_steps)
            or final_statuses.get("owner_stage_approval_brief") == "owner_stage_approval_brief_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_stage_approval_brief_status": final_statuses.get("owner_stage_approval_brief"),
            },
            error="owner stage approval brief is not ready or accounted for after refresh",
        ),
        _check(
            "owner_approval_handoff_ready",
            dry_run
            or any(step.name == "owner_approval_handoff" for step in expected_nonzero_steps)
            or final_statuses.get("owner_approval_handoff") == "owner_approval_handoff_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_approval_handoff_status": final_statuses.get("owner_approval_handoff"),
            },
            error="owner approval handoff is not ready or accounted for after refresh",
        ),
        _check(
            "pre_approval_drift_guard_ready",
            dry_run
            or any(step.name == "pre_approval_drift_guard" for step in expected_nonzero_steps)
            or final_statuses.get("pre_approval_drift_guard") == "pre_approval_drift_guard_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "pre_approval_drift_guard_status": final_statuses.get("pre_approval_drift_guard"),
            },
            error="pre-approval drift guard is not ready or accounted for after refresh",
        ),
        _check(
            "owner_approval_resume_packet_accounted_for",
            dry_run
            or any(step.name == "owner_approval_resume_packet" for step in expected_nonzero_steps)
            or final_statuses.get("owner_approval_resume_packet")
            in {
                "owner_approval_resume_packet_waiting_for_owner",
                "owner_approval_resume_packet_ready",
            },
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_approval_resume_packet_status": final_statuses.get("owner_approval_resume_packet"),
            },
            error="owner approval resume packet is not waiting for owner or ready after refresh",
        ),
        _check(
            "owner_post_approval_operator_checklist_accounted_for",
            dry_run
            or any(step.name == "owner_post_approval_operator_checklist" for step in expected_nonzero_steps)
            or final_statuses.get("owner_post_approval_operator_checklist")
            in {
                "owner_post_approval_operator_checklist_waiting_for_owner",
                "owner_post_approval_operator_checklist_ready",
            },
            details={
                "owner_post_approval_operator_checklist_status": final_statuses.get(
                    "owner_post_approval_operator_checklist"
                )
            },
            error="owner post-approval operator checklist is not waiting for owner or ready after refresh",
        ),
        _check(
            "owner_stage_execution_plan_accounted_for",
            dry_run
            or any(step.name == "owner_stage_execution_plan" for step in expected_nonzero_steps)
            or final_statuses.get("owner_stage_execution_plan") == "owner_stage_execution_ready",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "owner_stage_execution_plan_status": final_statuses.get("owner_stage_execution_plan"),
            },
            error="owner stage execution plan did not reach a ready or expected pre-approval blocked state",
        ),
        _check(
            "closure_snapshot_accounted_for",
            dry_run
            or any(step.name == "closure_snapshot" for step in expected_nonzero_steps)
            or final_statuses.get("closure_snapshot") == "commercial_delivery_complete",
            details={
                "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
                "closure_snapshot_status": final_statuses.get("closure_snapshot"),
            },
            error="closure snapshot did not reach complete or expected pre-staging blocked state",
        ),
        _check(
            "commercial_delivery_report_count_alias_normalization_ready",
            dry_run
            or final_statuses.get("commercial_delivery_report_count_alias_normalization") == "passed",
            details={
                "commercial_delivery_report_count_alias_normalization_status": final_statuses.get(
                    "commercial_delivery_report_count_alias_normalization"
                )
            },
            error="commercial delivery report count alias normalization is not ready after refresh",
        ),
        _check(
            "commercial_delivery_report_hygiene_ready",
            dry_run or final_statuses.get("commercial_delivery_report_hygiene") == "passed",
            details={"commercial_delivery_report_hygiene_status": final_statuses.get("commercial_delivery_report_hygiene")},
            error="commercial delivery report hygiene is not ready after refresh",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more commercial delivery reports claim full Codex parity",
        ),
        _check(
            "no_refresh_chain_release_mutation",
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
    if dry_run:
        status = "commercial_delivery_refresh_chain_receipt_planned"
    elif any(check.status == "failed" for check in checks):
        status = "commercial_delivery_refresh_chain_receipt_blocked"
    else:
        status = "commercial_delivery_refresh_chain_receipt_ready"

    return RefreshChainReceipt(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_refresh_chain_receipt",
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        dry_run=dry_run,
        stop_on_failure=stop_on_failure,
        reports_dir=_display_path(reports_dir),
        steps=steps,
        checks=checks,
        summary={
            "step_count": len(steps),
            "passed_step_count": len(passed_steps),
            "planned_step_count": len(planned_steps),
            "failed_step_count": len(failed_steps),
            "expected_nonzero_step_count": len(expected_nonzero_steps),
            "expected_nonzero_steps": [step.name for step in expected_nonzero_steps],
            "control_modes_preservation_status": final_statuses.get("control_modes_preservation"),
            "control_modes_plan_only_default": _read_summary_value(final_task_board, "control_modes_plan_only_default"),
            "control_modes_loop_phases": _read_summary_value(final_task_board, "control_modes_loop_phases"),
            "control_modes_surface_file_count": _read_summary_value(
                final_task_board,
                "control_modes_surface_file_count",
            ),
            "final_task_board_status": final_statuses.get("task_board"),
            "secondary_pending_count": _read_summary_value(final_task_board, "secondary_pending_count"),
            "secondary_handoff_next_count": _read_summary_value(final_task_board, "secondary_handoff_next_count"),
            "secondary_handoff_next_queue": _read_summary_value(final_task_board, "secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": _read_summary_value(
                final_task_board,
                "secondary_handoff_completed_count",
            ),
            "secondary_handoff_latest_completed_candidate": _read_summary_value(
                final_task_board,
                "secondary_handoff_latest_completed_candidate",
            ),
            "owner_command_audit_status": final_statuses.get("owner_command_audit"),
            "owner_decision_brief_status": final_statuses.get("owner_decision_brief"),
            "owner_pre_stage_readiness_gate_status": final_statuses.get("owner_pre_stage_readiness_gate"),
            "owner_staging_runbook_status": final_statuses.get("owner_staging_runbook"),
            "owner_staging_preflight_status": final_statuses.get("owner_staging_preflight"),
            "owner_stage_approval_gate_status": final_statuses.get("owner_stage_approval_gate"),
            "owner_post_stage_commit_gate_status": final_statuses.get("owner_post_stage_commit_gate"),
            "owner_commit_packet_status": final_statuses.get("owner_commit_packet"),
            "owner_staging_rollback_plan_status": final_statuses.get("owner_staging_rollback_plan"),
            "owner_delivery_packet_status": final_statuses.get("owner_delivery_packet"),
            "owner_stage_approval_request_status": final_statuses.get("owner_stage_approval_request"),
            "owner_approval_payload_audit_status": final_statuses.get("owner_approval_payload_audit"),
            "owner_stage_approval_brief_status": final_statuses.get("owner_stage_approval_brief"),
            "owner_approval_handoff_status": final_statuses.get("owner_approval_handoff"),
            "pre_approval_drift_guard_status": final_statuses.get("pre_approval_drift_guard"),
            "owner_approval_resume_packet_status": final_statuses.get("owner_approval_resume_packet"),
            "owner_post_approval_operator_checklist_status": final_statuses.get(
                "owner_post_approval_operator_checklist"
            ),
            "owner_stage_execution_plan_status": final_statuses.get("owner_stage_execution_plan"),
            "closure_snapshot_status": final_statuses.get("closure_snapshot"),
            "owner_post_staging_verifier_status": final_statuses.get("owner_post_staging_verifier"),
            "closure_refresh_chain_step_count": closure_refresh_chain_step_count,
            "closure_refresh_chain_step_count_lag_expected": (
                isinstance(closure_refresh_chain_step_count, int)
                and closure_refresh_chain_step_count < len(steps)
                and final_statuses.get("closure_snapshot") == "commercial_delivery_closure_blocked"
            ),
            "commercial_delivery_report_count_alias_normalization_status": final_statuses.get(
                "commercial_delivery_report_count_alias_normalization"
            ),
            "commercial_delivery_report_hygiene_status": final_statuses.get("commercial_delivery_report_hygiene"),
        },
        final_report_statuses=final_statuses,
        next_actions=[
            "Inspect this receipt before treating regenerated commercial delivery reports as current.",
            "The expected nonzero owner post-staging verifier is acceptable only before owner staging when the cached index is empty.",
            "The expected nonzero owner post-stage commit gate is acceptable only before owner staging when the cached index is empty.",
            "The expected nonzero owner commit packet is acceptable only before owner staging when the cached index is empty.",
            "The expected nonzero owner approval payload audit is acceptable only until the real owner approval payload exists.",
            "The expected nonzero owner stage approval gate is acceptable only until explicit owner approval evidence exists.",
            "The expected nonzero owner stage execution plan is acceptable only until the approval gate is ready.",
            "The owner approval handoff must stay ready before requesting the owner to create the real approval payload.",
            "The owner approval resume packet must stay waiting_for_owner until real owner approval exists.",
            "The owner post-approval operator checklist must stay waiting_for_owner until real owner approval exists.",
            "Control mode preservation must stay ready so plan mode and goal-loop behavior survive fusion.",
            "The expected nonzero closure snapshot is acceptable only before owner approval, staging, post-stage verification, and commit gates are complete.",
            "Commercial delivery report count aliases and scoped hygiene must be refreshed after the owner-gated report chain.",
            "The owner delivery packet is refreshed once before owner approval artifacts and once after stage execution planning to prevent stale approval counts.",
            "The owner delivery packet must stay ready for pre-stage owner review even when post-stage commit is not yet allowed.",
            "Run owner staging preflight immediately before any owner-approved git add commands.",
            "After owner-approved staging, rerun owner post-staging verifier before commit.",
        ],
        known_limits=[
            "This receipt runs local report generator scripts and writes local evidence only.",
            "It does not stage files, create commits, push, call network services, run agents, or execute secondary candidates.",
            "It does not claim full Codex parity.",
            "The task board may need one extra refresh after this receipt is written if a current receipt status is required inside the task board.",
        ],
    )


def render_markdown_receipt(report: RefreshChainReceipt) -> str:
    lines = [
        "# Commercial Delivery Refresh Chain Receipt",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Dry run: `{str(report.dry_run).lower()}`",
        f"- Step count: `{report.summary['step_count']}`",
        f"- Failed step count: `{report.summary['failed_step_count']}`",
        f"- Expected nonzero step count: `{report.summary['expected_nonzero_step_count']}`",
        f"- Secondary pending count: `{report.summary.get('secondary_pending_count')}`",
        f"- Secondary handoff completed count: `{report.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{report.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Secondary next queue: `{', '.join(report.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Control modes preservation: `{report.summary.get('control_modes_preservation_status')}`",
        f"- Control modes plan-only default: `{report.summary.get('control_modes_plan_only_default')}`",
        "",
        "## Steps",
        "",
    ]
    for step in report.steps:
        command = " ".join(step.command)
        lines.extend(
            [
                f"- `{step.name}`: `{step.status}`",
                f"  - Command: `{command}`",
                f"  - Return code: `{step.returncode}`",
                f"  - Report status: `{step.report_status}`",
            ]
        )
        if step.error:
            lines.append(f"  - Error: {step.error}")
    lines.extend(["", "## Checks", ""])
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in report.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(report: RefreshChainReceipt, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_receipt(report: RefreshChainReceipt, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_receipt(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_refresh_chain_receipt(
        reports_dir=args.reports_dir,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
        stop_on_failure=not args.continue_on_failure,
    )
    write_report(report, args.output)
    write_markdown_receipt(report, args.markdown_output)
    print(f"Commercial delivery refresh chain receipt status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    for step in report.steps:
        print(f"- {step.name}: {step.status}")
        if step.error:
            print(f"  error: {step.error}")
    return 0 if report.status in {
        "commercial_delivery_refresh_chain_receipt_ready",
        "commercial_delivery_refresh_chain_receipt_planned",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
