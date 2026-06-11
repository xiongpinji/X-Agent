from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_staging_packet import (
    build_owner_staging_packet,
    render_markdown_packet,
    write_markdown_packet,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest() -> dict[str, object]:
    return {
        "status": "original_kernel_delivery_manifest_ready",
        "stage_include_count": 2,
        "full_codex_parity_claimed": False,
        "excluded_dirty_paths": [
            {"path": "frontend/src/App.tsx", "scope": "frontend", "reason": "ui session"},
        ],
    }


def _staging_review() -> dict[str, object]:
    return {
        "status": "staging_review_ready",
        "owner_gated": True,
        "stage_include_count": 2,
        "eligible_stage_count": 2,
        "blocked_stage_count": 0,
        "unchanged_stage_count": 0,
        "full_codex_parity_claimed": False,
        "paths": [
            {
                "path": "backend/app/core/storage.py",
                "status": "eligible",
                "exists": True,
                "dirty": True,
                "category": "backend_core",
            },
            {
                "path": "tests/test_storage.py",
                "status": "eligible",
                "exists": True,
                "dirty": True,
                "category": "test",
            },
        ],
    }


def _post_commit_staging_review() -> dict[str, object]:
    payload = _staging_review()
    payload.update(
        {
            "eligible_stage_count": 0,
            "unchanged_stage_count": 2,
            "paths": [
                {
                    "path": "backend/app/core/storage.py",
                    "status": "unchanged",
                    "exists": True,
                    "dirty": False,
                    "category": "backend_core",
                },
                {
                    "path": "tests/test_storage.py",
                    "status": "unchanged",
                    "exists": True,
                    "dirty": False,
                    "category": "test",
                },
            ],
        }
    )
    return payload


def _task_board() -> dict[str, object]:
    return {
        "status": "commercial_delivery_ready_for_owner_staging_review",
        "summary": {
            "secondary_pending_count": 0,
            "secondary_handoff_next_count": 1,
            "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
            "secondary_handoff_completed_count": 44,
            "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
        },
    }


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_owner_staging_packet_ready_for_owner_review(tmp_path: Path) -> None:
    staging_review = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    task_board = tmp_path / "task-board.json"
    _write_json(staging_review, _staging_review())
    _write_json(manifest, _manifest())
    _write_json(task_board, _task_board())

    packet = build_owner_staging_packet(
        staging_review_path=staging_review,
        manifest_path=manifest,
        task_board_path=task_board,
    )

    assert packet.status == "owner_staging_packet_ready"
    assert packet.owner_gated is True
    assert packet.mutation_performed is False
    assert packet.git_stage_performed is False
    assert packet.git_commit_performed is False
    assert packet.git_push_performed is False
    assert packet.network_mutation_performed is False
    assert packet.agent_execution_enabled is False
    assert packet.stage_paths == ["backend/app/core/storage.py", "tests/test_storage.py"]
    assert packet.stage_commands == [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]
    assert packet.stage_path_digest == _digest_values(packet.stage_paths)
    assert packet.stage_command_digest == _digest_values(packet.stage_commands)
    assert packet.summary["task_board_readable"] is True
    assert packet.summary["secondary_pending_count"] == 0
    assert packet.summary["secondary_handoff_next_count"] == 1
    assert packet.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert packet.summary["secondary_handoff_completed_count"] == 44
    assert packet.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert len(packet.stage_path_digest) == 64
    assert len(packet.stage_command_digest) == 64
    assert "python scripts\\commercial_delivery_refresh_chain_receipt.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_pre_stage_readiness_gate.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_stage_approval_request.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_stage_approval_brief.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_stage_approval_gate.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_stage_execution_plan.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_staging_rollback_plan.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_staging_preflight.py" in packet.pre_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_staging_preflight.py" not in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_command_audit.py" in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_post_staging_verifier.py" in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_post_stage_commit_gate.py" in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_commit_packet.py" in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_delivery_packet.py" in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_decision_brief.py" not in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_owner_pre_stage_readiness_gate.py" not in packet.post_stage_verification_commands
    assert "python scripts\\commercial_delivery_staging_review.py" not in packet.post_stage_verification_commands
    assert any("test_commercial_delivery_owner_post_stage_commit_gate.py" in command for command in packet.post_stage_verification_commands)
    assert any("test_commercial_delivery_owner_commit_packet.py" in command for command in packet.post_stage_verification_commands)
    assert any("test_commercial_delivery_owner_delivery_packet.py" in command for command in packet.post_stage_verification_commands)
    assert any("test_commercial_delivery_owner_post_staging_verifier.py" in command for command in packet.post_stage_verification_commands)
    assert any("test_commercial_delivery_owner_command_audit.py" in command for command in packet.post_stage_verification_commands)
    assert packet.verification_commands == packet.post_stage_verification_commands
    assert any("pre_stage_verification_commands" in action for action in packet.next_actions)
    assert packet.excluded_dirty_paths == [
        {"path": "frontend/src/App.tsx", "scope": "frontend", "reason": "ui session"}
    ]
    assert {check.status for check in packet.checks} == {"passed"}


def test_owner_staging_packet_accounts_for_post_commit_noop(tmp_path: Path) -> None:
    staging_review = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    task_board = tmp_path / "task-board.json"
    _write_json(staging_review, _post_commit_staging_review())
    _write_json(manifest, _manifest())
    _write_json(task_board, _task_board())

    packet = build_owner_staging_packet(
        staging_review_path=staging_review,
        manifest_path=manifest,
        task_board_path=task_board,
    )

    assert packet.status == "owner_staging_packet_ready"
    assert packet.eligible_stage_count == 0
    assert packet.unchanged_stage_count == 2
    assert packet.stage_paths == []
    assert packet.stage_commands == []
    assert packet.stage_path_digest == _digest_values([])
    assert packet.stage_command_digest == _digest_values([])
    assert packet.summary["post_commit_noop_accounted_for"] is True
    assert packet.summary["unchanged_stage_count"] == 2
    assert {check.status for check in packet.checks} == {"passed"}
    eligible = next(check for check in packet.checks if check.name == "eligible_paths_present")
    assert eligible.details["post_commit_noop_accounted_for"] is True
    count = next(check for check in packet.checks if check.name == "stage_path_count_matches_review")
    assert count.details["post_commit_noop_accounted_for"] is True


def test_owner_staging_packet_blocks_when_staging_review_not_ready(tmp_path: Path) -> None:
    staging_review = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    task_board = tmp_path / "task-board.json"
    payload = _staging_review()
    payload["status"] = "staging_review_blocked"
    payload["blocked_stage_count"] = 1
    payload["paths"] = [
        {"path": "backend/app/api/workbench.py", "status": "blocked", "reason": "protected"}
    ]
    _write_json(staging_review, payload)
    _write_json(manifest, _manifest())
    _write_json(task_board, _task_board())

    packet = build_owner_staging_packet(
        staging_review_path=staging_review,
        manifest_path=manifest,
        task_board_path=task_board,
    )

    assert packet.status == "owner_staging_packet_blocked"
    assert packet.blocked_paths == ["backend/app/api/workbench.py"]
    assert packet.stage_commands == []
    review = next(check for check in packet.checks if check.name == "staging_review_ready")
    assert review.status == "failed"
    blocked = next(check for check in packet.checks if check.name == "no_blocked_stage_paths")
    assert blocked.status == "failed"


def test_owner_staging_packet_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    staging_review = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    task_board = tmp_path / "task-board.json"
    payload = _manifest()
    payload["full_codex_parity_claimed"] = True
    _write_json(staging_review, _staging_review())
    _write_json(manifest, payload)
    _write_json(task_board, _task_board())

    packet = build_owner_staging_packet(
        staging_review_path=staging_review,
        manifest_path=manifest,
        task_board_path=task_board,
    )

    assert packet.status == "owner_staging_packet_blocked"
    assert packet.full_codex_parity_claimed is True
    parity = next(check for check in packet.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"


def test_owner_staging_packet_blocks_missing_reports(tmp_path: Path) -> None:
    packet = build_owner_staging_packet(
        staging_review_path=tmp_path / "missing-staging.json",
        manifest_path=tmp_path / "missing-manifest.json",
        task_board_path=tmp_path / "missing-task-board.json",
    )

    assert packet.status == "owner_staging_packet_blocked"
    assert packet.stage_commands == []
    assert packet.summary["task_board_readable"] is False
    assert packet.summary["secondary_handoff_next_queue"] == []
    assert next(check for check in packet.checks if check.name == "staging_review_readable").status == "failed"
    assert next(check for check in packet.checks if check.name == "manifest_readable").status == "failed"


def test_owner_staging_packet_does_not_block_on_missing_task_board(tmp_path: Path) -> None:
    staging_review = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    _write_json(staging_review, _staging_review())
    _write_json(manifest, _manifest())

    packet = build_owner_staging_packet(
        staging_review_path=staging_review,
        manifest_path=manifest,
        task_board_path=tmp_path / "missing-task-board.json",
    )

    assert packet.status == "owner_staging_packet_ready"
    assert packet.summary["task_board_readable"] is False
    assert "task_board_error" in packet.summary
    assert packet.summary["secondary_handoff_next_queue"] == []
    assert {check.status for check in packet.checks} == {"passed"}


def test_owner_staging_packet_writes_json_and_markdown(tmp_path: Path) -> None:
    staging_review = tmp_path / "staging.json"
    manifest = tmp_path / "manifest.json"
    task_board = tmp_path / "task-board.json"
    _write_json(staging_review, _staging_review())
    _write_json(manifest, _manifest())
    _write_json(task_board, _task_board())
    packet = build_owner_staging_packet(
        staging_review_path=staging_review,
        manifest_path=manifest,
        task_board_path=task_board,
    )

    json_output = tmp_path / "packet.json"
    md_output = tmp_path / "packet.md"
    write_report(packet, json_output)
    write_markdown_packet(packet, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_staging_packet_ready"
    assert payload["stage_path_digest"] == packet.stage_path_digest
    assert payload["stage_command_digest"] == packet.stage_command_digest
    assert payload["summary"]["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert payload["summary"]["secondary_handoff_completed_count"] == 44
    assert "Commercial Delivery Owner Staging Packet" in markdown
    assert f"Stage path digest: `{packet.stage_path_digest}`" in markdown
    assert f"Stage command digest: `{packet.stage_command_digest}`" in markdown
    assert "Secondary handoff next queue: `integration_review_action_status_board.py`" in markdown
    assert "Secondary handoff completed count: `44`" in markdown
    assert "git add -- 'backend/app/core/storage.py'" in render_markdown_packet(packet)
    assert "Pre-Stage Verification Commands" in markdown
    assert "Post-Stage Verification Commands" in markdown
