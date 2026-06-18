from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_session_budget_guard_readiness_packet', 'collection_key': 'budgets', 'required_packet_refs': ['token_budget_policy', 'elapsed_time_policy', 'retry_budget_policy', 'tool_call_budget_policy', 'session_budget_manifest_ref', 'bounded_execution_governance_ref'], 'packet_missing_refs': ['token_budget_policy_ref', 'elapsed_time_policy_ref', 'retry_budget_policy_ref', 'tool_call_budget_policy_ref', 'session_budget_manifest_ref', 'bounded_execution_governance_ref'], 'required_item_refs': ['token_budget_refs', 'elapsed_time_refs', 'retry_budget_refs', 'tool_call_budget_refs', 'context_compaction_threshold_refs'], 'conditional_refs': {'needs_failure_evidence': ['interruption_refs', 'cancellation_policy_refs']}, 'ready_actions': ['share_session_budget_guard_readiness_with_mainline'], 'empty_actions': ['provide_codex_session_budget_guard_inventory'], 'prefix': 'codex_session_budget_guard_readiness', 'failed_code': 'codex_session_budget_guard_status_failed', 'packet_missing_code': 'codex_session_budget_guard_packet_missing_evidence', 'live_code': 'codex_session_budget_guard_live_operation_blocked', 'summary_ref_field': 'tool_call_budget_refs', 'summary_ref_count_key': 'tool_call_budget_ref_count'}


def summarize_codex_session_budget_guard(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_session_budget_guard_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
