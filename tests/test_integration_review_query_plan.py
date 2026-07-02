from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.integration_review_query_plan import (
    build_integration_review_query_plan,
    summarize_review_query_plan_item,
)


def test_review_query_plan_builds_ready_queries_from_evidence_index() -> None:
    plan = build_integration_review_query_plan(
        {
            "plan_id": "query-plan-1",
            "review_evidence_index": {
                "records": [
                    {
                        "candidate_id": "integration_review_evidence_index",
                        "ref": "6 passed",
                        "source": "validation_evidence",
                        "ref_type": "validation",
                        "status": "ready",
                        "owner": "mainline",
                    },
                    {
                        "candidate_id": "integration_review_evidence_index",
                        "ref": "docs/original-kernel-secondary-handoff.md",
                        "source": "handoff_refs",
                        "ref_type": "handoff",
                        "status": "ready",
                        "owner": "mainline",
                    },
                ]
            },
            "owner_hints": {"integration_review_evidence_index": "mainline"},
            "reviewer_hints": {"integration_review_evidence_index": "reviewer-a"},
        }
    )

    assert plan["kind"] == "integration_review_query_plan"
    assert plan["ok"] is True
    assert plan["status"] == "ready"
    assert plan["summary"]["query_count"] == 1
    assert plan["queries"][0]["candidate_id"] == "integration_review_evidence_index"
    assert plan["queries"][0]["filters"]["source"] == ["validation_evidence", "handoff_refs"]
    assert plan["queries"][0]["filters"]["ref_type"] == ["validation", "handoff"]
    assert plan["queries"][0]["evidence_refs"] == ["6 passed", "docs/original-kernel-secondary-handoff.md"]
    assert plan["next_actions"] == ["share_review_query_plan_with_mainline"]


def test_explicit_filters_are_merged_with_evidence_index_filters() -> None:
    plan = build_integration_review_query_plan(
        {
            "filters": {"source": ["handoff_refs"], "ref_type": ["handoff"]},
            "candidate_filters": [
                {
                    "candidate_id": "candidate-a",
                    "sources": ["validation_evidence"],
                    "ref_types": ["validation"],
                    "owner": "owner-a",
                    "reviewer": "reviewer-a",
                }
            ],
            "review_evidence_index": {
                "records": [
                    {
                        "candidate_id": "candidate-a",
                        "ref": "tests passed",
                        "source": "validation_evidence",
                        "ref_type": "validation",
                        "status": "ready",
                    }
                ]
            },
        }
    )

    query = plan["queries"][0]
    assert plan["status"] == "ready"
    assert query["filters"]["candidate_id"] == ["candidate-a"]
    assert query["filters"]["source"] == ["handoff_refs", "validation_evidence"]
    assert query["filters"]["ref_type"] == ["handoff", "validation"]
    assert query["owner"] == "owner-a"
    assert query["reviewer"] == "reviewer-a"


def test_blocked_evidence_and_retention_decision_block_query() -> None:
    plan = build_integration_review_query_plan(
        {
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
            "review_retention_policy": {
                "decisions": [
                    {
                        "candidate_id": "candidate-a",
                        "status": "blocked",
                        "owner": "owner-a",
                        "evidence_refs": ["blocked evidence"],
                    }
                ]
            },
            "reviewer_hints": {"candidate-a": "reviewer-a"},
        }
    )

    assert plan["status"] == "blocked"
    assert plan["blocked_queries"] == ["review-query:candidate-a"]
    assert plan["queries"][0]["status"] == "blocked"
    assert "query source blocked" in plan["queries"][0]["reasons"]
    assert plan["next_actions"] == [
        "resolve_review_query_plan_blockers",
        "rebuild_integration_review_query_plan",
    ]


def test_missing_candidate_or_evidence_refs_need_review() -> None:
    plan = build_integration_review_query_plan(
        {
            "queries": [
                {
                    "query_key": "manual-query",
                    "source": "manual",
                    "ref_type": "evidence",
                }
            ]
        }
    )

    assert plan["status"] == "needs_review"
    assert plan["review_queries"] == ["manual-query"]
    assert plan["queries"][0]["candidate_id"] == "unknown"
    assert plan["queries"][0]["reasons"] == [
        "candidate id missing",
        "evidence refs missing",
        "owner hint missing",
        "reviewer hint missing",
    ]
    assert "complete_review_query_plan" in plan["next_actions"]


def test_empty_review_query_plan_requests_inputs() -> None:
    plan = build_integration_review_query_plan({})

    assert plan["ok"] is False
    assert plan["status"] == "empty"
    assert plan["next_actions"] == ["provide_review_query_plan_inputs"]


def test_summarize_review_query_plan_item_accepts_dataclass_like_payload() -> None:
    @dataclass
    class Query:
        candidate_id: str
        query_key: str
        source: str
        ref_type: str
        refs: tuple[str, ...]
        owner: str
        reviewer: str
        status: str

    item = summarize_review_query_plan_item(
        Query(
            candidate_id="candidate-a",
            query_key="query-a",
            source="manual",
            ref_type="handoff",
            refs=("handoff",),
            owner="owner-a",
            reviewer="reviewer-a",
            status="ready",
        )
    )

    assert item.candidate_id == "candidate-a"
    assert item.query_key == "query-a"
    assert item.status == "ready"
    assert item.filters["source"] == ["manual"]
    assert item.filters["ref_type"] == ["handoff"]
    assert item.evidence_refs == ("handoff",)
