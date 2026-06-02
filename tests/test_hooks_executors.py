"""Unit tests for hook executors (backend/app/core/hooks/executors.py).

Covers:
    - CommandHook: allow/deny/ask/modify parsing, non-zero exit, timeout,
      invalid JSON, unknown action, tool_matcher filtering (fail-open).
    - PythonHook: the four target shapes (instance / class / factory / bare
      async callable), tool_matcher filtering, bad target paths.
    - build_hook: dispatch on type, regex compile errors, missing fields.
    - load_hooks_from_config / register_hooks_from_config: skip disabled and
      invalid definitions, register survivors.
"""

from __future__ import annotations

import sys
import textwrap

import pytest

from backend.app.core.hooks.config import HookDefinition, HooksConfig
from backend.app.core.hooks.executors import (
    CommandHook,
    PythonHook,
    build_hook,
    load_hooks_from_config,
    register_hooks_from_config,
)
from backend.app.core.hooks.manager import HookManager
from backend.app.core.hooks.types import (
    HookAction,
    HookContext,
    HookDecision,
    HookEvent,
)


def _pre_ctx(tool_name: str = "write_file", **kw) -> HookContext:
    return HookContext(
        event=HookEvent.PRE_TOOL_USE,
        tool_name=tool_name,
        arguments={"path": "/etc/passwd"},
        **kw,
    )


def _post_ctx(tool_name: str = "write_file", **kw) -> HookContext:
    return HookContext(
        event=HookEvent.POST_TOOL_USE,
        tool_name=tool_name,
        result={"ok": True},
        **kw,
    )


def _cmd(script: str) -> list[str]:
    """Build an argv that runs an inline python script reading stdin."""
    return [sys.executable, "-c", textwrap.dedent(script)]


# ---------------------------------------------------------------------------
# CommandHook
# ---------------------------------------------------------------------------


class TestCommandHook:
    @pytest.mark.asyncio
    async def test_allow(self):
        hook = CommandHook(
            name="ok",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "allow", "reason": "fine"}))
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW
        assert decision.hook_name == "ok"

    @pytest.mark.asyncio
    async def test_deny(self):
        hook = CommandHook(
            name="block",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "deny", "reason": "prod write"}))
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.DENY
        assert decision.reason == "prod write"

    @pytest.mark.asyncio
    async def test_ask(self):
        hook = CommandHook(
            name="confirm",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "ask", "reason": "needs human"}))
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ASK

    @pytest.mark.asyncio
    async def test_modify_input(self):
        hook = CommandHook(
            name="rewrite",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "modify",
                                  "modified_input": {"path": "/tmp/safe"}}))
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.MODIFY
        assert decision.modified_input == {"path": "/tmp/safe"}

    @pytest.mark.asyncio
    async def test_modify_output(self):
        hook = CommandHook(
            name="redact",
            events={HookEvent.POST_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "modify",
                                  "modified_output": {"ok": True, "redacted": True}}))
                """
            ),
        )
        decision = await hook(_post_ctx())
        assert decision.action == HookAction.MODIFY
        assert decision.modified_output == {"ok": True, "redacted": True}

    @pytest.mark.asyncio
    async def test_modify_no_payload_is_allow(self):
        hook = CommandHook(
            name="noop-modify",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "modify"}))
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_nonzero_exit_is_allow(self):
        hook = CommandHook(
            name="crash",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys
                sys.exit(3)
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW
        assert "exit code 3" in decision.reason

    @pytest.mark.asyncio
    async def test_invalid_json_is_allow(self):
        hook = CommandHook(
            name="garbage",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                print("not json at all")
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW
        assert "invalid JSON" in decision.reason

    @pytest.mark.asyncio
    async def test_unknown_action_is_allow(self):
        hook = CommandHook(
            name="weird",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "explode"}))
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW
        assert "unknown action" in decision.reason

    @pytest.mark.asyncio
    async def test_timeout_is_allow(self):
        hook = CommandHook(
            name="slow",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            timeout=0.3,
            command=_cmd(
                """
                import time
                time.sleep(5)
                """
            ),
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW
        assert "timeout" in decision.reason

    @pytest.mark.asyncio
    async def test_spawn_error_is_allow(self):
        hook = CommandHook(
            name="missing",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=["this_binary_does_not_exist_xyz123"],
        )
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW

    @pytest.mark.asyncio
    async def test_tool_matcher_skips_nonmatching(self):
        # Command would DENY, but tool_matcher doesn't match the tool name,
        # so the hook short-circuits to ALLOW without ever spawning.
        hook = CommandHook(
            name="only-writes",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "deny"}))
                """
            ),
            tool_matcher=__import__("re").compile("write_file"),
        )
        decision = await hook(_pre_ctx(tool_name="read_file"))
        assert decision.action == HookAction.ALLOW
        assert "tool_matcher skip" in decision.reason

    @pytest.mark.asyncio
    async def test_tool_matcher_fires_on_match(self):
        hook = CommandHook(
            name="only-writes",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            command=_cmd(
                """
                import sys, json
                json.load(sys.stdin)
                print(json.dumps({"action": "deny", "reason": "blocked"}))
                """
            ),
            tool_matcher=__import__("re").compile("write_file"),
        )
        decision = await hook(_pre_ctx(tool_name="write_file"))
        assert decision.action == HookAction.DENY


