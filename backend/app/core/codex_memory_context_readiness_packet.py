from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_memory_context_readiness_packet', 'collection_key': 'sources', 'packet_missing_refs': ['context_budget_policy', 'stale_context_policy', 'redaction_policy'], 'required_item_refs': ['redaction_refs', 'validation_refs'], 'ready_actions': ['share_memory_context_readiness_with_mainline'], 'empty_actions': ['provide_codex_memory_context_inventory'], 'packet_missing_actions': ['attach_packet_level_context_policies', 'refresh_memory_context_readiness'], 'blocked_actions': ['restore_required_context_sources', 'review_memory_context_scope'], 'prefix': 'codex_memory_context_readiness', 'failed_code': 'codex_memory_context_source_disabled', 'packet_missing_code': 'codex_memory_context_packet_missing_evidence'}


def summarize_codex_memory_context_source(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_memory_context_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
