from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_review_comment_readiness_packet import (
    build_codex_review_comment_readiness_packet,
    summarize_codex_review_comment,
)


PACKET_POLICIES = {
    "review_policy": "review-policy",
    "comment_fetch_policy": "comment-fetch-policy",
    "response_policy": "response-policy",
    "closure_policy": "closure-policy",
    "provider_auth_ref": "gh-auth",
    "feedback_manifest_ref": "feedback-manifest",
}


def test_ready_resolved_pr_review_comment_with_closure_receipts() -> None:
    packet = build_codex_review_comment_readiness_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-1",
                    "provider": "github",
                    "response_status": "resolved",
                    "pr_ref": "PR-42",
                    "review_thread_ref": "thread-1",
                    "comment_refs": ["comment-1"],
                    "inline_comment_refs": ["inline-1"],
                    "requested_change_refs": ["change-1"],
                    "issue_thread_refs": ["issue-1"],
                    "changed_file_refs": ["backend/app/core/service.py"],
                    "owner_assignment_refs": ["owner-a"],
                    "fix_validation_refs": ["pytest receipt"],
                    "reviewer_handoff_refs": ["handoff.md#review"],
                    "closure_receipts": ["closed-by-reviewer"],
                    "artifact_refs": ["review-summary.json"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_review_comment_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["review_count"] == 1
    assert packet["summary"]["closure_receipt_count"] == 1
    assert packet["next_actions"] == ["share_review_comment_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_review_comment_readiness_packet(
        {
            "reviews": [
                {
                    "review_id": "review-1",
                    "provider": "github",
                    "response_status": "resolved",
                    "pr_ref": "PR-1",
                    "review_thread_ref": "thread",
                    "comment_refs": ["comment"],
                    "changed_file_refs": ["file"],
                    "closure_receipts": ["closed"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_review_comment_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "review_policy_ref",
        "comment_fetch_policy_ref",
        "response_policy_ref",
        "closure_policy_ref",
        "provider_auth_ref",
        "feedback_manifest_ref",
    ]


def test_requested_changes_without_owner_validation_or_handoff_needs_review() -> None:
    review = summarize_codex_review_comment(
        {
            "review_id": "review-2",
            "provider": "github",
            "response_status": "requested-changes",
            "pr_ref": "PR-2",
            "review_thread_ref": "thread",
            "requested_change_refs": ["change"],
            "changed_file_refs": ["file"],
            "artifact_refs": ["artifact"],
        }
    )

    assert review.readiness_state == "needs_review"
    assert "review_feedback_open" in review.warnings
    assert "owner_assignment_refs" in review.missing_refs
    assert "fix_validation_refs" in review.missing_refs
    assert "reviewer_handoff_refs" in review.missing_refs


def test_blocked_response_status_blocks_packet() -> None:
    packet = build_codex_review_comment_readiness_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-3",
                    "provider": "github",
                    "response_status": "failed",
                    "pr_ref": "PR-3",
                    "review_thread_ref": "thread",
                    "comment_refs": ["comment"],
                    "changed_file_refs": ["file"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_review_comment_response_blocked"
    assert packet["next_actions"] == [
        "resolve_review_comment_blockers",
        "refresh_review_comment_readiness",
    ]


def test_resolved_review_without_closure_receipts_needs_review() -> None:
    packet = build_codex_review_comment_readiness_packet(
        {
            **PACKET_POLICIES,
            "reviews": [
                {
                    "review_id": "review-4",
                    "provider": "github",
                    "response_status": "resolved",
                    "pr_ref": "PR-4",
                    "review_thread_ref": "thread",
                    "comment_refs": ["comment"],
                    "changed_file_refs": ["file"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert "closure_receipts" in packet["reviews"][0]["missing_refs"]
    assert packet["findings"][0]["code"] == "codex_review_comment_missing_evidence"


def test_empty_payload_requests_review_comment_inventory() -> None:
    packet = build_codex_review_comment_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_review_comment_inventory"]


def test_dataclass_like_review_is_accepted_by_summarizer() -> None:
    @dataclass
    class Review:
        review_id: str
        provider: str
        response_status: str
        pr_ref: str
        review_thread_ref: str
        comment_refs: list[str]
        changed_file_refs: list[str]
        closure_receipts: list[str]
        artifact_refs: list[str]

    review = summarize_codex_review_comment(
        Review(
            "review-5",
            "github",
            "resolved",
            "PR-5",
            "thread",
            ["comment"],
            ["file"],
            ["closed"],
            ["artifact"],
        )
    )

    assert review.review_id == "review-5"
    assert review.provider == "github"
    assert review.readiness_state == "ready"
