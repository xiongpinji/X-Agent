from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_action_status_board import (
    build_integration_review_action_status_board,
    summarize_review_action_status_item,
)


def test_review_action_status_board_builds_ready_lane() -> None:
    board = build_integration_review_action_status_board(
        {
            "board_id": "board-1",
            "answer_action_matrix": {
                "actions": [
                    {
                        "candidate_id": "integration_review_answer_action_matrix",
                        "action_key": "action-a",
                        "status": "ready",
                        "priority": "low",
                        "evidence_refs": ["6 passed", "handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
        }
    )

    assert board["kind"] == "integration_review_action_status_board"
    assert board["ok"] is True
    assert board["status"] == "ready"
    assert board["summary"]["item_count"] == 1
    assert board["lanes"] == {"ready": ["action-a"]}
    assert board["by_owner"] == {"mainline": ["action-a"]}
    assert board["items"][0]["lane"] == "ready"
    assert board["next_actions"] == ["share_review_action_status_board_with_mainline"]


def test_missing_owner_and_blockers_make_status_need_review() -> None:
    board = build_integration_review_action_status_board(
        {
            "answer_action_matrix": {
                "actions": [
                    {
                        "candidate_id": "candidate-a",
                        "action_key": "action-a",
                        "status": "needs_review",
                        "priority": "medium",
                        "blockers": ["missing_review_answer_evidence"],
                        "evidence_refs": ["partial evidence"],
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert board["status"] == "needs_review"
    assert board["review_candidates"] == ["candidate-a"]
    assert board["items"][0]["lane"] == "needs_review"
    assert board["items"][0]["blockers"] == ["missing_review_answer_evidence"]
    assert "status blockers present" in board["items"][0]["reasons"]
    assert "assign_review_action_status_owner" in board["next_actions"]


def test_blocked_validation_state_blocks_status_board() -> None:
    board = build_integration_review_action_status_board(
        {
            "answer_action_matrix": {
                "actions": [
                    {
                        "candidate_id": "candidate-a",
                        "action_key": "action-a",
                        "status": "ready",
                        "evidence_refs": ["blocked evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "validation_state": [
                {
                    "candidate_id": "candidate-a",
                    "status": "blocked",
                    "refs": ["blocked evidence"],
                    "blockers": ["validation timeout"],
                }
            ],
        }
    )

    assert board["status"] == "blocked"
    assert board["blocked_candidates"] == ["candidate-a"]
    assert board["items"][0]["lane"] == "blocked"
    assert board["items"][0]["priority"] == "high"
    assert board["items"][0]["blockers"] == ["validation timeout", "validation_blocked"]
    assert board["next_actions"] == [
        "resolve_review_action_status_blockers",
        "attach_review_action_status_evidence",
        "rebuild_integration_review_action_status_board",
    ]


def test_explicit_status_payload_overrides_action_status() -> None:
    board = build_integration_review_action_status_board(
        {
            "statuses": [
                {
                    "candidate_id": "candidate-a",
                    "status_key": "status-a",
                    "status": "ready",
                    "priority": "high",
                    "action_refs": ["manual action"],
                    "evidence_refs": ["manual evidence"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ]
        }
    )

    assert board["status"] == "ready"
    assert board["items"][0]["status_key"] == "status-a"
    assert board["items"][0]["priority"] == "high"
    assert board["items"][0]["lane"] == "priority_review"


def test_empty_review_action_status_board_requests_inputs() -> None:
    board = build_integration_review_action_status_board({})

    assert board["ok"] is False
    assert board["status"] == "empty"
    assert board["next_actions"] == ["provide_review_action_status_board_inputs"]


def test_summarize_review_action_status_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Status:
        candidate_id: str
        status_key: str
        status: str
        action_refs: tuple[str, ...]
        evidence_refs: tuple[str, ...]
        owner: str
        reviewer: str
        priority: str

    item = summarize_review_action_status_item(
        Status(
            candidate_id="candidate-a",
            status_key="status-a",
            status="ready",
            action_refs=("action-a",),
            evidence_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
            priority="low",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.lane == "ready"
    assert item.action_refs == ("action-a",)
