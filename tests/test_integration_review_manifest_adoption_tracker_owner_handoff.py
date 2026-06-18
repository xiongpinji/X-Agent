from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_tracker_owner_handoff import (
    build_integration_review_manifest_adoption_tracker_owner_handoff,
    summarize_review_manifest_adoption_tracker_owner_handoff_item,
)


def test_tracker_owner_handoff_marks_assigned_final_packet_ready() -> None:
    handoff = build_integration_review_manifest_adoption_tracker_owner_handoff(
        {
            "manifest_adoption_tracker_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "packet_key": "packet-a",
                        "status": "ready",
                        "accepted": True,
                        "assignee": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "tracker_refs": ["task-a"],
                        "notification_refs": ["notice-a"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert handoff["kind"] == "integration_review_manifest_adoption_tracker_owner_handoff"
    assert handoff["ok"] is True
    assert handoff["status"] == "ready"
    assert handoff["items"][0]["handoff_state"] == "ready_for_owner_review"
    assert handoff["owner_groups"] == {"backend-owner": ["candidate-a"]}
    assert handoff["next_actions"] == ["share_manifest_adoption_tracker_owner_handoff_with_mainline"]


def test_tracker_owner_handoff_requires_missing_assignments_and_refs() -> None:
    handoff = build_integration_review_manifest_adoption_tracker_owner_handoff(
        {
            "manifest_adoption_tracker_final_packet": {
                "items": [{"candidate_id": "candidate-a", "packet_key": "packet-a", "status": "ready", "accepted": True}]
            }
        }
    )

    assert handoff["status"] == "needs_review"
    assert handoff["review_candidates"] == ["candidate-a"]
    assert "owner" in handoff["items"][0]["missing_assignments"]
    assert "attach_manifest_adoption_tracker_owner_handoff_validation_refs" in handoff["next_actions"]


def test_tracker_owner_handoff_blocks_blocked_final_packet() -> None:
    handoff = build_integration_review_manifest_adoption_tracker_owner_handoff(
        {
            "manifest_adoption_tracker_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "packet_key": "packet-a",
                        "status": "blocked",
                        "accepted": False,
                        "assignee": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "handoff_refs": ["handoff"],
                        "blockers": ["tracker card incomplete"],
                    }
                ]
            }
        }
    )

    assert handoff["status"] == "blocked"
    assert handoff["blocked_candidates"] == ["candidate-a"]
    assert handoff["items"][0]["owner_actions"] == ["review_tracker_handoff_blockers"]
    assert handoff["next_actions"][0] == "resolve_manifest_adoption_tracker_owner_handoff_blockers"


def test_acceptance_check_and_context_can_supply_fallback_refs_and_owners() -> None:
    handoff = build_integration_review_manifest_adoption_tracker_owner_handoff(
        {
            "manifest_adoption_tracker_final_packet": {
                "items": [{"candidate_id": "candidate-a", "packet_key": "packet-a", "status": "ready", "accepted": True}]
            },
            "manifest_adoption_tracker_acceptance_check": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "tracker_refs": ["task-a"],
                        "notification_refs": ["notice-a"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "owner_context": {"candidate-a": "backend-owner"},
            "reviewer_context": {"candidate-a": "mainline-reviewer"},
        }
    )

    assert handoff["status"] == "ready"
    assert handoff["items"][0]["owner"] == "backend-owner"
    assert handoff["items"][0]["reviewer"] == "mainline-reviewer"
    assert handoff["items"][0]["tracker_refs"] == ["task-a"]


def test_explicit_tracker_owner_handoff_can_seed_payload() -> None:
    handoff = build_integration_review_manifest_adoption_tracker_owner_handoff(
        {
            "handoffs": [
                {
                    "candidate_id": "candidate-a",
                    "handoff_key": "handoff-a",
                    "status": "ready",
                    "accepted": True,
                    "owner": "backend-owner",
                    "reviewer": "mainline-reviewer",
                    "tracker_refs": ["task-a"],
                    "notification_refs": ["notice-a"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert handoff["status"] == "ready"
    assert handoff["items"][0]["handoff_key"] == "handoff-a"
    assert handoff["items"][0]["owner"] == "backend-owner"


def test_empty_tracker_owner_handoff_requests_inputs() -> None:
    handoff = build_integration_review_manifest_adoption_tracker_owner_handoff({})

    assert handoff["ok"] is False
    assert handoff["status"] == "empty"
    assert handoff["next_actions"] == ["provide_review_manifest_adoption_tracker_owner_handoff_inputs"]


def test_summarize_tracker_owner_handoff_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Handoff:
        candidate_id: str
        handoff_key: str
        status: str
        accepted: bool
        owner: str
        reviewer: str
        tracker_refs: tuple[str, ...]
        notification_refs: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_tracker_owner_handoff_item(
        Handoff(
            candidate_id="candidate-a",
            handoff_key="handoff-a",
            status="ready",
            accepted=True,
            owner="backend-owner",
            reviewer="mainline-reviewer",
            tracker_refs=("task-a",),
            notification_refs=("notice-a",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.handoff_state == "ready_for_owner_review"
