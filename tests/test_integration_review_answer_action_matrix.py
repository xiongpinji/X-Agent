from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_answer_action_matrix import (
    build_integration_review_answer_action_matrix,
    summarize_review_answer_action,
)


def test_review_answer_action_matrix_builds_ready_action() -> None:
    matrix = build_integration_review_answer_action_matrix(
        {
            "matrix_id": "matrix-1",
            "answer_brief": {
                "answers": [
                    {
                        "candidate_id": "integration_review_answer_brief",
                        "status": "ready",
                        "evidence_refs": ["6 passed", "handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
        }
    )

    assert matrix["kind"] == "integration_review_answer_action_matrix"
    assert matrix["ok"] is True
    assert matrix["status"] == "ready"
    assert matrix["summary"]["action_count"] == 1
    assert matrix["actions"][0]["priority"] == "low"
    assert matrix["actions"][0]["action"] == "Schedule mainline evaluation for integration_review_answer_brief."
    assert matrix["by_owner"] == {"mainline": ["review-answer-action:integration_review_answer_brief"]}
    assert matrix["next_actions"] == ["share_review_answer_action_matrix_with_mainline"]


def test_missing_evidence_and_owner_make_action_need_review() -> None:
    matrix = build_integration_review_answer_action_matrix(
        {
            "answer_brief": {
                "answers": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "needs_review",
                        "missing_refs": ["handoff"],
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert matrix["status"] == "needs_review"
    assert matrix["review_actions"] == ["review-answer-action:candidate-a"]
    assert matrix["actions"][0]["priority"] == "medium"
    assert matrix["actions"][0]["blockers"] == ["missing_review_answer_evidence", "owner_missing"]
    assert "action blockers present" in matrix["actions"][0]["reasons"]
    assert "assign_review_answer_action_owner" in matrix["next_actions"]


def test_blocked_answer_or_digest_blocks_action_matrix() -> None:
    matrix = build_integration_review_answer_action_matrix(
        {
            "answer_brief": {
                "answers": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "blocked",
                        "evidence_refs": ["blocked evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "query_result_digest": {
                "digests": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "blocked",
                        "matched_refs": ["blocked evidence"],
                    }
                ]
            },
        }
    )

    assert matrix["status"] == "blocked"
    assert matrix["blocked_actions"] == ["review-answer-action:candidate-a"]
    assert matrix["actions"][0]["priority"] == "high"
    assert "answer_source_blocked" in matrix["actions"][0]["blockers"]
    assert matrix["next_actions"] == [
        "resolve_review_answer_action_blockers",
        "attach_review_answer_action_evidence",
        "rebuild_integration_review_answer_action_matrix",
    ]


def test_explicit_action_payload_overrides_generated_action() -> None:
    matrix = build_integration_review_answer_action_matrix(
        {
            "actions": [
                {
                    "candidate_id": "candidate-a",
                    "action_key": "action-a",
                    "action": "Queue candidate-a for owner review.",
                    "status": "ready",
                    "evidence_refs": ["manual evidence"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ]
        }
    )

    assert matrix["status"] == "ready"
    assert matrix["actions"][0]["action_key"] == "action-a"
    assert matrix["actions"][0]["action"] == "Queue candidate-a for owner review."
    assert matrix["actions"][0]["priority"] == "low"


def test_empty_review_answer_action_matrix_requests_inputs() -> None:
    matrix = build_integration_review_answer_action_matrix({})

    assert matrix["ok"] is False
    assert matrix["status"] == "empty"
    assert matrix["next_actions"] == ["provide_review_answer_action_matrix_inputs"]


def test_summarize_review_answer_action_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Action:
        candidate_id: str
        action_key: str
        action: str
        evidence_refs: tuple[str, ...]
        owner: str
        reviewer: str
        status: str

    item = summarize_review_answer_action(
        Action(
            candidate_id="candidate-a",
            action_key="action-a",
            action="Review candidate-a.",
            evidence_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
            status="ready",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.action_key == "action-a"
    assert item.status == "ready"
    assert item.priority == "low"
    assert item.evidence_refs == ("handoff",)
