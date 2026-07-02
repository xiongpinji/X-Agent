from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_final_review_packet', 'collection_key': 'reviews', 'required_packet_refs': ['final_review_policy', 'owner_acceptance_policy', 'residual_risk_policy', 'secondary_integration_policy', 'secondary_integration_final_review_manifest_ref', 'secondary_integration_final_review_governance_ref'], 'packet_missing_refs': ['final_review_policy_ref', 'owner_acceptance_policy_ref', 'residual_risk_policy_ref', 'secondary_integration_policy_ref', 'secondary_integration_final_review_manifest_ref', 'secondary_integration_final_review_governance_ref'], 'required_item_refs': ['closure_index_refs', 'evaluation_receipt_refs', 'decision_brief_refs', 'owner_acceptance_refs', 'validation_refs', 'skipped_item_refs', 'artifact_refs', 'final_next_action_refs'], 'conditional_refs': {'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_final_review_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_final_review_inventory'], 'review_actions': ['request_secondary_integration_owner_acceptance', 'refresh_final_review_packet'], 'prefix': 'codex_secondary_integration_final_review', 'failed_code': 'codex_secondary_integration_final_review_status_failed', 'packet_missing_code': 'codex_secondary_integration_final_review_packet_missing_evidence', 'live_code': 'codex_secondary_integration_final_review_live_operation_blocked', 'summary_ref_field': 'owner_acceptance_refs', 'summary_ref_count_key': 'owner_acceptance_ref_count'}


def summarize_codex_secondary_integration_final_review(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_final_review_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
