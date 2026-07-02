from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_calendar import (
    build_integration_review_calendar,
    summarize_review_calendar_slot,
)


def test_review_calendar_builds_ready_slots_from_reviewer_assignments() -> None:
    calendar = build_integration_review_calendar(
        {
            "calendar_id": "calendar-1",
            "default_window": "mainline_review_day_1",
            "reviewer_assignment_matrix": {
                "assignments": [
                    {
                        "candidate_id": "integration_reviewer_assignment_matrix",
                        "owner": "mainline",
                        "primary_reviewer": "architecture",
                        "review_status": "ready",
                        "risk_level": "low",
                    }
                ]
            },
        }
    )

    assert calendar["kind"] == "integration_review_calendar"
    assert calendar["ok"] is True
    assert calendar["status"] == "ready"
    assert calendar["summary"]["slot_count"] == 1
    assert calendar["slots"][0]["window"] == "mainline_review_day_1"
    assert calendar["by_reviewer"] == {"architecture": ["integration_reviewer_assignment_matrix"]}
    assert calendar["next_actions"] == ["share_review_calendar_with_mainline"]


def test_missing_reviewer_and_owner_needs_review() -> None:
    calendar = build_integration_review_calendar(
        {
            "candidates": [
                {
                    "candidate_id": "candidate-a",
                    "status": "ready",
                }
            ]
        }
    )

    assert calendar["status"] == "needs_review"
    slot = calendar["slots"][0]
    assert slot["status"] == "needs_review"
    assert slot["reasons"] == ["reviewer missing", "owner missing"]
    assert calendar["next_actions"] == [
        "complete_review_calendar_plan",
        "assign_calendar_reviewer",
        "assign_calendar_owner",
        "rebuild_integration_review_calendar",
    ]


def test_blocked_digest_signal_blocks_calendar_slot() -> None:
    calendar = build_integration_review_calendar(
        {
            "reviewer_assignment_matrix": {
                "assignments": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "mainline",
                        "primary_reviewer": "architecture",
                        "review_status": "ready",
                        "risk_level": "medium",
                    }
                ]
            },
            "manifest_review_digest": {
                "signals": [
                    {
                        "signal_id": "conflict_risk",
                        "status": "blocked",
                        "severity": "high",
                        "refs": ["candidate-a"],
                    }
                ]
            },
        }
    )

    assert calendar["status"] == "blocked"
    assert calendar["blocked_candidates"] == ["candidate-a"]
    slot = calendar["slots"][0]
    assert slot["risk_level"] == "high"
    assert slot["window"] == "review_window_urgent"
    assert "review digest blocks calendar slot" in slot["reasons"]
    assert calendar["next_actions"] == [
        "resolve_blocked_review_calendar_slots",
        "rebuild_integration_review_calendar",
    ]


def test_urgency_hints_prioritize_and_bucket_windows() -> None:
    calendar = build_integration_review_calendar(
        {
            "default_window": "day_1",
            "reviewer_assignment_matrix": {
                "assignments": [
                    {
                        "candidate_id": "low",
                        "owner": "mainline",
                        "primary_reviewer": "review",
                        "review_status": "ready",
                        "risk_level": "low",
                    },
                    {
                        "candidate_id": "urgent",
                        "owner": "mainline",
                        "primary_reviewer": "review",
                        "review_status": "ready",
                        "risk_level": "high",
                    },
                ]
            },
            "urgency_hints": {"urgent": 95, "low": 30},
        }
    )

    assert [slot["candidate_id"] for slot in calendar["slots"]] == ["urgent", "low"]
    assert calendar["slots"][0]["window"] == "review_window_urgent"
    assert calendar["slots"][1]["window"] == "day_1_later"
    assert calendar["by_window"] == {
        "review_window_urgent": ["urgent"],
        "day_1_later": ["low"],
    }


def test_empty_review_calendar_requests_inputs() -> None:
    calendar = build_integration_review_calendar({})

    assert calendar["ok"] is False
    assert calendar["status"] == "empty"
    assert calendar["next_actions"] == ["provide_review_calendar_inputs"]


def test_summarize_review_calendar_slot_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Slot:
        candidate_id: str
        owner: str
        reviewer: str
        status: str
        window: str

    slot = summarize_review_calendar_slot(
        Slot("candidate-a", "mainline", "architecture", "ready", "day_1")
    )

    assert slot.candidate_id == "candidate-a"
    assert slot.owner == "mainline"
    assert slot.reviewer == "architecture"
    assert slot.status == "ready"
    assert slot.window == "day_1"
