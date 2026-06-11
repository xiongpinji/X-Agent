from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.commercial_delivery_owner_stage_approval_gate import (
    build_owner_stage_approval_gate,
    render_markdown_gate,
    write_markdown_gate,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _commit_preview() -> str:
    return 'git commit -m "chore: prepare X-Agent commercial delivery package"'


def _stage_commands() -> list[str]:
    return [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]


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


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
        "owner_approval_payload_audit_path": tmp_path / "owner-approval-payload-audit.json",
        "owner_approval_path": tmp_path / "owner-stage-approval.json",
    }
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "stage_ready": True,
            "commit_ready": False,
            "owner_approval_required": True,
            "summary": {
                "stage_include_count": 80,
                "owner_stage_command_count": 80,
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
                "commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(),
                "stage_command_digest": _stage_command_digest(),
                "expected_stage_path_set_digest": _path_set_digest(),
            },
            "sections": [
                {
                    "name": "owner_stage_commands",
                    "commands": _stage_commands(),
                }
            ],
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_path"],
        {
            "status": "owner_stage_approval_submitted",
            "decision": "approve_owner_stage",
            "approve_stage": True,
            "owner": "delivery-owner",
            "approval_id": "approval-2026-06-10-001",
            "approved_at": "2026-06-10T10:00:00Z",
            "rationale": "Owner reviewed the delivery packet and approves explicit staging commands.",
            "stage_include_count": 80,
            "owner_stage_command_count": 80,
            "stage_path_digest": _stage_path_digest(),
            "stage_command_digest": _stage_command_digest(),
            "expected_stage_path_set_digest": _path_set_digest(),
            "commit_command_preview": _commit_preview(),
            "acknowledge_pre_stage_verification": True,
            "acknowledge_post_stage_verification": True,
            "acknowledge_no_broad_git_add": True,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["owner_approval_payload_audit_path"],
        {
            "status": "owner_approval_payload_ready",
            "approval_payload_valid": True,
            "ready_for_approval_gate": True,
            "owner": "delivery-owner",
            "approval_id": "approval-2026-06-10-001",
            "approved_at": "2026-06-10T10:00:00Z",
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 80,
                "owner_stage_command_count": 80,
                "approval_stage_include_count": 80,
                "approval_owner_stage_command_count": 80,
                "commit_command_preview": _commit_preview(),
                "approval_commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(),
                "approval_stage_path_digest": _stage_path_digest(),
                "stage_command_digest": _stage_command_digest(),
                "approval_stage_command_digest": _stage_command_digest(),
                "expected_stage_path_set_digest": _path_set_digest(),
                "approval_expected_stage_path_set_digest": _path_set_digest(),
            },
        },
    )
    return paths


def test_owner_stage_approval_gate_ready_with_matching_owner_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_ready"
    assert gate.evidence_type == "commercial_delivery_owner_stage_approval_gate"
    assert gate.owner_gated is True
    assert gate.mutation_performed is False
    assert gate.git_stage_performed is False
    assert gate.git_commit_performed is False
    assert gate.git_push_performed is False
    assert gate.network_mutation_performed is False
    assert gate.agent_execution_enabled is False
    assert gate.full_codex_parity_claimed is False
    assert gate.stage_approved is True
    assert gate.stage_allowed is True
    assert gate.owner == "delivery-owner"
    assert gate.approval_id == "approval-2026-06-10-001"
    assert gate.summary["stage_include_count"] == 80
    assert gate.summary["stage_path_digest"] == _stage_path_digest()
    assert gate.summary["approval_stage_path_digest"] == _stage_path_digest()
    assert gate.summary["expected_stage_path_set_digest"] == _path_set_digest()
    assert gate.summary["approval_expected_stage_path_set_digest"] == _path_set_digest()
    assert gate.summary["stage_command_digest"] == _stage_command_digest()
    assert gate.summary["approval_stage_command_digest"] == _stage_command_digest()
    assert gate.summary["secondary_pending_count"] == 0
    assert gate.summary["secondary_handoff_next_count"] == 1
    assert gate.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert gate.summary["secondary_handoff_completed_count"] == 44
    assert gate.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert gate.summary["owner_approval_payload_audit_status"] == "owner_approval_payload_ready"
    assert gate.summary["owner_approval_payload_valid"] is True
    assert gate.summary["owner_approval_payload_ready_for_gate"] is True
    assert gate.summary["owner_action_required"] is False
    assert gate.summary["blocking_reasons"] == []
    assert {check.status for check in gate.checks} == {"passed"}


