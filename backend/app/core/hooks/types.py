"""Core type definitions for the X-Agent hooks system.

These types form the control-plane contract: a hook receives an immutable
``HookContext`` describing an event and returns a ``HookDecision`` that the
``HookManager`` aggregates into a ``HookResult``. The manager applies the
result to the agent's tool-execution chokepoint
(``backend/app/core/tools.py::ToolRegistry.execute``).

Design notes:
    - Hooks are a CONTROL layer (deny / modify / ask), distinct from the
      EventBus which is observation only.
    - The aggregation policy is fail-closed: a single DENY short-circuits.
    - All payloads are plain dicts so command-based (subprocess) hooks and
      in-process Python hooks share one JSON-serialisable contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class HookEvent(str, Enum):
    """Lifecycle and tool events at which hooks may fire.

    Values mirror the agent execution path:
        - PRE_TOOL_USE / POST_TOOL_USE wrap the single tool chokepoint in
          ``ToolRegistry.execute`` (around the ``tool.handler`` call).
        - AGENT_START / AGENT_STOP wrap ``AgentLoop.run``.
        - USER_PROMPT_SUBMIT fires when a task/prompt enters the loop.
    """

    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    AGENT_START = "agent_start"
    AGENT_STOP = "agent_stop"
    USER_PROMPT_SUBMIT = "user_prompt_submit"


class HookAction(str, Enum):
    """The verdict a hook returns for an event.

    Semantics:
        - ALLOW: proceed unchanged.
        - DENY: block the action; the manager short-circuits remaining hooks.
        - ASK: require human approval before proceeding (routed to the
          existing ApprovalStore by the integration layer).
        - MODIFY: proceed, but with ``modified_input`` (PRE) or
          ``modified_output`` (POST) replacing the original payload.
    """

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
    MODIFY = "modify"


@dataclass(frozen=True)
class HookContext:
    """Immutable payload passed to every hook for a single event.

    Attributes:
        event: Which hook event is firing.
        tool_name: Tool being invoked (empty for non-tool events).
        arguments: Tool arguments for PRE_TOOL_USE; may be empty otherwise.
        result: Tool result/record for POST_TOOL_USE; empty otherwise.
        trace_id: Correlation id from the active RunContext.
        request_id: Request id from the active RunContext.
        tenant_id: Tenant id from the active RunContext.
        user_id: User id from the active RunContext.
        risk_level: Risk level string of the tool/context, if known.
        metadata: Free-form extra data (e.g. prompt text, iteration).
    """

    event: HookEvent
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    request_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    risk_level: str = "low"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict (for subprocess command hooks)."""
        return {
            "event": self.event.value,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "risk_level": self.risk_level,
            "metadata": self.metadata,
        }


@dataclass
class HookDecision:
    """A single hook's verdict for an event.

    Attributes:
        action: The verdict (allow/deny/ask/modify).
        reason: Human-readable explanation, surfaced in audit/errors.
        modified_input: Replacement arguments when action is MODIFY on a
            PRE_TOOL_USE event. Ignored otherwise.
        modified_output: Replacement result when action is MODIFY on a
            POST_TOOL_USE event. Ignored otherwise.
        hook_name: Identifier of the hook that produced this decision.
    """

    action: HookAction = HookAction.ALLOW
    reason: str = ""
    modified_input: dict[str, Any] | None = None
    modified_output: dict[str, Any] | None = None
    hook_name: str = ""

    @classmethod
    def allow(cls, reason: str = "", hook_name: str = "") -> HookDecision:
        """Build an ALLOW decision."""
        return cls(action=HookAction.ALLOW, reason=reason, hook_name=hook_name)

    @classmethod
    def deny(cls, reason: str, hook_name: str = "") -> HookDecision:
        """Build a DENY decision."""
        return cls(action=HookAction.DENY, reason=reason, hook_name=hook_name)

    @classmethod
    def ask(cls, reason: str, hook_name: str = "") -> HookDecision:
        """Build an ASK (require approval) decision."""
        return cls(action=HookAction.ASK, reason=reason, hook_name=hook_name)

    @classmethod
    def modify_input(
        cls, arguments: dict[str, Any], reason: str = "", hook_name: str = ""
    ) -> HookDecision:
        """Build a MODIFY decision that rewrites tool arguments (PRE)."""
        return cls(
            action=HookAction.MODIFY,
            reason=reason,
            modified_input=arguments,
            hook_name=hook_name,
        )

    @classmethod
    def modify_output(
        cls, result: dict[str, Any], reason: str = "", hook_name: str = ""
    ) -> HookDecision:
        """Build a MODIFY decision that rewrites a tool result (POST)."""
        return cls(
            action=HookAction.MODIFY,
            reason=reason,
            modified_output=result,
            hook_name=hook_name,
        )


@dataclass
class HookResult:
    """Aggregated outcome after running all hooks for one event.

    Produced by ``HookManager.trigger``. The integration layer reads
    ``final_action`` to decide whether to proceed, block, or seek approval,
    and uses ``effective_arguments`` / ``effective_result`` to apply any
    modifications.

    Attributes:
        final_action: The decisive action after aggregation (fail-closed:
            DENY wins, then ASK, then MODIFY, else ALLOW).
        reason: Reason from the decisive decision.
        effective_arguments: Arguments after applying MODIFY chain (PRE).
        effective_result: Result after applying MODIFY chain (POST).
        decisions: All individual decisions, in execution order.
    """

    final_action: HookAction = HookAction.ALLOW
    reason: str = ""
    effective_arguments: dict[str, Any] | None = None
    effective_result: dict[str, Any] | None = None
    decisions: list[HookDecision] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        """True when execution may proceed without blocking or approval."""
        return self.final_action in (HookAction.ALLOW, HookAction.MODIFY)

    @property
    def denied(self) -> bool:
        """True when execution must be blocked."""
        return self.final_action == HookAction.DENY

    @property
    def needs_approval(self) -> bool:
        """True when execution requires human approval before proceeding."""
        return self.final_action == HookAction.ASK


@runtime_checkable
class Hook(Protocol):
    """Protocol every hook implements.

    A hook is an async callable taking a ``HookContext`` and returning a
    ``HookDecision``. It also exposes ``name`` and the set of ``events`` it
    subscribes to, plus an integer ``priority`` (lower runs first).
    """

    name: str
    events: set[HookEvent]
    priority: int

    async def __call__(self, context: HookContext) -> HookDecision:
        """Evaluate the event and return a decision."""
        ...
