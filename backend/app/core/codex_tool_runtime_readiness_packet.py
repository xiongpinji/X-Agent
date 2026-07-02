from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_tool_runtime_readiness_packet', 'collection_key': 'mcp_tools', 'required_item_refs': ['manifest_ref', 'source_ref', 'version_ref', 'schema_ref'], 'ready_actions': ['share_codex_tool_runtime_readiness_with_mainline'], 'empty_actions': ['provide_codex_tool_runtime_inventory'], 'blocked_actions': ['block_unsafe_runtime_surfaces', 'review_permission_and_sandbox_policy'], 'prefix': 'codex_tool_runtime_readiness', 'failed_code': 'codex_tool_runtime_high_risk_without_manual_approval', 'missing_code': 'codex_tool_runtime_missing_evidence'}


def summarize_codex_tool_runtime_component(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_tool_runtime_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
