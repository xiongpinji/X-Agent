from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_external_source_freshness_readiness_packet', 'collection_key': 'external_sources', 'required_packet_refs': ['external_source_policy', 'freshness_policy', 'attribution_policy', 'stale_context_policy', 'external_source_manifest_ref', 'current_information_governance_ref'], 'packet_missing_refs': ['external_source_policy_ref', 'freshness_policy_ref', 'attribution_policy_ref', 'stale_context_policy_ref', 'external_source_manifest_ref', 'current_information_governance_ref'], 'required_item_refs': ['stale_context_warning_refs', 'official_source_refs', 'retrieval_timestamp_refs', 'freshness_refs', 'source_attribution_refs', 'citation_refs', 'validation_receipt_refs'], 'ready_actions': ['share_external_source_freshness_readiness_with_mainline'], 'empty_actions': ['provide_codex_external_source_freshness_inventory'], 'blocked_actions': ['resolve_external_source_freshness_blockers', 'refresh_external_source_freshness_readiness'], 'prefix': 'codex_external_source_freshness_readiness', 'failed_code': 'codex_external_source_freshness_status_failed', 'packet_missing_code': 'codex_external_source_freshness_packet_missing_evidence', 'live_code': 'codex_external_source_freshness_live_operation_blocked', 'summary_ref_field': 'official_source_refs', 'summary_ref_count_key': 'official_source_ref_count'}


def summarize_codex_external_source_freshness(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_external_source_freshness_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
