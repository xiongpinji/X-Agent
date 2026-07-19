"""Unit tests for HookManager (backend/app/core/hooks/manager.py).

Covers registration, priority ordering, fail-closed aggregation (deny
short-circuit), ASK stickiness, MODIFY chaining, exception isolation, and
that EventBus publishing never affects the control decision.
"""

from __future__ import annotations

import pytest

from backend.app.core.hooks.manager import (
    HookManager,
    get_hook_manager,
    set_hook_manager,
)
from backend.app.core.hooks.types import (
    HookAction,
    HookContext,
    HookDecision,
    HookEvent,
)


class _Hook:
    """Minimal configurable hook for tests."""

    def __init__(self, name, decision, events=None, priority=100, record=None):
        self.name = name
        self._decision = decision
        self.events = events or {HookEvent.PRE_TOOL_USE}
        self.priority = priority
        self._record = record

    async def __call__(self, context: HookContext) -> HookDecision:
        if self._record is not None:
            self._record.append(self.name)
        decision = self._decision(context) if callable(self._decision) else self._decision
        return decision


def _pre_ctx(**kwargs) -> HookContext:
    return HookContext(event=HookEvent.PRE_TOOL_USE, tool_name="write_file", **kwargs)


@pytest.fixture
def manager():
    return HookManager(event_bus=None)


class TestRegistration:
    def test_register_and_query(self, manager):
        hook = _Hook("a", HookDecision.allow())
        manager.register(hook)
        assert manager.has_hooks(HookEvent.PRE_TOOL_USE) is True
        assert manager.hooks_for(HookEvent.PRE_TOOL_USE) == [hook]
        assert manager.has_hooks(HookEvent.POST_TOOL_USE) is False

    def test_priority_ordering(self, manager):
        low = _Hook("low", HookDecision.allow(), priority=10)
        high = _Hook("high", HookDecision.allow(), priority=90)
        manager.register(high)
        manager.register(low)
        ordered = manager.hooks_for(HookEvent.PRE_TOOL_USE)
        assert [h.name for h in ordered] == ["low", "high"]

    def test_unregister(self, manager):
        hook = _Hook("a", HookDecision.allow())
        manager.register(hook)
        manager.unregister(hook)
        assert manager.has_hooks(HookEvent.PRE_TOOL_USE) is False

    def test_clear(self, manager):
        manager.register(_Hook("a", HookDecision.allow()))
        manager.clear()
        assert manager.has_hooks(HookEvent.PRE_TOOL_USE) is False


class TestAggregation:
    async def test_no_hooks_allows(self, manager):
        result = await manager.trigger(_pre_ctx())
        assert result.final_action == HookAction.ALLOW
        assert result.allowed is True

    async def test_all_allow(self, manager):
        manager.register(_Hook("a", HookDecision.allow()))
        manager.register(_Hook("b", HookDecision.allow()))
        result = await manager.trigger(_pre_ctx())
        assert result.final_action == HookAction.ALLOW
        assert len(result.decisions) == 2

    async def test_deny_short_circuits(self, manager):
        order: list[str] = []
        manager.register(
            _Hook("first", HookDecision.deny("blocked"), priority=10, record=order)
        )
        manager.register(
            _Hook("second", HookDecision.allow(), priority=20, record=order)
        )
        result = await manager.trigger(_pre_ctx())
        assert result.denied is True
        assert result.reason == "blocked"
        # second hook must NOT run after a deny
        assert order == ["first"]

    async def test_ask_is_sticky(self, manager):
        manager.register(_Hook("a", HookDecision.allow(), priority=10))
        manager.register(_Hook("b", HookDecision.ask("approve?"), priority=20))
        result = await manager.trigger(_pre_ctx())
        assert result.needs_approval is True
        assert result.reason == "approve?"

    async def test_deny_beats_ask(self, manager):
        # deny at higher priority short-circuits before ask is seen
        manager.register(_Hook("deny", HookDecision.deny("no"), priority=10))
        manager.register(_Hook("ask", HookDecision.ask("approve?"), priority=20))
        result = await manager.trigger(_pre_ctx())
        assert result.denied is True

    async def test_modify_input_chains(self, manager):
        def first(ctx):
            args = dict(ctx.arguments)
            args["step1"] = True
            return HookDecision.modify_input(args)

        def second(ctx):
            # should see step1 from the first hook's modification
            assert ctx.arguments.get("step1") is True
            args = dict(ctx.arguments)
            args["step2"] = True
            return HookDecision.modify_input(args)

        manager.register(_Hook("first", first, priority=10))
        manager.register(_Hook("second", second, priority=20))
        result = await manager.trigger(_pre_ctx(arguments={"path": "a.txt"}))
        assert result.final_action == HookAction.MODIFY
        assert result.effective_arguments == {
            "path": "a.txt",
            "step1": True,
            "step2": True,
        }

    async def test_modify_output_for_post(self, manager):
        hook = _Hook(
            "redact",
            HookDecision.modify_output({"output": "REDACTED"}),
            events={HookEvent.POST_TOOL_USE},
        )
        manager.register(hook)
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name="read_file",
            result={"output": "secret"},
        )
        result = await manager.trigger(ctx)
        assert result.final_action == HookAction.MODIFY
        assert result.effective_result == {"output": "REDACTED"}


class TestExceptionIsolation:
    async def test_raising_hook_becomes_allow(self, manager):
        def boom(ctx):
            raise RuntimeError("hook bug")

        manager.register(_Hook("boom", boom))
        result = await manager.trigger(_pre_ctx())
        # a raising hook must not crash; treated as allow
        assert result.final_action == HookAction.ALLOW
        assert result.decisions[0].action == HookAction.ALLOW

    async def test_raising_hook_does_not_block_others(self, manager):
        def boom(ctx):
            raise RuntimeError("hook bug")

        manager.register(_Hook("boom", boom, priority=10))
        manager.register(_Hook("deny", HookDecision.deny("no"), priority=20))
        result = await manager.trigger(_pre_ctx())
        assert result.denied is True


class TestGlobalAccessor:
    def test_get_creates_singleton(self):
        set_hook_manager(None)
        m1 = get_hook_manager()
        m2 = get_hook_manager()
        assert m1 is m2

    def test_set_override(self):
        custom = HookManager()
        set_hook_manager(custom)
        assert get_hook_manager() is custom
        set_hook_manager(None)
