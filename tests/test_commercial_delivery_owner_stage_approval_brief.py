from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.commercial_delivery_owner_stage_approval_brief import (
    build_owner_stage_approval_brief,
    render_markdown_brief,
    write_markdown_brief,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_commands() -> list[str]:
    return ["git add -- 'backend/app/core/storage.py'", "git add -- 'tests/test_storage.py'"]


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _stage_path_digest() -> str:
    return hashlib.sha256(
        json.dumps(_stage_paths(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _path_set_digest() -> str:
    return hashlib.sha256(
        json.dumps(sorted(set(_stage_paths())), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _stage_command_digest() -> str:
    return hashlib.sha256(
        json.dumps(_stage_commands(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_inputs(tmp_path: Path, *, approved: bool = False) -> dict[str, Path]:
    paths = {
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
        "owner_stage_approval_request_path": tmp_path / "owner-stage-approval-request.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_stage_execution_plan_path": tmp_path / "owner-stage-execution-plan.json",
        "refresh_chain_path": tmp_path / "refresh-chain.json",
        "task_board_path": tmp_path / "task-board.json",
    }
    gate_status = "owner_stage_approval_ready" if approved else "owner_stage_approval_blocked"
    execution_status = "owner_stage_execution_ready" if approved else "owner_stage_execution_blocked"
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "owner_gated": True,
            "stage_ready": True,
            "owner_approval_required": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "stage_path_digest": _stage_path_digest(),
                "stage_command_digest": _stage_command_digest(),
                "expected_stage_path_set_digest": _path_set_digest(),
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
            "sections": [
                {
                    "name": "owner_stage_commands",
                    "commands": _stage_commands(),
                }
            ],
        },
    )
    _write_json(
        paths["owner_stage_approval_request_path"],
        {
            "status": "owner_stage_approval_request_ready",
            "owner_gated": True,
            "approval_payload_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.json",
            "template_output_path": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.template.json",
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "stage_path_digest": _stage_path_digest(),
                "stage_command_digest": _stage_command_digest(),
                "expected_stage_path_set_digest": _path_set_digest(),
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
            },
            "suggested_owner_approval_payload": {
                "decision": "approve_owner_stage",
                "approve_stage": True,
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "stage_path_digest": _stage_path_digest(),
                "stage_command_digest": _stage_command_digest(),
                "expected_stage_path_set_digest": _path_set_digest(),
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
            },
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": gate_status,
            "owner_gated": True,
            "stage_allowed": approved,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": execution_status,
            "owner_gated": True,
            "stage_allowed": approved,
            "stage_ready": True,
            "stage_command_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["refresh_chain_path"],
        {
            "status": "commercial_delivery_refresh_chain_receipt_ready",
            "summary": {"expected_nonzero_steps": ["owner_stage_approval_gate"]},
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
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_stage_approval_brief_ready_before_real_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_ready"
    assert brief.evidence_type == "commercial_delivery_owner_stage_approval_brief"
    assert brief.owner_gated is True
    assert brief.mutation_performed is False
    assert brief.git_stage_performed is False
    assert brief.git_commit_performed is False
    assert brief.git_push_performed is False
    assert brief.network_mutation_performed is False
    assert brief.agent_execution_enabled is False
    assert brief.real_owner_approval_written is False
    assert brief.full_codex_parity_claimed is False
    assert brief.approval_ready is False
    assert brief.approval_required is True
    assert brief.stage_allowed is False
    assert brief.stage_execution_ready is False
    assert brief.summary["stage_include_count"] == 2
    assert brief.summary["stage_path_digest"] == _stage_path_digest()
    assert brief.summary["request_stage_path_digest"] == _stage_path_digest()
    assert brief.summary["expected_stage_path_set_digest"] == _path_set_digest()
    assert brief.summary["request_expected_stage_path_set_digest"] == _path_set_digest()
    assert brief.summary["template_expected_stage_path_set_digest"] == _path_set_digest()
    assert brief.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert brief.summary["owner_stage_execution_plan_status"] == "owner_stage_execution_blocked"
    assert brief.summary["secondary_handoff_completed_count"] == 44
    assert brief.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert brief.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert brief.summary["request_secondary_handoff_completed_count"] == 44
    assert (
        brief.summary["request_secondary_handoff_latest_completed_candidate"]
        == "integration_review_answer_action_matrix.py"
    )
    assert brief.summary["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert brief.summary["control_modes_plan_only_default"] is True
    assert brief.summary["control_modes_loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert brief.summary["control_modes_surface_file_count"] == 12
    assert brief.owner_action_payload_template["decision"] == "approve_owner_stage"
    assert brief.owner_action_payload_template["stage_path_digest"] == _stage_path_digest()
    assert brief.owner_action_payload_template["stage_command_digest"] == _stage_command_digest()
    assert brief.owner_action_payload_template["expected_stage_path_set_digest"] == _path_set_digest()
    assert {check.status for check in brief.checks} == {"passed"}


def test_owner_stage_approval_brief_accepts_refresh_self_bootstrap(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [{"name": "owner_stage_approval_brief", "status": "failed"}]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_ready"
    check = next(check for check in brief.checks if check.name == "refresh_chain_ready")
    assert check.status == "passed"
    assert check.details["failed_steps"] == ["owner_stage_approval_brief"]


def test_owner_stage_approval_brief_blocks_unrelated_failed_refresh_receipt(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [{"name": "owner_command_audit", "status": "failed"}]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_blocked"
    assert next(check for check in brief.checks if check.name == "refresh_chain_ready").status == "failed"


def test_owner_stage_approval_brief_ready_after_real_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_ready"
    assert brief.approval_ready is True
    assert brief.stage_allowed is True
    assert brief.stage_execution_ready is True
    assert brief.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_ready"


def test_owner_stage_approval_brief_blocks_count_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_stage_approval_request_path"].read_text(encoding="utf-8"))
    payload["summary"]["owner_stage_command_count"] = 3
    paths["owner_stage_approval_request_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_blocked"
    assert next(
        check for check in brief.checks if check.name == "approval_request_counts_match_delivery_packet"
    ).status == "failed"


def test_owner_stage_approval_brief_blocks_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_stage_approval_request_path"].read_text(encoding="utf-8"))
    payload["summary"]["stage_path_digest"] = "0" * 64
    payload["suggested_owner_approval_payload"]["stage_path_digest"] = "0" * 64
    paths["owner_stage_approval_request_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_blocked"
    assert next(
        check for check in brief.checks if check.name == "approval_request_digests_match_delivery_packet"
    ).status == "failed"


def test_owner_stage_approval_brief_blocks_expected_path_set_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_stage_approval_request_path"].read_text(encoding="utf-8"))
    payload["summary"]["expected_stage_path_set_digest"] = "0" * 64
    payload["suggested_owner_approval_payload"]["expected_stage_path_set_digest"] = "0" * 64
    paths["owner_stage_approval_request_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_blocked"
    assert next(
        check for check in brief.checks if check.name == "approval_request_digests_match_delivery_packet"
    ).status == "failed"


def test_owner_stage_approval_brief_blocks_unknown_execution_plan(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_stage_execution_plan_path"].read_text(encoding="utf-8"))
    payload["status"] = "owner_stage_execution_unknown"
    paths["owner_stage_execution_plan_path"].write_text(json.dumps(payload), encoding="utf-8")

    brief = build_owner_stage_approval_brief(**paths)

    assert brief.status == "owner_stage_approval_brief_blocked"
    assert next(
        check for check in brief.checks if check.name == "owner_stage_execution_plan_accounted_for"
    ).status == "failed"


def test_owner_stage_approval_brief_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    brief = build_owner_stage_approval_brief(**paths)
    json_output = tmp_path / "brief.json"
    md_output = tmp_path / "brief.md"

    write_report(brief, json_output)
    write_markdown_brief(brief, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_stage_approval_brief_ready"
    assert "Commercial Delivery Owner Stage Approval Brief" in markdown
    assert "approve_owner_stage" in render_markdown_brief(brief)
