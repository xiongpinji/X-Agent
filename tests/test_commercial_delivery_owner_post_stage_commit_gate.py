from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_post_stage_commit_gate import (
    build_owner_post_stage_commit_gate,
    render_markdown_gate,
    write_markdown_gate,
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


def _write_reports(reports_dir: Path) -> dict[str, Path]:
    paths = {
        "owner_packet_path": reports_dir / "owner-packet.json",
        "owner_post_staging_path": reports_dir / "owner-post-staging.json",
        "owner_command_audit_path": reports_dir / "owner-command-audit.json",
        "owner_decision_brief_path": reports_dir / "owner-decision-brief.json",
        "task_board_path": reports_dir / "task-board.json",
    }
    stage_paths = _stage_paths()
    stage_commands = [f"git add -- '{path}'" for path in stage_paths]
    _write_json(
        paths["owner_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_include_count": len(stage_paths),
            "stage_paths": stage_paths,
            "stage_path_digest": _digest_values(stage_paths),
            "stage_commands": stage_commands,
            "stage_command_digest": _digest_values(stage_commands),
            "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
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
            "expected_stage_path_set_digest": _path_set_digest(stage_paths),
            "cached_staged_path_set_digest": _path_set_digest(stage_paths),
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
        paths["owner_decision_brief_path"],
        {
            "status": "ready_for_owner_staging_decision",
            "owner_gated": True,
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
                "secondary_pending_blocks_owner_staging": False,
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_post_stage_commit_gate_ready_after_exact_owner_staging(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_ready"
    assert gate.decision == "ready_for_owner_commit"
    assert gate.commit_allowed is True
    assert gate.evidence_type == "commercial_delivery_owner_post_stage_commit_gate"
    assert gate.owner_gated is True
    assert gate.mutation_performed is False
    assert gate.git_stage_performed is False
    assert gate.git_commit_performed is False
    assert gate.git_push_performed is False
    assert gate.network_mutation_performed is False
    assert gate.agent_execution_enabled is False
    assert gate.full_codex_parity_claimed is False
    assert gate.expected_stage_paths == _stage_paths()
    assert gate.cached_staged_paths == _stage_paths()
    assert gate.expected_stage_path_set_digest == _path_set_digest(_stage_paths())
    assert gate.cached_staged_path_set_digest == _path_set_digest(_stage_paths())
    assert gate.stage_path_digest == _digest_values(_stage_paths())
    assert gate.stage_command_digest == _digest_values([f"git add -- '{path}'" for path in _stage_paths()])
    assert gate.command_path_set_digest == _path_set_digest(_stage_paths())
    assert gate.owner_packet_stage_path_set_digest == _path_set_digest(_stage_paths())
    assert gate.summary["cached_staged_path_count"] == 2
    assert gate.summary["cached_staged_path_set_digest"] == gate.cached_staged_path_set_digest
    assert gate.summary["stage_path_digest"] == gate.stage_path_digest
    assert gate.summary["stage_command_digest"] == gate.stage_command_digest
    assert gate.summary["command_audit_command_digest"] == gate.stage_command_digest
    assert gate.summary["verifier_expected_stage_path_set_digest"] == gate.expected_stage_path_set_digest
    assert gate.summary["verifier_cached_staged_path_set_digest"] == gate.cached_staged_path_set_digest
    assert gate.summary["owner_post_staging_status"] == "owner_post_staging_verification_ready"
    assert gate.summary["secondary_pending_count"] == 2
    assert gate.summary["secondary_handoff_next_count"] == 1
    assert gate.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert gate.summary["secondary_handoff_completed_count"] == 44
    assert gate.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert gate.summary["owner_action_required"] is False
    assert gate.summary["blocking_reasons"] == []
    secondary_check = next(check for check in gate.checks if check.name == "secondary_pending_does_not_block_owner_commit")
    assert secondary_check.details["secondary_handoff_completed_count"] == 44
    assert secondary_check.details["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert {check.status for check in gate.checks} == {"passed"}


def test_owner_post_stage_commit_gate_blocks_when_post_staging_not_ready(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_staging_path"].read_text(encoding="utf-8"))
    payload["status"] = "owner_post_staging_verification_blocked"
    payload["cached_staged_path_count"] = 0
    payload["cached_staged_paths"] = []
    payload["cached_staged_path_set_digest"] = None
    payload["missing_cached_paths"] = _stage_paths()
    paths["owner_post_staging_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_blocked"
    assert gate.commit_allowed is False
    assert gate.summary["owner_action_required"] is True
    assert "owner_post_staging_verification_ready" in gate.summary["blocking_reasons"]
    assert "stage_counts_agree" in gate.summary["blocking_reasons"]
    assert "cached_paths_match_owner_packet" in gate.summary["blocking_reasons"]
    assert next(
        check for check in gate.checks if check.name == "owner_post_staging_verification_ready"
    ).status == "failed"
    assert next(check for check in gate.checks if check.name == "cached_paths_match_owner_packet").status == "failed"


def test_owner_post_stage_commit_gate_blocks_unexpected_cached_path(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_staging_path"].read_text(encoding="utf-8"))
    payload["cached_staged_path_count"] = 3
    payload["cached_staged_paths"] = _stage_paths() + ["scripts/unexpected.py"]
    payload["cached_staged_path_set_digest"] = _path_set_digest(_stage_paths() + ["scripts/unexpected.py"])
    payload["unexpected_cached_paths"] = ["scripts/unexpected.py"]
    paths["owner_post_staging_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_blocked"
    assert gate.summary["cached_staged_path_count"] == 3
    assert next(check for check in gate.checks if check.name == "stage_counts_agree").status == "failed"
    assert next(check for check in gate.checks if check.name == "path_set_digests_match_owner_packet").status == "failed"
    assert next(check for check in gate.checks if check.name == "post_staging_has_no_path_drift").status == "failed"


def test_owner_post_stage_commit_gate_allows_stage_path_subset_of_manifest_count(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    payload["stage_include_count"] = 100
    paths["owner_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_ready"
    stage_count = next(check for check in gate.checks if check.name == "stage_counts_agree")
    assert stage_count.status == "passed"
    assert stage_count.details["owner_packet_stage_include_count"] == 100
    assert stage_count.details["owner_packet_stage_path_count"] == len(_stage_paths())


def test_owner_post_stage_commit_gate_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["full_codex_parity_claimed"] = True
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_blocked"
    assert gate.full_codex_parity_claimed is True
    assert next(check for check in gate.checks if check.name == "no_full_codex_parity_claim").status == "failed"


def test_owner_post_stage_commit_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    gate = build_owner_post_stage_commit_gate(**paths)
    json_output = tmp_path / "commit-gate.json"
    md_output = tmp_path / "commit-gate.md"

    write_report(gate, json_output)
    write_markdown_gate(gate, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_post_stage_commit_gate_ready"
    assert payload["expected_stage_path_set_digest"] == gate.expected_stage_path_set_digest
    assert payload["cached_staged_path_set_digest"] == gate.cached_staged_path_set_digest
    assert payload["summary"]["blocking_reasons"] == []
    assert payload["summary"]["owner_action_required"] is False
    assert "Commercial Delivery Owner Post-Stage Commit Gate" in markdown
    assert "Owner action required: `false`" in markdown
    assert "Blocking reasons: ``" in markdown
    assert f"Expected stage path set digest: `{gate.expected_stage_path_set_digest}`" in markdown
    assert f"Cached staged path set digest: `{gate.cached_staged_path_set_digest}`" in markdown
    assert "ready_for_owner_commit" in render_markdown_gate(gate)


def test_owner_post_stage_commit_gate_blocks_verifier_digest_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_post_staging_path"].read_text(encoding="utf-8"))
    payload["cached_staged_path_set_digest"] = "0" * 64
    paths["owner_post_staging_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_blocked"
    digest = next(check for check in gate.checks if check.name == "path_set_digests_match_owner_packet")
    assert digest.status == "failed"


def test_owner_post_stage_commit_gate_blocks_ordered_command_digest_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_command_audit_path"].read_text(encoding="utf-8"))
    payload["command_digest"] = "1" * 64
    paths["owner_command_audit_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_blocked"
    digest = next(check for check in gate.checks if check.name == "ordered_stage_digests_match_owner_packet")
    assert digest.status == "failed"


def test_owner_post_stage_commit_gate_accepts_post_staging_decision_brief_refresh(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_decision_brief_path"].read_text(encoding="utf-8"))
    payload.update(
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "summary": {
                "post_staging_status": "owner_post_staging_verification_ready",
                "cached_staged_path_count": len(_stage_paths()),
            },
            "checks": [
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_commands_match_manifest", "status": "failed"},
                {"name": "post_staging_not_yet_applied", "status": "failed"},
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "task_board_ready", "status": "failed"},
            ],
        }
    )
    paths["owner_decision_brief_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_ready"
    decision = next(check for check in gate.checks if check.name == "owner_decision_brief_pre_stage_ready")
    assert decision.status == "passed"
    assert decision.details["status"] == "blocked_before_owner_staging_decision"
    assert decision.details["post_staging_status"] == "owner_post_staging_verification_ready"
    assert gate.summary["blocking_reasons"] == []


def test_owner_post_stage_commit_gate_accounts_for_stale_decision_brief_from_post_staging_verifier(
    tmp_path: Path,
) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_decision_brief_path"].read_text(encoding="utf-8"))
    payload.update(
        {
            "status": "blocked_before_owner_staging_decision",
            "mutation_performed": False,
            "git_stage_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_mutation_performed": False,
            "agent_execution_enabled": False,
            "summary": {},
            "checks": [
                {"name": "owner_preflight_ready", "status": "failed"},
                {"name": "owner_pre_stage_readiness_gate_ready", "status": "failed"},
                {"name": "owner_approval_boundary_accounted_for", "status": "failed"},
                {"name": "stage_commands_match_manifest", "status": "failed"},
                {"name": "post_staging_not_yet_applied", "status": "failed"},
            ],
        }
    )
    paths["owner_decision_brief_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_ready"
    decision = next(check for check in gate.checks if check.name == "owner_decision_brief_pre_stage_ready")
    assert decision.status == "passed"
    assert decision.details["status"] == "blocked_before_owner_staging_decision"
    assert decision.details["post_staging_status"] == "owner_post_staging_verification_ready"
    assert decision.details["cached_staged_path_count"] == len(_stage_paths())


def test_owner_post_stage_commit_gate_accepts_post_commit_noop_evidence(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    empty_digest = _digest_values([])
    for key in ("owner_packet_path", "owner_command_audit_path"):
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
                "command_path_digest": empty_digest,
                "expected_path_digest": empty_digest,
                "owner_packet_stage_path_digest": empty_digest,
                "command_digest": empty_digest,
                "owner_packet_stage_command_digest": empty_digest,
                "summary": {"post_commit_noop_accounted_for": True},
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
    brief = json.loads(paths["owner_decision_brief_path"].read_text(encoding="utf-8"))
    brief.update(
        {
            "status": "blocked_before_owner_staging_decision",
            "summary": {},
            "checks": [{"name": "post_staging_not_yet_applied", "status": "failed"}],
        }
    )
    paths["owner_decision_brief_path"].write_text(json.dumps(brief), encoding="utf-8")
    task_board = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    task_board.update(
        {
            "status": "commercial_delivery_blocked",
            "summary": {
                **task_board["summary"],
                "owner_post_stage_commit_gate_status": "owner_post_stage_commit_gate_ready",
                "owner_commit_packet_status": "owner_commit_packet_ready",
            },
        }
    )
    paths["task_board_path"].write_text(json.dumps(task_board), encoding="utf-8")

    gate = build_owner_post_stage_commit_gate(**paths)

    assert gate.status == "owner_post_stage_commit_gate_ready"
    assert gate.commit_allowed is True
    assert gate.summary["post_commit_noop_accounted_for"] is True
    assert gate.summary["task_board_post_commit_noop_accounted_for"] is True
    assert gate.summary["expected_stage_path_set_digest"] == empty_digest
    assert gate.summary["cached_staged_path_set_digest"] == empty_digest
    assert next(check for check in gate.checks if check.name == "stage_counts_agree").status == "passed"
    task_board_check = next(check for check in gate.checks if check.name == "task_board_ready")
    assert task_board_check.status == "passed"
    assert task_board_check.details["task_board_post_commit_noop_accounted_for"] is True
