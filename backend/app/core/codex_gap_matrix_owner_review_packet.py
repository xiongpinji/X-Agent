from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_gap_matrix_owner_review_packet', 'collection_key': 'reviews', 'required_packet_refs': ['gap_matrix_review_policy', 'owner_review_policy', 'mainline_acceptance_policy', 'residual_gap_decision_policy', 'codex_gap_matrix_owner_review_manifest_ref', 'codex_parity_owner_governance_ref'], 'packet_missing_refs': ['gap_matrix_review_policy_ref', 'owner_review_policy_ref', 'mainline_acceptance_policy_ref', 'residual_gap_decision_policy_ref', 'codex_gap_matrix_owner_review_manifest_ref', 'codex_parity_owner_governance_ref'], 'required_item_refs': ['owner_reviewer_refs', 'mainline_review_refs', 'acceptance_decision_refs', 'residual_gap_decision_refs', 'validation_receipt_refs', 'handoff_refs', 'artifact_refs', 'next_candidate_refs'], 'ready_actions': ['share_codex_gap_matrix_owner_review_packet_with_mainline'], 'empty_actions': ['provide_codex_gap_matrix_owner_review_inventory'], 'review_actions': ['review_codex_gap_matrix_owner_residual_gaps', 'queue_next_codex_gap_candidate'], 'prefix': 'codex_gap_matrix_owner_review', 'failed_code': 'codex_gap_matrix_owner_review_status_failed', 'packet_missing_code': 'codex_gap_matrix_owner_review_packet_missing_evidence', 'live_code': 'codex_gap_matrix_owner_review_live_operation_blocked', 'summary_ref_field': 'acceptance_decision_refs', 'summary_ref_count_key': 'acceptance_decision_ref_count'}


def summarize_codex_gap_matrix_owner_review(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_gap_matrix_owner_review_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
