from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from scripts.original_kernel_delivery_manifest import (
    DEFAULT_EVIDENCE_REPORTS,
    DEFAULT_STAGE_FILES,
    FileSpec,
    build_report,
    write_report,
)


def test_original_kernel_delivery_manifest_ready_with_excluded_dirty_paths(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(reports_dir)
    git_status_lines = [
        "?? backend/app/core/storage.py",
        " M frontend/src/App.tsx",
        " M backend/app/api/workbench.py",
        "?? backend/app/core/workflow_events.py",
        "?? backend/app/core/long_tasks_recovery_audit.py",
        "?? backend/app/core/skill_bundles.py",
        "?? backend/app/core/trace_analysis.py",
        "?? backend/app/core/agent_orchestration_runtime.py",
        "?? backend/app/core/agent_registry.py",
        "?? backend/app/core/policy_risk_analysis.py",
        "?? backend/app/core/acceptance_matrix.py",
        "?? backend/app/core/model_provider_contracts.py",
        "?? backend/app/core/deployment_security_contracts.py",
        "?? backend/app/core/url_safety.py",
        "?? backend/app/core/output_redaction.py",
        "?? backend/app/core/patch_risk_analysis.py",
        "?? backend/app/core/open_source_report_audit.py",
        "?? backend/app/core/task_environment_contracts.py",
        "?? backend/app/core/pr_review_readiness.py",
        "?? backend/app/core/instruction_source_audit.py",
        "?? backend/app/core/browser_task_readiness.py",
        "?? backend/app/core/open_source_adoption_matrix.py",
        "?? backend/app/core/agent_eval_matrix.py",
        "?? backend/app/core/subagent_handoff_matrix.py",
        "?? backend/app/core/mcp_tool_readiness.py",
        "?? backend/app/core/channel_integration_readiness.py",
        "?? backend/app/core/release_evidence_pack.py",
        "?? backend/app/core/runtime_capability_manifest.py",
        "?? backend/app/core/integration_candidate_scorecard.py",
        "?? backend/app/core/integration_decision_audit.py",
        "?? backend/app/core/integration_readiness_snapshot.py",
        "?? backend/app/core/candidate_dependency_map.py",
        "?? backend/app/core/integration_sequence_plan.py",
        "?? backend/app/core/integration_traceability_index.py",
        "?? backend/app/core/integration_review_packet.py",
        "?? backend/app/core/integration_governance_summary.py",
        "?? backend/app/core/integration_followup_queue.py",
        "?? backend/app/core/integration_owner_digest.py",
        "?? backend/app/core/integration_closure_checklist.py",
        "?? backend/app/core/integration_final_review_brief.py",
        "?? backend/app/core/integration_adoption_readme.py",
        "?? backend/app/core/integration_rollout_guardrails.py",
        "?? backend/app/core/integration_post_adoption_monitor.py",
        "?? backend/app/core/integration_sunset_review.py",
        "?? backend/app/core/integration_secondary_index.py",
        "?? backend/app/core/integration_conflict_risk_register.py",
        "?? backend/app/core/integration_review_readiness_gate.py",
        "?? backend/app/core/integration_review_packet_manifest.py",
        "?? backend/app/core/integration_stage_label_policy.py",
        "?? backend/app/core/integration_manifest_diff_summary.py",
        "?? backend/app/core/integration_manifest_review_digest.py",
        "?? backend/app/core/integration_reviewer_assignment_matrix.py",
        "?? backend/app/core/integration_review_calendar.py",
        "?? backend/app/core/integration_review_minutes.py",
        "?? backend/app/core/integration_review_archive_manifest.py",
        "?? backend/app/core/integration_review_retention_policy.py",
        "?? backend/app/core/integration_review_evidence_index.py",
        "?? backend/app/core/integration_review_query_plan.py",
        "?? backend/app/core/integration_review_query_result_digest.py",
        "?? backend/app/core/integration_review_answer_brief.py",
        "?? backend/app/core/integration_review_answer_action_matrix.py",
        "?? backend/app/core/integration_review_action_status_board.py",
        "?? backend/app/core/codex_tool_runtime_readiness_packet.py",
        "?? backend/app/core/codex_permission_sandbox_readiness_packet.py",
        "?? backend/app/core/codex_memory_context_readiness_packet.py",
        "?? backend/app/core/codex_background_task_readiness_packet.py",
        "?? tests/test_workflow_events.py",
        "?? tests/test_long_tasks_recovery_audit.py",
        "?? tests/test_skill_bundles.py",
        "?? tests/test_trace_analysis.py",
        "?? tests/test_agent_orchestration_runtime.py",
        "?? tests/test_agent_registry.py",
        "?? tests/test_policy_risk_analysis.py",
        "?? tests/test_acceptance_matrix.py",
        "?? tests/test_model_provider_contracts.py",
        "?? tests/test_deployment_security_contracts.py",
        "?? tests/test_url_safety.py",
        "?? tests/test_output_redaction.py",
        "?? tests/test_patch_risk_analysis.py",
        "?? tests/test_open_source_report_audit.py",
        "?? tests/test_task_environment_contracts.py",
        "?? tests/test_pr_review_readiness.py",
        "?? tests/test_instruction_source_audit.py",
        "?? tests/test_browser_task_readiness.py",
        "?? tests/test_open_source_adoption_matrix.py",
        "?? tests/test_agent_eval_matrix.py",
        "?? tests/test_subagent_handoff_matrix.py",
        "?? tests/test_mcp_tool_readiness.py",
        "?? tests/test_channel_integration_readiness.py",
        "?? tests/test_release_evidence_pack.py",
        "?? tests/test_runtime_capability_manifest.py",
        "?? tests/test_integration_candidate_scorecard.py",
        "?? tests/test_integration_decision_audit.py",
        "?? tests/test_integration_readiness_snapshot.py",
        "?? tests/test_candidate_dependency_map.py",
        "?? tests/test_integration_sequence_plan.py",
        "?? tests/test_integration_traceability_index.py",
        "?? tests/test_integration_review_packet.py",
        "?? tests/test_integration_governance_summary.py",
        "?? tests/test_integration_followup_queue.py",
        "?? tests/test_integration_owner_digest.py",
        "?? tests/test_integration_closure_checklist.py",
        "?? tests/test_integration_final_review_brief.py",
        "?? tests/test_integration_adoption_readme.py",
        "?? tests/test_integration_rollout_guardrails.py",
        "?? tests/test_integration_post_adoption_monitor.py",
        "?? tests/test_integration_sunset_review.py",
        "?? tests/test_integration_secondary_index.py",
        "?? tests/test_integration_conflict_risk_register.py",
        "?? tests/test_integration_review_readiness_gate.py",
        "?? tests/test_integration_review_packet_manifest.py",
        "?? tests/test_integration_stage_label_policy.py",
        "?? tests/test_integration_manifest_diff_summary.py",
        "?? tests/test_integration_manifest_review_digest.py",
        "?? tests/test_integration_reviewer_assignment_matrix.py",
        "?? tests/test_integration_review_calendar.py",
        "?? tests/test_integration_review_minutes.py",
        "?? tests/test_integration_review_archive_manifest.py",
        "?? tests/test_integration_review_retention_policy.py",
        "?? tests/test_integration_review_evidence_index.py",
        "?? tests/test_integration_review_query_plan.py",
        "?? tests/test_integration_review_query_result_digest.py",
        "?? tests/test_integration_review_answer_brief.py",
        "?? tests/test_integration_review_answer_action_matrix.py",
        "?? tests/test_integration_review_action_status_board.py",
        "?? tests/test_codex_tool_runtime_readiness_packet.py",
        "?? tests/test_codex_permission_sandbox_readiness_packet.py",
        "?? tests/test_codex_memory_context_readiness_packet.py",
        "?? tests/test_codex_background_task_readiness_packet.py",
        "?? docs/original-kernel-secondary-handoff.md",
        "?? docs/codex-gap-open-source-fill-report-2026-06-09.md",
        "?? docs/codex-capability-alignment-matrix-2026-06-12.md",
        "?? .agents/",
    ]

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=git_status_lines,
    )

    assert report["status"] == "original_kernel_delivery_manifest_ready"
    assert report["evidence_type"] == "original_kernel_delivery_manifest"
    assert report["entrypoints_modified"] is False
    assert report["api_router_modified"] is False
    assert report["control_plane_modified"] is False
    assert report["frontend_modified"] is False
    assert report["agent_loop_modified"] is False
    assert report["backend_core_init_modified"] is False
    assert report["mutation_performed"] is False
    assert report["report_file_written"] is False
    assert report["git_status_read_performed"] is True
    assert report["git_stage_performed"] is False
    assert report["git_commit_performed"] is False
    assert report["git_push_performed"] is False
    assert report["network_mutation_performed"] is False
    assert report["agent_execution_enabled"] is False
    assert report["command_execution_enabled"] is False
    assert report["full_codex_parity_claimed"] is False
    assert report["runtime_reports_stage_excluded"] is True
    assert report["stage_include_count"] == len(DEFAULT_STAGE_FILES)
    assert "frontend/src/App.tsx" not in report["stage_include_paths"]

    excluded = {item["path"]: item for item in report["excluded_dirty_paths"]}
    assert excluded["frontend/src/App.tsx"]["scope"] == "frontend"
    assert excluded["backend/app/api/workbench.py"]["scope"] == "api_router"
    assert excluded["backend/app/core/workflow_events.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/long_tasks_recovery_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/skill_bundles.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/trace_analysis.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/agent_orchestration_runtime.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/agent_registry.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/policy_risk_analysis.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/acceptance_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/model_provider_contracts.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/deployment_security_contracts.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/url_safety.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/output_redaction.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/patch_risk_analysis.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/open_source_report_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/task_environment_contracts.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/pr_review_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/instruction_source_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/browser_task_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/open_source_adoption_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/agent_eval_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/subagent_handoff_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/mcp_tool_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/channel_integration_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/release_evidence_pack.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/runtime_capability_manifest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_candidate_scorecard.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_decision_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_readiness_snapshot.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/candidate_dependency_map.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_sequence_plan.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_traceability_index.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_packet.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_governance_summary.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_followup_queue.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_owner_digest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_closure_checklist.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_final_review_brief.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_adoption_readme.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_rollout_guardrails.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_post_adoption_monitor.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_sunset_review.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_secondary_index.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_conflict_risk_register.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_readiness_gate.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_packet_manifest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_stage_label_policy.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_manifest_diff_summary.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_manifest_review_digest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_reviewer_assignment_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_calendar.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_minutes.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_archive_manifest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_retention_policy.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_evidence_index.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_query_plan.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_query_result_digest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_answer_brief.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_answer_action_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/integration_review_action_status_board.py"]["scope"] == "secondary_pending_candidate"
    assert excluded["backend/app/core/codex_tool_runtime_readiness_packet.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["backend/app/core/codex_permission_sandbox_readiness_packet.py"]["scope"] == (
        "secondary_integration_candidate"
    )
    assert excluded["backend/app/core/codex_memory_context_readiness_packet.py"]["scope"] == (
        "secondary_integration_candidate"
    )
    assert excluded["backend/app/core/codex_background_task_readiness_packet.py"]["scope"] == (
        "secondary_integration_candidate"
    )
    assert excluded["tests/test_workflow_events.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_long_tasks_recovery_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_skill_bundles.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_trace_analysis.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_agent_orchestration_runtime.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_agent_registry.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_policy_risk_analysis.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_acceptance_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_model_provider_contracts.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_deployment_security_contracts.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_url_safety.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_output_redaction.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_patch_risk_analysis.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_open_source_report_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_task_environment_contracts.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_pr_review_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_instruction_source_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_browser_task_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_open_source_adoption_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_agent_eval_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_subagent_handoff_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_mcp_tool_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_channel_integration_readiness.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_release_evidence_pack.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_runtime_capability_manifest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_candidate_scorecard.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_decision_audit.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_readiness_snapshot.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_candidate_dependency_map.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_sequence_plan.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_traceability_index.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_packet.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_governance_summary.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_followup_queue.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_owner_digest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_closure_checklist.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_final_review_brief.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_adoption_readme.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_rollout_guardrails.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_post_adoption_monitor.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_sunset_review.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_secondary_index.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_conflict_risk_register.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_readiness_gate.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_packet_manifest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_stage_label_policy.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_manifest_diff_summary.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_manifest_review_digest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_reviewer_assignment_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_calendar.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_minutes.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_archive_manifest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_retention_policy.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_evidence_index.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_query_plan.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_query_result_digest.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_answer_brief.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_answer_action_matrix.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_integration_review_action_status_board.py"]["scope"] == "secondary_pending_candidate"
    assert excluded["tests/test_codex_tool_runtime_readiness_packet.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_codex_permission_sandbox_readiness_packet.py"]["scope"] == (
        "secondary_integration_candidate"
    )
    assert excluded["tests/test_codex_memory_context_readiness_packet.py"]["scope"] == "secondary_integration_candidate"
    assert excluded["tests/test_codex_background_task_readiness_packet.py"]["scope"] == (
        "secondary_integration_candidate"
    )
    assert excluded["docs/original-kernel-secondary-handoff.md"]["scope"] == "secondary_handoff"
    assert excluded["docs/codex-gap-open-source-fill-report-2026-06-09.md"]["scope"] == "secondary_handoff"
    assert excluded["docs/codex-capability-alignment-matrix-2026-06-12.md"]["scope"] == "secondary_handoff"
    assert excluded[".agents/"]["scope"] == "agent_workspace_config"

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["required_stage_files_present"]["status"] == "passed"
    assert checks["no_mainline_entrypoint_or_ui_in_stage_manifest"]["status"] == "passed"
    assert checks["required_evidence_reports_ready"]["status"] == "passed"
    assert checks["excluded_dirty_paths_partitioned"]["status"] == "passed"


