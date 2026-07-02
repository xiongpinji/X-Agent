from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_answer_brief import (
    build_integration_review_answer_brief,
    summarize_review_answer_brief_item,
)


def test_review_answer_brief_builds_ready_decision_answer() -> None:
    brief = build_integration_review_answer_brief(
        {
            "brief_id": "brief-1",
            "query_result_digest": {
                "digests": [
                    {
                        "candidate_id": "integration_review_query_result_digest",
                        "query_key": "query-a",
                        "status": "ready",
                        "matched_refs": ["6 passed", "handoff"],
                        "sources": ["validation_evidence", "handoff_refs"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "question_hints": {
                "integration_review_query_result_digest": "Is the query result digest ready for mainline evaluation?"
            },
        }
    )

    assert brief["kind"] == "integration_review_answer_brief"
    assert brief["ok"] is True
    assert brief["status"] == "ready"
    assert brief["summary"]["answer_count"] == 1
    assert brief["summary"]["high_confidence_count"] == 1
    assert brief["answers"][0]["confidence"] == "high"
    assert brief["answers"][0]["evidence_refs"] == ["6 passed", "handoff"]
    assert brief["answers"][0]["question"] == "Is the query result digest ready for mainline evaluation?"
    assert brief["next_actions"] == ["share_review_answer_brief_with_mainline"]


def test_missing_refs_make_answer_brief_need_review() -> None:
    brief = build_integration_review_answer_brief(
        {
            "query_result_digest": {
                "digests": [
                    {
                        "candidate_id": "candidate-a",
                        "query_key": "query-a",
                        "status": "needs_review",
                        "matched_refs": ["tests passed"],
                        "missing_refs": ["handoff"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            }
        }
    )

    assert brief["status"] == "needs_review"
    assert brief["review_candidates"] == ["candidate-a"]
    assert brief["answers"][0]["missing_refs"] == ["handoff"]
    assert brief["answers"][0]["confidence"] == "low"
    assert "answer evidence incomplete" in brief["answers"][0]["reasons"]
    assert "attach_review_answer_evidence" in brief["next_actions"]


def test_blocked_digest_or_evidence_blocks_answer_brief() -> None:
    brief = build_integration_review_answer_brief(
        {
            "query_result_digest": {
                "digests": [
                    {
                        "candidate_id": "candidate-a",
                        "query_key": "query-a",
                        "status": "blocked",
                        "matched_refs": ["blocked evidence"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "review_evidence_index": {
                "records": [
                    {
                        "candidate_id": "candidate-a",
                        "ref": "blocked evidence",
                        "source": "integration_review_retention_policy",
                        "status": "blocked",
                    }
                ]
            },
        }
    )

    assert brief["status"] == "blocked"
    assert brief["blocked_candidates"] == ["candidate-a"]
    assert brief["answers"][0]["status"] == "blocked"
    assert "answer source blocked" in brief["answers"][0]["reasons"]
    assert brief["next_actions"] == [
        "resolve_review_answer_blockers",
        "rebuild_integration_review_answer_brief",
    ]


def test_explicit_answer_payload_overrides_generated_text() -> None:
    brief = build_integration_review_answer_brief(
        {
            "answers": [
                {
                    "candidate_id": "candidate-a",
                    "question": "Can this be reviewed?",
                    "answer": "Review after owner confirms the remaining evidence.",
                    "evidence_refs": ["manual evidence"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                    "status": "ready",
                }
            ]
        }
    )

    assert brief["status"] == "ready"
    assert brief["answers"][0]["answer"] == "Review after owner confirms the remaining evidence."
    assert brief["answers"][0]["question"] == "Can this be reviewed?"
    assert brief["answers"][0]["confidence"] == "high"


def test_empty_review_answer_brief_requests_inputs() -> None:
    brief = build_integration_review_answer_brief({})

    assert brief["ok"] is False
    assert brief["status"] == "empty"
    assert brief["next_actions"] == ["provide_review_answer_brief_inputs"]


def test_summarize_review_answer_brief_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Answer:
        candidate_id: str
        question: str
        answer: str
        evidence_refs: tuple[str, ...]
        owner: str
        reviewer: str
        status: str

    item = summarize_review_answer_brief_item(
        Answer(
            candidate_id="candidate-a",
            question="Can mainline review this?",
            answer="Yes, evidence is attached.",
            evidence_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
            status="ready",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.status == "ready"
    assert item.confidence == "high"
    assert item.evidence_refs == ("handoff",)
