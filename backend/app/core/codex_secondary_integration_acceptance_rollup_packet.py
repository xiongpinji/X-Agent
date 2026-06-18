from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_acceptance_rollup_packet', 'collection_key': 'rollups', 'required_packet_refs': ['acceptance_rollup_policy', 'owner_acceptance_policy', 'residual_risk_policy', 'secondary_integration_policy', 'secondary_integration_acceptance_rollup_manifest_ref', 'secondary_integration_acceptance_governance_ref'], 'packet_missing_refs': ['acceptance_rollup_policy_ref', 'owner_acceptance_policy_ref', 'residual_risk_policy_ref', 'secondary_integration_policy_ref', 'secondary_integration_acceptance_rollup_manifest_ref', 'secondary_integration_acceptance_governance_ref'], 'required_item_refs': ['final_review_refs', 'closure_index_refs', 'owner_acceptance_refs', 'validation_refs', 'candidate_disposition_refs', 'owner_next_action_refs'], 'conditional_refs': {'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_acceptance_rollup_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_acceptance_rollup_inventory'], 'review_actions': ['review_deferred_secondary_candidates', 'refresh_acceptance_rollup_packet'], 'prefix': 'codex_secondary_integration_acceptance_rollup', 'failed_code': 'codex_secondary_integration_acceptance_rollup_status_failed', 'packet_missing_code': 'codex_secondary_integration_acceptance_rollup_packet_missing_evidence', 'live_code': 'codex_secondary_integration_acceptance_rollup_live_operation_blocked', 'summary_ref_field': 'accepted_candidate_refs', 'summary_ref_count_key': 'accepted_candidate_ref_count'}


def summarize_codex_secondary_integration_acceptance_rollup(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_acceptance_rollup_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
