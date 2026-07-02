from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_gap_matrix_owner_review_packet import (
    build_codex_gap_matrix_owner_review_packet,
    summarize_codex_gap_matrix_owner_review,
)


PACKET_POLICIES = {
    "gap_matrix_review_policy": "gap-matrix-review-policy",
    "owner_review_policy": "owner-review-policy",
    "mainline_acceptance_policy": "mainline-acceptance-policy",
    "residual_gap_decision_policy": "residual-gap-decision-policy",
    "codex_gap_matrix_owner_review_manifest_ref": "owner-review-manifest",
    "codex_parity_owner_governance_ref": "codex-parity-owner-governance",
}


def test_ready_codex_gap_matrix_owner_review_has_complete_evidence() -> None:
    packet = build_codex_gap_matrix_owner_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-1",
                    "status": "accepted",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_reviewer_refs": ["owner-reviewer"],
                    "mainline_review_refs": ["mainline-review"],
                    "acceptance_decision_refs": ["acceptance-decision"],
                    "residual_gap_decision_refs": ["residual-decision"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                    "next_candidate_refs": ["next-candidate"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_gap_matrix_owner_review_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["review_count"] == 1
    assert packet["summary"]["acceptance_decision_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_gap_matrix_owner_review_packet_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_gap_matrix_owner_review_packet(
        {
            "reviews": [
                {
                    "review_id": "review-2",
                    "status": "approved",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_reviewer_refs": ["owner-reviewer"],
                    "mainline_review_refs": ["mainline-review"],
                    "acceptance_decision_refs": ["acceptance-decision"],
                    "residual_gap_decision_refs": ["residual-decision"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_owner_review_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "gap_matrix_review_policy_ref",
        "owner_review_policy_ref",
        "mainline_acceptance_policy_ref",
        "residual_gap_decision_policy_ref",
        "codex_gap_matrix_owner_review_manifest_ref",
        "codex_parity_owner_governance_ref",
    ]


def test_blocked_or_rejected_owner_review_blocks_candidate() -> None:
    packet = build_codex_gap_matrix_owner_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-3",
                    "status": "rejected",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_reviewer_refs": ["owner-reviewer"],
                    "mainline_review_refs": ["mainline-review"],
                    "acceptance_decision_refs": ["acceptance-decision"],
                    "residual_gap_decision_refs": ["residual-decision"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    review = packet["reviews"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_owner_review_status_failed"
    assert "codex_gap_matrix_owner_review_status_failed" in review["blockers"]


def test_missing_review_refs_needs_review() -> None:
    review = summarize_codex_gap_matrix_owner_review(
        {
            "review_id": "review-4",
            "status": "reviewed",
            "gap_matrix_ref": "gap-matrix",
        }
    )

    assert review.readiness_state == "needs_review"
    assert "owner_reviewer_refs" in review.missing_refs
    assert "mainline_review_refs" in review.missing_refs
    assert "acceptance_decision_refs" in review.missing_refs
    assert "residual_gap_decision_refs" in review.missing_refs
    assert "validation_receipt_refs" in review.missing_refs
    assert "handoff_refs" in review.missing_refs
    assert "artifact_refs" in review.missing_refs


def test_open_owner_review_requires_next_candidate_ref() -> None:
    review = summarize_codex_gap_matrix_owner_review(
        {
            "review_id": "review-5",
            "status": "needs-review",
            "gap_matrix_ref": "gap-matrix",
            "owner_reviewer_refs": ["owner-reviewer"],
            "mainline_review_refs": ["mainline-review"],
            "acceptance_decision_refs": ["acceptance-decision"],
            "residual_gap_decision_refs": ["residual-decision"],
            "validation_receipt_refs": ["validation"],
            "handoff_refs": ["handoff"],
            "artifact_refs": ["artifact"],
        }
    )

    assert review.readiness_state == "needs_review"
    assert "next_candidate_refs" in review.missing_refs
    assert "codex_gap_matrix_owner_review_still_open" in review.warnings


def test_residual_gap_warning_drives_next_candidate_queue() -> None:
    packet = build_codex_gap_matrix_owner_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-6",
                    "status": "accepted",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_reviewer_refs": ["owner-reviewer"],
                    "mainline_review_refs": ["mainline-review"],
                    "acceptance_decision_refs": ["acceptance-decision"],
                    "residual_gap_decision_refs": ["residual-decision"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                    "next_candidate_refs": ["next-candidate"],
                    "residual_gap_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_owner_review_residual_gap"
    assert packet["next_actions"] == [
        "review_codex_gap_matrix_owner_residual_gaps",
        "queue_next_codex_gap_candidate",
    ]


def test_live_owner_mainline_manifest_stage_or_scoring_mutation_blocks_candidate() -> None:
    packet = build_codex_gap_matrix_owner_review_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-7",
                    "status": "approved",
                    "gap_matrix_ref": "gap-matrix",
                    "owner_reviewer_refs": ["owner-reviewer"],
                    "mainline_review_refs": ["mainline-review"],
                    "acceptance_decision_refs": ["acceptance-decision"],
                    "residual_gap_decision_refs": ["residual-decision"],
                    "validation_receipt_refs": ["validation"],
                    "handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                    "owner_decision_mutation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_gap_matrix_owner_review_live_operation_blocked"
    assert "live_codex_gap_matrix_owner_review_operation_attempted" in packet["reviews"][0]["blockers"]


def test_empty_payload_requests_codex_gap_matrix_owner_review_inventory() -> None:
    packet = build_codex_gap_matrix_owner_review_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_gap_matrix_owner_review_inventory"]


def test_dataclass_like_owner_review_is_accepted_by_summarizer() -> None:
    @dataclass
    class OwnerReview:
        review_id: str
        status: str
        gap_matrix_ref: str
        owner_reviewer_refs: list[str]
        mainline_review_refs: list[str]
        acceptance_decision_refs: list[str]
        residual_gap_decision_refs: list[str]
        validation_receipt_refs: list[str]
        handoff_refs: list[str]
        artifact_refs: list[str]
        next_candidate_refs: list[str]

    review = summarize_codex_gap_matrix_owner_review(
        OwnerReview(
            "review-8",
            "validated",
            "gap-matrix",
            ["owner-reviewer"],
            ["mainline-review"],
            ["acceptance-decision"],
            ["residual-decision"],
            ["validation"],
            ["handoff"],
            ["artifact"],
            ["next-candidate"],
        )
    )

    assert review.review_id == "review-8"
    assert review.status == "validated"
    assert review.readiness_state == "ready"
