from __future__ import annotations

from backend.app.core.contracts import RiskLevel, RunContext, ToolPolicyVerdict


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
                reason=f"Tool {tool_name} is {risk_level.value} risk and requires approval.",
            )

        scope = f"tool:{tool_name}"
        wildcard = "tools:*"
        read_scope = "tools:read"
        has_tool_scope = scope in context.permission_scope
        has_wildcard_scope = wildcard in context.permission_scope
        has_read_scope = read_scope in context.permission_scope
        if not (has_tool_scope or has_wildcard_scope or has_read_scope):
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
