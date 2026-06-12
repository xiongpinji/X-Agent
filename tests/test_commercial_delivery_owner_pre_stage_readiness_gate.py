from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_delivery_owner_pre_stage_readiness_gate import (
    build_owner_pre_stage_readiness_gate,
    render_markdown_gate,
    write_markdown_gate,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_reports(reports_dir: Path, *, secondary_pending_count: int = 2) -> dict[str, Path]:
    pending_paths = [
        "backend/app/core/integration_review_answer_action_matrix.py",
        "tests/test_integration_review_answer_action_matrix.py",
    ][:secondary_pending_count]
    paths = {
        "manifest_path": reports_dir / "manifest.json",
        "staging_review_path": reports_dir / "staging-review.json",
        "owner_packet_path": reports_dir / "owner-packet.json",
        "owner_preflight_path": reports_dir / "owner-preflight.json",
        "owner_post_staging_path": reports_dir / "owner-post-staging.json",
        "refresh_receipt_path": reports_dir / "refresh-receipt.json",
        "owner_command_audit_path": reports_dir / "owner-command-audit.json",
        "owner_decision_brief_path": reports_dir / "owner-decision-brief.json",
        "owner_approval_handoff_path": reports_dir / "owner-approval-handoff.json",
        "pre_approval_drift_guard_path": reports_dir / "pre-approval-drift-guard.json",
        "owner_approval_resume_packet_path": reports_dir / "owner-approval-resume-packet.json",
        "owner_post_approval_operator_checklist_path": reports_dir / "owner-post-approval-operator-checklist.json",
        "task_board_path": reports_dir / "task-board.json",
    }
    _write_json(
        paths["manifest_path"],
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
        paths["staging_review_path"],
        {
            "status": "staging_review_ready",
            "owner_gated": True,
            "stage_include_count": 2,
            "eligible_stage_count": 2,
            "blocked_stage_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_packet_path"],
        {
            "status": "owner_staging_packet_ready",
            "owner_gated": True,
            "stage_include_count": 2,
            "eligible_stage_count": 2,
            "stage_commands": [
                "git add -- 'backend/app/core/storage.py'",
                "git add -- 'tests/test_storage.py'",
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_preflight_path"],
        {
            "status": "owner_staging_preflight_ready",
            "owner_gated": True,
            "stage_command_count": 2,
            "stage_path_count": 2,
            "cached_staged_path_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_staging_path"],
        {
            "status": "owner_post_staging_verification_blocked",
            "owner_gated": True,
            "cached_staged_path_count": 0,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["refresh_receipt_path"],
        {
            "status": "commercial_delivery_refresh_chain_receipt_ready",
            "summary": {
                "failed_step_count": 0,
                "expected_nonzero_step_count": 1,
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_command_audit_path"],
        {
            "status": "owner_command_audit_ready",
            "owner_gated": True,
            "command_count": 2,
            "expected_path_count": 2,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_decision_brief_path"],
        {
            "status": "ready_for_owner_staging_decision",
            "owner_gated": True,
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
    _write_json(
        paths["owner_approval_handoff_path"],
        {
            "status": "owner_approval_handoff_ready",
            "owner_gated": True,
            "owner_action_required": True,
            "stage_allowed": False,
            "summary": {
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_waiting_for_owner"
                ),
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["pre_approval_drift_guard_path"],
        {
            "status": "pre_approval_drift_guard_ready",
            "owner_gated": True,
            "real_owner_approval_present": False,
            "summary": {
                "owner_post_approval_operator_checklist_status": (
                    "owner_post_approval_operator_checklist_waiting_for_owner"
                ),
            },
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_resume_packet_path"],
        {
            "status": "owner_approval_resume_packet_waiting_for_owner",
            "owner_gated": True,
            "waiting_for_owner": True,
            "resume_ready": False,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_post_approval_operator_checklist_path"],
        {
            "status": "owner_post_approval_operator_checklist_waiting_for_owner",
            "owner_gated": True,
            "waiting_for_owner": True,
            "operator_ready": False,
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
                "secondary_pending_blocks_owner_staging": False,
                "refresh_chain_receipt_status": "commercial_delivery_refresh_chain_receipt_ready",
            },
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_pre_stage_readiness_gate_ready(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_ready"
    assert gate.evidence_type == "commercial_delivery_owner_pre_stage_readiness_gate"
    assert gate.owner_gated is True
    assert gate.mutation_performed is False
    assert gate.git_stage_performed is False
    assert gate.git_commit_performed is False
    assert gate.git_push_performed is False
    assert gate.network_mutation_performed is False
    assert gate.agent_execution_enabled is False
    assert gate.full_codex_parity_claimed is False
    assert gate.summary["stage_include_count"] == 2
    assert gate.summary["stage_command_count"] == 2
    assert gate.summary["secondary_pending_count"] == 2
    assert gate.summary["secondary_handoff_next_count"] == 1
    assert gate.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert gate.summary["secondary_handoff_completed_count"] == 44
    assert gate.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert gate.summary["decision_brief_secondary_handoff_completed_count"] == 44
    assert (
        gate.summary["decision_brief_secondary_handoff_latest_completed_candidate"]
        == "integration_review_answer_action_matrix.py"
    )
    assert gate.summary["refresh_chain_receipt_status"] == "commercial_delivery_refresh_chain_receipt_ready"
    assert gate.summary["owner_post_staging_status"] == "owner_post_staging_verification_blocked"
    assert gate.summary["owner_approval_handoff_status"] == "owner_approval_handoff_ready"
    assert gate.summary["pre_approval_drift_guard_status"] == "pre_approval_drift_guard_ready"
    assert gate.summary["owner_approval_resume_packet_status"] == "owner_approval_resume_packet_waiting_for_owner"
    assert gate.summary["owner_approval_resume_packet_waiting_for_owner"] is True
    assert gate.summary["owner_approval_resume_packet_resume_ready"] is False
    assert gate.summary["owner_post_approval_operator_checklist_status"] == (
        "owner_post_approval_operator_checklist_waiting_for_owner"
    )
    assert gate.summary["owner_post_approval_operator_checklist_waiting_for_owner"] is True
    assert gate.summary["owner_post_approval_operator_checklist_operator_ready"] is False
    secondary_check = next(check for check in gate.checks if check.name == "secondary_pending_does_not_block_owner_stage")
    assert secondary_check.details["task_board_secondary_handoff_completed_count"] == 44
    assert secondary_check.details["decision_brief_secondary_handoff_completed_count"] == 44
    assert {check.status for check in gate.checks} == {"passed"}


def test_owner_pre_stage_readiness_gate_allows_subset_eligible_stage_commands(
    tmp_path: Path,
) -> None:
    paths = _write_reports(tmp_path)
    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    manifest["stage_include_count"] = 100
    paths["manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")
    staging_review = json.loads(paths["staging_review_path"].read_text(encoding="utf-8"))
    staging_review["stage_include_count"] = 100
    staging_review["eligible_stage_count"] = 2
    paths["staging_review_path"].write_text(json.dumps(staging_review), encoding="utf-8")
    owner_packet = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    owner_packet["stage_include_count"] = 100
    owner_packet["eligible_stage_count"] = 2
    paths["owner_packet_path"].write_text(json.dumps(owner_packet), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_ready"
    assert gate.summary["stage_include_count"] == 100
    assert gate.summary["stage_command_count"] == 2
    count_check = next(check for check in gate.checks if check.name == "stage_counts_agree")
    assert count_check.status == "passed"
    assert count_check.details["manifest_stage_include_count"] == 100
    assert count_check.details["staging_review_eligible_stage_count"] == 2
    assert count_check.details["owner_packet_stage_command_count"] == 2


def test_owner_pre_stage_readiness_gate_accepts_post_commit_noop_stage(
    tmp_path: Path,
) -> None:
    paths = _write_reports(tmp_path)
    noop_digest = "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"

    staging_review = json.loads(paths["staging_review_path"].read_text(encoding="utf-8"))
    staging_review["stage_include_count"] = 100
    staging_review["eligible_stage_count"] = 0
    paths["staging_review_path"].write_text(json.dumps(staging_review), encoding="utf-8")

    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    manifest["stage_include_count"] = 100
    paths["manifest_path"].write_text(json.dumps(manifest), encoding="utf-8")

    owner_packet = json.loads(paths["owner_packet_path"].read_text(encoding="utf-8"))
    owner_packet["stage_include_count"] = 100
    owner_packet["eligible_stage_count"] = 0
    owner_packet["stage_commands"] = []
    owner_packet["summary"] = {
        "post_commit_noop_accounted_for": True,
        "stage_path_digest": noop_digest,
        "stage_command_digest": noop_digest,
        "expected_stage_path_set_digest": noop_digest,
    }
    paths["owner_packet_path"].write_text(json.dumps(owner_packet), encoding="utf-8")

    owner_preflight = json.loads(paths["owner_preflight_path"].read_text(encoding="utf-8"))
    owner_preflight["stage_command_count"] = 0
    owner_preflight["stage_path_count"] = 0
    owner_preflight["cached_staged_path_count"] = 0
    paths["owner_preflight_path"].write_text(json.dumps(owner_preflight), encoding="utf-8")

    owner_post_staging = json.loads(paths["owner_post_staging_path"].read_text(encoding="utf-8"))
    owner_post_staging["status"] = "owner_post_staging_verification_ready"
    owner_post_staging["cached_staged_path_count"] = 0
    owner_post_staging["post_commit_noop_accounted_for"] = True
    owner_post_staging["summary"] = {"post_commit_noop_accounted_for": True}
    paths["owner_post_staging_path"].write_text(json.dumps(owner_post_staging), encoding="utf-8")

    owner_command_audit = json.loads(paths["owner_command_audit_path"].read_text(encoding="utf-8"))
    owner_command_audit["command_count"] = 0
    owner_command_audit["expected_path_count"] = 0
    owner_command_audit["post_commit_noop_accounted_for"] = True
    paths["owner_command_audit_path"].write_text(json.dumps(owner_command_audit), encoding="utf-8")

    decision_brief = json.loads(paths["owner_decision_brief_path"].read_text(encoding="utf-8"))
    decision_brief["status"] = "blocked_before_owner_staging_decision"
    paths["owner_decision_brief_path"].write_text(json.dumps(decision_brief), encoding="utf-8")

    owner_approval_handoff = json.loads(paths["owner_approval_handoff_path"].read_text(encoding="utf-8"))
    owner_approval_handoff["status"] = "owner_approval_handoff_ready"
    owner_approval_handoff["stage_allowed"] = True
    paths["owner_approval_handoff_path"].write_text(json.dumps(owner_approval_handoff), encoding="utf-8")

    pre_approval_guard = json.loads(paths["pre_approval_drift_guard_path"].read_text(encoding="utf-8"))
    pre_approval_guard["status"] = "pre_approval_drift_guard_ready"
    pre_approval_guard["real_owner_approval_present"] = True
    paths["pre_approval_drift_guard_path"].write_text(json.dumps(pre_approval_guard), encoding="utf-8")

    resume_packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    resume_packet["status"] = "owner_approval_resume_packet_ready"
    resume_packet["waiting_for_owner"] = False
    resume_packet["resume_ready"] = True
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(resume_packet), encoding="utf-8")

    operator_checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    operator_checklist["status"] = "owner_post_approval_operator_checklist_ready"
    operator_checklist["waiting_for_owner"] = False
    operator_checklist["operator_ready"] = True
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(operator_checklist), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_ready"
    assert gate.summary["stage_include_count"] == 100
    assert gate.summary["stage_command_count"] == 0
    assert gate.summary["post_commit_noop_accounted_for"] is True
    assert {check.status for check in gate.checks} == {"passed"}
    post_staging_check = next(
        check for check in gate.checks if check.name == "owner_post_staging_expected_pre_stage_state"
    )
    assert post_staging_check.details["post_commit_noop_accounted_for"] is True
    count_check = next(check for check in gate.checks if check.name == "stage_counts_agree")
    assert count_check.details["post_commit_noop_stage_counts_agree"] is True


def test_owner_pre_stage_readiness_gate_blocks_missing_report(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    paths["refresh_receipt_path"].unlink()

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    assert next(check for check in gate.checks if check.name == "reports_readable").status == "failed"
    assert next(check for check in gate.checks if check.name == "refresh_chain_receipt_ready").status == "failed"


def test_owner_pre_stage_readiness_gate_blocks_stage_count_drift(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_command_audit_path"].read_text(encoding="utf-8"))
    payload["command_count"] = 1
    paths["owner_command_audit_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    assert next(check for check in gate.checks if check.name == "stage_counts_agree").status == "failed"


def test_owner_pre_stage_readiness_gate_blocks_failed_refresh_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["refresh_receipt_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_command_audit", "status": "failed"},
    ]
    paths["refresh_receipt_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    assert next(check for check in gate.checks if check.name == "refresh_chain_receipt_ready").status == "failed"


def test_owner_pre_stage_readiness_gate_blocks_owner_boundary_mismatch(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    packet = json.loads(paths["owner_approval_resume_packet_path"].read_text(encoding="utf-8"))
    packet["status"] = "owner_approval_resume_packet_ready"
    packet["waiting_for_owner"] = False
    packet["resume_ready"] = True
    paths["owner_approval_resume_packet_path"].write_text(json.dumps(packet), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    check = next(check for check in gate.checks if check.name == "owner_approval_boundary_waiting_or_ready")
    assert check.status == "failed"
    assert check.details["owner_approval_resume_packet_resume_ready"] is True
    assert check.details["operator_checklist_operator_ready"] is False


def test_owner_pre_stage_readiness_gate_blocks_operator_checklist_unknown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    checklist = json.loads(paths["owner_post_approval_operator_checklist_path"].read_text(encoding="utf-8"))
    checklist["status"] = "owner_post_approval_operator_checklist_blocked"
    paths["owner_post_approval_operator_checklist_path"].write_text(json.dumps(checklist), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    check = next(check for check in gate.checks if check.name == "operator_checklist_accounted_for")
    assert check.status == "failed"
    assert check.details["status"] == "owner_post_approval_operator_checklist_blocked"


def test_owner_pre_stage_readiness_gate_accepts_self_bootstrap_refresh_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["refresh_receipt_path"].read_text(encoding="utf-8"))
    payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
    payload["summary"]["failed_step_count"] = 1
    payload["steps"] = [
        {"name": "owner_pre_stage_readiness_gate", "status": "failed"},
    ]
    paths["refresh_receipt_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_ready"
    check = next(check for check in gate.checks if check.name == "refresh_chain_receipt_ready")
    assert check.status == "passed"
    assert check.details["failed_steps"] == ["owner_pre_stage_readiness_gate"]


def test_owner_pre_stage_readiness_gate_accepts_downstream_self_bootstrap_refresh_receipt(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    allowed_steps = [
        "owner_delivery_packet_before_owner_approval",
        "owner_delivery_packet",
        "owner_stage_approval_brief",
        "closure_snapshot",
        "owner_approval_handoff",
    ]

    for step_name in allowed_steps:
        payload = json.loads(paths["refresh_receipt_path"].read_text(encoding="utf-8"))
        payload["status"] = "commercial_delivery_refresh_chain_receipt_blocked"
        payload["summary"]["failed_step_count"] = 1
        payload["steps"] = [{"name": step_name, "status": "failed"}]
        paths["refresh_receipt_path"].write_text(json.dumps(payload), encoding="utf-8")

        gate = build_owner_pre_stage_readiness_gate(**paths)

        assert gate.status == "owner_pre_stage_readiness_ready"
        check = next(check for check in gate.checks if check.name == "refresh_chain_receipt_ready")
        assert check.status == "passed"
        assert check.details["failed_steps"] == [step_name]


def test_owner_pre_stage_readiness_gate_blocks_nonempty_index(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["owner_preflight_path"].read_text(encoding="utf-8"))
    payload["cached_staged_path_count"] = 1
    paths["owner_preflight_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    assert next(check for check in gate.checks if check.name == "git_index_empty_before_owner_stage").status == "failed"


def test_owner_pre_stage_readiness_gate_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    payload = json.loads(paths["task_board_path"].read_text(encoding="utf-8"))
    payload["full_codex_parity_claimed"] = True
    paths["task_board_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_pre_stage_readiness_gate(**paths)

    assert gate.status == "owner_pre_stage_readiness_blocked"
    assert gate.full_codex_parity_claimed is True
    assert next(check for check in gate.checks if check.name == "no_full_codex_parity_claim").status == "failed"


def test_owner_pre_stage_readiness_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_reports(tmp_path)
    gate = build_owner_pre_stage_readiness_gate(**paths)
    json_output = tmp_path / "gate.json"
    md_output = tmp_path / "gate.md"

    write_report(gate, json_output)
    write_markdown_gate(gate, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_pre_stage_readiness_ready"
    assert "Commercial Delivery Owner Pre-Stage Readiness Gate" in markdown
    assert "Owner approval resume packet" in markdown
    assert "refresh_chain_receipt_ready" in render_markdown_gate(gate)
