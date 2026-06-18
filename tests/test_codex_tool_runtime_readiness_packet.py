from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_tool_runtime_readiness_packet import (
    build_codex_tool_runtime_readiness_packet,
    summarize_codex_tool_runtime_component,
)


def test_ready_packet_with_runtime_surfaces_and_evidence() -> None:
    packet = build_codex_tool_runtime_readiness_packet(
        {
            "mcp_tools": [
                {
                    "name": "github_search",
                    "status": "ready",
                    "manifest_ref": "mcp/github.json",
                    "source_ref": "official",
                    "version_ref": "2026-06-12",
                    "schema_ref": "schemas/github_search.json",
                }
            ],
            "skills": [
                {
                    "name": "build-web-apps",
                    "status": "ready",
                    "manifest_ref": "skills/build-web-apps/SKILL.md",
                    "source_ref": "openai-curated",
                    "version_ref": "c6ea566d",
                    "schema_ref": "skill_metadata",
                }
            ],
            "browser": {
                "name": "browser",
                "status": "validated",
                "approval_profile": "manual",
                "sandbox_profile": "isolated",
                "session_ref": "browser-session-1",
                "validation_refs": ["browser-ready-receipt"],
            },
            "shell": {
                "name": "shell_command",
                "status": "ready",
                "approval_profile": "manual",
                "sandbox_profile": "workspace_write",
                "validation_refs": ["pytest-shell-policy"],
            },
            "patch": {
                "name": "apply_patch",
                "status": "ready",
                "approval_profile": "ask",
                "sandbox_profile": "workspace_write",
                "validation_refs": ["patch-contract-test"],
            },
        }
    )

    assert packet["kind"] == "codex_tool_runtime_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["component_count"] == 5
    assert packet["summary"]["ready_count"] == 5
    assert packet["summary"]["by_component_type"]["mcp"] == 1
    assert packet["next_actions"] == ["share_codex_tool_runtime_readiness_with_mainline"]


def test_high_risk_shell_without_manual_approval_or_sandbox_is_blocked() -> None:
    packet = build_codex_tool_runtime_readiness_packet(
        {
            "shell": {
                "name": "shell_command",
                "status": "ready",
                "approval_profile": "auto",
                "risk_level": "critical",
            }
        }
    )

    assert packet["status"] == "blocked"
    assert packet["components"][0]["readiness_state"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_tool_runtime_high_risk_without_manual_approval"
    assert "high_risk_component_without_sandbox" in packet["components"][0]["blockers"]
    assert packet["next_actions"] == [
        "block_unsafe_runtime_surfaces",
        "review_permission_and_sandbox_policy",
    ]


def test_plugin_or_skill_missing_manifest_source_version_schema_needs_review() -> None:
    packet = build_codex_tool_runtime_readiness_packet(
        {
            "plugins": [{"name": "sentry", "status": "ready", "source_ref": "installed"}],
            "skills": [{"name": "understand-anything", "status": "ready"}],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["summary"]["missing_ref_count"] == 7
    assert packet["findings"][0]["code"] == "codex_tool_runtime_missing_evidence"
    assert "manifest_ref" in packet["components"][0]["missing_refs"]
    assert "version_ref" in packet["components"][1]["missing_refs"]


def test_browser_and_computer_use_missing_visual_evidence_needs_review() -> None:
    packet = build_codex_tool_runtime_readiness_packet(
        {
            "browser": {
                "name": "browser",
                "status": "ready",
                "approval_profile": "manual",
                "sandbox_profile": "isolated",
            },
            "computer_use": {
                "name": "computer_use",
                "status": "ready",
                "approval_profile": "manual",
                "sandbox_profile": "isolated",
            },
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["summary"]["needs_review_count"] == 2
    assert packet["components"][0]["missing_refs"] == ["session_or_visual_evidence_ref"]
    assert packet["components"][1]["missing_refs"] == ["session_or_visual_evidence_ref"]


def test_empty_payload_requests_runtime_inventory() -> None:
    packet = build_codex_tool_runtime_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["summary"]["component_count"] == 0
    assert packet["next_actions"] == ["provide_codex_tool_runtime_inventory"]


def test_dataclass_like_component_is_accepted_by_summarizer() -> None:
    @dataclass
    class RuntimeComponent:
        name: str
        component_type: str
        status: str
        approval_profile: str
        sandbox_profile: str
        validation_refs: list[str]

    item = summarize_codex_tool_runtime_component(
        RuntimeComponent(
            "apply_patch",
            "patch",
            "ready",
            "manual",
            "workspace_write",
            ["patch-receipt"],
        )
    )

    assert item.name == "apply_patch"
    assert item.component_type == "patch"
    assert item.readiness_state == "ready"
    assert item.validation_refs == ("patch-receipt",)
