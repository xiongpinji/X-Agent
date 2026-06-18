from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_long_running_task_supervision_readiness_packet', 'collection_key': 'tasks', 'required_packet_refs': ['heartbeat_policy', 'progress_policy', 'timeout_policy', 'escalation_policy', 'task_supervision_manifest_ref', 'durable_task_governance_ref'], 'packet_missing_refs': ['heartbeat_policy_ref', 'progress_policy_ref', 'timeout_policy_ref', 'escalation_policy_ref', 'task_supervision_manifest_ref', 'durable_task_governance_ref'], 'required_item_refs': ['escalation_refs', 'heartbeat_refs', 'progress_refs', 'supervision_refs', 'timeout_refs', 'checkpoint_refs', 'validation_receipt_refs', 'artifact_refs'], 'ready_actions': ['share_long_running_task_supervision_readiness_with_mainline'], 'empty_actions': ['provide_codex_long_running_task_supervision_inventory'], 'prefix': 'codex_long_running_task_supervision_readiness', 'failed_code': 'codex_long_running_task_supervision_status_failed', 'packet_missing_code': 'codex_long_running_task_supervision_packet_missing_evidence', 'live_code': 'codex_long_running_task_supervision_live_operation_blocked', 'summary_ref_field': 'heartbeat_refs', 'summary_ref_count_key': 'heartbeat_ref_count'}


def summarize_codex_long_running_task_supervision(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_long_running_task_supervision_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
