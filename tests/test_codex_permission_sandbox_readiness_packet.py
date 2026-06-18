from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_permission_sandbox_readiness_packet import (
    build_codex_permission_sandbox_readiness_packet,
    summarize_codex_permission_sandbox_policy,
)


def test_ready_policy_matches_codex_workspace_write_on_request_shape() -> None:
    packet = build_codex_permission_sandbox_readiness_packet(
        {
            "name": "interactive-default",
            "approval_policy": "on-request",
            "sandbox_policy": "workspace-write",
            "filesystem_scope": "workspace",
            "network_scope": "limited",
            "destructive_command_policy": "manual",
            "shell_policy": "enabled",
            "patch_policy": "enabled",
            "hook_policy": "enabled",
            "operator_prompt_policy": "enabled",
            "allowed_write_roots": ["."],
            "blocked_commands": ["rm", "git reset", "drop"],
            "trusted_hook_refs": ["hooks/trust.json"],
            "audit_refs": ["docs/codex-permissions.md"],
            "validation_refs": ["tests/test_permission_policy.py"],
        }
    )

    assert packet["kind"] == "codex_permission_sandbox_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["ready_count"] == 1
    assert packet["policies"][0]["approval_policy"] == "on_request"
    assert packet["policies"][0]["sandbox_policy"] == "workspace_write"
    assert packet["next_actions"] == ["share_permission_sandbox_readiness_with_mainline"]


def test_never_approval_and_danger_sandbox_without_external_isolation_is_blocked() -> None:
    packet = build_codex_permission_sandbox_readiness_packet(
        {
            "approval_policy": "never",
            "sandbox_policy": "danger-full-access",
            "filesystem_scope": "unrestricted",
            "network_scope": "unrestricted",
            "destructive_command_policy": "allow",
            "shell_policy": "enabled",
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_permission_sandbox_autonomous_approval"
    assert "dangerous_sandbox_without_external_isolation" in packet["policies"][0]["blockers"]
    assert "unrestricted_filesystem_scope" in packet["policies"][0]["blockers"]
    assert packet["next_actions"] == [
        "tighten_approval_and_sandbox_policy",
        "remove_dangerous_runtime_bypass",
    ]


def test_workspace_write_without_write_roots_or_receipts_needs_review() -> None:
    packet = build_codex_permission_sandbox_readiness_packet(
        {
            "approval_policy": "on-request",
            "sandbox_policy": "workspace-write",
            "filesystem_scope": "workspace",
            "network_scope": "limited",
            "shell_policy": "enabled",
            "patch_policy": "enabled",
            "blocked_commands": ["rm"],
            "audit_refs": ["policy-audit"],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_permission_sandbox_missing_evidence"
    assert "allowed_write_roots" in packet["policies"][0]["missing_refs"]
    assert "shell_validation_refs" in packet["policies"][0]["missing_refs"]
    assert "patch_validation_refs" in packet["policies"][0]["missing_refs"]


def test_enabled_hooks_without_trust_refs_needs_review() -> None:
    packet = build_codex_permission_sandbox_readiness_packet(
        {
            "approval_policy": "manual",
            "sandbox_policy": "read-only",
            "filesystem_scope": "read-only",
            "network_scope": "none",
            "destructive_command_policy": "manual",
            "hook_policy": "enabled",
            "blocked_commands": ["rm"],
            "audit_refs": ["audit"],
            "validation_refs": ["validation"],
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["policies"][0]["missing_refs"] == ["trusted_hook_refs"]
    assert packet["next_actions"] == [
        "attach_permission_sandbox_evidence",
        "refresh_permission_sandbox_readiness",
    ]


def test_hook_trust_bypass_is_blocked_even_with_other_evidence() -> None:
    packet = build_codex_permission_sandbox_readiness_packet(
        {
            "approval_policy": "manual",
            "sandbox_policy": "workspace-write",
            "filesystem_scope": "workspace",
            "network_scope": "limited",
            "destructive_command_policy": "manual",
            "hook_policy": "dangerously-bypass-hook-trust",
            "allowed_write_roots": ["."],
            "blocked_commands": ["rm"],
            "trusted_hook_refs": ["hook-trust"],
            "audit_refs": ["audit"],
            "validation_refs": ["validation"],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_permission_sandbox_hook_trust_bypass"
    assert "hook_trust_bypass_enabled" in packet["policies"][0]["blockers"]


def test_empty_payload_requests_policy_input() -> None:
    packet = build_codex_permission_sandbox_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_permission_sandbox_policy"]


def test_dataclass_like_policy_is_accepted_by_summarizer() -> None:
    @dataclass
    class Policy:
        name: str
        approval_policy: str
        sandbox_policy: str
        filesystem_scope: str
        network_scope: str
        destructive_command_policy: str
        shell_policy: str
        patch_policy: str
        hook_policy: str
        operator_prompt_policy: str
        allowed_write_roots: list[str]
        blocked_commands: list[str]
        trusted_hook_refs: list[str]
        audit_refs: list[str]
        validation_refs: list[str]

    policy = summarize_codex_permission_sandbox_policy(
        Policy(
            "profile",
            "manual",
            "workspace-write",
            "workspace",
            "limited",
            "manual",
            "enabled",
            "enabled",
            "enabled",
            "enabled",
            ["."],
            ["rm"],
            ["hook-trust"],
            ["audit"],
            ["validation"],
        )
    )

    assert policy.name == "profile"
    assert policy.approval_policy == "manual"
    assert policy.sandbox_policy == "workspace_write"
    assert policy.readiness_state == "ready"
