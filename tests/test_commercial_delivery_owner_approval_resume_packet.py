from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_approval_resume_packet import (
    build_owner_approval_resume_packet,
    render_markdown_packet,
    write_markdown_packet,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _update_json(path: Path, **updates: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
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


def _write_inputs(tmp_path: Path, *, approved: bool = False) -> dict[str, Path]:
    paths = {
        "owner_approval_handoff_path": tmp_path / "owner-approval-handoff.json",
        "pre_approval_drift_guard_path": tmp_path / "pre-approval-drift-guard.json",
        "owner_approval_payload_audit_path": tmp_path / "owner-approval-payload-audit.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_stage_execution_plan_path": tmp_path / "owner-stage-execution-plan.json",
        "owner_staging_runbook_path": tmp_path / "owner-staging-runbook.json",
        "owner_staging_rollback_plan_path": tmp_path / "owner-staging-rollback-plan.json",
        "owner_post_staging_verifier_path": tmp_path / "owner-post-staging-verifier.json",
        "owner_post_stage_commit_gate_path": tmp_path / "owner-post-stage-commit-gate.json",
        "owner_commit_packet_path": tmp_path / "owner-commit-packet.json",
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
        "task_board_path": tmp_path / "task-board.json",
        "owner_approval_path": tmp_path / "owner-stage-approval.json",
    }
    stage_path_digest = _digest_values(_stage_paths())
    stage_command_digest = _digest_values(_stage_commands())
    expected_stage_path_set_digest = _path_set_digest(_stage_paths())
    secondary_summary = {
        "secondary_pending_count": 0,
        "secondary_handoff_next_count": 1,
        "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
        "secondary_handoff_completed_count": 44,
        "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
    }
    common_summary = {
        "stage_include_count": 2,
        "owner_stage_command_count": 2,
        "stage_path_digest": stage_path_digest,
        "stage_command_digest": stage_command_digest,
        "expected_stage_path_set_digest": expected_stage_path_set_digest,
        **secondary_summary,
    }
    _write_json(
        paths["owner_approval_handoff_path"],
        {
            "status": "owner_approval_handoff_ready",
            "owner_gated": True,
            "summary": common_summary,
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
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                **secondary_summary,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_payload_audit_path"],
        {
            "status": "owner_approval_payload_ready" if approved else "owner_approval_payload_blocked",
            "approval_payload_present": approved,
            "approval_payload_valid": approved,
            "ready_for_approval_gate": approved,
            "summary": {"blocking_reasons": [] if approved else ["owner_approval_payload_readable"]},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_ready" if approved else "owner_stage_approval_blocked",
            "owner_gated": True,
            "stage_allowed": approved,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "blocking_reasons": [] if approved else ["owner_approval_readable"],
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": "owner_stage_execution_ready" if approved else "owner_stage_execution_blocked",
            "owner_gated": True,
            "stage_allowed": approved,
            "stage_ready": True,
            "stage_command_count": 2,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "planned_stage_commands": _stage_commands() if approved else [],
            "summary": {
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "blocking_reasons": [] if approved else ["approval_gate_ready"],
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_runbook_path"],
        {
            "status": "owner_staging_runbook_ready",
            "owner_gated": True,
            "summary": {
                "stage_command_count": 2,
                "commit_command_preview": "git commit -m test",
                **secondary_summary,
            },
            "sections": [
                {
                    "name": "pre_stage_verification",
                    "commands": ["python scripts\\commercial_delivery_owner_staging_preflight.py"],
                },
                {"name": "owner_stage_commands", "commands": _stage_commands()},
                {
                    "name": "post_stage_verification",
                    "commands": ["python scripts\\commercial_delivery_owner_post_staging_verifier.py"],
                },
            ],
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
            "status": "owner_post_staging_verification_blocked",
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "summary": {"blocking_reasons": ["cached_paths_present_after_owner_staging"], **secondary_summary},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_blocked",
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "summary": {"blocking_reasons": ["owner_post_staging_verification_ready"], **secondary_summary},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {
            "status": "owner_commit_packet_blocked",
            "commit_allowed": False,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "summary": {"blocking_reasons": ["owner_post_stage_commit_gate_ready"], **secondary_summary},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "owner_gated": True,
            "stage_ready": True,
            "summary": {
                **common_summary,
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "commit_command_preview": "git commit -m test",
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["task_board_path"],
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": secondary_summary,
            "full_codex_parity_claimed": False,
        },
    )
    if approved:
        _write_json(
            paths["owner_approval_path"],
            {
                "status": "owner_stage_approval_payload",
                "decision": "approve_owner_stage",
                "approve_stage": True,
            },
        )
    return paths


def test_resume_packet_waits_for_owner_without_mutation(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_waiting_for_owner"
    assert packet.waiting_for_owner is True
    assert packet.resume_ready is False
    assert packet.real_owner_approval_present is False
    assert packet.real_owner_approval_written is False
    assert packet.mutation_performed is False
    assert packet.git_stage_performed is False
    assert packet.git_commit_performed is False
    assert packet.git_push_performed is False
    assert packet.network_mutation_performed is False
    assert packet.agent_execution_enabled is False
    assert packet.stage_allowed is False
    assert packet.stage_execution_ready is False
    assert {check.status for check in packet.checks} == {"passed"}
    assert packet.summary["owner_action_required"] is True
    assert packet.summary["stage_include_count"] == 2
    assert packet.summary["secondary_handoff_completed_count"] == 44
    assert packet.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    stage_group = next(group for group in packet.command_groups if group.name == "owner_stage_commands")
    assert stage_group.executable_now is False
    assert stage_group.commands == _stage_commands()
    approval_group = next(group for group in packet.command_groups if group.name == "owner_create_approval_payload")
    assert approval_group.executable_now is True


def test_resume_packet_ready_after_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_ready"
    assert packet.waiting_for_owner is False
    assert packet.resume_ready is True
    assert packet.real_owner_approval_present is True
    assert packet.stage_allowed is True
    assert packet.stage_execution_ready is True
    assert {check.status for check in packet.checks} == {"passed"}
    assert packet.summary["owner_action_required"] is False
    assert packet.summary["planned_stage_commands_count"] == 2
    stage_group = next(group for group in packet.command_groups if group.name == "owner_stage_commands")
    assert stage_group.executable_now is True
    assert stage_group.commands == _stage_commands()
    preflight_group = next(group for group in packet.command_groups if group.name == "pre_stage_verification")
    assert preflight_group.executable_now is True


def test_resume_packet_accounts_for_post_stage_superseded_handoff_and_runbook(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    _update_json(paths["owner_approval_handoff_path"], status="owner_approval_handoff_blocked")
    _update_json(paths["owner_staging_runbook_path"], status="owner_staging_runbook_blocked")
    _update_json(
        paths["owner_post_staging_verifier_path"],
        status="owner_post_staging_verification_ready",
    )
    _update_json(paths["owner_post_stage_commit_gate_path"], status="owner_post_stage_commit_gate_ready")
    _update_json(paths["owner_commit_packet_path"], status="owner_commit_packet_ready", commit_allowed=True)

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_ready"
    assert packet.resume_ready is True
    assert {check.status for check in packet.checks} == {"passed"}
    assert packet.report_statuses["owner_approval_handoff"] == "owner_approval_handoff_blocked"
    assert packet.report_statuses["owner_staging_runbook"] == "owner_staging_runbook_blocked"
    assert packet.summary["owner_approval_handoff_post_stage_accounted_for"] is True
    assert packet.summary["owner_staging_runbook_post_stage_accounted_for"] is True
    handoff_check = next(check for check in packet.checks if check.name == "owner_approval_handoff_ready")
    runbook_check = next(check for check in packet.checks if check.name == "owner_staging_runbook_ready")
    assert handoff_check.details["post_stage_accounted_for"] is True
    assert runbook_check.details["post_stage_accounted_for"] is True


def test_resume_packet_accepts_subset_stage_commands_after_post_stage_evidence(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    _update_json(
        paths["owner_approval_handoff_path"],
        status="owner_approval_handoff_blocked",
        summary={
            "stage_include_count": 100,
            "owner_stage_command_count": 8,
            "stage_path_digest": _digest_values(_stage_paths()),
            "stage_command_digest": _digest_values(_stage_commands()),
            "expected_stage_path_set_digest": _path_set_digest(_stage_paths()),
        },
    )
    _update_json(paths["owner_staging_runbook_path"], status="owner_staging_runbook_blocked", summary={"stage_command_count": 8})
    _update_json(paths["owner_stage_execution_plan_path"], stage_command_count=8)
    _update_json(
        paths["owner_delivery_packet_path"],
        summary={
            "stage_include_count": 100,
            "owner_stage_command_count": 8,
            "stage_path_digest": _digest_values(_stage_paths()),
            "stage_command_digest": _digest_values(_stage_commands()),
            "expected_stage_path_set_digest": _path_set_digest(_stage_paths()),
            "control_modes_preservation_status": "control_modes_preservation_ready",
            "control_modes_plan_only_default": True,
            "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            "commit_command_preview": "git commit -m test",
        },
    )
    _update_json(
        paths["owner_post_staging_verifier_path"],
        status="owner_post_staging_verification_ready",
        stage_path_digest=_digest_values(_stage_paths()),
        stage_command_digest=_digest_values(_stage_commands()),
        expected_stage_path_set_digest=_path_set_digest(_stage_paths()),
    )
    _update_json(paths["owner_post_stage_commit_gate_path"], status="owner_post_stage_commit_gate_ready")
    _update_json(paths["owner_commit_packet_path"], status="owner_commit_packet_ready", commit_allowed=True)

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_ready"
    assert packet.resume_ready is True
    assert next(check for check in packet.checks if check.name == "stage_counts_consistent").status == "passed"
    assert packet.summary["stage_include_count"] == 100
    assert packet.summary["owner_stage_command_count"] == 8
    assert packet.summary["runbook_stage_command_count"] == 8
    assert packet.summary["execution_plan_stage_command_count"] == 8


def test_resume_packet_keeps_blocked_superseded_inputs_without_post_stage_evidence(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    _update_json(paths["owner_approval_handoff_path"], status="owner_approval_handoff_blocked")
    _update_json(paths["owner_staging_runbook_path"], status="owner_staging_runbook_blocked")

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_blocked"
    assert packet.resume_ready is False
    assert "owner_approval_handoff_ready" in packet.summary["blocking_reasons"]
    assert "owner_staging_runbook_ready" in packet.summary["blocking_reasons"]
    assert packet.summary["owner_approval_handoff_post_stage_accounted_for"] is False
    assert packet.summary["owner_staging_runbook_post_stage_accounted_for"] is False


def test_resume_packet_blocks_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_commit_packet_path"].read_text(encoding="utf-8"))
    payload["stage_command_digest"] = "1" * 64
    paths["owner_commit_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_blocked"
    assert next(check for check in packet.checks if check.name == "stage_command_digest_consistent").status == "failed"
    assert "stage_command_digest_consistent" in packet.summary["blocking_reasons"]


def test_resume_packet_accepts_post_commit_noop_without_reopening_owner_gates(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    empty_digest = _digest_values([])
    for key in ("owner_approval_handoff_path", "owner_staging_runbook_path"):
        _update_json(
            paths[key],
            status="owner_approval_handoff_blocked" if key == "owner_approval_handoff_path" else "owner_staging_runbook_blocked",
            summary={
                "stage_include_count": 100,
                "owner_stage_command_count": 0,
                "stage_command_count": 0,
                "stage_path_digest": empty_digest,
                "stage_command_digest": empty_digest,
                "expected_stage_path_set_digest": empty_digest,
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
            },
        )
    _update_json(
        paths["pre_approval_drift_guard_path"],
        status="pre_approval_drift_guard_blocked",
        real_owner_approval_present=True,
        summary={
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
            "secondary_pending_count": 0,
            "secondary_handoff_next_count": 1,
            "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
            "secondary_handoff_completed_count": 44,
            "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
        },
    )
    _update_json(
        paths["owner_approval_payload_audit_path"],
        status="owner_approval_payload_blocked",
        approval_payload_present=True,
        approval_payload_valid=False,
        ready_for_approval_gate=False,
    )
    _update_json(
        paths["owner_stage_approval_gate_path"],
        status="owner_stage_approval_blocked",
        stage_allowed=False,
        summary={
            "stage_include_count": 100,
            "owner_stage_command_count": 0,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
        },
    )
    _update_json(
        paths["owner_stage_execution_plan_path"],
        status="owner_stage_execution_blocked",
        stage_allowed=False,
        stage_command_count=0,
        stage_path_digest=empty_digest,
        stage_command_digest=empty_digest,
        planned_stage_commands=[],
        summary={"expected_stage_path_set_digest": empty_digest},
    )
    _update_json(
        paths["owner_delivery_packet_path"],
        summary={
            "stage_include_count": 100,
            "owner_stage_command_count": 0,
            "post_commit_noop_accounted_for": True,
            "stage_path_digest": empty_digest,
            "stage_command_digest": empty_digest,
            "expected_stage_path_set_digest": empty_digest,
            "control_modes_preservation_status": "control_modes_preservation_ready",
            "control_modes_plan_only_default": True,
            "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            "commit_command_preview": "git commit -m test",
        },
    )
    _update_json(
        paths["owner_post_staging_verifier_path"],
        status="owner_post_staging_verification_ready",
        stage_path_digest=empty_digest,
        stage_command_digest=empty_digest,
        expected_stage_path_set_digest=empty_digest,
    )
    _update_json(
        paths["owner_post_stage_commit_gate_path"],
        status="owner_post_stage_commit_gate_ready",
        stage_path_digest=empty_digest,
        stage_command_digest=empty_digest,
        expected_stage_path_set_digest=empty_digest,
    )
    _update_json(
        paths["owner_commit_packet_path"],
        status="owner_commit_packet_ready",
        commit_allowed=True,
        stage_path_digest=empty_digest,
        stage_command_digest=empty_digest,
        expected_stage_path_set_digest=empty_digest,
    )
    _update_json(paths["task_board_path"], status="commercial_delivery_blocked", summary={
        "secondary_pending_count": 0,
        "owner_commit_packet_status": "owner_commit_packet_ready",
        "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_ready",
    })

    packet = build_owner_approval_resume_packet(**paths)

    assert packet.status == "owner_approval_resume_packet_ready"
    assert packet.resume_ready is True
    assert packet.stage_allowed is False
    assert packet.stage_execution_ready is False
    assert packet.summary["post_commit_noop_resume_ready"] is True
    assert packet.summary["task_board_post_commit_accounted_for"] is True
    assert next(check for check in packet.checks if check.name == "stage_counts_consistent").status == "passed"


def test_resume_packet_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    packet = build_owner_approval_resume_packet(**paths)
    json_output = tmp_path / "packet.json"
    md_output = tmp_path / "packet.md"

    write_report(packet, json_output)
    write_markdown_packet(packet, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert payload["checks_count"] == len(payload["checks"])
    assert payload["command_groups_count"] == len(payload["command_groups"])
    assert payload["next_actions_count"] == len(payload["next_actions"])
    assert payload["known_limits_count"] == len(payload["known_limits"])
    assert "Commercial Delivery Owner Approval Resume Packet" in markdown
    assert "owner_stage_commands" in render_markdown_packet(packet)
    assert "integration_review_answer_action_matrix.py" in markdown
