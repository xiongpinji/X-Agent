"""Runtime task delegation for multi-agent collaboration (P1-09).

This module is the live runtime path that turns routing into execution:

    caller (AgentLoop tool / API) -> CollaborationDelegator.delegate()
        -> candidate pool (explicit specs + org store + room members)
        -> capability match (required scopes/tags subset of candidate caps)
        -> round-robin pick (RoundRobinBalancer)
        -> core.dispatch.dispatch() suggestion ranks the pool when
           org/department/agent hints are present (dispatch.py is thus part of
           the runtime path, not just a suggest-only endpoint)
        -> agent_spawner.spawn_agent() runs a REAL AgentLoop for the sub-agent
        -> optional wait + result callback into the collaboration room

Honesty rules enforced here:

- No capable candidate -> :class:`NoCapableAgentError` (never silently falls
  back to an unqualified agent).
- ``wait=True`` timeout -> explicit ``status="timeout"`` result.
- Unsupported isolation levels raise from the spawner (CONTAINER points to the
  sandbox path).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, Callable, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.agent_spawner import AgentSpawner, agent_spawner
from backend.app.core.collaboration.store import CollaborationStore, collaboration_store

# NOTE: core.dispatch is imported lazily inside ``_build_candidate_pool`` —
# dispatch.py itself imports this package, so a top-level import would be
# circular.


class DelegationError(RuntimeError):
    """Base error for delegation failures."""


class NoCapableAgentError(DelegationError):
    """Raised when no candidate satisfies the required capabilities.

    Carries the requirement and the pool for observability; callers (API
    layer) should surface this as an explicit client-visible error.
    """

    def __init__(self, required: Sequence[str], pool: Sequence["CandidateSpec"]) -> None:
        self.required = list(required)
        self.pool_ids = [candidate.agent_id for candidate in pool]
        super().__init__(
            "No capable agent found: required capabilities "
            f"{self.required!r} not satisfied by any candidate in pool "
            f"{self.pool_ids!r}. Register a candidate with matching "
            "capabilities or relax the requirement."
        )


class CandidateSpec(BaseModel):
    """A delegation candidate (sub-agent identity + capabilities)."""

    agent_id: str
    agent_type: str = "subagent"
    capabilities: list[str] = Field(default_factory=list)
    source: str = "explicit"  # explicit | org | room


class DelegationRequest(BaseModel):
    """Request to delegate a task to a capability-matched sub-agent."""

    task: str = Field(..., min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)
    candidates: list[CandidateSpec] = Field(default_factory=list)
    org_id: str | None = None
    department_id: str | None = None
    room_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "system"
    isolation: str | None = None  # none | thread | process (container -> explicit error)
    wait: bool = True
    timeout_seconds: int = Field(default=600, ge=1, le=86400)
    max_iterations: int = Field(default=10, ge=1, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DelegationResult(BaseModel):
    """Outcome of a delegation attempt."""

    delegation_id: str
    status: str  # completed | failed | timeout | running
    task: str
    spawned_agent_id: str | None = None
    selected_candidate: CandidateSpec | None = None
    matched_candidate_ids: list[str] = Field(default_factory=list)
    pool_size: int = 0
    balancer: str = "round_robin"
    dispatch_evidence: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    room_id: str | None = None
    tenant_id: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


def normalize_capabilities(capabilities: Sequence[str]) -> set[str]:
    """Case-insensitive normalization for capability matching."""
    return {str(cap).strip().lower() for cap in capabilities if str(cap).strip()}


def capability_match(candidate: CandidateSpec, required: Sequence[str]) -> bool:
    """A candidate matches iff every required capability is covered.

    An empty requirement matches every candidate. Matching is
    case-insensitive; capabilities double as scopes/tags by convention.
    """
    needed = normalize_capabilities(required)
    if not needed:
        return True
    return needed.issubset(normalize_capabilities(candidate.capabilities))


class RoundRobinBalancer:
    """Thread-safe round-robin picker, keyed per candidate-pool signature.

    The cursor advances per pool key, so repeated delegations over the same
    matched pool rotate through all members (minimal load balancing).
    """

    def __init__(self) -> None:
        self._cursors: dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def pool_key(tenant_id: str, candidates: Sequence[CandidateSpec]) -> str:
        ids = ",".join(sorted(candidate.agent_id for candidate in candidates))
        return f"{tenant_id}|{ids}"

    def pick(self, pool_key: str, candidates: Sequence[CandidateSpec]) -> CandidateSpec:
        if not candidates:
            raise DelegationError("RoundRobinBalancer.pick called with an empty pool.")
        with self._lock:
            cursor = self._cursors.get(pool_key, 0)
            self._cursors[pool_key] = cursor + 1
        return candidates[cursor % len(candidates)]

    def cursor(self, pool_key: str) -> int:
        with self._lock:
            return self._cursors.get(pool_key, 0)


class CollaborationDelegator:
    """Delegates tasks to real sub-agents with capability match + round-robin."""

    def __init__(
        self,
        *,
        spawner: AgentSpawner | None = None,
        store: CollaborationStore | None = None,
        balancer: RoundRobinBalancer | None = None,
        dispatch_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._spawner = spawner if spawner is not None else agent_spawner
        self._store = store if store is not None else collaboration_store
        self._balancer = balancer if balancer is not None else RoundRobinBalancer()
        # ``None`` resolves lazily on first use — the module-level singleton is
        # constructed at import time, when core.dispatch may still be partially
        # initialized (it imports this package).
        self._dispatch_fn = dispatch_fn
        self._history: dict[str, DelegationResult] = {}

    async def delegate(self, request: DelegationRequest) -> DelegationResult:
        """Delegate ``request.task`` to a matched sub-agent running a real AgentLoop.

        Raises:
            NoCapableAgentError: No candidate satisfies the required
                capabilities (explicit — never silently falls back).
            ValueError / NotImplementedError: Invalid isolation input from the
                spawner contract.
        """
        delegation_id = f"dlg_{uuid4().hex[:12]}"
        pool, dispatch_evidence = self._build_candidate_pool(request)
        matched = [candidate for candidate in pool if capability_match(candidate, request.required_capabilities)]
        if not matched:
            raise NoCapableAgentError(request.required_capabilities, pool)

        pool_key = RoundRobinBalancer.pool_key(request.tenant_id, matched)
        target = self._balancer.pick(pool_key, matched)

        trace_id = str(request.metadata.get("trace_id") or delegation_id)
        context = {
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "delegation_id": delegation_id,
            "trace_id": trace_id,
            "request_id": str(request.metadata.get("request_id") or delegation_id),
            "room_id": request.room_id or "",
            "required_capabilities": list(request.required_capabilities),
            "delegator": str(request.metadata.get("delegator") or "collaboration-delegator"),
            **dict(request.metadata.get("context") or {}),
        }
        spawned_agent_id = await self._spawner.spawn_agent(
            agent_type=target.agent_type,
            task=request.task,
            context=context,
            isolation=request.isolation,
            max_iterations=request.max_iterations,
            timeout_seconds=request.timeout_seconds,
            metadata={"delegation_id": delegation_id, "candidate": target.agent_id},
        )

        status = "running"
        result_payload: dict[str, Any] | None = None
        error: str | None = None
        if request.wait:
            final = await self._spawner.wait_for_agent(spawned_agent_id, timeout_seconds=request.timeout_seconds)
            if final is None:
                status = "timeout"
                error = f"Sub-agent {spawned_agent_id} did not finish within {request.timeout_seconds}s."
            else:
                status = str(final.get("status") or "completed")
                result_payload = final.get("result")
                error = final.get("error")
                if status not in {"completed", "failed"}:
                    # initializing/ready/running/terminated surface verbatim;
                    # anything unexpected is still explicit, never silent.
                    error = error or f"Sub-agent ended in unexpected status: {status}"

        completed_at = datetime.now(UTC) if status != "running" else None
        result = DelegationResult(
            delegation_id=delegation_id,
            status=status,
            task=request.task,
            spawned_agent_id=spawned_agent_id,
            selected_candidate=target,
            matched_candidate_ids=[candidate.agent_id for candidate in matched],
            pool_size=len(pool),
            balancer="round_robin",
            dispatch_evidence=dispatch_evidence,
            result=result_payload,
            error=error,
            room_id=request.room_id,
            tenant_id=request.tenant_id,
            completed_at=completed_at,
        )
        self._history[delegation_id] = result

        if request.room_id:
            self._post_room_callback(request, result)
        return result

    def get_delegation(self, delegation_id: str) -> DelegationResult | None:
        return self._history.get(delegation_id)

    def list_delegations(self, *, tenant_id: str | None = None, limit: int = 50) -> list[DelegationResult]:
        items = list(self._history.values())
        if tenant_id is not None:
            items = [item for item in items if item.tenant_id == tenant_id]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[: max(1, limit)]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_candidate_pool(self, request: DelegationRequest) -> tuple[list[CandidateSpec], dict[str, Any]]:
        """Assemble the candidate pool and (optionally) dispatch-based ranking.

        Sources, in priority order: explicit candidates from the request, org
        store agents (when org/department hints are given), and room members
        (when a room is given). When org context exists, core.dispatch's
        suggestion ranks org candidates first (leader, then selected agents) —
        that call is what wires dispatch.py into the live runtime path.
        """
        pool: list[CandidateSpec] = []
        seen: set[str] = set()

        def _add(candidate: CandidateSpec) -> None:
            if candidate.agent_id and candidate.agent_id not in seen:
                seen.add(candidate.agent_id)
                pool.append(candidate)

        for candidate in request.candidates:
            _add(candidate)

        org_agents: list[Any] = []
        if request.org_id or request.department_id:
            from backend.app.core import org as org_core

            org_agents = org_core.organization_store.list_agents(
                org_id=request.org_id,
                department_id=request.department_id,
            )
            for node in org_agents:
                _add(
                    CandidateSpec(
                        agent_id=node.agent_id,
                        agent_type=f"org:{getattr(node.role, 'value', node.role)}",
                        capabilities=list(node.capabilities or []),
                        source="org",
                    )
                )

        if request.room_id:
            room = self._store.get_room(request.room_id)
            if room is not None:
                for member_id in room.members:
                    _add(CandidateSpec(agent_id=str(member_id), source="room"))

        evidence: dict[str, Any] = {}
        if (request.org_id or request.department_id) and org_agents:
            from backend.app.core.dispatch import DispatchRequest

            if self._dispatch_fn is None:
                from backend.app.core.dispatch import dispatch as suggest_dispatch

                self._dispatch_fn = suggest_dispatch

            suggestion = self._dispatch_fn(
                DispatchRequest(
                    org_id=request.org_id,
                    department_id=request.department_id,
                    agent_id=str(request.metadata.get("agent_id") or "") or None,
                    room_id=request.room_id,
                    task=request.task,
                    mode="auto",
                )
            ).suggestion
            preferred_ids: list[str] = []
            leader = suggestion.selected_leader or {}
            if leader.get("agent_id"):
                preferred_ids.append(str(leader["agent_id"]))
            for agent in suggestion.selected_agents:
                if isinstance(agent, dict) and agent.get("agent_id"):
                    preferred_ids.append(str(agent["agent_id"]))
            if preferred_ids:
                rank = {agent_id: index for index, agent_id in enumerate(preferred_ids)}
                original_positions = {candidate.agent_id: index for index, candidate in enumerate(pool)}
                pool.sort(
                    key=lambda candidate: (
                        rank.get(candidate.agent_id, len(rank)),
                        original_positions[candidate.agent_id],
                    )
                )
            evidence = {
                "dispatch_used": True,
                "preferred_agent_ids": preferred_ids,
                "confidence": suggestion.confidence,
            }
        else:
            evidence = {"dispatch_used": False, "reason": "no org/department context"}

        if not pool and not request.required_capabilities:
            # Zero-config path: no roster anywhere and nothing specific
            # required -> a single implicit generalist keeps the delegation
            # tool usable. Capability-requiring requests do NOT get this
            # fallback (they must fail explicitly instead).
            pool.append(CandidateSpec(agent_id="generalist", source="implicit"))
            evidence["implicit_generalist"] = True

        return pool, evidence

    def _post_room_callback(self, request: DelegationRequest, result: DelegationResult) -> None:
        """Report the delegation outcome back into the collaboration room."""
        room = self._store.get_room(request.room_id or "")
        if room is None:
            return
        answer = ""
        if isinstance(result.result, dict):
            answer = str(result.result.get("answer") or "")
        excerpt = answer[:500] + ("…" if len(answer) > 500 else "")
        content = (
            f"[delegation {result.delegation_id}] status={result.status} "
            f"target={result.spawned_agent_id} candidate={result.selected_candidate.agent_id if result.selected_candidate else '-'}"
            + (f"\n{excerpt}" if excerpt else "")
            + (f"\nerror: {result.error}" if result.error else "")
        )
        self._store.post_message(
            room.room_id,
            sender_id=str(request.metadata.get("agent_id") or "delegator"),
            sender_type="agent",
            content=content,
            metadata={
                "delegation_id": result.delegation_id,
                "spawned_agent_id": result.spawned_agent_id or "",
                "status": result.status,
                "agent_id": str(request.metadata.get("agent_id") or "delegator"),
                "department_id": request.department_id or "",
            },
        )


async def delegate_subtask(
    task: str,
    required_capabilities: str = "",
    room_id: str = "",
    timeout_seconds: int = 600,
    isolation: str = "none",
) -> dict[str, Any]:
    """Delegate a subtask to a capability-matched sub-agent (AgentLoop tool).

    The sub-agent runs a real AgentLoop via the agent spawner; candidates are
    filtered by ``required_capabilities`` (comma-separated scopes/tags) and
    picked round-robin for load balancing. The final answer is returned and,
    when ``room_id`` is given, also posted back into the collaboration room.

    Integration wiring (integration wave): register this function in
    ``backend/app/core/tools.py`` ``build_default_tool_registry`` as
    ``registry.register("delegate_subtask", "Delegate a subtask to a capability-matched sub-agent.", delegate_subtask)``.
    """
    capabilities = [cap.strip() for cap in required_capabilities.split(",") if cap.strip()]
    delegator = get_delegator()
    result = await delegator.delegate(
        DelegationRequest(
            task=task,
            required_capabilities=capabilities,
            room_id=room_id or None,
            timeout_seconds=max(1, int(timeout_seconds)),
            isolation=isolation or None,
        )
    )
    return result.model_dump(mode="json")


# Module-level singletons (import-safe: no side effects beyond construction).
delegator = CollaborationDelegator()


def get_delegator() -> CollaborationDelegator:
    return delegator
