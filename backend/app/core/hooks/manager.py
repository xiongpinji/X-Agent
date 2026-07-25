"""Hook registration and dispatch for the X-Agent hooks system.

``HookManager`` is the control-plane dispatcher. Modules register hooks for
specific :class:`HookEvent` values; the agent's tool chokepoint and lifecycle
points call :meth:`HookManager.trigger`, which runs matching hooks in priority
order, aggregates their decisions fail-closed, and returns a
:class:`HookResult`.

Relationship to EventBus:
    The EventBus is observation-only and cannot block. The HookManager adds
    control (deny/ask/modify) but *also* publishes a best-effort observability
    event to the EventBus so existing subscribers still see hook activity.
    EventBus publishing never affects the control decision and never raises.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.app.core.hooks.types import (
    Hook,
    HookAction,
    HookContext,
    HookDecision,
    HookEvent,
    HookResult,
)

if TYPE_CHECKING:
    from backend.app.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class HookManager:
    """Registers hooks and dispatches events to them.

    Hooks are stored per :class:`HookEvent` and executed in ascending
    ``priority`` order (lower first). Each hook runs inside an exception
    guard so a faulty hook cannot crash agent execution; a hook that raises
    is treated as ALLOW (its failure is logged, not fatal) to avoid wedging
    the agent on a buggy observer — DENY must be explicit.

    Args:
        event_bus: Optional EventBus for observability publishing. When None,
            the manager attempts a lazy global lookup at trigger time; if that
            also fails, publishing is silently skipped.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._hooks: dict[HookEvent, list[Hook]] = {}
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, hook: Hook) -> None:
        """Register a hook for all events declared in ``hook.events``.

        Args:
            hook: A :class:`Hook`-conforming object. Registered once per event
                it subscribes to; the per-event list stays sorted by priority.
        """
        for event in hook.events:
            handlers = self._hooks.setdefault(event, [])
            handlers.append(hook)
            handlers.sort(key=lambda h: getattr(h, "priority", 100))
        logger.debug(
            "Registered hook %s for events %s",
            getattr(hook, "name", repr(hook)),
            [e.value for e in hook.events],
        )

    def unregister(self, hook: Hook) -> None:
        """Remove a previously registered hook from all of its events."""
        for event in list(self._hooks.keys()):
            handlers = self._hooks.get(event, [])
            self._hooks[event] = [h for h in handlers if h is not hook]

    def clear(self) -> None:
        """Remove all registered hooks (primarily for tests)."""
        self._hooks.clear()

    def hooks_for(self, event: HookEvent) -> list[Hook]:
        """Return the priority-ordered hooks registered for ``event``."""
        return list(self._hooks.get(event, []))

    def has_hooks(self, event: HookEvent) -> bool:
        """True when at least one hook is registered for ``event``."""
        return bool(self._hooks.get(event))

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    async def trigger(self, context: HookContext) -> HookResult:
        """Run all hooks for ``context.event`` and aggregate their decisions.

        Aggregation is fail-closed and short-circuiting:
            1. The first DENY wins immediately; remaining hooks do not run.
            2. Otherwise ASK is sticky (any ASK forces approval).
            3. MODIFY decisions chain: each rewrites the working payload, which
               is fed to the next hook so modifications compose.
            4. With no DENY/ASK, the result is ALLOW (or MODIFY if any hook
               rewrote the payload).

        Args:
            context: The event payload.

        Returns:
            A :class:`HookResult` describing the decisive action and the
            effective (possibly modified) arguments/result.
        """
        handlers = self._hooks.get(context.event, [])
        if not handlers:
            return HookResult(final_action=HookAction.ALLOW)

        is_pre = context.event == HookEvent.PRE_TOOL_USE
        working_args = dict(context.arguments)
        working_result = dict(context.result)
        decisions: list[HookDecision] = []
        saw_ask = False
        saw_modify = False

        for hook in handlers:
            # Feed the running (possibly modified) payload to each hook.
            current = HookContext(
                event=context.event,
                tool_name=context.tool_name,
                arguments=dict(working_args),
                result=dict(working_result),
                trace_id=context.trace_id,
                request_id=context.request_id,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                risk_level=context.risk_level,
                metadata=dict(context.metadata),
            )
            decision = await self._safe_call(hook, current)
            decisions.append(decision)

            if decision.action == HookAction.DENY:
                result = HookResult(
                    final_action=HookAction.DENY,
                    reason=decision.reason,
                    effective_arguments=working_args if is_pre else None,
                    effective_result=None if is_pre else working_result,
                    decisions=decisions,
                )
                await self._publish(context, result)
                return result

            if decision.action == HookAction.ASK:
                saw_ask = True

            if decision.action == HookAction.MODIFY:
                if is_pre and decision.modified_input is not None:
                    working_args = dict(decision.modified_input)
                    saw_modify = True
                elif not is_pre and decision.modified_output is not None:
                    working_result = dict(decision.modified_output)
                    saw_modify = True

        if saw_ask:
            final_action = HookAction.ASK
            reason = next(
                (d.reason for d in decisions if d.action == HookAction.ASK), ""
            )
        elif saw_modify:
            final_action = HookAction.MODIFY
            reason = next(
                (d.reason for d in decisions if d.action == HookAction.MODIFY), ""
            )
        else:
            final_action = HookAction.ALLOW
            reason = ""

        result = HookResult(
            final_action=final_action,
            reason=reason,
            effective_arguments=working_args if is_pre else None,
            effective_result=None if is_pre else working_result,
            decisions=decisions,
        )
        await self._publish(context, result)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _safe_call(self, hook: Hook, context: HookContext) -> HookDecision:
        """Invoke a hook, converting any exception into a logged ALLOW.

        A raising hook is non-fatal: the agent proceeds. Blocking requires an
        explicit DENY so a buggy observer can never silently wedge execution.
        """
        try:
            return await hook(context)
        except Exception as exc:
            name = getattr(hook, "name", repr(hook))
            logger.error(
                "Hook %s raised for event %s: %s",
                name,
                context.event.value,
                exc,
                exc_info=True,
            )
            return HookDecision.allow(reason=f"hook error: {exc}", hook_name=name)

    async def _publish(self, context: HookContext, result: HookResult) -> None:
        """Best-effort observability publish to the EventBus. Never raises."""
        try:
            bus = self._event_bus
            if bus is None:
                from backend.app.core.event_bus import get_event_bus

                bus = get_event_bus()

            from backend.app.core.event_bus import Event, EventType

            event = Event(
                event_type=EventType.SYSTEM_WARNING
                if result.denied
                else EventType.TOOL_EXECUTED,
                source="hooks",
                data={
                    "hook_event": context.event.value,
                    "tool_name": context.tool_name,
                    "final_action": result.final_action.value,
                    "reason": result.reason,
                    "decision_count": len(result.decisions),
                },
                correlation_id=context.trace_id,
                user_id=context.user_id if context.user_id != "anonymous" else None,
                tenant_id=context.tenant_id if context.tenant_id != "default" else None,
            )
            await bus.publish(event)
        except Exception as exc:
            logger.debug("Hook observability publish skipped: %s", exc)


# ----------------------------------------------------------------------
# Global accessor
# ----------------------------------------------------------------------
_hook_manager: HookManager | None = None


def get_hook_manager() -> HookManager:
    """Get or lazily create the process-global :class:`HookManager`."""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = HookManager()
    return _hook_manager


def set_hook_manager(manager: HookManager | None) -> None:
    """Override the global hook manager (primarily for tests/wiring)."""
    global _hook_manager
    _hook_manager = manager
