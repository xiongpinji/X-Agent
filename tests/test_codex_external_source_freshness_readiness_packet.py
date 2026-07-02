from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_external_source_freshness_readiness_packet import (
    build_codex_external_source_freshness_readiness_packet,
    summarize_codex_external_source_freshness,
)


PACKET_POLICIES = {
    "external_source_policy": "external-source-policy",
    "freshness_policy": "freshness-policy",
    "attribution_policy": "attribution-policy",
    "stale_context_policy": "stale-context-policy",
    "external_source_manifest_ref": "external-source-manifest",
    "current_information_governance_ref": "current-information-governance",
}


def test_ready_external_source_has_current_information_evidence() -> None:
    packet = build_codex_external_source_freshness_readiness_packet(
        {
            **PACKET_POLICIES,
            "external_sources": [
                {
                    "source_id": "source-1",
                    "status": "fresh",
                    "source_ref": "source-url",
                    "official_source_refs": ["official-docs"],
                    "retrieval_timestamp_refs": ["retrieved-at"],
                    "freshness_refs": ["freshness-check"],
                    "source_attribution_refs": ["attribution"],
                    "stale_context_warning_refs": ["stale-warning-policy"],
                    "citation_refs": ["citation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_external_source_freshness_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["source_count"] == 1
    assert packet["summary"]["official_source_ref_count"] == 1
    assert packet["next_actions"] == ["share_external_source_freshness_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_external_source_freshness_readiness_packet(
        {
            "external_sources": [
                {
                    "source_id": "source-2",
                    "status": "fresh",
                    "source_ref": "source-url",
                    "official_source_refs": ["official-docs"],
                    "retrieval_timestamp_refs": ["retrieved-at"],
                    "freshness_refs": ["freshness"],
                    "source_attribution_refs": ["attribution"],
                    "citation_refs": ["citation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_external_source_freshness_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "external_source_policy_ref",
        "freshness_policy_ref",
        "attribution_policy_ref",
        "stale_context_policy_ref",
        "external_source_manifest_ref",
        "current_information_governance_ref",
    ]


def test_stale_or_outdated_source_requires_warning_and_blocks() -> None:
    packet = build_codex_external_source_freshness_readiness_packet(
        {
            **PACKET_POLICIES,
            "external_sources": [
                {
                    "source_id": "source-3",
                    "status": "stale",
                    "source_ref": "source-url",
                    "official_source_refs": ["official-docs"],
                    "retrieval_timestamp_refs": ["retrieved-at"],
                    "freshness_refs": ["freshness"],
                    "source_attribution_refs": ["attribution"],
                    "citation_refs": ["citation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    source = packet["external_sources"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_external_source_freshness_status_failed"
    assert "stale_context_warning_refs" in source["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_external_source_freshness_blockers",
        "refresh_external_source_freshness_readiness",
    ]


def test_missing_official_timestamp_freshness_attribution_citation_and_receipts_needs_review() -> None:
    source = summarize_codex_external_source_freshness(
        {
            "source_id": "source-4",
            "status": "current",
            "source_ref": "source-url",
        }
    )

    assert source.readiness_state == "needs_review"
    assert "official_source_refs" in source.missing_refs
    assert "retrieval_timestamp_refs" in source.missing_refs
    assert "freshness_refs" in source.missing_refs
    assert "source_attribution_refs" in source.missing_refs
    assert "citation_refs" in source.missing_refs
    assert "validation_receipt_refs" in source.missing_refs


def test_live_web_retrieval_network_or_cache_mutation_blocks_candidate() -> None:
    packet = build_codex_external_source_freshness_readiness_packet(
        {
            **PACKET_POLICIES,
            "external_sources": [
                {
                    "source_id": "source-5",
                    "status": "validated",
                    "source_ref": "source-url",
                    "official_source_refs": ["official-docs"],
                    "retrieval_timestamp_refs": ["retrieved-at"],
                    "freshness_refs": ["freshness"],
                    "source_attribution_refs": ["attribution"],
                    "stale_context_warning_refs": ["stale-warning"],
                    "citation_refs": ["citation"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "web_browsing_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_external_source_freshness_live_operation_blocked"
    assert "live_external_source_operation_attempted" in packet["external_sources"][0]["blockers"]


def test_empty_payload_requests_external_source_freshness_inventory() -> None:
    packet = build_codex_external_source_freshness_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_external_source_freshness_inventory"]


def test_current_information_claim_requires_retrieval_timestamp_refs() -> None:
    source = summarize_codex_external_source_freshness(
        {
            "source_id": "source-6",
            "status": "fresh",
            "source_ref": "source-url",
            "official_source_refs": ["official"],
            "freshness_refs": ["freshness"],
            "source_attribution_refs": ["attribution"],
            "citation_refs": ["citation"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
            "current_information_claimed": True,
        }
    )

    assert source.readiness_state == "needs_review"
    assert "retrieval_timestamp_refs" in source.missing_refs


def test_dataclass_like_external_source_is_accepted_by_summarizer() -> None:
    @dataclass
    class ExternalSource:
        source_id: str
        status: str
        source_ref: str
        official_source_refs: list[str]
        retrieval_timestamp_refs: list[str]
        freshness_refs: list[str]
        source_attribution_refs: list[str]
        stale_context_warning_refs: list[str]
        citation_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    source = summarize_codex_external_source_freshness(
        ExternalSource(
            "source-7",
            "cited",
            "source-url",
            ["official"],
            ["retrieved-at"],
            ["freshness"],
            ["attribution"],
            ["stale-warning"],
            ["citation"],
            ["validation"],
            ["artifact"],
        )
    )

    assert source.source_id == "source-7"
    assert source.status == "cited"
    assert source.readiness_state == "ready"
