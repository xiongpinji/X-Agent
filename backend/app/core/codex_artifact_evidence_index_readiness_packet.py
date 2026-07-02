from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_artifact_evidence_index_readiness_packet', 'collection_key': 'artifacts', 'required_packet_refs': ['artifact_policy', 'evidence_index_policy', 'provenance_policy', 'retention_policy', 'artifact_evidence_manifest_ref', 'work_product_governance_ref'], 'packet_missing_refs': ['artifact_policy_ref', 'evidence_index_policy_ref', 'provenance_policy_ref', 'retention_policy_ref', 'artifact_evidence_manifest_ref', 'work_product_governance_ref'], 'required_item_refs': ['evidence_index_refs', 'provenance_refs', 'handoff_refs', 'source_refs', 'owner_refs', 'retention_refs'], 'conditional_refs': {'needs_failure_evidence': ['failure_handoff_refs'], 'integrity_claimed': ['integrity_refs']}, 'ready_actions': ['share_artifact_evidence_index_readiness_with_mainline'], 'empty_actions': ['provide_codex_artifact_evidence_index_inventory'], 'prefix': 'codex_artifact_evidence_index_readiness', 'failed_code': 'codex_artifact_evidence_index_status_failed', 'packet_missing_code': 'codex_artifact_evidence_index_packet_missing_evidence', 'live_code': 'codex_artifact_evidence_index_live_operation_blocked', 'summary_ref_field': 'evidence_index_refs', 'summary_ref_count_key': 'evidence_index_ref_count'}


def summarize_codex_artifact_evidence_index(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_artifact_evidence_index_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
