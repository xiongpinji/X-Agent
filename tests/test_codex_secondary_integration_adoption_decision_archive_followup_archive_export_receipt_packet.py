from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt,
)


PACKET_POLICIES = {
    "followup_archive_export_receipt_policy": "followup-archive-export-receipt-policy",
    "archive_export_policy": "archive-export-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "export_validation_policy": "export-validation-policy",
    "secondary_integration_adoption_decision_archive_followup_archive_export_receipt_ref": "followup-archive-export-receipt",
    "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref": "followup-archive-export-governance",
}


def test_ready_secondary_integration_archive_followup_archive_export_receipt_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "export_receipt_id": "export-receipt-1",
                    "status": "receipted",
                    "archive_followup_export_receipt_ref": "export-receipt",
                    "export_manifest_refs": ["export-manifest"],
                    "closure_receipt_refs": ["closure-receipt"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["receipt_count"] == 1
    assert packet["summary"]["owner_acknowledgement_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet(
        {
            "receipts": [
                {
                    "export_receipt_id": "export-receipt-2",
                    "status": "receipted",
                    "archive_followup_export_receipt_ref": "export-receipt",
                    "export_manifest_refs": ["export-manifest"],
                    "closure_receipt_refs": ["closure-receipt"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_archive_export_receipt_policy_ref",
        "archive_export_policy_ref",
        "receipt_retention_policy_ref",
        "export_validation_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_receipt_ref",
        "secondary_integration_adoption_decision_archive_followup_archive_export_governance_ref",
    ]


def test_failed_or_stale_archive_export_receipt_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "export_receipt_id": "export-receipt-3",
                    "status": "stale",
                    "archive_followup_export_receipt_ref": "export-receipt",
                    "export_manifest_refs": ["export-manifest"],
                    "closure_receipt_refs": ["closure-receipt"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    receipt = packet["receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_status_failed" in receipt["blockers"]


def test_missing_archive_export_receipt_refs_needs_review() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt(
        {
            "export_receipt_id": "export-receipt-4",
            "status": "receipted",
            "archive_followup_export_receipt_ref": "export-receipt",
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "export_manifest_refs" in receipt.missing_refs
    assert "closure_receipt_refs" in receipt.missing_refs
    assert "retention_refs" in receipt.missing_refs
    assert "validation_refs" in receipt.missing_refs
    assert "evidence_refs" in receipt.missing_refs
    assert "owner_acknowledgement_refs" in receipt.missing_refs
    assert "reviewer_acknowledgement_refs" in receipt.missing_refs
    assert "next_action_refs" in receipt.missing_refs


def test_open_archive_export_receipt_warns_until_acknowledgements_attach() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt(
        {
            "export_receipt_id": "export-receipt-5",
            "status": "needs-review",
            "archive_followup_export_receipt_ref": "export-receipt",
            "export_manifest_refs": ["export-manifest"],
            "closure_receipt_refs": ["closure-receipt"],
            "retention_refs": ["retention"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "owner_acknowledgement_refs": ["owner-ack"],
            "reviewer_acknowledgement_refs": ["reviewer-ack"],
            "next_action_refs": ["next-action"],
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert receipt.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_still_open" in receipt.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "export_receipt_id": "export-receipt-6",
                    "status": "receipted",
                    "archive_followup_export_receipt_ref": "export-receipt",
                    "export_manifest_refs": ["export-manifest"],
                    "closure_receipt_refs": ["closure-receipt"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_missing_evidence"
    assert "residual_risk_refs" in packet["receipts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet",
    ]


def test_owner_acknowledgement_warning_drives_acknowledgement_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "export_receipt_id": "export-receipt-7",
                    "status": "receipted",
                    "archive_followup_export_receipt_ref": "export-receipt",
                    "export_manifest_refs": ["export-manifest"],
                    "closure_receipt_refs": ["closure-receipt"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "residual_risk_refs": ["none"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "next_action_refs": ["next-action"],
                    "owner_acknowledgement_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_owner_acknowledgement_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_export_receipt_owner_acknowledgements",
        "refresh_archive_followup_export_receipt_packet",
    ]


def test_live_archive_export_receipt_file_write_index_persistence_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "export_receipt_id": "export-receipt-8",
                    "status": "receipted",
                    "archive_followup_export_receipt_ref": "export-receipt",
                    "export_manifest_refs": ["export-manifest"],
                    "closure_receipt_refs": ["closure-receipt"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "owner_acknowledgement_refs": ["owner-ack"],
                    "reviewer_acknowledgement_refs": ["reviewer-ack"],
                    "next_action_refs": ["next-action"],
                    "archive_export_receipt_persistence_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_operation_attempted" in packet["receipts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_archive_export_receipt_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt_inventory"]


def test_dataclass_like_archive_export_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupArchiveExportReceipt:
        export_receipt_id: str
        status: str
        archive_followup_export_receipt_ref: str
        export_manifest_refs: list[str]
        closure_receipt_refs: list[str]
        retention_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        residual_risk_refs: list[str]
        owner_acknowledgement_refs: list[str]
        reviewer_acknowledgement_refs: list[str]
        next_action_refs: list[str]

    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_archive_export_receipt(
        FollowupArchiveExportReceipt(
            "export-receipt-9",
            "complete",
            "export-receipt",
            ["export-manifest"],
            ["closure-receipt"],
            ["retention"],
            ["validation"],
            ["evidence"],
            ["none"],
            ["owner-ack"],
            ["reviewer-ack"],
            ["next-action"],
        )
    )

    assert receipt.export_receipt_id == "export-receipt-9"
    assert receipt.status == "complete"
    assert receipt.readiness_state == "ready"
