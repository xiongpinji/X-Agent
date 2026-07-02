from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_open_source_candidate_evaluation_readiness_packet', 'collection_key': 'candidates', 'required_packet_refs': ['open_source_policy', 'license_policy', 'security_policy', 'adoption_policy', 'open_source_evaluation_manifest_ref', 'capability_gap_governance_ref'], 'packet_missing_refs': ['open_source_policy_ref', 'license_policy_ref', 'security_policy_ref', 'adoption_policy_ref', 'open_source_evaluation_manifest_ref', 'capability_gap_governance_ref'], 'required_item_refs': ['repository_ref', 'license_refs', 'maintenance_refs', 'security_refs', 'capability_gap_refs', 'competitor_comparison_refs', 'validation_receipt_refs', 'artifact_refs', 'owner_refs', 'adoption_decision_refs'], 'ready_actions': ['share_open_source_candidate_evaluation_readiness_with_mainline'], 'empty_actions': ['provide_codex_open_source_candidate_evaluation_inventory'], 'review_actions': ['review_open_source_candidate_maintenance_risk', 'decide_adoption_guardrail'], 'prefix': 'codex_open_source_candidate_evaluation_readiness', 'failed_code': 'codex_open_source_candidate_evaluation_license_blocked', 'packet_missing_code': 'codex_open_source_candidate_evaluation_packet_missing_evidence', 'live_code': 'codex_open_source_candidate_evaluation_live_operation_blocked', 'summary_ref_field': 'capability_gap_refs', 'summary_ref_count_key': 'capability_gap_ref_count'}


def summarize_codex_open_source_candidate_evaluation(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_open_source_candidate_evaluation_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
