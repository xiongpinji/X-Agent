from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_manifest_adoption_notification_preview import (
    build_integration_review_manifest_adoption_notification_preview,
    summarize_review_manifest_adoption_notification_preview_item,
)


def test_notification_preview_marks_assigned_owner_handoff_ready() -> None:
    preview = build_integration_review_manifest_adoption_notification_preview(
        {
            "manifest_adoption_owner_handoff": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "handoff_key": "handoff-a",
                        "status": "ready",
                        "go_no_go": "go",
                        "recommended_outcome": "adopt",
                        "owner": "backend-owner",
                        "reviewer": "mainline-reviewer",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["kind"] == "integration_review_manifest_adoption_notification_preview"
    assert preview["ok"] is True
    assert preview["status"] == "ready"
    assert preview["summary"]["owner_notification_count"] == 1
    assert preview["summary"]["reviewer_notification_count"] == 1
    assert preview["ready_candidates"] == ["candidate-a"]
    assert preview["next_actions"] == ["share_manifest_adoption_notification_preview_with_mainline"]


def test_notification_preview_requires_missing_recipients() -> None:
    preview = build_integration_review_manifest_adoption_notification_preview(
        {
            "manifest_adoption_owner_handoff": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "handoff_key": "handoff-a",
                        "status": "ready",
                        "go_no_go": "go",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            }
        }
    )

    assert preview["status"] == "needs_review"
    assert preview["review_candidates"] == ["candidate-a"]
    assert {item["notification_state"] for item in preview["items"]} == {"needs_recipient"}
    assert "assign_manifest_adoption_owner_notification_recipient" in preview["next_actions"]
    assert "assign_manifest_adoption_reviewer_notification_recipient" in preview["next_actions"]


def test_notification_preview_blocks_blocked_handoff() -> None:
    preview = build_integration_review_manifest_adoption_notification_preview(
        {
            "manifest_adoption_owner_handoff": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "handoff_key": "handoff-a",
                        "status": "blocked",
                        "go_no_go": "no_go",
                        "recommended_outcome": "defer",
                        "owner": "backend-owner",
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
    assert {item["notification_state"] for item in preview["items"]} == {"blocked"}
    assert preview["items"][0]["blockers"] == ["forbidden scope overlap"]
    assert preview["next_actions"][0] == "resolve_manifest_adoption_notification_preview_blockers"


def test_final_packet_and_context_can_supply_fallback_refs_and_recipients() -> None:
    preview = build_integration_review_manifest_adoption_notification_preview(
        {
            "manifest_adoption_owner_handoff": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "handoff_key": "handoff-a",
                        "status": "ready",
                        "go_no_go": "go",
                    }
                ]
            },
            "manifest_adoption_final_packet": {
                "items": [
                    {
                        "candidate_id": "candidate-a",
                        "validation_refs": ["pytest candidate-a"],
                        "handoff_refs": ["handoff"],
                    }
                ]
            },
            "owner_context": {"candidate-a": {"recipient": "backend-owner", "channel": "teams"}},
            "reviewer_context": {"candidate-a": {"recipient": "mainline-reviewer", "channel": "linear"}},
        }
    )

    assert preview["status"] == "ready"
    assert {item["recipient"] for item in preview["items"]} == {"backend-owner", "mainline-reviewer"}
    assert {item["channel"] for item in preview["items"]} == {"teams", "linear"}
    assert preview["items"][0]["validation_refs"] == ["pytest candidate-a"]
    assert preview["items"][0]["handoff_refs"] == ["handoff"]


def test_explicit_notification_preview_can_seed_output() -> None:
    preview = build_integration_review_manifest_adoption_notification_preview(
        {
            "notifications": [
                {
                    "candidate_id": "candidate-a",
                    "notification_key": "notice-a",
                    "recipient_roles": ["owner"],
                    "status": "ready",
                    "go_no_go": "go",
                    "recommended_outcome": "adopt",
                    "owner": "backend-owner",
                    "channel": "handoff-doc",
                    "subject": "Review candidate-a",
                    "message": "Candidate-a is ready for detached review.",
                    "validation_refs": ["pytest"],
                    "handoff_refs": ["handoff"],
                }
            ]
        }
    )

    assert preview["status"] == "ready"
    assert len(preview["items"]) == 1
    assert preview["items"][0]["notification_key"] == "notice-a:owner"
    assert preview["items"][0]["subject"] == "Review candidate-a"
    assert preview["items"][0]["message"] == "Candidate-a is ready for detached review."


def test_empty_notification_preview_requests_inputs() -> None:
    preview = build_integration_review_manifest_adoption_notification_preview({})

    assert preview["ok"] is False
    assert preview["status"] == "empty"
    assert preview["next_actions"] == ["provide_review_manifest_adoption_notification_preview_inputs"]


def test_summarize_notification_preview_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Notification:
        candidate_id: str
        notification_key: str
        status: str
        recipient_role: str
        recipient: str
        channel: str
        go_no_go: str
        recommended_outcome: str
        validation_refs: tuple[str, ...]
        handoff_refs: tuple[str, ...]

    item = summarize_review_manifest_adoption_notification_preview_item(
        Notification(
            candidate_id="candidate-a",
            notification_key="notice-a",
            status="ready",
            recipient_role="owner",
            recipient="backend-owner",
            channel="handoff-doc",
            go_no_go="go",
            recommended_outcome="adopt",
            validation_refs=("pytest",),
            handoff_refs=("handoff",),
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.notification_state == "ready_to_notify"
