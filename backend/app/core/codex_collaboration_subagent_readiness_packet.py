from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_collaboration_subagent_readiness_packet', 'collection_key': 'collaborations', 'required_packet_refs': ['collaboration_policy', 'assignment_policy', 'handoff_policy', 'aggregation_policy', 'collaboration_manifest_ref', 'coordination_governance_ref'], 'packet_missing_refs': ['collaboration_policy_ref', 'assignment_policy_ref', 'handoff_policy_ref', 'aggregation_policy_ref', 'collaboration_manifest_ref', 'coordination_governance_ref'], 'required_item_refs': ['timeout_refs', 'aggregation_refs', 'assignment_refs', 'worker_thread_refs', 'handoff_refs', 'partial_result_refs', 'validation_receipt_refs'], 'ready_actions': ['share_collaboration_subagent_readiness_with_mainline'], 'empty_actions': ['provide_codex_collaboration_subagent_inventory'], 'blocked_actions': ['resolve_collaboration_subagent_blockers', 'refresh_collaboration_subagent_readiness'], 'prefix': 'codex_collaboration_subagent_readiness', 'failed_code': 'codex_collaboration_subagent_status_failed', 'packet_missing_code': 'codex_collaboration_subagent_packet_missing_evidence', 'live_code': 'codex_collaboration_subagent_live_execution_blocked', 'summary_ref_field': 'aggregation_refs', 'summary_ref_count_key': 'aggregation_ref_count'}


def summarize_codex_collaboration_subagent(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_collaboration_subagent_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
