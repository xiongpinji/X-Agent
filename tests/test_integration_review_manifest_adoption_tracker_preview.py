from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_tracker_preview import (
    build_integration_review_manifest_adoption_tracker_preview,
    summarize_review_manifest_adoption_tracker_preview_item,
)


def test_tracker_preview_marks_notification_preview_ready() -> None:
    preview = build_integration_review_manifest_adoption_tracker_preview(
        {
            "manifest_adoption_notification_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "notification_key": "notice-a",
                        "status": "ready",
                        "recipient": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["kind"] == "integration_review_manifest_adoption_tracker_preview"
    assert preview["ok"] is True
    assert preview["status"] == "ready"
    assert preview["items"][0]["tracker_state"] == "ready_to_create_task"
    assert preview["items"][0]["assignee"] == "backend-owner"
    assert preview["next_actions"] == ["share_manifest_adoption_tracker_preview_with_mainline"]


def test_tracker_preview_requires_missing_assignments_and_refs() -> None:
    preview = build_integration_review_manifest_adoption_tracker_preview(
        {
            "manifest_adoption_notification_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "notification_key": "notice-a",
                        "status": "ready",
                    }
                ]
            }
        }
    )

    assert preview["status"] == "needs_review"
    assert preview["review_candidates"] == ["candidate-a"]
    assert preview["items"][0]["tracker_state"] == "needs_assignee"
    assert "assign_manifest_adoption_tracker_assignee" in preview["next_actions"]
    assert "attach_manifest_adoption_tracker_validation_refs" in preview["next_actions"]


def test_tracker_preview_blocks_blocked_notification_preview() -> None:
    preview = build_integration_review_manifest_adoption_tracker_preview(
        {
            "manifest_adoption_notification_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "notification_key": "notice-a",
                        "status": "blocked",
                        "recipient": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "handoff_refs": ["handoff"],
                        "blockers": ["forbidden scope overlap"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "blocked"
    assert preview["blocked_candidates"] == ["candidate-a"]
    assert preview["items"][0]["priority"] == "high"
    assert preview["items"][0]["tracker_state"] == "blocked"
    assert preview["next_actions"][0] == "resolve_manifest_adoption_tracker_preview_blockers"


def test_owner_handoff_and_final_packet_can_supply_fallback_refs_and_assignees() -> None:
    preview = build_integration_review_manifest_adoption_tracker_preview(
        {
            "manifest_adoption_notification_preview": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "notification_key": "notice-a",
                        "status": "ready",
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

    assert preview["status"] == "ready"
    assert preview["items"][0]["assignee"] == "backend-owner"
    assert preview["items"][0]["reviewer"] == "mainline-reviewer"
    assert preview["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert preview["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_tracker_preview_can_seed_output() -> None:
    preview = build_integration_review_manifest_adoption_tracker_preview(
        {
            "tasks": [
                {
                    "candidate_id": "candidate-a",
                    "tracker_key": "task-a",
                    "status": "ready",
                    "task_title": "Review candidate-a adoption",
                    "assignee": "backend-owner",
                    "reviewer": "mainline-reviewer",
                    "priority": "low",
                    "labels": ["adoption"],
                    "notification_refs": ["notice-a"],
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert preview["status"] == "ready"
    assert preview["items"][0]["tracker_key"] == "task-a"
    assert preview["items"][0]["task_title"] == "Review candidate-a adoption"
    assert preview["items"][0]["priority"] == "low"
    assert "secondary_integration_candidate" in preview["items"][0]["labels"]


def test_empty_tracker_preview_requests_inputs() -> None:
    preview = build_integration_review_manifest_adoption_tracker_preview({})

    assert preview["ok"] is False
    assert preview["status"] == "empty"
    assert preview["next_actions"] == ["provide_review_manifest_adoption_tracker_preview_inputs"]


def test_summarize_tracker_preview_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Tracker:
        candidate_id: str
        tracker_key: str
        status: str
        task_title: str
        assignee: str
        reviewer: str
        priority: str
        notification_refs: tuple[str, ...]
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_tracker_preview_item(
        Tracker(
            candidate_id="candidate-a",
            tracker_key="task-a",
            status="ready",
            task_title="Review candidate-a adoption",
            assignee="backend-owner",
            reviewer="mainline-reviewer",
            priority="medium",
            notification_refs=("notice-a",),
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.tracker_state == "ready_to_create_task"
