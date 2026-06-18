from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_gap_matrix_traceability_readiness_packet', 'collection_key': 'capabilities', 'required_packet_refs': ['gap_matrix_policy', 'traceability_policy', 'adoption_status_policy', 'residual_gap_policy', 'codex_gap_matrix_manifest_ref', 'codex_parity_governance_ref'], 'packet_missing_refs': ['gap_matrix_policy_ref', 'traceability_policy_ref', 'adoption_status_policy_ref', 'residual_gap_policy_ref', 'codex_gap_matrix_manifest_ref', 'codex_parity_governance_ref'], 'required_item_refs': ['capability_ref', 'competitor_source_refs', 'candidate_refs', 'handoff_refs', 'adoption_status_refs', 'owner_refs', 'implemented_module_refs', 'validation_receipt_refs'], 'conditional_refs': {'residual_gap_detected': ['residual_gap_refs']}, 'ready_actions': ['share_codex_gap_matrix_traceability_readiness_with_mainline'], 'empty_actions': ['provide_codex_gap_matrix_traceability_inventory'], 'review_actions': ['review_codex_gap_matrix_residual_gaps', 'decide_next_gap_candidate'], 'prefix': 'codex_gap_matrix_traceability_readiness', 'failed_code': 'codex_gap_matrix_traceability_status_failed', 'packet_missing_code': 'codex_gap_matrix_traceability_packet_missing_evidence', 'live_code': 'codex_gap_matrix_traceability_live_operation_blocked', 'summary_ref_field': 'implemented_module_refs', 'summary_ref_count_key': 'implemented_module_ref_count'}


def summarize_codex_gap_matrix_traceability(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_gap_matrix_traceability_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
