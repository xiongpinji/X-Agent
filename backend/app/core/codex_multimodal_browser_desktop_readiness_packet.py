from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.app.core.codex_readiness_packet import (
    CodexReadinessItem,
    build_codex_readiness_packet,
    summarize_codex_readiness_item,
)

CONFIG = {'kind': 'codex_multimodal_browser_desktop_readiness_packet', 'collection_key': 'interactions', 'required_packet_refs': ['browser_policy', 'desktop_policy', 'visual_observation_policy', 'gesture_policy', 'interaction_manifest_ref', 'multimodal_governance_ref'], 'packet_missing_refs': ['browser_policy_ref', 'desktop_policy_ref', 'visual_observation_policy_ref', 'gesture_policy_ref', 'interaction_manifest_ref', 'multimodal_governance_ref'], 'required_item_refs': ['screenshot_refs', 'browser_session_refs', 'dom_snapshot_refs', 'desktop_target_refs', 'ui_snapshot_refs', 'visual_observation_refs'], 'ready_actions': ['share_multimodal_browser_desktop_readiness_with_mainline'], 'empty_actions': ['provide_codex_multimodal_browser_desktop_inventory'], 'blocked_actions': ['resolve_multimodal_browser_desktop_blockers', 'refresh_multimodal_browser_desktop_readiness'], 'prefix': 'codex_multimodal_browser_desktop_readiness', 'failed_code': 'codex_multimodal_browser_desktop_status_failed', 'packet_missing_code': 'codex_multimodal_browser_desktop_packet_missing_evidence', 'live_code': 'codex_multimodal_browser_desktop_live_execution_blocked', 'summary_ref_field': 'screenshot_refs', 'summary_ref_count_key': 'screenshot_ref_count'}


def summarize_codex_multimodal_browser_desktop(item: Mapping[str, Any] | Any) -> CodexReadinessItem:
    return summarize_codex_readiness_item(
        item,
        prefix=CONFIG["prefix"],
        required_refs=CONFIG.get("required_item_refs", ()),
        conditional_refs=CONFIG.get("conditional_refs", {}),
        failed_code=CONFIG.get("failed_code"),
        live_code=CONFIG.get("live_code"),
    )


def build_codex_multimodal_browser_desktop_readiness_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_codex_readiness_packet(payload, **CONFIG)
