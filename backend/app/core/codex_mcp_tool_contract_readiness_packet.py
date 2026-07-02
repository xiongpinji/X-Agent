from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_mcp_tool_contract_readiness_packet', 'collection_key': 'tools', 'required_packet_refs': ['tool_contract_policy', 'mcp_server_policy', 'permission_policy', 'schema_policy', 'tool_manifest_ref', 'tool_contract_matrix_ref'], 'packet_missing_refs': ['tool_contract_policy_ref', 'mcp_server_policy_ref', 'permission_policy_ref', 'schema_policy_ref', 'tool_manifest_ref', 'tool_contract_matrix_ref'], 'required_item_refs': ['tool_schema_refs', 'tool_permission_refs', 'argument_schema_refs', 'result_schema_refs', 'discovery_refs', 'validation_receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['failure_taxonomy_refs']}, 'ready_actions': ['share_mcp_tool_contract_readiness_with_mainline'], 'empty_actions': ['provide_codex_mcp_tool_contract_inventory'], 'blocked_actions': ['resolve_mcp_tool_contract_blockers', 'refresh_mcp_tool_contract_readiness'], 'prefix': 'codex_mcp_tool_contract_readiness', 'failed_code': 'codex_mcp_tool_contract_status_failed', 'packet_missing_code': 'codex_mcp_tool_contract_packet_missing_evidence', 'live_code': 'codex_mcp_tool_contract_live_mutation_blocked', 'summary_ref_field': 'argument_schema_refs', 'summary_ref_count_key': 'argument_schema_ref_count'}


def summarize_codex_mcp_tool_contract(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_mcp_tool_contract_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
