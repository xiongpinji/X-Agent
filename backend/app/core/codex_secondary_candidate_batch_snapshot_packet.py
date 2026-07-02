from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_candidate_batch_snapshot_packet', 'collection_key': 'batches', 'required_packet_refs': ['candidate_batch_policy', 'batch_readiness_policy', 'batch_risk_policy', 'next_batch_policy', 'secondary_candidate_batch_manifest_ref', 'secondary_candidate_batch_governance_ref'], 'packet_missing_refs': ['candidate_batch_policy_ref', 'batch_readiness_policy_ref', 'batch_risk_policy_ref', 'next_batch_policy_ref', 'secondary_candidate_batch_manifest_ref', 'secondary_candidate_batch_governance_ref'], 'required_item_refs': ['candidate_refs', 'readiness_rollup_refs', 'adoption_readiness_refs', 'validation_receipt_refs', 'owner_mainline_review_refs', 'skipped_item_refs', 'next_batch_refs'], 'conditional_refs': {'needs_failure_evidence': ['risk_refs']}, 'ready_actions': ['share_codex_secondary_candidate_batch_snapshot_with_mainline'], 'empty_actions': ['provide_codex_secondary_candidate_batch_snapshot_inventory'], 'review_actions': ['review_secondary_candidate_batch_risks', 'plan_next_secondary_candidate_batch'], 'prefix': 'codex_secondary_candidate_batch_snapshot', 'failed_code': 'codex_secondary_candidate_batch_snapshot_status_failed', 'packet_missing_code': 'codex_secondary_candidate_batch_snapshot_packet_missing_evidence', 'live_code': 'codex_secondary_candidate_batch_snapshot_live_operation_blocked', 'summary_ref_field': 'candidate_refs', 'summary_ref_count_key': 'candidate_ref_count'}


def summarize_codex_secondary_candidate_batch_snapshot(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_candidate_batch_snapshot_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
