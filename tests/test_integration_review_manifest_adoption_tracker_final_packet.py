from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_tracker_final_packet import (
    build_integration_review_manifest_adoption_tracker_final_packet,
    summarize_review_manifest_adoption_tracker_final_packet_item,
)


def test_tracker_final_packet_marks_accepted_check_ready() -> None:
    packet = build_integration_review_manifest_adoption_tracker_final_packet(
        {
            "manifest_adoption_tracker_acceptance_check": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "check_key": "check-a",
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

    assert packet["kind"] == "integration_review_manifest_adoption_tracker_final_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["accepted_candidates"] == ["candidate-a"]
    assert packet["items"][0]["packet_state"] == "ready_for_mainline_tracker_review"
    assert packet["next_actions"] == ["share_manifest_adoption_tracker_final_packet_with_mainline"]


def test_tracker_final_packet_needs_review_for_missing_refs() -> None:
    packet = build_integration_review_manifest_adoption_tracker_final_packet(
        {
            "manifest_adoption_tracker_acceptance_check": {
                "items": [{"candidate_id": "candidate-a", "check_key": "check-a", "status": "ready", "accepted": True}]
            }
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["review_candidates"] == ["candidate-a"]
    assert packet["items"][0]["accepted"] is False
    assert "attach_manifest_adoption_tracker_final_packet_validation_refs" in packet["next_actions"]


def test_tracker_final_packet_blocks_blocked_acceptance_check() -> None:
    packet = build_integration_review_manifest_adoption_tracker_final_packet(
        {
            "manifest_adoption_tracker_acceptance_check": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "check_key": "check-a",
                        "status": "blocked",
                        "accepted": False,
                        "assignee": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "tracker_refs": ["task-a"],
                        "handoff_refs": ["handoff"],
                        "blockers": ["tracker card incomplete"],
                    }
                ]
            }
        }
    )

    assert packet["status"] == "blocked"
    assert packet["blocked_candidates"] == ["candidate-a"]
    assert packet["items"][0]["recommended_outcome"] == "resolve_blockers"
    assert packet["next_actions"][0] == "resolve_manifest_adoption_tracker_final_packet_blockers"


def test_tracker_digest_preview_and_notification_can_supply_fallback_refs() -> None:
    packet = build_integration_review_manifest_adoption_tracker_final_packet(
        {
            "manifest_adoption_tracker_acceptance_check": {
                "items": [{"candidate_id": "candidate-a", "check_key": "check-a", "status": "ready", "accepted": True}]
            },
            "manifest_adoption_tracker_digest": {
                "items": [{"candidate_id": "candidate-a", "assignee": "backend-owner", "reviewer": "mainline-reviewer", "handoff_refs": ["handoff"]}]
            },
            "manifest_adoption_tracker_preview": {
                "items": [{"candidate_id": "candidate-a", "tracker_key": "task-a", "validation_refs": ["pytest candidate-a"]}]
            },
            "manifest_adoption_notification_preview": {
                "items": [{"candidate_id": "candidate-a", "notification_key": "notice-a"}]
            },
        }
    )

    assert packet["status"] == "ready"
    assert packet["items"][0]["tracker_refs"] == ["task-a"]
    assert packet["items"][0]["notification_refs"] == ["notice-a"]
    assert packet["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert packet["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_tracker_final_packet_can_seed_output() -> None:
    packet = build_integration_review_manifest_adoption_tracker_final_packet(
        {
            "packets": [
                {
                    "candidate_id": "candidate-a",
                    "packet_key": "packet-a",
                    "status": "ready",
                    "accepted": True,
                    "assignee": "backend-owner",
                    "reviewer": "mainline-reviewer",
                    "priority": "low",
                    "tracker_refs": ["task-a"],
                    "notification_refs": ["notice-a"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert packet["status"] == "ready"
    assert packet["items"][0]["packet_key"] == "packet-a"
    assert packet["items"][0]["recommended_outcome"] == "share_with_mainline"
    assert packet["items"][0]["priority"] == "low"


def test_empty_tracker_final_packet_requests_inputs() -> None:
    packet = build_integration_review_manifest_adoption_tracker_final_packet({})

    assert packet["ok"] is False
    assert packet["status"] == "empty"
    assert packet["next_actions"] == ["provide_review_manifest_adoption_tracker_final_packet_inputs"]


def test_summarize_tracker_final_packet_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Packet:
        candidate_id: str
        packet_key: str
        status: str
        accepted: bool
        assignee: str
        reviewer: str
        priority: str
        tracker_refs: tuple[str, ...]
        notification_refs: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_tracker_final_packet_item(
        Packet(
            candidate_id="candidate-a",
            packet_key="packet-a",
            status="ready",
            accepted=True,
            assignee="backend-owner",
            reviewer="mainline-reviewer",
            priority="medium",
            tracker_refs=("task-a",),
            notification_refs=("notice-a",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.packet_state == "ready_for_mainline_tracker_review"
