from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_review_comment_readiness_packet', 'collection_key': 'reviews', 'required_packet_refs': ['review_policy', 'comment_fetch_policy', 'response_policy', 'closure_policy', 'provider_auth_ref', 'feedback_manifest_ref'], 'packet_missing_refs': ['review_policy_ref', 'comment_fetch_policy_ref', 'response_policy_ref', 'closure_policy_ref', 'provider_auth_ref', 'feedback_manifest_ref'], 'required_item_refs': ['owner_assignment_refs', 'fix_validation_refs', 'reviewer_handoff_refs', 'closure_receipts'], 'ready_actions': ['share_review_comment_readiness_with_mainline'], 'empty_actions': ['provide_codex_review_comment_inventory'], 'blocked_actions': ['resolve_review_comment_blockers', 'refresh_review_comment_readiness'], 'prefix': 'codex_review_comment_readiness', 'failed_code': 'codex_review_comment_response_blocked', 'missing_code': 'codex_review_comment_missing_evidence', 'packet_missing_code': 'codex_review_comment_packet_missing_evidence'}


def summarize_codex_review_comment(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_review_comment_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
