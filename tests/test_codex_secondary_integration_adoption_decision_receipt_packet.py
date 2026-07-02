from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_receipt_packet import (
    build_codex_secondary_integration_adoption_decision_receipt_packet,
    summarize_codex_secondary_integration_adoption_decision_receipt,
)


PACKET_POLICIES = {
    "adoption_decision_receipt_policy": "adoption-decision-receipt-policy",
    "owner_receipt_policy": "owner-receipt-policy",
    "mainline_acknowledgement_policy": "mainline-acknowledgement-policy",
    "receipt_timestamp_policy": "receipt-timestamp-policy",
    "secondary_integration_adoption_decision_receipt_manifest_ref": "adoption-decision-receipt-manifest",
    "secondary_integration_adoption_decision_receipt_governance_ref": "adoption-decision-receipt-governance",
}


def test_ready_secondary_integration_adoption_decision_receipt_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-1",
                    "status": "acknowledged",
                    "adoption_decision_receipt_ref": "decision-receipt",
                    "decision_ledger_refs": ["decision-ledger"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "mainline_acknowledgement_refs": ["mainline-ack"],
                    "accepted_disposition_refs": ["accepted"],
                    "deferred_disposition_refs": ["deferred"],
                    "rejected_disposition_refs": ["rejected"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "receipt_timestamp_refs": ["timestamp"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_receipt_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["receipt_count"] == 1
    assert packet["summary"]["mainline_acknowledgement_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_receipt_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet(
        {
            "receipts": [
                {
                    "receipt_id": "receipt-2",
                    "status": "received",
                    "adoption_decision_receipt_ref": "decision-receipt",
                    "decision_ledger_refs": ["decision-ledger"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "mainline_acknowledgement_refs": ["mainline-ack"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "receipt_timestamp_refs": ["timestamp"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "adoption_decision_receipt_policy_ref",
        "owner_receipt_policy_ref",
        "mainline_acknowledgement_policy_ref",
        "receipt_timestamp_policy_ref",
        "secondary_integration_adoption_decision_receipt_manifest_ref",
        "secondary_integration_adoption_decision_receipt_governance_ref",
    ]


def test_failed_or_stale_adoption_decision_receipt_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-3",
                    "status": "stale",
                    "adoption_decision_receipt_ref": "decision-receipt",
                    "decision_ledger_refs": ["decision-ledger"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "mainline_acknowledgement_refs": ["mainline-ack"],
                    "rejected_disposition_refs": ["rejected"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "receipt_timestamp_refs": ["timestamp"],
                }
            ],
        }
    )

    receipt = packet["receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_receipt_status_failed"
    assert "codex_secondary_integration_adoption_decision_receipt_status_failed" in receipt["blockers"]


def test_missing_adoption_decision_receipt_refs_needs_review() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_receipt(
        {
            "receipt_id": "receipt-4",
            "status": "acknowledged",
            "adoption_decision_receipt_ref": "decision-receipt",
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "decision_ledger_refs" in receipt.missing_refs
    assert "owner_receipt_refs" in receipt.missing_refs
    assert "mainline_acknowledgement_refs" in receipt.missing_refs
    assert "candidate_disposition_refs" in receipt.missing_refs
    assert "validation_refs" in receipt.missing_refs
    assert "residual_risk_refs" in receipt.missing_refs
    assert "handoff_refs" in receipt.missing_refs
    assert "receipt_timestamp_refs" in receipt.missing_refs


def test_open_adoption_decision_receipt_warns_until_receipts_attach() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_receipt(
        {
            "receipt_id": "receipt-5",
            "status": "needs-review",
            "adoption_decision_receipt_ref": "decision-receipt",
            "decision_ledger_refs": ["decision-ledger"],
            "owner_receipt_refs": ["owner-receipt"],
            "mainline_acknowledgement_refs": ["mainline-ack"],
            "deferred_disposition_refs": ["deferred"],
            "validation_refs": ["validation"],
            "residual_risk_refs": ["risk"],
            "handoff_refs": ["handoff"],
            "receipt_timestamp_refs": ["timestamp"],
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert receipt.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_receipt_still_open" in receipt.warnings


def test_residual_risk_warning_drives_receipt_input_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-6",
                    "status": "received",
                    "adoption_decision_receipt_ref": "decision-receipt",
                    "decision_ledger_refs": ["decision-ledger"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "mainline_acknowledgement_refs": ["mainline-ack"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "receipt_timestamp_refs": ["timestamp"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_receipt_residual_risk"
    assert packet["next_actions"] == [
        "review_secondary_integration_adoption_receipt_risks",
        "update_adoption_receipt_inputs",
    ]


def test_missing_timestamp_warning_drives_receipt_timestamp_attachment() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-7",
                    "status": "reviewed",
                    "adoption_decision_receipt_ref": "decision-receipt",
                    "decision_ledger_refs": ["decision-ledger"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "mainline_acknowledgement_refs": ["mainline-ack"],
                    "deferred_disposition_refs": ["deferred"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "receipt_timestamp_refs": ["timestamp"],
                    "receipt_timestamp_missing": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_receipt_timestamp_missing"
    assert packet["next_actions"] == [
        "attach_adoption_decision_receipt_timestamps",
        "refresh_adoption_decision_receipt_packet",
    ]


def test_live_receipt_decision_disposition_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-8",
                    "status": "received",
                    "adoption_decision_receipt_ref": "decision-receipt",
                    "decision_ledger_refs": ["decision-ledger"],
                    "owner_receipt_refs": ["owner-receipt"],
                    "mainline_acknowledgement_refs": ["mainline-ack"],
                    "accepted_disposition_refs": ["accepted"],
                    "validation_refs": ["validation"],
                    "residual_risk_refs": ["risk"],
                    "handoff_refs": ["handoff"],
                    "receipt_timestamp_refs": ["timestamp"],
                    "receipt_persistence_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_receipt_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_receipt_operation_attempted" in packet["receipts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_adoption_decision_receipt_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_receipt_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_receipt_inventory"]


def test_dataclass_like_adoption_decision_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class AdoptionReceipt:
        receipt_id: str
        status: str
        adoption_decision_receipt_ref: str
        decision_ledger_refs: list[str]
        owner_receipt_refs: list[str]
        mainline_acknowledgement_refs: list[str]
        accepted_disposition_refs: list[str]
        deferred_disposition_refs: list[str]
        rejected_disposition_refs: list[str]
        validation_refs: list[str]
        residual_risk_refs: list[str]
        handoff_refs: list[str]
        receipt_timestamp_refs: list[str]

    receipt = summarize_codex_secondary_integration_adoption_decision_receipt(
        AdoptionReceipt(
            "receipt-9",
            "closed",
            "decision-receipt",
            ["decision-ledger"],
            ["owner-receipt"],
            ["mainline-ack"],
            ["accepted"],
            ["deferred"],
            ["rejected"],
            ["validation"],
            ["risk"],
            ["handoff"],
            ["timestamp"],
        )
    )

    assert receipt.receipt_id == "receipt-9"
    assert receipt.status == "closed"
    assert receipt.readiness_state == "ready"
