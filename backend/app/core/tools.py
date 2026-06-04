from __future__ import annotations

import inspect
import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from backend.app.core.approvals import ApprovalStatus, ApprovalStore
from backend.app.core.contracts import RiskLevel, RunContext, ToolCallRecord, ToolPolicyVerdict, AgentPlanStepRecord
from backend.app.core.policy import ToolPolicyEngine
from backend.app.settings import PROJECT_ROOT

import contextvars as _contextvars

# Per-run override for the file-tool sandbox root. Defaults to PROJECT_ROOT.
# Set via set_tool_root_override() so sandbox/issue-to-PR tasks can operate on
# a cloned repo dir while keeping the same within-root containment guarantee
# (paths are still confined to whichever root is active). contextvars keeps
# this coroutine-safe so concurrent agent runs don't leak roots into each other.
_tool_root_override: "_contextvars.ContextVar[str | None]" = _contextvars.ContextVar(
    "xagent_tool_root_override", default=None
)


def set_tool_root_override(root: str | None):
    """Set the active file-tool root (returns a token for reset)."""
    return _tool_root_override.set(root)


def reset_tool_root_override(token) -> None:
    """Restore the previous file-tool root."""
    _tool_root_override.reset(token)


def _active_tool_base() -> "Path":
    """The currently-allowed root: per-run override if set, else PROJECT_ROOT."""
    override = _tool_root_override.get()
    return Path(override).resolve() if override else Path(PROJECT_ROOT).resolve()

if TYPE_CHECKING:
    from backend.app.core.hooks import HookManager

# Import parallel execution components (lazy import to avoid circular dependencies)
_parallel_executor = None
_tool_result_cache = None

ToolHandler = Callable[..., Awaitable[Any]]


# Forbidden paths that should never be accessed
_FORBIDDEN_PATHS = {
    "/etc",
    "/sys",
    "/proc",
    "/dev",
    "/boot",
    "/root",
    "/var/log",
    "/var/spool",
    "/tmp",
    "/var/tmp",
}


def _is_path_forbidden(path: Path) -> bool:
    """Check if path is in forbidden system directories."""
    path_str = str(path).lower()
    for forbidden in _FORBIDDEN_PATHS:
        if path_str.startswith(forbidden.lower()):
            return True
    return False


def _resolve_tool_path(path: str) -> Path:
    """Restrict file paths to the project root to prevent traversal attacks.

    Security checks:
    - Path must be within PROJECT_ROOT
    - Path must not contain symlinks pointing outside PROJECT_ROOT
    - Path must not be in forbidden system directories
    """
    base = _active_tool_base()
    target = Path(path).expanduser().resolve()

    # Check if path is in forbidden directories
    if _is_path_forbidden(target):
        raise PermissionError(f"Access to system directory forbidden: {target}")

    # Verify path is within project root
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(f"Path must be within project directory: {base}")

    # Check for symlink attacks
    if target.is_symlink():
        real_target = target.resolve()
        try:
            real_target.relative_to(base)
        except ValueError:
            raise PermissionError(f"Symlink target must be within project directory: {real_target}")

    return target


def _resolve_tool_root(root: str) -> Path:
    """Restrict directory roots to the project root to prevent traversal attacks.

    Security checks:
    - Root must be within PROJECT_ROOT
    - Root must not be in forbidden system directories
    """
    base = _active_tool_base()
    target = Path(root).expanduser().resolve()

    # Check if path is in forbidden directories
    if _is_path_forbidden(target):
        raise PermissionError(f"Access to system directory forbidden: {target}")

    # Verify root is within project root
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(f"Root must be within project directory: {base}")

    return target


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    handler: ToolHandler
    risk_level: RiskLevel = RiskLevel.LOW
    required_scope: str = ""
    parameters_schema: dict[str, Any] = field(default_factory=dict)


