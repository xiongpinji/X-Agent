from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_search_context_readiness_packet', 'collection_key': 'search_contexts', 'required_packet_refs': ['search_policy', 'source_policy', 'freshness_policy', 'scope_policy', 'search_manifest_ref', 'context_governance_ref'], 'packet_missing_refs': ['search_policy_ref', 'source_policy_ref', 'freshness_policy_ref', 'scope_policy_ref', 'search_manifest_ref', 'context_governance_ref'], 'required_item_refs': ['freshness_refs', 'source_attribution_refs', 'scope_refs', 'relevance_refs', 'ranking_refs', 'validation_receipt_refs'], 'ready_actions': ['share_search_context_readiness_with_mainline'], 'empty_actions': ['provide_codex_search_context_inventory'], 'blocked_actions': ['resolve_search_context_blockers', 'refresh_search_context_readiness'], 'prefix': 'codex_search_context_readiness', 'failed_code': 'codex_search_context_status_failed', 'packet_missing_code': 'codex_search_context_packet_missing_evidence', 'live_code': 'codex_search_context_live_execution_blocked', 'summary_ref_field': 'source_attribution_refs', 'summary_ref_count_key': 'source_attribution_ref_count'}


def summarize_codex_search_context(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_search_context_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
