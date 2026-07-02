from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_output_contract_readiness_packet import (
    build_codex_output_contract_readiness_packet,
    summarize_codex_output_contract,
)


PACKET_POLICIES = {
    "final_answer_policy": "final-answer-policy",
    "command_output_policy": "command-output-policy",
    "file_reference_policy": "file-reference-policy",
    "verification_policy": "verification-policy",
    "output_contract_manifest_ref": "output-contract-manifest",
    "response_governance_ref": "response-governance",
}


def test_ready_output_contract_has_response_evidence() -> None:
    packet = build_codex_output_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "outputs": [
                {
                    "output_id": "output-1",
                    "status": "completed",
                    "final_answer_ref": "final-answer",
                    "command_output_summary_refs": ["command-summary"],
                    "file_reference_refs": ["file-ref"],
                    "verification_evidence_refs": ["verification"],
                    "next_step_refs": ["next-step"],
                    "handoff_refs": ["handoff"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "command_outputs_claimed": True,
                    "changed_files_claimed": True,
                }
            ],
        }
    )

    assert packet["kind"] == "codex_output_contract_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["output_count"] == 1
    assert packet["summary"]["command_output_summary_ref_count"] == 1
    assert packet["next_actions"] == ["share_output_contract_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_output_contract_readiness_packet(
        {
            "outputs": [
                {
                    "output_id": "output-2",
                    "status": "completed",
                    "final_answer_ref": "final",
                    "verification_evidence_refs": ["verification"],
                    "next_step_refs": ["next"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_output_contract_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "final_answer_policy_ref",
        "command_output_policy_ref",
        "file_reference_policy_ref",
        "verification_policy_ref",
        "output_contract_manifest_ref",
        "response_governance_ref",
    ]


def test_failed_output_blocks_and_requires_failure_disclosure_refs() -> None:
    packet = build_codex_output_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "outputs": [
                {
                    "output_id": "output-3",
                    "status": "failed",
                    "final_answer_ref": "final",
                    "verification_evidence_refs": ["verification"],
                    "next_step_refs": ["next"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    output = packet["outputs"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_output_contract_status_failed"
    assert "failure_disclosure_refs" in output["missing_refs"]


def test_missing_final_command_file_verification_and_next_refs_needs_review() -> None:
    output = summarize_codex_output_contract(
        {
            "output_id": "output-4",
            "status": "completed",
            "command_outputs_claimed": True,
            "changed_files_claimed": True,
            "artifact_refs": ["artifact"],
        }
    )

    assert output.readiness_state == "needs_review"
    assert "final_answer_ref" in output.missing_refs
    assert "command_output_summary_refs" in output.missing_refs
    assert "file_reference_refs" in output.missing_refs
    assert "verification_evidence_refs" in output.missing_refs
    assert "next_step_refs" in output.missing_refs


def test_verified_output_requires_verification_evidence_and_validation_receipts() -> None:
    packet = build_codex_output_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "outputs": [
                {
                    "output_id": "output-5",
                    "status": "validated",
                    "final_answer_ref": "final",
                    "next_step_refs": ["next"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    output = packet["outputs"][0]
    assert packet["status"] == "needs_review"
    assert "verification_evidence_refs" in output["missing_refs"]
    assert "validation_receipt_refs" in output["missing_refs"]


def test_live_response_transcript_or_output_wiring_attempt_blocks_candidate() -> None:
    packet = build_codex_output_contract_readiness_packet(
        {
            **PACKET_POLICIES,
            "outputs": [
                {
                    "output_id": "output-6",
                    "status": "completed",
                    "final_answer_ref": "final",
                    "failure_disclosure_refs": ["failure"],
                    "verification_evidence_refs": ["verification"],
                    "next_step_refs": ["next"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "transcript_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_output_contract_live_operation_blocked"
    assert "live_output_operation_attempted" in packet["outputs"][0]["blockers"]


def test_empty_payload_requests_output_contract_inventory() -> None:
    packet = build_codex_output_contract_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_output_contract_inventory"]


def test_dataclass_like_output_contract_is_accepted_by_summarizer() -> None:
    @dataclass
    class OutputContract:
        output_id: str
        status: str
        final_answer_ref: str
        command_output_summary_refs: list[str]
        file_reference_refs: list[str]
        failure_disclosure_refs: list[str]
        verification_evidence_refs: list[str]
        next_step_refs: list[str]
        handoff_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    output = summarize_codex_output_contract(
        OutputContract(
            "output-7",
            "passed",
            "final",
            ["command"],
            ["file"],
            ["failure"],
            ["verification"],
            ["next"],
            ["handoff"],
            ["validation"],
            ["artifact"],
        )
    )

    assert output.output_id == "output-7"
    assert output.status == "passed"
    assert output.readiness_state == "ready"
