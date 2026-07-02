from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_tracker_acceptance_check import (
    build_integration_review_manifest_adoption_tracker_acceptance_check,
    summarize_review_manifest_adoption_tracker_acceptance_check_item,
)


def test_tracker_acceptance_check_accepts_ready_digest() -> None:
    check = build_integration_review_manifest_adoption_tracker_acceptance_check(
        {
            "manifest_adoption_tracker_digest": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "digest_key": "digest-a",
                        "status": "ready",
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

    assert check["kind"] == "integration_review_manifest_adoption_tracker_acceptance_check"
    assert check["ok"] is True
    assert check["status"] == "ready"
    assert check["accepted_candidates"] == ["candidate-a"]
    assert check["items"][0]["acceptance_state"] == "accepted_for_mainline_tracker_review"
    assert check["next_actions"] == ["share_manifest_adoption_tracker_acceptance_check_with_mainline"]


def test_tracker_acceptance_check_requires_missing_assignments_and_refs() -> None:
    check = build_integration_review_manifest_adoption_tracker_acceptance_check(
        {
            "manifest_adoption_tracker_digest": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "digest_key": "digest-a",
                        "status": "ready",
                    }
                ]
            }
        }
    )

    assert check["status"] == "needs_review"
    assert check["review_candidates"] == ["candidate-a"]
    assert check["items"][0]["acceptance_state"] == "needs_evidence"
    assert "assignee" in check["items"][0]["missing_refs"]
    assert "attach_manifest_adoption_tracker_acceptance_validation_refs" in check["next_actions"]


def test_tracker_acceptance_check_blocks_blocked_digest() -> None:
    check = build_integration_review_manifest_adoption_tracker_acceptance_check(
        {
            "manifest_adoption_tracker_digest": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "digest_key": "digest-a",
                        "status": "blocked",
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

    assert check["status"] == "blocked"
    assert check["blocked_candidates"] == ["candidate-a"]
    assert check["items"][0]["accepted"] is False
    assert check["items"][0]["acceptance_state"] == "blocked"
    assert check["next_actions"][0] == "resolve_manifest_adoption_tracker_acceptance_blockers"


def test_tracker_preview_notification_and_handoff_can_supply_fallback_refs() -> None:
    check = build_integration_review_manifest_adoption_tracker_acceptance_check(
        {
            "manifest_adoption_tracker_digest": {
                "items": [{"candidate_id": "candidate-a", "digest_key": "digest-a", "status": "ready"}]
            },
            "manifest_adoption_tracker_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "tracker_key": "task-a",
                        "assignee": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "validation_refs": ["pytest candidate-a"],
                    }
                ]
            },
            "manifest_adoption_notification_preview": {
                "items": [{"candidate_id": "candidate-a", "notification_key": "notice-a"}]
            },
            "manifest_adoption_owner_handoff": {
                "items": [{"candidate_id": "candidate-a", "handoff_refs": ["handoff"]}]
            },
        }
    )

    assert check["status"] == "ready"
    assert check["items"][0]["tracker_refs"] == ["task-a"]
    assert check["items"][0]["notification_refs"] == ["notice-a"]
    assert check["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert check["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_tracker_acceptance_check_can_seed_output() -> None:
    check = build_integration_review_manifest_adoption_tracker_acceptance_check(
        {
            "checks": [
                {
                    "candidate_id": "candidate-a",
                    "check_key": "check-a",
                    "status": "ready",
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

    assert check["status"] == "ready"
    assert check["items"][0]["check_key"] == "check-a"
    assert check["items"][0]["accepted"] is True
    assert check["items"][0]["priority"] == "low"


def test_empty_tracker_acceptance_check_requests_inputs() -> None:
    check = build_integration_review_manifest_adoption_tracker_acceptance_check({})

    assert check["ok"] is False
    assert check["status"] == "empty"
    assert check["next_actions"] == ["provide_review_manifest_adoption_tracker_acceptance_check_inputs"]


def test_summarize_tracker_acceptance_check_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Check:
        candidate_id: str
        check_key: str
        status: str
        assignee: str
        reviewer: str
        priority: str
        tracker_refs: tuple[str, ...]
        notification_refs: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_tracker_acceptance_check_item(
        Check(
            candidate_id="candidate-a",
            check_key="check-a",
            status="ready",
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
    assert item.accepted is True
