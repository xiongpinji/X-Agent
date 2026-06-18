from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_mainline_adoption_readiness_rollup_packet', 'collection_key': 'adoptions', 'required_packet_refs': ['mainline_adoption_policy', 'secondary_candidate_policy', 'integration_risk_policy', 'skipped_item_policy', 'mainline_adoption_readiness_manifest_ref', 'secondary_integration_governance_ref'], 'packet_missing_refs': ['mainline_adoption_policy_ref', 'secondary_candidate_policy_ref', 'integration_risk_policy_ref', 'skipped_item_policy_ref', 'mainline_adoption_readiness_manifest_ref', 'secondary_integration_governance_ref'], 'required_item_refs': ['closure_rollup_refs', 'owner_review_refs', 'validation_chain_refs', 'integration_risk_refs', 'skipped_item_refs', 'mainline_decision_refs', 'artifact_refs', 'next_step_refs'], 'ready_actions': ['share_codex_mainline_adoption_readiness_rollup_with_mainline'], 'empty_actions': ['provide_codex_mainline_adoption_readiness_inventory'], 'review_actions': ['review_mainline_adoption_integration_risks', 'decide_secondary_candidate_next_steps'], 'prefix': 'codex_mainline_adoption_readiness_rollup', 'failed_code': 'codex_mainline_adoption_readiness_rollup_status_failed', 'packet_missing_code': 'codex_mainline_adoption_readiness_rollup_packet_missing_evidence', 'live_code': 'codex_mainline_adoption_readiness_rollup_live_operation_blocked', 'summary_ref_field': 'mainline_decision_refs', 'summary_ref_count_key': 'mainline_decision_ref_count'}


def summarize_codex_mainline_adoption_readiness_rollup(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_mainline_adoption_readiness_rollup_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
