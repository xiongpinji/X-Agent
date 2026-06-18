from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_secondary_integration_adoption_decision_archive_query_preview_packet import (
    build_codex_secondary_integration_adoption_decision_archive_query_preview_packet,
    summarize_codex_secondary_integration_adoption_decision_archive_query_preview,
)


PACKET_POLICIES = {
    "archive_query_preview_policy": "archive-query-preview-policy",
    "archive_index_policy": "archive-index-policy",
    "lookup_key_policy": "lookup-key-policy",
    "query_result_policy": "query-result-policy",
    "secondary_integration_adoption_decision_archive_query_preview_manifest_ref": "query-preview-manifest",
    "secondary_integration_adoption_decision_archive_query_governance_ref": "query-governance",
}


def test_ready_secondary_integration_archive_query_preview_has_complete_evidence() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "preview-1",
                    "status": "previewed",
                    "archive_query_preview_ref": "query-preview",
                    "archive_index_refs": ["archive-index"],
                    "lookup_keys": ["candidate-a"],
                    "query_refs": ["query"],
                    "filter_refs": ["filter"],
                    "result_refs": ["result"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "missing_result_refs": ["none"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_secondary_integration_adoption_decision_archive_query_preview_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["preview_count"] == 1
    assert packet["summary"]["lookup_key_count"] == 1
    assert packet["next_actions"] == ["share_codex_secondary_integration_adoption_decision_archive_query_preview_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(
        {
            "previews": [
                {
                    "preview_id": "preview-2",
                    "status": "matched",
                    "archive_query_preview_ref": "query-preview",
                    "archive_index_refs": ["archive-index"],
                    "lookup_keys": ["candidate-a"],
                    "query_refs": ["query"],
                    "filter_refs": ["filter"],
                    "result_refs": ["result"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_query_preview_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "archive_query_preview_policy_ref",
        "archive_index_policy_ref",
        "lookup_key_policy_ref",
        "query_result_policy_ref",
        "secondary_integration_adoption_decision_archive_query_preview_manifest_ref",
        "secondary_integration_adoption_decision_archive_query_governance_ref",
    ]


def test_failed_or_stale_query_preview_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "preview-3",
                    "status": "stale",
                    "archive_query_preview_ref": "query-preview",
                    "archive_index_refs": ["archive-index"],
                    "lookup_keys": ["candidate-a"],
                    "query_refs": ["query"],
                    "filter_refs": ["filter"],
                    "result_refs": ["result"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                }
            ],
        }
    )

    preview = packet["previews"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_query_preview_status_failed"
    assert "codex_secondary_integration_adoption_decision_archive_query_preview_status_failed" in preview["blockers"]


def test_missing_archive_query_preview_refs_needs_review() -> None:
    preview = summarize_codex_secondary_integration_adoption_decision_archive_query_preview(
        {
            "preview_id": "preview-4",
            "status": "previewed",
            "archive_query_preview_ref": "query-preview",
        }
    )

    assert preview.readiness_state == "needs_review"
    assert "archive_index_refs" in preview.missing_refs
    assert "lookup_keys" in preview.missing_refs
    assert "query_refs" in preview.missing_refs
    assert "filter_refs" in preview.missing_refs
    assert "result_refs" in preview.missing_refs
    assert "retention_refs" in preview.missing_refs
    assert "validation_refs" in preview.missing_refs


def test_open_archive_query_preview_warns_until_receipts_attach() -> None:
    preview = summarize_codex_secondary_integration_adoption_decision_archive_query_preview(
        {
            "preview_id": "preview-5",
            "status": "needs-review",
            "archive_query_preview_ref": "query-preview",
            "archive_index_refs": ["archive-index"],
            "lookup_keys": ["candidate-a"],
            "query_refs": ["query"],
            "filter_refs": ["filter"],
            "result_refs": ["result"],
            "retention_refs": ["retention"],
            "validation_refs": ["validation"],
        }
    )

    assert preview.readiness_state == "needs_review"
    assert preview.missing_refs == ()
    assert "codex_secondary_integration_adoption_decision_archive_query_preview_still_open" in preview.warnings


def test_missing_results_warning_requires_missing_result_refs() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "preview-6",
                    "status": "previewed",
                    "archive_query_preview_ref": "query-preview",
                    "archive_index_refs": ["archive-index"],
                    "lookup_keys": ["candidate-a"],
                    "query_refs": ["query"],
                    "filter_refs": ["filter"],
                    "result_refs": ["result"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "missing_results_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_query_preview_missing_evidence"
    assert "missing_result_refs" in packet["previews"][0]["missing_refs"]
    assert packet["next_actions"] == [
        "attach_codex_secondary_integration_adoption_decision_archive_query_preview_evidence",
        "refresh_codex_secondary_integration_adoption_decision_archive_query_preview_packet",
    ]


def test_filter_review_warning_drives_filter_review_action() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "preview-7",
                    "status": "previewed",
                    "archive_query_preview_ref": "query-preview",
                    "archive_index_refs": ["archive-index"],
                    "lookup_keys": ["candidate-a"],
                    "query_refs": ["query"],
                    "filter_refs": ["filter"],
                    "result_refs": ["result"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "filter_review_required": True,
                }
            ],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_query_preview_filter_review_required"
    assert packet["next_actions"] == [
        "review_archive_query_filters",
        "refresh_archive_query_preview_packet",
    ]


def test_live_query_search_database_or_runtime_mutation_blocks_candidate() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(
        {
            **PACKET_POLICIES,
            "previews": [
                {
                    "preview_id": "preview-8",
                    "status": "previewed",
                    "archive_query_preview_ref": "query-preview",
                    "archive_index_refs": ["archive-index"],
                    "lookup_keys": ["candidate-a"],
                    "query_refs": ["query"],
                    "filter_refs": ["filter"],
                    "result_refs": ["result"],
                    "retention_refs": ["retention"],
                    "validation_refs": ["validation"],
                    "query_execution_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_secondary_integration_adoption_decision_archive_query_preview_live_operation_blocked"
    assert "live_codex_secondary_integration_adoption_decision_archive_query_preview_operation_attempted" in packet["previews"][0]["blockers"]


def test_empty_payload_requests_secondary_integration_archive_query_preview_inventory() -> None:
    packet = build_codex_secondary_integration_adoption_decision_archive_query_preview_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_secondary_integration_adoption_decision_archive_query_preview_inventory"]


def test_dataclass_like_archive_query_preview_is_accepted_by_summarizer() -> None:
    @dataclass
    class QueryPreview:
        preview_id: str
        status: str
        archive_query_preview_ref: str
        archive_index_refs: list[str]
        lookup_keys: list[str]
        query_refs: list[str]
        filter_refs: list[str]
        result_refs: list[str]
        retention_refs: list[str]
        validation_refs: list[str]
        missing_result_refs: list[str]

    preview = summarize_codex_secondary_integration_adoption_decision_archive_query_preview(
        QueryPreview(
            "preview-9",
            "complete",
            "query-preview",
            ["archive-index"],
            ["candidate-a"],
            ["query"],
            ["filter"],
            ["result"],
            ["retention"],
            ["validation"],
            ["none"],
        )
    )

    assert preview.preview_id == "preview-9"
    assert preview.status == "complete"
    assert preview.readiness_state == "ready"
