from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_terminal_command_readiness_packet', 'collection_key': 'commands', 'required_packet_refs': ['command_policy', 'permission_policy', 'sandbox_policy', 'redaction_policy', 'command_manifest_ref', 'execution_governance_ref'], 'packet_missing_refs': ['command_policy_ref', 'permission_policy_ref', 'sandbox_policy_ref', 'redaction_policy_ref', 'command_manifest_ref', 'execution_governance_ref'], 'required_item_refs': ['permission_refs', 'sandbox_refs', 'timeout_refs', 'stdout_transcript_refs', 'exit_code_refs', 'redaction_refs'], 'conditional_refs': {'needs_failure_evidence': ['stderr_transcript_refs']}, 'ready_actions': ['share_terminal_command_readiness_with_mainline'], 'empty_actions': ['provide_codex_terminal_command_inventory'], 'blocked_actions': ['resolve_terminal_command_blockers', 'refresh_terminal_command_readiness'], 'prefix': 'codex_terminal_command_readiness', 'failed_code': 'codex_terminal_command_status_failed', 'packet_missing_code': 'codex_terminal_command_packet_missing_evidence', 'live_code': 'codex_terminal_command_live_execution_blocked', 'summary_ref_field': 'exit_code_refs', 'summary_ref_count_key': 'exit_code_ref_count'}


def summarize_codex_terminal_command(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_terminal_command_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
