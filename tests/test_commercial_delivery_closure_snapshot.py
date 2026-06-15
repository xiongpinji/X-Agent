from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_closure_snapshot import (
    build_commercial_delivery_closure_snapshot,
    render_markdown_snapshot,
    write_markdown_snapshot,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _stage_commands() -> list[str]:
    return [f"git add -- '{path}'" for path in _stage_paths()]


def _path_set_digest(paths: list[str]) -> str:
    return _digest_values(sorted(set(paths)))


def _write_inputs(tmp_path: Path, *, complete: bool = False) -> dict[str, Path]:
    paths = {
        "manifest_path": tmp_path / "manifest.json",
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
        "owner_stage_approval_brief_path": tmp_path / "owner-stage-approval-brief.json",
        "owner_approval_payload_audit_path": tmp_path / "owner-approval-payload-audit.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_stage_execution_plan_path": tmp_path / "owner-stage-execution-plan.json",
        "owner_staging_rollback_plan_path": tmp_path / "owner-staging-rollback-plan.json",
        "owner_post_staging_verifier_path": tmp_path / "owner-post-staging-verifier.json",
        "owner_post_stage_commit_gate_path": tmp_path / "owner-post-stage-commit-gate.json",
        "owner_commit_packet_path": tmp_path / "owner-commit-packet.json",
        "refresh_chain_path": tmp_path / "refresh-chain.json",
        "task_board_path": tmp_path / "task-board.json",
        "pre_approval_drift_guard_path": tmp_path / "pre-approval-drift-guard.json",
        "owner_approval_resume_packet_path": tmp_path / "owner-approval-resume-packet.json",
        "owner_post_approval_operator_checklist_path": tmp_path / "owner-post-approval-operator-checklist.json",
    }
    stage_path_digest = _digest_values(_stage_paths())
    stage_command_digest = _digest_values(_stage_commands())
    stage_path_set_digest = _path_set_digest(_stage_paths())
    cached_path_set_digest = stage_path_set_digest if complete else None
    _write_json(paths["manifest_path"], {"status": "original_kernel_delivery_manifest_ready", "full_codex_parity_claimed": False})
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "owner_gated": True,
            "stage_ready": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "owner_stage_execution_stage_command_count": 2,
                "rollback_reset_command_count": 2,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_modes_surface_file_count": 12,
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
            },
        },
    )
    _write_json(
        paths["owner_stage_approval_brief_path"],
        {
            "status": "owner_stage_approval_brief_ready",
            "owner_gated": True,
            "summary": {
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_payload_audit_path"],
        {
            "status": "owner_approval_payload_ready" if complete else "owner_approval_payload_blocked",
            "approval_payload_present": complete,
            "approval_payload_valid": complete,
            "ready_for_approval_gate": complete,
            "summary": {
                "blocking_reasons": []
                if complete
                else [
                    "owner_approval_payload_readable",
                    "approval_decision_present",
                    "owner_identity_present",
                ]
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_ready" if complete else "owner_stage_approval_blocked",
            "owner_gated": True,
            "stage_allowed": complete,
            "summary": {
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "blocking_reasons": [] if complete else ["owner_approval_readable"],
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": "owner_stage_execution_ready" if complete else "owner_stage_execution_blocked",
            "owner_gated": True,
            "stage_allowed": complete,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "summary": {"blocking_reasons": [] if complete else ["approval_gate_ready"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_rollback_plan_path"],
        {"status": "owner_staging_rollback_plan_ready", "owner_gated": True, "full_codex_parity_claimed": False},
    )
    _write_json(
        paths["owner_post_staging_verifier_path"],
        {
            "status": "owner_post_staging_verification_ready" if complete else "owner_post_staging_verification_blocked",
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": stage_path_set_digest,
            "cached_staged_path_set_digest": cached_path_set_digest,
            "summary": {
                "blocking_reasons": []
                if complete
                else [
                    "cached_paths_present_after_owner_staging",
                    "cached_path_set_digest_matches_expected_paths",
                ]
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_ready" if complete else "owner_post_stage_commit_gate_blocked",
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": stage_path_set_digest,
            "cached_staged_path_set_digest": cached_path_set_digest,
            "summary": {
                "blocking_reasons": [] if complete else ["owner_post_staging_verification_ready"]
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {
            "status": "owner_commit_packet_ready" if complete else "owner_commit_packet_blocked",
            "commit_allowed": complete,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": stage_path_set_digest,
            "cached_staged_path_set_digest": cached_path_set_digest,
            "summary": {
                "blocking_reasons": [] if complete else ["owner_post_stage_commit_gate_ready"]
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["refresh_chain_path"],
        {
            "status": "commercial_delivery_refresh_chain_receipt_ready",
            "summary": {"step_count": 19, "expected_nonzero_step_count": 0 if complete else 5},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["task_board_path"],
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": {
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "control_modes_preservation_status": "control_modes_preservation_ready",
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["pre_approval_drift_guard_path"],
        {
            "status": "pre_approval_drift_guard_ready",
            "real_owner_approval_present": False,
            "summary": {
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_resume_packet_path"],
        {
            "status": "owner_approval_resume_packet_ready"
            if complete
            else "owner_approval_resume_packet_waiting_for_owner",
            "waiting_for_owner": not complete,
            "resume_ready": complete,
            "real_owner_approval_present": complete,
            "summary": {
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": stage_path_set_digest,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_approval_operator_checklist_path"],
        {
            "status": "owner_post_approval_operator_checklist_ready"
            if complete
            else "owner_post_approval_operator_checklist_waiting_for_owner",
            "waiting_for_owner": not complete,
            "operator_ready": complete,
            "real_owner_approval_present": complete,
            "summary": {"stage_command_count": 2},
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_closure_snapshot_blocks_before_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert snapshot.delivery_complete is False
    assert snapshot.stage_ready is True
    assert snapshot.approval_ready is False
    assert snapshot.stage_execution_ready is False
    assert snapshot.post_stage_ready is False
    assert snapshot.commit_ready is False
    assert snapshot.rollback_ready is True
    assert snapshot.full_codex_parity_claimed is False
    assert snapshot.summary["stage_path_digest"] == _digest_values(_stage_paths())
    assert snapshot.summary["stage_command_digest"] == _digest_values(_stage_commands())
    assert snapshot.summary["expected_stage_path_set_digest"] == _path_set_digest(_stage_paths())
    assert snapshot.summary["cached_staged_path_set_digest"] is None
    assert snapshot.summary["secondary_handoff_completed_count"] == 44
    assert snapshot.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert snapshot.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert snapshot.summary["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert snapshot.summary["control_modes_plan_only_default"] is True
    assert snapshot.summary["control_modes_loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert snapshot.summary["control_modes_surface_file_count"] == 12
    assert snapshot.summary["approval_brief_control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert snapshot.summary["task_board_control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert snapshot.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_ready"
    assert snapshot.summary["pre_approval_drift_guard_real_owner_approval_present"] is False
    assert snapshot.summary["pre_approval_drift_guard_stage_path_digest"] == _digest_values(_stage_paths())
    assert snapshot.summary["pre_approval_drift_guard_stage_command_digest"] == _digest_values(_stage_commands())
    assert snapshot.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert snapshot.summary["owner_approval_resume_packet_waiting_for_owner"] is True
    assert snapshot.summary["owner_approval_resume_packet_resume_ready"] is False
    assert snapshot.summary["owner_approval_resume_packet_real_owner_approval_present"] is False
    assert (
        snapshot.summary["owner_post_approval_operator_checklist_status"]
        == "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert snapshot.summary["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert snapshot.summary["owner_post_approval_operator_checklist_operator_ready"] is False
    assert snapshot.summary["owner_post_approval_operator_checklist_real_owner_approval_present"] is False
    assert snapshot.summary["owner_action_required"] is True
    assert snapshot.summary["owner_blocking_reason_count"] == 9
    assert snapshot.summary["owner_blocking_reasons_by_report"] == {
        "owner_stage_approval_gate": ["owner_approval_readable"],
        "owner_approval_payload_audit": [
            "owner_approval_payload_readable",
            "approval_decision_present",
            "owner_identity_present",
        ],
        "owner_stage_execution_plan": ["approval_gate_ready"],
        "owner_post_staging_verifier": [
            "cached_paths_present_after_owner_staging",
            "cached_path_set_digest_matches_expected_paths",
        ],
        "owner_post_stage_commit_gate": ["owner_post_staging_verification_ready"],
        "owner_commit_packet": ["owner_post_stage_commit_gate_ready"],
    }
    assert snapshot.summary["owner_approval_payload_audit_status"] == "owner_approval_payload_blocked"
    assert snapshot.summary["owner_approval_payload_present"] is False
    assert snapshot.summary["owner_approval_payload_valid"] is False
    assert snapshot.summary["owner_approval_payload_ready_for_gate"] is False
    assert "owner_stage_approval_gate_not_ready" in snapshot.blockers
    assert "owner_commit_packet_not_ready" in snapshot.blockers
    assert "cached_staged_path_set_digest_not_ready" in snapshot.blockers
    assert next(check for check in snapshot.checks if check.name == "stage_ready").status == "passed"
    assert next(check for check in snapshot.checks if check.name == "owner_approval_ready").status == "failed"
    control_check = next(check for check in snapshot.checks if check.name == "control_modes_preserved")
    assert control_check.status == "passed"
    assert control_check.details["delivery_control_modes_plan_only_default"] is True
    assert next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready").status == "passed"
    assert (
        next(check for check in snapshot.checks if check.name == "owner_approval_resume_packet_accounted_for").status
        == "passed"
    )
    assert (
        next(
            check
            for check in snapshot.checks
            if check.name == "owner_post_approval_operator_checklist_accounted_for"
        ).status
        == "passed"
    )


def test_closure_snapshot_accepts_refresh_self_bootstrap_before_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_delivery_packet_before_owner_approval", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert snapshot.delivery_complete is False
    check = next(check for check in snapshot.checks if check.name == "refresh_chain_ready")
    assert check.status == "passed"
    assert check.details["failed_steps"] == ["owner_delivery_packet_before_owner_approval"]


def test_closure_snapshot_accepts_task_board_refresh_self_bootstrap(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "task_board_before_owner_decision", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    check = next(check for check in snapshot.checks if check.name == "refresh_chain_ready")
    assert check.status == "passed"
    assert check.details["failed_steps"] == ["task_board_before_owner_decision"]


def test_closure_snapshot_completes_with_closure_refresh_self_bootstrap(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "closure_snapshot", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    check = next(check for check in snapshot.checks if check.name == "refresh_chain_ready")
    assert check.status == "passed"
    assert check.details["refresh_chain_status"] == "commercial_delivery_refresh_chain_receipt_blocked"
    assert check.details["failed_steps"] == ["closure_snapshot"]
    assert snapshot.summary["refresh_chain_raw_ready"] is False
    assert snapshot.summary["refresh_chain_ready_for_snapshot"] is True
    assert snapshot.summary["refresh_chain_failed_steps"] == ["closure_snapshot"]


def test_closure_snapshot_accounts_for_stale_resume_packet_during_closure_self_bootstrap(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    refresh_payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh_payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    refresh_payload["summary"]["failed_step_count"] = 1
    refresh_payload["steps"] = [
        {"name": "closure_snapshot", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(refresh_payload), encoding="utf-8")
    resume_payload = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_payload["status"] = "owner_approval_resume_packet_blocked"
    resume_payload["waiting_for_owner"] = False
    resume_payload["resume_ready"] = False
    resume_payload["real_owner_approval_present"] = True
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_blocked"
    assert snapshot.summary["owner_approval_resume_packet_post_stage_accounted_for"] is True
    check = next(check for check in snapshot.checks if check.name == "owner_approval_resume_packet_accounted_for")
    assert check.status == "passed"
    assert check.details["post_stage_accounted_for"] is True


def test_closure_snapshot_accounts_for_stale_operator_checklist_during_post_stage_bootstrap(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    refresh_payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh_payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    refresh_payload["summary"]["failed_step_count"] = 1
    checklist_payload = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    checklist_payload["status"] = "owner_post_approval_operator_checklist_blocked"
    checklist_payload["waiting_for_owner"] = False
    checklist_payload["operator_ready"] = False
    checklist_payload["real_owner_approval_present"] = True
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(checklist_payload), encoding="utf-8")

    for failed_step in ("owner_pre_stage_readiness_gate", "owner_approval_handoff"):
        refresh_payload["steps"] = [
            {"name": failed_step, "status": "failed"},
        ]
        paths["refresh_chain_path"].write_text(json.dumps(refresh_payload), encoding="utf-8")

        snapshot = build_commercial_delivery_closure_snapshot(**paths)

        assert snapshot.status == "commercial_delivery_complete"
        assert snapshot.delivery_complete is True
        assert snapshot.summary["owner_post_approval_operator_checklist_status"] == (
            "owner_post_approval_operator_checklist_blocked"
        )
        assert snapshot.summary["owner_post_approval_operator_checklist_post_stage_accounted_for"] is True
        check = next(
            check for check in snapshot.checks if check.name == "owner_post_approval_operator_checklist_accounted_for"
        )
        assert check.status == "passed"
        assert check.details["post_stage_accounted_for"] is True


def test_closure_snapshot_accounts_for_delivery_packet_refresh_bootstrap_after_post_stage(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    refresh_payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh_payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    refresh_payload["summary"]["failed_step_count"] = 1
    refresh_payload["steps"] = [
        {"name": "owner_delivery_packet_before_owner_approval", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(refresh_payload), encoding="utf-8")
    resume_payload = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_payload["status"] = "owner_approval_resume_packet_blocked"
    resume_payload["waiting_for_owner"] = False
    resume_payload["resume_ready"] = False
    resume_payload["real_owner_approval_present"] = True
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_payload), encoding="utf-8")
    checklist_payload = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    checklist_payload["status"] = "owner_post_approval_operator_checklist_blocked"
    checklist_payload["waiting_for_owner"] = False
    checklist_payload["operator_ready"] = False
    checklist_payload["real_owner_approval_present"] = True
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(checklist_payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.summary["refresh_chain_failed_steps"] == ["owner_delivery_packet_before_owner_approval"]
    assert snapshot.summary["owner_approval_resume_packet_post_stage_accounted_for"] is True
    assert snapshot.summary["owner_post_approval_operator_checklist_post_stage_accounted_for"] is True
    assert next(
        check for check in snapshot.checks if check.name == "owner_approval_resume_packet_accounted_for"
    ).status == "passed"
    assert next(
        check for check in snapshot.checks if check.name == "owner_post_approval_operator_checklist_accounted_for"
    ).status == "passed"


def test_closure_snapshot_blocks_unrelated_failed_refresh_receipt(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_command_audit", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert next(check for check in snapshot.checks if check.name == "refresh_chain_ready").status == "failed"


def test_closure_snapshot_blocks_unrelated_failed_refresh_receipt_when_other_gates_ready(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_command_audit", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert snapshot.delivery_complete is False
    check = next(check for check in snapshot.checks if check.name == "refresh_chain_ready")
    assert check.status == "failed"
    assert check.details["failed_steps"] == ["owner_command_audit"]
    assert snapshot.summary["refresh_chain_raw_ready"] is False
    assert snapshot.summary["refresh_chain_ready_for_snapshot"] is False
    assert snapshot.summary["refresh_chain_failed_steps"] == ["owner_command_audit"]


def test_closure_snapshot_complete_when_all_owner_gates_ready(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.blockers == []
    assert snapshot.summary["owner_action_required"] is False
    assert snapshot.summary["owner_blocking_reason_count"] == 0
    assert snapshot.summary["owner_blocking_reasons_by_report"] == {}
    assert {check.status for check in snapshot.checks} == {"passed"}
    assert snapshot.summary["cached_staged_path_set_digest"] == _path_set_digest(_stage_paths())
    assert (
        snapshot.summary["owner_post_approval_operator_checklist_status"]
        == "owner_post_approval_operator_checklist_ready"
    )
    assert snapshot.summary["owner_post_approval_operator_checklist_operator_ready"] is True


def test_closure_snapshot_completes_with_post_commit_accounted_blocked_owner_gates(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    delivery_packet = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    delivery_packet["summary"].update(
        {
            "post_stage_chain_accounted_for": True,
            "post_commit_owner_gate_accounted_for": True,
            "post_commit_stage_approval_accounted_for": True,
            "post_commit_stage_execution_accounted_for": True,
        }
    )
    paths["owner_delivery_packet_path"].write_text(json.dumps(delivery_packet), encoding="utf-8")
    approval_payload = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    approval_payload["status"] = "owner_approval_payload_blocked"
    approval_payload["approval_payload_present"] = True
    approval_payload["approval_payload_valid"] = False
    approval_payload["ready_for_approval_gate"] = False
    approval_payload["summary"]["blocking_reasons"] = [
        "owner_delivery_packet_ready",
        "owner_stage_approval_request_ready",
    ]
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(approval_payload), encoding="utf-8")
    approval_gate = json.loads(paths["owner_stage_approval_gate_path"].read_text(encoding="utf-8"))
    approval_gate["status"] = "owner_stage_approval_blocked"
    approval_gate["stage_allowed"] = False
    approval_gate["summary"]["blocking_reasons"] = [
        "owner_delivery_packet_ready",
        "owner_approval_payload_audit_ready",
        "owner_delivery_packet_pre_stage_ready",
    ]
    paths["owner_stage_approval_gate_path"].write_text(json.dumps(approval_gate), encoding="utf-8")
    execution_plan = json.loads(paths["owner_stage_execution_plan_path"].read_text(encoding="utf-8"))
    execution_plan["status"] = "owner_stage_execution_blocked"
    execution_plan["stage_allowed"] = False
    execution_plan["summary"]["blocking_reasons"] = [
        "owner_staging_preflight_accounted_for",
        "owner_delivery_packet_ready",
        "approval_gate_ready",
        "no_cached_staged_paths_before_stage_execution_or_accounted",
    ]
    paths["owner_stage_execution_plan_path"].write_text(json.dumps(execution_plan), encoding="utf-8")
    refresh = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    refresh["summary"]["failed_step_count"] = 1
    refresh["steps"] = [{"name": "owner_staging_preflight", "status": "failed"}]
    paths["refresh_chain_path"].write_text(json.dumps(refresh), encoding="utf-8")
    resume_packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_packet["status"] = "owner_approval_resume_packet_blocked"
    resume_packet["waiting_for_owner"] = False
    resume_packet["resume_ready"] = False
    resume_packet["real_owner_approval_present"] = True
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_packet), encoding="utf-8")
    operator_checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    operator_checklist["status"] = "owner_post_approval_operator_checklist_blocked"
    operator_checklist["waiting_for_owner"] = False
    operator_checklist["operator_ready"] = False
    operator_checklist["real_owner_approval_present"] = True
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(operator_checklist), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.stage_ready is True
    assert snapshot.approval_ready is True
    assert snapshot.stage_execution_ready is True
    assert snapshot.summary["post_commit_closure_accounted_for"] is True
    assert snapshot.summary["delivery_post_stage_chain_accounted_for"] is True
    assert snapshot.summary["delivery_post_commit_owner_gate_accounted_for"] is True
    assert snapshot.summary["post_commit_refresh_accounted_for"] is True
    assert snapshot.summary["owner_approval_resume_packet_post_stage_accounted_for"] is True
    assert snapshot.summary["owner_post_approval_operator_checklist_post_stage_accounted_for"] is True
    assert snapshot.summary["owner_blocking_reason_count"] == 0
    assert snapshot.summary["owner_blocking_reasons_by_report"] == {}
    assert snapshot.summary["owner_action_required"] is False
    assert next(check for check in snapshot.checks if check.name == "owner_approval_ready").status == "passed"
    assert next(check for check in snapshot.checks if check.name == "stage_execution_ready").status == "passed"
    assert next(check for check in snapshot.checks if check.name == "refresh_chain_ready").status == "passed"


def test_closure_snapshot_completes_when_post_approval_drift_guard_is_accounted_for(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "stage_path_digest": _digest_values(_stage_paths()),
                "stage_command_digest": _digest_values(_stage_commands()),
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
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.blockers == []
    drift_check = next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True
    assert snapshot.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_blocked"
    assert snapshot.summary["pre_approval_drift_guard_accounted_for"] is True


def test_closure_snapshot_completes_after_post_stage_task_board_drift_guard_only_blocker(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    stage_path_digest = _digest_values(_stage_paths())
    stage_command_digest = _digest_values(_stage_commands())
    expected_stage_path_set_digest = _path_set_digest(_stage_paths())
    _write_json(
        paths["task_board_path"],
        {
            "status": "commercial_delivery_blocked",
            "summary": {
                "secondary_pending_count": 1,
                "secondary_pending_blocks_owner_staging": False,
                "owner_staging_preflight_accounted_for": True,
                "owner_post_staging_verifier_status": "owner_post_staging_verification_ready",
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_ready",
                "owner_commit_packet_status": "owner_commit_packet_ready",
                "eligible_stage_count": 2,
                "owner_stage_command_count": 2,
                "post_staging_cached_path_count": 2,
                "control_modes_preservation_status": "control_modes_preservation_ready",
            },
            "checks": [
                {
                    "name": "pre_approval_drift_guard_ready",
                    "status": "failed",
                }
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "owner_approval_payload_audit": "owner_approval_payload_ready",
                "owner_stage_approval_gate": "owner_stage_approval_ready",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_ready",
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
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
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.summary["task_board_post_stage_accounted_for"] is True
    assert snapshot.summary["task_board_ready_for_snapshot"] is True
    assert snapshot.summary["pre_approval_drift_guard_post_stage_accounted_for"] is True
    assert snapshot.summary["pre_approval_drift_guard_accounted_for"] is True
    assert next(check for check in snapshot.checks if check.name == "task_board_ready").status == "passed"
    drift_check = next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_post_stage_accounted_for"] is True


def test_closure_snapshot_accounts_for_post_approval_complete_pre_approval_drift_guard(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "stage_path_digest": _digest_values(_stage_paths()),
                "stage_command_digest": _digest_values(_stage_commands()),
                "expected_stage_path_set_digest": _path_set_digest(_stage_paths()),
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": True,
                "owner_approval_payload_ready_for_gate": True,
                "owner_stage_approval_gate_status": "owner_stage_approval_ready",
                "owner_stage_execution_plan_status": "owner_stage_execution_ready",
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
                {"name": "approval_gate_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    drift_check = next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True


def test_closure_snapshot_accounts_for_post_commit_pre_approval_drift_guard(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=False)
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "stage_path_digest": _digest_values(_stage_paths()),
                "stage_command_digest": _digest_values(_stage_commands()),
                "expected_stage_path_set_digest": _path_set_digest(_stage_paths()),
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

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    drift_check = next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True
    assert snapshot.summary["pre_approval_drift_guard_accounted_for"] is True


def test_closure_snapshot_accounts_for_post_commit_pre_approval_drift_guard_with_blocked_operator_checklist(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=False)
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "stage_path_digest": _digest_values(_stage_paths()),
                "stage_command_digest": _digest_values(_stage_commands()),
                "expected_stage_path_set_digest": _path_set_digest(_stage_paths()),
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

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    drift_check = next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True
    assert snapshot.summary["pre_approval_drift_guard_accounted_for"] is True


def test_closure_snapshot_accounts_for_post_approval_boundary_drift_guard(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "owner_approval_payload_audit": "owner_approval_payload_blocked",
                "owner_stage_approval_gate": "owner_stage_approval_blocked",
                "owner_stage_execution_plan": "owner_stage_execution_ready",
                "owner_post_approval_operator_checklist": "owner_post_approval_operator_checklist_blocked",
                "closure_snapshot": "commercial_delivery_complete",
            },
            "summary": {
                "stage_path_digest": _digest_values(_stage_paths()),
                "stage_command_digest": _digest_values(_stage_commands()),
                "expected_stage_path_set_digest": _path_set_digest(_stage_paths()),
                "owner_approval_payload_present": True,
                "owner_approval_payload_valid": False,
                "owner_approval_payload_ready_for_gate": False,
                "owner_stage_approval_gate_status": "owner_stage_approval_blocked",
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
                {"name": "approval_payload_blocked_before_owner", "status": "failed"},
                {"name": "stage_execution_blocked_before_owner", "status": "failed"},
                {"name": "operator_checklist_waiting_before_owner", "status": "failed"},
                {"name": "closure_blocked_before_owner", "status": "failed"},
            ],
        },
    )

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    drift_check = next(check for check in snapshot.checks if check.name == "pre_approval_drift_guard_ready")
    assert drift_check.status == "passed"
    assert drift_check.details["pre_approval_drift_guard_accounted_for"] is True
    assert snapshot.summary["pre_approval_drift_guard_accounted_for"] is True


def test_closure_snapshot_blocks_expected_nonzero_owner_stage_boundary_until_real_gates_pass(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=False)
    stage_path_digest = _digest_values(_stage_paths())
    stage_command_digest = _digest_values(_stage_commands())
    stage_path_set_digest = _path_set_digest(_stage_paths())
    expected_nonzero_steps = [
        "owner_post_staging_verifier",
        "owner_post_stage_commit_gate",
        "owner_commit_packet",
        "owner_approval_payload_audit",
        "owner_stage_approval_gate",
        "owner_stage_execution_plan",
        "owner_delivery_packet",
        "owner_approval_resume_packet",
        "owner_post_approval_operator_checklist",
    ]
    delivery_packet = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    delivery_packet.update({"status": "owner_delivery_packet_blocked", "stage_ready": False})
    delivery_packet["summary"].update(
        {
            "stage_include_count": 100,
            "owner_stage_command_count": 2,
            "owner_stage_execution_stage_command_count": 2,
            "rollback_reset_command_count": 2,
            "expected_nonzero_steps": expected_nonzero_steps,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": stage_path_set_digest,
        }
    )
    paths["owner_delivery_packet_path"].write_text(json.dumps(delivery_packet), encoding="utf-8")
    approval_payload = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    approval_payload.update(
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": True,
            "approval_payload_valid": False,
            "ready_for_approval_gate": False,
        }
    )
    approval_payload["summary"]["blocking_reasons"] = [
        "owner_delivery_packet_ready",
        "approval_counts_match_request_and_delivery_packet",
    ]
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(approval_payload), encoding="utf-8")
    approval_gate = json.loads(paths["owner_stage_approval_gate_path"].read_text(encoding="utf-8"))
    approval_gate.update({"status": "owner_stage_approval_blocked", "stage_allowed": False})
    approval_gate["summary"].update(
        {
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "blocking_reasons": ["owner_approval_payload_audit_ready"],
        }
    )
    paths["owner_stage_approval_gate_path"].write_text(json.dumps(approval_gate), encoding="utf-8")
    execution_plan = json.loads(paths["owner_stage_execution_plan_path"].read_text(encoding="utf-8"))
    execution_plan.update(
        {
            "status": "owner_stage_execution_blocked",
            "stage_allowed": False,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
        }
    )
    execution_plan["summary"]["blocking_reasons"] = ["approval_gate_ready"]
    paths["owner_stage_execution_plan_path"].write_text(json.dumps(execution_plan), encoding="utf-8")
    post_staging = json.loads(paths["owner_post_staging_verifier_path"].read_text(encoding="utf-8"))
    post_staging.update(
        {
            "status": "owner_post_staging_verification_blocked",
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 0,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": stage_path_set_digest,
            "cached_staged_path_set_digest": None,
        }
    )
    post_staging["summary"].update(
        {
            "blocking_reasons": [
                "cached_paths_present_after_owner_staging",
                "cached_path_set_digest_matches_expected_paths",
            ],
            "expected_stage_path_count": 2,
            "cached_staged_path_count": 0,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": stage_path_set_digest,
            "cached_staged_path_set_digest": None,
        }
    )
    paths["owner_post_staging_verifier_path"].write_text(json.dumps(post_staging), encoding="utf-8")
    for key, status in (
        ("owner_post_stage_commit_gate_path", "owner_post_stage_commit_gate_blocked"),
        ("owner_commit_packet_path", "owner_commit_packet_blocked"),
    ):
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        payload.update(
            {
                "status": status,
                "commit_allowed": False,
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": stage_path_set_digest,
                "cached_staged_path_set_digest": None,
            }
        )
        payload["summary"]["blocking_reasons"] = ["owner_post_staging_verification_ready"]
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    refresh = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh["status"] = "commercial_delivery_refresh_chain_receipt_ready"
    refresh["summary"].update(
        {
            "expected_nonzero_step_count": len(expected_nonzero_steps),
            "expected_nonzero_steps": expected_nonzero_steps,
            "failed_step_count": 0,
        }
    )
    refresh["steps"] = [
        {"name": name, "status": "expected_nonzero_accepted"}
        for name in expected_nonzero_steps
    ]
    paths["refresh_chain_path"].write_text(json.dumps(refresh), encoding="utf-8")
    _write_json(
        paths["pre_approval_drift_guard_path"],
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
                "owner_post_approval_operator_checklist": (
                    "owner_post_approval_operator_checklist_blocked"
                ),
                "closure_snapshot": "commercial_delivery_closure_blocked",
            },
            "summary": {
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": stage_path_set_digest,
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
    resume_packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_packet.update(
        {
            "status": "owner_approval_resume_packet_blocked",
            "waiting_for_owner": False,
            "resume_ready": False,
            "real_owner_approval_present": True,
        }
    )
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_packet), encoding="utf-8")
    operator_checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    operator_checklist.update(
        {
            "status": "owner_post_approval_operator_checklist_blocked",
            "waiting_for_owner": False,
            "operator_ready": False,
            "real_owner_approval_present": True,
        }
    )
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(operator_checklist), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert snapshot.delivery_complete is False
    assert snapshot.summary["refresh_expected_nonzero_ready"] is True
    assert snapshot.summary["owner_delivery_packet_expected_nonzero_accounted_for"] is True
    assert snapshot.summary["owner_approval_expected_nonzero_accounted_for"] is True
    assert snapshot.summary["stage_execution_expected_nonzero_accounted_for"] is True
    assert snapshot.summary["post_stage_expected_nonzero_accounted_for"] is True
    assert snapshot.summary["commit_expected_nonzero_accounted_for"] is True
    assert snapshot.summary["cached_staged_path_set_digest_pre_stage_accounted_for"] is True
    assert snapshot.summary["owner_approval_resume_packet_post_stage_accounted_for"] is False
    assert snapshot.summary["owner_post_approval_operator_checklist_post_stage_accounted_for"] is False
    assert snapshot.summary["owner_blocking_reasons_by_report"]
    assert "owner_stage_approval_gate_not_ready" in snapshot.blockers
    assert "owner_stage_execution_plan_not_ready" in snapshot.blockers
    assert "post_staging_verifier_not_ready" in snapshot.blockers
    assert "owner_commit_packet_not_ready" in snapshot.blockers
    assert "cached_staged_path_set_digest_not_ready" in snapshot.blockers
    assert next(check for check in snapshot.checks if check.name == "stage_ready").status == "failed"
    assert next(check for check in snapshot.checks if check.name == "owner_approval_ready").status == "failed"
    assert next(check for check in snapshot.checks if check.name == "stage_execution_ready").status == "failed"
    assert next(check for check in snapshot.checks if check.name == "post_stage_ready").status == "failed"
    assert next(check for check in snapshot.checks if check.name == "commit_ready").status == "failed"
    cached_check = next(
        check for check in snapshot.checks if check.name == "cached_staged_path_set_digest_consistent"
    )
    assert cached_check.status == "failed"
    assert cached_check.details["cached_staged_path_set_digest_pre_stage_accounted_for"] is True


def test_closure_snapshot_blocks_count_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["summary"]["rollback_reset_command_count"] = 3
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert next(check for check in snapshot.checks if check.name == "stage_counts_consistent").status == "failed"


def test_closure_snapshot_allows_subset_eligible_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["summary"]["stage_include_count"] = 100
    payload["summary"]["owner_stage_command_count"] = 2
    payload["summary"]["owner_stage_execution_stage_command_count"] = 2
    payload["summary"]["rollback_reset_command_count"] = 2
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    count_check = next(check for check in snapshot.checks if check.name == "stage_counts_consistent")
    assert count_check.status == "passed"
    assert count_check.details["stage_include_count"] == 100
    assert count_check.details["owner_stage_command_count"] == 2


def test_closure_snapshot_completes_post_commit_noop_with_zero_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    empty_digest = _digest_values([])
    delivery_packet = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    delivery_packet["summary"].update(
        {
            "stage_include_count": 100,
            "owner_stage_command_count": 0,
            "owner_stage_execution_stage_command_count": 0,
            "rollback_reset_command_count": 0,
            "post_stage_chain_accounted_for": True,
            "post_commit_owner_gate_accounted_for": True,
            "post_commit_stage_approval_accounted_for": True,
            "post_commit_stage_execution_accounted_for": True,
            "post_commit_noop_accounted_for": True,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
        }
    )
    paths["owner_delivery_packet_path"].write_text(json.dumps(delivery_packet), encoding="utf-8")
    for key in ("owner_stage_approval_brief_path", "owner_stage_approval_gate_path"):
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        payload["status"] = (
            "owner_stage_approval_brief_blocked"
            if key == "owner_stage_approval_brief_path"
            else "owner_stage_approval_blocked"
        )
        payload["stage_allowed"] = False
        payload["summary"].update(
            {
                "stage_path_digest": empty_digest,
                "stage_command_digest": empty_digest,
                "blocking_reasons": ["owner_delivery_packet_ready"],
            }
        )
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    payload = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    payload.update(
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": True,
            "approval_payload_valid": False,
            "ready_for_approval_gate": False,
        }
    )
    payload["summary"]["blocking_reasons"] = ["owner_delivery_packet_ready"]
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(payload), encoding="utf-8")
    execution_plan = json.loads(paths["owner_stage_execution_plan_path"].read_text(encoding="utf-8"))
    execution_plan.update(
        {
            "status": "owner_stage_execution_blocked",
            "stage_allowed": False,
            "stage_command_count": 0,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
        }
    )
    execution_plan["summary"]["blocking_reasons"] = ["owner_delivery_packet_ready"]
    paths["owner_stage_execution_plan_path"].write_text(json.dumps(execution_plan), encoding="utf-8")
    for key in ("owner_post_staging_verifier_path", "owner_post_stage_commit_gate_path", "owner_commit_packet_path"):
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        payload.update(
            {
                "stage_path_digest": empty_digest,
                "stage_command_digest": empty_digest,
                "expected_stage_path_set_digest": empty_digest,
                "cached_staged_path_set_digest": empty_digest,
            }
        )
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    rollback = json.loads(paths["owner_staging_rollback_plan_path"].read_text(encoding="utf-8"))
    rollback.update({"reset_command_count": 0, "rollback_available": False, "rollback_required": False})
    paths["owner_staging_rollback_plan_path"].write_text(json.dumps(rollback), encoding="utf-8")
    refresh = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    refresh["summary"]["failed_step_count"] = 4
    refresh["steps"] = [
        {"name": "owner_delivery_packet", "status": "failed"},
        {"name": "closure_snapshot", "status": "failed"},
        {"name": "owner_approval_resume_packet", "status": "failed"},
        {"name": "owner_post_approval_operator_checklist", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(refresh), encoding="utf-8")
    pre_approval = json.loads(paths["pre_approval_drift_guard_path"].read_text(encoding="utf-8"))
    pre_approval.update({"status": "pre_approval_drift_guard_blocked", "real_owner_approval_present": True})
    pre_approval["summary"].update(
        {
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
        }
    )
    paths["pre_approval_drift_guard_path"].write_text(json.dumps(pre_approval), encoding="utf-8")
    resume_packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_packet["status"] = "owner_approval_resume_packet_blocked"
    resume_packet["waiting_for_owner"] = False
    resume_packet["resume_ready"] = False
    resume_packet["real_owner_approval_present"] = True
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_packet), encoding="utf-8")
    operator_checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    operator_checklist["status"] = "owner_post_approval_operator_checklist_blocked"
    operator_checklist["waiting_for_owner"] = False
    operator_checklist["operator_ready"] = False
    operator_checklist["real_owner_approval_present"] = True
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(operator_checklist), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.summary["post_commit_noop_accounted_for"] is True
    assert snapshot.summary["post_commit_refresh_accounted_for"] is True
    assert snapshot.summary["owner_approval_resume_packet_post_stage_accounted_for"] is True
    assert snapshot.summary["owner_post_approval_operator_checklist_post_commit_noop_accounted_for"] is True
    count_check = next(check for check in snapshot.checks if check.name == "stage_counts_consistent")
    assert count_check.status == "passed"
    assert count_check.details["owner_stage_command_count"] == 0


def test_closure_snapshot_completes_ready_resume_after_noop_commit_accounting(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    empty_digest = _digest_values([])
    delivery_packet = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    delivery_packet["summary"].update(
        {
            "stage_include_count": 100,
            "owner_stage_command_count": 0,
            "owner_stage_execution_stage_command_count": 0,
            "rollback_reset_command_count": 0,
            "post_stage_chain_accounted_for": True,
            "post_commit_owner_gate_accounted_for": True,
            "post_commit_stage_approval_accounted_for": True,
            "post_commit_stage_execution_accounted_for": True,
            "post_commit_noop_accounted_for": True,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
        }
    )
    paths["owner_delivery_packet_path"].write_text(json.dumps(delivery_packet), encoding="utf-8")
    for key in ("owner_stage_approval_brief_path", "owner_stage_approval_gate_path"):
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        payload["status"] = (
            "owner_stage_approval_brief_blocked"
            if key == "owner_stage_approval_brief_path"
            else "owner_stage_approval_blocked"
        )
        payload["stage_allowed"] = False
        payload["summary"].update(
            {
                "stage_path_digest": empty_digest,
                "stage_command_digest": empty_digest,
                "expected_stage_path_set_digest": empty_digest,
                "blocking_reasons": ["owner_delivery_packet_ready"],
            }
        )
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    approval_payload = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    approval_payload.update(
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": True,
            "approval_payload_valid": False,
            "ready_for_approval_gate": False,
        }
    )
    approval_payload["summary"].update(
        {
            "post_commit_noop_accounted_for": True,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
            "blocking_reasons": ["owner_delivery_packet_ready"],
        }
    )
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(approval_payload), encoding="utf-8")
    execution_plan = json.loads(paths["owner_stage_execution_plan_path"].read_text(encoding="utf-8"))
    execution_plan.update(
        {
            "status": "owner_stage_execution_blocked",
            "stage_allowed": False,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
        }
    )
    execution_plan["summary"].update(
        {
            "post_commit_noop_accounted_for": True,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
            "blocking_reasons": ["owner_delivery_packet_ready"],
        }
    )
    paths["owner_stage_execution_plan_path"].write_text(json.dumps(execution_plan), encoding="utf-8")
    for key in ("owner_post_staging_verifier_path", "owner_post_stage_commit_gate_path", "owner_commit_packet_path"):
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        payload.update(
            {
                "stage_path_digest": empty_digest,
                "stage_command_digest": empty_digest,
                "expected_stage_path_set_digest": empty_digest,
                "cached_staged_path_set_digest": empty_digest,
                "post_commit_noop_accounted_for": True,
            }
        )
        payload.setdefault("summary", {})
        payload["summary"].update(
            {
                "stage_path_digest": empty_digest,
                "stage_command_digest": empty_digest,
                "expected_stage_path_set_digest": empty_digest,
                "cached_staged_path_set_digest": empty_digest,
                "post_commit_noop_accounted_for": True,
            }
        )
        if key == "owner_post_stage_commit_gate_path":
            payload["status"] = "owner_post_stage_commit_gate_blocked"
            payload["commit_allowed"] = False
            payload["summary"]["blocking_reasons"] = ["task_board_ready"]
        elif key == "owner_commit_packet_path":
            payload["status"] = "owner_commit_packet_blocked"
            payload["commit_allowed"] = False
            payload["summary"]["blocking_reasons"] = [
                "owner_post_stage_commit_gate_ready",
                "task_board_ready",
                "commit_allowed_by_gate",
            ]
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    rollback = json.loads(paths["owner_staging_rollback_plan_path"].read_text(encoding="utf-8"))
    rollback.update({"reset_command_count": 0, "rollback_available": False, "rollback_required": False})
    rollback["summary"] = {
        "post_commit_noop_accounted_for": True,
        "stage_path_digest": empty_digest,
    }
    paths["owner_staging_rollback_plan_path"].write_text(json.dumps(rollback), encoding="utf-8")
    refresh = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    refresh["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    refresh["summary"]["failed_step_count"] = 14
    refresh["steps"] = [
        {"name": "task_board_before_owner_decision", "status": "failed"},
        {"name": "owner_decision_brief", "status": "failed"},
        {"name": "owner_pre_stage_readiness_gate", "status": "failed"},
        {"name": "owner_staging_runbook", "status": "failed"},
        {"name": "owner_delivery_packet_before_owner_approval", "status": "failed"},
        {"name": "owner_stage_approval_request", "status": "failed"},
        {"name": "owner_approval_payload_audit", "status": "failed"},
        {"name": "owner_stage_approval_brief", "status": "failed"},
        {"name": "owner_delivery_packet", "status": "failed"},
        {"name": "closure_snapshot", "status": "failed"},
        {"name": "owner_approval_handoff", "status": "failed"},
        {"name": "pre_approval_drift_guard", "status": "failed"},
        {"name": "owner_approval_resume_packet", "status": "failed"},
        {"name": "owner_post_approval_operator_checklist", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(refresh), encoding="utf-8")
    pre_approval = json.loads(paths["pre_approval_drift_guard_path"].read_text(encoding="utf-8"))
    pre_approval.update({"status": "pre_approval_drift_guard_blocked", "real_owner_approval_present": True})
    pre_approval["summary"].update(
        {
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
        }
    )
    paths["pre_approval_drift_guard_path"].write_text(json.dumps(pre_approval), encoding="utf-8")
    resume_packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_packet.update(
        {
            "status": "owner_approval_resume_packet_ready",
            "waiting_for_owner": False,
            "resume_ready": True,
            "real_owner_approval_present": True,
            "stage_allowed": False,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
        }
    )
    resume_packet["summary"].update(
        {
            "post_commit_noop_accounted_for": True,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
            "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
            "owner_commit_packet_status": "owner_commit_packet_blocked",
        }
    )
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_packet), encoding="utf-8")
    operator_checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    operator_checklist.update(
        {
            "status": "owner_post_approval_operator_checklist_ready",
            "waiting_for_owner": False,
            "operator_ready": True,
            "real_owner_approval_present": True,
            "stage_allowed": False,
        }
    )
    operator_checklist["summary"].update(
        {
            "blocking_reasons": [],
            "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_blocked",
            "owner_commit_packet_status": "owner_commit_packet_blocked",
        }
    )
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(operator_checklist), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert snapshot.delivery_complete is True
    assert snapshot.commit_ready is True
    assert snapshot.summary["commit_noop_accounted_for"] is True
    assert snapshot.summary["commit_gate_noop_accounted_for"] is True
    assert snapshot.summary["commit_packet_noop_accounted_for"] is True
    assert snapshot.summary["post_commit_refresh_accounted_for"] is True
    assert snapshot.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_ready"
    assert (
        snapshot.summary["owner_post_approval_operator_checklist_status"]
        == "owner_post_approval_operator_checklist_ready"
    )
    assert snapshot.summary["owner_blocking_reasons_by_report"] == {}
    assert snapshot.blockers == []
    commit_check = next(check for check in snapshot.checks if check.name == "commit_ready")
    assert commit_check.status == "passed"
    assert commit_check.details["commit_allowed"] is False
    assert commit_check.details["commit_noop_accounted_for"] is True


def test_closure_snapshot_accepts_superseded_approval_brief_after_post_stage_evidence(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    old_stage_paths = ["backend/app/core/old_storage.py"]
    old_stage_commands = ["git add -- 'backend/app/core/old_storage.py'"]
    approval_brief = json.loads(paths["owner_stage_approval_brief_path"].read_text(encoding="utf-8"))
    approval_brief["summary"].update(
        {
            "stage_path_digest": _digest_values(old_stage_paths),
            "stage_command_digest": _digest_values(old_stage_commands),
        }
    )
    paths["owner_stage_approval_brief_path"].write_text(json.dumps(approval_brief), encoding="utf-8")
    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_complete"
    assert next(check for check in snapshot.checks if check.name == "stage_counts_consistent").status == "passed"
    assert next(check for check in snapshot.checks if check.name == "stage_path_digest_consistent").status == "passed"
    assert next(check for check in snapshot.checks if check.name == "stage_command_digest_consistent").status == "passed"
    path_check = next(check for check in snapshot.checks if check.name == "stage_path_digest_consistent")
    assert path_check.details["current_post_stage_ready_for_digest"] is True


def test_closure_snapshot_blocks_stage_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    payload = json.loads(paths["owner_commit_packet_path"].read_text(encoding="utf-8"))
    payload["stage_command_digest"] = "1" * 64
    paths["owner_commit_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert next(check for check in snapshot.checks if check.name == "stage_command_digest_consistent").status == "failed"
    assert "cached_staged_path_set_digest_not_ready" not in snapshot.blockers


def test_closure_snapshot_blocks_cached_set_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, complete=True)
    payload = json.loads(paths["owner_post_stage_commit_gate_path"].read_text(encoding="utf-8"))
    payload["cached_staged_path_set_digest"] = "2" * 64
    paths["owner_post_stage_commit_gate_path"].write_text(json.dumps(payload), encoding="utf-8")

    snapshot = build_commercial_delivery_closure_snapshot(**paths)

    assert snapshot.status == "commercial_delivery_closure_blocked"
    assert next(
        check for check in snapshot.checks if check.name == "cached_staged_path_set_digest_consistent"
    ).status == "failed"


def test_closure_snapshot_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    snapshot = build_commercial_delivery_closure_snapshot(**paths)
    json_output = tmp_path / "snapshot.json"
    md_output = tmp_path / "snapshot.md"

    write_report(snapshot, json_output)
    write_markdown_snapshot(snapshot, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "commercial_delivery_closure_blocked"
    assert payload["checks_count"] == len(payload["checks"])
    assert payload["blockers_count"] == len(payload["blockers"])
    assert payload["next_actions_count"] == len(payload["next_actions"])
    assert payload["known_limits_count"] == len(payload["known_limits"])
    assert payload["summary"]["owner_action_required"] is True
    assert payload["summary"]["owner_blocking_reason_count"] == 9
    assert "Commercial Delivery Closure Snapshot" in markdown
    assert "Owner blocking reason count: `9`" in markdown
    assert "owner_approval_payload_audit" in markdown
    assert "owner_post_staging_verifier" in markdown
    assert f"Stage path digest: `{snapshot.summary['stage_path_digest']}`" in markdown
    assert "owner_stage_approval_gate_not_ready" in render_markdown_snapshot(snapshot)
