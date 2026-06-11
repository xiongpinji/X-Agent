from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_stage_execution_plan import (
    build_owner_stage_execution_plan,
    render_markdown_plan,
    write_markdown_plan,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str:
    return _digest_values(sorted(set(paths)))


def _write_inputs(
    tmp_path: Path,
    *,
    approval_ready: bool = False,
    post_stage: bool = False,
) -> dict[str, Path]:
    paths = {
        "owner_staging_packet_path": tmp_path / "owner-staging-packet.json",
        "owner_staging_preflight_path": tmp_path / "owner-staging-preflight.json",
        "owner_stage_approval_gate_path": tmp_path / "owner-stage-approval-gate.json",
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
    }
    stage_commands = [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]
    stage_paths = ["backend/app/core/storage.py", "tests/test_storage.py"]
    stage_path_digest = _digest_values(stage_paths)
    stage_command_digest = _digest_values(stage_commands)
    expected_stage_path_set_digest = _path_set_digest(stage_paths)
    _write_json(
        paths["owner_staging_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_commands": stage_commands,
            "stage_paths": stage_paths,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_preflight_path"],
        {
            "status": "owner_staging_preflight_blocked" if post_stage else "owner_staging_preflight_ready",
            "stage_command_count": 2,
            "cached_staged_path_count": 2 if post_stage else 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_ready" if approval_ready else "owner_stage_approval_blocked",
            "stage_allowed": approval_ready,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
            },
        },
    )
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "stage_ready": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "stage_path_digest": stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
            },
        },
    )
    return paths


def test_stage_execution_plan_blocks_until_approval_gate_ready(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert plan.evidence_type == "commercial_delivery_owner_stage_execution_plan"
    assert plan.owner_gated is True
    assert plan.mutation_performed is False
    assert plan.git_stage_performed is False
    assert plan.git_commit_performed is False
    assert plan.git_push_performed is False
    assert plan.network_mutation_performed is False
    assert plan.agent_execution_enabled is False
    assert plan.full_codex_parity_claimed is False
    assert plan.stage_allowed is False
    assert plan.stage_ready is True
    assert plan.stage_command_count == 2
    assert plan.planned_stage_commands == []
    assert plan.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert plan.summary["stage_allowed"] is False
    assert plan.summary["owner_action_required"] is True
    assert plan.summary["blocking_reasons"] == ["approval_gate_ready"]
    assert next(check for check in plan.checks if check.name == "approval_gate_ready").status == "failed"


def test_stage_execution_plan_ready_with_approved_gate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_ready"
    assert plan.stage_allowed is True
    assert plan.planned_stage_commands == [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]
    assert plan.stage_path_digest == _digest_values(["backend/app/core/storage.py", "tests/test_storage.py"])
    assert plan.stage_command_digest == _digest_values(plan.planned_stage_commands)
    assert plan.summary["stage_path_digest"] == plan.stage_path_digest
    assert plan.summary["stage_command_digest"] == plan.stage_command_digest
    assert plan.summary["expected_stage_path_set_digest"] == _path_set_digest([
        "backend/app/core/storage.py",
        "tests/test_storage.py",
    ])
    assert plan.summary["secondary_pending_count"] == 0
    assert plan.summary["secondary_handoff_next_count"] == 1
    assert plan.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert plan.summary["secondary_handoff_completed_count"] == 44
    assert plan.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert plan.summary["owner_action_required"] is False
    assert plan.summary["blocking_reasons"] == []
    assert {check.status for check in plan.checks} == {"passed"}


def test_stage_execution_plan_allows_subset_eligible_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    delivery_packet = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    delivery_packet["summary"]["stage_include_count"] = 100
    delivery_packet["summary"]["owner_stage_command_count"] = 2
    paths["owner_delivery_packet_path"].write_text(json.dumps(delivery_packet), encoding="utf-8")
    approval_gate = json.loads(paths["owner_stage_approval_gate_path"].read_text(encoding="utf-8"))
    approval_gate["summary"]["stage_include_count"] = 100
    approval_gate["summary"]["owner_stage_command_count"] = 2
    paths["owner_stage_approval_gate_path"].write_text(json.dumps(approval_gate), encoding="utf-8")

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_ready"
    assert plan.summary["delivery_stage_include_count"] == 100
    assert plan.summary["delivery_owner_stage_command_count"] == 2
    assert plan.summary["approval_stage_include_count"] == 100
    assert plan.summary["approval_owner_stage_command_count"] == 2
    assert next(check for check in plan.checks if check.name == "stage_command_counts_match").status == "passed"
    assert next(check for check in plan.checks if check.name == "approval_count_matches_stage_commands").status == "passed"


def test_stage_execution_plan_ready_after_stage_execution_with_verified_cached_index(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True, post_stage=True)

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_ready"
    assert plan.stage_allowed is True
    assert plan.stage_ready is True
    assert plan.summary["strict_stage_ready"] is False
    assert plan.summary["post_stage_accounted_for"] is True
    assert plan.planned_stage_commands == [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]
    assert next(
        check for check in plan.checks if check.name == "owner_staging_preflight_accounted_for"
    ).status == "passed"
    assert next(
        check for check in plan.checks if check.name == "no_cached_staged_paths_before_stage_execution_or_accounted"
    ).status == "passed"


def test_stage_execution_plan_blocks_post_stage_cached_index_without_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=False, post_stage=True)

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert plan.summary["post_stage_accounted_for"] is False
    assert next(check for check in plan.checks if check.name == "approval_gate_ready").status == "failed"
    assert next(
        check for check in plan.checks if check.name == "no_cached_staged_paths_before_stage_execution_or_accounted"
    ).status == "failed"


