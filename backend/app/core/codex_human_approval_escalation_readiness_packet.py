from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_human_approval_escalation_readiness_packet', 'collection_key': 'approvals', 'required_packet_refs': ['approval_policy', 'escalation_policy', 'timeout_policy', 'decision_policy', 'approval_manifest_ref', 'approval_governance_ref'], 'packet_missing_refs': ['approval_policy_ref', 'escalation_policy_ref', 'timeout_policy_ref', 'decision_policy_ref', 'approval_manifest_ref', 'approval_governance_ref'], 'required_item_refs': ['escalation_refs', 'decision_receipt_refs', 'denial_refs'], 'ready_actions': ['share_human_approval_readiness_with_mainline'], 'empty_actions': ['provide_codex_human_approval_inventory'], 'blocked_actions': ['resolve_human_approval_blockers', 'refresh_human_approval_readiness'], 'prefix': 'codex_human_approval_escalation_readiness', 'failed_code': 'codex_human_approval_status_failed', 'packet_missing_code': 'codex_human_approval_packet_missing_evidence', 'live_code': 'codex_human_approval_live_dispatch_blocked', 'summary_ref_field': 'decision_receipt_refs', 'summary_ref_count_key': 'decision_receipt_ref_count'}


def summarize_codex_human_approval_escalation(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_human_approval_escalation_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
