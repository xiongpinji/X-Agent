from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.commercial_delivery_owner_stage_approval_request import (
    build_owner_stage_approval_request,
    render_markdown_request,
    write_markdown_request,
    write_report,
    write_template,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _stage_commands(count: int = 2) -> list[str]:
    return [f"git add -- 'file-{index}.py'" for index in range(count)]


def _stage_paths(count: int = 2) -> list[str]:
    return [f"file-{index}.py" for index in range(count)]


def _stage_path_digest(count: int = 2) -> str:
    return hashlib.sha256(
        json.dumps(_stage_paths(count), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _path_set_digest(count: int = 2) -> str:
    return hashlib.sha256(
        json.dumps(sorted(set(_stage_paths(count))), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _stage_command_digest(count: int = 2) -> str:
    return hashlib.sha256(
        json.dumps(_stage_commands(count), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_inputs(reports_dir: Path, *, count: int = 2, approval_gate_status: str = "blocked") -> dict[str, Path]:
    paths = {
        "owner_delivery_packet_path": reports_dir / "owner-delivery-packet.json",
        "owner_stage_approval_gate_path": reports_dir / "owner-stage-approval-gate.json",
        "owner_approval_path": reports_dir / "owner-stage-approval.json",
        "template_output_path": reports_dir / "owner-stage-approval.template.json",
    }
    gate_ready = approval_gate_status == "ready"
    stage_commands = _stage_commands(count)
    _write_json(
        paths["owner_delivery_packet_path"],
        {
            "status": "owner_delivery_packet_ready",
            "stage_ready": True,
            "owner_approval_required": True,
            "full_codex_parity_claimed": False,
            "summary": {
                "stage_include_count": count,
                "owner_stage_command_count": count,
                "owner_stage_approval_gate_status": (
                    "owner_stage_approval_ready" if gate_ready else "owner_stage_approval_blocked"
                ),
                "stage_allowed": gate_ready,
                "stage_path_digest": _stage_path_digest(count),
                "stage_command_digest": _stage_command_digest(count),
                "expected_stage_path_set_digest": _path_set_digest(count),
                "commit_command_preview": 'git commit -m "chore: prepare X-Agent commercial delivery package"',
                "secondary_pending_count": 0,
                "secondary_handoff_next_count": 1,
                "secondary_handoff_next_queue": ["integration_review_action_status_board.py"],
                "secondary_handoff_completed_count": 44,
                "secondary_handoff_latest_completed_candidate": "integration_review_answer_action_matrix.py",
            },
            "sections": [
                {
                    "name": "owner_stage_commands",
                    "commands": stage_commands,
                }
            ],
        },
    )
    _write_json(
        paths["owner_stage_approval_gate_path"],
        {
            "status": "owner_stage_approval_ready" if gate_ready else "owner_stage_approval_blocked",
            "stage_allowed": gate_ready,
            "full_codex_parity_claimed": False,
        },
    )
    return paths


def test_owner_stage_approval_request_ready_with_blocked_gate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_ready"
    assert request.evidence_type == "commercial_delivery_owner_stage_approval_request"
    assert request.owner_gated is True
    assert request.mutation_performed is False
    assert request.git_stage_performed is False
    assert request.git_commit_performed is False
    assert request.git_push_performed is False
    assert request.network_mutation_performed is False
    assert request.agent_execution_enabled is False
    assert request.full_codex_parity_claimed is False
    assert request.approval_required is True
    assert request.summary["stage_include_count"] == 2
    assert request.summary["owner_stage_command_count"] == 2
    assert request.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_blocked"
    assert request.summary["stage_allowed"] is False
    assert request.suggested_owner_approval_payload["decision"] == "approve_owner_stage"
    assert request.suggested_owner_approval_payload["approve_stage"] is True
    assert request.suggested_owner_approval_payload["stage_include_count"] == 2
    assert request.suggested_owner_approval_payload["owner_stage_command_count"] == 2
    assert request.suggested_owner_approval_payload["stage_path_digest"] == _stage_path_digest()
    assert request.suggested_owner_approval_payload["stage_command_digest"] == _stage_command_digest()
    assert request.suggested_owner_approval_payload["expected_stage_path_set_digest"] == _path_set_digest()
    assert request.summary["stage_path_digest"] == _stage_path_digest()
    assert request.summary["stage_command_digest"] == _stage_command_digest()
    assert request.summary["expected_stage_path_set_digest"] == _path_set_digest()
    assert request.summary["template_identity_placeholders_present"] is True
    assert request.summary["template_owner_placeholder"] == "<owner-name-or-id>"
    assert request.summary["template_approval_id_placeholder"] == "<approval-id>"
    assert request.summary["template_approved_at_placeholder"] == "<ISO-8601 UTC timestamp>"
    assert request.summary["secondary_handoff_next_queue"] == ["integration_review_action_status_board.py"]
    assert request.summary["secondary_handoff_completed_count"] == 44
    assert request.summary["secondary_handoff_latest_completed_candidate"] == "integration_review_answer_action_matrix.py"
    assert "secondary_handoff_next_queue" not in request.suggested_owner_approval_payload
    assert "secondary_handoff_completed_count" not in request.suggested_owner_approval_payload
    assert "secondary_handoff_latest_completed_candidate" not in request.suggested_owner_approval_payload
    assert request.suggested_owner_approval_payload["acknowledge_no_broad_git_add"] is True
    assert {check.status for check in request.checks} == {"passed"}


def test_owner_stage_approval_request_allows_subset_eligible_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, count=2)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["summary"]["stage_include_count"] = 100
    payload["summary"]["eligible_stage_count"] = 2
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_ready"
    assert request.summary["stage_include_count"] == 100
    assert request.summary["eligible_stage_count"] == 2
    assert request.summary["owner_stage_command_count"] == 2
    assert request.suggested_owner_approval_payload["stage_include_count"] == 100
    assert request.suggested_owner_approval_payload["owner_stage_command_count"] == 2
    count_check = next(check for check in request.checks if check.name == "stage_counts_match_delivery_packet")
    assert count_check.status == "passed"


def test_owner_stage_approval_request_writes_report_markdown_and_template(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    request = build_owner_stage_approval_request(**paths)
    report_output = tmp_path / "request.json"
    markdown_output = tmp_path / "request.md"

    write_report(request, report_output)
    write_markdown_request(request, markdown_output)
    write_template(request, paths["template_output_path"])

    payload = json.loads(report_output.read_text(encoding="utf-8"))
    template = json.loads(paths["template_output_path"].read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "owner_stage_approval_request_ready"
    assert payload["checks_count"] == len(payload["checks"]) == len(request.checks)
    assert payload["next_actions_count"] == len(request.next_actions)
    assert payload["known_limits_count"] == len(request.known_limits)
    assert template["status"] == "owner_stage_approval_submitted"
    assert template["owner"] == "<owner-name-or-id>"
    assert template["approval_id"] == "<approval-id>"
    assert template["approved_at"] == "<ISO-8601 UTC timestamp>"
    assert template["stage_include_count"] == 2
    assert len(template["stage_path_digest"]) == 64
    assert len(template["stage_command_digest"]) == 64
    assert len(template["expected_stage_path_set_digest"]) == 64
    assert paths["owner_approval_path"].exists() is False
    assert "Suggested Approval Payload" in markdown
    assert "Commercial Delivery Owner Stage Approval Request" in render_markdown_request(request)


def test_owner_stage_approval_request_blocks_missing_delivery_packet(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["owner_delivery_packet_path"].unlink()

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_blocked"
    assert next(check for check in request.checks if check.name == "owner_delivery_packet_readable").status == "failed"
    assert next(check for check in request.checks if check.name == "owner_delivery_packet_ready").status == "failed"


def test_owner_stage_approval_request_blocks_stage_count_drift(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, count=2)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["summary"]["owner_stage_command_count"] = 3
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_blocked"
    assert next(check for check in request.checks if check.name == "stage_counts_match_delivery_packet").status == "failed"


def test_owner_stage_approval_request_blocks_missing_stage_commands(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, count=2)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["sections"] = []
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_blocked"
    assert next(check for check in request.checks if check.name == "stage_command_digest_present").status == "failed"


def test_owner_stage_approval_request_blocks_missing_stage_path_digest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, count=2)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["summary"].pop("stage_path_digest")
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_blocked"
    assert next(check for check in request.checks if check.name == "stage_path_digest_present").status == "failed"


def test_owner_stage_approval_request_blocks_missing_expected_stage_path_set_digest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, count=2)
    payload = json.loads(paths["owner_delivery_packet_path"].read_text(encoding="utf-8"))
    payload["summary"].pop("expected_stage_path_set_digest")
    paths["owner_delivery_packet_path"].write_text(json.dumps(payload), encoding="utf-8")

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_blocked"
    assert next(
        check for check in request.checks if check.name == "expected_stage_path_set_digest_present"
    ).status == "failed"


def test_owner_stage_approval_request_accepts_ready_gate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, approval_gate_status="ready")

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_ready"
    assert request.summary["owner_stage_approval_gate_status"] == "owner_stage_approval_ready"
    assert request.summary["stage_allowed"] is True


def test_owner_stage_approval_request_rejects_template_over_real_approval(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    paths["template_output_path"] = paths["owner_approval_path"]

    request = build_owner_stage_approval_request(**paths)

    assert request.status == "owner_stage_approval_request_blocked"
    assert next(
        check for check in request.checks if check.name == "template_does_not_target_real_approval_file"
    ).status == "failed"
