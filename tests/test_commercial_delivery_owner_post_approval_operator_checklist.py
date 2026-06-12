from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_owner_post_approval_operator_checklist import (
    build_post_approval_operator_checklist,
    render_markdown_checklist,
    write_markdown_checklist,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _stage_commands() -> list[str]:
    return [f"git add -- '{path}'" for path in _stage_paths()]


def _command_group(name: str, commands: list[str] | None = None, executable_now: bool = False) -> dict[str, object]:
    return {
        "name": name,
        "title": name.replace("_", " ").title(),
        "commands": commands or [],
        "executable_now": executable_now,
        "prerequisites": [f"{name}_prerequisite"],
        "notes": [f"{name} note"],
    }


def _write_inputs(tmp_path: Path, *, approved: bool = False, post_stage: bool = False) -> dict[str, Path]:
    paths = {
        "owner_approval_resume_packet_path": tmp_path / "owner-approval-resume-packet.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_stage_execution_plan_path": tmp_path / "owner-stage-execution-plan.json",
        "owner_staging_preflight_path": tmp_path / "owner-staging-preflight.json",
        "owner_post_staging_verifier_path": tmp_path / "owner-post-staging-verifier.json",
        "owner_post_stage_commit_gate_path": tmp_path / "owner-post-stage-commit-gate.json",
        "owner_commit_packet_path": tmp_path / "owner-commit-packet.json",
        "owner_approval_path": tmp_path / "owner-stage-approval.json",
    }
    _write_json(
        paths["owner_approval_resume_packet_path"],
        {
            "status": "owner_approval_resume_packet_ready"
            if approved
            else "owner_approval_resume_packet_waiting_for_owner",
            "waiting_for_owner": not approved,
            "resume_ready": approved,
            "real_owner_approval_present": approved,
            "summary": {
                "stage_include_count": 2,
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "control_modes_preservation_status": "control_modes_preservation_ready",
                "control_modes_plan_only_default": True,
                "control_modes_loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
            },
            "command_groups": [
                _command_group("owner_create_approval_payload", executable_now=not approved),
                _command_group("approval_payload_audit", ["python scripts\\commercial_delivery_owner_approval_payload_audit.py"], approved),
                _command_group("approval_gate", ["python scripts\\commercial_delivery_owner_stage_approval_gate.py"], approved),
                _command_group(
                    "stage_execution_plan",
                    ["python scripts\\commercial_delivery_owner_stage_execution_plan.py"],
                    approved,
                ),
                _command_group("pre_stage_verification", ["python scripts\\commercial_delivery_owner_staging_preflight.py"], approved),
                _command_group("owner_stage_commands", _stage_commands(), approved),
                _command_group(
                    "post_stage_verification",
                    ["python scripts\\commercial_delivery_owner_post_staging_verifier.py"],
                ),
                _command_group(
                    "commit_gate_and_packet",
                    [
                        "python scripts\\commercial_delivery_owner_post_stage_commit_gate.py",
                        "python scripts\\commercial_delivery_owner_commit_packet.py",
                    ],
                ),
                _command_group(
                    "post_commit_evidence_refresh",
                    [
                        "python scripts\\commercial_delivery_owner_delivery_packet.py",
                        "python scripts\\commercial_delivery_closure_snapshot.py",
                    ],
                ),
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_ready" if approved else "owner_stage_approval_blocked",
            "stage_allowed": approved,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": "owner_stage_execution_ready" if approved else "owner_stage_execution_blocked",
            "stage_allowed": approved,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_preflight_path"],
        {
            "status": "owner_staging_preflight_blocked" if post_stage else "owner_staging_preflight_ready",
            "cached_staged_path_count": 2 if post_stage else 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_staging_verifier_path"],
        {
            "status": "owner_post_staging_verification_ready" if post_stage else "owner_post_staging_verification_blocked",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_ready" if post_stage else "owner_post_stage_commit_gate_blocked",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {
            "status": "owner_commit_packet_ready" if post_stage else "owner_commit_packet_blocked",
            "commit_allowed": post_stage,
            "full_codex_parity_claimed": False,
        },
    )
    if approved:
        _write_json(paths["owner_approval_path"], {"decision": "approve_owner_stage", "approve_stage": True})
    return paths


def test_operator_checklist_waits_for_owner_without_mutation(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_waiting_for_owner"
    assert checklist.waiting_for_owner is True
    assert checklist.operator_ready is False
    assert checklist.real_owner_approval_present is False
    assert checklist.stage_allowed is False
    assert checklist.stage_execution_ready is False
    assert checklist.mutation_performed is False
    assert checklist.git_stage_performed is False
    assert checklist.git_commit_performed is False
    assert checklist.git_push_performed is False
    assert checklist.network_mutation_performed is False
    assert checklist.agent_execution_enabled is False
    assert {check.status for check in checklist.checks} == {"passed"}
    assert checklist.summary["stage_command_count"] == 2
    assert checklist.summary["secondary_handoff_completed_count"] == 44
    stage_item = next(item for item in checklist.checklist if item.id == "owner_stage_commands")
    assert stage_item.executable_now is False
    assert stage_item.commands == _stage_commands()


def test_operator_checklist_ready_after_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_ready"
    assert checklist.waiting_for_owner is False
    assert checklist.operator_ready is True
    assert checklist.real_owner_approval_present is True
    assert checklist.stage_allowed is True
    assert checklist.stage_execution_ready is True
    assert {check.status for check in checklist.checks} == {"passed"}
    preflight = next(item for item in checklist.checklist if item.id == "pre_stage_verification")
    stage_item = next(item for item in checklist.checklist if item.id == "owner_stage_commands")
    assert preflight.executable_now is True
    assert stage_item.executable_now is True
    assert stage_item.commands == _stage_commands()


def test_operator_checklist_ready_after_owner_staging_without_reexecutable_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True, post_stage=True)

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_ready"
    assert checklist.operator_ready is True
    assert checklist.summary["pre_stage_ready"] is False
    assert checklist.summary["post_stage_sequence_accounted_for"] is True
    assert checklist.summary["owner_staging_preflight_cached_staged_path_count"] == 2
    preflight = next(item for item in checklist.checklist if item.id == "pre_stage_verification")
    stage_item = next(item for item in checklist.checklist if item.id == "owner_stage_commands")
    assert preflight.status == "complete"
    assert preflight.executable_now is False
    assert stage_item.status == "complete"
    assert stage_item.executable_now is False


def test_operator_checklist_blocks_post_stage_preflight_without_post_stage_evidence(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True, post_stage=True)
    _write_json(
        paths["owner_post_staging_verifier_path"],
        {"status": "owner_post_staging_verification_blocked", "full_codex_parity_claimed": False},
    )

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_blocked"
    assert checklist.operator_ready is False
    assert checklist.summary["post_stage_sequence_accounted_for"] is False
    assert "operator_state_accounted_for" in checklist.summary["blocking_reasons"]


def test_operator_checklist_blocks_missing_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    payload = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    for group in payload["command_groups"]:
        if group["name"] == "owner_stage_commands":
            group["commands"] = []
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_blocked"
    assert next(check for check in checklist.checks if check.name == "operator_sequence_present").status == "failed"
    assert "operator_sequence_present" in checklist.summary["blocking_reasons"]


def test_operator_checklist_accepts_post_commit_noop_without_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    payload = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    payload["summary"].update(
        {
            "stage_include_count": 100,
            "post_commit_noop_resume_ready": True,
            "post_commit_noop_accounted_for": True,
        }
    )
    for group in payload["command_groups"]:
        if group["name"] == "owner_stage_commands":
            group["commands"] = []
        if group["name"] in {"pre_stage_verification", "owner_stage_commands"}:
            group["executable_now"] = False
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(payload), encoding="utf-8")
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {"status": "owner_stage_approval_blocked", "stage_allowed": False, "full_codex_parity_claimed": False},
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {"status": "owner_stage_execution_blocked", "stage_allowed": False, "full_codex_parity_claimed": False},
    )
    _write_json(
        paths["owner_post_staging_verifier_path"],
        {"status": "owner_post_staging_verification_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {"status": "owner_post_stage_commit_gate_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {"status": "owner_commit_packet_ready", "commit_allowed": True, "full_codex_parity_claimed": False},
    )

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_ready"
    assert checklist.operator_ready is True
    assert checklist.stage_allowed is False
    assert checklist.stage_execution_ready is False
    assert checklist.summary["stage_command_count"] == 0
    assert checklist.summary["post_commit_noop_sequence_accounted_for"] is True
    assert next(check for check in checklist.checks if check.name == "operator_sequence_present").status == "passed"
    stage_item = next(item for item in checklist.checklist if item.id == "owner_stage_commands")
    assert stage_item.status == "complete"
    assert stage_item.commands == []


def test_operator_checklist_accepts_post_commit_noop_with_blocked_commit_reports(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approved=True)
    payload = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    payload["summary"].update(
        {
            "stage_include_count": 100,
            "post_commit_noop_resume_ready": True,
            "post_commit_noop_accounted_for": True,
        }
    )
    for group in payload["command_groups"]:
        if group["name"] == "owner_stage_commands":
            group["commands"] = []
        if group["name"] in {"pre_stage_verification", "owner_stage_commands"}:
            group["executable_now"] = False
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(payload), encoding="utf-8")
    _write_json(
        paths["owner_post_staging_verifier_path"],
        {"status": "owner_post_staging_verification_ready", "full_codex_parity_claimed": False},
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_blocked",
            "commit_allowed": False,
            "summary": {"post_commit_noop_accounted_for": True},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {
            "status": "owner_commit_packet_blocked",
            "commit_allowed": False,
            "summary": {"post_commit_noop_accounted_for": True},
            "full_codex_parity_claimed": False,
        },
    )

    checklist = build_post_approval_operator_checklist(**paths)

    assert checklist.status == "owner_post_approval_operator_checklist_ready"
    assert checklist.summary["post_commit_noop_sequence_accounted_for"] is True
    assert checklist.summary["commit_gate_noop_accounted_for"] is True
    assert checklist.summary["commit_packet_noop_accounted_for"] is True
    assert next(check for check in checklist.checks if check.name == "operator_sequence_present").status == "passed"


def test_operator_checklist_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    checklist = build_post_approval_operator_checklist(**paths)
    json_output = tmp_path / "checklist.json"
    md_output = tmp_path / "checklist.md"

    write_report(checklist, json_output)
    write_markdown_checklist(checklist, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_post_approval_operator_checklist_waiting_for_owner"
    assert payload["checklist_count"] == len(payload["checklist"])
    assert payload["checks_count"] == len(payload["checks"])
    assert payload["next_actions_count"] == len(payload["next_actions"])
    assert payload["known_limits_count"] == len(payload["known_limits"])
    assert "Commercial Delivery Post-Approval Operator Checklist" in markdown
    assert "owner_stage_commands" in render_markdown_checklist(checklist)
    assert "integration_review_answer_action_matrix.py" in markdown
