from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secondary_integration_adoption_decision_archive_answer_brief_packet', 'collection_key': 'briefs', 'required_packet_refs': ['archive_answer_brief_policy', 'query_result_policy', 'source_citation_policy', 'owner_followup_policy', 'secondary_integration_adoption_decision_archive_answer_brief_manifest_ref', 'secondary_integration_adoption_decision_archive_answer_governance_ref'], 'packet_missing_refs': ['archive_answer_brief_policy_ref', 'query_result_policy_ref', 'source_citation_policy_ref', 'owner_followup_policy_ref', 'secondary_integration_adoption_decision_archive_answer_brief_manifest_ref', 'secondary_integration_adoption_decision_archive_answer_governance_ref'], 'required_item_refs': ['archive_query_preview_refs', 'query_result_refs', 'answer_refs', 'source_refs', 'citation_refs', 'validation_refs', 'owner_followup_refs', 'unresolved_result_refs'], 'ready_actions': ['share_codex_secondary_integration_adoption_decision_archive_answer_brief_with_mainline'], 'empty_actions': ['provide_codex_secondary_integration_adoption_decision_archive_answer_brief_inventory'], 'review_actions': ['review_archive_answer_citations', 'refresh_archive_answer_brief_packet'], 'prefix': 'codex_secondary_integration_adoption_decision_archive_answer_brief', 'failed_code': 'codex_secondary_integration_adoption_decision_archive_answer_brief_status_failed', 'missing_code': 'codex_secondary_integration_adoption_decision_archive_answer_brief_missing_evidence', 'packet_missing_code': 'codex_secondary_integration_adoption_decision_archive_answer_brief_packet_missing_evidence', 'live_code': 'codex_secondary_integration_adoption_decision_archive_answer_brief_live_operation_blocked', 'summary_ref_field': 'citation_refs', 'summary_ref_count_key': 'citation_ref_count'}


def summarize_codex_secondary_integration_adoption_decision_archive_answer_brief(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secondary_integration_adoption_decision_archive_answer_brief_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
