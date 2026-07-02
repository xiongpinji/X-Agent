from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_followup_routing_packet import (
    build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_followup_routing,
)


PACKET_POLICIES = {
    "archive_followup_routing_policy": "archive-followup-routing-policy",
    "owner_reviewer_policy": "owner-reviewer-policy",
    "due_window_policy": "due-window-policy",
    "routing_evidence_policy": "routing-evidence-policy",
    "secondary_integration_adoption_decision_archive_followup_routing_manifest_ref": "followup-routing-manifest",
    "secondary_integration_adoption_decision_archive_followup_governance_ref": "followup-governance",
}


def test_ready_secondary_integration_archive_followup_routing_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "routing_id": "route-1",
                    "status": "routed",
                    "archive_followup_routing_ref": "followup-routing",
                    "archive_answer_brief_refs": ["answer-brief"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "unresolved_result_refs": ["unresolved"],
                    "citation_review_refs": ["citation-review"],
                    "validation_refs": ["validation"],
                    "routing_refs": ["routing"],
                    "due_window_refs": ["due-window"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_followup_routing_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["routing_count"] == 1
    assert packet["summary"]["owner_followup_ref_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_followup_routing_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(
        {
            "routes": [
                {
                    "routing_id": "route-2",
                    "status": "routed",
                    "archive_followup_routing_ref": "followup-routing",
                    "archive_answer_brief_refs": ["answer-brief"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "unresolved_result_refs": ["unresolved"],
                    "citation_review_refs": ["citation-review"],
                    "validation_refs": ["validation"],
                    "routing_refs": ["routing"],
                    "due_window_refs": ["due-window"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_routing_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "archive_followup_routing_policy_ref",
        "owner_reviewer_policy_ref",
        "due_window_policy_ref",
        "routing_evidence_policy_ref",
        "secondary_integration_adoption_decision_archive_followup_routing_manifest_ref",
        "secondary_integration_adoption_decision_archive_followup_governance_ref",
    ]


def test_failed_or_stale_followup_routing_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "routing_id": "route-3",
                    "status": "stale",
                    "archive_followup_routing_ref": "followup-routing",
                    "archive_answer_brief_refs": ["answer-brief"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "unresolved_result_refs": ["unresolved"],
                    "citation_review_refs": ["citation-review"],
                    "validation_refs": ["validation"],
                    "routing_refs": ["routing"],
                    "due_window_refs": ["due-window"],
                }
            ],
        }
    )

    route = packet["routes"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_routing_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_followup_routing_status_failed" in route["blockers"]


def test_missing_followup_routing_refs_needs_review() -> None:
    route = summarize_codex_secondary_integration_adoption_decision_archive_followup_routing(
        {
            "routing_id": "route-4",
            "status": "routed",
            "archive_followup_routing_ref": "followup-routing",
        }
    )

    assert route.readiness_state == "needs_review"
    assert "archive_answer_brief_refs" in route.missing_refs
    assert "owner_followup_refs" in route.missing_refs
    assert "reviewer_refs" in route.missing_refs
    assert "unresolved_result_refs" in route.missing_refs
    assert "citation_review_refs" in route.missing_refs
    assert "validation_refs" in route.missing_refs
    assert "routing_refs" in route.missing_refs
    assert "due_window_refs" in route.missing_refs


def test_open_followup_routing_warns_until_receipts_attach() -> None:
    route = summarize_codex_secondary_integration_adoption_decision_archive_followup_routing(
        {
            "routing_id": "route-5",
            "status": "needs-review",
            "archive_followup_routing_ref": "followup-routing",
            "archive_answer_brief_refs": ["answer-brief"],
            "owner_followup_refs": ["owner-followup"],
            "reviewer_refs": ["reviewer"],
            "unresolved_result_refs": ["unresolved"],
            "citation_review_refs": ["citation-review"],
            "validation_refs": ["validation"],
            "routing_refs": ["routing"],
            "due_window_refs": ["due-window"],
        }
    )

    assert route.readiness_state == "needs_review"
    assert route.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_followup_routing_still_open" in route.warnings


def test_due_window_warning_drives_due_window_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "routing_id": "route-6",
                    "status": "routed",
                    "archive_followup_routing_ref": "followup-routing",
                    "archive_answer_brief_refs": ["answer-brief"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "unresolved_result_refs": ["unresolved"],
                    "citation_review_refs": ["citation-review"],
                    "validation_refs": ["validation"],
                    "routing_refs": ["routing"],
                    "due_window_refs": ["due-window"],
                    "due_window_missing": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_routing_due_window_review_required"
    assert packet["next_actions"] == [
        "review_archive_followup_due_windows",
        "refresh_archive_followup_routing_packet",
    ]


def test_owner_followup_pending_warning_drives_owner_followup_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "routing_id": "route-7",
                    "status": "assigned",
                    "archive_followup_routing_ref": "followup-routing",
                    "archive_answer_brief_refs": ["answer-brief"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "unresolved_result_refs": ["unresolved"],
                    "citation_review_refs": ["citation-review"],
                    "validation_refs": ["validation"],
                    "routing_refs": ["routing"],
                    "due_window_refs": ["due-window"],
                    "owner_followup_pending": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_routing_owner_followup_pending"
    assert packet["next_actions"] == [
        "review_archive_owner_followups",
        "refresh_archive_followup_routing_packet",
    ]


def test_live_notification_issue_taskboard_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet(
        {
            **PACKET_POLICIES,
            "routes": [
                {
                    "routing_id": "route-8",
                    "status": "routed",
                    "archive_followup_routing_ref": "followup-routing",
                    "archive_answer_brief_refs": ["answer-brief"],
                    "owner_followup_refs": ["owner-followup"],
                    "reviewer_refs": ["reviewer"],
                    "unresolved_result_refs": ["unresolved"],
                    "citation_review_refs": ["citation-review"],
                    "validation_refs": ["validation"],
                    "routing_refs": ["routing"],
                    "due_window_refs": ["due-window"],
                    "notification_dispatch_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_followup_routing_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_followup_routing_operation_attempted" in packet["routes"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_followup_routing_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_followup_routing_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_followup_routing_inventory"]


def test_dataclass_like_archive_followup_routing_is_accepted_by_summarizer() -> None:
    @dataclass
    class FollowupRouting:
        routing_id: str
        status: str
        archive_followup_routing_ref: str
        archive_answer_brief_refs: list[str]
        owner_followup_refs: list[str]
        reviewer_refs: list[str]
        unresolved_result_refs: list[str]
        citation_review_refs: list[str]
        validation_refs: list[str]
        routing_refs: list[str]
        due_window_refs: list[str]

    route = summarize_codex_secondary_integration_adoption_decision_archive_followup_routing(
        FollowupRouting(
            "route-9",
            "complete",
            "followup-routing",
            ["answer-brief"],
            ["owner-followup"],
            ["reviewer"],
            ["unresolved"],
            ["citation-review"],
            ["validation"],
            ["routing"],
            ["due-window"],
        )
    )

    assert route.routing_id == "route-9"
    assert route.status == "complete"
    assert route.readiness_state == "ready"
