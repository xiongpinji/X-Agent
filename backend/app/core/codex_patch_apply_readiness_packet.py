from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_patch_apply_readiness_packet', 'collection_key': 'patches', 'required_packet_refs': ['patch_policy', 'apply_policy', 'conflict_policy', 'rollback_policy', 'patch_manifest_ref', 'apply_governance_ref'], 'packet_missing_refs': ['patch_policy_ref', 'apply_policy_ref', 'conflict_policy_ref', 'rollback_policy_ref', 'patch_manifest_ref', 'apply_governance_ref'], 'required_item_refs': ['preimage_refs', 'postimage_refs', 'dry_run_refs', 'backup_refs', 'validation_receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['conflict_refs', 'rollback_refs']}, 'ready_actions': ['share_patch_apply_readiness_with_mainline'], 'empty_actions': ['provide_codex_patch_apply_inventory'], 'blocked_actions': ['resolve_patch_apply_blockers', 'refresh_patch_apply_readiness'], 'prefix': 'codex_patch_apply_readiness', 'failed_code': 'codex_patch_apply_status_failed', 'packet_missing_code': 'codex_patch_apply_packet_missing_evidence', 'live_code': 'codex_patch_apply_live_mutation_blocked', 'summary_ref_field': 'dry_run_refs', 'summary_ref_count_key': 'dry_run_ref_count'}


def summarize_codex_patch_apply(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_patch_apply_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
