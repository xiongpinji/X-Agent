from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_tool_result_provenance_receipt_readiness_packet import (
    build_codex_tool_result_provenance_receipt_readiness_packet,
    summarize_codex_tool_result_provenance_receipt,
)


PACKET_POLICIES = {
    "tool_result_policy": "tool-result-policy",
    "provenance_policy": "provenance-policy",
    "receipt_policy": "receipt-policy",
    "redaction_policy": "redaction-policy",
    "tool_result_manifest_ref": "tool-result-manifest",
    "tool_result_governance_ref": "tool-result-governance",
}


def test_ready_tool_result_provenance_receipt_has_execution_evidence() -> None:
    packet = build_codex_tool_result_provenance_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-1",
                    "status": "validated",
                    "tool_call_ref": "tool-call",
                    "result_refs": ["result"],
                    "source_refs": ["source"],
                    "provenance_refs": ["provenance"],
                    "stdout_receipt_refs": ["stdout"],
                    "stderr_receipt_refs": ["stderr"],
                    "exit_status_refs": ["exit-status"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_tool_result_provenance_receipt_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["receipt_count"] == 1
    assert packet["summary"]["provenance_ref_count"] == 1
    assert packet["next_actions"] == ["share_tool_result_provenance_receipt_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_tool_result_provenance_receipt_readiness_packet(
        {
            "receipts": [
                {
                    "receipt_id": "receipt-2",
                    "status": "recorded",
                    "tool_call_ref": "tool-call",
                    "result_refs": ["result"],
                    "source_refs": ["source"],
                    "provenance_refs": ["provenance"],
                    "stdout_receipt_refs": ["stdout"],
                    "stderr_receipt_refs": ["stderr"],
                    "exit_status_refs": ["exit-status"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_tool_result_provenance_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "tool_result_policy_ref",
        "provenance_policy_ref",
        "receipt_policy_ref",
        "redaction_policy_ref",
        "tool_result_manifest_ref",
        "tool_result_governance_ref",
    ]


def test_failed_tool_result_requires_stderr_receipt_and_blocks() -> None:
    packet = build_codex_tool_result_provenance_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-3",
                    "status": "failed",
                    "tool_call_ref": "tool-call",
                    "result_refs": ["result"],
                    "source_refs": ["source"],
                    "provenance_refs": ["provenance"],
                    "stdout_receipt_refs": ["stdout"],
                    "exit_status_refs": ["exit-status"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    receipt = packet["receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_tool_result_provenance_receipt_status_failed"
    assert "stderr_receipt_refs" in receipt["missing_refs"]


def test_missing_tool_result_source_provenance_stdout_exit_redaction_validation_artifact_needs_review() -> None:
    receipt = summarize_codex_tool_result_provenance_receipt(
        {
            "receipt_id": "receipt-4",
            "status": "recorded",
            "owner_refs": ["owner"],
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "tool_call_ref" in receipt.missing_refs
    assert "result_refs" in receipt.missing_refs
    assert "source_refs" in receipt.missing_refs
    assert "provenance_refs" in receipt.missing_refs
    assert "stdout_receipt_refs" in receipt.missing_refs
    assert "exit_status_refs" in receipt.missing_refs
    assert "redaction_refs" in receipt.missing_refs
    assert "validation_receipt_refs" in receipt.missing_refs
    assert "artifact_refs" in receipt.missing_refs


def test_live_tool_command_capture_or_artifact_mutation_attempt_blocks_candidate() -> None:
    packet = build_codex_tool_result_provenance_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-5",
                    "status": "validated",
                    "tool_call_ref": "tool-call",
                    "result_refs": ["result"],
                    "source_refs": ["source"],
                    "provenance_refs": ["provenance"],
                    "stdout_receipt_refs": ["stdout"],
                    "stderr_receipt_refs": ["stderr"],
                    "exit_status_refs": ["exit-status"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                    "stdout_capture_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_tool_result_provenance_receipt_live_operation_blocked"
    assert "live_tool_result_operation_attempted" in packet["receipts"][0]["blockers"]


def test_empty_payload_requests_tool_result_provenance_receipt_inventory() -> None:
    packet = build_codex_tool_result_provenance_receipt_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_tool_result_provenance_receipt_inventory"]


def test_still_open_receipt_waits_for_completion() -> None:
    packet = build_codex_tool_result_provenance_receipt_readiness_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-6",
                    "status": "capturing",
                    "tool_call_ref": "tool-call",
                    "result_refs": ["result"],
                    "source_refs": ["source"],
                    "provenance_refs": ["provenance"],
                    "stdout_receipt_refs": ["stdout"],
                    "stderr_receipt_refs": ["stderr"],
                    "exit_status_refs": ["exit-status"],
                    "redaction_refs": ["redaction"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "owner_refs": ["owner"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_tool_result_provenance_receipt_still_open"
    assert packet["next_actions"] == [
        "wait_for_tool_result_provenance_receipt_completion",
        "attach_tool_result_provenance_receipts",
    ]


def test_dataclass_like_tool_result_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class ToolResultReceipt:
        receipt_id: str
        status: str
        tool_call_ref: str
        result_refs: list[str]
        source_refs: list[str]
        provenance_refs: list[str]
        stdout_receipt_refs: list[str]
        stderr_receipt_refs: list[str]
        exit_status_refs: list[str]
        redaction_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]
        owner_refs: list[str]

    receipt = summarize_codex_tool_result_provenance_receipt(
        ToolResultReceipt(
            "receipt-7",
            "passed",
            "tool-call",
            ["result"],
            ["source"],
            ["provenance"],
            ["stdout"],
            ["stderr"],
            ["exit-status"],
            ["redaction"],
            ["validation"],
            ["artifact"],
            ["owner"],
        )
    )

    assert receipt.receipt_id == "receipt-7"
    assert receipt.status == "passed"
    assert receipt.readiness_state == "ready"
