"""Integration tests: hooks woven into ToolRegistry.execute.

These verify the control plane at the real agent tool chokepoint
(backend/app/core/tools.py::ToolRegistry.execute):
    - hook_manager=None is a perfect no-op (backward compatibility)
    - PRE_TOOL_USE DENY blocks the handler and returns a failure record
    - PRE_TOOL_USE MODIFY rewrites the arguments the handler receives
    - PRE_TOOL_USE ASK routes to the ApprovalStore and blocks
    - POST_TOOL_USE MODIFY rewrites the tool output
"""

from __future__ import annotations

import pytest

from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.hooks.manager import HookManager
from backend.app.core.hooks.types import HookDecision, HookEvent
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import ToolRegistry

# Schema that accepts any arguments. The registry's _schema_from_signature turns
# `def echo(**kwargs)` into properties={"kwargs": ...} with additionalProperties=False,
# which then rejects real args like {"a": 1}. These tests care about hook behaviour,
# not arg validation, so register an open schema.
_OPEN_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": True}


class _Hook:
    """Configurable test hook."""

    def __init__(self, name, decision, events, priority=100):
        self.name = name
        self._decision = decision
        self.events = events
        self.priority = priority

    async def __call__(self, context):
        return self._decision(context) if callable(self._decision) else self._decision


@pytest.fixture
def context():
    # tools:read scope passes the Phase 0 policy for low-risk tools
    return RunContext(permission_scope=["tools:read"])


def _make_registry(hook_manager=None):
    policy = ToolPolicyEngine(enable_high_risk_tools=True)
    registry = ToolRegistry(policy, hook_manager=hook_manager)

    async def echo(**kwargs):
        return {"echoed": kwargs}

    registry.register(
        name="echo",
        description="echo args",
        handler=echo,
        risk_level=RiskLevel.LOW,
        parameters_schema=_OPEN_SCHEMA,
    )
    return registry


class TestBackwardCompatibility:
    async def test_no_hook_manager_is_noop(self, context):
        registry = _make_registry(hook_manager=None)
        record = await registry.execute(context, "echo", {"a": 1})
        assert record.success is True
        assert record.output == {"echoed": {"a": 1}}

    async def test_empty_hook_manager_allows(self, context):
        registry = _make_registry(hook_manager=HookManager())
        record = await registry.execute(context, "echo", {"a": 1})
        assert record.success is True
        assert record.output == {"echoed": {"a": 1}}


class TestPreToolUseDeny:
    async def test_deny_blocks_handler(self, context):
        manager = HookManager()
        manager.register(
            _Hook(
                "block",
                HookDecision.deny("not allowed"),
                events={HookEvent.PRE_TOOL_USE},
            )
        )
        registry = _make_registry(hook_manager=manager)
        record = await registry.execute(context, "echo", {"a": 1})
        assert record.success is False
        assert "not allowed" in record.error

    async def test_deny_does_not_run_handler(self, context):
        ran = {"called": False}

        async def spy(**kwargs):
            ran["called"] = True
            return {"ok": True}

        policy = ToolPolicyEngine()
        manager = HookManager()
        manager.register(
            _Hook("block", HookDecision.deny("no"), events={HookEvent.PRE_TOOL_USE})
        )
        registry = ToolRegistry(policy, hook_manager=manager)
        registry.register(name="spy", description="spy", handler=spy, parameters_schema=_OPEN_SCHEMA)
        record = await registry.execute(context, "spy", {})
        assert record.success is False
        assert ran["called"] is False


class TestPreToolUseModify:
    async def test_modify_rewrites_arguments(self, context):
        def sanitize(ctx):
            args = dict(ctx.arguments)
            args["a"] = 999
            return HookDecision.modify_input(args)

        manager = HookManager()
        manager.register(
            _Hook("sanitize", sanitize, events={HookEvent.PRE_TOOL_USE})
        )
        registry = _make_registry(hook_manager=manager)
        record = await registry.execute(context, "echo", {"a": 1})
        assert record.success is True
        # handler should have received the modified argument
        assert record.output == {"echoed": {"a": 999}}


class TestPreToolUseAsk:
    async def test_ask_blocks_and_creates_approval(self, context):
        created = {}

        class _Approval:
            id = "appr-123"

        class _ApprovalStore:
            def create_tool_approval(self, **kwargs):
                created.update(kwargs)
                return _Approval()

        policy = ToolPolicyEngine()
        manager = HookManager()
        manager.register(
            _Hook(
                "ask",
                HookDecision.ask("please approve"),
                events={HookEvent.PRE_TOOL_USE},
            )
        )
        registry = ToolRegistry(
            policy, approval_store=_ApprovalStore(), hook_manager=manager
        )

        async def echo(**kwargs):
            return {"echoed": kwargs}

        registry.register(name="echo", description="echo", handler=echo, parameters_schema=_OPEN_SCHEMA)
        record = await registry.execute(context, "echo", {"a": 1})
        assert record.success is False
        assert "appr-123" in record.error
        assert created["tool_name"] == "echo"


class TestPostToolUseModify:
    async def test_post_modify_rewrites_output(self, context):
        manager = HookManager()
        manager.register(
            _Hook(
                "redact",
                HookDecision.modify_output({"echoed": "REDACTED"}),
                events={HookEvent.POST_TOOL_USE},
            )
        )
        registry = _make_registry(hook_manager=manager)
        record = await registry.execute(context, "echo", {"secret": "x"})
        assert record.success is True
        assert record.output == {"echoed": "REDACTED"}

    async def test_post_observe_only_keeps_output(self, context):
        manager = HookManager()
        manager.register(
            _Hook("observe", HookDecision.allow(), events={HookEvent.POST_TOOL_USE})
        )
        registry = _make_registry(hook_manager=manager)
        record = await registry.execute(context, "echo", {"a": 1})
        assert record.output == {"echoed": {"a": 1}}
