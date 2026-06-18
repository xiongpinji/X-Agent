from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_mainline_evaluation_receipt_packet import (
    build_codex_mainline_evaluation_receipt_packet,
    summarize_codex_mainline_evaluation_receipt,
)


PACKET_POLICIES = {
    "mainline_receipt_policy": "mainline-receipt-policy",
    "candidate_classification_policy": "candidate-classification-policy",
    "evaluation_receipt_policy": "evaluation-receipt-policy",
    "next_action_policy": "next-action-policy",
    "mainline_evaluation_receipt_manifest_ref": "mainline-evaluation-receipt-manifest",
    "mainline_evaluation_governance_ref": "mainline-evaluation-governance",
}


def test_ready_mainline_evaluation_receipt_has_complete_evidence() -> None:
    packet = build_codex_mainline_evaluation_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-1",
                    "status": "evaluated",
                    "mainline_read_receipt_ref": "read-receipt",
                    "candidate_classification_refs": ["classification"],
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                    "next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_mainline_evaluation_receipt_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["receipt_count"] == 1
    assert packet["summary"]["candidate_classification_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_mainline_evaluation_receipt_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_mainline_evaluation_receipt_packet(
        {
            "receipts": [
                {
                    "receipt_id": "receipt-2",
                    "status": "classified",
                    "mainline_read_receipt_ref": "read-receipt",
                    "candidate_classification_refs": ["classification"],
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_mainline_evaluation_receipt_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "mainline_receipt_policy_ref",
        "candidate_classification_policy_ref",
        "evaluation_receipt_policy_ref",
        "next_action_policy_ref",
        "mainline_evaluation_receipt_manifest_ref",
        "mainline_evaluation_governance_ref",
    ]


def test_failed_or_stale_mainline_receipt_blocks_candidate() -> None:
    packet = build_codex_mainline_evaluation_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-3",
                    "status": "stale",
                    "mainline_read_receipt_ref": "read-receipt",
                    "candidate_classification_refs": ["classification"],
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                }
            ],
        }
    )

    receipt = packet["receipts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_mainline_evaluation_receipt_status_failed"
    assert "codex_mainline_evaluation_receipt_status_failed" in receipt["blockers"]


def test_missing_receipt_refs_needs_review() -> None:
    receipt = summarize_codex_mainline_evaluation_receipt(
        {
            "receipt_id": "receipt-4",
            "status": "evaluated",
            "mainline_read_receipt_ref": "read-receipt",
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "candidate_classification_refs" in receipt.missing_refs
    assert "batch_snapshot_refs" in receipt.missing_refs
    assert "decision_brief_refs" in receipt.missing_refs
    assert "adoption_readiness_refs" in receipt.missing_refs
    assert "validation_refs" in receipt.missing_refs
    assert "risk_refs" in receipt.missing_refs
    assert "skipped_item_refs" in receipt.missing_refs


def test_open_receipt_requires_next_action_refs() -> None:
    receipt = summarize_codex_mainline_evaluation_receipt(
        {
            "receipt_id": "receipt-5",
            "status": "needs-review",
            "mainline_read_receipt_ref": "read-receipt",
            "candidate_classification_refs": ["classification"],
            "batch_snapshot_refs": ["batch-snapshot"],
            "decision_brief_refs": ["decision-brief"],
            "adoption_readiness_refs": ["adoption-readiness"],
            "validation_refs": ["validation"],
            "risk_refs": ["risk"],
            "skipped_item_refs": ["skipped-items"],
        }
    )

    assert receipt.readiness_state == "needs_review"
    assert "next_action_refs" in receipt.missing_refs
    assert "codex_mainline_evaluation_receipt_still_open" in receipt.warnings


def test_stale_receipt_warning_drives_refresh_action() -> None:
    packet = build_codex_mainline_evaluation_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-6",
                    "status": "evaluated",
                    "mainline_read_receipt_ref": "read-receipt",
                    "candidate_classification_refs": ["classification"],
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                    "next_action_refs": ["next-action"],
                    "stale_receipt_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_mainline_evaluation_receipt_stale"
    assert packet["next_actions"] == [
        "review_stale_mainline_evaluation_receipts",
        "refresh_secondary_candidate_evaluation",
    ]


def test_live_notification_receipt_classification_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_mainline_evaluation_receipt_packet(
        {
            **PACKET_POLICIES,
            "receipts": [
                {
                    "receipt_id": "receipt-7",
                    "status": "classified",
                    "mainline_read_receipt_ref": "read-receipt",
                    "candidate_classification_refs": ["classification"],
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                    "mainline_receipt_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_mainline_evaluation_receipt_live_operation_blocked"
    assert "live_codex_mainline_evaluation_receipt_operation_attempted" in packet["receipts"][0]["blockers"]


def test_empty_payload_requests_mainline_evaluation_receipt_inventory() -> None:
    packet = build_codex_mainline_evaluation_receipt_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_mainline_evaluation_receipt_inventory"]


def test_dataclass_like_mainline_evaluation_receipt_is_accepted_by_summarizer() -> None:
    @dataclass
    class Receipt:
        receipt_id: str
        status: str
        mainline_read_receipt_ref: str
        candidate_classification_refs: list[str]
        batch_snapshot_refs: list[str]
        decision_brief_refs: list[str]
        adoption_readiness_refs: list[str]
        validation_refs: list[str]
        risk_refs: list[str]
        skipped_item_refs: list[str]
        next_action_refs: list[str]

    receipt = summarize_codex_mainline_evaluation_receipt(
        Receipt(
            "receipt-8",
            "classified",
            "read-receipt",
            ["classification"],
            ["batch-snapshot"],
            ["decision-brief"],
            ["adoption-readiness"],
            ["validation"],
            ["risk"],
            ["skipped-items"],
            ["next-action"],
        )
    )

    assert receipt.receipt_id == "receipt-8"
    assert receipt.status == "classified"
    assert receipt.readiness_state == "ready"