def test_original_kernel_delivery_manifest_includes_post_approval_owner_gates(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(reports_dir)
    owner_gate_paths = {
        "scripts/commercial_delivery_owner_approval_resume_packet.py",
        "scripts/commercial_delivery_owner_post_approval_operator_checklist.py",
        "tests/test_commercial_delivery_owner_approval_resume_packet.py",
        "tests/test_commercial_delivery_owner_post_approval_operator_checklist.py",
    }

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[f"?? {path}" for path in sorted(owner_gate_paths)],
    )

    assert report["status"] == "original_kernel_delivery_manifest_ready"
    assert owner_gate_paths <= set(report["stage_include_paths"])

    files = {item["path"]: item for item in report["files"]}
    assert files["scripts/commercial_delivery_owner_approval_resume_packet.py"]["category"] == (
        "commercial_delivery_gate_script"
    )
    assert files["scripts/commercial_delivery_owner_post_approval_operator_checklist.py"]["category"] == (
        "commercial_delivery_gate_script"
    )
    assert files["tests/test_commercial_delivery_owner_approval_resume_packet.py"]["category"] == (
        "commercial_delivery_gate_test"
    )
    assert files["tests/test_commercial_delivery_owner_post_approval_operator_checklist.py"]["category"] == (
        "commercial_delivery_gate_test"
    )
    excluded_paths = {item["path"] for item in report["excluded_dirty_paths"]}
    assert owner_gate_paths.isdisjoint(excluded_paths)


