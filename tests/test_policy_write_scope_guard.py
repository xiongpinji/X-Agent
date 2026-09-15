"""写类工具的 permission_scope 越权回归测试。

背景：实测发现 tools:read 即可放行 write_file（read_scope 分支过宽），
标准模式（只读 scope）下文件被真实写入。本测试锁定写类工具必须
tools:write / tools:* / 专属 tool:name 才放行。
"""

from __future__ import annotations

from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.policy import WRITE_CLASS_TOOLS, ToolPolicyEngine


def _ctx(scopes: list[str]) -> RunContext:
    return RunContext(
        trace_id="t-scope-guard",
        request_id="r-scope-guard",
        permission_scope=scopes,
    )


def test_write_tool_blocked_with_read_only_scope() -> None:
    engine = ToolPolicyEngine()
    for tool in ("write_file", "apply_text_patch", "run_command", "git_commit"):
        verdict = engine.evaluate(_ctx(["agent:run", "tools:read"]), tool, RiskLevel.MEDIUM)
        assert not verdict.allowed, f"{tool} must be blocked under tools:read-only scope"
        assert "tools:write" in verdict.reason


def test_write_tool_allowed_with_write_scope() -> None:
    engine = ToolPolicyEngine()
    for tool in WRITE_CLASS_TOOLS:
        verdict = engine.evaluate(_ctx(["agent:run", "tools:read", "tools:write"]), tool, RiskLevel.MEDIUM)
        assert verdict.allowed, f"{tool} must pass with tools:write"


def test_write_tool_allowed_with_wildcard_or_dedicated_scope() -> None:
    engine = ToolPolicyEngine()
    assert engine.evaluate(_ctx(["tools:*"]), "write_file", RiskLevel.MEDIUM).allowed
    assert engine.evaluate(_ctx(["tool:write_file"]), "write_file", RiskLevel.MEDIUM).allowed


def test_read_tool_still_works_with_read_scope() -> None:
    engine = ToolPolicyEngine()
    for tool in ("read_file", "inspect_tree", "list_files", "search_text"):
        verdict = engine.evaluate(_ctx(["agent:run", "tools:read"]), tool, RiskLevel.LOW)
        assert verdict.allowed, f"{tool} must remain usable under tools:read"


def test_read_tool_blocked_without_any_scope() -> None:
    engine = ToolPolicyEngine()
    verdict = engine.evaluate(_ctx(["agent:run"]), "read_file", RiskLevel.LOW)
    assert not verdict.allowed
