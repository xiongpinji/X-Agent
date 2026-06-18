from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_query_preview_packet', 'collection_key': 'previews', 'required_packet_refs': ['archive_query_preview_policy', 'archive_index_policy', 'lookup_key_policy', 'query_result_policy', 'secondary_integration_adoption_decision_archive_query_preview_manifest_ref', 'secondary_integration_adoption_decision_archive_query_governance_ref'], 'packet_missing_refs': ['archive_query_preview_policy_ref', 'archive_index_policy_ref', 'lookup_key_policy_ref', 'query_result_policy_ref', 'secondary_integration_adoption_decision_archive_query_preview_manifest_ref', 'secondary_integration_adoption_decision_archive_query_governance_ref'], 'required_item_refs': ['archive_index_refs', 'lookup_keys', 'query_refs', 'filter_refs', 'result_refs', 'validation_refs', 'retention_refs'], 'conditional_refs': {'needs_failure_evidence': ['retention_refs', 'missing_result_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_query_preview_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_query_preview_inventory'], 'review_actions': ['review_archive_query_filters', 'refresh_archive_query_preview_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_query_preview', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_query_preview_status_failed', 'missing_code': 'codex_secondary_integration_adoption_decision_archive_query_preview_missing_evidence', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_query_preview_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_query_preview_live_operation_blocked'}


def summarize_codex_secondary_integration_adoption_decision_archive_query_preview(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_query_preview_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
