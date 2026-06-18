from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_task_progress_event_timeline_readiness_packet', 'collection_key': 'timelines', 'required_packet_refs': ['timeline_policy', 'progress_event_policy', 'phase_transition_policy', 'budget_policy', 'task_timeline_manifest_ref', 'task_timeline_governance_ref'], 'packet_missing_refs': ['timeline_policy_ref', 'progress_event_policy_ref', 'phase_transition_policy_ref', 'budget_policy_ref', 'task_timeline_manifest_ref', 'task_timeline_governance_ref'], 'required_item_refs': ['task_ref', 'progress_event_refs', 'phase_transition_refs', 'elapsed_time_refs', 'budget_refs', 'artifact_refs', 'owner_refs', 'tool_event_refs', 'validation_event_refs'], 'ready_actions': ['share_task_progress_event_timeline_readiness_with_mainline'], 'empty_actions': ['provide_codex_task_progress_event_timeline_inventory'], 'blocked_actions': ['resolve_task_progress_event_timeline_blockers', 'refresh_task_progress_event_timeline_readiness'], 'review_actions': ['wait_for_task_progress_event_timeline_completion', 'attach_task_timeline_receipts'], 'prefix': 'codex_task_progress_event_timeline_readiness', 'failed_code': 'codex_task_progress_event_timeline_status_failed', 'packet_missing_code': 'codex_task_progress_event_timeline_packet_missing_evidence', 'live_code': 'codex_task_progress_event_timeline_live_operation_blocked', 'summary_ref_field': 'progress_event_refs', 'summary_ref_count_key': 'progress_event_ref_count'}


def summarize_codex_task_progress_event_timeline(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_task_progress_event_timeline_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
