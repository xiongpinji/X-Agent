from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_delivery_packet import (
    build_owner_delivery_packet,
    render_markdown_packet,
    write_markdown_packet,
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


def _write_reports(
    reports_dir: Path,
    *,
    stage_count: int = 2,
    secondary_pending_count: int = 0,
    secondary_pending_blocks_owner_staging: bool = False,
    post_stage: bool = False,
) -> dict[str, Path]:
    paths = {
        "manifest_path": reports_dir / "manifest.json",
        "owner_staging_packet_path": reports_dir / "owner-staging-packet.json",
        "owner_staging_runbook_path": reports_dir / "owner-staging-runbook.json",
        "owner_pre_stage_gate_path": reports_dir / "owner-pre-stage-gate.json",
        "owner_post_stage_commit_gate_path": reports_dir / "owner-post-stage-commit-gate.json",
        "owner_commit_packet_path": reports_dir / "owner-commit-packet.json",
        "owner_stage_approval_gate_path": reports_dir / "owner-stage-approval-gate.json",
        "owner_stage_approval_request_path": reports_dir / "owner-stage-approval-request.json",
        "owner_stage_execution_plan_path": reports_dir / "owner-stage-execution-plan.json",
        "owner_staging_rollback_plan_path": reports_dir / "owner-staging-rollback-plan.json",
        "refresh_chain_path": reports_dir / "refresh-chain.json",
        "task_board_path": reports_dir / "task-board.json",
        "control_modes_preservation_path": reports_dir / "control-modes-preservation.json",
    }
    stage_commands = [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ][:stage_count]
    stage_paths = ["backend/app/core/storage.py", "tests/test_storage.py"][:stage_count]
    pre_stage_commands = [
        "python scripts\\commercial_delivery_refresh_chain_receipt.py",
        "python scripts\\commercial_delivery_owner_staging_preflight.py",
    ]
    post_stage_commands = [
        "git diff --cached --name-only",
        "python scripts\\commercial_delivery_owner_post_staging_verifier.py",
        "python scripts\\commercial_delivery_owner_post_stage_commit_gate.py",
        "python scripts\\commercial_delivery_owner_commit_packet.py",
    ]
    commit_preview = 'git commit -m "chore: prepare X-Agent commercial delivery package"'
    _write_json(
        paths["manifest_path"],
        {
            "status": "original_kernel_delivery_manifest_ready",
            "stage_include_count": stage_count,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_include_count": stage_count,
            "stage_path_digest": _digest_values(stage_paths),
            "stage_command_digest": _digest_values(stage_commands),
            "stage_paths": stage_paths,
            "stage_commands": stage_commands,
            "pre_stage_verification_commands": pre_stage_commands,
            "post_stage_verification_commands": post_stage_commands,
            "commit_command_preview": commit_preview,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_staging_runbook_path"],
        {
            "status": "owner_staging_runbook_blocked" if post_stage else "owner_staging_runbook_ready",
            "owner_gated": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_pre_stage_gate_path"],
        {
            "status": "owner_pre_stage_readiness_blocked" if post_stage else "owner_pre_stage_readiness_ready",
            "owner_gated": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_stage_commit_gate_path"],
        {
            "status": "owner_post_stage_commit_gate_ready" if post_stage else "owner_post_stage_commit_gate_blocked",
            "owner_gated": True,
            "commit_allowed": post_stage,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_commit_packet_path"],
        {
            "status": "owner_commit_packet_ready" if post_stage else "owner_commit_packet_blocked",
            "owner_gated": True,
            "commit_allowed": post_stage,
            "commit_command_preview": commit_preview,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["refresh_chain_path"],
        {
            "status": "commercial_delivery_refresh_chain_receipt_ready",
            "summary": {
                "step_count": 13,
                "expected_nonzero_steps": [
                    "owner_staging_preflight" if post_stage else "owner_post_staging_verifier",
                    "owner_decision_brief" if post_stage else "owner_stage_approval_gate",
                    "owner_pre_stage_readiness_gate" if post_stage else "owner_post_stage_commit_gate",
                    "owner_staging_runbook" if post_stage else "owner_commit_packet",
                ],
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_ready" if post_stage else "owner_stage_approval_blocked",
            "owner_gated": True,
            "stage_allowed": post_stage,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_stage_approval_request_path"],
        {
            "status": "owner_stage_approval_request_ready",
            "owner_gated": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": stage_count,
                "owner_stage_command_count": stage_count,
                "owner_stage_approval_gate_status": (
                    "owner_stage_approval_ready" if post_stage else "owner_stage_approval_blocked"
                ),
                "stage_allowed": post_stage,
            },
        },
    )
    _write_json(
        paths["owner_stage_execution_plan_path"],
        {
            "status": "owner_stage_execution_ready" if post_stage else "owner_stage_execution_blocked",
            "owner_gated": True,
            "stage_allowed": post_stage,
            "stage_command_count": stage_count,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_command_count": stage_count,
                "owner_stage_approval_gate_status": (
                    "owner_stage_approval_ready" if post_stage else "owner_stage_approval_blocked"
                ),
                "stage_allowed": post_stage,
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
            "reset_command_count": stage_count,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["task_board_path"],
        {
            "status": "commercial_delivery_ready_for_owner_staging_review",
            "summary": {
                "secondary_pending_count": secondary_pending_count,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "secondary_pending_blocks_owner_staging": secondary_pending_blocks_owner_staging,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["control_modes_preservation_path"],
        {
            "status": "control_modes_preservation_ready",
            "summary": {
                "plan_only_default": True,
                "loop_phases": ["explore", "plan", "edit", "verify", "deliver"],
                "control_surface_file_count": 12,
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_delivery_packet_ready_for_pre_stage_owner_review(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert packet.evidence_type == "commercial_delivery_owner_delivery_packet"
    assert packet.owner_gated is True
    assert packet.mutation_performed is False
    assert packet.git_stage_performed is False
    assert packet.git_commit_performed is False
    assert packet.git_push_performed is False
    assert packet.network_mutation_performed is False
    assert packet.agent_execution_enabled is False
    assert packet.full_codex_parity_claimed is False
    assert packet.stage_ready is True
    assert packet.commit_ready is False
    assert packet.owner_approval_required is True
    assert packet.summary["stage_include_count"] == 2
    assert packet.summary["owner_stage_command_count"] == 2
    assert packet.summary["stage_path_digest"] == _digest_values([
        "backend/app/core/storage.py",
        "tests/test_storage.py",
    ])
    assert packet.summary["expected_stage_path_set_digest"] == _path_set_digest([
        "backend/app/core/storage.py",
        "tests/test_storage.py",
    ])
    assert packet.summary["stage_command_digest"] == _digest_values([
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ])
    assert packet.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert packet.summary["owner_stage_approval_request_status"] == "owner_stage_approval_request_ready"
    assert packet.summary["owner_stage_execution_plan_status"] == "owner_stage_execution_blocked"
    assert packet.summary["owner_staging_rollback_plan_status"] == "owner_staging_rollback_plan_ready"
    assert packet.summary["stage_allowed"] is False
    assert packet.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert packet.summary["owner_stage_execution_allowed"] is False
    assert packet.summary["rollback_available"] is True
    assert packet.summary["rollback_reset_command_count"] == 2
    assert packet.summary["owner_commit_packet_status"] == "owner_commit_packet_blocked"
    assert packet.summary["secondary_pending_count"] == 0
    assert packet.summary["secondary_handoff_completed_count"] == 44
    assert packet.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert packet.summary["control_modes_preservation_status"] == "control_modes_preservation_ready"
    assert packet.summary["control_modes_plan_only_default"] is True
    assert packet.summary["control_modes_loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert packet.summary["control_modes_surface_file_count"] == 12
    assert [section.name for section in packet.sections] == [
        "pre_stage_verification",
        "owner_stage_commands",
        "post_stage_verification",
        "commit_preview",
    ]
    assert {check.status for check in packet.checks} == {"passed"}


def test_owner_delivery_packet_ready_after_owner_staging_with_post_stage_evidence(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, post_stage=True, secondary_pending_count=2)

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert packet.stage_ready is True
    assert packet.commit_ready is True
    assert packet.summary["strict_stage_ready"] is False
    assert packet.summary["post_stage_chain_accounted_for"] is True
    assert packet.summary["owner_staging_runbook_status"] == "owner_staging_runbook_blocked"
    assert packet.summary["owner_pre_stage_gate_status"] == "owner_pre_stage_readiness_blocked"
    assert packet.summary["owner_commit_packet_status"] == "owner_commit_packet_ready"
    assert packet.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_ready"
    assert packet.summary["owner_stage_execution_plan_status"] == "owner_stage_execution_ready"
    assert next(check for check in packet.checks if check.name == "owner_pre_stage_chain_ready").status == "passed"


def test_owner_delivery_packet_blocks_post_stage_pre_stage_reports_without_commit_evidence(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, post_stage=True)
    commit_packet = json.loads(paths["owner_commit_packet_path"].read_text(encoding="utf-8"))
    commit_packet["status"] = "owner_commit_packet_blocked"
    commit_packet["commit_allowed"] = False
    paths["owner_commit_packet_path"].write_text(json.dumps(commit_packet), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert packet.summary["post_stage_chain_accounted_for"] is False
    assert next(check for check in packet.checks if check.name == "owner_pre_stage_chain_ready").status == "failed"


def test_owner_delivery_packet_blocks_missing_report(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    paths["owner_staging_runbook_path"].unlink()

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(check for check in packet.checks if check.name == "reports_readable").status == "failed"
    assert next(check for check in packet.checks if check.name == "owner_pre_stage_chain_ready").status == "failed"


def test_owner_delivery_packet_blocks_stage_count_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, stage_count=2)
    payload = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    payload["stage_include_count"] = 3
    paths["manifest_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(check for check in packet.checks if check.name == "stage_command_count_matches_manifest").status == "failed"


def test_owner_delivery_packet_blocks_missing_stage_digest(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_staging_packet_path"].read_text(encoding="utf-8"))
    payload.pop("stage_path_digest")
    paths["owner_staging_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(check for check in packet.checks if check.name == "stage_digests_present").status == "failed"


def test_owner_delivery_packet_blocks_missing_stage_paths_for_path_set_digest(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_staging_packet_path"].read_text(encoding="utf-8"))
    payload.pop("stage_paths")
    paths["owner_staging_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(check for check in packet.checks if check.name == "stage_digests_present").status == "failed"


def test_owner_delivery_packet_blocks_unaccounted_pre_stage_commit_packet(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["summary"]["expected_nonzero_steps"] = ["owner_post_staging_verifier"]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(
        check for check in packet.checks if check.name == "pre_stage_post_stage_blockers_are_expected"
    ).status == "failed"


def test_owner_delivery_packet_accepts_delivery_self_bootstrap_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["summary"]["expected_nonzero_steps"] = ["owner_post_staging_verifier"]
    payload["steps"] = [
        {"name": "owner_delivery_packet_before_owner_approval", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert next(check for check in packet.checks if check.name == "refresh_chain_ready").status == "passed"
    blocker_check = next(
        check for check in packet.checks if check.name == "pre_stage_post_stage_blockers_are_expected"
    )
    assert blocker_check.status == "passed"
    assert blocker_check.details["refresh_delivery_bootstrap"] is True


def test_owner_delivery_packet_accepts_post_stage_chain_during_delivery_self_bootstrap(
    tmp_path: Path,
) -> None:
    paths = _write_reports(tmp_path, post_stage=True)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["summary"]["expected_nonzero_steps"] = [
        "owner_staging_preflight",
        "owner_decision_brief",
    ]
    payload["steps"] = [
        {"name": "owner_delivery_packet_before_owner_approval", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert packet.stage_ready is True
    assert packet.summary["post_stage_chain_accounted_for"] is True
    check = next(check for check in packet.checks if check.name == "owner_pre_stage_chain_ready")
    assert check.status == "passed"
    assert check.details["refresh_delivery_bootstrap"] is True


def test_owner_delivery_packet_accepts_pre_stage_self_bootstrap_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["summary"]["expected_nonzero_steps"] = ["owner_post_staging_verifier"]
    payload["steps"] = [
        {"name": "owner_pre_stage_readiness_gate", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert next(check for check in packet.checks if check.name == "refresh_chain_ready").status == "passed"
    blocker_check = next(
        check for check in packet.checks if check.name == "pre_stage_post_stage_blockers_are_expected"
    )
    assert blocker_check.status == "passed"
    assert blocker_check.details["refresh_delivery_bootstrap"] is True


def test_owner_delivery_packet_accepts_stage_execution_self_bootstrap_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, post_stage=True)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_stage_execution_plan", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert next(check for check in packet.checks if check.name == "refresh_chain_ready").status == "passed"


def test_owner_delivery_packet_blocks_other_failed_refresh_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["refresh_chain_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_command_audit", "status": "failed"},
    ]
    paths["refresh_chain_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(check for check in packet.checks if check.name == "refresh_chain_ready").status == "failed"


def test_owner_delivery_packet_allows_missing_optional_stage_reports(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    paths["owner_stage_approval_request_path"].unlink()
    paths["owner_stage_execution_plan_path"].unlink()
    paths["owner_staging_rollback_plan_path"].unlink()

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert packet.summary["owner_stage_approval_request_missing"] is True
    assert packet.summary["owner_stage_execution_plan_missing"] is True
    assert packet.summary["owner_staging_rollback_plan_missing"] is True
    assert next(
        check for check in packet.checks if check.name == "owner_stage_approval_request_accounted_for"
    ).status == "passed"
    assert next(
        check for check in packet.checks if check.name == "owner_stage_execution_plan_accounted_for"
    ).status == "passed"
    assert next(
        check for check in packet.checks if check.name == "owner_staging_rollback_plan_accounted_for"
    ).status == "passed"


def test_owner_delivery_packet_blocks_unknown_stage_execution_plan(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_stage_execution_plan_path"].read_text(encoding="utf-8"))
    payload["status"] = "owner_stage_execution_unknown"
    paths["owner_stage_execution_plan_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(
        check for check in packet.checks if check.name == "owner_stage_execution_plan_accounted_for"
    ).status == "failed"


def test_owner_delivery_packet_blocks_unknown_rollback_plan(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_staging_rollback_plan_path"].read_text(encoding="utf-8"))
    payload["status"] = "owner_staging_rollback_plan_unknown"
    paths["owner_staging_rollback_plan_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert next(
        check for check in packet.checks if check.name == "owner_staging_rollback_plan_accounted_for"
    ).status == "failed"


def test_owner_delivery_packet_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["full_codex_parity_claimed"] = True
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    assert packet.full_codex_parity_claimed is True
    assert next(check for check in packet.checks if check.name == "no_full_codex_parity_claim").status == "failed"


def test_owner_delivery_packet_allows_secondary_pending_when_task_board_does_not_block(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path, secondary_pending_count=2)

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_ready"
    assert packet.summary["secondary_pending_count"] == 2
    secondary_check = next(
        check for check in packet.checks if check.name == "secondary_pending_does_not_block_owner_review"
    )
    assert secondary_check.status == "passed"
    assert secondary_check.details["secondary_pending_blocks_owner_staging"] is False


def test_owner_delivery_packet_blocks_when_secondary_pending_blocks_owner_review(tmp_path: Path) -> None:
    paths = _write_reports(
        tmp_path,
        secondary_pending_count=2,
        secondary_pending_blocks_owner_staging=True,
    )

    packet = build_owner_delivery_packet(**paths)

    assert packet.status == "owner_delivery_packet_blocked"
    secondary_check = next(
        check for check in packet.checks if check.name == "secondary_pending_does_not_block_owner_review"
    )
    assert secondary_check.status == "failed"
    assert secondary_check.details["secondary_pending_count"] == 2
    assert secondary_check.details["secondary_pending_blocks_owner_staging"] is True


def test_owner_delivery_packet_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    packet = build_owner_delivery_packet(**paths)
    json_output = tmp_path / "delivery-packet.json"
    md_output = tmp_path / "delivery-packet.md"

    write_report(packet, json_output)
    write_markdown_packet(packet, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_delivery_packet_ready"
    assert "Commercial Delivery Owner Delivery Packet" in markdown
    assert "Owner-approved stage commands" in render_markdown_packet(packet)
