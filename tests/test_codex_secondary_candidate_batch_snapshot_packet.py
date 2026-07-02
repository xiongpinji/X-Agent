from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_candidate_batch_snapshot_packet import (
    build_codex_secondary_candidate_batch_snapshot_packet,
    summarize_codex_secondary_candidate_batch_snapshot,
)


PACKET_POLICIES = {
    "candidate_batch_policy": "candidate-batch-policy",
    "batch_readiness_policy": "batch-readiness-policy",
    "batch_risk_policy": "batch-risk-policy",
    "next_batch_policy": "next-batch-policy",
    "secondary_candidate_batch_manifest_ref": "secondary-candidate-batch-manifest",
    "secondary_candidate_batch_governance_ref": "secondary-candidate-batch-governance",
}


def test_ready_secondary_candidate_batch_snapshot_has_complete_evidence() -> None:
    packet = build_codex_secondary_candidate_batch_snapshot_packet(
        {
            **PACKET_POLICIES,
            "batches": [
                {
                    "batch_id": "batch-1",
                    "status": "batched",
                    "batch_ref": "batch",
                    "candidate_refs": ["candidate"],
                    "readiness_rollup_refs": ["readiness-rollup"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_receipt_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "skipped_item_refs": ["skipped-items"],
                    "next_batch_refs": ["next-batch"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_candidate_batch_snapshot_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["batch_count"] == 1
    assert packet["summary"]["candidate_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_candidate_batch_snapshot_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_candidate_batch_snapshot_packet(
        {
            "batches": [
                {
                    "batch_id": "batch-2",
                    "status": "validated",
                    "batch_ref": "batch",
                    "candidate_refs": ["candidate"],
                    "readiness_rollup_refs": ["readiness-rollup"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_receipt_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "skipped_item_refs": ["skipped-items"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_candidate_batch_snapshot_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "candidate_batch_policy_ref",
        "batch_readiness_policy_ref",
        "batch_risk_policy_ref",
        "next_batch_policy_ref",
        "secondary_candidate_batch_manifest_ref",
        "secondary_candidate_batch_governance_ref",
    ]


def test_rejected_or_regressed_batch_snapshot_blocks_candidate() -> None:
    packet = build_codex_secondary_candidate_batch_snapshot_packet(
        {
            **PACKET_POLICIES,
            "batches": [
                {
                    "batch_id": "batch-3",
                    "status": "regressed",
                    "batch_ref": "batch",
                    "candidate_refs": ["candidate"],
                    "readiness_rollup_refs": ["readiness-rollup"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_receipt_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "skipped_item_refs": ["skipped-items"],
                }
            ],
        }
    )

    batch = packet["batches"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_candidate_batch_snapshot_status_failed"
    assert "codex_secondary_candidate_batch_snapshot_status_failed" in batch["blockers"]


def test_missing_batch_refs_needs_review() -> None:
    batch = summarize_codex_secondary_candidate_batch_snapshot(
        {
            "batch_id": "batch-4",
            "status": "reviewed",
            "batch_ref": "batch",
        }
    )

    assert batch.readiness_state == "needs_review"
    assert "candidate_refs" in batch.missing_refs
    assert "readiness_rollup_refs" in batch.missing_refs
    assert "adoption_readiness_refs" in batch.missing_refs
    assert "validation_receipt_refs" in batch.missing_refs
    assert "risk_refs" in batch.missing_refs
    assert "owner_mainline_review_refs" in batch.missing_refs
    assert "skipped_item_refs" in batch.missing_refs


def test_open_batch_requires_next_batch_refs() -> None:
    batch = summarize_codex_secondary_candidate_batch_snapshot(
        {
            "batch_id": "batch-5",
            "status": "needs-review",
            "batch_ref": "batch",
            "candidate_refs": ["candidate"],
            "readiness_rollup_refs": ["readiness-rollup"],
            "adoption_readiness_refs": ["adoption-readiness"],
            "validation_receipt_refs": ["validation"],
            "risk_refs": ["risk"],
            "owner_mainline_review_refs": ["owner-mainline-review"],
            "skipped_item_refs": ["skipped-items"],
        }
    )

    assert batch.readiness_state == "needs_review"
    assert "next_batch_refs" in batch.missing_refs
    assert "codex_secondary_candidate_batch_snapshot_still_open" in batch.warnings


def test_integration_risk_warning_drives_next_batch_planning() -> None:
    packet = build_codex_secondary_candidate_batch_snapshot_packet(
        {
            **PACKET_POLICIES,
            "batches": [
                {
                    "batch_id": "batch-6",
                    "status": "batched",
                    "batch_ref": "batch",
                    "candidate_refs": ["candidate"],
                    "readiness_rollup_refs": ["readiness-rollup"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_receipt_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "skipped_item_refs": ["skipped-items"],
                    "next_batch_refs": ["next-batch"],
                    "integration_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_candidate_batch_snapshot_risk"
    assert packet["next_actions"] == [
        "review_secondary_candidate_batch_risks",
        "plan_next_secondary_candidate_batch",
    ]


def test_live_batch_mainline_manifest_stage_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_candidate_batch_snapshot_packet(
        {
            **PACKET_POLICIES,
            "batches": [
                {
                    "batch_id": "batch-7",
                    "status": "accepted",
                    "batch_ref": "batch",
                    "candidate_refs": ["candidate"],
                    "readiness_rollup_refs": ["readiness-rollup"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_receipt_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "owner_mainline_review_refs": ["owner-mainline-review"],
                    "skipped_item_refs": ["skipped-items"],
                    "batch_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_candidate_batch_snapshot_live_operation_blocked"
    assert "live_codex_secondary_candidate_batch_snapshot_operation_attempted" in packet["batches"][0]["blockers"]


def test_empty_payload_requests_secondary_candidate_batch_inventory() -> None:
    packet = build_codex_secondary_candidate_batch_snapshot_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_candidate_batch_snapshot_inventory"]


def test_dataclass_like_batch_snapshot_is_accepted_by_summarizer() -> None:
    @dataclass
    class Batch:
        batch_id: str
        status: str
        batch_ref: str
        candidate_refs: list[str]
        readiness_rollup_refs: list[str]
        adoption_readiness_refs: list[str]
        validation_receipt_refs: list[str]
        risk_refs: list[str]
        owner_mainline_review_refs: list[str]
        skipped_item_refs: list[str]
        next_batch_refs: list[str]

    batch = summarize_codex_secondary_candidate_batch_snapshot(
        Batch(
            "batch-8",
            "validated",
            "batch",
            ["candidate"],
            ["readiness-rollup"],
            ["adoption-readiness"],
            ["validation"],
            ["risk"],
            ["owner-mainline-review"],
            ["skipped-items"],
            ["next-batch"],
        )
    )

    assert batch.batch_id == "batch-8"
    assert batch.status == "validated"
    assert batch.readiness_state == "ready"
