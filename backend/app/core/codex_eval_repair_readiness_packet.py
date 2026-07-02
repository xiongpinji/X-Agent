from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_eval_repair_readiness_packet', 'collection_key': 'repairs', 'required_packet_refs': ['eval_policy', 'repair_policy', 'validation_policy', 'rollback_policy', 'eval_manifest_ref'], 'packet_missing_refs': ['eval_policy_ref', 'repair_policy_ref', 'validation_policy_ref', 'rollback_policy_ref', 'eval_manifest_ref'], 'required_item_refs': ['patch_attempt_refs', 'validation_rerun_refs', 'closure_receipts'], 'conditional_refs': {'needs_failure_evidence': ['rollback_refs']}, 'ready_actions': ['share_eval_repair_readiness_with_mainline'], 'empty_actions': ['provide_codex_eval_repair_inventory'], 'blocked_actions': ['resolve_eval_repair_blockers', 'refresh_eval_repair_readiness'], 'prefix': 'codex_eval_repair_readiness', 'failed_code': 'codex_eval_repair_state_blocked', 'missing_code': 'codex_eval_repair_missing_evidence', 'packet_missing_code': 'codex_eval_repair_packet_missing_evidence'}


def summarize_codex_eval_repair(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_eval_repair_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
