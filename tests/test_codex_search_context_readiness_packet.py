from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_search_context_readiness_packet import (
    build_codex_search_context_readiness_packet,
    summarize_codex_search_context,
)


PACKET_POLICIES = {
    "search_policy": "search-policy",
    "source_policy": "source-policy",
    "freshness_policy": "freshness-policy",
    "scope_policy": "scope-policy",
    "search_manifest_ref": "search-manifest",
    "context_governance_ref": "context-governance",
}


def test_ready_search_context_has_context_gathering_evidence() -> None:
    packet = build_codex_search_context_readiness_packet(
        {
            **PACKET_POLICIES,
            "search_contexts": [
                {
                    "search_context_id": "search-1",
                    "status": "validated",
                    "search_query_ref": "query",
                    "result_set_refs": ["results"],
                    "source_attribution_refs": ["sources"],
                    "freshness_refs": ["freshness"],
                    "scope_refs": ["scope"],
                    "relevance_refs": ["relevance"],
                    "ranking_refs": ["ranking"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_search_context_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["search_context_count"] == 1
    assert packet["summary"]["source_attribution_ref_count"] == 1
    assert packet["next_actions"] == ["share_search_context_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_search_context_readiness_packet(
        {
            "search_contexts": [
                {
                    "search_context_id": "search-1",
                    "status": "validated",
                    "search_query_ref": "query",
                    "result_set_refs": ["results"],
                    "source_attribution_refs": ["sources"],
                    "scope_refs": ["scope"],
                    "relevance_refs": ["relevance"],
                    "ranking_refs": ["ranking"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_search_context_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "search_policy_ref",
        "source_policy_ref",
        "freshness_policy_ref",
        "scope_policy_ref",
        "search_manifest_ref",
        "context_governance_ref",
    ]


def test_stale_or_untrusted_context_requires_freshness_ref_and_blocks() -> None:
    packet = build_codex_search_context_readiness_packet(
        {
            **PACKET_POLICIES,
            "search_contexts": [
                {
                    "search_context_id": "search-2",
                    "status": "stale",
                    "search_query_ref": "query",
                    "result_set_refs": ["results"],
                    "source_attribution_refs": ["sources"],
                    "scope_refs": ["scope"],
                    "relevance_refs": ["relevance"],
                    "ranking_refs": ["ranking"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    context = packet["search_contexts"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_search_context_status_failed"
    assert "freshness_refs" in context["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_search_context_blockers",
        "refresh_search_context_readiness",
    ]


def test_missing_source_scope_relevance_ranking_and_receipt_refs_needs_review() -> None:
    context = summarize_codex_search_context(
        {
            "search_context_id": "search-3",
            "status": "recorded",
            "search_query_ref": "query",
            "result_set_refs": ["results"],
            "artifact_refs": ["artifact"],
        }
    )

    assert context.readiness_state == "needs_review"
    assert "source_attribution_refs" in context.missing_refs
    assert "scope_refs" in context.missing_refs
    assert "relevance_refs" in context.missing_refs
    assert "ranking_refs" in context.missing_refs
    assert "validation_receipt_refs" in context.missing_refs


def test_live_filesystem_web_or_index_search_attempt_blocks_candidate() -> None:
    packet = build_codex_search_context_readiness_packet(
        {
            **PACKET_POLICIES,
            "search_contexts": [
                {
                    "search_context_id": "search-4",
                    "status": "validated",
                    "search_query_ref": "query",
                    "result_set_refs": ["results"],
                    "source_attribution_refs": ["sources"],
                    "freshness_refs": ["freshness"],
                    "scope_refs": ["scope"],
                    "relevance_refs": ["relevance"],
                    "ranking_refs": ["ranking"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "search_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_search_context_live_execution_blocked"
    assert "live_search_context_execution_attempted" in packet["search_contexts"][0]["blockers"]


def test_empty_payload_requests_search_context_inventory() -> None:
    packet = build_codex_search_context_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_search_context_inventory"]


def test_dataclass_like_search_context_is_accepted_by_summarizer() -> None:
    @dataclass
    class SearchContext:
        search_context_id: str
        status: str
        search_query_ref: str
        result_set_refs: list[str]
        source_attribution_refs: list[str]
        freshness_refs: list[str]
        scope_refs: list[str]
        relevance_refs: list[str]
        ranking_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    context = summarize_codex_search_context(
        SearchContext(
            "search-5",
            "passed",
            "query",
            ["results"],
            ["sources"],
            ["freshness"],
            ["scope"],
            ["relevance"],
            ["ranking"],
            ["validation"],
            ["artifact"],
        )
    )

    assert context.search_context_id == "search-5"
    assert context.status == "passed"
    assert context.readiness_state == "ready"
