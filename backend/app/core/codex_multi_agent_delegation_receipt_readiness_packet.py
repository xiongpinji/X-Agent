from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_multi_agent_delegation_receipt_readiness_packet', 'collection_key': 'delegations', 'required_packet_refs': ['delegation_policy', 'scope_policy', 'handoff_policy', 'completion_policy', 'delegation_manifest_ref', 'multi_agent_governance_ref'], 'packet_missing_refs': ['delegation_policy_ref', 'scope_policy_ref', 'handoff_policy_ref', 'completion_policy_ref', 'delegation_manifest_ref', 'multi_agent_governance_ref'], 'required_item_refs': ['delegation_ref', 'source_thread_ref', 'target_thread_refs', 'scope_refs', 'handoff_refs', 'validation_receipt_refs', 'artifact_refs', 'owner_refs', 'completion_receipt_refs'], 'ready_actions': ['share_multi_agent_delegation_receipt_readiness_with_mainline'], 'empty_actions': ['provide_codex_multi_agent_delegation_receipt_inventory'], 'blocked_actions': ['resolve_multi_agent_delegation_receipt_blockers', 'refresh_multi_agent_delegation_receipt_readiness'], 'review_actions': ['wait_for_multi_agent_delegation_completion', 'attach_multi_agent_delegation_receipts'], 'prefix': 'codex_multi_agent_delegation_receipt_readiness', 'failed_code': 'codex_multi_agent_delegation_receipt_status_failed', 'packet_missing_code': 'codex_multi_agent_delegation_receipt_packet_missing_evidence', 'live_code': 'codex_multi_agent_delegation_receipt_live_operation_blocked', 'summary_ref_field': 'completion_receipt_refs', 'summary_ref_count_key': 'completion_receipt_ref_count'}


def summarize_codex_multi_agent_delegation_receipt(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_multi_agent_delegation_receipt_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
