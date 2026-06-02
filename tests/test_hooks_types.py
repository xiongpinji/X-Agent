"""Unit tests for hooks core types (backend/app/core/hooks/types.py)."""

from __future__ import annotations

from backend.app.core.hooks.types import (
    Hook,
    HookAction,
    HookContext,
    HookDecision,
    HookEvent,
    HookResult,
)


class TestHookEvent:
    """Test HookEvent enum values."""

    def test_event_values(self):
        assert HookEvent.PRE_TOOL_USE.value == "pre_tool_use"
        assert HookEvent.POST_TOOL_USE.value == "post_tool_use"
        assert HookEvent.AGENT_START.value == "agent_start"
        assert HookEvent.AGENT_STOP.value == "agent_stop"
        assert HookEvent.USER_PROMPT_SUBMIT.value == "user_prompt_submit"

    def test_event_from_string(self):
        assert HookEvent("pre_tool_use") == HookEvent.PRE_TOOL_USE


class TestHookContext:
    """Test HookContext payload."""

    def test_defaults(self):
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE)
        assert ctx.tool_name == ""
        assert ctx.arguments == {}
        assert ctx.result == {}
        assert ctx.tenant_id == "default"
        assert ctx.user_id == "anonymous"
        assert ctx.risk_level == "low"

    def test_to_dict_roundtrip_keys(self):
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="write_file",
            arguments={"path": "a.txt"},
            result={"output": "ok"},
            trace_id="t1",
            request_id="r1",
            tenant_id="acme",
            user_id="bob",
            risk_level="high",
            metadata={"iteration": 2},
        )
        data = ctx.to_dict()
        assert data["event"] == "post_tool_use"
        assert data["tool_name"] == "write_file"
        assert data["arguments"] == {"path": "a.txt"}
        assert data["result"] == {"output": "ok"}
        assert data["trace_id"] == "t1"
        assert data["tenant_id"] == "acme"
        assert data["risk_level"] == "high"
        assert data["metadata"] == {"iteration": 2}

    def test_is_frozen(self):
        ctx = HookContext(event=HookEvent.PRE_TOOL_USE)
        try:
            ctx.tool_name = "x"  # type: ignore[misc]
            raised = False
        except Exception:
            raised = True
        assert raised, "HookContext should be immutable (frozen)"


class TestHookDecision:
    """Test HookDecision factory helpers."""

    def test_allow(self):
        d = HookDecision.allow(reason="ok", hook_name="h")
        assert d.action == HookAction.ALLOW
        assert d.reason == "ok"
        assert d.hook_name == "h"

    def test_deny(self):
        d = HookDecision.deny("nope", hook_name="guard")
        assert d.action == HookAction.DENY
        assert d.reason == "nope"

    def test_ask(self):
        d = HookDecision.ask("need approval")
        assert d.action == HookAction.ASK

    def test_modify_input(self):
        d = HookDecision.modify_input({"path": "safe.txt"}, reason="sanitized")
        assert d.action == HookAction.MODIFY
        assert d.modified_input == {"path": "safe.txt"}
        assert d.modified_output is None

    def test_modify_output(self):
        d = HookDecision.modify_output({"output": "redacted"})
        assert d.action == HookAction.MODIFY
        assert d.modified_output == {"output": "redacted"}
        assert d.modified_input is None

    def test_default_is_allow(self):
        assert HookDecision().action == HookAction.ALLOW


class TestHookResult:
    """Test HookResult convenience properties."""

    def test_allow_properties(self):
        r = HookResult(final_action=HookAction.ALLOW)
        assert r.allowed is True
        assert r.denied is False
        assert r.needs_approval is False

    def test_modify_counts_as_allowed(self):
        r = HookResult(final_action=HookAction.MODIFY)
        assert r.allowed is True
        assert r.denied is False

    def test_deny_properties(self):
        r = HookResult(final_action=HookAction.DENY, reason="x")
        assert r.denied is True
        assert r.allowed is False

    def test_ask_properties(self):
        r = HookResult(final_action=HookAction.ASK)
        assert r.needs_approval is True
        assert r.allowed is False


class TestHookProtocol:
    """Test that a simple object satisfies the Hook protocol."""

    def test_runtime_checkable(self):
        class MyHook:
            name = "my"
            events = {HookEvent.PRE_TOOL_USE}
            priority = 10

            async def __call__(self, context: HookContext) -> HookDecision:
                return HookDecision.allow()

        assert isinstance(MyHook(), Hook)