def test_original_kernel_delivery_manifest_includes_pre_approval_drift_guard_gate(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(reports_dir)
    drift_guard_paths = {
        "scripts/commercial_delivery_pre_approval_drift_guard.py",
        "tests/test_commercial_delivery_pre_approval_drift_guard.py",
    }

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[f" M {path}" for path in sorted(drift_guard_paths)],
    )

    assert report["status"] == "original_kernel_delivery_manifest_ready"
    assert drift_guard_paths <= set(report["stage_include_paths"])

    files = {item["path"]: item for item in report["files"]}
    assert files["scripts/commercial_delivery_pre_approval_drift_guard.py"]["category"] == (
        "commercial_delivery_gate_script"
    )
    assert files["tests/test_commercial_delivery_pre_approval_drift_guard.py"]["category"] == (
        "commercial_delivery_gate_test"
    )
    excluded_paths = {item["path"] for item in report["excluded_dirty_paths"]}
    assert drift_guard_paths.isdisjoint(excluded_paths)


def test_original_kernel_delivery_manifest_includes_owner_approval_payload_audit_gate(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(reports_dir)
    audit_paths = {
        "scripts/commercial_delivery_owner_approval_payload_audit.py",
        "tests/test_commercial_delivery_owner_approval_payload_audit.py",
    }

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[f" M {path}" for path in sorted(audit_paths)],
    )

    assert report["status"] == "original_kernel_delivery_manifest_ready"
    assert audit_paths <= set(report["stage_include_paths"])

    files = {item["path"]: item for item in report["files"]}
    assert files["scripts/commercial_delivery_owner_approval_payload_audit.py"]["category"] == (
        "commercial_delivery_gate_script"
    )
    assert files["tests/test_commercial_delivery_owner_approval_payload_audit.py"]["category"] == (
        "commercial_delivery_gate_test"
    )
    excluded_paths = {item["path"] for item in report["excluded_dirty_paths"]}
    assert audit_paths.isdisjoint(excluded_paths)


