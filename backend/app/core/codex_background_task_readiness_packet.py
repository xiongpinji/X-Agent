from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_background_task_readiness_packet', 'collection_key': 'tasks', 'required_packet_refs': ['retry_policy', 'resumability_policy', 'artifact_policy', 'queue_ref', 'handoff_policy_ref', 'notification_policy_ref'], 'packet_missing_refs': ['retry_policy_ref', 'resumability_policy_ref', 'artifact_policy_ref', 'task_queue_ref', 'handoff_policy_ref', 'notification_policy_ref'], 'required_item_refs': ['resumability_ref', 'remote_execution_ref', 'handoff_ref', 'artifact_refs', 'validation_refs', 'diff_or_pr_refs'], 'ready_actions': ['share_background_task_readiness_with_mainline'], 'empty_actions': ['provide_codex_background_task_inventory'], 'blocked_actions': ['resolve_background_task_blockers', 'refresh_background_task_readiness'], 'prefix': 'codex_background_task_readiness', 'failed_code': 'codex_background_task_terminal_failure', 'missing_code': 'codex_background_task_missing_evidence', 'packet_missing_code': 'codex_background_task_packet_missing_evidence'}


def summarize_codex_background_task(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    payload = item if isinstance(item, Mapping) else getattr(item, "__dict__", {})
    required_refs = list(CONFIG.get("required_item_refs", ()))
    if str(payload.get("task_type") or "").lower() != "cloud":
        required_refs = [ref for ref in required_refs if ref not in {"remote_execution_ref", "resumability_ref"}]
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=required_refs,
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_background_task_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
