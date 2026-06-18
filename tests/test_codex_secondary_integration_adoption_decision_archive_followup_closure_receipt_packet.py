from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt,
)


PACKET_POLICIES = {
    "followup_closure_receipt_policy": "followup-closure-receipt-policy",
    "closure_evidence_policy": "closure-evidence-policy",
    "residual_risk_policy": "residual-risk-policy",
    "receipt_retention_policy": "receipt-retention-policy",
    "secondary_integration_adoption_decision_archive_followup_closure_receipt_manifest_ref": "followup-closure-receipt-manifest",
    "secondary_integration_adoption_decision_archive_followup_receipt_governance_ref": "followup-receipt-governance",
}


def test_ready_secondary_integration_archive_followup_closure_receipt_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-1",
                    "status": "receipted",
                    "archive_followup_closure_receipt_ref": "closure-receipt",
                    "closure_readiness_refs": ["closure-readiness"],
                    "disposition_preview_refs": ["disposition-preview"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "receipt_refs": ["receipt"],
                    "residual_risk_refs": ["none"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["receipt_count"] == 1
    assert packet["summary"]["residual_risk_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(
        {
            "receipts": [
                {
                    "receipt_id": "receipt-2",
                    "status": "receipted",
                    "archive_followup_closure_receipt_ref": "closure-receipt",
                    "closure_readiness_refs": ["closure-readiness"],
                    "disposition_preview_refs": ["disposition-preview"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "receipt_refs": ["receipt"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "followup_closure_receipt_policy_ref",
        "closure_evidence_policy_ref",
        "residual_risk_policy_ref",
        "receipt_retention_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_closure_receipt_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_receipt_governance_ref",
    ]


def test_failed_or_stale_followup_closure_receipt_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-3",
                    "status": "stale",
                    "archive_followup_closure_receipt_ref": "closure-receipt",
                    "closure_readiness_refs": ["closure-readiness"],
                    "disposition_preview_refs": ["disposition-preview"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "receipt_refs": ["receipt"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    receipt = packet["receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_status_failed" in receipt["blockers"]


def test_missing_followup_closure_receipt_refs_needs_review() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt(
        {
            "receipt_id": "receipt-4",
            "status": "receipted",
            "archive_followup_closure_receipt_ref": "closure-receipt",
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "closure_readiness_refs" in receipt.missing_refs
    assert "disposition_preview_refs" in receipt.missing_refs
    assert "owner_signoff_refs" in receipt.missing_refs
    assert "closure_criteria_refs" in receipt.missing_refs
    assert "validation_refs" in receipt.missing_refs
    assert "evidence_refs" in receipt.missing_refs
    assert "receipt_refs" in receipt.missing_refs
    assert "next_action_refs" in receipt.missing_refs


def test_open_followup_closure_receipt_warns_until_receipts_attach() -> None:
    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt(
        {
            "receipt_id": "receipt-5",
            "status": "needs-review",
            "archive_followup_closure_receipt_ref": "closure-receipt",
            "closure_readiness_refs": ["closure-readiness"],
            "disposition_preview_refs": ["disposition-preview"],
            "owner_signoff_refs": ["owner-signoff"],
            "closure_criteria_refs": ["closure-criteria"],
            "validation_refs": ["validation"],
            "evidence_refs": ["evidence"],
            "receipt_refs": ["receipt"],
            "next_action_refs": ["next-action"],
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert receipt.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_still_open" in receipt.warnings


def test_residual_risk_warning_requires_risk_refs_and_drives_evidence_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-6",
                    "status": "receipted",
                    "archive_followup_closure_receipt_ref": "closure-receipt",
                    "closure_readiness_refs": ["closure-readiness"],
                    "disposition_preview_refs": ["disposition-preview"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "receipt_refs": ["receipt"],
                    "next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_missing_evidence"
    assert "residual_risk_refs" in packet["receipts"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet",
    ]


def test_receipt_retention_warning_drives_retention_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-7",
                    "status": "receipted",
                    "archive_followup_closure_receipt_ref": "closure-receipt",
                    "closure_readiness_refs": ["closure-readiness"],
                    "disposition_preview_refs": ["disposition-preview"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "receipt_refs": ["receipt"],
                    "next_action_refs": ["next-action"],
                    "receipt_retention_needs_review": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_retention_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_receipt_retention",
        "refresh_archive_followup_closure_receipt_packet",
    ]


def test_live_receipt_persistence_closure_disposition_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-8",
                    "status": "receipted",
                    "archive_followup_closure_receipt_ref": "closure-receipt",
                    "closure_readiness_refs": ["closure-readiness"],
                    "disposition_preview_refs": ["disposition-preview"],
                    "owner_signoff_refs": ["owner-signoff"],
                    "closure_criteria_refs": ["closure-criteria"],
                    "validation_refs": ["validation"],
                    "evidence_refs": ["evidence"],
                    "receipt_refs": ["receipt"],
                    "next_action_refs": ["next-action"],
                    "closure_receipt_persistence_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_operation_attempted" in packet["receipts"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_closure_receipt_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt_inventory"]


def test_dataclass_like_archive_followup_closure_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupClosureReceipt:
        receipt_id: str
        status: str
        archive_followup_closure_receipt_ref: str
        closure_readiness_refs: list[str]
        disposition_preview_refs: list[str]
        owner_signoff_refs: list[str]
        closure_criteria_refs: list[str]
        validation_refs: list[str]
        evidence_refs: list[str]
        receipt_refs: list[str]
        residual_risk_refs: list[str]
        next_action_refs: list[str]

    receipt = summarize_codex_secondary_integration_adoption_decision_archive_followup_closure_receipt(
        FollowupClosureReceipt(
            "receipt-9",
            "complete",
            "closure-receipt",
            ["closure-readiness"],
            ["disposition-preview"],
            ["owner-signoff"],
            ["closure-criteria"],
            ["validation"],
            ["evidence"],
            ["receipt"],
            ["none"],
            ["next-action"],
        )
    )

    assert receipt.receipt_id == "receipt-9"
    assert receipt.status == "complete"
    assert receipt.readiness_state == "ready"
