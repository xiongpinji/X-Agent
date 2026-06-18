from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_pr_delivery_readiness_packet import (
    build_codex_pr_delivery_readiness_packet,
    summarize_codex_pr_delivery,
)


PACKET_POLICIES = {
    "delivery_policy": "delivery-policy",
    "review_policy": "review-policy",
    "ci_policy": "ci-policy",
    "redaction_policy": "redaction-policy",
    "reviewer_policy_ref": "reviewer-policy",
    "delivery_manifest_ref": "delivery-manifest",
}


def test_ready_github_pr_delivery_with_diff_ci_review_and_receipts() -> None:
    packet = build_codex_pr_delivery_readiness_packet(
        {
            **PACKET_POLICIES,
            "deliveries": [
                {
                    "delivery_id": "delivery-1",
                    "provider": "github",
                    "review_status": "open",
                    "dry_run": True,
                    "diff_refs": ["diff.patch"],
                    "branch_refs": ["feature/codex-gap"],
                    "commit_refs": ["abc123"],
                    "pr_refs": ["PR-42"],
                    "ci_check_refs": ["pytest", "lint"],
                    "ci_states": ["passed", "success"],
                    "file_change_refs": ["summary.json"],
                    "risk_labels": ["docs"],
                    "reviewer_handoff_refs": ["handoff.md#pr"],
                    "artifact_refs": ["pytest.log"],
                    "validation_refs": ["validation-receipt"],
                    "redaction_refs": ["secret-scan"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_pr_delivery_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["delivery_count"] == 1
    assert packet["summary"]["pr_ref_count"] == 1
    assert packet["next_actions"] == ["share_pr_delivery_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_pr_delivery_readiness_packet(
        {
            "deliveries": [
                {
                    "delivery_id": "delivery-1",
                    "provider": "github",
                    "review_status": "open",
                    "dry_run": True,
                    "diff_refs": ["diff"],
                    "branch_refs": ["branch"],
                    "commit_refs": ["commit"],
                    "pr_refs": ["PR-1"],
                    "ci_check_refs": ["pytest"],
                    "ci_states": ["passed"],
                    "file_change_refs": ["files"],
                    "reviewer_handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                    "validation_refs": ["validation"],
                    "redaction_refs": ["redaction"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_pr_delivery_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "delivery_policy_ref",
        "review_policy_ref",
        "ci_policy_ref",
        "redaction_policy_ref",
        "reviewer_policy_ref",
        "delivery_manifest_ref",
    ]


def test_non_dry_run_delivery_is_blocked_for_secondary_candidate() -> None:
    packet = build_codex_pr_delivery_readiness_packet(
        {
            **PACKET_POLICIES,
            "deliveries": [
                {
                    "delivery_id": "delivery-2",
                    "provider": "github",
                    "review_status": "open",
                    "dry_run": False,
                    "diff_refs": ["diff"],
                    "branch_refs": ["branch"],
                    "commit_refs": ["commit"],
                    "pr_refs": ["PR-2"],
                    "ci_check_refs": ["pytest"],
                    "ci_states": ["passed"],
                    "file_change_refs": ["files"],
                    "reviewer_handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                    "validation_refs": ["validation"],
                    "redaction_refs": ["redaction"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_pr_delivery_non_dry_run_blocked"
    assert "non_dry_run_delivery_requires_mainline_execution" in packet["deliveries"][0]["blockers"]


def test_failed_ci_blocks_delivery() -> None:
    packet = build_codex_pr_delivery_readiness_packet(
        {
            **PACKET_POLICIES,
            "deliveries": [
                {
                    "delivery_id": "delivery-3",
                    "provider": "github",
                    "review_status": "open",
                    "dry_run": True,
                    "diff_refs": ["diff"],
                    "branch_refs": ["branch"],
                    "commit_refs": ["commit"],
                    "pr_refs": ["PR-3"],
                    "ci_check_refs": ["pytest"],
                    "ci_states": ["failed"],
                    "file_change_refs": ["files"],
                    "reviewer_handoff_refs": ["handoff"],
                    "artifact_refs": ["artifact"],
                    "validation_refs": ["validation"],
                    "redaction_refs": ["redaction"],
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_pr_delivery_ci_failed"
    assert packet["next_actions"] == ["resolve_pr_delivery_blockers", "refresh_pr_delivery_readiness"]


def test_high_risk_labels_require_reviewer_handoff() -> None:
    delivery = summarize_codex_pr_delivery(
        {
            "delivery_id": "delivery-4",
            "provider": "github",
            "review_status": "open",
            "dry_run": True,
            "diff_refs": ["diff"],
            "branch_refs": ["branch"],
            "commit_refs": ["commit"],
            "pr_refs": ["PR-4"],
            "ci_check_refs": ["pytest"],
            "ci_states": ["passed"],
            "file_change_refs": ["files"],
            "risk_labels": ["security"],
            "artifact_refs": ["artifact"],
            "validation_refs": ["validation"],
            "redaction_refs": ["redaction"],
        }
    )

    assert delivery.readiness_state == "needs_review"
    assert "reviewer_handoff_refs" in delivery.missing_refs
    assert "pr_delivery_lacks_reviewer_handoff" in delivery.warnings


def test_empty_payload_requests_delivery_inventory() -> None:
    packet = build_codex_pr_delivery_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_pr_delivery_inventory"]


def test_dataclass_like_delivery_is_accepted_by_summarizer() -> None:
    @dataclass
    class Delivery:
        delivery_id: str
        provider: str
        review_status: str
        dry_run: bool
        diff_refs: list[str]
        branch_refs: list[str]
        commit_refs: list[str]
        pr_refs: list[str]
        ci_check_refs: list[str]
        ci_states: list[str]
        file_change_refs: list[str]
        reviewer_handoff_refs: list[str]
        artifact_refs: list[str]
        validation_refs: list[str]
        redaction_refs: list[str]

    delivery = summarize_codex_pr_delivery(
        Delivery(
            "delivery-5",
            "github",
            "open",
            True,
            ["diff"],
            ["branch"],
            ["commit"],
            ["PR-5"],
            ["pytest"],
            ["passed"],
            ["files"],
            ["handoff"],
            ["artifact"],
            ["validation"],
            ["redaction"],
        )
    )

    assert delivery.delivery_id == "delivery-5"
    assert delivery.provider == "github"
    assert delivery.readiness_state == "ready"
