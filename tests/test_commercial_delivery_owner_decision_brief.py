from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_owner_decision_brief import (
    build_owner_decision_brief,
    render_markdown_brief,
    write_markdown_brief,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_reports(reports_dir: Path, *, secondary_pending_count: int = 0) -> dict[str, Path]:
    pending_paths = [
        "backend/app/core/integration_review_answer_action_matrix.py",
        "tests/test_integration_review_answer_action_matrix.py",
    ][:secondary_pending_count]
    manifest = reports_dir / "manifest.json"
    staging_review = reports_dir / "staging-review.json"
    owner_packet = reports_dir / "owner-packet.json"
    owner_preflight = reports_dir / "owner-preflight.json"
    owner_post_staging = reports_dir / "owner-post-staging.json"
    owner_command_audit = reports_dir / "owner-command-audit.json"
    owner_pre_stage_readiness_gate = reports_dir / "owner-pre-stage-readiness-gate.json"
    owner_approval_handoff = reports_dir / "owner-approval-handoff.json"
    owner_approval_resume_packet = reports_dir / "owner-approval-resume-packet.json"
    owner_post_approval_operator_checklist = reports_dir / "owner-post-approval-operator-checklist.json"
    task_board = reports_dir / "task-board.json"

    _write_json(
        manifest,
        {
            "status": "original_kernel_delivery_manifest_ready",
            "stage_include_count": 2,
            "excluded_dirty_paths": [
                {"path": path, "scope": "secondary_pending_candidate"}
                for path in pending_paths
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        staging_review,
        {
            "status": "staging_review_ready",
            "owner_gated": True,
            "eligible_stage_count": 2,
            "blocked_stage_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_packet,
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_commands": [
                "git add -- 'backend/app/core/storage.py'",
                "git add -- 'tests/test_storage.py'",
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_preflight,
        {
            "status": "owner_staging_preflight_ready",
            "owner_gated": True,
            "cached_staged_path_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_post_staging,
        {
            "status": "owner_post_staging_verification_blocked",
            "owner_gated": True,
            "cached_staged_path_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_command_audit,
        {
            "status": "owner_command_audit_ready",
            "owner_gated": True,
            "command_count": 2,
            "expected_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_pre_stage_readiness_gate,
        {
            "status": "owner_pre_stage_readiness_ready",
            "owner_gated": True,
            "summary": {
                "owner_approval_resume_packet_status": "owner_approval_resume_packet_waiting_for_owner",
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_waiting_for_owner"
                ),
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_approval_handoff,
        {
            "status": "owner_approval_handoff_ready",
            "owner_gated": True,
            "owner_action_required": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_approval_resume_packet,
        {
            "status": "owner_approval_resume_packet_waiting_for_owner",
            "owner_gated": True,
            "waiting_for_owner": True,
            "resume_ready": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        owner_post_approval_operator_checklist,
        {
            "status": "owner_post_approval_operator_checklist_waiting_for_owner",
            "owner_gated": True,
            "waiting_for_owner": True,
            "operator_ready": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        task_board,
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": {
                "secondary_pending_count": secondary_pending_count,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "secondary_pending_blocks_owner_staging": False,
            },
            "full_codex_parity_claimed": False,
        },
    )
    return {
        "manifest_path": manifest,
        "staging_review_path": staging_review,
        "owner_packet_path": owner_packet,
        "owner_preflight_path": owner_preflight,
        "owner_post_staging_path": owner_post_staging,
        "owner_command_audit_path": owner_command_audit,
        "owner_pre_stage_readiness_gate_path": owner_pre_stage_readiness_gate,
        "owner_approval_handoff_path": owner_approval_handoff,
        "owner_approval_resume_packet_path": owner_approval_resume_packet,
        "owner_post_approval_operator_checklist_path": owner_post_approval_operator_checklist,
        "task_board_path": task_board,
    }


def test_owner_decision_brief_ready_with_pending_secondary_not_blocking(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, secondary_pending_count=2)

    brief = build_owner_decision_brief(**paths)

    assert brief.status == "ready_for_owner_staging_decision"
    assert brief.evidence_type == "commercial_delivery_owner_decision_brief"
    assert brief.owner_gated is True
    assert brief.mutation_performed is False
    assert brief.git_stage_performed is False
    assert brief.git_commit_performed is False
    assert brief.git_push_performed is False
    assert brief.network_mutation_performed is False
    assert brief.agent_execution_enabled is False
    assert brief.full_codex_parity_claimed is False
    assert brief.summary["stage_include_count"] == 2
    assert brief.summary["owner_stage_command_count"] == 2
    assert brief.summary["owner_command_audit_command_count"] == 2
    assert brief.summary["owner_command_audit_expected_path_count"] == 2
    assert brief.summary["secondary_pending_count"] == 2
    assert brief.summary["secondary_handoff_next_count"] == 1
    assert brief.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert brief.summary["secondary_handoff_completed_count"] == 44
    assert brief.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert brief.summary["owner_command_audit_status"] == "owner_command_audit_ready"
    assert brief.summary["owner_pre_stage_readiness_gate_status"] == "owner_pre_stage_readiness_ready"
    assert brief.summary["owner_approval_handoff_status"] == "owner_approval_handoff_ready"
    assert brief.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert brief.summary["owner_approval_resume_packet_waiting_for_owner"] is True
    assert brief.summary["owner_approval_resume_packet_resume_ready"] is False
    assert brief.summary["owner_post_approval_operator_checklist_status"] == (
        "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert brief.summary["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert brief.summary["owner_post_approval_operator_checklist_operator_ready"] is False
    assert brief.summary["secondary_pending_blocks_owner_staging"] is False
    assert brief.pending_secondary_paths == [
        "backend/app/core/integration_review_answer_action_matrix.py",
        "tests/test_integration_review_answer_action_matrix.py",
    ]
    assert {check.status for check in brief.checks} == {"passed"}


def test_owner_decision_brief_blocks_when_required_report_missing(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    paths["owner_packet_path"].unlink()

    brief = build_owner_decision_brief(**paths)

    assert brief.status == "blocked_before_owner_staging_decision"
    readable = next(check for check in brief.checks if check.name == "reports_readable")
    packet = next(check for check in brief.checks if check.name == "owner_packet_ready")
    assert readable.status == "failed"
    assert packet.status == "failed"


def test_owner_decision_brief_blocks_when_stage_command_count_drifts(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    payload["stage_commands"] = ["git add -- 'backend/app/core/storage.py'"]
    paths["owner_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_decision_brief(**paths)

    assert brief.status == "blocked_before_owner_staging_decision"
    count_check = next(check for check in brief.checks if check.name == "stage_commands_match_manifest")
    assert count_check.status == "failed"


def test_owner_decision_brief_blocks_when_command_audit_count_drifts(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_command_audit_path"].read_text(encoding="utf-8"))
    payload["expected_path_count"] = 1
    paths["owner_command_audit_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_decision_brief(**paths)

    assert brief.status == "blocked_before_owner_staging_decision"
    count_check = next(check for check in brief.checks if check.name == "stage_commands_match_manifest")
    assert count_check.status == "failed"
    assert count_check.details["owner_command_audit_expected_path_count"] == 1


def test_owner_decision_brief_blocks_unknown_owner_boundary(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    packet["status"] = "owner_approval_resume_packet_blocked"
    packet["waiting_for_owner"] = False
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    brief = build_owner_decision_brief(**paths)

    assert brief.status == "blocked_before_owner_staging_decision"
    check = next(check for check in brief.checks if check.name == "owner_approval_boundary_accounted_for")
    assert check.status == "failed"
    assert check.details["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_blocked"


def test_owner_decision_brief_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, secondary_pending_count=1)
    brief = build_owner_decision_brief(**paths)
    json_output = tmp_path / "brief.json"
    md_output = tmp_path / "brief.md"

    write_report(brief, json_output)
    write_markdown_brief(brief, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "ready_for_owner_staging_decision"
    assert "Commercial Delivery Owner Decision Brief" in markdown
    assert "Owner pre-stage readiness gate" in markdown
    assert "integration_review_answer_action_matrix.py" in render_markdown_brief(brief)