def test_original_kernel_delivery_manifest_blocks_missing_required_file(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES, omit={"backend/app/core/storage.py"})
    _write_evidence_reports(reports_dir)

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[],
    )

    assert report["status"] == "original_kernel_delivery_manifest_blocked"
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["required_stage_files_present"]["status"] == "failed"
    assert checks["required_stage_files_present"]["details"]["missing"] == [
        "backend/app/core/storage.py"
    ]


def test_original_kernel_delivery_manifest_blocks_forbidden_stage_path(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    stage_files = tuple(DEFAULT_STAGE_FILES) + (FileSpec("frontend/src/App.tsx", "frontend"),)
    _write_stage_files(tmp_path, stage_files)
    _write_evidence_reports(reports_dir)

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        stage_files=stage_files,
        git_status_lines=[],
    )

    assert report["status"] == "original_kernel_delivery_manifest_blocked"
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["no_mainline_entrypoint_or_ui_in_stage_manifest"]["status"] == "failed"
    assert checks["no_mainline_entrypoint_or_ui_in_stage_manifest"]["details"]["forbidden_paths"] == [
        "frontend/src/App.tsx"
    ]


def test_original_kernel_delivery_manifest_blocks_unready_evidence_report(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(
        reports_dir,
        overrides={
            "original-kernel-module-integration-summary.json": {
                "status": "failed",
                "evidence_type": "original_kernel_module_integration_summary",
            }
        },
    )

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[],
    )

    assert report["status"] == "original_kernel_delivery_manifest_blocked"
    evidence = {item["filename"]: item for item in report["evidence_reports"]}
    assert evidence["original-kernel-module-integration-summary.json"]["status"] == "failed"
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["required_evidence_reports_ready"]["status"] == "failed"
    assert checks["required_evidence_reports_ready"]["details"]["failed"] == [
        "original-kernel-module-integration-summary.json"
    ]


