from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.commercial_delivery_owner_approval_handoff import (
    build_owner_approval_handoff,
    render_markdown_handoff,
    write_markdown_handoff,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _commit_preview() -> str:
    return 'git commit -m "chore: prepare X-Agent commercial delivery package"'


def _stage_commands(count: int = 2) -> list[str]:
    return [f"git add -- 'file-{index}.py'" for index in range(count)]


def _stage_paths(count: int = 2) -> list[str]:
    return [f"file-{index}.py" for index in range(count)]


def _stage_path_digest(count: int = 2) -> str:
    return hashlib.sha256(
        json.dumps(_stage_paths(count), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _path_set_digest(count: int = 2) -> str:
    return hashlib.sha256(
        json.dumps(sorted(set(_stage_paths(count))), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _stage_command_digest(count: int = 2) -> str:
    return hashlib.sha256(
        json.dumps(_stage_commands(count), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _approval_template(count: int = 2, command_count: int | None = None) -> dict[str, object]:
    command_count = count if command_count is None else command_count
    return {
        "status": "owner_stage_approval_submitted",
        "decision": "approve_owner_stage",
        "approve_stage": True,
        "owner": "<owner-name-or-id>",
        "approval_id": "<approval-id>",
        "approved_at": "<ISO-8601 UTC timestamp>",
        "rationale": "Owner reviewed the delivery packet and approves explicit staging commands.",
        "stage_include_count": count,
        "owner_stage_command_count": command_count,
        "stage_path_digest": _stage_path_digest(count),
        "stage_command_digest": _stage_command_digest(command_count),
        "expected_stage_path_set_digest": _path_set_digest(count),
        "commit_command_preview": _commit_preview(),
        "acknowledge_pre_stage_verification": True,
        "acknowledge_post_stage_verification": True,
        "acknowledge_no_broad_git_add": True,
        "full_codex_parity_claimed": False,
    }


def _write_inputs(tmp_path: Path, *, count: int = 2, command_count: int | None = None) -> dict[str, Path]:
    command_count = count if command_count is None else command_count
    paths = {
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
        "owner_stage_approval_request_path": tmp_path / "owner-stage-approval-request.json",
        "owner_stage_approval_template_path": tmp_path / "owner-stage-approval.template.json",
        "owner_stage_approval_brief_path": tmp_path / "owner-stage-approval-brief.json",
        "owner_approval_payload_audit_path": tmp_path / "owner-approval-payload-audit.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_stage_execution_plan_path": tmp_path / "owner-stage-execution-plan.json",
        "owner_staging_rollback_plan_path": tmp_path / "owner-staging-rollback-plan.json",
        "owner_post_approval_operator_checklist_path": tmp_path / "owner-post-approval-operator-checklist.json",
        "closure_snapshot_path": tmp_path / "closure-snapshot.json",
        "task_board_path": tmp_path / "task-board.json",
        "owner_approval_path": tmp_path / "owner-stage-approval.json",
    }
    template = _approval_template(count, command_count)
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "owner_gated": True,
            "stage_ready": True,
            "owner_approval_required": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": count,
                "owner_stage_command_count": command_count,
                "rollback_reset_command_count": command_count,
                "commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(count),
                "stage_command_digest": _stage_command_digest(command_count),
                "expected_stage_path_set_digest": _path_set_digest(count),
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_modes_surface_file_count": 12,
            },
            "sections": [
                {
                    "name": "owner_stage_commands",
                    "commands": _stage_commands(command_count),
                }
            ],
        },
    )
    _write_json(
        paths["owner_stage_approval_request_path"],
        {
            "status": "owner_stage_approval_request_ready",
            "owner_gated": True,
            "approval_payload_path": str(paths["owner_approval_path"]),
            "template_output_path": str(paths["owner_stage_approval_template_path"]),
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": count,
                "owner_stage_command_count": command_count,
                "commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(count),
                "stage_command_digest": _stage_command_digest(command_count),
                "expected_stage_path_set_digest": _path_set_digest(count),
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
            },
            "suggested_owner_approval_payload": template,
        },
    )
    _write_json(paths["owner_stage_approval_template_path"], template)
    _write_json(
        paths["owner_stage_approval_brief_path"],
        {
            "status": "owner_stage_approval_brief_ready",
            "owner_gated": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": count,
                "owner_stage_command_count": command_count,
                "commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(count),
                "stage_command_digest": _stage_command_digest(command_count),
                "expected_stage_path_set_digest": _path_set_digest(count),
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
            },
            "owner_action_payload_template": template,
        },
    )
    _write_json(
        paths["owner_approval_payload_audit_path"],
        {
            "status": "owner_approval_payload_blocked",
            "owner_gated": True,
            "approval_payload_present": False,
            "approval_payload_valid": False,
            "ready_for_approval_gate": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": count,
                "owner_stage_command_count": command_count,
                "commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(count),
                "stage_command_digest": _stage_command_digest(command_count),
                "expected_stage_path_set_digest": _path_set_digest(count),
            },
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_blocked",
            "owner_gated": True,
            "stage_allowed": False,
            "full_codex_parity_claimed": False,
            "summary": {"stage_include_count": count, "owner_stage_command_count": command_count},
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": "owner_stage_execution_blocked",
            "owner_gated": True,
            "stage_allowed": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_command_count": command_count,
                "delivery_stage_include_count": count,
                "approval_stage_include_count": count,
            },
        },
    )
    _write_json(
        paths["owner_staging_rollback_plan_path"],
        {
            "status": "owner_staging_rollback_plan_ready",
            "owner_gated": True,
            "rollback_available": True,
            "rollback_required": False,
            "reset_command_count": command_count,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_approval_operator_checklist_path"],
        {
            "status": "owner_post_approval_operator_checklist_waiting_for_owner",
            "owner_gated": True,
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "real_owner_approval_present": False,
            "waiting_for_owner": True,
            "operator_ready": False,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": count,
                "stage_command_count": command_count,
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_waiting_for_owner",
            },
        },
    )
    _write_json(
        paths["closure_snapshot_path"],
        {
            "status": "commercial_delivery_closure_blocked",
            "delivery_complete": False,
            "full_codex_parity_claimed": False,
            "blockers": [
                "owner_stage_approval_gate_not_ready",
                "owner_stage_execution_plan_not_ready",
                "post_staging_verifier_not_ready",
                "owner_commit_packet_not_ready",
            ],
            "summary": {
                "stage_include_count": count,
                "owner_stage_command_count": command_count,
                "rollback_reset_command_count": command_count,
                "expected_stage_path_set_digest": _path_set_digest(count),
                "cached_staged_path_set_digest": None,
            },
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
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_approval_handoff_ready_before_real_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_ready"
    assert handoff.evidence_type == "commercial_delivery_owner_approval_handoff"
    assert handoff.owner_gated is True
    assert handoff.mutation_performed is False
    assert handoff.git_stage_performed is False
    assert handoff.git_commit_performed is False
    assert handoff.git_push_performed is False
    assert handoff.network_mutation_performed is False
    assert handoff.agent_execution_enabled is False
    assert handoff.real_owner_approval_written is False
    assert handoff.full_codex_parity_claimed is False
    assert handoff.approval_payload_audit_path.endswith("owner-approval-payload-audit.json")
    assert handoff.owner_action_required is True
    assert handoff.stage_allowed is False
    assert handoff.delivery_complete is False
    assert handoff.summary["stage_include_count"] == 2
    assert handoff.summary["owner_stage_command_count"] == 2
    assert handoff.summary["rollback_reset_command_count"] == 2
    assert handoff.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert handoff.summary["secondary_handoff_completed_count"] == 44
    assert handoff.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert handoff.summary["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert handoff.summary["control_modes_plan_only_default"] is True
    assert handoff.summary["control_modes_loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert handoff.summary["control_modes_surface_file_count"] == 12
    assert handoff.summary["brief_control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert handoff.summary["brief_control_modes_plan_only_default"] is True
    assert handoff.summary["closure_snapshot_status"] == "commercial_delivery_closure_blocked"
    assert handoff.summary["owner_approval_payload_audit_status"] == "owner_approval_payload_blocked"
    assert handoff.summary["owner_approval_payload_present"] is False
    assert handoff.summary["owner_approval_payload_valid"] is False
    assert handoff.summary["owner_approval_payload_ready_for_gate"] is False
    assert handoff.report_statuses["owner_post_approval_operator_checklist"] == (
        "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert handoff.summary["owner_post_approval_operator_checklist_present"] is True
    assert handoff.summary["owner_post_approval_operator_checklist_status"] == (
        "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert handoff.summary["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert handoff.summary["owner_post_approval_operator_checklist_operator_ready"] is False
    assert handoff.summary["owner_post_approval_operator_checklist_real_owner_approval_present"] is False
    assert handoff.summary["template_identity_placeholders_present"] is True
    assert handoff.summary["template_owner_placeholder"] == "<owner-name-or-id>"
    assert handoff.summary["template_approval_id_placeholder"] == "<approval-id>"
    assert handoff.summary["template_approved_at_placeholder"] == "<ISO-8601 UTC timestamp>"
    assert handoff.summary["stage_path_digest"] == _stage_path_digest()
    assert handoff.summary["template_stage_path_digest"] == _stage_path_digest()
    assert handoff.summary["request_stage_path_digest"] == _stage_path_digest()
    assert handoff.summary["brief_stage_path_digest"] == _stage_path_digest()
    assert handoff.summary["expected_stage_path_set_digest"] == _path_set_digest()
    assert handoff.summary["template_expected_stage_path_set_digest"] == _path_set_digest()
    assert handoff.summary["request_expected_stage_path_set_digest"] == _path_set_digest()
    assert handoff.summary["brief_expected_stage_path_set_digest"] == _path_set_digest()
    assert handoff.summary["closure_expected_stage_path_set_digest"] == _path_set_digest()
    assert handoff.summary["closure_cached_staged_path_set_digest"] is None
    assert handoff.summary["approval_payload_audit_stage_path_digest"] == _stage_path_digest()
    assert handoff.summary["approval_payload_audit_stage_command_digest"] == _stage_command_digest()
    assert handoff.summary["approval_payload_audit_expected_stage_path_set_digest"] == _path_set_digest()
    assert handoff.owner_action_payload_template["decision"] == "approve_owner_stage"
    assert handoff.owner_action_payload_template["expected_stage_path_set_digest"] == _path_set_digest()
    assert {check.status for check in handoff.checks} == {"passed"}


def test_owner_approval_handoff_allows_subset_owner_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, count=3, command_count=2)

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_ready"
    assert handoff.summary["stage_include_count"] == 3
    assert handoff.summary["owner_stage_command_count"] == 2
    assert handoff.summary["rollback_reset_command_count"] == 2
    assert handoff.summary["approval_template_stage_include_count"] == 3
    assert handoff.summary["approval_template_owner_stage_command_count"] == 2
    assert handoff.summary["approval_request_stage_include_count"] == 3
    assert handoff.summary["approval_request_owner_stage_command_count"] == 2
    assert handoff.summary["approval_brief_stage_include_count"] == 3
    assert handoff.summary["approval_brief_owner_stage_command_count"] == 2
    assert handoff.summary["closure_snapshot_stage_include_count"] == 3
    assert handoff.summary["closure_snapshot_owner_stage_command_count"] == 2
    counts_check = next(check for check in handoff.checks if check.name == "current_counts_match")
    assert counts_check.status == "passed"
    assert counts_check.details["stage_coverage_counts_match"] is True
    assert counts_check.details["owner_command_counts_match"] is True
    assert counts_check.details["owner_command_count_within_stage_coverage"] is True
    assert handoff.summary["stage_path_digest"] == _stage_path_digest(3)
    assert handoff.summary["stage_command_digest"] == _stage_command_digest(2)
    assert handoff.owner_action_payload_template["stage_include_count"] == 3
    assert handoff.owner_action_payload_template["owner_stage_command_count"] == 2


def test_owner_approval_handoff_allows_missing_optional_operator_checklist(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_post_approval_operator_checklist_path"].unlink()

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_ready"
    assert handoff.summary["owner_post_approval_operator_checklist_present"] is False
    assert handoff.summary["owner_post_approval_operator_checklist_status"] is None
    assert handoff.report_statuses["owner_post_approval_operator_checklist"] is None
    assert next(check for check in handoff.checks if check.name == "operator_checklist_accounted_for").status == "passed"


def test_owner_approval_handoff_blocks_operator_checklist_unaccounted_status(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    checklist["status"] = "owner_post_approval_operator_checklist_blocked"
    checklist["waiting_for_owner"] = False
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(checklist), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    check = next(check for check in handoff.checks if check.name == "operator_checklist_accounted_for")
    assert check.status == "failed"
    assert check.details["operator_checklist_status"] == "owner_post_approval_operator_checklist_blocked"


def test_owner_approval_handoff_blocks_operator_checklist_without_owner_gate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    checklist["owner_gated"] = False
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(checklist), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    check = next(check for check in handoff.checks if check.name == "owner_gate_present")
    assert check.status == "failed"
    assert check.details["operator_checklist_owner_gated"] is False


def test_owner_approval_handoff_blocks_count_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_stage_approval_template_path"].read_text(encoding="utf-8"))
    payload["stage_include_count"] = 3
    paths["owner_stage_approval_template_path"].write_text(json.dumps(payload), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(check for check in handoff.checks if check.name == "current_counts_match").status == "failed"
    assert next(
        check for check in handoff.checks if check.name == "approval_template_matches_delivery_packet"
    ).status == "failed"


def test_owner_approval_handoff_blocks_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_stage_approval_request_path"].read_text(encoding="utf-8"))
    payload["summary"]["stage_path_digest"] = "0" * 64
    paths["owner_stage_approval_request_path"].write_text(json.dumps(payload), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(
        check for check in handoff.checks if check.name == "approval_request_and_brief_digests_match_delivery_packet"
    ).status == "failed"


def test_owner_approval_handoff_blocks_template_identity_values(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    template = json.loads(paths["owner_stage_approval_template_path"].read_text(encoding="utf-8"))
    template["owner"] = "delivery-owner"
    template["approval_id"] = "approval-2026-06-10-001"
    template["approved_at"] = "2026-06-10T10:00:00Z"
    paths["owner_stage_approval_template_path"].write_text(json.dumps(template), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert handoff.summary["template_identity_placeholders_present"] is False
    check = next(
        check for check in handoff.checks if check.name == "approval_template_identity_placeholders_present"
    )
    assert check.status == "failed"
    assert check.details["template_owner"] == "delivery-owner"


def test_owner_approval_handoff_blocks_approval_payload_audit_not_pre_approval_blocked(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    audit = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    audit["status"] = "owner_approval_payload_ready"
    audit["approval_payload_present"] = True
    audit["approval_payload_valid"] = True
    audit["ready_for_approval_gate"] = True
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(audit), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(
        check for check in handoff.checks if check.name == "approval_payload_audit_pre_approval_blocked"
    ).status == "failed"


def test_owner_approval_handoff_blocks_approval_payload_audit_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    audit = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    audit["summary"]["expected_stage_path_set_digest"] = "0" * 64
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(audit), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(
        check for check in handoff.checks if check.name == "approval_payload_audit_digest_context_matches_delivery_packet"
    ).status == "failed"


def test_owner_approval_handoff_blocks_expected_path_set_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["closure_snapshot_path"].read_text(encoding="utf-8"))
    payload["summary"]["expected_stage_path_set_digest"] = "0" * 64
    paths["closure_snapshot_path"].write_text(json.dumps(payload), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(
        check for check in handoff.checks if check.name == "closure_expected_stage_path_set_digest_matches_delivery_packet"
    ).status == "failed"


def test_owner_approval_handoff_blocks_template_written_to_real_approval_path(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_stage_approval_template_path"] = paths["owner_approval_path"]
    _write_json(paths["owner_approval_path"], _approval_template())

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(check for check in handoff.checks if check.name == "template_path_is_not_real_approval").status == "failed"
    assert next(
        check for check in handoff.checks if check.name == "real_owner_approval_not_written_by_handoff"
    ).status == "failed"


def test_owner_approval_handoff_blocks_missing_closure_blockers(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["closure_snapshot_path"].read_text(encoding="utf-8"))
    payload["blockers"] = ["owner_stage_approval_gate_not_ready"]
    paths["closure_snapshot_path"].write_text(json.dumps(payload), encoding="utf-8")

    handoff = build_owner_approval_handoff(**paths)

    assert handoff.status == "owner_approval_handoff_blocked"
    assert next(check for check in handoff.checks if check.name == "pre_approval_blockers_accounted_for").status == "failed"


def test_owner_approval_handoff_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    handoff = build_owner_approval_handoff(**paths)
    output = tmp_path / "handoff.json"
    markdown_output = tmp_path / "handoff.md"

    write_report(handoff, output)
    write_markdown_handoff(handoff, markdown_output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_approval_handoff_ready"
    assert "Commercial Delivery Owner Approval Handoff" in markdown
    assert "Owner approval payload audit status" in markdown
    assert "Owner post-approval operator checklist status" in markdown
    assert "Expected stage path set digest" in markdown
    assert "approve_owner_stage" in render_markdown_handoff(handoff)
