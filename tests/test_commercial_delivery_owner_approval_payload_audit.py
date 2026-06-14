from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_delivery_owner_approval_payload_audit import (
    build_owner_approval_payload_audit,
    render_markdown_audit,
    write_markdown_audit,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_commands() -> list[str]:
    return [
        "git add -- 'backend/app/core/storage.py'",
        "git add -- 'tests/test_storage.py'",
    ]


def _stage_paths() -> list[str]:
    return ["backend/app/core/storage.py", "tests/test_storage.py"]


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stage_path_digest() -> str:
    return _digest_values(_stage_paths())


def _stage_command_digest() -> str:
    return _digest_values(_stage_commands())


def _path_set_digest() -> str:
    return _digest_values(sorted(set(_stage_paths())))


def _commit_preview() -> str:
    return 'git commit -m "chore: prepare X-Agent commercial delivery package"'


def _approval_payload() -> dict[str, object]:
    return {
        "status": "owner_stage_approval_submitted",
        "decision": "approve_owner_stage",
        "approve_stage": True,
        "owner": "delivery-owner",
        "approval_id": "approval-2026-06-10-001",
        "approved_at": "2026-06-10T10:00:00Z",
        "rationale": "Owner reviewed the delivery packet and approves explicit staging commands.",
        "stage_include_count": 2,
        "owner_stage_command_count": 2,
        "stage_path_digest": _stage_path_digest(),
        "stage_command_digest": _stage_command_digest(),
        "expected_stage_path_set_digest": _path_set_digest(),
        "commit_command_preview": _commit_preview(),
        "acknowledge_pre_stage_verification": True,
        "acknowledge_post_stage_verification": True,
        "acknowledge_no_broad_git_add": True,
        "full_codex_parity_claimed": False,
    }


def _write_inputs(tmp_path: Path, *, write_approval: bool = True) -> dict[str, Path]:
    paths = {
        "owner_delivery_packet_path": tmp_path / "owner-delivery-packet.json",
        "owner_stage_approval_request_path": tmp_path / "owner-stage-approval-request.json",
        "owner_approval_path": tmp_path / "owner-stage-approval.json",
    }
    approval = _approval_payload()
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "owner_gated": True,
            "stage_ready": True,
            "owner_approval_required": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
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
        },
    )
    _write_json(
        paths["owner_stage_approval_request_path"],
        {
            "status": "owner_stage_approval_request_ready",
            "owner_gated": True,
            "approval_payload_path": str(paths["owner_approval_path"]),
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": 2,
                "owner_stage_command_count": 2,
                "commit_command_preview": _commit_preview(),
                "stage_path_digest": _stage_path_digest(),
                "stage_command_digest": _stage_command_digest(),
                "expected_stage_path_set_digest": _path_set_digest(),
            },
            "suggested_owner_approval_payload": approval,
        },
    )
    if write_approval:
        _write_json(paths["owner_approval_path"], approval)
    return paths


