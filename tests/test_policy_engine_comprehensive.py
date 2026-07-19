"""Comprehensive tests for ToolPolicyEngine with 100% coverage."""
import pytest
from backend.app.core.contracts import RiskLevel, RunContext, ToolPolicyVerdict
from backend.app.core.policy import ToolPolicyEngine


class TestToolPolicyEngineInitialization:
    """Test ToolPolicyEngine initialization."""

    def test_init_default_high_risk_disabled(self):
        """Test default initialization disables high-risk tools."""
        engine = ToolPolicyEngine()
        assert engine.enable_high_risk_tools is False

    def test_init_high_risk_enabled(self):
        """Test initialization with high-risk tools enabled."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        assert engine.enable_high_risk_tools is True

    def test_init_high_risk_explicitly_disabled(self):
        """Test explicit disabling of high-risk tools."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        assert engine.enable_high_risk_tools is False


class TestToolPolicyEngineHighRiskTools:
    """Test high-risk tool evaluation."""

    def test_high_risk_tool_blocked_when_disabled(self):
        """Test HIGH risk tool is blocked when high-risk disabled."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "delete_file", RiskLevel.HIGH)
        assert verdict.allowed is False
        assert verdict.requires_approval is True
        assert verdict.sandbox_profile == "locked"
        assert "HIGH risk" in verdict.reason

    def test_critical_risk_tool_blocked_when_disabled(self):
        """Test CRITICAL risk tool is blocked when high-risk disabled."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "execute_code", RiskLevel.CRITICAL)
        assert verdict.allowed is False
        assert verdict.requires_approval is True
        assert verdict.sandbox_profile == "locked"
        assert "CRITICAL risk" in verdict.reason

    def test_high_risk_tool_allowed_when_enabled(self):
        """Test HIGH risk tool is allowed when high-risk enabled."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "delete_file", RiskLevel.HIGH)
        assert verdict.allowed is True
        assert verdict.requires_approval is False
        assert verdict.sandbox_profile == "process"

    def test_critical_risk_tool_allowed_when_enabled(self):
        """Test CRITICAL risk tool is allowed when high-risk enabled."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "execute_code", RiskLevel.CRITICAL)
        assert verdict.allowed is True
        assert verdict.requires_approval is False
        assert verdict.sandbox_profile == "process"


class TestToolPolicyEnginePermissionScopes:
    """Test permission scope evaluation."""

    def test_specific_tool_scope_allowed(self):
        """Test specific tool scope grants access."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tool:read_file"],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is True
        assert verdict.requires_approval is False

    def test_wildcard_scope_allowed(self):
        """Test wildcard scope grants access to all tools."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "any_tool", RiskLevel.LOW)
        assert verdict.allowed is True
        assert verdict.requires_approval is False

    def test_read_scope_allowed(self):
        """Test read scope grants access."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:read"],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is True
        assert verdict.requires_approval is False

    def test_missing_permission_scope_denied(self):
        """Test missing permission scope denies access."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["other:scope"],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is False
        assert verdict.requires_approval is False
        assert verdict.sandbox_profile == "none"
        assert "Missing permission scope" in verdict.reason

    def test_empty_permission_scope_denied(self):
        """Test empty permission scope denies access."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=[],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is False
        assert verdict.requires_approval is False
        assert verdict.sandbox_profile == "none"


class TestToolPolicyEngineRiskLevels:
    """Test different risk levels."""

    def test_low_risk_tool_allowed(self):
        """Test LOW risk tool is allowed."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is True
        assert verdict.requires_approval is False
        assert verdict.sandbox_profile == "process"

    def test_medium_risk_tool_allowed(self):
        """Test MEDIUM risk tool is allowed."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "write_file", RiskLevel.MEDIUM)
        assert verdict.allowed is True
        assert verdict.requires_approval is False
        assert verdict.sandbox_profile == "process"

    def test_all_risk_levels_with_wildcard(self):
        """Test all risk levels with wildcard scope."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        for risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]:
            verdict = engine.evaluate(context, "tool", risk_level)
            assert verdict.allowed is True


class TestToolPolicyEngineEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_tool_name(self):
        """Test evaluation with empty tool name."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "", RiskLevel.LOW)
        assert verdict.allowed is True

    def test_very_long_tool_name(self):
        """Test evaluation with very long tool name."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        long_name = "a" * 1000
        verdict = engine.evaluate(context, long_name, RiskLevel.LOW)
        assert verdict.allowed is True

    def test_special_characters_in_tool_name(self):
        """Test evaluation with special characters in tool name."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "tool-name_123.test", RiskLevel.LOW)
        assert verdict.allowed is True

    def test_multiple_matching_scopes(self):
        """Test evaluation with multiple matching scopes."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tool:read_file", "tools:*", "tools:read"],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is True

    def test_case_sensitive_scope_matching(self):
        """Test that scope matching is case-sensitive."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["TOOLS:*"],  # uppercase
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        # Should not match because scope matching is case-sensitive
        assert verdict.allowed is False


class TestToolPolicyEngineVerdictStructure:
    """Test verdict structure and content."""

    def test_verdict_has_all_fields(self):
        """Test verdict contains all required fields."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "tool", RiskLevel.LOW)
        assert hasattr(verdict, "allowed")
        assert hasattr(verdict, "requires_approval")
        assert hasattr(verdict, "sandbox_profile")
        assert hasattr(verdict, "reason")

    def test_verdict_reason_contains_tool_name(self):
        """Test verdict reason contains tool name."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "my_tool", RiskLevel.HIGH)
        assert "my_tool" in verdict.reason

    def test_verdict_reason_contains_risk_level(self):
        """Test verdict reason contains risk level."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "tool", RiskLevel.CRITICAL)
        assert "CRITICAL" in verdict.reason

    def test_verdict_sandbox_profile_values(self):
        """Test verdict sandbox profile has valid values."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "tool", RiskLevel.LOW)
        assert verdict.sandbox_profile in ["locked", "none", "process"]


class TestToolPolicyEngineContextVariations:
    """Test with various context configurations."""

    def test_different_tenant_ids(self):
        """Test evaluation with different tenant IDs."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        for tenant_id in ["tenant1", "tenant2", "tenant-123"]:
            context = RunContext(
                tenant_id=tenant_id,
                user_id="user1",
                trace_id="trace1",
                permission_scope=["tools:*"],
            )
            verdict = engine.evaluate(context, "tool", RiskLevel.LOW)
            assert verdict.allowed is True

    def test_different_user_ids(self):
        """Test evaluation with different user IDs."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        for user_id in ["user1", "user2", "admin"]:
            context = RunContext(
                tenant_id="tenant1",
                user_id=user_id,
                trace_id="trace1",
                permission_scope=["tools:*"],
            )
            verdict = engine.evaluate(context, "tool", RiskLevel.LOW)
            assert verdict.allowed is True

    def test_different_trace_ids(self):
        """Test evaluation with different trace IDs."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        for trace_id in ["trace1", "trace2", "trace-uuid"]:
            context = RunContext(
                tenant_id="tenant1",
                user_id="user1",
                trace_id=trace_id,
                permission_scope=["tools:*"],
            )
            verdict = engine.evaluate(context, "tool", RiskLevel.LOW)
            assert verdict.allowed is True


class TestToolPolicyEngineComplexScenarios:
    """Test complex real-world scenarios."""

    def test_high_risk_tool_with_specific_scope_denied(self):
        """Test HIGH risk tool denied even with specific scope."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tool:delete_file"],  # specific scope
        )
        verdict = engine.evaluate(context, "delete_file", RiskLevel.HIGH)
        assert verdict.allowed is False
        assert verdict.requires_approval is True

    def test_critical_tool_with_wildcard_scope_denied(self):
        """Test CRITICAL tool denied even with wildcard scope."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],  # wildcard scope
        )
        verdict = engine.evaluate(context, "execute_code", RiskLevel.CRITICAL)
        assert verdict.allowed is False
        assert verdict.requires_approval is True

    def test_low_risk_tool_without_scope_denied(self):
        """Test LOW risk tool denied without proper scope."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["other:scope"],
        )
        verdict = engine.evaluate(context, "read_file", RiskLevel.LOW)
        assert verdict.allowed is False
        assert verdict.requires_approval is False

    def test_approval_required_for_high_risk_disabled(self):
        """Test approval required when high-risk tools disabled."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "tool", RiskLevel.HIGH)
        assert verdict.requires_approval is True
        assert verdict.allowed is False

    def test_no_approval_required_for_low_risk(self):
        """Test no approval required for low-risk tools."""
        engine = ToolPolicyEngine(enable_high_risk_tools=False)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict = engine.evaluate(context, "tool", RiskLevel.LOW)
        assert verdict.requires_approval is False
        assert verdict.allowed is True


class TestToolPolicyEngineConsistency:
    """Test consistency of policy evaluation."""

    def test_same_input_same_output(self):
        """Test same input produces same output."""
        engine = ToolPolicyEngine(enable_high_risk_tools=True)
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        verdict1 = engine.evaluate(context, "tool", RiskLevel.LOW)
        verdict2 = engine.evaluate(context, "tool", RiskLevel.LOW)
        assert verdict1.allowed == verdict2.allowed
        assert verdict1.requires_approval == verdict2.requires_approval
        assert verdict1.sandbox_profile == verdict2.sandbox_profile

    def test_different_engines_same_policy(self):
        """Test different engine instances apply same policy."""
        context = RunContext(
            tenant_id="tenant1",
            user_id="user1",
            trace_id="trace1",
            permission_scope=["tools:*"],
        )
        engine1 = ToolPolicyEngine(enable_high_risk_tools=True)
        engine2 = ToolPolicyEngine(enable_high_risk_tools=True)
        verdict1 = engine1.evaluate(context, "tool", RiskLevel.LOW)
        verdict2 = engine2.evaluate(context, "tool", RiskLevel.LOW)
        assert verdict1.allowed == verdict2.allowed
        assert verdict1.requires_approval == verdict2.requires_approval
