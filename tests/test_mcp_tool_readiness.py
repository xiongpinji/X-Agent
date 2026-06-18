from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.mcp_tool_readiness import (
    assess_mcp_tool_readiness,
    build_mcp_tool_readiness,
)


def test_mcp_tool_readiness_marks_safe_read_only_tool_ready() -> None:
    matrix = build_mcp_tool_readiness(
        {
            "server": "github",
            "tools": [
                {
                    "name": "list_issues",
                    "server": "github",
                    "description": "Read-only issue listing tool",
                    "auth_mode": "oauth",
                    "approval_profile": "read_only",
                    "risk_level": "low",
                    "scopes": ["issues:read"],
                    "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}}},
                }
            ],
        }
    )

    assert matrix["kind"] == "mcp_tool_readiness"
    assert matrix["ok"] is True
    assert matrix["status"] == "ready"
    assert matrix["summary"]["ready_count"] == 1
    assert matrix["next_actions"] == ["prepare_mcp_tool_integration_review"]


def test_shell_and_filesystem_tool_without_manual_approval_is_blocked() -> None:
    matrix = build_mcp_tool_readiness(
        {
            "tools": [
                {
                    "name": "run_shell_patch",
                    "description": "Execute shell commands and patch files",
                    "auth_mode": "bearer",
                    "approval_profile": "auto",
                    "scopes": ["repo:write"],
                    "parameters": {"type": "object"},
                }
            ]
        }
    )

    assert matrix["status"] == "blocked"
    assert matrix["tools"][0]["risk_level"] == "critical"
    assert set(matrix["tools"][0]["capability_flags"]) >= {"shell", "filesystem_write"}
    assert matrix["issues"][0]["code"] == "mcp_tool_high_risk_without_manual_approval"
    assert matrix["next_actions"] == ["block_or_disable_unsafe_tools", "review_mcp_auth_and_approval"]


def test_secret_capable_tool_with_anonymous_auth_is_blocked() -> None:
    item = assess_mcp_tool_readiness(
        {
            "name": "read_vault_secret",
            "description": "Read secret token from vault",
            "auth_mode": "none",
            "approval_profile": "manual",
            "input_schema": {"type": "object"},
            "scopes": ["secrets:read"],
        }
    )

    assert item.decision == "blocked"
    assert item.risk_level == "high"
    assert "secrets" in item.capability_flags
    assert "secret-capable tool has anonymous auth" in item.reasons


def test_missing_schema_or_scopes_for_risky_tool_needs_review() -> None:
    matrix = build_mcp_tool_readiness(
        {
            "tools": [
                {
                    "name": "fetch_url",
                    "description": "Fetch URL over network",
                    "auth_mode": "api_key",
                    "approval_profile": "ask",
                    "risk_level": "medium",
                }
            ]
        }
    )

    assert matrix["status"] == "needs_review"
    assert matrix["tools"][0]["decision"] == "needs_review"
    assert "scopes missing for risky tool" in matrix["tools"][0]["reasons"]
    assert "input schema missing" in matrix["tools"][0]["reasons"]
    assert matrix["issues"][0]["code"] == "mcp_tool_scopes_missing"


def test_denied_tool_is_blocked_even_if_metadata_is_complete() -> None:
    matrix = build_mcp_tool_readiness(
        {
            "tools": [
                {
                    "name": "delete_project",
                    "description": "Delete project",
                    "auth": "oauth",
                    "approval": "deny",
                    "risk": "high",
                    "permissions": ["project:delete"],
                    "schema": {"type": "object"},
                }
            ]
        }
    )

    assert matrix["status"] == "blocked"
    assert matrix["issues"][0]["code"] == "mcp_tool_approval_profile_blocks"


def test_accepts_manifest_and_dataclass_like_tool_payload() -> None:
    @dataclass
    class Tool:
        name: str
        description: str
        auth_mode: str
        approval_profile: str
        risk_level: str
        scopes: list[str]
        input_schema: dict[str, str]

    matrix = build_mcp_tool_readiness(
        {
            "manifest": {
                "tools": [
                    Tool(
                        "search_docs",
                        "Search documentation over HTTP index",
                        "api_key",
                        "ask",
                        "medium",
                        ["docs:read"],
                        {"type": "object"},
                    )
                ]
            }
        }
    )

    assert matrix["status"] == "ready"
    assert matrix["tools"][0]["name"] == "search_docs"
    assert matrix["tools"][0]["risk_level"] == "medium"
    assert matrix["tools"][0]["scope_count"] == 1


def test_empty_matrix_requests_tool_metadata() -> None:
    matrix = build_mcp_tool_readiness({})

    assert matrix["status"] == "empty"
    assert matrix["ok"] is False
    assert matrix["next_actions"] == ["provide_mcp_tool_metadata"]
