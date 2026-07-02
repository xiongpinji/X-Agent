from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_mainline_evaluation_receipt_packet', 'collection_key': 'receipts', 'required_packet_refs': ['mainline_receipt_policy', 'candidate_classification_policy', 'evaluation_receipt_policy', 'next_action_policy', 'mainline_evaluation_receipt_manifest_ref', 'mainline_evaluation_governance_ref'], 'packet_missing_refs': ['mainline_receipt_policy_ref', 'candidate_classification_policy_ref', 'evaluation_receipt_policy_ref', 'next_action_policy_ref', 'mainline_evaluation_receipt_manifest_ref', 'mainline_evaluation_governance_ref'], 'required_item_refs': ['candidate_classification_refs', 'batch_snapshot_refs', 'decision_brief_refs', 'adoption_readiness_refs', 'validation_refs', 'skipped_item_refs'], 'conditional_refs': {'needs_failure_evidence': ['risk_refs', 'next_action_refs']}, 'ready_actions': ['share_codex_mainline_evaluation_receipt_with_mainline'], 'empty_actions': ['provide_codex_mainline_evaluation_receipt_inventory'], 'review_actions': ['review_stale_mainline_evaluation_receipts', 'refresh_secondary_candidate_evaluation'], 'prefix': 'codex_mainline_evaluation_receipt', 'failed_code': 'codex_mainline_evaluation_receipt_status_failed', 'packet_missing_code': 'codex_mainline_evaluation_receipt_packet_missing_evidence', 'live_code': 'codex_mainline_evaluation_receipt_live_operation_blocked', 'summary_ref_field': 'candidate_classification_refs', 'summary_ref_count_key': 'candidate_classification_ref_count'}


def summarize_codex_mainline_evaluation_receipt(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_mainline_evaluation_receipt_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