def test_owner_stage_approval_gate_blocks_missing_approval_file(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_approval_path"].unlink()

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert gate.stage_allowed is False
    assert gate.summary["owner_action_required"] is True
    assert "owner_approval_readable" in gate.summary["blocking_reasons"]
    assert "owner_approval_decision_present" in gate.summary["blocking_reasons"]
    assert next(check for check in gate.checks if check.name == "owner_approval_readable").status == "failed"
    assert next(check for check in gate.checks if check.name == "owner_approval_decision_present").status == "failed"


def test_owner_stage_approval_gate_blocks_missing_approval_payload_audit(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_approval_payload_audit_path"].unlink()

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert gate.stage_allowed is False
    assert next(check for check in gate.checks if check.name == "owner_approval_payload_audit_readable").status == "failed"
    assert next(check for check in gate.checks if check.name == "owner_approval_payload_audit_ready").status == "failed"


def test_owner_stage_approval_gate_blocks_unready_approval_payload_audit(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    audit = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    audit["status"] = "owner_approval_payload_blocked"
    audit["approval_payload_valid"] = False
    audit["ready_for_approval_gate"] = False
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(audit), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert gate.stage_allowed is False
    assert next(check for check in gate.checks if check.name == "owner_approval_payload_audit_ready").status == "failed"


def test_owner_stage_approval_gate_blocks_approval_payload_audit_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    audit = json.loads(paths["owner_approval_payload_audit_path"].read_text(encoding="utf-8"))
    audit["summary"]["approval_stage_path_digest"] = "0" * 64
    paths["owner_approval_payload_audit_path"].write_text(json.dumps(audit), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert gate.stage_allowed is False
    check = next(check for check in gate.checks if check.name == "owner_approval_payload_audit_ready")
    assert check.status == "failed"
    assert check.details["audit_approval_stage_path_digest"] == "0" * 64


def test_owner_stage_approval_gate_blocks_rejected_decision(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["decision"] = "reject_owner_stage"
    payload["approve_stage"] = False
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert gate.stage_approved is False
    assert next(check for check in gate.checks if check.name == "owner_approval_decision_present").status == "failed"


def test_owner_stage_approval_gate_blocks_template_placeholders(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["owner"] = "<owner-name-or-id>"
    payload["approval_id"] = "<approval-id>"
    payload["approved_at"] = "<ISO-8601 UTC timestamp>"
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    identity = next(check for check in gate.checks if check.name == "owner_identity_present")
    assert identity.status == "failed"
    assert identity.details["approved_at_iso8601"] is False
    assert identity.details["placeholders_rejected"] is True


def test_owner_stage_approval_gate_blocks_non_iso_approved_at(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["approved_at"] = "approved today"
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    identity = next(check for check in gate.checks if check.name == "owner_identity_present")
    assert identity.status == "failed"
    assert identity.details["approved_at_iso8601"] is False


def test_owner_stage_approval_gate_blocks_stage_count_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["stage_include_count"] = 79
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert next(check for check in gate.checks if check.name == "stage_counts_match_owner_delivery_packet").status == "failed"


def test_owner_stage_approval_gate_blocks_commit_preview_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["commit_command_preview"] = 'git commit -m "different"'
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert next(check for check in gate.checks if check.name == "commit_preview_matches_owner_delivery_packet").status == "failed"


def test_owner_stage_approval_gate_blocks_stage_command_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["stage_command_digest"] = "0" * 64
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert next(
        check for check in gate.checks if check.name == "stage_command_digest_matches_owner_delivery_packet"
    ).status == "failed"


def test_owner_stage_approval_gate_blocks_stage_path_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["stage_path_digest"] = "0" * 64
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert next(
        check for check in gate.checks if check.name == "stage_path_digest_matches_owner_delivery_packet"
    ).status == "failed"


def test_owner_stage_approval_gate_blocks_expected_path_set_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["expected_stage_path_set_digest"] = "0" * 64
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert next(
        check for check in gate.checks if check.name == "expected_stage_path_set_digest_matches_owner_delivery_packet"
    ).status == "failed"


def test_owner_stage_approval_gate_blocks_missing_acknowledgement(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["acknowledge_no_broad_git_add"] = False
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    gate = build_owner_stage_approval_gate(**paths)

    assert gate.status == "owner_stage_approval_blocked"
    assert next(check for check in gate.checks if check.name == "owner_acknowledges_gates").status == "failed"


def test_owner_stage_approval_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    gate = build_owner_stage_approval_gate(**paths)
    json_output = tmp_path / "approval-gate.json"
    md_output = tmp_path / "approval-gate.md"

    write_report(gate, json_output)
    write_markdown_gate(gate, md_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = md_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_stage_approval_ready"
    assert payload["checks_count"] == len(payload["checks"]) == len(gate.checks)
    assert payload["next_actions_count"] == len(gate.next_actions)
    assert payload["known_limits_count"] == len(gate.known_limits)
    assert payload["summary"]["blocking_reasons"] == []
    assert payload["summary"]["owner_action_required"] is False
    assert "Commercial Delivery Owner Stage Approval Gate" in markdown
    assert "Owner action required: `false`" in markdown
    assert "Blocking reasons: ``" in markdown
    assert "approval-2026-06-10-001" in render_markdown_gate(gate)
