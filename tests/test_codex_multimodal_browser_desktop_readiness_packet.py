from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_multimodal_browser_desktop_readiness_packet import (
    build_codex_multimodal_browser_desktop_readiness_packet,
    summarize_codex_multimodal_browser_desktop,
)


PACKET_POLICIES = {
    "browser_policy": "browser-policy",
    "desktop_policy": "desktop-policy",
    "visual_observation_policy": "visual-observation-policy",
    "gesture_policy": "gesture-policy",
    "interaction_manifest_ref": "interaction-manifest",
    "multimodal_governance_ref": "multimodal-governance",
}


def test_ready_multimodal_browser_desktop_interaction_has_visual_evidence() -> None:
    packet = build_codex_multimodal_browser_desktop_readiness_packet(
        {
            **PACKET_POLICIES,
            "interactions": [
                {
                    "interaction_id": "visual-1",
                    "status": "observed",
                    "interaction_ref": "interaction",
                    "focus": ["browser", "desktop", "visual"],
                    "browser_session_refs": ["browser-session"],
                    "screenshot_refs": ["screenshot"],
                    "dom_snapshot_refs": ["dom"],
                    "ui_snapshot_refs": ["ui"],
                    "visual_observation_refs": ["visual"],
                    "user_gesture_refs": ["gesture"],
                    "desktop_target_refs": ["desktop"],
                    "permission_refs": ["permission"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_multimodal_browser_desktop_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["interaction_count"] == 1
    assert packet["summary"]["screenshot_ref_count"] == 1
    assert packet["next_actions"] == ["share_multimodal_browser_desktop_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_multimodal_browser_desktop_readiness_packet(
        {
            "interactions": [
                {
                    "interaction_id": "visual-2",
                    "status": "recorded",
                    "interaction_ref": "interaction",
                    "focus": ["browser"],
                    "browser_session_refs": ["browser-session"],
                    "screenshot_refs": ["screenshot"],
                    "dom_snapshot_refs": ["dom"],
                    "user_gesture_refs": ["gesture"],
                    "permission_refs": ["permission"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_multimodal_browser_desktop_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "browser_policy_ref",
        "desktop_policy_ref",
        "visual_observation_policy_ref",
        "gesture_policy_ref",
        "interaction_manifest_ref",
        "multimodal_governance_ref",
    ]


def test_failed_or_timed_out_interaction_requires_observation_refs_and_blocks() -> None:
    packet = build_codex_multimodal_browser_desktop_readiness_packet(
        {
            **PACKET_POLICIES,
            "interactions": [
                {
                    "interaction_id": "visual-3",
                    "status": "timed-out",
                    "interaction_ref": "interaction",
                    "focus": ["browser"],
                    "browser_session_refs": ["browser-session"],
                    "dom_snapshot_refs": ["dom"],
                    "user_gesture_refs": ["gesture"],
                    "permission_refs": ["permission"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    interaction = packet["interactions"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_multimodal_browser_desktop_status_failed"
    assert "screenshot_refs" in interaction["missing_refs"]
    assert packet["next_actions"] == [
        "resolve_multimodal_browser_desktop_blockers",
        "refresh_multimodal_browser_desktop_readiness",
    ]


def test_browser_focused_interaction_requires_session_dom_screenshot_refs() -> None:
    interaction = summarize_codex_multimodal_browser_desktop(
        {
            "interaction_id": "visual-4",
            "status": "recorded",
            "interaction_ref": "interaction",
            "focus": ["browser"],
            "user_gesture_refs": ["gesture"],
            "permission_refs": ["permission"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert interaction.readiness_state == "needs_review"
    assert "browser_session_refs" in interaction.missing_refs
    assert "dom_snapshot_refs" in interaction.missing_refs
    assert "screenshot_refs" in interaction.missing_refs


def test_visual_and_desktop_evidence_require_ui_desktop_and_visual_refs() -> None:
    interaction = summarize_codex_multimodal_browser_desktop(
        {
            "interaction_id": "visual-5",
            "status": "recorded",
            "interaction_ref": "interaction",
            "focus": ["desktop", "visual"],
            "screenshot_refs": ["screenshot"],
            "user_gesture_refs": ["gesture"],
            "permission_refs": ["permission"],
            "validation_receipt_refs": ["validation"],
            "artifact_refs": ["artifact"],
        }
    )

    assert interaction.readiness_state == "needs_review"
    assert "desktop_target_refs" in interaction.missing_refs
    assert "ui_snapshot_refs" in interaction.missing_refs
    assert "visual_observation_refs" in interaction.missing_refs


def test_live_browser_launch_or_desktop_action_attempt_blocks_candidate() -> None:
    packet = build_codex_multimodal_browser_desktop_readiness_packet(
        {
            **PACKET_POLICIES,
            "interactions": [
                {
                    "interaction_id": "visual-6",
                    "status": "recorded",
                    "interaction_ref": "interaction",
                    "focus": ["desktop"],
                    "screenshot_refs": ["screenshot"],
                    "ui_snapshot_refs": ["ui"],
                    "user_gesture_refs": ["gesture"],
                    "desktop_target_refs": ["desktop"],
                    "permission_refs": ["permission"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "desktop_automation_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_multimodal_browser_desktop_live_execution_blocked"
    assert "live_browser_desktop_execution_attempted" in packet["interactions"][0]["blockers"]


def test_empty_payload_requests_multimodal_browser_desktop_inventory() -> None:
    packet = build_codex_multimodal_browser_desktop_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_multimodal_browser_desktop_inventory"]


def test_dataclass_like_interaction_is_accepted_by_summarizer() -> None:
    @dataclass
    class Interaction:
        interaction_id: str
        status: str
        interaction_ref: str
        focus: list[str]
        browser_session_refs: list[str]
        screenshot_refs: list[str]
        dom_snapshot_refs: list[str]
        ui_snapshot_refs: list[str]
        visual_observation_refs: list[str]
        user_gesture_refs: list[str]
        desktop_target_refs: list[str]
        permission_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    interaction = summarize_codex_multimodal_browser_desktop(
        Interaction(
            "visual-7",
            "passed",
            "interaction",
            ["browser", "desktop", "visual"],
            ["browser-session"],
            ["screenshot"],
            ["dom"],
            ["ui"],
            ["visual"],
            ["gesture"],
            ["desktop"],
            ["permission"],
            ["validation"],
            ["artifact"],
        )
    )

    assert interaction.interaction_id == "visual-7"
    assert interaction.status == "passed"
    assert interaction.readiness_state == "ready"
