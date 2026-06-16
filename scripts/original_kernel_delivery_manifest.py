#!/usr/bin/env python3
"""Build the original-kernel selective delivery manifest.

The manifest is a read-only staging gate. It lists the original-kernel files
that are safe to stage explicitly, records required evidence reports, and
separates unrelated dirty worktree paths so UI or entrypoint work from another
session is not accidentally included.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.storage import atomic_write_json  # noqa: E402
from scripts.original_kernel_module_integration_summary import EXPECTED_REPORTS  # noqa: E402

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-delivery-manifest.json"


@dataclass(frozen=True)
class FileSpec:
    path: str
    category: str
    required: bool = True


@dataclass(frozen=True)
class EvidenceSpec:
    filename: str
    status: str
    evidence_type: str


@dataclass(frozen=True)
class ManifestFile:
    path: str
    category: str
    required: bool
    status: str
    git_status: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class EvidenceReport:
    filename: str
    path: str
    required: bool
    status: str
    report_status: str | None = None
    evidence_type: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    full_codex_parity_claimed: bool | None = None
    error: str | None = None


@dataclass(frozen=True)
class ManifestCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


CORE_MODULE_FILES: tuple[FileSpec, ...] = (
    FileSpec("backend/app/core/storage.py", "core_module"),
    FileSpec("backend/app/core/audit_signing.py", "core_module"),
    FileSpec("backend/app/core/structured_logging.py", "core_module"),
    FileSpec("backend/app/core/permission_profiles.py", "core_module"),
    FileSpec("backend/app/core/repo_context.py", "core_module"),
    FileSpec("backend/app/core/context_pack.py", "core_module"),
    FileSpec("backend/app/core/coding_loop.py", "core_module"),
    FileSpec("backend/app/core/agent_run_closure.py", "core_module"),
    FileSpec("backend/app/core/long_task_models.py", "core_module"),
    FileSpec("backend/app/core/long_task_state_machine.py", "core_module"),
    FileSpec("backend/app/core/long_task_merge_gates.py", "core_module"),
    FileSpec("backend/app/core/long_tasks_helpers.py", "core_module"),
    FileSpec("backend/app/core/shell_job_runner.py", "core_module"),
    FileSpec("backend/app/core/pull_request_delivery.py", "core_module"),
    FileSpec("backend/app/core/workflow_events.py", "core_module"),
)

SCRIPT_FILES: tuple[FileSpec, ...] = (
    FileSpec("scripts/check_report_hygiene.py", "support_script"),
    FileSpec("scripts/normalize_report_count_aliases.py", "support_script"),
    FileSpec("scripts/run_pytest_evidence.py", "support_script"),
    FileSpec("scripts/original_kernel_minimal_integration_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_context_integration_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_agent_run_closure_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_long_task_integration_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_shell_job_runner_integration_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_pull_request_delivery_integration_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_report_evidence_integration_report.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_module_integration_summary.py", "integration_report_script"),
    FileSpec("scripts/original_kernel_delivery_manifest.py", "delivery_manifest_script"),
    FileSpec("scripts/commercial_delivery_owner_command_audit.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_decision_brief.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_pre_stage_readiness_gate.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_stage_approval_request.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_approval_payload_audit.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_pre_approval_drift_guard.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_stage_approval_brief.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_stage_approval_gate.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_approval_handoff.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_approval_resume_packet.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_stage_execution_plan.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_staging_rollback_plan.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_staging_preflight.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_staging_packet.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_staging_runbook.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_post_staging_verifier.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_post_stage_commit_gate.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_post_approval_operator_checklist.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_commit_packet.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_owner_delivery_packet.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_staging_review.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_stage3_staging_external_evidence_intake.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_closure_snapshot.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_refresh_chain_receipt.py", "commercial_delivery_gate_script"),
    FileSpec("scripts/commercial_delivery_task_board.py", "commercial_delivery_gate_script"),
)

TEST_FILES: tuple[FileSpec, ...] = (
    FileSpec("tests/test_storage.py", "test"),
    FileSpec("tests/test_audit_signing.py", "test"),
    FileSpec("tests/test_structured_logging.py", "test"),
    FileSpec("tests/test_permission_profiles.py", "test"),
    FileSpec("tests/test_repo_context.py", "test"),
    FileSpec("tests/test_context_pack.py", "test"),
    FileSpec("tests/test_coding_loop.py", "test"),
    FileSpec("tests/test_agent_run_closure.py", "test"),
    FileSpec("tests/test_long_task_models.py", "test"),
    FileSpec("tests/test_long_task_state_machine.py", "test"),
    FileSpec("tests/test_long_task_merge_gates.py", "test"),
    FileSpec("tests/test_long_tasks_helpers.py", "test"),
    FileSpec("tests/test_shell_job_runner.py", "test"),
    FileSpec("tests/test_pull_request_delivery.py", "test"),
    FileSpec("tests/test_workflow_events.py", "test"),
    FileSpec("tests/test_report_hygiene.py", "test"),
    FileSpec("tests/test_normalize_report_count_aliases.py", "test"),
    FileSpec("tests/test_run_pytest_evidence.py", "test"),
    FileSpec("tests/test_original_kernel_minimal_integration_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_context_integration_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_agent_run_closure_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_long_task_integration_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_shell_job_runner_integration_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_pull_request_delivery_integration_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_report_evidence_integration_report.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_module_integration_summary.py", "integration_report_test"),
    FileSpec("tests/test_original_kernel_delivery_manifest.py", "delivery_manifest_test"),
    FileSpec("tests/test_commercial_delivery_owner_command_audit.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_decision_brief.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_pre_stage_readiness_gate.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_stage_approval_request.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_approval_payload_audit.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_pre_approval_drift_guard.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_stage_approval_brief.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_stage_approval_gate.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_approval_handoff.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_approval_resume_packet.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_stage_execution_plan.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_staging_rollback_plan.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_staging_preflight.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_staging_packet.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_staging_runbook.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_post_staging_verifier.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_post_stage_commit_gate.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_post_approval_operator_checklist.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_commit_packet.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_owner_delivery_packet.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_staging_review.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_stage3_staging_external_evidence_intake.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_closure_snapshot.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_refresh_chain_receipt.py", "commercial_delivery_gate_test"),
    FileSpec("tests/test_commercial_delivery_task_board.py", "commercial_delivery_gate_test"),
)

DOC_FILES: tuple[FileSpec, ...] = (
    FileSpec("docs/original-kernel-integration-assessment.md", "integration_assessment_doc"),
    FileSpec("docs/original-kernel-collaboration-protocol.md", "collaboration_protocol_doc"),
)

DEFAULT_STAGE_FILES: tuple[FileSpec, ...] = CORE_MODULE_FILES + SCRIPT_FILES + TEST_FILES + DOC_FILES

DEFAULT_EVIDENCE_REPORTS: tuple[EvidenceSpec, ...] = (
    *(
        EvidenceSpec(
            filename=spec.filename,
            status=spec.ready_status,
            evidence_type=spec.evidence_type,
        )
        for spec in EXPECTED_REPORTS
    ),
    EvidenceSpec(
        filename="original-kernel-module-integration-summary.json",
        status="original_kernel_module_integration_summary_ready",
        evidence_type="original_kernel_module_integration_summary",
    ),
)

FORBIDDEN_STAGE_PREFIXES = (
    "frontend/",
    "backend/app/api/",
    "backend/app/control_plane",
)
FORBIDDEN_STAGE_EXACT = {
    "backend/app/main.py",
    "backend/app/core/__init__.py",
}
SECONDARY_INTEGRATION_CANDIDATES = {
    "backend/app/core/long_tasks_recovery_audit.py",
    "tests/test_long_tasks_recovery_audit.py",
    "backend/app/core/skill_bundles.py",
    "tests/test_skill_bundles.py",
    "backend/app/core/trace_analysis.py",
    "tests/test_trace_analysis.py",
    "backend/app/core/agent_orchestration_runtime.py",
    "tests/test_agent_orchestration_runtime.py",
    "backend/app/core/agent_registry.py",
    "tests/test_agent_registry.py",
    "backend/app/core/policy_risk_analysis.py",
    "tests/test_policy_risk_analysis.py",
    "backend/app/core/acceptance_matrix.py",
    "tests/test_acceptance_matrix.py",
    "backend/app/core/model_provider_contracts.py",
    "tests/test_model_provider_contracts.py",
    "backend/app/core/deployment_security_contracts.py",
    "tests/test_deployment_security_contracts.py",
    "backend/app/core/url_safety.py",
    "tests/test_url_safety.py",
    "backend/app/core/output_redaction.py",
    "tests/test_output_redaction.py",
    "backend/app/core/patch_risk_analysis.py",
    "tests/test_patch_risk_analysis.py",
    "backend/app/core/open_source_report_audit.py",
    "tests/test_open_source_report_audit.py",
    "backend/app/core/task_environment_contracts.py",
    "tests/test_task_environment_contracts.py",
    "backend/app/core/pr_review_readiness.py",
    "tests/test_pr_review_readiness.py",
    "backend/app/core/instruction_source_audit.py",
    "tests/test_instruction_source_audit.py",
    "backend/app/core/browser_task_readiness.py",
    "tests/test_browser_task_readiness.py",
    "backend/app/core/open_source_adoption_matrix.py",
    "tests/test_open_source_adoption_matrix.py",
    "backend/app/core/agent_eval_matrix.py",
    "tests/test_agent_eval_matrix.py",
    "backend/app/core/subagent_handoff_matrix.py",
    "tests/test_subagent_handoff_matrix.py",
    "backend/app/core/mcp_tool_readiness.py",
    "tests/test_mcp_tool_readiness.py",
    "backend/app/core/channel_integration_readiness.py",
    "tests/test_channel_integration_readiness.py",
    "backend/app/core/release_evidence_pack.py",
    "tests/test_release_evidence_pack.py",
    "backend/app/core/runtime_capability_manifest.py",
    "tests/test_runtime_capability_manifest.py",
    "backend/app/core/integration_candidate_scorecard.py",
    "tests/test_integration_candidate_scorecard.py",
    "backend/app/core/integration_decision_audit.py",
    "tests/test_integration_decision_audit.py",
    "backend/app/core/integration_readiness_snapshot.py",
    "tests/test_integration_readiness_snapshot.py",
    "backend/app/core/candidate_dependency_map.py",
    "tests/test_candidate_dependency_map.py",
    "backend/app/core/integration_sequence_plan.py",
    "tests/test_integration_sequence_plan.py",
    "backend/app/core/integration_traceability_index.py",
    "tests/test_integration_traceability_index.py",
    "backend/app/core/integration_review_packet.py",
    "tests/test_integration_review_packet.py",
    "backend/app/core/integration_governance_summary.py",
    "tests/test_integration_governance_summary.py",
    "backend/app/core/integration_followup_queue.py",
    "tests/test_integration_followup_queue.py",
    "backend/app/core/integration_owner_digest.py",
    "tests/test_integration_owner_digest.py",
    "backend/app/core/integration_closure_checklist.py",
    "tests/test_integration_closure_checklist.py",
    "backend/app/core/integration_final_review_brief.py",
    "tests/test_integration_final_review_brief.py",
    "backend/app/core/integration_adoption_readme.py",
    "tests/test_integration_adoption_readme.py",
    "backend/app/core/integration_rollout_guardrails.py",
    "tests/test_integration_rollout_guardrails.py",
    "backend/app/core/integration_post_adoption_monitor.py",
    "tests/test_integration_post_adoption_monitor.py",
    "backend/app/core/integration_sunset_review.py",
    "tests/test_integration_sunset_review.py",
    "backend/app/core/integration_secondary_index.py",
    "tests/test_integration_secondary_index.py",
    "backend/app/core/integration_conflict_risk_register.py",
    "tests/test_integration_conflict_risk_register.py",
    "backend/app/core/integration_review_readiness_gate.py",
    "tests/test_integration_review_readiness_gate.py",
    "backend/app/core/integration_review_packet_manifest.py",
    "tests/test_integration_review_packet_manifest.py",
    "backend/app/core/integration_stage_label_policy.py",
    "tests/test_integration_stage_label_policy.py",
    "backend/app/core/integration_manifest_diff_summary.py",
    "tests/test_integration_manifest_diff_summary.py",
    "backend/app/core/integration_manifest_review_digest.py",
    "tests/test_integration_manifest_review_digest.py",
    "backend/app/core/integration_reviewer_assignment_matrix.py",
    "tests/test_integration_reviewer_assignment_matrix.py",
    "backend/app/core/integration_review_calendar.py",
    "tests/test_integration_review_calendar.py",
    "backend/app/core/integration_review_minutes.py",
    "tests/test_integration_review_minutes.py",
    "backend/app/core/integration_review_archive_manifest.py",
    "tests/test_integration_review_archive_manifest.py",
    "backend/app/core/integration_review_retention_policy.py",
    "tests/test_integration_review_retention_policy.py",
    "backend/app/core/integration_review_evidence_index.py",
    "tests/test_integration_review_evidence_index.py",
    "backend/app/core/integration_review_query_plan.py",
    "tests/test_integration_review_query_plan.py",
    "backend/app/core/integration_review_query_result_digest.py",
    "tests/test_integration_review_query_result_digest.py",
    "backend/app/core/integration_review_answer_brief.py",
    "tests/test_integration_review_answer_brief.py",
    "backend/app/core/integration_review_answer_action_matrix.py",
    "tests/test_integration_review_answer_action_matrix.py",
}
SECONDARY_HANDOFF_FILES = {
    "docs/original-kernel-secondary-handoff.md",
    "docs/codex-gap-open-source-fill-report-2026-06-09.md",
    "docs/codex-capability-alignment-matrix-2026-06-12.md",
}
SECONDARY_PENDING_CANDIDATES = {
    "backend/app/core/integration_review_action_status_board.py",
    "tests/test_integration_review_action_status_board.py",
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip()


def _display_path(path: Path, *, root: Path) -> str:
    try:
        return _normalize_path(str(path.resolve().relative_to(root.resolve())))
    except ValueError:
        return _normalize_path(str(path.resolve()))


def _sha256_file(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, "file not found"
    except OSError as exc:
        return None, None, f"could not read file: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "report not found"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report: {exc}"
    if not isinstance(payload, dict):
        return None, "report JSON root is not an object"
    return payload, None


def _git_status_lines(workspace_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "status", "--short"],
        cwd=workspace_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _parse_git_status(lines: Sequence[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for raw_line in lines:
        if not raw_line.strip():
            continue
        status = raw_line[:2].strip() or raw_line[:2]
        path_value = raw_line[3:] if len(raw_line) > 3 else raw_line[2:].strip()
        if " -> " in path_value:
            path_value = path_value.split(" -> ", 1)[1]
        path_value = path_value.strip().strip('"')
        entries.append(
            {
                "status": status,
                "path": _normalize_path(path_value),
                "raw": raw_line,
            }
        )
    return entries


def _status_for_path(path: str, git_entries: list[dict[str, str]]) -> str | None:
    normalized = _normalize_path(path)
    for entry in git_entries:
        entry_path = entry["path"]
        if entry_path == normalized:
            return entry["status"]
        if entry_path.endswith("/") and normalized.startswith(entry_path):
            return entry["status"]
    return None


def _file_from_spec(spec: FileSpec, *, workspace_root: Path, git_entries: list[dict[str, str]]) -> ManifestFile:
    normalized = _normalize_path(spec.path)
    path = workspace_root / normalized
    sha256, size_bytes, error = _sha256_file(path)
    status = "present" if error is None else ("missing" if spec.required else "optional_missing")
    return ManifestFile(
        path=normalized,
        category=spec.category,
        required=spec.required,
        status=status,
        git_status=_status_for_path(normalized, git_entries),
        sha256=sha256,
        size_bytes=size_bytes,
        error=error,
    )


def _evidence_from_spec(spec: EvidenceSpec, *, reports_dir: Path) -> EvidenceReport:
    path = reports_dir / spec.filename
    sha256, size_bytes, read_error = _sha256_file(path)
    payload, json_error = _read_json(path)
    error = read_error or json_error
    report_status = payload.get("status") if isinstance(payload, dict) else None
    evidence_type = payload.get("evidence_type") if isinstance(payload, dict) else None
    parity_claim = payload.get("full_codex_parity_claimed") if isinstance(payload, dict) else None

    passed = all(
        [
            error is None,
            report_status == spec.status,
            evidence_type == spec.evidence_type,
            parity_claim is not True,
        ]
    )
    status = "passed" if passed else "failed"
    if error is None and not passed:
        error = "report status, evidence_type, or parity claim does not match the expected delivery gate"

    return EvidenceReport(
        filename=spec.filename,
        path=_display_path(path, root=reports_dir.parent.parent if reports_dir.name == "reports" else reports_dir),
        required=True,
        status=status,
        report_status=report_status if isinstance(report_status, str) else None,
        evidence_type=evidence_type if isinstance(evidence_type, str) else None,
        sha256=sha256,
        size_bytes=size_bytes,
        full_codex_parity_claimed=parity_claim if isinstance(parity_claim, bool) else None,
        error=error,
    )


def _is_forbidden_stage_path(path: str) -> bool:
    normalized = _normalize_path(path)
    return normalized in FORBIDDEN_STAGE_EXACT or any(
        normalized.startswith(prefix) for prefix in FORBIDDEN_STAGE_PREFIXES
    )


def _is_codex_gap_readiness_candidate(path: str) -> bool:
    normalized = _normalize_path(path)
    return (
        normalized.startswith("backend/app/core/codex_")
        and normalized.endswith("_readiness_packet.py")
    ) or (
        normalized.startswith("tests/test_codex_")
        and normalized.endswith("_readiness_packet.py")
    )


def _excluded_scope(path: str) -> str:
    normalized = _normalize_path(path)
    if normalized in SECONDARY_INTEGRATION_CANDIDATES or _is_codex_gap_readiness_candidate(normalized):
        return "secondary_integration_candidate"
    if normalized in SECONDARY_HANDOFF_FILES:
        return "secondary_handoff"
    if normalized in SECONDARY_PENDING_CANDIDATES:
        return "secondary_pending_candidate"
    if normalized.startswith("frontend/"):
        return "frontend"
    if normalized.startswith("backend/app/api/"):
        return "api_router"
    if normalized in FORBIDDEN_STAGE_EXACT:
        return "mainline_entrypoint"
    if normalized.startswith(".xagent_runtime/"):
        return "runtime_report"
    if normalized.startswith(".agents/") or normalized.startswith(".codex/") or normalized == "AGENTS.md":
        return "agent_workspace_config"
    if normalized.startswith("docs/"):
        return "unrelated_doc"
    return "unrelated_worktree_change"


def _excluded_dirty_entries(
    *, git_entries: list[dict[str, str]], intended_paths: set[str]
) -> list[dict[str, str]]:
    excluded: list[dict[str, str]] = []
    for entry in git_entries:
        path = entry["path"]
        if path in intended_paths:
            continue
        if path.endswith("/") and any(item.startswith(path) for item in intended_paths):
            continue
        excluded.append(
            {
                "path": path,
                "status": entry["status"],
                "scope": _excluded_scope(path),
            }
        )
    return excluded


def _required_files_check(files: list[ManifestFile]) -> ManifestCheck:
    missing = [item.path for item in files if item.required and item.status != "present"]
    passed = not missing
    return ManifestCheck(
        name="required_stage_files_present",
        status="passed" if passed else "failed",
        details={
            "required_count": sum(1 for item in files if item.required),
            "missing": missing,
        },
        error=None if passed else "one or more intended original-kernel stage files are missing",
    )


def _forbidden_stage_paths_check(files: list[ManifestFile]) -> ManifestCheck:
    forbidden = [item.path for item in files if _is_forbidden_stage_path(item.path)]
    passed = not forbidden
    return ManifestCheck(
        name="no_mainline_entrypoint_or_ui_in_stage_manifest",
        status="passed" if passed else "failed",
        details={"forbidden_paths": forbidden},
        error=None if passed else "stage manifest includes frontend, API router, control plane, or mainline entrypoint paths",
    )


def _evidence_reports_check(reports: list[EvidenceReport]) -> ManifestCheck:
    failed = [item.filename for item in reports if item.status != "passed"]
    passed = not failed
    return ManifestCheck(
        name="required_evidence_reports_ready",
        status="passed" if passed else "failed",
        details={
            "required_count": len(reports),
            "passed_count": sum(1 for item in reports if item.status == "passed"),
            "failed": failed,
        },
        error=None if passed else "one or more original-kernel evidence reports are missing or not ready",
    )


def _excluded_dirty_scope_check(excluded_dirty: list[dict[str, str]]) -> ManifestCheck:
    return ManifestCheck(
        name="excluded_dirty_paths_partitioned",
        status="passed",
        details={
            "excluded_dirty_count": len(excluded_dirty),
            "scopes": sorted({item["scope"] for item in excluded_dirty}),
        },
    )


def _overall_status(checks: list[ManifestCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "original_kernel_delivery_manifest_blocked"
    return "original_kernel_delivery_manifest_ready"


def build_report(
    *,
    workspace_root: str | Path = ROOT,
    reports_dir: str | Path | None = None,
    stage_files: Sequence[FileSpec] = DEFAULT_STAGE_FILES,
    evidence_reports: Sequence[EvidenceSpec] = DEFAULT_EVIDENCE_REPORTS,
    git_status_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    report_dir = Path(reports_dir).resolve() if reports_dir is not None else workspace / ".xagent_runtime" / "reports"
    status_lines = list(git_status_lines) if git_status_lines is not None else _git_status_lines(workspace)
    git_entries = _parse_git_status(status_lines)

    files = [_file_from_spec(spec, workspace_root=workspace, git_entries=git_entries) for spec in stage_files]
    evidence = [_evidence_from_spec(spec, reports_dir=report_dir) for spec in evidence_reports]
    intended_paths = {_normalize_path(item.path) for item in stage_files}
    excluded_dirty = _excluded_dirty_entries(git_entries=git_entries, intended_paths=intended_paths)
    checks = [
        _required_files_check(files),
        _forbidden_stage_paths_check(files),
        _evidence_reports_check(evidence),
        _excluded_dirty_scope_check(excluded_dirty),
    ]
    status = _overall_status(checks)

    return {
        "status": status,
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_delivery_manifest",
        "workspace_root": str(workspace),
        "reports_dir": str(report_dir),
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "git_status_read_performed": True,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "command_execution_enabled": False,
        "full_codex_parity_claimed": False,
        "runtime_reports_stage_excluded": True,
        "stage_include_count": len(files),
        "stage_include_paths": [item.path for item in files],
        "excluded_dirty_count": len(excluded_dirty),
        "excluded_dirty_paths": excluded_dirty,
        "files": [asdict(item) for item in files],
        "evidence_reports": [asdict(item) for item in evidence],
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This manifest is read-only and does not run git add, git commit, or git push.",
            "Runtime reports under .xagent_runtime are evidence only and are excluded from default staging.",
            "Frontend, API router, control plane, agent loop, and backend core package entrypoints are excluded from this original-kernel delivery scope.",
            "No full Codex parity claim is made by this manifest.",
        ],
        "next_actions": [
            "Use stage_include_paths for explicit staging only after review.",
            "Keep excluded_dirty_paths out of the original-kernel delivery commit unless separately approved.",
        ],
    }


def write_report(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    workspace_root: str | Path = ROOT,
    reports_dir: str | Path | None = None,
    git_status_lines: Sequence[str] | None = None,
) -> dict[str, Any]:
    report = build_report(
        workspace_root=workspace_root,
        reports_dir=reports_dir,
        git_status_lines=git_status_lines,
    )
    report["report_file_written"] = True
    report["report_path"] = str(output_path)
    atomic_write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reports-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_report(args.output, reports_dir=args.reports_dir)

    print(f"Original kernel delivery manifest status: {report['status']}")
    print(f"Report written to {args.output}")
    print(f"Stage include files: {report['stage_include_count']}")
    print(f"Excluded dirty paths: {report['excluded_dirty_count']}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_delivery_manifest_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
