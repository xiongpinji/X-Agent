from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_refresh_chain_receipt import (
    CommandRunResult,
    build_refresh_chain_receipt,
    render_markdown_receipt,
    write_markdown_receipt,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ready_reports(reports_dir: Path, *, post_staging_status: str = "owner_post_staging_verification_blocked") -> None:
    pre_staging_blocked = post_staging_status == "owner_post_staging_verification_blocked"
    post_stage_commit_gate_status = (
        "owner_post_stage_commit_gate_blocked"
        if pre_staging_blocked
        else "owner_post_stage_commit_gate_ready"
    )
    owner_commit_packet_status = (
        "owner_commit_packet_blocked"
        if pre_staging_blocked
        else "owner_commit_packet_ready"
    )
    owner_stage_approval_gate_status = (
        "owner_stage_approval_blocked"
        if pre_staging_blocked
        else "owner_stage_approval_ready"
    )
    owner_approval_payload_audit_status = (
        "owner_approval_payload_blocked"
        if pre_staging_blocked
        else "owner_approval_payload_ready"
    )
    _write_json(
        reports_dir / "original-kernel-delivery-manifest.json",
        {"status": "original_kernel_delivery_manifest_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-control-modes-preservation.json",
        {
            "status": "control_modes_preservation_ready",
            "summary": {
                "plan_only_default": True,
                "loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_surface_file_count": 12,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-staging-review.json",
        {"status": "staging_review_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-packet.json",
        {"status": "owner_staging_packet_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-preflight.json",
        {"status": "owner_staging_preflight_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-staging-verifier.json",
        {
            "status": post_staging_status,
            "cached_staged_path_count": 0 if post_staging_status == "owner_post_staging_verification_blocked" else 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-task-board.json",
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": {
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_modes_surface_file_count": 12,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-command-audit.json",
        {"status": "owner_command_audit_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {"status": "ready_for_owner_staging_decision", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {"status": "owner_pre_stage_readiness_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-runbook.json",
        {"status": "owner_staging_runbook_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-stage-commit-gate.json",
        {
            "status": post_stage_commit_gate_status,
            "summary": {
                "cached_staged_path_count": 0 if post_stage_commit_gate_status.endswith("_blocked") else 2,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-commit-packet.json",
        {
            "status": owner_commit_packet_status,
            "summary": {
                "cached_staged_path_count": 0 if owner_commit_packet_status.endswith("_blocked") else 2,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-rollback-plan.json",
        {"status": "owner_staging_rollback_plan_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-delivery-packet.json",
        {
            "status": "owner_delivery_packet_ready",
            "stage_ready": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "owner_stage_execution_stage_command_count": 2,
                "rollback_reset_command_count": 2,
            },
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-request.json",
        {"status": "owner_stage_approval_request_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        {
            "status": owner_approval_payload_audit_status,
            "approval_payload_present": not pre_staging_blocked,
            "ready_for_approval_gate": not pre_staging_blocked,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        {"status": "owner_stage_approval_brief_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {"status": "owner_approval_handoff_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-execution-plan.json",
        {
            "status": "owner_stage_execution_blocked" if pre_staging_blocked else "owner_stage_execution_ready",
            "stage_allowed": not pre_staging_blocked,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-gate.json",
        {
            "status": owner_stage_approval_gate_status,
            "stage_allowed": owner_stage_approval_gate_status == "owner_stage_approval_ready",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked" if pre_staging_blocked else "commercial_delivery_complete",
            "delivery_complete": not pre_staging_blocked,
            "stage_ready": True,
            "full_codex_parity_claimed": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ]
            if pre_staging_blocked
            else [],
            "checks": [
                {"name": "owner_approval_ready", "status": "failed"},
                {"name": "stage_execution_ready", "status": "failed"},
                {"name": "post_stage_ready", "status": "failed"},
                {"name": "commit_ready", "status": "failed"},
                {"name": "cached_staged_path_set_digest_consistent", "status": "failed"},
            ]
            if pre_staging_blocked
            else [{"name": "delivery_complete", "status": "passed"}],
            "summary": {
                "refresh_chain_step_count": 24 if pre_staging_blocked else 26,
            },
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-pre-approval-drift-guard.json",
        {
            "status": "pre_approval_drift_guard_ready",
            "real_owner_approval_present": False,
            "summary": {
                "stage_path_digest": "path-digest-123",
                "stage_command_digest": "command-digest-456",
                "expected_stage_path_set_digest": "path-set-digest-789",
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        {
            "status": "owner_approval_resume_packet_waiting_for_owner"
            if pre_staging_blocked
            else "owner_approval_resume_packet_ready",
            "waiting_for_owner": pre_staging_blocked,
            "resume_ready": not pre_staging_blocked,
            "real_owner_approval_present": not pre_staging_blocked,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-post-approval-operator-checklist.json",
        {
            "status": "owner_post_approval_operator_checklist_waiting_for_owner"
            if pre_staging_blocked
            else "owner_post_approval_operator_checklist_ready",
            "waiting_for_owner": pre_staging_blocked,
            "operator_ready": not pre_staging_blocked,
            "real_owner_approval_present": not pre_staging_blocked,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-report-count-alias-normalization.json",
        {
            "kind": "report_count_alias_normalization",
            "ok": True,
            "status": "passed",
            "include_globs": ["commercial-delivery-*.json"],
            "include_globs_count": 1,
            "updated_reports": [],
            "updated_reports_count": 0,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-report-hygiene.json",
        {
            "kind": "report_hygiene",
            "ok": True,
            "status": "passed",
            "include_globs": ["commercial-delivery-*.json"],
            "include_globs_count": 1,
            "issue_artifacts": [],
            "issue_artifacts_count": 0,
            "artifacts": [],
            "artifacts_count": 0,
        },
    )


def _runner(returncodes: dict[str, int] | None = None):
    returncodes = returncodes or {}

    def run(command: list[str], timeout_seconds: float) -> CommandRunResult:
        script = command[1].replace("scripts\\", "").replace(".py", "")
        name = {
            "normalize_report_count_aliases": "commercial_delivery_report_count_alias_normalization",
            "check_report_hygiene": "commercial_delivery_report_hygiene",
        }.get(script, script)
        return CommandRunResult(
            command=command,
            returncode=returncodes.get(name, 0),
            duration_seconds=0.01,
            stdout=f"{name} api_key=super-secret-value",
            stderr="",
            timed_out=False,
        )

    return run


def _post_commit_history_runner(
    reports_dir: Path,
    returncodes: dict[str, int] | None = None,
):
    returncodes = returncodes or {}
    delivery_packet_runs = 0

    def run(command: list[str], timeout_seconds: float) -> CommandRunResult:
        nonlocal delivery_packet_runs
        script = command[1].replace("scripts\\", "").replace(".py", "")
        name = {
            "normalize_report_count_aliases": "commercial_delivery_report_count_alias_normalization",
            "check_report_hygiene": "commercial_delivery_report_hygiene",
        }.get(script, script)
        if name == "commercial_delivery_owner_delivery_packet":
            delivery_packet_runs += 1
            if delivery_packet_runs == 2:
                _write_json(
                    reports_dir / "commercial-delivery-owner-delivery-packet.json",
                    {
                        "status": "owner_delivery_packet_ready",
                        "stage_ready": True,
                        "full_codex_parity_claimed": False,
                        "summary": {
                            "stage_include_count": 100,
                            "owner_stage_command_count": 1,
                            "owner_stage_execution_stage_command_count": 1,
                            "rollback_reset_command_count": 1,
                        },
                    },
                )
                return CommandRunResult(
                    command=command,
                    returncode=0,
                    duration_seconds=0.01,
                    stdout=f"{name} api_key=super-secret-value",
                    stderr="",
                    timed_out=False,
                )
        return CommandRunResult(
            command=command,
            returncode=returncodes.get(name, 0),
            duration_seconds=0.01,
            stdout=f"{name} api_key=super-secret-value",
            stderr="",
            timed_out=False,
        )

    return run


def test_refresh_chain_receipt_ready_with_expected_pre_staging_nonzero(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir)

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner(
            {
                "commercial_delivery_owner_post_staging_verifier": 1,
                "commercial_delivery_owner_post_stage_commit_gate": 1,
                "commercial_delivery_owner_commit_packet": 1,
                "commercial_delivery_owner_approval_payload_audit": 1,
                "commercial_delivery_owner_stage_approval_gate": 1,
                "commercial_delivery_owner_stage_execution_plan": 1,
                "commercial_delivery_closure_snapshot": 1,
            }
        ),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.evidence_type == "commercial_delivery_refresh_chain_receipt"
    assert receipt.mutation_performed is False
    assert receipt.git_stage_performed is False
    assert receipt.git_commit_performed is False
    assert receipt.git_push_performed is False
    assert receipt.network_mutation_performed is False
    assert receipt.agent_execution_enabled is False
    assert receipt.full_codex_parity_claimed is False
    assert receipt.summary["expected_nonzero_steps"] == [
        "owner_post_staging_verifier",
        "owner_post_stage_commit_gate",
        "owner_commit_packet",
        "owner_approval_payload_audit",
        "owner_stage_approval_gate",
        "owner_stage_execution_plan",
        "closure_snapshot",
    ]
    assert receipt.summary["expected_nonzero_step_count"] == 7
    assert receipt.summary["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert receipt.summary["control_modes_plan_only_default"] is True
    assert receipt.summary["control_modes_loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert receipt.summary["control_modes_surface_file_count"] == 12
    assert receipt.summary["secondary_pending_count"] == 0
    assert receipt.summary["secondary_handoff_next_count"] == 1
    assert receipt.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert receipt.summary["secondary_handoff_completed_count"] == 44
    assert receipt.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert receipt.summary["owner_pre_stage_readiness_gate_status"] == "owner_pre_stage_readiness_ready"
    assert receipt.summary["owner_staging_runbook_status"] == "owner_staging_runbook_ready"
    assert receipt.summary["owner_post_stage_commit_gate_status"] == "owner_post_stage_commit_gate_blocked"
    assert receipt.summary["owner_commit_packet_status"] == "owner_commit_packet_blocked"
    assert receipt.summary["owner_staging_rollback_plan_status"] == "owner_staging_rollback_plan_ready"
    assert receipt.summary["owner_delivery_packet_status"] == "owner_delivery_packet_ready"
    assert receipt.summary["owner_stage_approval_request_status"] == "owner_stage_approval_request_ready"
    assert receipt.summary["owner_approval_payload_audit_status"] == "owner_approval_payload_blocked"
    assert receipt.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_ready"
    assert receipt.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert (
        receipt.summary["owner_post_approval_operator_checklist_status"]
        == "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert receipt.summary["owner_stage_approval_brief_status"] == "owner_stage_approval_brief_ready"
    assert receipt.summary["owner_approval_handoff_status"] == "owner_approval_handoff_ready"
    assert receipt.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert receipt.summary["owner_stage_execution_plan_status"] == "owner_stage_execution_blocked"
    assert receipt.summary["closure_snapshot_status"] == "commercial_delivery_closure_blocked"
    assert receipt.summary["closure_refresh_chain_step_count"] == 24
    assert receipt.summary["closure_refresh_chain_step_count_lag_expected"] is True
    assert receipt.summary["commercial_delivery_report_count_alias_normalization_status"] == "passed"
    assert receipt.summary["commercial_delivery_report_hygiene_status"] == "passed"
    assert {check.status for check in receipt.checks} == {"passed"}
    step_names = [step.name for step in receipt.steps]
    assert step_names.index("original_kernel_manifest") < step_names.index("control_modes_preservation")
    assert step_names.index("control_modes_preservation") < step_names.index("staging_review")
    assert step_names.index("owner_stage_approval_request") < step_names.index("owner_stage_approval_gate")
    assert step_names.index("owner_staging_rollback_plan") < step_names.index("owner_delivery_packet_before_owner_approval")
    assert step_names.index("owner_delivery_packet_before_owner_approval") < step_names.index("owner_stage_approval_request")
    assert step_names.index("owner_stage_approval_request") < step_names.index("owner_approval_payload_audit")
    assert step_names.index("owner_approval_payload_audit") < step_names.index("owner_stage_approval_gate")
    assert step_names.index("owner_stage_approval_gate") < step_names.index("owner_stage_approval_brief")
    assert step_names.index("owner_stage_approval_brief") < step_names.index("owner_stage_execution_plan")
    assert step_names.index("owner_stage_execution_plan") < step_names.index("owner_delivery_packet")
    assert step_names.index("owner_delivery_packet") < step_names.index("closure_snapshot")
    assert step_names.index("closure_snapshot") < step_names.index("owner_approval_handoff")
    assert step_names.index("owner_approval_handoff") < step_names.index("pre_approval_drift_guard")
    assert step_names.index("pre_approval_drift_guard") < step_names.index("owner_approval_resume_packet")
    assert step_names.index("owner_approval_resume_packet") < step_names.index(
        "owner_post_approval_operator_checklist"
    )
    assert step_names.index("owner_post_approval_operator_checklist") < step_names.index(
        "task_board_after_owner_decision"
    )
    assert step_names.index("task_board_after_owner_decision") < step_names.index(
        "commercial_delivery_report_count_alias_normalization"
    )
    assert step_names.index("commercial_delivery_report_count_alias_normalization") < step_names.index(
        "commercial_delivery_report_hygiene"
    )
    post = next(step for step in receipt.steps if step.name == "owner_post_staging_verifier")
    assert post.status == "expected_nonzero_accepted"
    assert post.expected_nonzero_accepted is True
    commit_gate = next(step for step in receipt.steps if step.name == "owner_post_stage_commit_gate")
    assert commit_gate.status == "expected_nonzero_accepted"
    assert commit_gate.expected_nonzero_accepted is True
    commit_packet = next(step for step in receipt.steps if step.name == "owner_commit_packet")
    assert commit_packet.status == "expected_nonzero_accepted"
    assert commit_packet.expected_nonzero_accepted is True
    approval_payload_audit = next(step for step in receipt.steps if step.name == "owner_approval_payload_audit")
    assert approval_payload_audit.status == "expected_nonzero_accepted"
    assert approval_payload_audit.expected_nonzero_accepted is True
    approval_gate = next(step for step in receipt.steps if step.name == "owner_stage_approval_gate")
    assert approval_gate.status == "expected_nonzero_accepted"
    assert approval_gate.expected_nonzero_accepted is True
    execution_plan = next(step for step in receipt.steps if step.name == "owner_stage_execution_plan")
    assert execution_plan.status == "expected_nonzero_accepted"
    assert execution_plan.expected_nonzero_accepted is True
    closure_snapshot = next(step for step in receipt.steps if step.name == "closure_snapshot")
    assert closure_snapshot.status == "expected_nonzero_accepted"
    assert closure_snapshot.expected_nonzero_accepted is True


def test_refresh_chain_receipt_ready_when_post_staging_is_ready(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")

    receipt = build_refresh_chain_receipt(reports_dir=reports_dir, command_runner=_runner())

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_step_count"] == 0
    assert next(step for step in receipt.steps if step.name == "owner_post_staging_verifier").status == "passed"
    assert next(step for step in receipt.steps if step.name == "owner_post_stage_commit_gate").status == "passed"
    assert next(step for step in receipt.steps if step.name == "owner_commit_packet").status == "passed"
    assert next(step for step in receipt.steps if step.name == "closure_snapshot").status == "passed"


def test_refresh_chain_receipt_accounts_for_stale_resume_packet_during_post_staging_pre_stage_gate(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "full_codex_parity_claimed": False,
            "summary": {
                "owner_post_staging_status": "owner_post_staging_verification_ready",
                "owner_post_staging_cached_staged_path_count": 2,
                "owner_preflight_cached_staged_path_count": 2,
            },
            "checks": [
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "owner_post_staging_expected_pre_stage_state", "status": "failed"},
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "owner_approval_resume_packet_accounted_for", "status": "failed"},
                {"name": "operator_checklist_accounted_for", "status": "failed"},
                {"name": "owner_approval_boundary_waiting_or_ready", "status": "failed"},
                {"name": "git_index_empty_before_owner_stage", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_pre_stage_readiness_gate": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_pre_stage_readiness_gate"]
    pre_stage_gate = next(step for step in receipt.steps if step.name == "owner_pre_stage_readiness_gate")
    assert pre_stage_gate.status == "expected_nonzero_accepted"
    assert pre_stage_gate.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_owner_approval_resume_packet(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        {
            "status": "owner_approval_resume_packet_blocked",
            "real_owner_approval_present": True,
            "waiting_for_owner": False,
            "resume_ready": False,
            "stage_allowed": False,
            "stage_execution_ready": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "pre_approval_drift_guard": "pre_approval_drift_guard_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_blocked",
                "owner_staging_runbook": "owner_staging_runbook_blocked",
                "owner_staging_rollback_plan": "owner_staging_rollback_plan_ready",
                "owner_post_staging_verifier": "owner_post_staging_verification_blocked",
                "owner_post_stage_commit_gate": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet": "owner_commit_packet_blocked",
                "owner_delivery_packet": "owner_delivery_packet_blocked",
                "task_board": "commercial_delivery_ready_for_owner_staging_review",
            },
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 14,
                "runbook_stage_command_count": 14,
                "execution_plan_stage_command_count": 14,
                "stage_commands_preview_count": 14,
                "owner_approval_payload_audit_status": "owner_approval_payload_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "post_stage_resume_evidence_ready": False,
                "owner_approval_handoff_post_stage_accounted_for": False,
                "owner_staging_runbook_post_stage_accounted_for": False,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_staging_runbook_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_counts_consistent", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_resume_packet": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_resume_packet"]
    resume_packet = next(step for step in receipt.steps if step.name == "owner_approval_resume_packet")
    assert resume_packet.status == "expected_nonzero_accepted"
    assert resume_packet.expected_nonzero_accepted is True
    assert (
        next(check for check in receipt.checks if check.name == "owner_approval_resume_packet_accounted_for").status
        == "passed"
    )


def test_refresh_chain_receipt_accounts_for_owner_approved_resume_packet_bootstrap(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-resume-packet.json",
        {
            "status": "owner_approval_resume_packet_blocked",
            "real_owner_approval_present": True,
            "waiting_for_owner": False,
            "resume_ready": False,
            "stage_allowed": True,
            "stage_execution_ready": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "pre_approval_drift_guard": "pre_approval_drift_guard_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_staging_runbook": "owner_staging_runbook_blocked",
                "owner_staging_rollback_plan": "owner_staging_rollback_plan_ready",
                "owner_post_staging_verifier": "owner_post_staging_verification_blocked",
                "owner_post_stage_commit_gate": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet": "owner_commit_packet_blocked",
                "owner_delivery_packet": "owner_delivery_packet_blocked",
                "task_board": "commercial_delivery_ready_for_owner_staging_review",
            },
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 2,
                "runbook_stage_command_count": 2,
                "execution_plan_stage_command_count": 2,
                "stage_commands_preview_count": 2,
                "owner_approval_payload_audit_status": "owner_approval_payload_ready",
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "post_stage_resume_evidence_ready": False,
                "owner_approval_handoff_post_stage_accounted_for": False,
                "owner_staging_runbook_post_stage_accounted_for": False,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_staging_runbook_ready", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_resume_packet": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_resume_packet"]
    resume_packet = next(step for step in receipt.steps if step.name == "owner_approval_resume_packet")
    assert resume_packet.status == "expected_nonzero_accepted"
    assert resume_packet.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_approval_resume_packet_accounted_for").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_approval_handoff_nonzero(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_blocked",
            "stage_allowed": True,
            "delivery_complete": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "owner_approval_payload_audit_status": "owner_approval_payload_ready",
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "closure_snapshot_status": "commercial_delivery_complete",
            },
            "checks": [
                {"name": "approval_payload_audit_pre_approval_blocked", "status": "failed"},
                {"name": "real_owner_approval_not_written_by_handoff", "status": "failed"},
                {"name": "stage_not_allowed_before_owner_approval", "status": "failed"},
                {"name": "operator_checklist_accounted_for", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_handoff": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_handoff"]
    assert receipt.summary["expected_nonzero_step_count"] == 1
    assert receipt.summary["owner_approval_handoff_status"] == "owner_approval_handoff_blocked"
    handoff = next(step for step in receipt.steps if step.name == "owner_approval_handoff")
    assert handoff.status == "expected_nonzero_accepted"
    assert handoff.expected_nonzero_accepted is True
    handoff_check = next(check for check in receipt.checks if check.name == "owner_approval_handoff_ready")
    assert handoff_check.status == "passed"
    assert handoff_check.details["expected_nonzero_steps"] == ["owner_approval_handoff"]


def test_refresh_chain_receipt_accounts_for_post_commit_owner_approval_handoff(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_blocked",
            "stage_allowed": False,
            "delivery_complete": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 12,
                "rollback_reset_command_count": 12,
                "owner_approval_payload_audit_status": "owner_approval_payload_blocked",
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_ready"
                ),
                "owner_post_approval_operator_checklist_operator_ready": True,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_brief_ready", "status": "failed"},
                {"name": "approval_payload_audit_pre_approval_blocked", "status": "failed"},
                {"name": "real_owner_approval_not_written_by_handoff", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_handoff": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_handoff"]
    handoff = next(step for step in receipt.steps if step.name == "owner_approval_handoff")
    assert handoff.status == "expected_nonzero_accepted"
    assert handoff.expected_nonzero_accepted is True
    handoff_check = next(check for check in receipt.checks if check.name == "owner_approval_handoff_ready")
    assert handoff_check.status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_owner_approval_handoff_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_blocked",
            "stage_allowed": False,
            "delivery_complete": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 14,
                "rollback_reset_command_count": 14,
                "owner_approval_payload_audit_status": "owner_approval_payload_blocked",
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_brief_ready", "status": "failed"},
                {"name": "approval_payload_audit_pre_approval_blocked", "status": "failed"},
                {"name": "real_owner_approval_not_written_by_handoff", "status": "failed"},
                {"name": "operator_checklist_accounted_for", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_handoff": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_handoff"]
    handoff = next(step for step in receipt.steps if step.name == "owner_approval_handoff")
    assert handoff.status == "expected_nonzero_accepted"
    assert handoff.expected_nonzero_accepted is True


def test_refresh_chain_receipt_blocks_post_approval_handoff_without_ready_evidence(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_blocked",
            "stage_allowed": True,
            "delivery_complete": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "owner_approval_payload_audit_status": "owner_approval_payload_blocked",
                "owner_approval_payload_present": False,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "closure_snapshot_status": "commercial_delivery_complete",
            },
            "checks": [
                {"name": "approval_payload_audit_pre_approval_blocked", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_handoff": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_blocked"
    assert receipt.summary["failed_step_count"] == 1
    failed = next(step for step in receipt.steps if step.name == "owner_approval_handoff")
    assert failed.status == "failed"
    assert failed.expected_nonzero_accepted is False
    assert next(check for check in receipt.checks if check.name == "no_unexpected_refresh_failures").status == "failed"


def test_refresh_chain_receipt_accounts_for_post_approval_pre_approval_drift_guard_nonzero(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
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
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "closure_snapshot_status": "commercial_delivery_complete",
                "closure_delivery_complete": True,
            },
            "checks": [
                {"name": "reports_readable", "status": "passed"},
                {"name": "real_owner_approval_absent", "status": "failed"},
                {"name": "approval_request_ready", "status": "passed"},
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_pre_approval_drift_guard": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["pre_approval_drift_guard"]
    assert receipt.summary["expected_nonzero_step_count"] == 1
    assert receipt.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_blocked"
    drift_guard = next(step for step in receipt.steps if step.name == "pre_approval_drift_guard")
    assert drift_guard.status == "expected_nonzero_accepted"
    assert drift_guard.expected_nonzero_accepted is True
    drift_guard_check = next(check for check in receipt.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_guard_check.status == "passed"
    assert drift_guard_check.details["expected_nonzero_steps"] == ["pre_approval_drift_guard"]


def test_refresh_chain_receipt_accounts_for_post_commit_pre_approval_drift_guard(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
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

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_pre_approval_drift_guard": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["pre_approval_drift_guard"]
    drift_guard = next(step for step in receipt.steps if step.name == "pre_approval_drift_guard")
    assert drift_guard.status == "expected_nonzero_accepted"
    assert drift_guard.expected_nonzero_accepted is True
    drift_guard_check = next(check for check in receipt.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_guard_check.status == "passed"


def test_refresh_chain_receipt_accounts_for_owner_approved_drift_guard_bootstrap(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
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
            "report_statuses": {
                "owner_stage_approval_request": "owner_stage_approval_request_ready",
                "owner_approval_handoff": "owner_approval_handoff_blocked",
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
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
                {"name": "approval_handoff_ready", "status": "failed"},
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_pre_approval_drift_guard": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["pre_approval_drift_guard"]
    drift_guard = next(step for step in receipt.steps if step.name == "pre_approval_drift_guard")
    assert drift_guard.status == "expected_nonzero_accepted"
    assert drift_guard.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "pre_approval_drift_guard_ready").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_pre_approval_drift_guard_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
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

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_pre_approval_drift_guard": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["pre_approval_drift_guard"]
    drift_guard = next(step for step in receipt.steps if step.name == "pre_approval_drift_guard")
    assert drift_guard.status == "expected_nonzero_accepted"
    assert drift_guard.expected_nonzero_accepted is True


def test_refresh_chain_receipt_blocks_post_approval_pre_approval_drift_guard_without_ready_evidence(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
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

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_pre_approval_drift_guard": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_blocked"
    assert receipt.summary["failed_step_count"] == 1
    failed = next(step for step in receipt.steps if step.name == "pre_approval_drift_guard")
    assert failed.status == "failed"
    assert failed.expected_nonzero_accepted is False
    assert next(check for check in receipt.checks if check.name == "no_unexpected_refresh_failures").status == "failed"


def test_refresh_chain_receipt_accepts_post_staging_preflight_nonzero(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-preflight.json",
        {
            "status": "owner_staging_preflight_blocked",
            "cached_staged_path_count": 2,
            "checks": [
                {"name": "no_cached_staged_paths_before_owner_staging", "status": "failed"},
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "blocked_before_owner_staging_decision",
            "summary": {
                "post_staging_status": "owner_post_staging_verification_ready",
                "cached_staged_path_count": 2,
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_blocked",
            },
            "checks": [
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "post_staging_not_yet_applied", "status": "failed"},
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "summary": {
                "owner_post_staging_status": "owner_post_staging_verification_ready",
                "owner_post_staging_cached_staged_path_count": 2,
                "owner_preflight_cached_staged_path_count": 2,
            },
            "checks": [
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "owner_post_staging_expected_pre_stage_state", "status": "failed"},
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "git_index_empty_before_owner_stage", "status": "failed"},
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-runbook.json",
        {
            "status": "owner_staging_runbook_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "summary": {
                "pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "stage_command_count": 2,
            },
            "checks": [
                {"name": "pre_stage_gate_ready", "status": "failed"},
            ],
            "full_codex_parity_claimed": False,
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner(
            {
                "commercial_delivery_owner_staging_preflight": 1,
                "commercial_delivery_owner_decision_brief": 1,
                "commercial_delivery_owner_pre_stage_readiness_gate": 1,
                "commercial_delivery_owner_staging_runbook": 1,
            }
        ),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == [
        "owner_staging_preflight",
        "owner_decision_brief",
        "owner_pre_stage_readiness_gate",
        "owner_staging_runbook",
    ]
    assert receipt.summary["expected_nonzero_step_count"] == 4
    preflight = next(step for step in receipt.steps if step.name == "owner_staging_preflight")
    assert preflight.status == "expected_nonzero_accepted"
    assert preflight.expected_nonzero_accepted is True
    decision_brief = next(step for step in receipt.steps if step.name == "owner_decision_brief")
    assert decision_brief.status == "expected_nonzero_accepted"
    assert decision_brief.expected_nonzero_accepted is True
    pre_stage_gate = next(step for step in receipt.steps if step.name == "owner_pre_stage_readiness_gate")
    assert pre_stage_gate.status == "expected_nonzero_accepted"
    assert pre_stage_gate.expected_nonzero_accepted is True
    runbook = next(step for step in receipt.steps if step.name == "owner_staging_runbook")
    assert runbook.status == "expected_nonzero_accepted"
    assert runbook.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_staging_preflight_accounted_for").status == "passed"
    assert next(check for check in receipt.checks if check.name == "owner_decision_brief_ready").status == "passed"
    assert (
        next(check for check in receipt.checks if check.name == "owner_pre_stage_readiness_gate_accounted_for").status
        == "passed"
    )
    assert next(check for check in receipt.checks if check.name == "owner_staging_runbook_accounted_for").status == "passed"
    assert next(step for step in receipt.steps if step.name == "owner_post_staging_verifier").status == "passed"
    assert next(step for step in receipt.steps if step.name == "owner_post_stage_commit_gate").status == "passed"
    assert next(step for step in receipt.steps if step.name == "owner_commit_packet").status == "passed"
    assert next(step for step in receipt.steps if step.name == "closure_snapshot").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_owner_decision_brief(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 12,
                "owner_command_audit_command_count": 12,
                "owner_command_audit_expected_path_count": 12,
                "cached_staged_path_count": 0,
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
            },
            "checks": [
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_commands_match_manifest", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_decision_brief": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_decision_brief"]
    decision_brief = next(step for step in receipt.steps if step.name == "owner_decision_brief")
    assert decision_brief.status == "expected_nonzero_accepted"
    assert decision_brief.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_decision_brief_ready").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_owner_decision_brief_with_blocked_resume_packet(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 14,
                "owner_command_audit_command_count": 14,
                "owner_command_audit_expected_path_count": 14,
                "cached_staged_path_count": 0,
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": False,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
            },
            "checks": [
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_commands_match_manifest", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_decision_brief": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_decision_brief"]
    decision_brief = next(step for step in receipt.steps if step.name == "owner_decision_brief")
    assert decision_brief.status == "expected_nonzero_accepted"
    assert decision_brief.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_owner_decision_brief_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 14,
                "owner_command_audit_command_count": 14,
                "owner_command_audit_expected_path_count": 14,
                "cached_staged_path_count": 0,
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": False,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_blocked",
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_approval_handoff_status": "owner_approval_handoff_blocked",
                "owner_approval_handoff_owner_action_required": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
            },
            "checks": [
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_commands_match_manifest", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_decision_brief": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_decision_brief"]
    decision_brief = next(step for step in receipt.steps if step.name == "owner_decision_brief")
    assert decision_brief.status == "expected_nonzero_accepted"
    assert decision_brief.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_pre_stage_readiness_gate(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "stage_command_count": 12,
                "owner_post_staging_status": "owner_post_staging_verification_blocked",
                "owner_post_staging_cached_staged_path_count": 0,
                "owner_preflight_cached_staged_path_count": 0,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
            },
            "checks": [
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "stage_counts_agree", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_pre_stage_readiness_gate": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_pre_stage_readiness_gate"]
    pre_stage_gate = next(step for step in receipt.steps if step.name == "owner_pre_stage_readiness_gate")
    assert pre_stage_gate.status == "expected_nonzero_accepted"
    assert pre_stage_gate.expected_nonzero_accepted is True
    assert (
        next(check for check in receipt.checks if check.name == "owner_pre_stage_readiness_gate_accounted_for").status
        == "passed"
    )


def test_refresh_chain_receipt_accounts_for_post_commit_pre_stage_readiness_gate_with_blocked_resume_packet(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "stage_command_count": 14,
                "owner_post_staging_status": "owner_post_staging_verification_blocked",
                "owner_post_staging_cached_staged_path_count": 0,
                "owner_preflight_cached_staged_path_count": 0,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": False,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
            },
            "checks": [
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "owner_approval_resume_packet_accounted_for", "status": "failed"},
                {"name": "owner_approval_boundary_waiting_or_ready", "status": "failed"},
                {"name": "stage_counts_agree", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_pre_stage_readiness_gate": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_pre_stage_readiness_gate"]
    pre_stage_gate = next(step for step in receipt.steps if step.name == "owner_pre_stage_readiness_gate")
    assert pre_stage_gate.status == "expected_nonzero_accepted"
    assert pre_stage_gate.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_pre_stage_readiness_gate_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "stage_command_count": 14,
                "owner_post_staging_status": "owner_post_staging_verification_blocked",
                "owner_post_staging_cached_staged_path_count": 0,
                "owner_preflight_cached_staged_path_count": 0,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": False,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_blocked",
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
            },
            "checks": [
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "owner_approval_resume_packet_accounted_for", "status": "failed"},
                {"name": "operator_checklist_accounted_for", "status": "failed"},
                {"name": "owner_approval_boundary_waiting_or_ready", "status": "failed"},
                {"name": "stage_counts_agree", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_pre_stage_readiness_gate": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_pre_stage_readiness_gate"]
    pre_stage_gate = next(step for step in receipt.steps if step.name == "owner_pre_stage_readiness_gate")
    assert pre_stage_gate.status == "expected_nonzero_accepted"
    assert pre_stage_gate.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_staging_runbook(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-runbook.json",
        {
            "status": "owner_staging_runbook_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
                "stage_command_count": 5,
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
            },
            "checks": [
                {"name": "pre_stage_gate_ready", "status": "failed"},
                {"name": "stage_command_count_matches_gate", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_staging_runbook": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_staging_runbook"]
    runbook = next(step for step in receipt.steps if step.name == "owner_staging_runbook")
    assert runbook.status == "expected_nonzero_accepted"
    assert runbook.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_staging_runbook_accounted_for").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_delivery_packet(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-delivery-packet.json",
        {
            "status": "owner_delivery_packet_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "eligible_stage_count": 11,
                "owner_stage_command_count": 11,
                "refresh_chain_step_count": 11,
                "expected_nonzero_steps": [
                    "owner_post_staging_verifier",
                    "owner_decision_brief",
                    "owner_pre_stage_readiness_gate",
                    "owner_stage_approval_gate",
                    "owner_stage_execution_plan",
                ],
                "owner_staging_runbook_status": "owner_staging_runbook_blocked",
                "owner_pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_approval_request_status": "owner_stage_approval_request_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_staging_rollback_plan_status": "owner_staging_rollback_plan_ready",
                "commit_allowed": False,
                "stage_allowed": False,
                "owner_stage_execution_allowed": False,
                "owner_stage_execution_stage_command_count": 5,
                "rollback_available": True,
                "rollback_required": False,
                "strict_stage_ready": False,
                "post_stage_chain_accounted_for": False,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_pre_stage_chain_ready", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_delivery_packet": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == [
        "owner_delivery_packet_before_owner_approval",
        "owner_delivery_packet",
    ]
    before_owner_packet = next(
        step for step in receipt.steps if step.name == "owner_delivery_packet_before_owner_approval"
    )
    final_packet = next(step for step in receipt.steps if step.name == "owner_delivery_packet")
    assert before_owner_packet.status == "expected_nonzero_accepted"
    assert before_owner_packet.expected_nonzero_accepted is True
    assert final_packet.status == "expected_nonzero_accepted"
    assert final_packet.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_delivery_packet_ready").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_delivery_packet_self_bootstrap(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-delivery-packet.json",
        {
            "status": "owner_delivery_packet_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "eligible_stage_count": 14,
                "owner_stage_command_count": 14,
                "refresh_chain_step_count": 7,
                "expected_nonzero_steps": ["owner_post_staging_verifier"],
                "owner_staging_runbook_status": "owner_staging_runbook_blocked",
                "owner_pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_approval_request_status": "owner_stage_approval_request_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_staging_rollback_plan_status": "owner_staging_rollback_plan_ready",
                "commit_allowed": False,
                "stage_allowed": False,
                "owner_stage_execution_allowed": False,
                "owner_stage_execution_stage_command_count": 14,
                "rollback_available": True,
                "rollback_required": False,
                "strict_stage_ready": False,
                "post_stage_chain_accounted_for": False,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_pre_stage_chain_ready", "status": "failed"},
                {"name": "refresh_chain_ready", "status": "failed"},
                {"name": "pre_stage_post_stage_blockers_are_expected", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_delivery_packet": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == [
        "owner_delivery_packet_before_owner_approval",
        "owner_delivery_packet",
    ]
    final_packet = next(step for step in receipt.steps if step.name == "owner_delivery_packet")
    assert final_packet.status == "expected_nonzero_accepted"
    assert final_packet.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_delivery_packet_refresh_bootstrap(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-delivery-packet.json",
        {
            "status": "owner_delivery_packet_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "eligible_stage_count": 14,
                "owner_stage_command_count": 14,
                "owner_stage_execution_stage_command_count": 14,
                "rollback_reset_command_count": 14,
                "refresh_chain_step_count": 10,
                "expected_nonzero_steps": [
                    "owner_post_staging_verifier",
                    "owner_decision_brief",
                ],
                "owner_staging_runbook_status": "owner_staging_runbook_blocked",
                "owner_pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_approval_request_status": "owner_stage_approval_request_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_staging_rollback_plan_status": "owner_staging_rollback_plan_ready",
                "commit_allowed": False,
                "stage_allowed": False,
                "owner_stage_execution_allowed": False,
                "rollback_available": True,
                "rollback_required": False,
                "strict_stage_ready": False,
                "post_stage_chain_accounted_for": False,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {
                    "name": "owner_pre_stage_chain_ready",
                    "status": "failed",
                    "details": {
                        "refresh_delivery_bootstrap": True,
                    },
                },
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_delivery_packet": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    final_packet = next(step for step in receipt.steps if step.name == "owner_delivery_packet")
    assert final_packet.status == "expected_nonzero_accepted"
    assert final_packet.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_stage_approval_request(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-request.json",
        {
            "status": "owner_stage_approval_request_blocked",
            "owner_gated": True,
            "approval_required": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "report_statuses": {
                "owner_delivery_packet": "owner_delivery_packet_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
            },
            "summary": {
                "stage_include_count": 5,
                "owner_stage_command_count": 2,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "stage_allowed": False,
                "approval_payload_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.json",
                "template_output_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.template.json",
                "template_identity_placeholders_present": True,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_delivery_packet_requires_approval", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_stage_approval_request": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_stage_approval_request"]
    approval_request = next(step for step in receipt.steps if step.name == "owner_stage_approval_request")
    assert approval_request.status == "expected_nonzero_accepted"
    assert approval_request.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_stage_approval_request_ready").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_history_payload_blockers(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-task-board.json",
        {
            "status": "commercial_delivery_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 1,
                "secondary_pending_count": 2,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 131,
                "secondary_pending_blocks_owner_staging": False,
                "refresh_chain_receipt_status": "commercial_delivery_refresh_chain_receipt_blocked",
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_modes_surface_file_count": 12,
                "pre_approval_drift_guard_status": "pre_approval_drift_guard_blocked",
                "pre_approval_drift_guard_accounted_for": False,
                "pre_approval_drift_guard_real_owner_approval_present": True,
            },
            "checks": [
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 1,
                "owner_command_audit_command_count": 1,
                "owner_command_audit_expected_path_count": 1,
                "cached_staged_path_count": 0,
                "post_staging_status": "owner_post_staging_verification_blocked",
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_approval_handoff_status": "owner_approval_handoff_blocked",
                "owner_approval_handoff_owner_action_required": True,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_blocked",
            },
            "checks": [
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "task_board_ready", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "stage_command_count": 1,
                "refresh_chain_receipt_status": "commercial_delivery_refresh_chain_receipt_blocked",
                "owner_command_audit_status": "owner_command_audit_ready",
                "owner_decision_brief_status": "blocked_before_owner_staging_decision",
                "owner_approval_handoff_status": "owner_approval_handoff_blocked",
                "owner_approval_handoff_owner_action_required": True,
                "owner_approval_handoff_stage_allowed": False,
                "pre_approval_drift_guard_status": "pre_approval_drift_guard_blocked",
                "pre_approval_drift_guard_real_owner_approval_present": True,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_blocked",
                "owner_preflight_cached_staged_path_count": 0,
                "owner_post_staging_status": "owner_post_staging_verification_blocked",
                "owner_post_staging_cached_staged_path_count": 0,
            },
            "checks": [
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "task_board_ready", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-delivery-packet.json",
        {
            "status": "owner_delivery_packet_blocked",
            "stage_ready": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "eligible_stage_count": 1,
                "owner_stage_command_count": 1,
                "owner_stage_execution_stage_command_count": 1,
                "rollback_reset_command_count": 1,
                "expected_nonzero_steps": [
                    "owner_decision_brief",
                    "owner_staging_runbook",
                    "owner_stage_approval_gate",
                    "owner_stage_execution_plan",
                ],
                "owner_staging_runbook_status": "owner_staging_runbook_blocked",
                "owner_pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_approval_request_status": "owner_stage_approval_request_blocked",
                "owner_approval_payload_audit_status": "owner_approval_payload_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_staging_rollback_plan_status": "owner_staging_rollback_plan_ready",
                "commit_allowed": False,
                "stage_allowed": False,
                "owner_stage_execution_allowed": False,
                "rollback_available": True,
                "rollback_required": False,
                "strict_stage_ready": False,
                "post_stage_chain_accounted_for": False,
                "refresh_delivery_bootstrap": True,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "a" * 64,
            },
            "checks": [
                {"name": "owner_pre_stage_chain_ready", "status": "failed"},
                {"name": "owner_approval_payload_audit_accounted_for", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": True,
            "ready_for_approval_gate": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 1,
                "approval_stage_include_count": 100,
                "approval_owner_stage_command_count": 2,
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "approval_commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "a" * 64,
                "approval_stage_path_digest": "c" * 64,
                "approval_stage_command_digest": "d" * 64,
                "approval_expected_stage_path_set_digest": "c" * 64,
                "post_commit_noop_accounted_for": False,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_stage_approval_request_ready", "status": "failed"},
                {"name": "approval_counts_match_request_and_delivery_packet", "status": "failed"},
                {"name": "approval_digests_match_request_and_delivery_packet", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_post_commit_history_runner(
            reports_dir,
            {
                "commercial_delivery_task_board": 1,
                "commercial_delivery_owner_decision_brief": 1,
                "commercial_delivery_owner_pre_stage_readiness_gate": 1,
                "commercial_delivery_owner_delivery_packet": 1,
                "commercial_delivery_owner_approval_payload_audit": 1,
            },
        ),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == [
        "task_board_before_owner_decision",
        "owner_decision_brief",
        "owner_pre_stage_readiness_gate",
        "owner_delivery_packet_before_owner_approval",
        "owner_approval_payload_audit",
        "task_board_after_owner_decision",
    ]
    assert {check.status for check in receipt.checks} == {"passed"}
    for name in receipt.summary["expected_nonzero_steps"]:
        step = next(step for step in receipt.steps if step.name == name)
        assert step.status == "expected_nonzero_accepted"
        assert step.expected_nonzero_accepted is True
    final_packet = next(step for step in receipt.steps if step.name == "owner_delivery_packet")
    assert final_packet.status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_approval_payload_audit(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": True,
            "ready_for_approval_gate": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 2,
                "approval_stage_include_count": 100,
                "approval_owner_stage_command_count": 2,
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "approval_commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "approval_stage_path_digest": "a" * 64,
                "approval_stage_command_digest": "b" * 64,
                "approval_expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_stage_approval_request_ready", "status": "failed"},
                {"name": "approval_counts_match_request_and_delivery_packet", "status": "failed"},
                {"name": "approval_digests_match_request_and_delivery_packet", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_payload_audit": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_payload_audit"]
    audit = next(step for step in receipt.steps if step.name == "owner_approval_payload_audit")
    assert audit.status == "expected_nonzero_accepted"
    assert audit.expected_nonzero_accepted is True
    assert (
        next(check for check in receipt.checks if check.name == "owner_approval_payload_audit_accounted_for").status
        == "passed"
    )


def test_refresh_chain_receipt_accounts_for_pre_approval_audit_bootstrap(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-payload-audit.json",
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": True,
            "ready_for_approval_gate": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 8,
                "approval_stage_include_count": 100,
                "approval_owner_stage_command_count": 8,
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "approval_commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "approval_stage_path_digest": "a" * 64,
                "approval_stage_command_digest": "b" * 64,
                "approval_expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_stage_approval_request_ready", "status": "failed"},
                {"name": "approval_counts_match_request_and_delivery_packet", "status": "passed"},
                {"name": "approval_digests_match_request_and_delivery_packet", "status": "passed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_payload_audit": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    audit = next(step for step in receipt.steps if step.name == "owner_approval_payload_audit")
    assert audit.status == "expected_nonzero_accepted"
    assert audit.expected_nonzero_accepted is True
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_payload_audit"]


def test_refresh_chain_receipt_accounts_for_post_commit_stage_approval_brief(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        {
            "status": "owner_stage_approval_brief_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 5,
                "owner_stage_command_count": 2,
                "owner_stage_approval_request_status": "owner_stage_approval_request_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "stage_allowed": False,
                "approval_required": True,
                "approval_payload_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.json",
                "template_output_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.template.json",
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "stage_path_digest": "a" * 64,
                "request_stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "request_stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "request_expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "owner_delivery_packet_ready", "status": "failed"},
                {"name": "owner_stage_approval_request_ready", "status": "failed"},
                {"name": "approval_request_counts_match_delivery_packet", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_stage_approval_brief": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_stage_approval_brief"]
    brief = next(step for step in receipt.steps if step.name == "owner_stage_approval_brief")
    assert brief.status == "expected_nonzero_accepted"
    assert brief.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "owner_stage_approval_brief_ready").status == "passed"


def test_refresh_chain_receipt_accounts_for_noop_owner_staging_refresh_bootstrap(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-decision-brief.json",
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "cached_staged_path_count": 0,
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_blocked",
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
                "stage_include_count": 100,
                "owner_stage_command_count": 0,
                "owner_command_audit_command_count": 0,
                "owner_command_audit_expected_path_count": 0,
            },
            "checks": [
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_commands_match_manifest", "status": "failed"},
                {"name": "post_staging_not_yet_applied", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "stage_command_count": 0,
                "owner_post_staging_status": "owner_post_staging_verification_ready",
                "owner_post_staging_cached_staged_path_count": 0,
                "owner_preflight_cached_staged_path_count": 0,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
                "owner_approval_handoff_status": "owner_approval_handoff_blocked",
                "owner_approval_handoff_owner_action_required": True,
                "owner_approval_handoff_stage_allowed": True,
                "pre_approval_drift_guard_status": "pre_approval_drift_guard_blocked",
                "pre_approval_drift_guard_real_owner_approval_present": True,
            },
            "checks": [
                {"name": "owner_post_staging_expected_pre_stage_state", "status": "failed"},
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "stage_counts_agree", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-staging-runbook.json",
        {
            "status": "owner_staging_runbook_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_command_count": 0,
                "pre_stage_gate_status": "owner_pre_stage_readiness_blocked",
                "task_board_status": "commercial_delivery_ready_for_owner_staging_review",
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
            },
            "checks": [
                {"name": "pre_stage_gate_ready", "status": "failed"},
                {"name": "stage_command_count_matches_gate", "status": "failed"},
                {"name": "stage_commands_are_explicit_path_adds", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-stage-approval-brief.json",
        {
            "status": "owner_stage_approval_brief_blocked",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 0,
                "owner_stage_approval_request_status": "owner_stage_approval_request_ready",
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "stage_allowed": True,
                "approval_required": True,
                "approval_payload_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.json",
                "template_output_path": (
                    ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.template.json"
                ),
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "stage_path_digest": "a" * 64,
                "request_stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "request_stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "request_expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "refresh_chain_ready", "status": "failed"},
            ],
        },
    )
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_blocked",
            "stage_allowed": True,
            "delivery_complete": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 0,
                "rollback_reset_command_count": 0,
                "post_approval_noop_accounted_for": True,
                "owner_approval_payload_audit_status": "owner_approval_payload_ready",
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "closure_snapshot_status": "commercial_delivery_complete",
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
            },
            "checks": [
                {"name": "approval_brief_ready", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner(
            {
                "commercial_delivery_owner_decision_brief": 1,
                "commercial_delivery_owner_pre_stage_readiness_gate": 1,
                "commercial_delivery_owner_staging_runbook": 1,
                "commercial_delivery_owner_stage_approval_brief": 1,
                "commercial_delivery_owner_approval_handoff": 1,
            }
        ),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == [
        "owner_decision_brief",
        "owner_pre_stage_readiness_gate",
        "owner_staging_runbook",
        "owner_stage_approval_brief",
        "owner_approval_handoff",
    ]
    assert {check.status for check in receipt.checks} == {"passed"}
    for name in receipt.summary["expected_nonzero_steps"]:
        step = next(step for step in receipt.steps if step.name == name)
        assert step.status == "expected_nonzero_accepted"
        assert step.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_closure_snapshot(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "stage_ready": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ],
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 11,
                "owner_stage_execution_stage_command_count": 11,
                "rollback_reset_command_count": 11,
                "pre_approval_drift_guard_accounted_for": True,
                "pre_approval_drift_guard_real_owner_approval_present": True,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_ready",
                "owner_approval_resume_packet_resume_ready": True,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "refresh_chain_ready_for_snapshot": True,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            },
            "checks": [
                {"name": "stage_ready", "status": "failed"},
                {"name": "owner_approval_ready", "status": "failed"},
                {"name": "stage_execution_ready", "status": "failed"},
                {"name": "post_stage_ready", "status": "failed"},
                {"name": "commit_ready", "status": "failed"},
                {"name": "cached_staged_path_set_digest_consistent", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_closure_snapshot": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["closure_snapshot"]
    closure = next(step for step in receipt.steps if step.name == "closure_snapshot")
    assert closure.status == "expected_nonzero_accepted"
    assert closure.expected_nonzero_accepted is True
    assert next(check for check in receipt.checks if check.name == "closure_snapshot_accounted_for").status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_closure_snapshot_with_blocked_resume_packet(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "stage_ready": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ],
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 14,
                "owner_stage_execution_stage_command_count": 14,
                "rollback_reset_command_count": 14,
                "pre_approval_drift_guard_accounted_for": True,
                "pre_approval_drift_guard_real_owner_approval_present": True,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": False,
                "owner_approval_resume_packet_real_owner_approval_present": True,
                "owner_approval_resume_packet_post_stage_accounted_for": False,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_ready",
                "owner_post_approval_operator_checklist_operator_ready": True,
                "refresh_chain_ready_for_snapshot": True,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            },
            "checks": [
                {"name": "stage_ready", "status": "failed"},
                {"name": "owner_approval_ready", "status": "failed"},
                {"name": "stage_execution_ready", "status": "failed"},
                {"name": "post_stage_ready", "status": "failed"},
                {"name": "commit_ready", "status": "failed"},
                {"name": "owner_approval_resume_packet_accounted_for", "status": "failed"},
                {"name": "cached_staged_path_set_digest_consistent", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_closure_snapshot": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["closure_snapshot"]
    closure = next(step for step in receipt.steps if step.name == "closure_snapshot")
    assert closure.status == "expected_nonzero_accepted"
    assert closure.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_closure_snapshot_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "stage_ready": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ],
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 14,
                "owner_stage_execution_stage_command_count": 14,
                "rollback_reset_command_count": 14,
                "pre_approval_drift_guard_accounted_for": True,
                "pre_approval_drift_guard_real_owner_approval_present": True,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_approval_resume_packet_waiting_for_owner": False,
                "owner_approval_resume_packet_resume_ready": False,
                "owner_approval_resume_packet_real_owner_approval_present": True,
                "owner_approval_resume_packet_post_stage_accounted_for": False,
                "owner_post_approval_operator_checklist_status": "owner_post_approval_operator_checklist_blocked",
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
                "owner_post_approval_operator_checklist_post_stage_accounted_for": False,
                "refresh_chain_ready_for_snapshot": True,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            },
            "checks": [
                {"name": "stage_ready", "status": "failed"},
                {"name": "owner_approval_ready", "status": "failed"},
                {"name": "stage_execution_ready", "status": "failed"},
                {"name": "post_stage_ready", "status": "failed"},
                {"name": "commit_ready", "status": "failed"},
                {"name": "owner_approval_resume_packet_accounted_for", "status": "failed"},
                {"name": "owner_post_approval_operator_checklist_accounted_for", "status": "failed"},
                {"name": "cached_staged_path_set_digest_consistent", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_closure_snapshot": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["closure_snapshot"]
    closure = next(step for step in receipt.steps if step.name == "closure_snapshot")
    assert closure.status == "expected_nonzero_accepted"
    assert closure.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_commit_handoff_after_delivery_ready(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-approval-handoff.json",
        {
            "status": "owner_approval_handoff_blocked",
            "stage_allowed": False,
            "delivery_complete": False,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 9,
                "rollback_reset_command_count": 9,
                "stage_path_digest": "a" * 64,
                "stage_command_digest": "b" * 64,
                "expected_stage_path_set_digest": "c" * 64,
                "owner_approval_payload_audit_status": "owner_approval_payload_blocked",
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "closure_snapshot_status": "commercial_delivery_closure_blocked",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "owner_post_approval_operator_checklist_waiting_for_owner": False,
                "owner_post_approval_operator_checklist_operator_ready": False,
                "owner_post_approval_operator_checklist_real_owner_approval_present": True,
            },
            "checks": [
                {"name": "approval_request_ready", "status": "failed"},
                {"name": "approval_brief_ready", "status": "failed"},
                {"name": "approval_payload_audit_pre_approval_blocked", "status": "failed"},
                {"name": "real_owner_approval_not_written_by_handoff", "status": "failed"},
                {"name": "operator_checklist_accounted_for", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_approval_handoff": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_approval_handoff"]
    handoff = next(step for step in receipt.steps if step.name == "owner_approval_handoff")
    assert handoff.status == "expected_nonzero_accepted"
    assert handoff.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_owner_approved_pre_stage_closure_snapshot(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "stage_ready": True,
            "approval_ready": False,
            "stage_execution_ready": False,
            "post_stage_ready": False,
            "commit_ready": False,
            "rollback_ready": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ],
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 9,
                "owner_stage_execution_stage_command_count": 9,
                "rollback_reset_command_count": 9,
                "pre_approval_drift_guard_accounted_for": True,
                "pre_approval_drift_guard_real_owner_approval_present": True,
                "refresh_chain_ready_for_snapshot": True,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            },
            "checks": [
                {"name": "owner_approval_ready", "status": "failed"},
                {"name": "stage_execution_ready", "status": "failed"},
                {"name": "post_stage_ready", "status": "failed"},
                {"name": "commit_ready", "status": "failed"},
                {"name": "cached_staged_path_set_digest_consistent", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_closure_snapshot": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["closure_snapshot"]
    closure = next(step for step in receipt.steps if step.name == "closure_snapshot")
    assert closure.status == "expected_nonzero_accepted"
    assert closure.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_owner_approved_pre_stage_closure_snapshot_with_post_approval_blockers(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-closure-snapshot.json",
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "stage_ready": True,
            "approval_ready": False,
            "stage_execution_ready": False,
            "post_stage_ready": False,
            "commit_ready": False,
            "rollback_ready": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "blockers": [
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
                "cached_staged_path_set_digest_not_ready",
            ],
            "summary": {
                "stage_include_count": 100,
                "owner_stage_command_count": 9,
                "owner_stage_execution_stage_command_count": 9,
                "rollback_reset_command_count": 9,
                "pre_approval_drift_guard_accounted_for": True,
                "pre_approval_drift_guard_real_owner_approval_present": True,
                "refresh_chain_ready_for_snapshot": True,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            },
            "checks": [
                {"name": "owner_approval_ready", "status": "failed"},
                {"name": "stage_execution_ready", "status": "failed"},
                {"name": "post_stage_ready", "status": "failed"},
                {"name": "commit_ready", "status": "failed"},
                {"name": "cached_staged_path_set_digest_consistent", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_closure_snapshot": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["closure_snapshot"]
    closure = next(step for step in receipt.steps if step.name == "closure_snapshot")
    assert closure.status == "expected_nonzero_accepted"
    assert closure.expected_nonzero_accepted is True


def test_refresh_chain_receipt_accounts_for_post_approval_pre_stage_gate_drift_guard_boundary(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-pre-stage-readiness-gate.json",
        {
            "status": "owner_pre_stage_readiness_blocked",
            "summary": {
                "owner_post_staging_status": "owner_post_staging_verification_ready",
                "owner_post_staging_cached_staged_path_count": 2,
                "owner_preflight_cached_staged_path_count": 2,
            },
            "checks": [
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "owner_post_staging_expected_pre_stage_state", "status": "failed"},
                {"name": "refresh_chain_receipt_ready", "status": "failed"},
                {"name": "owner_decision_brief_ready", "status": "failed"},
                {"name": "owner_approval_handoff_ready", "status": "failed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
                {"name": "git_index_empty_before_owner_stage", "status": "failed"},
            ],
            "full_codex_parity_claimed": False,
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_pre_stage_readiness_gate": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_pre_stage_readiness_gate"]
    pre_stage_gate = next(step for step in receipt.steps if step.name == "owner_pre_stage_readiness_gate")
    assert pre_stage_gate.status == "expected_nonzero_accepted"
    assert pre_stage_gate.expected_nonzero_accepted is True
    pre_stage_check = next(check for check in receipt.checks if check.name == "owner_pre_stage_readiness_gate_accounted_for")
    assert pre_stage_check.status == "passed"


def test_refresh_chain_receipt_accounts_for_post_commit_operator_checklist(
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir, post_staging_status="owner_post_staging_verification_ready")
    _write_json(
        reports_dir / "commercial-delivery-owner-post-approval-operator-checklist.json",
        {
            "status": "owner_post_approval_operator_checklist_blocked",
            "waiting_for_owner": False,
            "operator_ready": False,
            "real_owner_approval_present": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 100,
                "stage_command_count": 14,
                "pre_stage_verification_command_count": 10,
                "post_stage_verification_command_count": 11,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_blocked",
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
                "owner_stage_execution_plan_status": "owner_stage_execution_blocked",
                "owner_staging_preflight_status": "owner_staging_preflight_ready",
                "owner_staging_preflight_cached_staged_path_count": 0,
                "owner_post_staging_verifier_status": "owner_post_staging_verification_blocked",
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
                "pre_stage_ready": False,
                "post_stage_sequence_accounted_for": False,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "blocking_reasons": [
                    "resume_packet_accounted_for",
                    "approval_gate_matches_resume",
                    "stage_execution_matches_resume",
                    "operator_state_accounted_for",
                ],
            },
            "checks": [
                {"name": "resume_packet_accounted_for", "status": "failed"},
                {"name": "approval_gate_matches_resume", "status": "failed"},
                {"name": "stage_execution_matches_resume", "status": "failed"},
                {"name": "operator_state_accounted_for", "status": "failed"},
            ],
        },
    )

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner({"commercial_delivery_owner_post_approval_operator_checklist": 1}),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_ready"
    assert receipt.summary["expected_nonzero_steps"] == ["owner_post_approval_operator_checklist"]
    checklist = next(step for step in receipt.steps if step.name == "owner_post_approval_operator_checklist")
    assert checklist.status == "expected_nonzero_accepted"
    assert checklist.expected_nonzero_accepted is True
    assert (
        next(
            check for check in receipt.checks if check.name == "owner_post_approval_operator_checklist_accounted_for"
        ).status
        == "passed"
    )


def test_refresh_chain_receipt_blocks_unexpected_step_failure(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir)

    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner(
            {
                "commercial_delivery_owner_post_staging_verifier": 1,
                "commercial_delivery_owner_command_audit": 2,
            }
        ),
    )

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_blocked"
    assert receipt.summary["failed_step_count"] == 1
    failed = next(step for step in receipt.steps if step.name == "owner_command_audit")
    assert failed.status == "failed"
    assert failed.error == "command exited 2"
    assert next(check for check in receipt.checks if check.name == "no_unexpected_refresh_failures").status == "failed"


def test_refresh_chain_receipt_dry_run_plans_without_running_commands(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"

    receipt = build_refresh_chain_receipt(reports_dir=reports_dir, dry_run=True)

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_planned"
    assert receipt.dry_run is True
    assert receipt.summary["planned_step_count"] == 29
    assert all(step.status == "planned" for step in receipt.steps)


def test_refresh_chain_receipt_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir)
    _write_json(
        reports_dir / "commercial-delivery-task-board.json",
        {"status": "commercial_delivery_ready_for_owner_staging_review", "full_codex_parity_claimed": True},
    )

    receipt = build_refresh_chain_receipt(reports_dir=reports_dir, command_runner=_runner())

    assert receipt.status == "commercial_delivery_refresh_chain_receipt_blocked"
    assert receipt.full_codex_parity_claimed is True
    assert next(check for check in receipt.checks if check.name == "no_full_codex_parity_claim").status == "failed"


def test_refresh_chain_receipt_writes_json_and_markdown(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_ready_reports(reports_dir)
    receipt = build_refresh_chain_receipt(
        reports_dir=reports_dir,
        command_runner=_runner(
            {
                "commercial_delivery_owner_post_staging_verifier": 1,
                "commercial_delivery_owner_post_stage_commit_gate": 1,
                "commercial_delivery_owner_commit_packet": 1,
                "commercial_delivery_owner_approval_payload_audit": 1,
                "commercial_delivery_owner_stage_approval_gate": 1,
                "commercial_delivery_owner_stage_execution_plan": 1,
                "commercial_delivery_closure_snapshot": 1,
            }
        ),
    )
    json_output = tmp_path / "receipt.json"
    md_output = tmp_path / "receipt.md"

    write_report(receipt, json_output)
    write_markdown_receipt(receipt, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "commercial_delivery_refresh_chain_receipt_ready"
    assert payload["steps_count"] == len(payload["steps"])
    assert payload["checks_count"] == len(payload["checks"])
    assert payload["next_actions_count"] == len(payload["next_actions"])
    assert payload["known_limits_count"] == len(payload["known_limits"])
    assert "Commercial Delivery Refresh Chain Receipt" in markdown
    assert "integration_review_answer_action_matrix.py" in markdown
    assert "owner_post_staging_verifier" in render_markdown_receipt(receipt)