def test_stage_execution_plan_blocks_approval_path_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    approval_gate = json.loads(paths["owner_stage_approval_gate_path"].read_text(encoding="utf-8"))
    approval_gate["summary"]["stage_path_digest"] = "0" * 64
    paths["owner_stage_approval_gate_path"].write_text(json.dumps(approval_gate), encoding="utf-8")

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert next(
        check for check in plan.checks if check.name == "stage_path_digest_matches_execution_surface"
    ).status == "failed"
    assert plan.planned_stage_commands == []


def test_stage_execution_plan_blocks_staging_command_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    packet = json.loads(paths["owner_staging_packet_path"].read_text(encoding="utf-8"))
    packet["stage_command_digest"] = "1" * 64
    paths["owner_staging_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert next(
        check for check in plan.checks if check.name == "stage_command_digest_matches_execution_surface"
    ).status == "failed"
    assert plan.planned_stage_commands == []


def test_stage_execution_plan_blocks_expected_path_set_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    approval_gate = json.loads(paths["owner_stage_approval_gate_path"].read_text(encoding="utf-8"))
    approval_gate["summary"]["expected_stage_path_set_digest"] = "0" * 64
    paths["owner_stage_approval_gate_path"].write_text(json.dumps(approval_gate), encoding="utf-8")

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert next(
        check for check in plan.checks if check.name == "expected_stage_path_set_digest_matches_execution_surface"
    ).status == "failed"
    assert plan.planned_stage_commands == []


def test_stage_execution_plan_blocks_count_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    packet = json.loads(paths["owner_staging_packet_path"].read_text(encoding="utf-8"))
    packet["stage_commands"].append("git add -- 'tests/test_extra.py'")
    paths["owner_staging_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert next(check for check in plan.checks if check.name == "stage_command_counts_match").status == "failed"
    assert next(check for check in plan.checks if check.name == "approval_count_matches_stage_commands").status == "failed"
    assert plan.planned_stage_commands == []


def test_stage_execution_plan_blocks_nonempty_cached_index(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    preflight = json.loads(paths["owner_staging_preflight_path"].read_text(encoding="utf-8"))
    preflight["cached_staged_path_count"] = 1
    paths["owner_staging_preflight_path"].write_text(json.dumps(preflight), encoding="utf-8")

    plan = build_owner_stage_execution_plan(**paths)

    assert plan.status == "owner_stage_execution_blocked"
    assert next(
        check for check in plan.checks if check.name == "no_cached_staged_paths_before_stage_execution_or_accounted"
    ).status == "failed"


def test_stage_execution_plan_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_ready=True)
    plan = build_owner_stage_execution_plan(**paths)
    json_output = tmp_path / "plan.json"
    md_output = tmp_path / "plan.md"

    write_report(plan, json_output)
    write_markdown_plan(plan, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_stage_execution_ready"
    assert payload["planned_stage_commands_count"] == len(payload["planned_stage_commands"]) == len(plan.planned_stage_commands)
    assert payload["checks_count"] == len(payload["checks"]) == len(plan.checks)
    assert payload["next_actions_count"] == len(plan.next_actions)
    assert payload["known_limits_count"] == len(plan.known_limits)
    assert payload["summary"]["blocking_reasons"] == []
    assert payload["summary"]["owner_action_required"] is False
    assert "Commercial Delivery Owner Stage Execution Plan" in markdown
    assert "Owner action required: `false`" in markdown
    assert "Blocking reasons: ``" in markdown
    assert "git add -- 'backend/app/core/storage.py'" in render_markdown_plan(plan)
