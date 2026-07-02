from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_query_result_digest import (
    build_integration_review_query_result_digest,
    summarize_review_query_result_digest_item,
)


def test_review_query_result_digest_summarizes_ready_query_results() -> None:
    digest = build_integration_review_query_result_digest(
        {
            "digest_id": "digest-1",
            "review_query_plan": {
                "queries": [
                    {
                        "candidate_id": "integration_review_query_plan",
                        "query_key": "review-query:integration_review_query_plan",
                        "status": "ready",
                        "evidence_refs": ["6 passed", "handoff"],
                        "sources": ["validation_evidence", "handoff_refs"],
                        "ref_types": ["validation", "handoff"],
                        "owner": "mainline",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "query_results": [
                {
                    "query_key": "review-query:integration_review_query_plan",
                    "candidate_id": "integration_review_query_plan",
                    "matched_refs": ["6 passed", "handoff"],
                    "source": "validation_evidence",
                    "ref_type": "validation",
                    "status": "ready",
                }
            ],
        }
    )

    assert digest["kind"] == "integration_review_query_result_digest"
    assert digest["ok"] is True
    assert digest["status"] == "ready"
    assert digest["summary"]["digest_count"] == 1
    assert digest["summary"]["result_count"] == 1
    assert digest["digests"][0]["matched_refs"] == ["6 passed", "handoff"]
    assert digest["digests"][0]["missing_refs"] == []
    assert digest["next_actions"] == ["share_review_query_result_digest_with_mainline"]


def test_partial_query_results_need_review_with_missing_refs() -> None:
    digest = build_integration_review_query_result_digest(
        {
            "review_query_plan": {
                "queries": [
                    {
                        "candidate_id": "candidate-a",
                        "query_key": "query-a",
                        "status": "ready",
                        "evidence_refs": ["tests passed", "handoff"],
                        "owner": "owner-a",
                        "reviewer": "reviewer-a",
                    }
                ]
            },
            "query_results": [
                {
                    "query_key": "query-a",
                    "candidate_id": "candidate-a",
                    "matched_refs": ["tests passed"],
                    "status": "ready",
                }
            ],
        }
    )

    assert digest["status"] == "needs_review"
    assert digest["review_queries"] == ["query-a"]
    assert digest["missing_refs"] == {"query-a": ["handoff"]}
    assert "query refs incomplete" in digest["digests"][0]["reasons"]
    assert "attach_review_query_result_payloads" in digest["next_actions"]


def test_blocked_result_or_evidence_blocks_digest() -> None:
    digest = build_integration_review_query_result_digest(
        {
            "review_query_plan": {
                "queries": [
                    {
                        "candidate_id": "candidate-a",
                        "query_key": "query-a",
                        "status": "ready",
                        "evidence_refs": ["blocked evidence"],
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
                        "ref_type": "evidence",
                        "status": "blocked",
                    }
                ]
            },
            "query_results": [
                {
                    "query_key": "query-a",
                    "candidate_id": "candidate-a",
                    "matched_refs": ["blocked evidence"],
                    "status": "blocked",
                }
            ],
        }
    )

    assert digest["status"] == "blocked"
    assert digest["blocked_queries"] == ["query-a"]
    assert digest["digests"][0]["status"] == "blocked"
    assert "query result source blocked" in digest["digests"][0]["reasons"]
    assert digest["next_actions"] == [
        "resolve_review_query_result_blockers",
        "rebuild_integration_review_query_result_digest",
    ]


def test_empty_review_query_result_digest_requests_inputs() -> None:
    digest = build_integration_review_query_result_digest({})

    assert digest["ok"] is False
    assert digest["status"] == "empty"
    assert digest["next_actions"] == ["provide_review_query_result_digest_inputs"]


def test_explicit_result_payload_can_seed_digest_without_plan() -> None:
    digest = build_integration_review_query_result_digest(
        {
            "query_results": [
                {
                    "query_key": "query-a",
                    "candidate_id": "candidate-a",
                    "matched_refs": ["direct result"],
                    "source": "manual",
                    "ref_type": "evidence",
                    "status": "ready",
                }
            ]
        }
    )

    assert digest["status"] == "needs_review"
    assert digest["digests"][0]["candidate_id"] == "candidate-a"
    assert digest["digests"][0]["result_count"] == 1
    assert digest["digests"][0]["matched_refs"] == ["direct result"]
    assert "expected refs missing" in digest["digests"][0]["reasons"]


def test_summarize_review_query_result_digest_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Digest:
        candidate_id: str
        query_key: str
        evidence_refs: tuple[str, ...]
        owner: str
        reviewer: str
        status: str

    item = summarize_review_query_result_digest_item(
        Digest(
            candidate_id="candidate-a",
            query_key="query-a",
            evidence_refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
            status="ready",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.query_key == "query-a"
    assert item.status == "needs_review"
    assert item.missing_refs == ("handoff",)
    assert "query results missing" in item.reasons
