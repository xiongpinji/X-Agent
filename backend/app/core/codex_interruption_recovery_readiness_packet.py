from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_interruption_recovery_readiness_packet', 'collection_key': 'recoveries', 'required_packet_refs': ['interruption_policy', 'recovery_policy', 'resume_policy', 'partial_progress_policy', 'interruption_recovery_manifest_ref', 'failure_recovery_governance_ref'], 'packet_missing_refs': ['interruption_policy_ref', 'recovery_policy_ref', 'resume_policy_ref', 'partial_progress_policy_ref', 'interruption_recovery_manifest_ref', 'failure_recovery_governance_ref'], 'required_item_refs': ['recovery_validation_refs', 'resumability_refs', 'partial_progress_refs', 'resume_token_refs', 'recovery_plan_refs'], 'conditional_refs': {'needs_failure_evidence': ['interruption_refs', 'failure_recovery_refs']}, 'ready_actions': ['share_interruption_recovery_readiness_with_mainline'], 'empty_actions': ['provide_codex_interruption_recovery_inventory'], 'prefix': 'codex_interruption_recovery_readiness', 'failed_code': 'codex_interruption_recovery_status_failed', 'packet_missing_code': 'codex_interruption_recovery_packet_missing_evidence', 'live_code': 'codex_interruption_recovery_live_operation_blocked', 'summary_ref_field': 'interruption_refs', 'summary_ref_count_key': 'interruption_ref_count'}


def summarize_codex_interruption_recovery(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_interruption_recovery_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
