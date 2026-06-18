from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_planning_goal_readiness_packet', 'collection_key': 'goals', 'required_packet_refs': ['planning_policy', 'goal_policy', 'approval_policy', 'completion_policy', 'planning_manifest_ref', 'goal_matrix_ref'], 'packet_missing_refs': ['planning_policy_ref', 'goal_policy_ref', 'approval_policy_ref', 'completion_policy_ref', 'planning_manifest_ref', 'goal_matrix_ref'], 'required_item_refs': ['plan_refs', 'task_decomposition_refs', 'progress_checkpoint_refs', 'user_approval_refs', 'completion_criteria_refs'], 'conditional_refs': {'needs_failure_evidence': ['interruption_resume_refs']}, 'ready_actions': ['share_planning_goal_readiness_with_mainline'], 'empty_actions': ['provide_codex_planning_goal_inventory'], 'blocked_actions': ['resolve_planning_goal_blockers', 'refresh_planning_goal_readiness'], 'prefix': 'codex_planning_goal_readiness', 'failed_code': 'codex_planning_goal_status_failed', 'packet_missing_code': 'codex_planning_goal_packet_missing_evidence', 'live_code': 'codex_planning_goal_live_mutation_blocked', 'summary_ref_field': 'approval_refs', 'summary_ref_count_key': 'approval_ref_count'}


def summarize_codex_planning_goal(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_planning_goal_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
