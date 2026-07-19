"""Hook executors: turn HookDefinition configs into runnable Hook objects.

This module bridges the declarative ``hooks.json`` configuration and the
runtime ``HookManager``. Two executor flavours are provided:

    - :class:`CommandHook` runs an external program via ``asyncio`` subprocess.
      The :class:`HookContext` is serialised as JSON on stdin; the program
      writes a JSON decision to stdout and exits. Non-zero exit codes or
      timeouts are treated as ALLOW (fail-open) to avoid wedging the agent on
      a buggy observer.
    - :class:`PythonHook` imports a dotted path (``"module:attr"``) and wraps
      the resolved object. The target may be a :class:`Hook` instance, a class
      to instantiate, a factory function returning a Hook, or a bare async
      callable ``(HookContext) -> HookDecision``.

Both executors support an optional ``tool_matcher`` regex: when set, the hook
short-circuits to ALLOW for tool events whose ``tool_name`` doesn't match.

Public helpers:
    - :func:`build_hook`: factory dispatching on ``HookDefinition.type``.
    - :func:`load_hooks_from_config`: build all enabled hooks from a config.
    - :func:`register_hooks_from_config`: load + register in one call.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Awaitable

from backend.app.core.hooks.config import HookDefinition, HooksConfig
from backend.app.core.hooks.manager import HookManager
from backend.app.core.hooks.types import (
    Hook,
    HookAction,
    HookContext,
    HookDecision,
    HookEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CommandHook
# ---------------------------------------------------------------------------


@dataclass
class CommandHook:
    """Subprocess-based hook executor.

    Runs an external command with the :class:`HookContext` as JSON on stdin.
    The command writes a JSON object to stdout with at least an ``action`` key
    (``"allow"`` | ``"deny"`` | ``"ask"`` | ``"modify"``). Optional keys:
    ``reason``, ``modified_input``, ``modified_output``.

    Exit code semantics:
        - 0: parse stdout JSON for the decision.
        - Non-zero: treat as ALLOW with a warning (fail-open).
        - Timeout: treat as ALLOW with a warning.

    Attributes:
        name: Unique identifier (from config).
        events: Set of events this hook subscribes to.
        priority: Lower runs first.
        command: Argv list (never shell-expanded).
        timeout: Max seconds to wait for the subprocess.
        tool_matcher: Optional compiled regex for tool-name filtering.
    """

    name: str
    events: set[HookEvent]
    priority: int
    command: list[str]
    timeout: float = 5.0
    tool_matcher: re.Pattern[str] | None = None

    async def __call__(self, context: HookContext) -> HookDecision:
        """Execute the command and parse its decision."""
        # Short-circuit on tool_matcher mismatch for tool events.
        if self.tool_matcher and context.tool_name:
            if not self.tool_matcher.search(context.tool_name):
                return HookDecision.allow(
                    reason="tool_matcher skip", hook_name=self.name
                )

        stdin_bytes = json.dumps(context.to_dict(), ensure_ascii=False).encode("utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_bytes), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "CommandHook %s timed out after %.1fs", self.name, self.timeout
            )
            return HookDecision.allow(
                reason=f"timeout after {self.timeout}s", hook_name=self.name
            )
        except OSError as exc:
            logger.warning("CommandHook %s failed to spawn: %s", self.name, exc)
            return HookDecision.allow(reason=f"spawn error: {exc}", hook_name=self.name)

        if proc.returncode != 0:
            logger.warning(
                "CommandHook %s exited %d: %s",
                self.name,
                proc.returncode,
                stderr.decode(errors="replace")[:200],
            )
            return HookDecision.allow(
                reason=f"exit code {proc.returncode}", hook_name=self.name
            )

        return self._parse_output(stdout)

    def _parse_output(self, stdout: bytes) -> HookDecision:
        """Parse JSON stdout into a HookDecision."""
        try:
            data = json.loads(stdout.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("CommandHook %s returned invalid JSON: %s", self.name, exc)
            return HookDecision.allow(reason=f"invalid JSON: {exc}", hook_name=self.name)

        action_str = data.get("action", "allow").lower()
        reason = data.get("reason", "")

        try:
            action = HookAction(action_str)
        except ValueError:
            logger.warning(
                "CommandHook %s returned unknown action %r", self.name, action_str
            )
            return HookDecision.allow(
                reason=f"unknown action: {action_str}", hook_name=self.name
            )

        if action == HookAction.DENY:
            return HookDecision.deny(reason=reason, hook_name=self.name)
        if action == HookAction.ASK:
            return HookDecision.ask(reason=reason, hook_name=self.name)
        if action == HookAction.MODIFY:
            modified_input = data.get("modified_input")
            modified_output = data.get("modified_output")
            if modified_input is not None:
                return HookDecision.modify_input(
                    modified_input, reason=reason, hook_name=self.name
                )
            if modified_output is not None:
                return HookDecision.modify_output(
                    modified_output, reason=reason, hook_name=self.name
                )
            # MODIFY with no payload → treat as ALLOW
            return HookDecision.allow(
                reason=reason or "modify with no payload", hook_name=self.name
            )
        # ALLOW
        return HookDecision.allow(reason=reason, hook_name=self.name)


# ---------------------------------------------------------------------------
# PythonHook
# ---------------------------------------------------------------------------


@dataclass
class PythonHook:
    """In-process Python hook executor.

    Imports a dotted path ``"module:attr"`` and wraps the resolved object.
    Supported target shapes:

        1. A :class:`Hook` instance (used directly).
        2. A class implementing :class:`Hook` (instantiated with no args).
        3. A factory ``() -> Hook`` (called once at load time).
        4. A bare async callable ``(HookContext) -> HookDecision`` (wrapped).

    Attributes:
        name: Unique identifier (from config).
        events: Set of events this hook subscribes to.
        priority: Lower runs first.
        target: Dotted import path ``"module:attr"``.
        tool_matcher: Optional compiled regex for tool-name filtering.
        _inner: The resolved callable (set by :meth:`load`).
    """

    name: str
    events: set[HookEvent]
    priority: int
    target: str
    tool_matcher: re.Pattern[str] | None = None
    _inner: Callable[[HookContext], Awaitable[HookDecision]] | None = field(
        default=None, repr=False
    )

    def load(self) -> None:
        """Import and resolve the target. Raises on failure."""
        if ":" not in self.target:
            raise ValueError(
                f"PythonHook {self.name}: target must be 'module:attr', got {self.target!r}"
            )
        module_path, attr_name = self.target.rsplit(":", 1)
        module = importlib.import_module(module_path)
        obj = getattr(module, attr_name)

        # Case 2 FIRST: a class implementing Hook. This must precede the
        # Hook-instance check because a runtime_checkable Protocol's
        # isinstance() also matches a *class object* (the class carries
        # name/events/priority/__call__ as attributes), which would otherwise
        # store the class itself instead of an instance.
        if isinstance(obj, type):
            instance = obj()
            if isinstance(instance, Hook) or callable(instance):
                self._inner = instance
                return
            raise TypeError(
                f"PythonHook {self.name}: class {obj} instance is not Hook or callable"
            )

        # Case 1: already a Hook instance
        if isinstance(obj, Hook):
            self._inner = obj
            return

        # Case 3: factory function returning Hook
        if callable(obj):
            # Try calling it with no args to see if it's a factory.
            try:
                result = obj()
                if isinstance(result, Hook) or callable(result):
                    self._inner = result
                    return
            except TypeError:
                # Not a zero-arg factory; assume it's a bare async callable
                # ``(HookContext) -> HookDecision``.
                pass
            # Case 4: bare async callable (HookContext) -> HookDecision
            self._inner = obj
            return

        raise TypeError(
            f"PythonHook {self.name}: target {self.target!r} resolved to non-callable {type(obj)}"
        )

    async def __call__(self, context: HookContext) -> HookDecision:
        """Invoke the loaded target."""
        if self._inner is None:
            return HookDecision.allow(
                reason="hook not loaded", hook_name=self.name
            )

        # Short-circuit on tool_matcher mismatch for tool events.
        if self.tool_matcher and context.tool_name:
            if not self.tool_matcher.search(context.tool_name):
                return HookDecision.allow(
                    reason="tool_matcher skip", hook_name=self.name
                )

        return await self._inner(context)


# ---------------------------------------------------------------------------
# Factory and loader helpers
# ---------------------------------------------------------------------------


def build_hook(definition: HookDefinition) -> Hook:
    """Build a runnable Hook from a HookDefinition.

    Args:
        definition: A validated hook definition from config.

    Returns:
        A :class:`CommandHook` or :class:`PythonHook` ready for registration.

    Raises:
        ValueError: If the definition type is unknown or invalid.
    """
    events = set(definition.event_enums())
    if not events:
        raise ValueError(f"Hook {definition.name!r} has no valid events")

    tool_matcher: re.Pattern[str] | None = None
    if definition.tool_matcher:
        try:
            tool_matcher = re.compile(definition.tool_matcher)
        except re.error as exc:
            raise ValueError(
                f"Hook {definition.name!r}: invalid tool_matcher regex: {exc}"
            ) from exc

    if definition.type == "command":
        if not definition.command:
            raise ValueError(f"Hook {definition.name!r}: command type requires 'command'")
        return CommandHook(
            name=definition.name,
            events=events,
            priority=definition.priority,
            command=definition.command,
            timeout=definition.timeout_seconds,
            tool_matcher=tool_matcher,
        )

    if definition.type == "python":
        if not definition.target:
            raise ValueError(f"Hook {definition.name!r}: python type requires 'target'")
        hook = PythonHook(
            name=definition.name,
            events=events,
            priority=definition.priority,
            target=definition.target,
            tool_matcher=tool_matcher,
        )
        hook.load()  # Raises on import failure
        return hook

    raise ValueError(f"Hook {definition.name!r}: unknown type {definition.type!r}")


def load_hooks_from_config(config: HooksConfig) -> list[Hook]:
    """Build all enabled, valid hooks from a HooksConfig.

    Invalid or disabled definitions are logged and skipped (fail-open at load
    time so one bad hook doesn't block the agent).

    Args:
        config: A loaded :class:`HooksConfig`.

    Returns:
        List of runnable :class:`Hook` objects.
    """
    hooks: list[Hook] = []
    for defn in config.hooks:
        if not defn.enabled:
            logger.debug("Skipping disabled hook %s", defn.name)
            continue
        errors = defn.validate()
        if errors:
            logger.warning("Skipping invalid hook %s: %s", defn.name, errors)
            continue
        try:
            hook = build_hook(defn)
            hooks.append(hook)
            logger.info("Loaded hook %s (%s)", defn.name, defn.type)
        except Exception as exc:  # noqa: BLE001 - fail-open at load time
            logger.warning("Failed to build hook %s: %s", defn.name, exc)
    return hooks


def register_hooks_from_config(manager: HookManager, config: HooksConfig) -> int:
    """Load hooks from config and register them with a HookManager.

    Args:
        manager: The :class:`HookManager` to register hooks with.
        config: A loaded :class:`HooksConfig`.

    Returns:
        Number of hooks successfully registered.
    """
    hooks = load_hooks_from_config(config)
    for hook in hooks:
        manager.register(hook)
    return len(hooks)
