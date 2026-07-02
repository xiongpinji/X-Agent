from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_environment_repro_readiness_packet', 'collection_key': 'reproducibility', 'required_packet_refs': ['environment_policy', 'sandbox_policy', 'redaction_policy', 'reproducibility_policy', 'environment_manifest_ref', 'validation_matrix_ref'], 'packet_missing_refs': ['environment_policy_ref', 'sandbox_policy_ref', 'redaction_policy_ref', 'reproducibility_policy_ref', 'environment_manifest_ref', 'validation_matrix_ref'], 'required_item_refs': ['workspace_snapshot_refs', 'dependency_lock_refs', 'runtime_version_refs', 'env_var_redaction_refs'], 'conditional_refs': {'needs_failure_evidence': ['failure_reproduction_refs']}, 'ready_actions': ['share_environment_repro_readiness_with_mainline'], 'empty_actions': ['provide_codex_environment_repro_inventory'], 'blocked_actions': ['resolve_environment_repro_blockers', 'refresh_environment_repro_readiness'], 'prefix': 'codex_environment_repro_readiness', 'failed_code': 'codex_environment_repro_status_failed', 'packet_missing_code': 'codex_environment_repro_packet_missing_evidence', 'live_code': 'codex_environment_repro_live_mutation_blocked', 'summary_ref_field': 'dependency_lock_refs', 'summary_ref_count_key': 'dependency_lock_ref_count'}


def summarize_codex_environment_repro(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_environment_repro_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
