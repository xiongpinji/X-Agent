from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_closure_index_packet', 'collection_key': 'closures', 'required_packet_refs': ['closure_index_policy', 'secondary_batch_policy', 'unresolved_item_policy', 'index_freshness_policy', 'secondary_integration_closure_index_manifest_ref', 'secondary_integration_closure_governance_ref'], 'packet_missing_refs': ['closure_index_policy_ref', 'secondary_batch_policy_ref', 'unresolved_item_policy_ref', 'index_freshness_policy_ref', 'secondary_integration_closure_index_manifest_ref', 'secondary_integration_closure_governance_ref'], 'required_item_refs': ['batch_snapshot_refs', 'decision_brief_refs', 'mainline_evaluation_receipt_refs', 'adoption_readiness_refs', 'validation_refs', 'skipped_item_refs', 'unresolved_item_refs'], 'conditional_refs': {'needs_failure_evidence': ['risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_closure_index_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_closure_index_inventory'], 'review_actions': ['review_stale_secondary_integration_closure_index', 'refresh_secondary_integration_closure_index'], 'prefix': 'codex_secondary_integration_closure_index', 'failed_code': 'codex_secondary_integration_closure_index_status_failed', 'packet_missing_code': 'codex_secondary_integration_closure_index_packet_missing_evidence', 'live_code': 'codex_secondary_integration_closure_index_live_operation_blocked', 'summary_ref_field': 'mainline_evaluation_receipt_refs', 'summary_ref_count_key': 'mainline_evaluation_receipt_ref_count'}


def summarize_codex_secondary_integration_closure_index(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_closure_index_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
