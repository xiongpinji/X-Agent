from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_ledger_packet', 'collection_key': 'decisions', 'required_packet_refs': ['adoption_decision_ledger_policy', 'owner_decision_policy', 'candidate_disposition_policy', 'decision_timestamp_policy', 'secondary_integration_adoption_decision_ledger_manifest_ref', 'secondary_integration_adoption_decision_governance_ref'], 'packet_missing_refs': ['adoption_decision_ledger_policy_ref', 'owner_decision_policy_ref', 'candidate_disposition_policy_ref', 'decision_timestamp_policy_ref', 'secondary_integration_adoption_decision_ledger_manifest_ref', 'secondary_integration_adoption_decision_governance_ref'], 'required_item_refs': ['acceptance_rollup_refs', 'final_review_refs', 'owner_decision_refs', 'candidate_disposition_refs', 'validation_refs', 'handoff_refs', 'decision_timestamp_refs'], 'conditional_refs': {'residual_risk_detected': ['residual_risk_refs']}, 'ready_actions': ['share_codex_secondary_integration_adoption_decision_ledger_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_ledger_inventory'], 'review_actions': ['attach_adoption_decision_timestamps', 'refresh_adoption_decision_ledger_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_ledger', 'failed_code': 'codex_secondary_integration_adoption_decision_ledger_status_failed', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_ledger_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_ledger_live_operation_blocked', 'summary_ref_field': 'accepted_disposition_refs', 'summary_ref_count_key': 'accepted_disposition_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_ledger(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_ledger_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
