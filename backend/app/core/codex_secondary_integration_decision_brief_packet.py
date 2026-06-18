from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_decision_brief_packet', 'collection_key': 'briefs', 'required_packet_refs': ['decision_brief_policy', 'recommended_decision_policy', 'batch_snapshot_policy', 'secondary_integration_policy', 'secondary_integration_decision_brief_manifest_ref', 'secondary_integration_decision_governance_ref'], 'packet_missing_refs': ['decision_brief_policy_ref', 'recommended_decision_policy_ref', 'batch_snapshot_policy_ref', 'secondary_integration_policy_ref', 'secondary_integration_decision_brief_manifest_ref', 'secondary_integration_decision_governance_ref'], 'required_item_refs': ['batch_snapshot_refs', 'adoption_readiness_refs', 'validation_refs', 'skipped_item_refs', 'owner_mainline_review_refs', 'recommended_decision_refs', 'next_step_refs'], 'conditional_refs': {'needs_failure_evidence': ['risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_decision_brief_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_decision_brief_inventory'], 'review_actions': ['review_secondary_integration_decision_risks', 'revise_recommended_secondary_decision'], 'prefix': 'codex_secondary_integration_decision_brief', 'failed_code': 'codex_secondary_integration_decision_brief_status_failed', 'packet_missing_code': 'codex_secondary_integration_decision_brief_packet_missing_evidence', 'live_code': 'codex_secondary_integration_decision_brief_live_operation_blocked', 'summary_ref_field': 'recommended_decision_refs', 'summary_ref_count_key': 'recommended_decision_ref_count'}


def summarize_codex_secondary_integration_decision_brief(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_decision_brief_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
