from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_minutes import (
    build_integration_review_minutes,
    summarize_review_minute_item,
)


def test_review_minutes_builds_ready_decision_summary() -> None:
    minutes = build_integration_review_minutes(
        {
            "minutes_id": "minutes-1",
            "review_calendar": {
                "slots": [
                    {
                        "candidate_id": "integration_review_calendar",
                        "owner": "mainline",
                        "reviewer": "architecture",
                        "status": "ready",
                        "risk_level": "low",
                    }
                ]
            },
            "validation_evidence": {
                "integration_review_calendar": {
                    "result": "6 passed",
                    "refs": ["tests/test_integration_review_calendar.py"],
                }
            },
        }
    )

    assert minutes["kind"] == "integration_review_minutes"
    assert minutes["ok"] is True
    assert minutes["status"] == "ready"
    assert minutes["summary"]["candidate_count"] == 1
    assert minutes["attendees"] == ["architecture", "mainline"]
    assert minutes["decisions"][0]["decision"] == "ready_for_mainline_review"
    assert minutes["agenda"][0]["topic"] == "Confirm secondary candidate ready for mainline review"
    assert minutes["next_actions"] == ["share_review_minutes_with_mainline"]


def test_missing_calendar_and_evidence_keeps_minutes_in_review() -> None:
    minutes = build_integration_review_minutes(
        {
            "reviewer_assignment_matrix": {
                "assignments": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "mainline",
                        "primary_reviewer": "review",
                        "review_status": "ready",
                    }
                ]
            }
        }
    )

    assert minutes["status"] == "needs_review"
    decision = minutes["decisions"][0]
    assert decision["status"] == "needs_review"
    assert decision["reasons"] == [
        "validation evidence missing",
        "review calendar slot missing",
    ]
    assert minutes["next_actions"] == [
        "complete_review_minutes",
        "attach_minutes_validation_evidence",
        "attach_review_calendar_slot",
        "rebuild_integration_review_minutes",
    ]


def test_blocked_digest_signal_blocks_review_minutes() -> None:
    minutes = build_integration_review_minutes(
        {
            "review_calendar": {
                "slots": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "mainline",
                        "reviewer": "architecture",
                        "status": "ready",
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
            "validation_evidence": {
                "candidate-a": {"result": "tests passed"},
            },
        }
    )

    assert minutes["status"] == "blocked"
    assert minutes["blocked_candidates"] == ["candidate-a"]
    decision = minutes["decisions"][0]
    assert decision["risk_level"] == "high"
    assert decision["decision"] == "blocked_pending_resolution"
    assert "review input blocked" in decision["reasons"]
    assert minutes["risks"] == [
        "blocked_review_items_present",
        "high_risk_review_items_present",
    ]
    assert minutes["next_actions"] == [
        "resolve_review_minutes_blockers",
        "rebuild_integration_review_minutes",
    ]


def test_explicit_decisions_and_validation_evidence_are_merged() -> None:
    minutes = build_integration_review_minutes(
        {
            "decisions": [
                {
                    "candidate_id": "candidate-a",
                    "decision": "defer_for_mainline_owner",
                    "status": "needs_review",
                    "owner": "mainline",
                    "reviewer": "architecture",
                }
            ],
            "review_calendar": {
                "slots": [
                    {
                        "candidate_id": "candidate-a",
                        "owner": "other",
                        "reviewer": "review",
                        "status": "ready",
                    }
                ]
            },
            "validation_evidence": [
                {
                    "candidate_id": "candidate-a",
                    "evidence_refs": ["handoff", "18 passed"],
                }
            ],
        }
    )

    assert minutes["status"] == "needs_review"
    assert minutes["decisions"][0]["decision"] == "defer_for_mainline_owner"
    assert minutes["decisions"][0]["owner"] == "mainline"
    assert minutes["decisions"][0]["reviewer"] == "architecture"
    assert minutes["decisions"][0]["evidence_refs"] == ["handoff", "18 passed"]
    assert minutes["review_candidates"] == ["candidate-a"]


def test_empty_review_minutes_requests_inputs() -> None:
    minutes = build_integration_review_minutes({})

    assert minutes["ok"] is False
    assert minutes["status"] == "empty"
    assert minutes["next_actions"] == ["provide_review_minutes_inputs"]


def test_summarize_review_minute_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Minute:
        candidate_id: str
        owner: str
        reviewer: str
        status: str
        evidence_refs: list[str]

    item = summarize_review_minute_item(
        Minute("candidate-a", "mainline", "architecture", "ready", ["handoff"])
    )

    assert item.candidate_id == "candidate-a"
    assert item.owner == "mainline"
    assert item.reviewer == "architecture"
    assert item.status == "needs_review"
    assert "review calendar slot missing" in item.reasons
