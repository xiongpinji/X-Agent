from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_model_router_readiness_packet', 'collection_key': 'routes', 'required_packet_refs': ['routing_policy', 'fallback_policy', 'cost_policy', 'safety_policy', 'model_manifest_ref', 'provider_matrix_ref'], 'packet_missing_refs': ['routing_policy_ref', 'fallback_policy_ref', 'cost_policy_ref', 'safety_policy_ref', 'model_manifest_ref', 'provider_matrix_ref'], 'required_item_refs': ['reasoning_profile', 'reasoning_profile_refs', 'fallback_policy_refs', 'context_window_refs', 'tool_call_compatibility_refs'], 'ready_actions': ['share_model_router_readiness_with_mainline'], 'empty_actions': ['provide_codex_model_router_inventory'], 'blocked_actions': ['resolve_model_router_blockers', 'refresh_model_router_readiness'], 'prefix': 'codex_model_router_readiness', 'failed_code': 'codex_model_router_status_failed', 'packet_missing_code': 'codex_model_router_packet_missing_evidence', 'live_code': 'codex_model_router_live_call_blocked', 'summary_ref_field': 'tool_call_compatibility_refs', 'summary_ref_count_key': 'tool_call_compatibility_ref_count'}


def summarize_codex_model_router(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_model_router_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
