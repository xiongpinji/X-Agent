from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_safety_policy_boundary_readiness_packet', 'collection_key': 'boundaries', 'required_packet_refs': ['safety_policy', 'refusal_policy', 'risky_operation_policy', 'escalation_policy', 'safety_boundary_manifest_ref', 'policy_governance_ref'], 'packet_missing_refs': ['safety_policy_ref', 'refusal_policy_ref', 'risky_operation_policy_ref', 'escalation_policy_ref', 'safety_boundary_manifest_ref', 'policy_governance_ref'], 'required_item_refs': ['risky_operation_refs', 'policy_decision_refs', 'refusal_refs', 'escalation_refs'], 'ready_actions': ['share_safety_policy_boundary_readiness_with_mainline'], 'empty_actions': ['provide_codex_safety_policy_boundary_inventory'], 'prefix': 'codex_safety_policy_boundary_readiness', 'failed_code': 'codex_safety_policy_boundary_status_failed', 'packet_missing_code': 'codex_safety_policy_boundary_packet_missing_evidence', 'live_code': 'codex_safety_policy_boundary_live_operation_blocked', 'summary_ref_field': 'policy_decision_refs', 'summary_ref_count_key': 'policy_decision_ref_count'}


def summarize_codex_safety_policy_boundary(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_safety_policy_boundary_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
