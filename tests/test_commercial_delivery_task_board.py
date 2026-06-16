from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_task_board import (
    build_task_board,
    render_markdown_board,
    write_markdown_board,
    write_report,
)

STAGE_PATH_DIGEST = "path-digest-123"
STAGE_COMMAND_DIGEST = "command-digest-456"
EXPECTED_STAGE_PATH_SET_DIGEST = "path-set-digest-789"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_reports(reports_dir: Path, *, secondary_pending: bool = False) -> None:
    _write_json(
        reports_dir / "commercial-pilot-final-gate.json",
        {"status": "final_gate_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-pilot-acceptance-gate.json",
        {"status": "pilot_acceptance_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-pilot-handoff-index.json",
        {"status": "handoff_index_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "rc-delivery-status.json",
        {"status": "commercial_rc_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-pilot-channel-readiness.json",
        {"status": "ready_with_owner_gates", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-control-modes-preservation.json",
        {
            "status": "control_modes_preservation_ready",
            "owner_gated": True,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "plan_only_default": True,
                "execute_true_required_for_agent_run": True,
                "loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_surface_file_count": 12,
                "stage_in_original_kernel_manifest": False,
            },
        },
    )
    excluded = [
        {"path": "backend/app/core/browser_task_readiness.py", "scope": "secondary_integration_candidate"},
    ]
    if secondary_pending:
        excluded.append(
            {"path": "backend/app/core/open_source_adoption_matrix.py", "scope": "secondary_pending_candidate"}
        )
    _write_json(
        reports_dir / "original-kernel-delivery-manifest.json",
        {
            "status": "original_kernel_delivery_manifest_ready",
            "stage_include_count": 54,
            "excluded_dirty_count": len(excluded),
            "excluded_dirty_paths": excluded,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "entrypoints_modified": False,
            "api_router_modified": False,
            "control_plane_modified": False,
            "frontend_modified": False,
            "agent_loop_modified": False,
            "backend_core_init_modified": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-staging-review.json",
        {
            "status": "staging_review_ready",
            "owner_gated": True,
            "eligible_stage_count": 54,
            "blocked_stage_count": 0,
            "unchanged_stage_count": 0,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-packet.json",
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_commands": [
                "git add -- 'backend/app/core/storage.py'",
                "git add -- 'tests/test_storage.py'",
            ],
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-preflight.json",
        {
            "status": "owner_staging_preflight_ready",
            "owner_gated": True,
            "stage_command_count": 2,
            "cached_staged_path_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        {
            "status": "owner_post_staging_verification_blocked",
            "owner_gated": True,
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 0,
            "summary": {
                "blocking_reasons": [
                    "cached_paths_present_after_owner_staging",
                    "cached_path_set_digest_matches_expected_paths",
                ]
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-command-audit.json",
        {
            "status": "owner_command_audit_ready",
            "owner_gated": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "ready_for_owner_staging_decision",
            "owner_gated": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-refresh-chain-receipt.json",
        {
            "status": "commercial_delivery_refresh_chain_receipt_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-runbook.json",
        {
            "status": "owner_staging_runbook_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        {
            "status": "owner_post_stage_commit_gate_blocked",
            "commit_allowed": False,
            "summary": {"blocking_reasons": ["owner_post_staging_verification_ready"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-commit-packet.json",
        {
            "status": "owner_commit_packet_blocked",
            "commit_allowed": False,
            "summary": {"blocking_reasons": ["owner_post_stage_commit_gate_ready"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-rollback-plan.json",
        {
            "status": "owner_staging_rollback_plan_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-delivery-packet.json",
        {
            "status": "owner_delivery_packet_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-request.json",
        {
            "status": "owner_stage_approval_request_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": False,
            "approval_payload_valid": False,
            "ready_for_approval_gate": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        {
            "status": "owner_stage_approval_brief_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-gate.json",
        {
            "status": "owner_stage_approval_blocked",
            "stage_allowed": False,
            "summary": {"blocking_reasons": ["owner_approval_readable"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-execution-plan.json",
        {
            "status": "owner_stage_execution_blocked",
            "stage_allowed": False,
            "summary": {"blocking_reasons": ["approval_gate_ready"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ],
            "summary": {
                "stage_path_digest": STAGE_PATH_DIGEST,
                "stage_command_digest": STAGE_COMMAND_DIGEST,
                "expected_stage_path_set_digest": EXPECTED_STAGE_PATH_SET_DIGEST,
                "cached_staged_path_set_digest": None,
                "owner_action_required": True,
                "owner_blocking_reason_count": 6,
                "owner_blocking_reasons_by_report": {
                    "owner_stage_approval_gate": ["owner_approval_readable"],
                    "owner_stage_execution_plan": ["approval_gate_ready"],
                    "owner_post_staging_verifier": [
                        "cached_paths_present_after_owner_staging",
                        "cached_path_set_digest_matches_expected_paths",
                    ],
                    "owner_post_stage_commit_gate": ["owner_post_staging_verification_ready"],
                    "owner_commit_packet": ["owner_post_stage_commit_gate_ready"],
                },
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_ready",
            "real_owner_approval_present": False,
            "summary": {
                "stage_path_digest": STAGE_PATH_DIGEST,
                "stage_command_digest": STAGE_COMMAND_DIGEST,
                "expected_stage_path_set_digest": EXPECTED_STAGE_PATH_SET_DIGEST,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        {
            "status": "owner_approval_resume_packet_waiting_for_owner",
            "waiting_for_owner": True,
            "resume_ready": False,
            "real_owner_approval_present": False,
            "summary": {
                "stage_path_digest": STAGE_PATH_DIGEST,
                "stage_command_digest": STAGE_COMMAND_DIGEST,
                "expected_stage_path_set_digest": EXPECTED_STAGE_PATH_SET_DIGEST,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-approval-operator-checklist.json",
        {
            "status": "owner_post_approval_operator_checklist_waiting_for_owner",
            "waiting_for_owner": True,
            "operator_ready": False,
            "real_owner_approval_present": False,
            "summary": {
                "stage_command_count": 2,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_waiting_for_owner",
            },
            "full_codex_parity_claimed": False,
        },
    )


def _write_handoff(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "## Secondary task queue",
                "",
                "Queue:",
                "1. `open_source_adoption_matrix.py`",
                "2. `agent_eval_matrix.py`",
                "3. `integration_review_action_status_board.py` - next",
                "- Completed `backend/app/core/integration_review_answer_action_matrix.py` as a detached candidate.",
            ]
        ),
        encoding="utf-8",
    )


def test_task_board_ready_with_current_delivery_evidence(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=["?? backend/app/core/browser_task_readiness.py"],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.evidence_type == "commercial_delivery_task_board"
    assert report.mutation_performed is False
    assert report.git_stage_performed is False
    assert report.full_codex_parity_claimed is False
    assert {check.status for check in report.checks} == {"passed"}
    staging = next(task for task in report.tasks if task.id == "owner_gated_staging_review")
    assert staging.status == "ready"
    assert staging.details["staging_review_status"] == "staging_review_ready"
    assert staging.details["owner_staging_packet_status"] == "owner_staging_packet_ready"
    assert staging.details["owner_staging_preflight_status"] == "owner_staging_preflight_ready"
    assert staging.details["owner_post_staging_verifier_status"] == "owner_post_staging_verification_blocked"
    assert staging.details["owner_decision_brief_status"] == "ready_for_owner_staging_decision"
    assert staging.details["owner_command_audit_status"] == "owner_command_audit_ready"
    assert staging.details["refresh_chain_receipt_status"] == "commercial_delivery_refresh_chain_receipt_ready"
    assert staging.details["owner_pre_stage_readiness_gate_status"] == "owner_pre_stage_readiness_ready"
    assert staging.details["owner_staging_runbook_status"] == "owner_staging_runbook_ready"
    assert staging.details["owner_post_stage_commit_gate_status"] == "owner_post_stage_commit_gate_blocked"
    assert staging.details["owner_commit_packet_status"] == "owner_commit_packet_blocked"
    assert staging.details["owner_staging_rollback_plan_status"] == "owner_staging_rollback_plan_ready"
    assert staging.details["owner_delivery_packet_status"] == "owner_delivery_packet_ready"
    assert staging.details["owner_stage_approval_request_status"] == "owner_stage_approval_request_ready"
    assert staging.details["owner_stage_approval_brief_status"] == "owner_stage_approval_brief_ready"
    assert staging.details["owner_approval_handoff_status"] == "owner_approval_handoff_ready"
    assert staging.details["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert staging.details["owner_stage_execution_plan_status"] == "owner_stage_execution_blocked"
    assert staging.details["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_ready"
    assert staging.details["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert staging.details["owner_approval_resume_packet_waiting_for_owner"] is True
    assert staging.details["owner_approval_resume_packet_resume_ready"] is False
    assert (
        staging.details["owner_post_approval_operator_checklist_status"]
        == "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert staging.details["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert staging.details["owner_post_approval_operator_checklist_operator_ready"] is False
    assert staging.details["pre_approval_drift_guard_real_owner_approval_present"] is False
    assert staging.details["pre_approval_drift_guard_stage_path_digest"] == STAGE_PATH_DIGEST
    assert staging.details["pre_approval_drift_guard_stage_command_digest"] == STAGE_COMMAND_DIGEST
    assert staging.details["closure_snapshot_status"] == "commercial_delivery_closure_blocked"
    assert staging.details["closure_delivery_complete"] is False
    assert staging.details["closure_blockers"] == [
        "owner_stage_approval_gate_not_ready",
        "owner_stage_execution_plan_not_ready",
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    ]
    assert staging.details["closure_owner_action_required"] is True
    assert staging.details["closure_owner_blocking_reason_count"] == 6
    assert staging.details["closure_owner_blocking_reasons_by_report"]["owner_post_staging_verifier"] == [
        "cached_paths_present_after_owner_staging",
        "cached_path_set_digest_matches_expected_paths",
    ]
    assert staging.details["closure_stage_path_digest"] == STAGE_PATH_DIGEST
    assert staging.details["closure_stage_command_digest"] == STAGE_COMMAND_DIGEST
    assert staging.details["closure_expected_stage_path_set_digest"] == EXPECTED_STAGE_PATH_SET_DIGEST
    assert staging.details["closure_cached_staged_path_set_digest"] is None
    assert staging.details["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert staging.details["blocked_stage_count"] == 0
    assert staging.details["owner_stage_command_count"] == 2
    assert staging.details["cached_staged_path_count"] == 0
    assert staging.details["post_staging_cached_path_count"] == 0
    control_modes = next(task for task in report.tasks if task.id == "control_modes_preservation")
    assert control_modes.status == "ready"
    assert control_modes.details["plan_only_default"] is True
    assert control_modes.details["execute_true_required_for_agent_run"] is True
    assert control_modes.details["stage_in_original_kernel_manifest"] is False
    assert report.summary["owner_post_staging_verifier_status"] == "owner_post_staging_verification_blocked"
    assert report.summary["owner_decision_brief_status"] == "ready_for_owner_staging_decision"
    assert report.summary["owner_command_audit_status"] == "owner_command_audit_ready"
    assert report.summary["refresh_chain_receipt_status"] == "commercial_delivery_refresh_chain_receipt_ready"
    assert report.summary["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert report.summary["control_modes_plan_only_default"] is True
    assert report.summary["control_modes_loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert report.summary["control_modes_surface_file_count"] == 12
    assert report.summary["owner_pre_stage_readiness_gate_status"] == "owner_pre_stage_readiness_ready"
    assert report.summary["owner_staging_runbook_status"] == "owner_staging_runbook_ready"
    assert report.summary["owner_post_stage_commit_gate_status"] == "owner_post_stage_commit_gate_blocked"
    assert report.summary["owner_commit_packet_status"] == "owner_commit_packet_blocked"
    assert report.summary["owner_staging_rollback_plan_status"] == "owner_staging_rollback_plan_ready"
    assert report.summary["owner_delivery_packet_status"] == "owner_delivery_packet_ready"
    assert report.summary["owner_stage_approval_request_status"] == "owner_stage_approval_request_ready"
    assert report.summary["owner_approval_payload_audit_status"] == "owner_approval_payload_blocked"
    assert report.summary["owner_approval_payload_present"] is False
    assert report.summary["owner_approval_payload_valid"] is False
    assert report.summary["owner_stage_approval_brief_status"] == "owner_stage_approval_brief_ready"
    assert report.summary["owner_approval_handoff_status"] == "owner_approval_handoff_ready"
    assert report.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert report.summary["owner_stage_execution_plan_status"] == "owner_stage_execution_blocked"
    assert report.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert report.summary["owner_approval_resume_packet_waiting_for_owner"] is True
    assert report.summary["owner_approval_resume_packet_resume_ready"] is False
    assert (
        report.summary["owner_post_approval_operator_checklist_status"]
        == "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert report.summary["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert report.summary["owner_post_approval_operator_checklist_operator_ready"] is False
    assert report.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_ready"
    assert report.summary["pre_approval_drift_guard_real_owner_approval_present"] is False
    assert report.summary["pre_approval_drift_guard_stage_path_digest"] == STAGE_PATH_DIGEST
    assert report.summary["pre_approval_drift_guard_stage_command_digest"] == STAGE_COMMAND_DIGEST
    assert report.summary["pre_approval_drift_guard_expected_stage_path_set_digest"] == EXPECTED_STAGE_PATH_SET_DIGEST
    assert report.summary["closure_snapshot_status"] == "commercial_delivery_closure_blocked"
    assert report.summary["closure_delivery_complete"] is False
    assert report.summary["closure_blockers"] == [
        "owner_stage_approval_gate_not_ready",
        "owner_stage_execution_plan_not_ready",
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
        "cached_staged_path_set_digest_not_ready",
    ]
    assert report.summary["closure_owner_action_required"] is True
    assert report.summary["closure_owner_blocking_reason_count"] == 6
    assert report.summary["closure_owner_blocking_reasons_by_report"]["owner_stage_approval_gate"] == [
        "owner_approval_readable"
    ]
    assert report.summary["closure_owner_blocking_reasons_by_report"]["owner_post_staging_verifier"] == [
        "cached_paths_present_after_owner_staging",
        "cached_path_set_digest_matches_expected_paths",
    ]
    assert report.summary["closure_stage_path_digest"] == STAGE_PATH_DIGEST
    assert report.summary["closure_stage_command_digest"] == STAGE_COMMAND_DIGEST
    assert report.summary["closure_expected_stage_path_set_digest"] == EXPECTED_STAGE_PATH_SET_DIGEST
    assert report.summary["closure_cached_staged_path_set_digest"] is None
    assert report.summary["secondary_handoff_next_count"] == 1
    assert report.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert report.summary["secondary_handoff_completed_count"] == 1
    assert (
        report.summary["secondary_handoff_latest_completed_candidate"]
        == "integration_review_answer_action_matrix.py"
    )
    secondary = next(task for task in report.tasks if task.id == "secondary_handoff_sync")
    assert secondary.status == "tracking_secondary_next"
    assert secondary.details["handoff_queue"] == [
        "open_source_adoption_matrix.py",
        "agent_eval_matrix.py",
        "integration_review_action_status_board.py",
    ]
    assert secondary.details["handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert secondary.details["handoff_completed_candidates"] == [
        "integration_review_answer_action_matrix.py"
    ]
    assert (
        secondary.details["handoff_latest_completed_candidate"]
        == "integration_review_answer_action_matrix.py"
    )


def test_task_board_tracks_completed_handoff_heading_sections(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    heading_candidate = (
        "integration_review_manifest_adoption_tracker_notification_notification_notification_notification_"
        "notification_notification_notification_notification_notification_owner_handoff.py"
    )
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "\n".join(
            [
                "## Secondary task queue",
                "",
                "Queue:",
                "1. `integration_review_action_status_board.py` - next",
                "- Completed `backend/app/core/integration_review_answer_action_matrix.py` as a detached candidate.",
                "",
                "### 2026-06-11: Integration review manifest adoption tracker notification notification "
                "notification notification notification notification notification notification notification owner handoff "
                "(#102 completed)",
                "",
                "Files:",
                f"- `backend/app/core/{heading_candidate}`",
                f"- `tests/test_{heading_candidate}`",
            ]
        ),
        encoding="utf-8",
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["secondary_handoff_completed_count"] == 2
    assert report.summary["secondary_handoff_latest_completed_candidate"] == heading_candidate
    secondary = next(task for task in report.tasks if task.id == "secondary_handoff_sync")
    assert secondary.details["handoff_completed_candidates"] == [
        "integration_review_answer_action_matrix.py",
        heading_candidate,
    ]
    assert secondary.details["handoff_latest_completed_candidate"] == heading_candidate


def test_task_board_tracks_dated_packet_handoff_sections_without_completed_marker(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    dated_candidate = (
        "codex_secondary_integration_adoption_decision_archive_followup_"
        "disposition_preview_packet.py"
    )
    next_candidate = (
        "backend/app/core/codex_secondary_integration_adoption_decision_archive_followup_"
        "closure_readiness_packet.py"
    )
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "\n".join(
            [
                "## Secondary task queue",
                "",
                "Queue:",
                "1. `integration_review_action_status_board.py` - next",
                "- Completed `backend/app/core/integration_review_answer_action_matrix.py` as a detached candidate.",
                "",
                "### 2026-06-13: Codex secondary integration adoption decision archive "
                "followup disposition preview packet",
                "",
                "Files:",
                f"- `backend/app/core/{dated_candidate}`",
                f"- `tests/test_{dated_candidate}`",
                "",
                "Validation commands and results:",
                "- Result: `543 passed`",
                "",
                "Next planned Codex-gap secondary candidate:",
                f"- `{next_candidate}`",
            ]
        ),
        encoding="utf-8",
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["secondary_handoff_next_queue"] == [next_candidate]
    assert report.summary["secondary_handoff_completed_count"] == 2
    assert report.summary["secondary_handoff_latest_completed_candidate"] == dated_candidate
    secondary = next(task for task in report.tasks if task.id == "secondary_handoff_sync")
    assert secondary.details["handoff_completed_candidates"] == [
        "integration_review_answer_action_matrix.py",
        dated_candidate,
    ]
    assert secondary.details["handoff_latest_completed_candidate"] == dated_candidate


def test_task_board_tracks_secondary_pending_without_blocking_owner_staging(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir, secondary_pending=True)
    _write_handoff(handoff)

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["secondary_pending_count"] == 1
    assert report.summary["secondary_handoff_next_count"] == 1
    assert report.summary["secondary_pending_blocks_owner_staging"] is False
    secondary = next(task for task in report.tasks if task.id == "secondary_handoff_sync")
    assert secondary.status == "waiting_secondary_validation"
    assert secondary.details["secondary_pending_paths"] == [
        "backend/app/core/open_source_adoption_matrix.py"
    ]


def test_task_board_accounts_for_post_staging_preflight_with_commit_packet_pending(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    preflight = json.loads((reports_dir / "commercial-delivery-owner-staging-preflight.json").read_text(encoding="utf-8"))
    preflight["status"] = "owner_staging_preflight_blocked"
    preflight["cached_staged_path_count"] = 2
    (reports_dir / "commercial-delivery-owner-staging-preflight.json").write_text(
        json.dumps(preflight),
        encoding="utf-8",
    )
    post_staging = json.loads(
        (reports_dir / "commercial-delivery-owner-post-staging-verifier.json").read_text(encoding="utf-8")
    )
    post_staging["status"] = "owner_post_staging_verification_ready"
    post_staging["cached_staged_path_count"] = 2
    post_staging["summary"] = {"cached_staged_path_count": 2}
    (reports_dir / "commercial-delivery-owner-post-staging-verifier.json").write_text(
        json.dumps(post_staging),
        encoding="utf-8",
    )
    commit_packet = json.loads((reports_dir / "commercial-delivery-owner-commit-packet.json").read_text(encoding="utf-8"))
    commit_packet["status"] = "owner_commit_packet_blocked"
    (reports_dir / "commercial-delivery-owner-commit-packet.json").write_text(
        json.dumps(commit_packet),
        encoding="utf-8",
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    check = next(check for check in report.checks if check.name == "owner_staging_preflight_accounted_for")
    assert check.status == "passed"
    assert report.summary["owner_staging_preflight_accounted_for"] is True
    assert report.summary["owner_post_staging_verifier_status"] == "owner_post_staging_verification_ready"


def test_task_board_normalizes_manifest_paths_for_secondary_pending(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    manifest_path = reports_dir / "original-kernel-delivery-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["excluded_dirty_paths"] = [
        {
            "path": "backend\\app\\core\\integration_followup_queue.py",
            "scope": "secondary_pending_candidate",
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["secondary_pending_count"] == 1
    secondary = next(task for task in report.tasks if task.id == "secondary_handoff_sync")
    assert secondary.details["secondary_pending_paths"] == [
        "backend/app/core/integration_followup_queue.py"
    ]


def test_task_board_blocks_when_required_report_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-pilot-final-gate.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    missing = next(task for task in report.tasks if task.id == "missing_or_unreadable_reports")
    assert missing.status == "blocked"
    assert "final_gate" in missing.details["errors"]


def test_task_board_blocks_when_staging_review_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-staging-review.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    staging_check = next(check for check in report.checks if check.name == "staging_review_ready")
    assert staging_check.status == "failed"
    staging_task = next(task for task in report.tasks if task.id == "owner_gated_staging_review")
    assert staging_task.status == "blocked"


def test_task_board_blocks_when_owner_staging_packet_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-staging-packet.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    packet_check = next(check for check in report.checks if check.name == "owner_staging_packet_ready")
    assert packet_check.status == "failed"
    assert "owner_staging_packet" in next(task for task in report.tasks if task.id == "missing_or_unreadable_reports").details["errors"]


def test_task_board_does_not_block_when_optional_owner_decision_brief_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-decision-brief.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_decision_brief_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_owner_command_audit_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-command-audit.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_command_audit_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_refresh_chain_receipt_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-refresh-chain-receipt.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["refresh_chain_receipt_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_owner_pre_stage_gate_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_pre_stage_readiness_gate_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_owner_staging_runbook_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-staging-runbook.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_staging_runbook_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_owner_post_stage_commit_gate_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_post_stage_commit_gate_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_owner_commit_packet_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-commit-packet.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_commit_packet_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_does_not_block_when_optional_owner_delivery_packet_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-delivery-packet.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert report.summary["owner_delivery_packet_status"] is None
    assert not any(task.id == "missing_or_unreadable_reports" for task in report.tasks)


def test_task_board_blocks_when_owner_staging_preflight_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    (reports_dir / "commercial-delivery-owner-staging-preflight.json").unlink()

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    preflight_check = next(check for check in report.checks if check.name == "owner_staging_preflight_accounted_for")
    assert preflight_check.status == "failed"
    staging_task = next(task for task in report.tasks if task.id == "owner_gated_staging_review")
    assert staging_task.status == "blocked"
    assert "owner_staging_preflight" in next(
        task for task in report.tasks if task.id == "missing_or_unreadable_reports"
    ).details["errors"]


def test_task_board_blocks_when_owner_staging_preflight_is_blocked(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-preflight.json",
        {
            "status": "owner_staging_preflight_blocked",
            "owner_gated": True,
            "stage_command_count": 2,
            "cached_staged_path_count": 1,
            "full_codex_parity_claimed": False,
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    preflight_check = next(check for check in report.checks if check.name == "owner_staging_preflight_accounted_for")
    assert preflight_check.status == "failed"
    assert report.summary["owner_staging_preflight_status"] == "owner_staging_preflight_blocked"
    assert report.summary["owner_staging_preflight_accounted_for"] is False
    assert report.summary["cached_staged_path_count"] == 1


def test_task_board_accepts_preflight_blocked_after_post_staging_ready(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-preflight.json",
        {
            "status": "owner_staging_preflight_blocked",
            "owner_gated": True,
            "stage_command_count": 2,
            "cached_staged_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        {
            "status": "owner_post_staging_verification_ready",
            "owner_gated": True,
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        {
            "status": "owner_post_stage_commit_gate_ready",
            "commit_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-commit-packet.json",
        {
            "status": "owner_commit_packet_ready",
            "commit_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert next(check for check in report.checks if check.name == "owner_staging_preflight_accounted_for").status == "passed"
    staging = next(task for task in report.tasks if task.id == "owner_gated_staging_review")
    assert staging.status == "ready"
    assert staging.details["owner_staging_preflight_status"] == "owner_staging_preflight_blocked"
    assert staging.details["owner_staging_preflight_accounted_for"] is True
    assert report.summary["owner_staging_preflight_accounted_for"] is True
    assert report.summary["owner_post_staging_verifier_status"] == "owner_post_staging_verification_ready"
    assert report.summary["owner_post_stage_commit_gate_status"] == "owner_post_stage_commit_gate_ready"
    assert report.summary["owner_commit_packet_status"] == "owner_commit_packet_ready"


def test_task_board_accepts_preflight_blocked_before_commit_gate_refresh(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-preflight.json",
        {
            "status": "owner_staging_preflight_blocked",
            "owner_gated": True,
            "stage_command_count": 2,
            "cached_staged_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        {
            "status": "owner_post_staging_verification_ready",
            "owner_gated": True,
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        {
            "status": "owner_post_stage_commit_gate_blocked",
            "commit_allowed": False,
            "summary": {"blocking_reasons": ["owner_decision_brief_pre_stage_ready"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-commit-packet.json",
        {
            "status": "owner_commit_packet_ready",
            "commit_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert next(check for check in report.checks if check.name == "owner_staging_preflight_accounted_for").status == "passed"
    assert report.summary["owner_staging_preflight_accounted_for"] is True
    assert report.summary["owner_post_stage_commit_gate_status"] == "owner_post_stage_commit_gate_blocked"


def test_task_board_accounts_for_post_approval_pre_approval_drift_guard(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        {
            "status": "owner_post_staging_verification_ready",
            "owner_gated": True,
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        {
            "status": "owner_post_stage_commit_gate_ready",
            "commit_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-commit-packet.json",
        {
            "status": "owner_commit_packet_ready",
            "commit_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        {
            "status": "owner_approval_payload_ready",
            "approval_payload_present": True,
            "approval_payload_valid": True,
            "ready_for_approval_gate": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-gate.json",
        {
            "status": "owner_stage_approval_ready",
            "stage_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-execution-plan.json",
        {
            "status": "owner_stage_execution_ready",
            "stage_allowed": True,
            "summary": {"blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_complete",
            "delivery_complete": True,
            "blockers": [],
            "summary": {
                "stage_path_digest": STAGE_PATH_DIGEST,
                "stage_command_digest": STAGE_COMMAND_DIGEST,
                "expected_stage_path_set_digest": EXPECTED_STAGE_PATH_SET_DIGEST,
                "cached_staged_path_set_digest": EXPECTED_STAGE_PATH_SET_DIGEST,
                "owner_action_required": False,
                "owner_blocking_reason_count": 0,
                "owner_blocking_reasons_by_report": {},
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "closure_snapshot": "commercial_delivery_complete",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "closure_snapshot_status": "commercial_delivery_complete",
                "closure_delivery_complete": True,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "secondary_handoff_summary_stable", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True
    assert report.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_blocked"


def test_task_board_accounts_for_post_commit_pre_approval_drift_guard(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_blocked",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_ready",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "closure_delivery_complete": False,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True
    assert report.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_blocked"
    assert report.summary["pre_approval_drift_guard_real_owner_approval_present"] is True


def test_task_board_accounts_for_post_commit_pre_approval_drift_guard_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_blocked",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "closure_delivery_complete": False,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_accounts_for_post_commit_drift_guard_with_missing_command_digest_sources(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_blocked",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "closure_delivery_complete": False,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {
                    "name": "stage_command_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_command_digest_sources": {
                            "owner_stage_approval_request": "b" * 64,
                            "owner_approval_handoff": None,
                            "owner_stage_approval_gate": None,
                            "owner_stage_execution_plan": "b" * 64,
                            "closure_snapshot": "b" * 64,
                            "task_board": "b" * 64,
                        }
                    },
                },
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_accounts_for_post_commit_drift_guard_with_all_missing_digest_sources(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_blocked",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "closure_delivery_complete": False,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {
                    "name": "stage_path_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_path_digest_sources": {
                            "owner_stage_approval_request": "a" * 64,
                            "owner_approval_handoff": None,
                            "owner_stage_approval_gate": None,
                            "owner_stage_execution_plan": "a" * 64,
                            "closure_snapshot": "a" * 64,
                            "task_board": "a" * 64,
                        }
                    },
                },
                {
                    "name": "stage_command_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_command_digest_sources": {
                            "owner_stage_approval_request": "b" * 64,
                            "owner_approval_handoff": None,
                            "owner_stage_approval_gate": None,
                            "owner_stage_execution_plan": "b" * 64,
                            "closure_snapshot": "b" * 64,
                            "task_board": "b" * 64,
                        }
                    },
                },
                {
                    "name": "expected_stage_path_set_digest_stable",
                    "status": "failed",
                    "details": {
                        "expected_stage_path_set_digest_sources": {
                            "owner_stage_approval_request": "c" * 64,
                            "owner_approval_handoff": None,
                            "closure_snapshot": "c" * 64,
                            "task_board": "c" * 64,
                        }
                    },
                },
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_accounts_for_post_commit_drift_guard_with_stale_task_board_digest(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)

    drift_guard_payload = {
        "status": "pre_approval_drift_guard_blocked",
        "real_owner_approval_present": True,
        "mutation_performed": False,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "full_codex_parity_claimed": False,
        "report_statuses": {
            "owner_stage_approval_request": "owner_stage_approval_request_blocked",
            "owner_approval_handoff": "owner_approval_handoff_blocked",
            "owner_approval_payload_audit": "owner_approval_payload_blocked",
            "owner_stage_approval_gate": "owner_stage_approval_blocked",
            "owner_stage_execution_plan": "owner_stage_execution_blocked",
            "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
            "closure_snapshot": "commercial_delivery_closure_blocked",
        },
        "summary": {
            "stage_path_digest": "a" * 64,
            "stage_command_digest": "b" * 64,
            "expected_stage_path_set_digest": "c" * 64,
            "owner_approval_payload_present": True,
            "owner_approval_payload_valid": False,
            "owner_approval_payload_ready_for_gate": False,
            "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
            "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
            "owner_post_approval_operator_checklist_status": (
                "owner_post_approval_operator_checklist_blocked"
            ),
            "owner_post_approval_operator_checklist_waiting_for_owner": False,
            "owner_post_approval_operator_checklist_operator_ready": False,
            "owner_post_approval_operator_checklist_real_owner_approval_present": True,
            "closure_snapshot_status": "commercial_delivery_closure_blocked",
            "closure_delivery_complete": False,
        },
        "checks": [
            {"name": "real_owner_approval_absent", "status": "failed"},
            {"name": "approval_request_ready", "status": "failed"},
            {"name": "approval_handoff_ready", "status": "failed"},
            {
                "name": "stage_path_digest_stable",
                "status": "failed",
                "details": {
                    "stage_path_digest_sources": {
                        "owner_stage_approval_request": "a" * 64,
                        "owner_approval_handoff": "a" * 64,
                        "owner_stage_approval_gate": "a" * 64,
                        "owner_stage_execution_plan": "a" * 64,
                        "closure_snapshot": "a" * 64,
                        "task_board": "d" * 64,
                    }
                },
            },
            {
                "name": "stage_command_digest_stable",
                "status": "failed",
                "details": {
                    "stage_command_digest_sources": {
                        "owner_stage_approval_request": "b" * 64,
                        "owner_approval_handoff": "b" * 64,
                        "owner_stage_approval_gate": "b" * 64,
                        "owner_stage_execution_plan": "b" * 64,
                        "closure_snapshot": "b" * 64,
                        "task_board": "e" * 64,
                    }
                },
            },
            {
                "name": "expected_stage_path_set_digest_stable",
                "status": "failed",
                "details": {
                    "expected_stage_path_set_digest_sources": {
                        "owner_stage_approval_request": "c" * 64,
                        "owner_approval_handoff": "c" * 64,
                        "closure_snapshot": "c" * 64,
                        "task_board": "f" * 64,
                    }
                },
            },
            {"name": "approval_payload_blocked_before_owner", "status": "failed"},
            {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
            {"name": "closure_blocked_before_owner", "status": "failed"},
        ],
    }
    _write_json(reports_dir / "commercial-delivery-pre-approval-drift-guard.json", drift_guard_payload)

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True

    _write_json(
        reports_dir / "commercial-delivery-refresh-chain-receipt.json",
        {"status": "commercial_delivery_refresh_chain_receipt_blocked", "full_codex_parity_claimed": False},
    )
    blocked_report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    blocked_drift_check = next(
        check for check in blocked_report.checks if check.name == "pre_approval_drift_guard_ready"
    )
    assert blocked_report.status == "commercial_delivery_blocked"
    assert blocked_drift_check.status == "failed"
    assert blocked_drift_check.details["pre_approval_drift_guard_accounted_for"] is False


def test_task_board_accounts_for_post_approval_noop_drift_guard(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_ready",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_complete",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_complete",
                "closure_delivery_complete": True,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {
                    "name": "stage_command_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_command_digest_sources": {
                            "owner_stage_approval_request": "b" * 64,
                            "owner_approval_handoff": None,
                            "owner_stage_approval_gate": "b" * 64,
                            "owner_stage_execution_plan": "b" * 64,
                            "closure_snapshot": "b" * 64,
                            "task_board": "b" * 64,
                        }
                    },
                },
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_accounts_for_post_approval_noop_task_board_digest_drift(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_ready",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_complete",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_complete",
                "closure_delivery_complete": True,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {
                    "name": "stage_path_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_path_digest_sources": {
                            "owner_stage_approval_request": "a" * 64,
                            "owner_stage_approval_gate": "a" * 64,
                            "owner_stage_execution_plan": "a" * 64,
                            "closure_snapshot": "a" * 64,
                            "task_board": "d" * 64,
                        }
                    },
                },
                {
                    "name": "stage_command_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_command_digest_sources": {
                            "owner_stage_approval_request": "b" * 64,
                            "owner_stage_approval_gate": "b" * 64,
                            "owner_stage_execution_plan": "b" * 64,
                            "closure_snapshot": "b" * 64,
                            "task_board": "e" * 64,
                        }
                    },
                },
                {
                    "name": "expected_stage_path_set_digest_stable",
                    "status": "failed",
                    "details": {
                        "expected_stage_path_set_digest_sources": {
                            "owner_stage_approval_request": "c" * 64,
                            "closure_snapshot": "c" * 64,
                            "task_board": "f" * 64,
                        }
                    },
                },
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_accounts_for_post_staging_pre_stage_task_board_digest_drift(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        {
            "status": "owner_post_staging_verification_ready",
            "owner_gated": True,
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 2,
            "summary": {"cached_staged_path_count": 2, "blocking_reasons": []},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_blocked",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "a" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "closure_delivery_complete": False,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {
                    "name": "stage_path_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_path_digest_sources": {
                            "owner_stage_approval_request": "a" * 64,
                            "owner_approval_handoff": "a" * 64,
                            "owner_stage_approval_gate": "a" * 64,
                            "owner_stage_execution_plan": "a" * 64,
                            "closure_snapshot": "a" * 64,
                            "task_board": "d" * 64,
                        }
                    },
                },
                {
                    "name": "stage_command_digest_stable",
                    "status": "failed",
                    "details": {
                        "stage_command_digest_sources": {
                            "owner_stage_approval_request": "b" * 64,
                            "owner_approval_handoff": "b" * 64,
                            "owner_stage_approval_gate": "b" * 64,
                            "owner_stage_execution_plan": "b" * 64,
                            "closure_snapshot": "b" * 64,
                            "task_board": "e" * 64,
                        }
                    },
                },
                {
                    "name": "expected_stage_path_set_digest_stable",
                    "status": "failed",
                    "details": {
                        "expected_stage_path_set_digest_sources": {
                            "owner_stage_approval_request": "a" * 64,
                            "owner_approval_handoff": "a" * 64,
                            "closure_snapshot": "a" * 64,
                            "task_board": "f" * 64,
                        }
                    },
                },
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_accounts_for_post_approval_boundary_drift_guard(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    drift_guard_payload = {
        "status": "pre_approval_drift_guard_blocked",
        "real_owner_approval_present": True,
        "mutation_performed": False,
        "git_stage_performed": False,
        "git_commit_performed": False,
        "git_push_performed": False,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "full_codex_parity_claimed": False,
        "report_statuses": {
            "owner_stage_approval_request": "owner_stage_approval_request_ready",
            "owner_approval_handoff": "owner_approval_handoff_blocked",
            "owner_approval_payload_audit": "owner_approval_payload_blocked",
            "owner_stage_approval_gate": "owner_stage_approval_blocked",
            "owner_stage_execution_plan": "owner_stage_execution_ready",
            "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
            "closure_snapshot": "commercial_delivery_complete",
        },
        "summary": {
            "stage_path_digest": "a" * 64,
            "stage_command_digest": "b" * 64,
            "expected_stage_path_set_digest": "c" * 64,
            "owner_approval_payload_present": True,
            "owner_approval_payload_valid": False,
            "owner_approval_payload_ready_for_gate": False,
            "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
            "owner_stage_execution_plan_status": "owner_stage_execution_ready",
            "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_blocked",
            "owner_post_approval_operator_checklist_waiting_for_owner": False,
            "owner_post_approval_operator_checklist_operator_ready": False,
            "owner_post_approval_operator_checklist_real_owner_approval_present": True,
            "closure_snapshot_status": "commercial_delivery_complete",
            "closure_delivery_complete": True,
        },
        "checks": [
            {"name": "real_owner_approval_absent", "status": "failed"},
            {"name": "approval_handoff_ready", "status": "failed"},
            {"name": "approval_payload_blocked_before_owner", "status": "failed"},
            {"name": "stage_execution_blocked_before_owner", "status": "failed"},
            {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
            {"name": "closure_blocked_before_owner", "status": "failed"},
        ],
    }
    _write_json(reports_dir / "commercial-delivery-pre-approval-drift-guard.json", drift_guard_payload)

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True

    drift_guard_payload["report_statuses"]["owner_stage_execution_plan"] = "owner_stage_execution_blocked"
    drift_guard_payload["summary"]["owner_stage_execution_plan_status"] = "owner_stage_execution_blocked"
    _write_json(reports_dir / "commercial-delivery-pre-approval-drift-guard.json", drift_guard_payload)

    blocked_report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    blocked_drift_check = next(
        check for check in blocked_report.checks if check.name == "pre_approval_drift_guard_ready"
    )
    assert blocked_report.status == "commercial_delivery_blocked"
    assert blocked_drift_check.status == "failed"
    assert blocked_drift_check.details["pre_approval_drift_guard_accounted_for"] is False


def test_task_board_accounts_for_receipt_expected_nonzero_drift_guard(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-refresh-chain-receipt.json",
        {
            "status": "commercial_delivery_refresh_chain_receipt_ready",
            "summary": {"expected_nonzero_steps": ["pre_approval_drift_guard"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_blocked",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_complete",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_complete",
                "closure_delivery_complete": True,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True

    receipt = json.loads((reports_dir / "commercial-delivery-refresh-chain-receipt.json").read_text(encoding="utf-8"))
    receipt["summary"]["expected_nonzero_steps"] = []
    _write_json(reports_dir / "commercial-delivery-refresh-chain-receipt.json", receipt)

    blocked_report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    blocked_drift_check = next(
        check for check in blocked_report.checks if check.name == "pre_approval_drift_guard_ready"
    )
    assert blocked_report.status == "commercial_delivery_blocked"
    assert blocked_drift_check.status == "failed"
    assert blocked_drift_check.details["pre_approval_drift_guard_accounted_for"] is False


def test_task_board_blocks_post_approval_pre_approval_drift_guard_without_ready_evidence(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "closure_snapshot": "commercial_delivery_complete",
            },
            "summary": {
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "closure_snapshot_status": "commercial_delivery_complete",
                "closure_delivery_complete": True,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "failed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is False


def test_task_board_accounts_for_post_approval_complete_pre_approval_drift_guard(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_blocked",
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_ready",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_ready"
                ),
                "owner_post_approval_operator_checklist_operator_ready": True,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "closure_delivery_complete": False,
            },
            "checks": [
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    drift_check = next(check for check in report.checks if check.name == "pre_approval_drift_guard_ready")
    assert report.status == "commercial_delivery_ready_for_owner_staging_review"
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_task_board_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    _write_json(
        reports_dir / "commercial-pilot-final-gate.json",
        {"status": "final_gate_ready", "full_codex_parity_claimed": True},
    )

    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    assert report.status == "commercial_delivery_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"


def test_write_report_and_markdown_board(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    handoff = tmp_path / "handoff.md"
    _write_reports(reports_dir)
    _write_handoff(handoff)
    report = build_task_board(
        reports_dir=reports_dir,
        secondary_handoff_path=handoff,
        git_status_lines=[],
    )

    json_output = tmp_path / "board.json"
    md_output = tmp_path / "board.md"
    write_report(report, json_output)
    write_markdown_board(report, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "commercial_delivery_ready_for_owner_staging_review"
    assert payload["tasks_count"] == len(payload["tasks"])
    assert payload["checks_count"] == len(payload["checks"])
    assert payload["next_actions_count"] == len(payload["next_actions"])
    assert payload["known_limits_count"] == len(payload["known_limits"])
    assert "Commercial Delivery Task Board" in markdown
    assert "Closure snapshot status" in markdown
    assert "Owner approval payload audit status" in markdown
    assert "Owner approval resume packet" in markdown
    assert STAGE_PATH_DIGEST in markdown
    assert EXPECTED_STAGE_PATH_SET_DIGEST in markdown
    assert "secondary_handoff_sync" in render_markdown_board(report)
