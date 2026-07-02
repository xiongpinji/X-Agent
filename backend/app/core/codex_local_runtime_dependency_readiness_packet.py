from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_local_runtime_dependency_readiness_packet', 'collection_key': 'runtimes', 'required_packet_refs': ['runtime_policy', 'dependency_policy', 'lockfile_policy', 'environment_template_policy', 'runtime_dependency_manifest_ref', 'reproducibility_governance_ref'], 'packet_missing_refs': ['runtime_policy_ref', 'dependency_policy_ref', 'lockfile_policy_ref', 'environment_template_policy_ref', 'runtime_dependency_manifest_ref', 'reproducibility_governance_ref'], 'required_item_refs': ['runtime_version_refs', 'package_manager_refs', 'lockfile_refs', 'environment_template_refs', 'install_verification_refs', 'validation_receipt_refs'], 'conditional_refs': {'needs_failure_evidence': ['version_mismatch_refs']}, 'ready_actions': ['share_local_runtime_dependency_readiness_with_mainline'], 'empty_actions': ['provide_codex_local_runtime_dependency_inventory'], 'prefix': 'codex_local_runtime_dependency_readiness', 'failed_code': 'codex_local_runtime_dependency_status_failed', 'packet_missing_code': 'codex_local_runtime_dependency_packet_missing_evidence', 'live_code': 'codex_local_runtime_dependency_live_operation_blocked'}


def summarize_codex_local_runtime_dependency(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_local_runtime_dependency_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
