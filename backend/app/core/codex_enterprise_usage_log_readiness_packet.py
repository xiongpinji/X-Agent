from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_enterprise_usage_log_readiness_packet', 'collection_key': 'usage_logs', 'required_packet_refs': ['usage_log_policy', 'admin_access_policy', 'privacy_policy', 'retention_policy', 'usage_manifest_ref', 'audit_export_policy'], 'packet_missing_refs': ['usage_log_policy_ref', 'admin_access_policy_ref', 'privacy_policy_ref', 'retention_policy_ref', 'usage_manifest_ref', 'audit_export_policy_ref'], 'required_item_refs': ['incident_escalation_refs', 'privacy_redaction_refs', 'admin_access_policy_refs', 'billing_quota_refs'], 'ready_actions': ['share_enterprise_usage_log_readiness_with_mainline'], 'empty_actions': ['provide_codex_enterprise_usage_log_inventory'], 'blocked_actions': ['resolve_enterprise_usage_log_blockers', 'refresh_enterprise_usage_log_readiness'], 'prefix': 'codex_enterprise_usage_log_readiness', 'failed_code': 'codex_enterprise_usage_log_status_failed', 'packet_missing_code': 'codex_enterprise_usage_log_packet_missing_evidence', 'live_code': 'codex_enterprise_usage_log_live_admin_mutation_blocked', 'summary_ref_field': 'billing_quota_refs', 'summary_ref_count_key': 'billing_quota_ref_count'}


def summarize_codex_enterprise_usage_log(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_enterprise_usage_log_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
