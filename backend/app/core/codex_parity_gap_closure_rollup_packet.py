from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_parity_gap_closure_rollup_packet', 'collection_key': 'rollups', 'required_packet_refs': ['gap_closure_policy', 'validation_chain_policy', 'mainline_handoff_policy', 'next_wave_policy', 'codex_parity_gap_closure_manifest_ref', 'codex_parity_closure_governance_ref'], 'packet_missing_refs': ['gap_closure_policy_ref', 'validation_chain_policy_ref', 'mainline_handoff_policy_ref', 'next_wave_policy_ref', 'codex_parity_gap_closure_manifest_ref', 'codex_parity_closure_governance_ref'], 'required_item_refs': ['owner_review_refs', 'accepted_candidate_refs', 'validation_chain_refs', 'mainline_handoff_refs', 'artifact_refs', 'deferred_candidate_refs', 'next_wave_refs'], 'conditional_refs': {'residual_gap_detected': ['residual_gap_refs']}, 'ready_actions': ['share_codex_parity_gap_closure_rollup_packet_with_mainline'], 'empty_actions': ['provide_codex_parity_gap_closure_rollup_inventory'], 'review_actions': ['review_codex_parity_residual_gaps', 'queue_codex_parity_next_wave'], 'prefix': 'codex_parity_gap_closure_rollup', 'failed_code': 'codex_parity_gap_closure_rollup_status_failed', 'packet_missing_code': 'codex_parity_gap_closure_rollup_packet_missing_evidence', 'live_code': 'codex_parity_gap_closure_rollup_live_operation_blocked', 'summary_ref_field': 'accepted_candidate_refs', 'summary_ref_count_key': 'accepted_candidate_ref_count'}


def summarize_codex_parity_gap_closure_rollup(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_parity_gap_closure_rollup_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
