from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_closure_index_packet import (
    build_codex_secondary_integration_closure_index_packet,
    summarize_codex_secondary_integration_closure_index,
)


PACKET_POLICIES = {
    "closure_index_policy": "closure-index-policy",
    "secondary_batch_policy": "secondary-batch-policy",
    "unresolved_item_policy": "unresolved-item-policy",
    "index_freshness_policy": "index-freshness-policy",
    "secondary_integration_closure_index_manifest_ref": "closure-index-manifest",
    "secondary_integration_closure_governance_ref": "closure-governance",
}


def test_ready_secondary_integration_closure_index_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_closure_index_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-1",
                    "status": "indexed",
                    "closure_index_ref": "closure-index",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "mainline_evaluation_receipt_refs": ["mainline-receipt"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                    "unresolved_item_refs": ["none"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_closure_index_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["closure_count"] == 1
    assert packet["summary"]["mainline_evaluation_receipt_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_closure_index_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_closure_index_packet(
        {
            "closures": [
                {
                    "closure_id": "closure-2",
                    "status": "current",
                    "closure_index_ref": "closure-index",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "mainline_evaluation_receipt_refs": ["mainline-receipt"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_closure_index_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "closure_index_policy_ref",
        "secondary_batch_policy_ref",
        "unresolved_item_policy_ref",
        "index_freshness_policy_ref",
        "secondary_integration_closure_index_manifest_ref",
        "secondary_integration_closure_governance_ref",
    ]


def test_failed_or_stale_closure_index_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_closure_index_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-3",
                    "status": "stale",
                    "closure_index_ref": "closure-index",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "mainline_evaluation_receipt_refs": ["mainline-receipt"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                }
            ],
        }
    )

    closure = packet["closures"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_closure_index_status_failed"
    assert "codex_secondary_integration_closure_index_status_failed" in closure["blockers"]


def test_missing_closure_index_refs_needs_review() -> None:
    closure = summarize_codex_secondary_integration_closure_index(
        {
            "closure_id": "closure-4",
            "status": "indexed",
            "closure_index_ref": "closure-index",
        }
    )

    assert closure.readiness_state == "needs_review"
    assert "batch_snapshot_refs" in closure.missing_refs
    assert "decision_brief_refs" in closure.missing_refs
    assert "mainline_evaluation_receipt_refs" in closure.missing_refs
    assert "adoption_readiness_refs" in closure.missing_refs
    assert "validation_refs" in closure.missing_refs
    assert "risk_refs" in closure.missing_refs
    assert "skipped_item_refs" in closure.missing_refs


def test_open_closure_index_requires_unresolved_item_refs() -> None:
    closure = summarize_codex_secondary_integration_closure_index(
        {
            "closure_id": "closure-5",
            "status": "needs-review",
            "closure_index_ref": "closure-index",
            "batch_snapshot_refs": ["batch-snapshot"],
            "decision_brief_refs": ["decision-brief"],
            "mainline_evaluation_receipt_refs": ["mainline-receipt"],
            "adoption_readiness_refs": ["adoption-readiness"],
            "validation_refs": ["validation"],
            "risk_refs": ["risk"],
            "skipped_item_refs": ["skipped-items"],
        }
    )

    assert closure.readiness_state == "needs_review"
    assert "unresolved_item_refs" in closure.missing_refs
    assert "codex_secondary_integration_closure_index_still_open" in closure.warnings


def test_stale_index_warning_drives_refresh_action() -> None:
    packet = build_codex_secondary_integration_closure_index_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-6",
                    "status": "indexed",
                    "closure_index_ref": "closure-index",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "mainline_evaluation_receipt_refs": ["mainline-receipt"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                    "unresolved_item_refs": ["unresolved"],
                    "stale_index_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_closure_index_stale"
    assert packet["next_actions"] == [
        "review_stale_secondary_integration_closure_index",
        "refresh_secondary_integration_closure_index",
    ]


def test_live_index_manifest_stage_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_closure_index_packet(
        {
            **PACKET_POLICIES,
            "closures": [
                {
                    "closure_id": "closure-7",
                    "status": "current",
                    "closure_index_ref": "closure-index",
                    "batch_snapshot_refs": ["batch-snapshot"],
                    "decision_brief_refs": ["decision-brief"],
                    "mainline_evaluation_receipt_refs": ["mainline-receipt"],
                    "adoption_readiness_refs": ["adoption-readiness"],
                    "validation_refs": ["validation"],
                    "risk_refs": ["risk"],
                    "skipped_item_refs": ["skipped-items"],
                    "closure_index_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_closure_index_live_operation_blocked"
    assert "live_codex_secondary_integration_closure_index_operation_attempted" in packet["closures"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_closure_index_inventory() -> None:
    packet = build_codex_secondary_integration_closure_index_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_closure_index_inventory"]


def test_dataclass_like_closure_index_is_accepted_by_summarizer() -> None:
    @dataclass
    class ClosureIndex:
        closure_id: str
        status: str
        closure_index_ref: str
        batch_snapshot_refs: list[str]
        decision_brief_refs: list[str]
        mainline_evaluation_receipt_refs: list[str]
        adoption_readiness_refs: list[str]
        validation_refs: list[str]
        risk_refs: list[str]
        skipped_item_refs: list[str]
        unresolved_item_refs: list[str]

    closure = summarize_codex_secondary_integration_closure_index(
        ClosureIndex(
            "closure-8",
            "current",
            "closure-index",
            ["batch-snapshot"],
            ["decision-brief"],
            ["mainline-receipt"],
            ["adoption-readiness"],
            ["validation"],
            ["risk"],
            ["skipped-items"],
            ["none"],
        )
    )

    assert closure.closure_id == "closure-8"
    assert closure.status == "current"
    assert closure.readiness_state == "ready"