# ---------------------------------------------------------------------------
# PythonHook
# ---------------------------------------------------------------------------


_PY_TARGET_MODULE = '''
from backend.app.core.hooks.types import HookAction, HookContext, HookDecision, HookEvent


class InstanceHook:
    """A Hook-conforming instance target."""
    name = "instance-hook"
    events = {HookEvent.PRE_TOOL_USE}
    priority = 10

    async def __call__(self, context):
        return HookDecision.deny(reason="instance denied", hook_name=self.name)


# Module-level singleton instance (case 1: Hook instance)
instance_singleton = InstanceHook()


class ClassHook:
    """A Hook class target (case 2: instantiated with no args)."""
    name = "class-hook"
    events = {HookEvent.PRE_TOOL_USE}
    priority = 20

    async def __call__(self, context):
        return HookDecision.ask(reason="class asked", hook_name=self.name)


def factory():
    """A factory returning a Hook (case 3)."""
    return ClassHook()


async def bare_hook(context):
    """A bare async callable (case 4)."""
    return HookDecision.modify_input({"path": "/tmp/x"}, hook_name="bare")
'''


@pytest.fixture
def py_target_module(tmp_path, monkeypatch):
    """Write an importable target module to tmp_path and put it on sys.path."""
    mod_path = tmp_path / "xagent_hook_targets.py"
    mod_path.write_text(_PY_TARGET_MODULE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    # Ensure a clean import each test.
    sys.modules.pop("xagent_hook_targets", None)
    yield "xagent_hook_targets"
    sys.modules.pop("xagent_hook_targets", None)


class TestPythonHook:
    @pytest.mark.asyncio
    async def test_instance_target(self, py_target_module):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target=f"{py_target_module}:instance_singleton",
        )
        hook.load()
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.DENY

    @pytest.mark.asyncio
    async def test_class_target(self, py_target_module):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target=f"{py_target_module}:ClassHook",
        )
        hook.load()
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ASK

    @pytest.mark.asyncio
    async def test_factory_target(self, py_target_module):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target=f"{py_target_module}:factory",
        )
        hook.load()
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ASK

    @pytest.mark.asyncio
    async def test_bare_callable_target(self, py_target_module):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target=f"{py_target_module}:bare_hook",
        )
        hook.load()
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.MODIFY
        assert decision.modified_input == {"path": "/tmp/x"}

    @pytest.mark.asyncio
    async def test_tool_matcher_skip(self, py_target_module):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target=f"{py_target_module}:instance_singleton",
            tool_matcher=__import__("re").compile("write_file"),
        )
        hook.load()
        decision = await hook(_pre_ctx(tool_name="read_file"))
        assert decision.action == HookAction.ALLOW
        assert "tool_matcher skip" in decision.reason

    def test_bad_target_no_colon(self):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target="no_colon_here",
        )
        with pytest.raises(ValueError, match="module:attr"):
            hook.load()

    def test_bad_target_missing_module(self):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target="nonexistent_module_xyz:Thing",
        )
        with pytest.raises(ModuleNotFoundError):
            hook.load()

    @pytest.mark.asyncio
    async def test_unloaded_is_allow(self):
        hook = PythonHook(
            name="h",
            events={HookEvent.PRE_TOOL_USE},
            priority=10,
            target="m:x",
        )
        # Never call load() — should fail-open.
        decision = await hook(_pre_ctx())
        assert decision.action == HookAction.ALLOW


# ---------------------------------------------------------------------------
# build_hook
# ---------------------------------------------------------------------------


