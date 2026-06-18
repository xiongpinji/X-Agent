from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_permission_sandbox_readiness_packet', 'collection_key': 'policies', 'required_item_refs': ['allowed_write_roots', 'blocked_commands', 'audit_refs'], 'ready_actions': ['share_permission_sandbox_readiness_with_mainline'], 'empty_actions': ['provide_codex_permission_sandbox_policy'], 'blocked_actions': ['tighten_approval_and_sandbox_policy', 'remove_dangerous_runtime_bypass'], 'review_actions': ['attach_permission_sandbox_evidence', 'refresh_permission_sandbox_readiness'], 'prefix': 'codex_permission_sandbox_readiness', 'failed_code': 'codex_permission_sandbox_autonomous_approval', 'missing_code': 'codex_permission_sandbox_missing_evidence'}


def summarize_codex_permission_sandbox_policy(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_permission_sandbox_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
