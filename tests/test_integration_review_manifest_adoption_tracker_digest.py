from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_tracker_digest import (
    build_integration_review_manifest_adoption_tracker_digest,
    summarize_review_manifest_adoption_tracker_digest_item,
)


def test_tracker_digest_marks_tracker_preview_ready() -> None:
    digest = build_integration_review_manifest_adoption_tracker_digest(
        {
            "manifest_adoption_tracker_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "tracker_key": "task-a",
                        "status": "ready",
                        "assignee": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "priority": "medium",
                        "labels": ["adoption"],
                        "notification_refs": ["notice-a"],
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert digest["kind"] == "integration_review_manifest_adoption_tracker_digest"
    assert digest["ok"] is True
    assert digest["status"] == "ready"
    assert digest["items"][0]["digest_state"] == "ready_for_mainline_tracker_review"
    assert digest["items"][0]["tracker_refs"] == ["task-a"]
    assert digest["next_actions"] == ["share_manifest_adoption_tracker_digest_with_mainline"]


def test_tracker_digest_requires_missing_assignments_and_refs() -> None:
    digest = build_integration_review_manifest_adoption_tracker_digest(
        {
            "manifest_adoption_tracker_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "tracker_key": "task-a",
                        "status": "ready",
                    }
                ]
            }
        }
    )

    assert digest["status"] == "needs_review"
    assert digest["review_candidates"] == ["candidate-a"]
    assert digest["items"][0]["digest_state"] == "needs_assignee"
    assert "assign_manifest_adoption_tracker_digest_assignee" in digest["next_actions"]
    assert "attach_manifest_adoption_tracker_digest_validation_refs" in digest["next_actions"]


def test_tracker_digest_blocks_blocked_tracker_preview() -> None:
    digest = build_integration_review_manifest_adoption_tracker_digest(
        {
            "manifest_adoption_tracker_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "tracker_key": "task-a",
                        "status": "blocked",
                        "assignee": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert digest["status"] == "blocked"
    assert digest["blocked_candidates"] == ["candidate-a"]
    assert digest["items"][0]["priority"] == "high"
    assert digest["items"][0]["digest_state"] == "blocked"
    assert digest["next_actions"][0] == "resolve_manifest_adoption_tracker_digest_blockers"


def test_notification_handoff_and_packet_can_supply_fallback_refs_and_owners() -> None:
    digest = build_integration_review_manifest_adoption_tracker_digest(
        {
            "manifest_adoption_tracker_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "tracker_key": "task-a",
                        "status": "ready",
                    }
                ]
            },
            "manifest_adoption_notification_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "notification_key": "notice-a",
                        "recipient": "backend-owner",
                    }
                ]
            },
            "manifest_adoption_owner_handoff": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "manifest_adoption_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "validation_refs": ["pytest candidate-a"],
                    }
                ]
            },
        }
    )

    assert digest["status"] == "ready"
    assert digest["items"][0]["assignee"] == "backend-owner"
    assert digest["items"][0]["reviewer"] == "mainline-reviewer"
    assert digest["items"][0]["notification_refs"] == ["notice-a"]
    assert digest["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert digest["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_tracker_digest_can_seed_output() -> None:
    digest = build_integration_review_manifest_adoption_tracker_digest(
        {
            "digests": [
                {
                    "candidate_id": "candidate-a",
                    "digest_key": "digest-a",
                    "status": "ready",
                    "summary": "Candidate-a tracker digest is ready.",
                    "assignee": "backend-owner",
                    "reviewer": "mainline-reviewer",
                    "priority": "low",
                    "labels": ["adoption"],
                    "tracker_refs": ["task-a"],
                    "notification_refs": ["notice-a"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert digest["status"] == "ready"
    assert digest["items"][0]["digest_key"] == "digest-a"
    assert digest["items"][0]["summary"] == "Candidate-a tracker digest is ready."
    assert digest["items"][0]["priority"] == "low"
    assert "tracker_digest" in digest["items"][0]["labels"]


def test_empty_tracker_digest_requests_inputs() -> None:
    digest = build_integration_review_manifest_adoption_tracker_digest({})

    assert digest["ok"] is False
    assert digest["status"] == "empty"
    assert digest["next_actions"] == ["provide_review_manifest_adoption_tracker_digest_inputs"]


def test_summarize_tracker_digest_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Digest:
        candidate_id: str
        digest_key: str
        status: str
        summary: str
        assignee: str
        reviewer: str
        priority: str
        tracker_refs: tuple[str, ...]
        notification_refs: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_tracker_digest_item(
        Digest(
            candidate_id="candidate-a",
            digest_key="digest-a",
            status="ready",
            summary="Candidate-a tracker digest is ready.",
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
    assert item.digest_state == "ready_for_mainline_tracker_review"
