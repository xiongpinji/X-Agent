from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_secrets_redaction_readiness_packet', 'collection_key': 'secret_reviews', 'required_packet_refs': ['secret_scan_policy', 'redaction_policy', 'transcript_policy', 'exposure_policy', 'secrets_manifest_ref', 'sensitive_data_governance_ref'], 'packet_missing_refs': ['secret_scan_policy_ref', 'redaction_policy_ref', 'transcript_policy_ref', 'exposure_policy_ref', 'secrets_manifest_ref', 'sensitive_data_governance_ref'], 'conditional_refs': {'needs_failure_evidence': ['exposure_refs', 'owner_escalation_refs']}, 'required_item_refs': ['secret_scan_refs', 'redaction_policy_refs', 'transcript_refs', 'artifact_refs', 'validation_receipt_refs'], 'ready_actions': ['share_secrets_redaction_readiness_with_mainline'], 'empty_actions': ['provide_codex_secrets_redaction_inventory'], 'blocked_actions': ['resolve_secrets_redaction_blockers', 'refresh_secrets_redaction_readiness'], 'prefix': 'codex_secrets_redaction_readiness', 'failed_code': 'codex_secrets_redaction_status_failed', 'packet_missing_code': 'codex_secrets_redaction_packet_missing_evidence', 'summary_ref_field': 'redaction_policy_refs', 'summary_ref_count_key': 'redaction_policy_ref_count'}


def summarize_codex_secrets_redaction(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_secrets_redaction_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
