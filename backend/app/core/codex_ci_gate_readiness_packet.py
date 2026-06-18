from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_ci_gate_readiness_packet', 'collection_key': 'gates', 'required_packet_refs': ['required_check_policy', 'workflow_policy', 'artifact_policy', 'review_posting_policy', 'ci_manifest_ref'], 'packet_missing_refs': ['required_check_policy_ref', 'workflow_policy_ref', 'artifact_policy_ref', 'review_posting_policy_ref', 'ci_manifest_ref'], 'required_item_refs': ['workflow_refs', 'check_run_refs', 'status_contexts', 'artifact_refs', 'review_result_posting_refs'], 'conditional_refs': {'needs_failure_evidence': ['failure_summaries', 'retry_or_rerun_refs']}, 'ready_actions': ['share_ci_gate_readiness_with_mainline'], 'empty_actions': ['provide_codex_ci_gate_inventory'], 'prefix': 'codex_ci_gate_readiness', 'failed_code': 'codex_ci_gate_check_failed', 'packet_missing_code': 'codex_ci_gate_packet_missing_evidence', 'summary_ref_field': 'review_posting_refs', 'summary_ref_count_key': 'review_posting_ref_count', 'open_warning_code': 'ci_gate_still_running'}


def summarize_codex_ci_gate(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    result = summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
        open_warning_code=CONFIG.get("open_warning_code"),
    )
    data = getattr(result, "payload", None) or getattr(result, "data", {})
    if "running" in [str(state).lower() for state in data.get("check_states", [])]:
        return CodexReadinessItem(
            payload=dict(data),
            readiness_state="needs_review",
            missing_refs=result.missing_refs,
            warnings=tuple(dict.fromkeys((*result.warnings, "ci_check_state_needs_review"))),
            blockers=result.blockers,
        )
    return result


def build_codex_ci_gate_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