def test_original_kernel_delivery_manifest_blocks_parity_claim_in_evidence(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(
        reports_dir,
        overrides={
            "original-kernel-minimal-integration.json": {
                "status": "original_kernel_minimal_integration_ready",
                "evidence_type": "original_kernel_minimal_integration",
                "full_codex_parity_claimed": True,
            }
        },
    )

    report = build_report(
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[],
    )

    assert report["status"] == "original_kernel_delivery_manifest_blocked"
    evidence = {item["filename"]: item for item in report["evidence_reports"]}
    assert evidence["original-kernel-minimal-integration.json"]["full_codex_parity_claimed"] is True
    assert evidence["original-kernel-minimal-integration.json"]["status"] == "failed"


def test_original_kernel_delivery_manifest_write_report_records_report_file_only(tmp_path: Path) -> None:
    reports_dir = tmp_path / ".xagent_runtime" / "reports"
    _write_stage_files(tmp_path, DEFAULT_STAGE_FILES)
    _write_evidence_reports(reports_dir)
    output = reports_dir / "original-kernel-delivery-manifest.json"

    report = write_report(
        output,
        workspace_root=tmp_path,
        reports_dir=reports_dir,
        git_status_lines=[" M frontend/index.html"],
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload == report
    assert payload["status"] == "original_kernel_delivery_manifest_ready"
    assert payload["report_file_written"] is True
    assert payload["report_path"] == str(output)
    assert payload["git_stage_performed"] is False
    assert payload["git_commit_performed"] is False
    assert payload["git_push_performed"] is False
    assert payload["excluded_dirty_paths"][0]["scope"] == "frontend"


def _write_stage_files(root: Path, specs: Sequence[FileSpec], *, omit: set[str] | None = None) -> None:
    omitted = omit or set()
    for spec in specs:
        if spec.path in omitted:
            continue
        path = root / spec.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {spec.category}: {spec.path}\n", encoding="utf-8")


def _write_evidence_reports(
    reports_dir: Path,
    *,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> None:
    per_file_overrides = overrides or {}
    reports_dir.mkdir(parents=True, exist_ok=True)
    for spec in DEFAULT_EVIDENCE_REPORTS:
        payload = {
            "status": spec.status,
            "evidence_type": spec.evidence_type,
            "full_codex_parity_claimed": False,
        }
        payload.update(per_file_overrides.get(spec.filename, {}))
        (reports_dir / spec.filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
