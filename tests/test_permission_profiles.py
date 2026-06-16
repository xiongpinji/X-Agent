import pytest

from backend.app.core.permission_profiles import (
    PermissionAction,
    PermissionDecision,
    PermissionProfile,
    evaluate_permission,
    is_permission_allowed,
)


def test_permission_profile_allows_declared_read_target() -> None:
    profile = PermissionProfile(
        profile_id="read-only",
        allow={"read": ["backend/app/**/*.py"]},
    )

    decision = evaluate_permission(
        profile,
        PermissionAction.READ,
        "backend\\app\\core\\security.py",
    )

    assert decision.allowed is True
    assert decision.effect == "allow"
    assert decision.matched_pattern == "backend/app/**/*.py"
    assert decision.target == "backend/app/core/security.py"


def test_permission_profile_denies_override_broad_allow() -> None:
    profile = PermissionProfile(
        profile_id="workspace-writer",
        allow={"write": ["*"]},
        deny={"write": [".env", "data/secrets/*"]},
    )

    blocked = evaluate_permission(profile, "write", "data/secrets/api-key.txt")
    allowed = evaluate_permission(profile, "write", "backend/app/core/policy.py")

    assert blocked.allowed is False
    assert blocked.effect == "deny"
    assert blocked.matched_pattern == "data/secrets/*"
    assert allowed.allowed is True


def test_permission_profile_defaults_to_deny_without_allow_match() -> None:
    profile = PermissionProfile(profile_id="empty")

    decision = evaluate_permission(profile, "tool", "shell_exec")

    assert decision == PermissionDecision(
        allowed=False,
        action=PermissionAction.TOOL,
        target="shell_exec",
        profile_id="empty",
        reason="tool is not allowed by profile empty.",
        effect="none",
        matched_pattern=None,
    )


def test_permission_profile_keeps_read_write_tool_network_independent() -> None:
    profile = PermissionProfile(
        profile_id="mixed",
        allow={
            "read": ["docs/*"],
            "write": ["scratch/*"],
            "tool": ["python"],
            "network": ["api.example.com"],
        },
    )

    assert is_permission_allowed(profile, "read", "docs/runbook.md") is True
    assert is_permission_allowed(profile, "write", "docs/runbook.md") is False
    assert is_permission_allowed(profile, "tool", "python") is True
    assert is_permission_allowed(profile, "tool", "powershell") is False
    assert is_permission_allowed(profile, "network", "api.example.com") is True
    assert is_permission_allowed(profile, "network", "admin.example.com") is False


def test_permission_profile_supports_declarative_dict_loading() -> None:
    profile = PermissionProfile.model_validate(
        {
            "profile_id": "agent-safe",
            "description": "Core policy profile",
            "allow": {
                "read": ["backend/app/core/*"],
                "tool": ["pytest", "ruff"],
                "network": ["*.internal.example"],
            },
            "deny": {
                "read": ["backend/app/core/*.secret"],
                "network": ["prod.internal.example"],
            },
        }
    )

    assert evaluate_permission(profile, "read", "backend/app/core/contracts.py").allowed is True
    assert evaluate_permission(profile, "read", "backend/app/core/token.secret").allowed is False
    assert evaluate_permission(profile, "tool", "pytest").allowed is True
    assert evaluate_permission(profile, "network", "dev.internal.example").allowed is True
    assert evaluate_permission(profile, "network", "prod.internal.example").allowed is False


def test_permission_profile_rejects_unknown_action() -> None:
    profile = PermissionProfile(profile_id="strict")

    with pytest.raises(ValueError):
        evaluate_permission(profile, "delete", "backend/app/core/security.py")
