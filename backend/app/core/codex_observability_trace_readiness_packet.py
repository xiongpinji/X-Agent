from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_observability_trace_readiness_packet', 'collection_key': 'traces', 'required_packet_refs': ['trace_schema_policy', 'redaction_policy', 'retention_policy', 'export_policy', 'trace_manifest_ref', 'audit_access_policy'], 'packet_missing_refs': ['trace_schema_policy_ref', 'redaction_policy_ref', 'retention_policy_ref', 'export_policy_ref', 'trace_manifest_ref', 'audit_access_policy_ref'], 'required_item_refs': ['error_taxonomy_refs', 'permission_prompt_refs', 'sandbox_event_refs'], 'ready_actions': ['share_observability_trace_readiness_with_mainline'], 'empty_actions': ['provide_codex_observability_trace_inventory'], 'blocked_actions': ['resolve_observability_trace_blockers', 'refresh_observability_trace_readiness'], 'prefix': 'codex_observability_trace_readiness', 'failed_code': 'codex_observability_trace_status_failed', 'packet_missing_code': 'codex_observability_trace_packet_missing_evidence', 'live_code': 'codex_observability_live_export_blocked', 'summary_ref_field': 'tool_call_trace_refs', 'summary_ref_count_key': 'tool_call_trace_ref_count'}


def summarize_codex_observability_trace(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_observability_trace_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