def test_owner_approval_payload_audit_ready_with_matching_payload(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_ready"
    assert audit.evidence_type == "commercial_delivery_owner_approval_payload_audit"
    assert audit.owner_gated is True
    assert audit.mutation_performed is False
    assert audit.git_stage_performed is False
    assert audit.git_commit_performed is False
    assert audit.git_push_performed is False
    assert audit.network_mutation_performed is False
    assert audit.agent_execution_enabled is False
    assert audit.full_codex_parity_claimed is False
    assert audit.approval_payload_present is True
    assert audit.approval_payload_valid is True
    assert audit.ready_for_approval_gate is True
    assert audit.owner == "delivery-owner"
    assert audit.approval_id == "approval-2026-06-10-001"
    assert audit.summary["stage_path_digest"] == _stage_path_digest()
    assert audit.summary["stage_command_digest"] == _stage_command_digest()
    assert audit.summary["expected_stage_path_set_digest"] == _path_set_digest()
    assert audit.summary["secondary_pending_count"] == 0
    assert audit.summary["secondary_handoff_next_count"] == 1
    assert audit.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert audit.summary["secondary_handoff_completed_count"] == 44
    assert audit.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert audit.summary["owner_action_required"] is False
    assert audit.summary["blocking_reasons"] == []
    assert {check.status for check in audit.checks} == {"passed"}


def test_owner_approval_payload_audit_accounts_for_matching_payload_bootstrap_cycle(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    delivery = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    delivery["status"] = "owner_delivery_packet_blocked"
    delivery["checks"] = [
        {
            "name": "owner_approval_payload_audit_accounted_for",
            "status": "failed",
            "details": {},
            "error": "owner approval payload audit is present but not ready or accounted for",
        }
    ]
    paths["owner_delivery_packet_path"].write_text(json.dumps(delivery), encoding="utf-8")
    request = json.loads(paths["owner_stage_approval_request_path"].read_text(encoding="utf-8"))
    request["status"] = "owner_stage_approval_request_blocked"
    request["checks"] = [
        {
            "name": "owner_delivery_packet_ready",
            "status": "failed",
            "details": {},
            "error": "owner delivery packet is not ready",
        }
    ]
    paths["owner_stage_approval_request_path"].write_text(json.dumps(request), encoding="utf-8")

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_ready"
    assert audit.approval_payload_valid is True
    assert audit.summary["owner_delivery_packet_status_accounted_for"] is True
    assert audit.summary["owner_delivery_packet_bootstrap_accounted_for"] is True
    assert audit.summary["owner_delivery_packet_failed_check_names"] == ["owner_approval_payload_audit_accounted_for"]
    assert audit.summary["owner_stage_approval_request_status_accounted_for"] is True
    assert audit.summary["owner_stage_approval_request_bootstrap_accounted_for"] is True
    assert audit.summary["owner_stage_approval_request_failed_check_names"] == ["owner_delivery_packet_ready"]
    assert next(check for check in audit.checks if check.name == "owner_delivery_packet_ready").status == "passed"
    assert next(check for check in audit.checks if check.name == "owner_stage_approval_request_ready").status == "passed"


def test_owner_approval_payload_audit_accounts_for_request_blocked_by_delivery_approval_boundary(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path)
    request = json.loads(paths["owner_stage_approval_request_path"].read_text(encoding="utf-8"))
    request["status"] = "owner_stage_approval_request_blocked"
    request["checks"] = [
        {
            "name": "owner_delivery_packet_ready",
            "status": "failed",
            "details": {},
            "error": "owner delivery packet is not ready",
        },
        {
            "name": "owner_delivery_packet_requires_approval",
            "status": "failed",
            "details": {},
            "error": "owner delivery packet is not in owner approval state",
        },
    ]
    paths["owner_stage_approval_request_path"].write_text(json.dumps(request), encoding="utf-8")

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_ready"
    assert audit.approval_payload_valid is True
    assert audit.summary["owner_stage_approval_request_status_accounted_for"] is True
    assert audit.summary["owner_stage_approval_request_bootstrap_accounted_for"] is True
    assert audit.summary["owner_stage_approval_request_failed_check_names"] == [
        "owner_delivery_packet_ready",
        "owner_delivery_packet_requires_approval",
    ]
    assert next(check for check in audit.checks if check.name == "owner_stage_approval_request_ready").status == "passed"


def test_owner_approval_payload_audit_blocks_missing_payload(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, write_approval=False)

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_blocked"
    assert audit.approval_payload_present is False
    assert audit.ready_for_approval_gate is False
    assert audit.summary["owner_action_required"] is True
    assert "owner_approval_payload_readable" in audit.summary["blocking_reasons"]
    assert "approval_decision_present" in audit.summary["blocking_reasons"]
    assert "owner_identity_present" in audit.summary["blocking_reasons"]
    assert next(check for check in audit.checks if check.name == "owner_approval_payload_readable").status == "failed"
    assert next(check for check in audit.checks if check.name == "approval_decision_present").status == "failed"


def test_owner_approval_payload_audit_blocks_placeholder_identity(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["owner"] = "<owner-name-or-id>"
    payload["approval_id"] = "<approval-id>"
    payload["approved_at"] = "<ISO-8601 UTC timestamp>"
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_blocked"
    identity = next(check for check in audit.checks if check.name == "owner_identity_present")
    assert identity.status == "failed"
    assert identity.details["approved_at_iso8601"] is False
    assert identity.details["placeholders_rejected"] is True


def test_owner_approval_payload_audit_blocks_digest_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["expected_stage_path_set_digest"] = "0" * 64
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_blocked"
    assert next(
        check for check in audit.checks if check.name == "approval_digests_match_request_and_delivery_packet"
    ).status == "failed"


def test_owner_approval_payload_audit_blocks_missing_acknowledgement(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    payload = json.loads(paths["owner_approval_path"].read_text(encoding="utf-8"))
    payload["acknowledge_no_broad_git_add"] = False
    paths["owner_approval_path"].write_text(json.dumps(payload), encoding="utf-8")

    audit = build_owner_approval_payload_audit(**paths)

    assert audit.status == "owner_approval_payload_blocked"
    assert next(check for check in audit.checks if check.name == "owner_acknowledgements_present").status == "failed"


def test_owner_approval_payload_audit_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    audit = build_owner_approval_payload_audit(**paths)
    output = tmp_path / "audit.json"
    markdown_output = tmp_path / "audit.md"

    write_report(audit, output)
    write_markdown_audit(audit, markdown_output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_approval_payload_ready"
    assert payload["checks_count"] == len(payload["checks"]) == len(audit.checks)
    assert payload["next_actions_count"] == len(audit.next_actions)
    assert payload["known_limits_count"] == len(audit.known_limits)
    assert payload["summary"]["owner_action_required"] is False
    assert payload["summary"]["blocking_reasons"] == []
    assert "Commercial Delivery Owner Approval Payload Audit" in markdown
    assert "Owner action required: `false`" in markdown
    assert "Blocking reasons: ``" in markdown
    assert "Expected stage path set digest" in markdown
    assert "approval-2026-06-10-001" in render_markdown_audit(audit)
