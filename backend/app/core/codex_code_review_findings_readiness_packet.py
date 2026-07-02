from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_code_review_findings_readiness_packet', 'collection_key': 'findings', 'required_packet_refs': ['review_policy', 'severity_policy', 'evidence_policy', 'suppression_policy', 'review_findings_manifest_ref', 'review_output_governance_ref'], 'packet_missing_refs': ['review_policy_ref', 'severity_policy_ref', 'evidence_policy_ref', 'suppression_policy_ref', 'review_findings_manifest_ref', 'review_output_governance_ref'], 'required_item_refs': ['file_line_refs', 'suggested_fix_refs', 'owner_refs'], 'ready_actions': ['share_code_review_findings_readiness_with_mainline'], 'empty_actions': ['provide_codex_code_review_findings_inventory'], 'blocked_actions': ['resolve_code_review_finding_blockers', 'refresh_code_review_findings_readiness'], 'prefix': 'codex_code_review_findings_readiness', 'failed_code': 'codex_code_review_finding_status_failed', 'packet_missing_code': 'codex_code_review_findings_packet_missing_evidence', 'live_code': 'codex_code_review_findings_live_output_blocked', 'summary_ref_field': 'file_line_refs', 'summary_ref_count_key': 'file_line_ref_count'}


def summarize_codex_code_review_finding(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_code_review_findings_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
