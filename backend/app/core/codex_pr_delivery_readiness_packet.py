from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_pr_delivery_readiness_packet', 'collection_key': 'deliveries', 'required_packet_refs': ['delivery_policy', 'review_policy', 'ci_policy', 'redaction_policy', 'reviewer_policy_ref', 'delivery_manifest_ref'], 'packet_missing_refs': ['delivery_policy_ref', 'review_policy_ref', 'ci_policy_ref', 'redaction_policy_ref', 'reviewer_policy_ref', 'delivery_manifest_ref'], 'required_item_refs': ['reviewer_handoff_refs'], 'ready_actions': ['share_pr_delivery_readiness_with_mainline'], 'empty_actions': ['provide_codex_pr_delivery_inventory'], 'blocked_actions': ['resolve_pr_delivery_blockers', 'refresh_pr_delivery_readiness'], 'prefix': 'codex_pr_delivery_readiness', 'packet_missing_code': 'codex_pr_delivery_packet_missing_evidence', 'live_code': 'codex_pr_delivery_non_dry_run_blocked', 'summary_ref_field': 'pr_refs', 'summary_ref_count_key': 'pr_ref_count'}


def summarize_codex_pr_delivery(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_pr_delivery_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