class TestBuildHook:
    def test_build_command(self):
        d = HookDefinition(
            name="c",
            type="command",
            events=["pre_tool_use"],
            command=["echo", "hi"],
            tool_matcher="write_.*",
            priority=5,
            timeout_seconds=2.0,
        )
        hook = build_hook(d)
        assert isinstance(hook, CommandHook)
        assert hook.priority == 5
        assert hook.timeout == 2.0
        assert hook.tool_matcher is not None
        assert hook.events == {HookEvent.PRE_TOOL_USE}

    def test_build_python(self, py_target_module):
        d = HookDefinition(
            name="p",
            type="python",
            events=["pre_tool_use"],
            target=f"{py_target_module}:instance_singleton",
        )
        hook = build_hook(d)
        assert isinstance(hook, PythonHook)
        assert hook._inner is not None  # load() ran

    def test_build_no_valid_events(self):
        d = HookDefinition(name="x", type="command", events=["bogus"], command=["a"])
        with pytest.raises(ValueError, match="no valid events"):
            build_hook(d)

    def test_build_bad_regex(self):
        d = HookDefinition(
            name="x",
            type="command",
            events=["pre_tool_use"],
            command=["a"],
            tool_matcher="(unclosed",
        )
        with pytest.raises(ValueError, match="invalid tool_matcher"):
            build_hook(d)

    def test_build_command_missing_command(self):
        d = HookDefinition(name="x", type="command", events=["pre_tool_use"])
        with pytest.raises(ValueError, match="requires 'command'"):
            build_hook(d)

    def test_build_python_missing_target(self):
        d = HookDefinition(name="x", type="python", events=["pre_tool_use"])
        with pytest.raises(ValueError, match="requires 'target'"):
            build_hook(d)

    def test_build_unknown_type(self):
        d = HookDefinition(name="x", type="weird", events=["pre_tool_use"])
        with pytest.raises(ValueError, match="unknown type"):
            build_hook(d)


# ---------------------------------------------------------------------------
# load / register from config
# ---------------------------------------------------------------------------


class TestLoadAndRegister:
    def test_load_skips_disabled(self, py_target_module):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(
                name="on",
                type="python",
                events=["pre_tool_use"],
                target=f"{py_target_module}:instance_singleton",
                enabled=True,
            ),
            HookDefinition(
                name="off",
                type="python",
                events=["pre_tool_use"],
                target=f"{py_target_module}:instance_singleton",
                enabled=False,
            ),
        ]
        hooks = load_hooks_from_config(cfg)
        assert len(hooks) == 1
        assert hooks[0].name == "on"

    def test_load_skips_invalid(self, py_target_module):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(
                name="good",
                type="python",
                events=["pre_tool_use"],
                target=f"{py_target_module}:instance_singleton",
            ),
            # Invalid: command type with no command
            HookDefinition(name="bad", type="command", events=["pre_tool_use"]),
        ]
        hooks = load_hooks_from_config(cfg)
        assert [h.name for h in hooks] == ["good"]

    def test_load_skips_build_failure(self):
        cfg = HooksConfig()
        cfg.hooks = [
            # Valid definition but target import fails at build time.
            HookDefinition(
                name="broken-import",
                type="python",
                events=["pre_tool_use"],
                target="nonexistent_module_zzz:Thing",
            ),
        ]
        hooks = load_hooks_from_config(cfg)
        assert hooks == []

    def test_register_from_config(self, py_target_module):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(
                name="r",
                type="python",
                events=["pre_tool_use", "post_tool_use"],
                target=f"{py_target_module}:instance_singleton",
            ),
        ]
        manager = HookManager()
        count = register_hooks_from_config(manager, cfg)
        assert count == 1
        assert manager.has_hooks(HookEvent.PRE_TOOL_USE)
        assert manager.has_hooks(HookEvent.POST_TOOL_USE)

    @pytest.mark.asyncio
    async def test_registered_hook_runs_through_manager(self, py_target_module):
        cfg = HooksConfig()
        cfg.hooks = [
            HookDefinition(
                name="deny-all",
                type="python",
                events=["pre_tool_use"],
                target=f"{py_target_module}:instance_singleton",
            ),
        ]
        manager = HookManager()
        register_hooks_from_config(manager, cfg)
        result = await manager.trigger(_pre_ctx())
        assert result.denied is True
        assert result.reason == "instance denied"
