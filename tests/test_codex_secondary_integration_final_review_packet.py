from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_final_review_packet import (
    build_codex_secondary_integration_final_review_packet,
    summarize_codex_secondary_integration_final_review,
)


PACKET_POLICIES = {
    "final_review_policy": "final-review-policy",
    "owner_acceptance_policy": "owner-acceptance-policy",
    "residual_risk_policy": "residual-risk-policy",
    "secondary_integration_policy": "secondary-integration-policy",
    "secondary_integration_final_review_manifest_ref": "final-review-manifest",
    "secondary_integration_final_review_governance_ref": "final-review-governance",
}


def test_ready_secondary_integration_final_review_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_final_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-1",
                    "status": "approved",
                    "final_review_ref": "final-review",
                    "closure_index_refs": ["closure-index"],
                    "evaluation_receipt_refs": ["evaluation-receipt"],
                    "decision_brief_refs": ["decision-brief"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "residual_risk_refs": ["residual-risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                    "final_next_action_refs": ["next-action"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_final_review_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["review_count"] == 1
    assert packet["summary"]["owner_acceptance_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_final_review_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_final_review_packet(
        {
            "reviews": [
                {
                    "review_id": "review-2",
                    "status": "accepted",
                    "final_review_ref": "final-review",
                    "closure_index_refs": ["closure-index"],
                    "evaluation_receipt_refs": ["evaluation-receipt"],
                    "decision_brief_refs": ["decision-brief"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "residual_risk_refs": ["residual-risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_final_review_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "final_review_policy_ref",
        "owner_acceptance_policy_ref",
        "residual_risk_policy_ref",
        "secondary_integration_policy_ref",
        "secondary_integration_final_review_manifest_ref",
        "secondary_integration_final_review_governance_ref",
    ]


def test_rejected_or_regressed_final_review_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_final_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-3",
                    "status": "rejected",
                    "final_review_ref": "final-review",
                    "closure_index_refs": ["closure-index"],
                    "evaluation_receipt_refs": ["evaluation-receipt"],
                    "decision_brief_refs": ["decision-brief"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "residual_risk_refs": ["residual-risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    review = packet["reviews"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_final_review_status_failed"
    assert "codex_secondary_integration_final_review_status_failed" in review["blockers"]


def test_missing_final_review_refs_needs_review() -> None:
    review = summarize_codex_secondary_integration_final_review(
        {
            "review_id": "review-4",
            "status": "approved",
            "final_review_ref": "final-review",
        }
    )

    assert review.readiness_state == "needs_review"
    assert "closure_index_refs" in review.missing_refs
    assert "evaluation_receipt_refs" in review.missing_refs
    assert "decision_brief_refs" in review.missing_refs
    assert "owner_acceptance_refs" in review.missing_refs
    assert "residual_risk_refs" in review.missing_refs
    assert "validation_refs" in review.missing_refs
    assert "skipped_item_refs" in review.missing_refs
    assert "artifact_refs" in review.missing_refs


def test_open_final_review_requires_final_next_action_refs() -> None:
    review = summarize_codex_secondary_integration_final_review(
        {
            "review_id": "review-5",
            "status": "needs-review",
            "final_review_ref": "final-review",
            "closure_index_refs": ["closure-index"],
            "evaluation_receipt_refs": ["evaluation-receipt"],
            "decision_brief_refs": ["decision-brief"],
            "owner_acceptance_refs": ["owner-acceptance"],
            "residual_risk_refs": ["residual-risk"],
            "validation_refs": ["validation"],
            "skipped_item_refs": ["skipped-items"],
            "artifact_refs": ["artifact"],
        }
    )

    assert review.readiness_state == "needs_review"
    assert "final_next_action_refs" in review.missing_refs
    assert "codex_secondary_integration_final_review_still_open" in review.warnings


def test_residual_risk_warning_drives_final_action_decision() -> None:
    packet = build_codex_secondary_integration_final_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-6",
                    "status": "approved",
                    "final_review_ref": "final-review",
                    "closure_index_refs": ["closure-index"],
                    "evaluation_receipt_refs": ["evaluation-receipt"],
                    "decision_brief_refs": ["decision-brief"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "residual_risk_refs": ["residual-risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                    "final_next_action_refs": ["next-action"],
                    "residual_risk_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_final_review_residual_risk"
    assert packet["next_actions"] == [
        "review_secondary_integration_residual_risks",
        "decide_secondary_integration_final_action",
    ]


def test_owner_acceptance_pending_drives_owner_request() -> None:
    packet = build_codex_secondary_integration_final_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-7",
                    "status": "validated",
                    "final_review_ref": "final-review",
                    "closure_index_refs": ["closure-index"],
                    "evaluation_receipt_refs": ["evaluation-receipt"],
                    "decision_brief_refs": ["decision-brief"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "residual_risk_refs": ["residual-risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                    "owner_acceptance_pending": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_final_review_owner_acceptance_pending"
    assert packet["next_actions"] == [
        "request_secondary_integration_owner_acceptance",
        "refresh_final_review_packet",
    ]


def test_live_approval_manifest_stage_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_final_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-8",
                    "status": "accepted",
                    "final_review_ref": "final-review",
                    "closure_index_refs": ["closure-index"],
                    "evaluation_receipt_refs": ["evaluation-receipt"],
                    "decision_brief_refs": ["decision-brief"],
                    "owner_acceptance_refs": ["owner-acceptance"],
                    "residual_risk_refs": ["residual-risk"],
                    "validation_refs": ["validation"],
                    "skipped_item_refs": ["skipped-items"],
                    "artifact_refs": ["artifact"],
                    "final_approval_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_final_review_live_operation_blocked"
    assert "live_codex_secondary_integration_final_review_operation_attempted" in packet["reviews"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_final_review_inventory() -> None:
    packet = build_codex_secondary_integration_final_review_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_final_review_inventory"]


def test_dataclass_like_final_review_is_accepted_by_summarizer() -> None:
    @dataclass
    class FinalReview:
        review_id: str
        status: str
        final_review_ref: str
        closure_index_refs: list[str]
        evaluation_receipt_refs: list[str]
        decision_brief_refs: list[str]
        owner_acceptance_refs: list[str]
        residual_risk_refs: list[str]
        validation_refs: list[str]
        skipped_item_refs: list[str]
        artifact_refs: list[str]
        final_next_action_refs: list[str]

    review = summarize_codex_secondary_integration_final_review(
        FinalReview(
            "review-9",
            "complete",
            "final-review",
            ["closure-index"],
            ["evaluation-receipt"],
            ["decision-brief"],
            ["owner-acceptance"],
            ["residual-risk"],
            ["validation"],
            ["skipped-items"],
            ["artifact"],
            ["next-action"],
        )
    )

    assert review.review_id == "review-9"
    assert review.status == "complete"
    assert review.readiness_state == "ready"
