from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_pre_approval_drift_guard import (
    build_pre_approval_drift_guard,
    render_markdown_guard,
    write_markdown_guard,
    write_report,
)

STAGE_PATH_DIGEST = "path-digest-123"
STAGE_COMMAND_DIGEST = "command-digest-456"
EXPECTED_STAGE_PATH_SET_DIGEST = "path-set-digest-789"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _secondary_summary() -> dict[str, object]:
    return {
        "secondary_pending_count": 0,
        "secondary_handoff_next_count": 1,
        "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
        "secondary_handoff_completed_count": 44,
        "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
    }


def _stage_summary() -> dict[str, object]:
    return {
        "stage_path_digest": STAGE_PATH_DIGEST,
        "stage_command_digest": STAGE_COMMAND_DIGEST,
        "expected_stage_path_set_digest": EXPECTED_STAGE_PATH_SET_DIGEST,
    }


def _placeholder_summary() -> dict[str, object]:
    return {
        "template_identity_placeholders_present": True,
        "template_owner_placeholder": "<owner-name-or-id>",
        "template_approval_id_placeholder": "<approval-id>",
        "template_approved_at_placeholder": "<ISO-8601 UTC timestamp>",
    }


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "manifest_path": tmp_path / "manifest.json",
        "owner_stage_approval_request_path": tmp_path / "owner-stage-approval-request.json",
        "owner_approval_handoff_path": tmp_path / "owner-approval-handoff.json",
        "owner_approval_payload_audit_path": tmp_path / "owner-approval-payload-audit.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_stage_execution_plan_path": tmp_path / "owner-stage-execution-plan.json",
        "owner_post_approval_operator_checklist_path": tmp_path / "owner-post-approval-operator-checklist.json",
        "closure_snapshot_path": tmp_path / "closure-snapshot.json",
        "task_board_path": tmp_path / "task-board.json",
        "owner_approval_path": tmp_path / "owner-stage-approval.json",
    }
    _write_json(
        paths["manifest_path"],
        {
            "status": "original_kernel_delivery_manifest_ready",
            "stage_include_count": 96,
            "excluded_dirty_count": 149,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_request_path"],
        {
            "status": "owner_stage_approval_request_ready",
            "summary": _stage_summary() | _secondary_summary() | _placeholder_summary(),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_handoff_path"],
        {
            "status": "owner_approval_handoff_ready",
            "summary": _stage_summary() | _secondary_summary() | _placeholder_summary(),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_payload_audit_path"],
        {
            "status": "owner_approval_payload_blocked",
            "approval_payload_present": False,
            "approval_payload_valid": False,
            "ready_for_approval_gate": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_blocked",
            "stage_allowed": False,
            "summary": {
                "stage_path_digest": STAGE_PATH_DIGEST,
                "stage_command_digest": STAGE_COMMAND_DIGEST,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": "owner_stage_execution_blocked",
            "stage_allowed": False,
            "summary": {
                "stage_path_digest": STAGE_PATH_DIGEST,
                "stage_command_digest": STAGE_COMMAND_DIGEST,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_approval_operator_checklist_path"],
        {
            "status": "owner_post_approval_operator_checklist_waiting_for_owner",
            "owner_gated": True,
            "waiting_for_owner": True,
            "operator_ready": False,
            "real_owner_approval_present": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["closure_snapshot_path"],
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "stage_ready": True,
            "approval_ready": False,
            "blockers": ["owner_stage_approval_gate_not_ready"],
            "summary": _stage_summary() | _secondary_summary(),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["task_board_path"],
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": _stage_summary() | _secondary_summary(),
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_pre_approval_drift_guard_ready_before_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    guard = build_pre_approval_drift_guard(**paths)

    assert guard.status == "pre_approval_drift_guard_ready"
    assert guard.evidence_type == "commercial_delivery_pre_approval_drift_guard"
    assert guard.owner_gated is True
    assert guard.mutation_performed is False
    assert guard.git_stage_performed is False
    assert guard.git_commit_performed is False
    assert guard.git_push_performed is False
    assert guard.network_mutation_performed is False
    assert guard.agent_execution_enabled is False
    assert guard.real_owner_approval_present is False
    assert {check.status for check in guard.checks} == {"passed"}
    assert guard.summary["stage_path_digest"] == STAGE_PATH_DIGEST
    assert guard.summary["stage_command_digest"] == STAGE_COMMAND_DIGEST
    assert guard.summary["expected_stage_path_set_digest"] == EXPECTED_STAGE_PATH_SET_DIGEST
    assert guard.summary["secondary_pending_count"] == 0
    assert guard.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert guard.summary["secondary_handoff_completed_count"] == 44
    assert guard.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert guard.summary["template_identity_placeholders_present"] is True
    assert guard.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert guard.summary["owner_stage_execution_plan_status"] == "owner_stage_execution_blocked"
    assert guard.summary["owner_post_approval_operator_checklist_present"] is True
    assert guard.summary["owner_post_approval_operator_checklist_status"] == (
        "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert guard.summary["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert guard.summary["owner_post_approval_operator_checklist_operator_ready"] is False
    assert guard.summary["owner_post_approval_operator_checklist_real_owner_approval_present"] is False
    assert guard.summary["closure_snapshot_status"] == "commercial_delivery_closure_blocked"
    assert guard.summary["closure_delivery_complete"] is False


def test_pre_approval_drift_guard_allows_missing_optional_operator_checklist(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_post_approval_operator_checklist_path"].unlink()

    guard = build_pre_approval_drift_guard(**paths)

    assert guard.status == "pre_approval_drift_guard_ready"
    assert guard.summary["owner_post_approval_operator_checklist_present"] is False
    assert guard.summary["owner_post_approval_operator_checklist_status"] is None
    assert next(
        check for check in guard.checks if check.name == "operator_checklist_waiting_before_owner"
    ).status == "passed"


def test_pre_approval_drift_guard_blocks_operator_checklist_ready_before_owner(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    checklist["status"] = "owner_post_approval_operator_checklist_ready"
    checklist["waiting_for_owner"] = False
    checklist["operator_ready"] = True
    checklist["real_owner_approval_present"] = True
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(checklist), encoding="utf-8")

    guard = build_pre_approval_drift_guard(**paths)

    assert guard.status == "pre_approval_drift_guard_blocked"
    check = next(check for check in guard.checks if check.name == "operator_checklist_waiting_before_owner")
    assert check.status == "failed"
    assert check.details["operator_checklist_status"] == "owner_post_approval_operator_checklist_ready"
    assert check.details["operator_ready"] is True


def test_pre_approval_drift_guard_blocks_if_owner_approval_payload_exists(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_approval_path"].write_text("{}", encoding="utf-8")

    guard = build_pre_approval_drift_guard(**paths)

    assert guard.status == "pre_approval_drift_guard_blocked"
    check = next(check for check in guard.checks if check.name == "real_owner_approval_absent")
    assert check.status == "failed"
    assert guard.real_owner_approval_present is True


def test_pre_approval_drift_guard_blocks_on_stage_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["summary"]["stage_path_digest"] = "different-digest"
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    guard = build_pre_approval_drift_guard(**paths)

    assert guard.status == "pre_approval_drift_guard_blocked"
    check = next(check for check in guard.checks if check.name == "stage_path_digest_stable")
    assert check.status == "failed"
    assert check.details["stage_path_digest_sources"]["task_board"] == "different-digest"


def test_pre_approval_drift_guard_accepts_task_board_closure_digest_aliases(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["summary"].pop("stage_path_digest")
    payload["summary"].pop("stage_command_digest")
    payload["summary"].pop("expected_stage_path_set_digest")
    payload["summary"]["closure_stage_path_digest"] = STAGE_PATH_DIGEST
    payload["summary"]["closure_stage_command_digest"] = STAGE_COMMAND_DIGEST
    payload["summary"]["closure_expected_stage_path_set_digest"] = EXPECTED_STAGE_PATH_SET_DIGEST
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    guard = build_pre_approval_drift_guard(**paths)

    assert guard.status == "pre_approval_drift_guard_ready"
    assert next(check for check in guard.checks if check.name == "stage_path_digest_stable").status == "passed"


def test_pre_approval_drift_guard_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    guard = build_pre_approval_drift_guard(**paths)
    output = tmp_path / "guard.json"
    markdown = tmp_path / "guard.md"

    write_report(guard, output)
    write_markdown_guard(guard, markdown)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "pre_approval_drift_guard_ready"
    assert payload["checks_count"] == len(guard.checks)
    text = markdown.read_text(encoding="utf-8")
    assert "Commercial Delivery Pre-Approval Drift Guard" in text
    assert "pre_approval_drift_guard_ready" in text
    assert "Owner post-approval operator checklist" in text
    assert render_markdown_guard(guard) == text
