from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_owner_staging_runbook import (
    build_owner_staging_runbook,
    render_markdown_runbook,
    write_markdown_runbook,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_reports(reports_dir: Path) -> dict[str, Path]:
    paths = {
        "owner_packet_path": reports_dir / "owner-packet.json",
        "pre_stage_gate_path": reports_dir / "pre-stage-gate.json",
        "task_board_path": reports_dir / "task-board.json",
    }
    pre_commands = [
        "python scripts\\commercial_delivery_refresh_chain_receipt.py",
        "python scripts\\commercial_delivery_owner_pre_stage_readiness_gate.py",
        "python scripts\\commercial_delivery_owner_staging_preflight.py",
        "git diff --cached --name-only",
    ]
    stage_commands = [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]
    post_commands = [
        "git diff --cached --name-only",
        "python scripts\\commercial_delivery_owner_command_audit.py",
        "python scripts\\commercial_delivery_owner_post_staging_verifier.py",
    ]
    _write_json(
        paths["owner_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_include_count": 2,
            "stage_commands": stage_commands,
            "pre_stage_verification_commands": pre_commands,
            "post_stage_verification_commands": post_commands,
            "verification_commands": post_commands,
            "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["pre_stage_gate_path"],
        {
            "status": "owner_pre_stage_readiness_ready",
            "owner_gated": True,
            "summary": {"stage_include_count": 2},
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["task_board_path"],
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": {
                "secondary_pending_count": 2,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "owner_pre_stage_readiness_gate_status": "owner_pre_stage_readiness_ready",
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_staging_runbook_ready(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_ready"
    assert runbook.evidence_type == "commercial_delivery_owner_staging_runbook"
    assert runbook.owner_gated is True
    assert runbook.mutation_performed is False
    assert runbook.git_stage_performed is False
    assert runbook.git_commit_performed is False
    assert runbook.git_push_performed is False
    assert runbook.network_mutation_performed is False
    assert runbook.agent_execution_enabled is False
    assert runbook.full_codex_parity_claimed is False
    assert runbook.summary["stage_command_count"] == 2
    assert runbook.summary["pre_stage_verification_command_count"] == 4
    assert runbook.summary["post_stage_verification_command_count"] == 3
    assert runbook.summary["verification_alias_matches_post"] is True
    assert runbook.summary["secondary_pending_count"] == 2
    assert runbook.summary["secondary_handoff_next_count"] == 1
    assert runbook.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert runbook.summary["secondary_handoff_completed_count"] == 44
    assert runbook.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert [section.name for section in runbook.sections] == [
        "pre_stage_verification",
        "owner_stage_commands",
        "post_stage_verification",
        "commit_preview",
    ]
    assert {check.status for check in runbook.checks} == {"passed"}


def test_owner_staging_runbook_accepts_post_commit_noop_accounting(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    owner_packet = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    owner_packet.update(
        {
            "stage_include_count": 100,
            "eligible_stage_count": 0,
            "blocked_stage_count": 0,
            "unchanged_stage_count": 100,
            "stage_commands": [],
            "summary": {
                "post_commit_noop_accounted_for": True,
                "unchanged_stage_count": 100,
            },
        }
    )
    paths["owner_packet_path"].write_text(json.dumps(owner_packet), encoding="utf-8")
    pre_stage_gate = json.loads(paths["pre_stage_gate_path"].read_text(encoding="utf-8"))
    pre_stage_gate["summary"] = {
        "stage_include_count": 100,
        "stage_command_count": 0,
        "post_commit_noop_accounted_for": True,
        "post_commit_noop_stage_counts_agree": True,
    }
    paths["pre_stage_gate_path"].write_text(json.dumps(pre_stage_gate), encoding="utf-8")

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_ready"
    assert runbook.summary["stage_command_count"] == 0
    assert runbook.summary["post_commit_noop_accounted_for"] is True
    assert {check.status for check in runbook.checks} == {"passed"}
    stage_check = next(check for check in runbook.checks if check.name == "stage_commands_are_explicit_path_adds")
    assert stage_check.details["post_commit_noop_accounted_for"] is True
    stage_section = next(section for section in runbook.sections if section.name == "owner_stage_commands")
    assert stage_section.commands == []
    assert "post-commit/noop" in stage_section.notes[0]


def test_owner_staging_runbook_accepts_active_subset_stage_count(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    owner_packet = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    owner_packet.update(
        {
            "stage_include_count": 100,
            "eligible_stage_count": 2,
            "blocked_stage_count": 0,
            "unchanged_stage_count": 98,
        }
    )
    paths["owner_packet_path"].write_text(json.dumps(owner_packet), encoding="utf-8")
    pre_stage_gate = json.loads(paths["pre_stage_gate_path"].read_text(encoding="utf-8"))
    pre_stage_gate["summary"] = {
        "stage_include_count": 100,
        "stage_command_count": 2,
    }
    paths["pre_stage_gate_path"].write_text(json.dumps(pre_stage_gate), encoding="utf-8")

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_ready"
    stage_count_check = next(check for check in runbook.checks if check.name == "stage_command_count_matches_gate")
    assert stage_count_check.details["owner_packet_stage_include_count"] == 100
    assert stage_count_check.details["owner_packet_eligible_stage_count"] == 2
    assert stage_count_check.details["pre_stage_gate_stage_command_count"] == 2
    assert stage_count_check.details["active_stage_count_matches_gate"] is True


def test_owner_staging_runbook_blocks_missing_gate(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    paths["pre_stage_gate_path"].unlink()

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_blocked"
    assert next(check for check in runbook.checks if check.name == "reports_readable").status == "failed"
    assert next(check for check in runbook.checks if check.name == "pre_stage_gate_ready").status == "failed"


def test_owner_staging_runbook_blocks_stage_count_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["pre_stage_gate_path"].read_text(encoding="utf-8"))
    payload["summary"]["stage_include_count"] = 3
    paths["pre_stage_gate_path"].write_text(json.dumps(payload), encoding="utf-8")

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_blocked"
    assert next(check for check in runbook.checks if check.name == "stage_command_count_matches_gate").status == "failed"


def test_owner_staging_runbook_blocks_post_stage_preflight_mix(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    payload["post_stage_verification_commands"].append("python scripts\\commercial_delivery_owner_staging_preflight.py")
    payload["verification_commands"] = payload["post_stage_verification_commands"]
    paths["owner_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_blocked"
    assert next(check for check in runbook.checks if check.name == "verification_commands_are_split").status == "failed"


def test_owner_staging_runbook_blocks_broad_stage_command(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    payload["stage_commands"] = ["git add ."]
    paths["owner_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_blocked"
    assert next(check for check in runbook.checks if check.name == "stage_commands_are_explicit_path_adds").status == "failed"


def test_owner_staging_runbook_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["full_codex_parity_claimed"] = True
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    runbook = build_owner_staging_runbook(**paths)

    assert runbook.status == "owner_staging_runbook_blocked"
    assert runbook.full_codex_parity_claimed is True
    assert next(check for check in runbook.checks if check.name == "no_full_codex_parity_claim").status == "failed"


def test_owner_staging_runbook_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    runbook = build_owner_staging_runbook(**paths)
    json_output = tmp_path / "runbook.json"
    md_output = tmp_path / "runbook.md"

    write_report(runbook, json_output)
    write_markdown_runbook(runbook, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_staging_runbook_ready"
    assert "Commercial Delivery Owner Staging Runbook" in markdown
    assert "Owner-approved stage commands" in render_markdown_runbook(runbook)
