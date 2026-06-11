from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_commit_packet import (
    build_owner_commit_packet,
    render_markdown_packet,
    write_markdown_packet,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str:
    return _digest_values(sorted(set(paths)))


def _commit_preview() -> str:
    return 'git commit -m "chore: prepare X-Agent commercial delivery package"'


def _write_reports(reports_dir: Path) -> dict[str, Path]:
    paths = {
        "owner_packet_path": reports_dir / "owner-packet.json",
        "owner_post_staging_path": reports_dir / "owner-post-staging.json",
        "owner_command_audit_path": reports_dir / "owner-command-audit.json",
        "owner_post_stage_commit_gate_path": reports_dir / "owner-post-stage-commit-gate.json",
        "task_board_path": reports_dir / "task-board.json",
    }
    stage_paths = _stage_paths()
    stage_commands = [f"git add -- '{path}'" for path in stage_paths]
    _write_json(
        paths["owner_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_paths": stage_paths,
            "stage_path_digest": _digest_values(stage_paths),
            "stage_commands": stage_commands,
            "stage_command_digest": _digest_values(stage_commands),
            "post_stage_verification_commands": [
                "git diff --cached --name-only",
                "python scripts\\commercial_delivery_owner_command_audit.py",
                "python scripts\\commercial_delivery_owner_post_staging_verifier.py",
                "python scripts\\commercial_delivery_owner_post_stage_commit_gate.py",
            ],
            "commit_command_preview": _commit_preview(),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_staging_path"],
        {
            "status": "owner_post_staging_verification_ready",
            "owner_gated": True,
            "expected_stage_path_count": len(stage_paths),
            "cached_staged_path_count": len(stage_paths),
            "cached_staged_paths": list(reversed(stage_paths)),
            "missing_cached_paths": [],
            "unexpected_cached_paths": [],
            "protected_cached_paths": [],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_command_audit_path"],
        {
            "status": "owner_command_audit_ready",
            "owner_gated": True,
            "command_count": len(stage_paths),
            "expected_path_count": len(stage_paths),
            "command_paths": stage_paths,
            "expected_paths": stage_paths,
            "command_path_digest": _digest_values(stage_paths),
            "expected_path_digest": _digest_values(stage_paths),
            "owner_packet_stage_path_digest": _digest_values(stage_paths),
            "command_digest": _digest_values(stage_commands),
            "owner_packet_stage_command_digest": _digest_values(stage_commands),
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_ready",
            "owner_gated": True,
            "decision": "ready_for_owner_commit",
            "commit_allowed": True,
            "commit_command_preview": _commit_preview(),
            "expected_stage_paths": stage_paths,
            "cached_staged_paths": list(reversed(stage_paths)),
            "expected_stage_path_set_digest": _path_set_digest(stage_paths),
            "cached_staged_path_set_digest": _path_set_digest(stage_paths),
            "stage_path_digest": _digest_values(stage_paths),
            "stage_command_digest": _digest_values(stage_commands),
            "command_path_set_digest": _path_set_digest(stage_paths),
            "summary": {"cached_staged_path_count": len(stage_paths)},
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
                "secondary_pending_blocks_owner_staging": False,
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_commit_packet_ready_after_post_stage_gate(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_ready"
    assert packet.decision == "ready_for_owner_commit"
    assert packet.commit_allowed is True
    assert packet.evidence_type == "commercial_delivery_owner_commit_packet"
    assert packet.owner_gated is True
    assert packet.mutation_performed is False
    assert packet.git_stage_performed is False
    assert packet.git_commit_performed is False
    assert packet.git_push_performed is False
    assert packet.network_mutation_performed is False
    assert packet.agent_execution_enabled is False
    assert packet.full_codex_parity_claimed is False
    assert packet.commit_command_preview == _commit_preview()
    assert packet.summary["cached_staged_path_count"] == 2
    assert packet.expected_stage_path_set_digest == _path_set_digest(_stage_paths())
    assert packet.cached_staged_path_set_digest == _path_set_digest(_stage_paths())
    assert packet.stage_path_digest == _digest_values(_stage_paths())
    assert packet.stage_command_digest == _digest_values([f"git add -- '{path}'" for path in _stage_paths()])
    assert packet.command_path_set_digest == _path_set_digest(_stage_paths())
    assert packet.gate_expected_stage_path_set_digest == _path_set_digest(_stage_paths())
    assert packet.gate_cached_staged_path_set_digest == _path_set_digest(_stage_paths())
    assert packet.summary["stage_path_digest"] == packet.stage_path_digest
    assert packet.summary["stage_command_digest"] == packet.stage_command_digest
    assert packet.summary["gate_stage_path_digest"] == packet.stage_path_digest
    assert packet.summary["gate_stage_command_digest"] == packet.stage_command_digest
    assert packet.summary["command_audit_command_digest"] == packet.stage_command_digest
    assert packet.summary["owner_post_stage_commit_gate_status"] == "owner_post_stage_commit_gate_ready"
    assert packet.summary["secondary_pending_count"] == 0
    assert packet.summary["secondary_handoff_next_count"] == 1
    assert packet.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert packet.summary["secondary_handoff_completed_count"] == 44
    assert packet.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert packet.summary["owner_action_required"] is False
    assert packet.summary["blocking_reasons"] == []
    secondary_check = next(check for check in packet.checks if check.name == "secondary_pending_does_not_block_owner_commit")
    assert secondary_check.details["secondary_handoff_completed_count"] == 44
    assert secondary_check.details["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert [section.name for section in packet.sections] == [
        "post_stage_verification",
        "commit_preview",
        "stop_conditions",
    ]
    assert {check.status for check in packet.checks} == {"passed"}


def test_owner_commit_packet_accepts_post_commit_noop_evidence(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    empty_digest = _digest_values([])
    for key in ("owner_packet_path", "owner_command_audit_path", "owner_post_stage_commit_gate_path"):
        payload = json.loads(paths[key].read_text(encoding="utf-8"))
        payload.update(
            {
                "stage_paths": [],
                "stage_path_digest": empty_digest,
                "stage_commands": [],
                "stage_command_digest": empty_digest,
                "command_count": 0,
                "expected_path_count": 0,
                "command_paths": [],
                "expected_paths": [],
                "expected_stage_paths": [],
                "cached_staged_paths": [],
                "expected_stage_path_set_digest": empty_digest,
                "cached_staged_path_set_digest": empty_digest,
                "command_path_set_digest": empty_digest,
                "command_path_digest": empty_digest,
                "expected_path_digest": empty_digest,
                "owner_packet_stage_path_digest": empty_digest,
                "command_digest": empty_digest,
                "owner_packet_stage_command_digest": empty_digest,
                "summary": {"cached_staged_path_count": 0, "post_commit_noop_accounted_for": True},
            }
        )
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    post_staging = json.loads(paths["owner_post_staging_path"].read_text(encoding="utf-8"))
    post_staging.update(
        {
            "expected_stage_path_count": 0,
            "cached_staged_path_count": 0,
            "cached_staged_paths": [],
            "expected_stage_path_set_digest": empty_digest,
            "cached_staged_path_set_digest": empty_digest,
            "summary": {"post_commit_noop_accounted_for": True},
        }
    )
    paths["owner_post_staging_path"].write_text(json.dumps(post_staging), encoding="utf-8")
    task_board = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    task_board.update(
        {
            "status": "commercial_delivery_blocked",
            "summary": {
                **task_board["summary"],
                "owner_staging_packet_status": "owner_staging_packet_ready",
                "owner_staging_preflight_accounted_for": True,
                "owner_post_staging_verifier_status": "owner_post_staging_verification_ready",
                "eligible_stage_count": 0,
                "owner_stage_command_count": 0,
                "post_staging_cached_path_count": 0,
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_ready",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
            },
            "checks": [
                {"name": "staging_review_ready", "status": "passed"},
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
            ],
        }
    )
    paths["task_board_path"].write_text(json.dumps(task_board), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_ready"
    assert packet.commit_allowed is True
    assert packet.summary["post_commit_noop_accounted_for"] is True
    assert packet.summary["task_board_post_commit_noop_accounted_for"] is True
    assert packet.expected_stage_path_set_digest == empty_digest
    assert packet.cached_staged_path_set_digest == empty_digest
    assert next(check for check in packet.checks if check.name == "staged_paths_match_owner_packet").status == "passed"
    task_board_check = next(check for check in packet.checks if check.name == "task_board_ready")
    assert task_board_check.status == "passed"
    assert task_board_check.details["task_board_post_commit_noop_accounted_for"] is True


def test_owner_commit_packet_accepts_post_staging_task_board_cycle(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    task_board = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    task_board.update(
        {
            "status": "commercial_delivery_blocked",
            "summary": {
                **task_board["summary"],
                "staging_review_status": "staging_review_ready",
                "owner_staging_packet_status": "owner_staging_packet_ready",
                "owner_staging_preflight_accounted_for": True,
                "owner_post_staging_verifier_status": "owner_post_staging_verification_ready",
                "eligible_stage_count": len(_stage_paths()),
                "owner_stage_command_count": len(_stage_paths()),
                "post_staging_cached_path_count": len(_stage_paths()),
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_ready",
                "owner_commit_packet_status": "owner_commit_packet_blocked",
            },
            "checks": [
                {"name": "pre_approval_drift_guard_ready", "status": "failed"},
            ],
        }
    )
    paths["task_board_path"].write_text(json.dumps(task_board), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_ready"
    assert packet.summary["task_board_post_staging_accounted_for"] is True
    task_board_check = next(check for check in packet.checks if check.name == "task_board_ready")
    assert task_board_check.status == "passed"
    assert task_board_check.details["task_board_post_staging_accounted_for"] is True


def test_owner_commit_packet_blocks_when_commit_gate_is_not_ready(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_stage_commit_gate_path"].read_text(encoding="utf-8"))
    payload["status"] = "owner_post_stage_commit_gate_blocked"
    payload["commit_allowed"] = False
    paths["owner_post_stage_commit_gate_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_blocked"
    assert packet.commit_allowed is False
    assert packet.summary["owner_action_required"] is True
    assert packet.summary["blocking_reasons"] == [
        "owner_post_stage_commit_gate_ready",
        "commit_allowed_by_gate",
    ]
    assert next(
        check for check in packet.checks if check.name == "owner_post_stage_commit_gate_ready"
    ).status == "failed"
    assert next(check for check in packet.checks if check.name == "commit_allowed_by_gate").status == "failed"


def test_owner_commit_packet_blocks_staged_path_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_staging_path"].read_text(encoding="utf-8"))
    payload["cached_staged_paths"] = ["backend/app/core/storage.py", "scripts/unexpected.py"]
    paths["owner_post_staging_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_blocked"
    assert next(check for check in packet.checks if check.name == "staged_paths_match_owner_packet").status == "failed"
    assert next(check for check in packet.checks if check.name == "path_set_digests_match_owner_packet").status == "failed"


def test_owner_commit_packet_blocks_commit_preview_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_stage_commit_gate_path"].read_text(encoding="utf-8"))
    payload["commit_command_preview"] = 'git commit -m "different"'
    paths["owner_post_stage_commit_gate_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_blocked"
    assert next(check for check in packet.checks if check.name == "commit_preview_consistent").status == "failed"


def test_owner_commit_packet_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["full_codex_parity_claimed"] = True
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_blocked"
    assert packet.full_codex_parity_claimed is True
    assert next(check for check in packet.checks if check.name == "no_full_codex_parity_claim").status == "failed"


def test_owner_commit_packet_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    packet = build_owner_commit_packet(**paths)
    json_output = tmp_path / "commit-packet.json"
    md_output = tmp_path / "commit-packet.md"

    write_report(packet, json_output)
    write_markdown_packet(packet, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_commit_packet_ready"
    assert payload["expected_stage_path_set_digest"] == packet.expected_stage_path_set_digest
    assert payload["gate_cached_staged_path_set_digest"] == packet.gate_cached_staged_path_set_digest
    assert payload["summary"]["blocking_reasons"] == []
    assert payload["summary"]["owner_action_required"] is False
    assert "Commercial Delivery Owner Commit Packet" in markdown
    assert "Owner action required: `false`" in markdown
    assert "Blocking reasons: ``" in markdown
    assert f"Expected stage path set digest: `{packet.expected_stage_path_set_digest}`" in markdown
    assert f"Cached staged path set digest: `{packet.cached_staged_path_set_digest}`" in markdown
    assert "ready_for_owner_commit" in render_markdown_packet(packet)


def test_owner_commit_packet_blocks_gate_digest_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_stage_commit_gate_path"].read_text(encoding="utf-8"))
    payload["cached_staged_path_set_digest"] = "0" * 64
    paths["owner_post_stage_commit_gate_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_blocked"
    digest = next(check for check in packet.checks if check.name == "path_set_digests_match_owner_packet")
    assert digest.status == "failed"


def test_owner_commit_packet_blocks_gate_ordered_command_digest_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_stage_commit_gate_path"].read_text(encoding="utf-8"))
    payload["stage_command_digest"] = "1" * 64
    paths["owner_post_stage_commit_gate_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_commit_packet(**paths)

    assert packet.status == "owner_commit_packet_blocked"
    digest = next(check for check in packet.checks if check.name == "ordered_stage_digests_match_owner_packet")
    assert digest.status == "failed"