class ToolExecutionRecord(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    trace_id: str
    tool_name: str
    tenant_id: str
    user_id: str
    success: bool
    created_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now(__import__('datetime').UTC).isoformat())
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    rollback_artifact: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionStore:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._records: dict[str, ToolExecutionRecord] = {}
        self._lock = RLock()
        if self._storage_path:
            self._load_from_disk()

    def record(self, context: RunContext, tool_call: ToolCallRecord) -> ToolExecutionRecord:
        record = ToolExecutionRecord(
            trace_id=context.trace_id,
            tool_name=tool_call.tool_name,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            success=tool_call.success,
            result={
                "arguments_preview": tool_call.arguments_preview,
                "latency_ms": tool_call.latency_ms,
                "risk_level": tool_call.risk_level.value,
                "policy": tool_call.policy.model_dump(mode="json"),
            },
            error=tool_call.error,
        )
        with self._lock:
            self._records[record.execution_id] = record
            self._persist()
        return record

    def get(self, execution_id: str) -> ToolExecutionRecord | None:
        return self._records.get(execution_id)

    def by_trace(self, trace_id: str) -> list[ToolExecutionRecord]:
        records = [record for record in self._records.values() if record.trace_id == trace_id]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records

    def _load_from_disk(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        with self._storage_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for item in payload:
            record = ToolExecutionRecord.model_validate(item)
            self._records[record.execution_id] = record

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [record.model_dump(mode="json") for record in self._records.values()]
        self._storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ToolRegistry:
    def __init__(
        self,
        policy_engine: ToolPolicyEngine | None = None,
        approval_store: ApprovalStore | None = None,
        execution_store: ToolExecutionStore | None = None,
        hook_manager: "HookManager | None" = None,
    ) -> None:
        # ``policy_engine`` is optional so the registry can be constructed with
        # no arguments (the agent-v2 integration suite and other lightweight
        # callers do ``ToolRegistry()``). The default Phase-0 engine permits
        # LOW-risk tools whenever the context carries the ``tools:read`` scope,
        # which the default :class:`RunContext` already grants — so no-arg
        # construction stays usable end-to-end without a bespoke policy.
        self._policy = policy_engine if policy_engine is not None else ToolPolicyEngine()
        self._approval_store = approval_store
        self._execution_store = execution_store
        self._hook_manager = hook_manager
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str | ToolDefinition,
        description: str | None = None,
        handler: ToolHandler | None = None,
        risk_level: RiskLevel = RiskLevel.LOW,
        required_scope: str | None = None,
        parameters_schema: dict[str, Any] | None = None,
    ) -> None:
        # Two calling conventions are accepted:
        #   * register(name, description, handler, ...)  — canonical / unpacked
        #   * register(tool_def)                         — a prebuilt ToolDefinition
        # The single-ToolDefinition form is used by the agent-v2 integration
        # suite; it is stored verbatim so the caller stays in full control of
        # required_scope / parameters_schema.
        if isinstance(name, ToolDefinition):
            self._tools[name.name] = name
            return
        self._tools[name] = ToolDefinition(
            name,
            description or "",
            handler,
            risk_level,
            required_scope or f"tool:{name}",
            parameters_schema or self._schema_from_signature(handler),
        )

    def definitions_for_llm(self) -> list[dict[str, Any]]:
        definitions = []
        for tool in self._tools.values():
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "x-risk-level": tool.risk_level.value,
                        "x-required-scope": tool.required_scope,
                        "parameters": tool.parameters_schema,
                    },
                }
            )
        return definitions

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "required_scope": tool.required_scope,
                "parameters": tool.parameters_schema,
            }
            for tool in self._tools.values()
        ]

    def capability_index(self) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {"read": [], "write": [], "search": [], "code": [], "utility": []}
        for tool in self._tools.values():
            bucket = "utility"
            name = tool.name.lower()
            if any(token in name for token in ["read", "list", "search", "inspect"]):
                bucket = "read" if "search" not in name else "search"
            if any(token in name for token in ["write", "edit", "update", "patch", "apply", "modify"]):
                bucket = "write"
            if any(token in name for token in ["code", "file", "repo", "diff"]):
                bucket = "code"
            index[bucket].append({"name": tool.name, "description": tool.description, "risk_level": tool.risk_level.value, "required_scope": tool.required_scope, "parameters": tool.parameters_schema})
        return index

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def related_tools(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        scored: list[tuple[int, ToolDefinition]] = []
        for tool in self._tools.values():
            score = 0
            haystack = f"{tool.name} {tool.description} {tool.required_scope}".lower()
            for token in query_lower.split():
                if token and token in haystack:
                    score += 1
            if any(word in tool.name.lower() for word in ["read", "list", "search", "inspect"]):
                score += 1
            if any(word in tool.name.lower() for word in ["write", "edit", "update", "patch", "apply", "modify"]):
                score += 1
            if score > 0:
                scored.append((score, tool))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [
            {"name": tool.name, "description": tool.description, "risk_level": tool.risk_level.value, "required_scope": tool.required_scope, "parameters": tool.parameters_schema}
            for _, tool in scored[:8]
        ]

    async def execute(
        self,
        context: RunContext,
        name: str | None = None,
        arguments: dict[str, Any] | None = None,
        *,
        tool_name: str | None = None,
    ) -> ToolCallRecord:
        # ``tool_name`` is an alias for the positional ``name`` so callers can
        # write ``execute(context=ctx, tool_name="echo", arguments={...})``
        # (used by the agent-v2 integration suite). The positional form
        # ``execute(ctx, "echo", {...})`` remains unchanged.
        if name is None:
            name = tool_name
        if name is None:
            raise TypeError("execute() requires a tool name (positional `name` or `tool_name=`).")
        if arguments is None:
            arguments = {}
        started = time.perf_counter()
        arguments_preview = self._preview_arguments(arguments)
        tool = self._tools.get(name)
        if tool is None:
            verdict = self._policy.evaluate(context, name, RiskLevel.LOW)
            record = ToolCallRecord(
                tool_name=name,
                success=False,
                error=f"Unknown tool: {name}",
                policy=verdict,
                risk_level=RiskLevel.LOW,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        verdict = self._policy.evaluate(context, tool.name, tool.risk_level)
        if not verdict.allowed:
            approval_id = None
            if verdict.requires_approval and self._approval_store is not None:
                approval = self._approval_store.create_tool_approval(
                    context=context,
                    tool_name=tool.name,
                    risk_level=tool.risk_level,
                    reason=verdict.reason,
                    arguments_preview=arguments_preview,
                    arguments=arguments,
                )
                approval_id = approval.id
            error = verdict.reason
            if approval_id:
                error = f"{verdict.reason} Approval request: {approval_id}"
            record = ToolCallRecord(
                tool_name=name,
                success=False,
                error=error,
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        validation_error = self._validate_arguments(arguments, tool.parameters_schema)
        if validation_error:
            record = ToolCallRecord(
                tool_name=name,
                success=False,
                error=validation_error,
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        # PRE_TOOL_USE hooks (control plane). No-op when no hook manager.
        if self._hook_manager is not None:
            pre = await self._run_pre_tool_hooks(context, tool, arguments)
            if pre is not None:
                blocked_args, hook_error, approval_id = pre
                error = hook_error
                if approval_id:
                    error = f"{hook_error} Approval request: {approval_id}"
                record = ToolCallRecord(
                    tool_name=name,
                    success=False,
                    error=error,
                    policy=verdict,
                    risk_level=tool.risk_level,
                    latency_ms=self._elapsed_ms(started),
                    arguments_preview=self._preview_arguments(blocked_args),
                    trace_id=context.trace_id,
                    request_id=context.request_id,
                )
                self._record_execution(context, record)
                return record
            # A MODIFY decision may have rewritten arguments in place.
            arguments_preview = self._preview_arguments(arguments)

        try:
            output = await tool.handler(**arguments)
            # POST_TOOL_USE hooks may rewrite the output (no-op when none).
            if self._hook_manager is not None:
                output = await self._run_post_tool_hooks(
                    context, tool, arguments, output
                )
            record = ToolCallRecord(
                tool_name=name,
                success=True,
                output=output,
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record
        except Exception as exc:  # noqa: BLE001 - tool failures must be captured, not leaked
            record = ToolCallRecord(
                tool_name=name,
                success=False,
                error=str(exc),
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

    async def _run_pre_tool_hooks(
        self,
        context: RunContext,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str | None] | None:
        """Run PRE_TOOL_USE hooks before a tool handler executes.

        On DENY or ASK the call is stopped; for ASK an approval is created via
        the existing ``ApprovalStore`` when available. On MODIFY the
        ``arguments`` dict is rewritten in place so the handler receives the
        new payload. On ALLOW nothing happens.

        Args:
            context: Active run context.
            tool: The resolved tool definition.
            arguments: Mutable tool arguments (rewritten in place on MODIFY).

        Returns:
            ``None`` when execution may proceed. Otherwise a tuple of
            ``(arguments, reason, approval_id)`` describing why the call was
            blocked, used by the caller to build a failure record.
        """
        from backend.app.core.hooks import HookContext, HookEvent

        hook_ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            tool_name=tool.name,
            arguments=dict(arguments),
            trace_id=context.trace_id,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            risk_level=tool.risk_level.value,
        )
        result = await self._hook_manager.trigger(hook_ctx)

        if result.denied:
            return arguments, result.reason or "blocked by hook", None

        if result.needs_approval:
            approval_id: str | None = None
            if self._approval_store is not None:
                approval = self._approval_store.create_tool_approval(
                    context=context,
                    tool_name=tool.name,
                    risk_level=tool.risk_level,
                    reason=result.reason or "approval required by hook",
                    arguments_preview=self._preview_arguments(arguments),
                    arguments=arguments,
                )
                approval_id = approval.id
            return arguments, result.reason or "approval required by hook", approval_id

        if (
            result.final_action.value == "modify"
            and result.effective_arguments is not None
        ):
            arguments.clear()
            arguments.update(result.effective_arguments)

        return None

    async def _run_post_tool_hooks(
        self,
        context: RunContext,
        tool: ToolDefinition,
        arguments: dict[str, Any],
        output: Any,
    ) -> Any:
        """Run POST_TOOL_USE hooks after a tool handler returns.

        POST hooks observe and may rewrite the output. DENY/ASK are not
        meaningful post-execution and are treated as observations only.

        Args:
            context: Active run context.
            tool: The resolved tool definition.
            arguments: The arguments the handler ran with.
            output: The handler's raw output.

        Returns:
            The (possibly modified) output.
        """
        from backend.app.core.hooks import HookContext, HookEvent

        result_payload = output if isinstance(output, dict) else {"output": output}
        hook_ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            tool_name=tool.name,
            arguments=dict(arguments),
            result=dict(result_payload),
            trace_id=context.trace_id,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            risk_level=tool.risk_level.value,
        )
        result = await self._hook_manager.trigger(hook_ctx)
        if (
            result.final_action.value == "modify"
            and result.effective_result is not None
        ):
            return result.effective_result
        return output

    def get_execution_store(self) -> ToolExecutionStore | None:
        return self._execution_store

    async def execute_batch(
        self,
        context: RunContext,
        tool_calls: list[dict[str, Any]],
        allow_partial_failure: bool = True,
    ) -> list[ToolCallRecord]:
        """Execute multiple tool calls in parallel.

        Args:
            context: Execution context
            tool_calls: List of dicts with 'name' and 'arguments' keys
            allow_partial_failure: If False, stop on first failure

        Returns:
            List of ToolCallRecord objects
        """
        # Import here to avoid circular dependencies
        from backend.app.core.parallel_tool_executor import ParallelToolExecutor, ToolCall

        # Initialize parallel executor if needed
        executor = ParallelToolExecutor(
            tool_registry=self,
            cache=self._get_or_create_cache(),
            max_concurrent=10,
        )

        # Convert to ToolCall objects
        calls = [
            ToolCall(
                tool_name=call.get("name", ""),
                arguments=call.get("arguments", {}),
            )
            for call in tool_calls
        ]

        # Execute in parallel
        results = await executor.execute_batch(calls, context, allow_partial_failure)

        # Convert to ToolCallRecord objects
        records = []
        for result in results:
            record = ToolCallRecord(
                tool_name=result.tool_name,
                success=result.success,
                output=result.output,
                error=result.error,
                policy=self._approved_execution_verdict(
                    allowed=result.success,
                    reason="Batch execution" if result.success else result.error or "Unknown error",
                ),
                risk_level=RiskLevel.LOW,
                latency_ms=result.latency_ms,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            records.append(record)

        return records

    async def execute_batch_with_dependencies(
        self,
        context: RunContext,
        tool_calls: list[dict[str, Any]],
        allow_partial_failure: bool = True,
    ) -> dict[str, ToolCallRecord]:
        """Execute tool calls considering dependencies between them.

        Args:
            context: Execution context
            tool_calls: List of dicts with 'id', 'name', and 'arguments' keys
            allow_partial_failure: If False, stop on first failure

        Returns:
            Dictionary mapping call_id to ToolCallRecord
        """
        # Import here to avoid circular dependencies
        from backend.app.core.parallel_tool_executor import ParallelToolExecutor, ToolCall

        # Initialize parallel executor if needed
        executor = ParallelToolExecutor(
            tool_registry=self,
            cache=self._get_or_create_cache(),
            max_concurrent=10,
        )

        # Convert to ToolCall objects
        calls = [
            ToolCall(
                tool_name=call.get("name", ""),
                arguments=call.get("arguments", {}),
                call_id=call.get("id", __import__("uuid").uuid4().hex[:8]),
            )
            for call in tool_calls
        ]

        # Execute with dependencies
        results = await executor.execute_with_dependencies(calls, context, allow_partial_failure)

        # Convert to ToolCallRecord objects
        records = {}
        for call_id, result in results.items():
            record = ToolCallRecord(
                tool_name=result.tool_name,
                success=result.success,
                output=result.output,
                error=result.error,
                policy=self._approved_execution_verdict(
                    allowed=result.success,
                    reason="Batch execution" if result.success else result.error or "Unknown error",
                ),
                risk_level=RiskLevel.LOW,
                latency_ms=result.latency_ms,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            records[call_id] = record

        return records

    def _get_or_create_cache(self) -> Any:
        """Get or create the tool result cache."""
        global _tool_result_cache
        if _tool_result_cache is None:
            from backend.app.core.tool_result_cache import ToolResultCache

            _tool_result_cache = ToolResultCache(max_size=1000, default_ttl=300)
        return _tool_result_cache

    def _record_execution(self, context: RunContext, record: ToolCallRecord) -> None:
        if self._execution_store is not None:
            self._execution_store.record(context, record)

    @staticmethod
    def _build_rollback_artifact(tool_name: str, arguments: dict[str, Any], output: Any) -> dict[str, Any]:
        artifact: dict[str, Any] = {"tool_name": tool_name, "arguments": arguments}
        if isinstance(output, dict):
            if "path" in output:
                artifact["path"] = output.get("path")
            if "previous_size" in output:
                artifact["previous_size"] = output.get("previous_size")
            if "current_size" in output:
                artifact["current_size"] = output.get("current_size")
            if "verified" in output:
                artifact["verified"] = output.get("verified")
            if "applied" in output:
                artifact["applied"] = output.get("applied")
        return artifact

    async def execute_approved(self, context: RunContext, approval_id: str) -> ToolCallRecord:
        started = time.perf_counter()
        denied = self._approved_execution_verdict(allowed=False, reason="Approval unavailable.")
        if self._approval_store is None:
            record = ToolCallRecord(
                tool_name="approval",
                success=False,
                error="Approval store is not configured.",
                policy=denied,
                latency_ms=self._elapsed_ms(started),
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        approval = self._approval_store.get(approval_id)
        if approval is None:
            record = ToolCallRecord(
                tool_name="approval",
                success=False,
                error=f"Approval request not found: {approval_id}",
                policy=denied,
                latency_ms=self._elapsed_ms(started),
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record
        if approval.tenant_id != context.tenant_id:
            record = ToolCallRecord(
                tool_name=approval.resource_id,
                success=False,
                error="Approval tenant does not match execution context.",
                policy=denied,
                risk_level=approval.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record
        if approval.status != ApprovalStatus.APPROVED:
            record = ToolCallRecord(
                tool_name=approval.resource_id,
                success=False,
                error=f"Approval request is {approval.status.value}, not approved.",
                policy=denied,
                risk_level=approval.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record
        if approval.resource_type != "tool" or approval.action != "tool.execute":
            record = ToolCallRecord(
                tool_name=approval.resource_id,
                success=False,
                error="Approval request is not a tool execution approval.",
                policy=denied,
                risk_level=approval.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        tool = self._tools.get(approval.resource_id)
        if tool is None:
            record = ToolCallRecord(
                tool_name=approval.resource_id,
                success=False,
                error=f"Unknown tool: {approval.resource_id}",
                policy=denied,
                risk_level=approval.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        verdict = self._approved_execution_verdict(
            allowed=True,
            reason=f"Approved by {approval.decided_by or 'unknown approver' }.",
        )
        validation_error = self._validate_arguments(approval.arguments, tool.parameters_schema)
        if validation_error:
            record = ToolCallRecord(
                tool_name=tool.name,
                success=False,
                error=validation_error,
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

        try:
            output = await tool.handler(**approval.arguments)
            rollback_artifact = self._build_rollback_artifact(tool.name, approval.arguments, output)
            self._approval_store.mark_executed(
                approval.id,
                executed_by=context.user_id,
                execution_trace_id=context.trace_id,
                linked_policy_trace_id=approval.linked_policy_trace_id,
            )
            record = ToolCallRecord(
                tool_name=tool.name,
                success=True,
                output=output,
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record
        except Exception as exc:  # noqa: BLE001 - approved tool failures are result data
            record = ToolCallRecord(
                tool_name=tool.name,
                success=False,
                error=str(exc),
                policy=verdict,
                risk_level=tool.risk_level,
                latency_ms=self._elapsed_ms(started),
                arguments_preview=approval.arguments_preview,
                trace_id=context.trace_id,
                request_id=context.request_id,
            )
            self._record_execution(context, record)
            return record

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)

    @staticmethod
    def _approved_execution_verdict(*, allowed: bool, reason: str) -> ToolPolicyVerdict:
        return ToolPolicyVerdict(
            allowed=allowed,
            requires_approval=False,
            sandbox_profile="approved" if allowed else "locked",
            reason=reason,
            approval_id=None,
        )

    @staticmethod
    def _preview_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
        preview: dict[str, Any] = {}
        for key, value in arguments.items():
            text = str(value)
            preview[key] = text if len(text) <= 120 else text[:117] + "..."
        return preview

    @staticmethod
    def _schema_from_signature(handler: ToolHandler) -> dict[str, Any]:
        signature = inspect.signature(handler)
        properties = {}
        required = []
        for name, parameter in signature.parameters.items():
            properties[name] = {
                "type": ToolRegistry._json_schema_type(parameter.annotation),
                "description": f"Argument {name}",
            }
            if parameter.default is inspect.Parameter.empty:
                required.append(name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    @staticmethod
    def _json_schema_type(annotation: Any) -> str:
        if annotation in {int, "int"}:
            return "integer"
        if annotation in {float, "float"}:
            return "number"
        if annotation in {bool, "bool"}:
            return "boolean"
        if annotation in {dict, "dict"}:
            return "object"
        if annotation in {list, "list"}:
            return "array"
        return "string"

    @staticmethod
    def _validate_arguments(arguments: dict[str, Any], schema: dict[str, Any]) -> str | None:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for name in required:
            if name not in arguments:
                return f"Missing required argument: {name}"

        if schema.get("additionalProperties") is False:
            unknown = sorted(set(arguments) - set(properties))
            if unknown:
                return f"Unknown arguments: {', '.join(unknown)}"

        for name, value in arguments.items():
            expected_type = properties.get(name, {}).get("type")
            if expected_type and not ToolRegistry._matches_json_type(value, expected_type):
                return f"Argument {name} must be {expected_type}."
        return None

    @staticmethod
    def _matches_json_type(value: Any, expected_type: str) -> bool:
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True
        if expected_type == "integer" and isinstance(value, bool):
            return False
        if expected_type == "number" and isinstance(value, bool):
            return False
        return isinstance(value, expected)


async def echo(text: str) -> str:
    return text


async def list_files(root: str = ".", pattern: str = "**/*", limit: int = 200) -> list[str]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return []
    items: list[str] = []
    for path in sorted(base.glob(pattern)):
        if len(items) >= max(1, limit):
            break
        if path.is_file():
            items.append(str(path.relative_to(base)))
    return items


async def inspect_tree(root: str = ".", limit: int = 200) -> dict[str, Any]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return {"root": str(base), "files": [], "directories": []}
    files: list[str] = []
    directories: list[str] = []
    for path in sorted(base.rglob("*")):
        if path.is_dir():
            directories.append(str(path.relative_to(base)))
        elif path.is_file():
            files.append(str(path.relative_to(base)))
        if len(files) >= max(1, limit) and len(directories) >= max(1, limit):
            break
    return {"root": str(base), "files": files[:limit], "directories": directories[:limit], "file_count": len(files), "directory_count": len(directories)}


async def coordinate_files(root: str, targets: list[str], query: str = "", limit: int = 5) -> dict[str, Any]:
    base = _resolve_tool_root(root)
    selected = []
    for target in targets[: max(1, limit)]:
        path = _resolve_tool_path(str(base / target))
        if path.exists() and path.is_file():
            selected.append({"path": str(path), "size": path.stat().st_size})
    return {"root": str(base), "query": query, "targets": selected, "count": len(selected)}


async def analyze_entrypoints(root: str = ".", limit: int = 50) -> dict[str, Any]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return {"root": str(base), "entrypoints": []}
    candidates = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".html"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        score = 0
        lowered = text.lower()
        if any(token in lowered for token in ["fastapi", "router =", "app =", "create_app", "main()", "if __name__ == '__main__'"]):
            score += 2
        if any(token in lowered for token in ["@router", "@app", "export default", "function app(", "document.addEventListener"]):
            score += 1
        if path.name in {"main.py", "app.py", "index.ts", "index.tsx", "index.js", "index.jsx", "index.html"}:
            score += 1
        if score > 0:
            candidates.append({"path": str(path.relative_to(base)), "score": score, "kind": path.suffix.lower().lstrip('.')})
    candidates.sort(key=lambda item: (-item["score"], item["path"]))
    return {"root": str(base), "entrypoints": candidates[: max(1, limit)], "count": len(candidates)}


async def analyze_dependencies(root: str = ".", limit: int = 100) -> dict[str, Any]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return {"root": str(base), "dependencies": []}
    files = [path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}]
    index: dict[str, list[str]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        imports = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from ") or stripped.startswith("const ") or stripped.startswith("export "):
                imports.append(stripped[:160])
        index[str(path.relative_to(base))] = imports[:20]
    hotspots = sorted(index.items(), key=lambda item: (-len(item[1]), item[0]))
    dependencies = [{"path": path, "import_count": len(imports), "imports": imports[:10]} for path, imports in hotspots[: max(1, limit)]]
    return {"root": str(base), "dependencies": dependencies, "count": len(index)}


async def assess_change_impact(root: str = ".", target: str = "", query: str = "", limit: int = 10) -> dict[str, Any]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return {"root": str(base), "impact": []}
    deps = await analyze_dependencies(root=root, limit=max(20, limit * 3))
    entrypoints = await analyze_entrypoints(root=root, limit=max(10, limit))
    target_norm = target.replace("\\", "/").strip().lower()
    query_terms = [term for term in query.lower().split() if term]
    scored: list[dict[str, Any]] = []
    for item in deps.get("dependencies", []):
        path = str(item.get("path", ""))
        lowered = path.lower().replace("\\", "/")
        score = int(item.get("import_count", 0))
        if target_norm and (target_norm in lowered or lowered in target_norm):
            score += 5
        if query_terms and any(term in lowered for term in query_terms):
            score += 2
        if any(ep.get("path") and ep["path"].lower() in lowered for ep in entrypoints.get("entrypoints", [])):
            score += 3
        scored.append({"path": path, "score": score, "import_count": item.get("import_count", 0), "imports": item.get("imports", [])})
    scored.sort(key=lambda item: (-item["score"], item["path"]))
    return {
        "root": str(base),
        "target": target,
        "query": query,
        "impact": scored[: max(1, limit)],
        "entrypoints": entrypoints.get("entrypoints", [])[: max(1, limit)],
    }


async def assess_change_impact(root: str = ".", target: str = "", limit: int = 20) -> dict[str, Any]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return {"root": str(base), "impact": []}
    target_name = Path(target).name.lower() if target else ""
    entrypoints = await analyze_entrypoints(root, limit=limit)
    dependencies = await analyze_dependencies(root, limit=limit)
    impact: list[dict[str, Any]] = []
    for item in entrypoints.get("entrypoints", []):
        score = int(item.get("score", 0)) + (1 if target_name and target_name in str(item.get("path", "")).lower() else 0)
        impact.append({"path": item.get("path"), "reason": "entrypoint", "score": score})
    for item in dependencies.get("dependencies", []):
        score = int(item.get("import_count", 0)) + (1 if target_name and target_name in str(item.get("path", "")).lower() else 0)
        impact.append({"path": item.get("path"), "reason": "dependency_hotspot", "score": score})
    if target:
        impact.append({"path": target, "reason": "target", "score": 100})
    impact.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("path", ""))))
    unique: dict[str, dict[str, Any]] = {}
    for item in impact:
        path = str(item.get("path", ""))
        if path and path not in unique:
            unique[path] = item
    return {"root": str(base), "target": target, "impact": list(unique.values())[: max(1, limit)], "count": len(unique)}


async def preview_batch_patches(patches: list[dict[str, Any]], root: str = ".") -> dict[str, Any]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return {"root": str(base), "previewed": []}
    results: list[dict[str, Any]] = []
    for patch in patches:
        result = await preview_text_patch(
            path=str(patch.get("path", "")),
            old_text=str(patch.get("old_text", "")),
            new_text=str(patch.get("new_text", "")),
            replace_all=bool(patch.get("replace_all", False)),
        )
        results.append(result)
    success_count = sum(1 for item in results if item.get("previewed") and not item.get("error"))
    return {"root": str(base), "previewed": results, "success_count": success_count, "total_count": len(patches)}


async def read_file(path: str, limit: int = 4000) -> str:
    file_path = _resolve_tool_path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    return file_path.read_text(encoding="utf-8", errors="ignore")[: max(0, limit)]


async def write_file(path: str, content: str, backup: bool = True) -> dict[str, Any]:
    file_path = _resolve_tool_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    previous = file_path.read_text(encoding="utf-8", errors="ignore") if file_path.exists() else ""
    if backup and file_path.exists():
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        backup_path.write_text(previous, encoding="utf-8")
    file_path.write_text(content, encoding="utf-8")
    return {"path": str(file_path), "written": True, "previous_size": len(previous), "current_size": len(content)}


async def preview_text_patch(path: str, old_text: str, new_text: str, replace_all: bool = False) -> dict[str, Any]:
    file_path = _resolve_tool_path(path)
    if not file_path.exists() or not file_path.is_file():
        return {"path": str(file_path), "previewed": False, "error": "file_not_found"}
    original = file_path.read_text(encoding="utf-8", errors="ignore")
    count = original.count(old_text)
    if count == 0:
        return {"path": str(file_path), "previewed": False, "error": "pattern_not_found", "match_count": 0}
    if not replace_all and count > 1:
        return {"path": str(file_path), "previewed": False, "error": "ambiguous_match", "match_count": count}
    updated = original.replace(old_text, new_text, 1 if not replace_all else -1)
    return {
        "path": str(file_path),
        "previewed": True,
        "replace_all": replace_all,
        "match_count": count,
        "previous_size": len(original),
        "current_size": len(updated),
        "delta": len(updated) - len(original),
    }


async def apply_text_patch(path: str, old_text: str, new_text: str, replace_all: bool = False, backup: bool = True) -> dict[str, Any]:
    file_path = _resolve_tool_path(path)
    if not file_path.exists() or not file_path.is_file():
        return {"path": str(file_path), "applied": False, "error": "file_not_found"}
    original = file_path.read_text(encoding="utf-8", errors="ignore")
    count = original.count(old_text)
    if count == 0:
        return {"path": str(file_path), "applied": False, "error": "pattern_not_found", "match_count": 0}
    if not replace_all and count > 1:
        return {"path": str(file_path), "applied": False, "error": "ambiguous_match", "match_count": count}
    updated = original.replace(old_text, new_text, 1 if not replace_all else -1)
    if backup:
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        backup_path.write_text(original, encoding="utf-8")
    file_path.write_text(updated, encoding="utf-8")
    verified = file_path.read_text(encoding="utf-8", errors="ignore")
    return {
        "path": str(file_path),
        "applied": True,
        "verified": verified == updated,
        "replace_all": replace_all,
        "match_count": count,
        "previous_size": len(original),
        "current_size": len(updated),
    }


async def apply_batch_patch(patches: list[dict[str, Any]], backup: bool = True) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    success_count = 0
    for patch in patches:
        result = await apply_text_patch(
            path=str(patch.get("path", "")),
            old_text=str(patch.get("old_text", "")),
            new_text=str(patch.get("new_text", "")),
            replace_all=bool(patch.get("replace_all", False)),
            backup=backup,
        )
        results.append(result)
        if result.get("applied") and result.get("verified"):
            success_count += 1
    return {"applied": success_count == len(patches) and bool(patches), "success_count": success_count, "total_count": len(patches), "results": results}


async def search_text(root: str, query: str, pattern: str = "**/*", limit: int = 20) -> list[dict[str, str]]:
    base = _resolve_tool_root(root)
    if not base.exists():
        return []
    results: list[dict[str, str]] = []
    lowered = query.lower()
    for path in sorted(base.glob(pattern)):
        if len(results) >= max(1, limit):
            break
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if lowered in text.lower():
            results.append({"path": str(path.relative_to(base)), "match": query})
    return results


async def summarize_text(text: str) -> str:
    trimmed = " ".join(text.split())
    if len(trimmed) <= 160:
        return trimmed
    return trimmed[:157] + "..."


async def normalize_text(text: str) -> str:
    return " ".join(text.split())


async def extract_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = []
    for token in text.replace("\n", " ").split():
        cleaned = token.strip(".,;:!?()[]{}<>\"'`~@#$%^&*-+=|\\/")
        if len(cleaned) < 3:
            continue
        lowered = cleaned.lower()
        if lowered not in tokens:
            tokens.append(lowered)
        if len(tokens) >= max(1, limit):
            break
    return tokens


def build_default_tool_registry(
    policy_engine: ToolPolicyEngine,
    approval_store: ApprovalStore | None = None,
    execution_store: ToolExecutionStore | None = None,
    hook_manager: "HookManager | None" = None,
) -> ToolRegistry:
    # Attach the process-global HookManager by default so configured hooks
    # fire at the execute() chokepoint. An empty manager (no hooks registered)
    # is a perfect no-op, so this stays backward compatible. The import is lazy
    # to keep the hooks package off the tools.py module-import path (avoids the
    # circular import; hooks/ never imports tools).
    if hook_manager is None:
        from backend.app.core.hooks import get_hook_manager

        hook_manager = get_hook_manager()
    registry = ToolRegistry(
        policy_engine,
        approval_store=approval_store,
        execution_store=execution_store,
        hook_manager=hook_manager,
    )
    registry.register("echo", "Echo text back to the caller.", echo)
    registry.register("list_files", "List files under a root directory.", list_files)
    registry.register("inspect_tree", "Inspect directories and files under a root directory.", inspect_tree)
    registry.register("coordinate_files", "Coordinate a focused set of files for a task.", coordinate_files)
    registry.register("analyze_entrypoints", "Analyze likely application entrypoints in the repository.", analyze_entrypoints)
    registry.register("analyze_dependencies", "Analyze likely imports and dependency hotspots in the repository.", analyze_dependencies)
    registry.register("assess_change_impact", "Assess likely impact areas before making a change.", assess_change_impact)
    registry.register("read_file", "Read a text file from disk.", read_file)
    registry.register("preview_batch_patches", "Preview a batch of focused text replacement patches.", preview_batch_patches)
    registry.register("preview_text_patch", "Preview a focused text replacement patch without writing.", preview_text_patch)
    registry.register("write_file", "Write a text file to disk with optional backup.", write_file, risk_level=RiskLevel.HIGH)
    registry.register("apply_text_patch", "Apply a focused text replacement patch to a file.", apply_text_patch, risk_level=RiskLevel.HIGH)
    registry.register("apply_batch_patch", "Apply a batch of focused text replacement patches.", apply_batch_patch, risk_level=RiskLevel.HIGH)
    registry.register("search_text", "Search for text across files under a root directory.", search_text)
    registry.register("summarize_text", "Summarize a short text locally.", summarize_text)
    registry.register("normalize_text", "Normalize whitespace in text.", normalize_text)
    registry.register("extract_keywords", "Extract simple keywords from text.", extract_keywords)
    return registry
