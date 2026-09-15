from __future__ import annotations

from backend.app.core.contracts import RiskLevel, RunContext, ToolPolicyVerdict

# 写类工具：产生文件/仓库/命令副作用，需要 tools:write（或 tools:* / 专属 tool:name）。
# 实测曾发现 tools:read 即可放行 write_file 的越权（read_scope 分支过宽）。
WRITE_CLASS_TOOLS: frozenset[str] = frozenset({
    "write_file",
    "apply_text_patch",
    "apply_batch_patch",
    "run_command",
    "git_commit",
    "git_create_branch",
})


class ToolPolicyEngine:
    """Phase 0 policy gate for tools.

    It intentionally blocks high-risk actions by default. Later phases can replace this
    with a persisted policy engine without changing ToolRegistry callers.
    """

    def __init__(self, enable_high_risk_tools: bool = False) -> None:
        self.enable_high_risk_tools = enable_high_risk_tools

    def evaluate(
        self,
        context: RunContext,
        tool_name: str,
        risk_level: RiskLevel,
    ) -> ToolPolicyVerdict:
        if risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL} and not self.enable_high_risk_tools:
            return ToolPolicyVerdict(
                allowed=False,
                requires_approval=True,
                sandbox_profile="locked",
                reason=f"Tool {tool_name} is {risk_level.name} risk and requires approval.",
            )

        scope = f"tool:{tool_name}"
        # 通配兼容单复数：角色表历史上有 tool:*（单数）与 tools:*（复数）两种拼法
        has_tool_scope = scope in context.permission_scope
        has_wildcard_scope = ("tools:*" in context.permission_scope
                              or "tool:*" in context.permission_scope)

        if tool_name in WRITE_CLASS_TOOLS:
            # 写类：tools:read 不够，必须显式可写
            if not (has_tool_scope or has_wildcard_scope or "tools:write" in context.permission_scope):
                return ToolPolicyVerdict(
                    allowed=False,
                    requires_approval=False,
                    sandbox_profile="none",
                    reason=(
                        f"Missing permission scope tools:write for write-class tool "
                        f"{tool_name} (granted: {', '.join(context.permission_scope) or 'none'})."
                    ),
                )
        else:
            # 读类：tools:read 即可
            if not (has_tool_scope or has_wildcard_scope or "tools:read" in context.permission_scope):
                return ToolPolicyVerdict(
                    allowed=False,
                    requires_approval=False,
                    sandbox_profile="none",
                    reason=f"Missing permission scope {scope}.",
                )

        return ToolPolicyVerdict(
            allowed=True,
            requires_approval=False,
            sandbox_profile="process",
            reason="Allowed by Phase 0 policy.",
        )
