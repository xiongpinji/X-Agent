from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core import collaboration as collaboration_core
from backend.app.core import memory as memory_core
from backend.app.core import org as org_core


class DispatchRequest(BaseModel):
    org_id: str | None = None
    department_id: str | None = None
    agent_id: str | None = None
    room_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    task: str = Field(..., min_length=1)
    task_type: str | None = None
    priority: int = 0
    summary: str | None = None
    mode: Literal["auto", "suggest", "force"] = "auto"
    memory_layer_hint: list[int] | None = None
    memory_scope_hint: dict[str, str] | None = None
    collaboration_hint: dict[str, str] | None = None
    replay_hint: bool = False


class DispatchContext(BaseModel):
    trace_id: str
    org_id: str | None = None
    department_id: str | None = None
    agent_id: str | None = None
    room_id: str | None = None
    session_id: str | None = None
    task: str
    task_type: str | None = None
    priority: int = 0
    mode: str = "auto"
    memory_layer_hint: list[int] = Field(default_factory=list)
    memory_scope_hint: dict[str, str] = Field(default_factory=dict)
    collaboration_hint: dict[str, str] = Field(default_factory=dict)
    replay_hint: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DispatchDecisionPath(BaseModel):
    step: str
    name: str
    input: dict[str, object] = Field(default_factory=dict)
    output: dict[str, object] = Field(default_factory=dict)
    reason: str = ""
    confidence: float = 0.0


class DispatchReasonPart(BaseModel):
    category: str
    label: str
    detail: str
    weight: float = 0.0
    evidence: dict[str, object] = Field(default_factory=dict)


class DispatchReason(BaseModel):
    summary: str = ""
    parts: list[DispatchReasonPart] = Field(default_factory=list)
    confidence: float = 0.0
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class DispatchAction(BaseModel):
    action: str
    target: str | None = None
    reason: str = ""
    priority: int = 0
    required_scope: list[str] = Field(default_factory=list)
    blocking_conditions: list[str] = Field(default_factory=list)
    parameters: dict[str, object] = Field(default_factory=dict)


class DispatchWorkflowStep(BaseModel):
    step_id: str
    name: str
    action: str
    target: str | None = None
    reason: str = ""
    priority: int = 0
    required_scope: list[str] = Field(default_factory=list)
    parameters: dict[str, object] = Field(default_factory=dict)
    blocking_conditions: list[str] = Field(default_factory=list)


class DispatchSuggestion(BaseModel):
    selected_org: dict[str, object] | None = None
    selected_department: dict[str, object] | None = None
    selected_leader: dict[str, object] | None = None
    selected_agents: list[dict[str, object]] = Field(default_factory=list)
    selected_room: dict[str, object] | None = None
    memory_summary: dict[str, object] | None = None
    memory_layers: list[dict[str, object]] = Field(default_factory=list)
    session_summary: dict[str, object] | None = None
    agent_memory: dict[str, object] | None = None
    department_memory: dict[str, object] | None = None
    collaboration_rooms: list[dict[str, object]] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    agent_memory_refs: dict[str, list[str]] = Field(default_factory=dict)
    department_memory_refs: dict[str, list[str]] = Field(default_factory=dict)
    replay_hints: dict[str, object] = Field(default_factory=dict)
    audit_hints: dict[str, object] = Field(default_factory=dict)
    recovery_hints: dict[str, object] = Field(default_factory=dict)
    confidence: float = 0.0
    reason: DispatchReason = Field(default_factory=DispatchReason)
    decision_path: list[DispatchDecisionPath] = Field(default_factory=list)
    next_actions: list[DispatchAction] = Field(default_factory=list)


class DispatchResult(BaseModel):
    request: DispatchRequest
    suggestion: DispatchSuggestion
    status: str = "ok"
    trace_id: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DispatchWorkflow(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    task: str = ""
    steps: list[DispatchWorkflowStep] = Field(default_factory=list)
    status: str = "draft"
    source: str = "dispatch"


class DispatchCard(BaseModel):
    card_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    subtitle: str = ""
    kind: str = "default"
    data: dict[str, object] = Field(default_factory=dict)


class DispatchDashboard(BaseModel):
    dispatch: dict[str, object] = Field(default_factory=dict)
    cards: list[DispatchCard] = Field(default_factory=list)
    workflow: dict[str, object] = Field(default_factory=dict)
    execution: dict[str, object] = Field(default_factory=dict)


class DispatchViews(BaseModel):
    organization: dict[str, object] = Field(default_factory=dict)
    department: dict[str, object] = Field(default_factory=dict)
    agent: dict[str, object] = Field(default_factory=dict)
    session: dict[str, object] = Field(default_factory=dict)
    collaboration: dict[str, object] = Field(default_factory=dict)
    replay_audit: dict[str, object] = Field(default_factory=dict)


def dispatch(request: DispatchRequest) -> DispatchResult:
    context = _build_context(request)
    org_view = _resolve_organization(context)
    department_view = _resolve_department(context)
    agent_view = _resolve_agent(context)
    session_view = _resolve_session(context)
    collaboration_view = _resolve_collaboration(context)
    replay_audit_view = _resolve_replay_and_audit(context)
    scored = _score_candidates(context, org_view, department_view, agent_view, session_view, collaboration_view, replay_audit_view)
    decision_path = _build_decision_path(context, org_view, department_view, agent_view, session_view, collaboration_view, replay_audit_view, scored)
    suggestion = _build_suggestion(context, org_view, department_view, agent_view, session_view, collaboration_view, replay_audit_view, scored, decision_path)
    return DispatchResult(request=request, suggestion=suggestion, trace_id=context.trace_id, status="ok")


def _build_context(request: DispatchRequest) -> DispatchContext:
    return DispatchContext(
        trace_id=request.trace_id or str(uuid4()),
        org_id=request.org_id,
        department_id=request.department_id,
        agent_id=request.agent_id,
        room_id=request.room_id,
        session_id=request.session_id,
        task=request.task,
        task_type=request.task_type,
        priority=request.priority,
        mode=request.mode,
        memory_layer_hint=request.memory_layer_hint or [],
        memory_scope_hint=request.memory_scope_hint or {},
        collaboration_hint=request.collaboration_hint or {},
        replay_hint=request.replay_hint,
    )


def _resolve_organization(context: DispatchContext) -> dict[str, object]:
    if not context.org_id:
        return {}
    org = org_core.organization_store.get_organization(context.org_id)
    if org is None:
        return {}
    departments = org_core.organization_store.list_departments(org_id=context.org_id)
    agents = org_core.organization_store.list_agents(org_id=context.org_id)
    trees = [org_core.organization_store.get_agent_tree(agent.agent_id) for agent in agents if agent.manager_agent_id is None]
    department_summaries = [org_core.organization_store.department_memory_summary(department.department_id) for department in departments]
    rooms = collaboration_core.collaboration_store.list_rooms(tenant_id=org.tenant_id)
    return {
        "organization": org,
        "departments": departments,
        "department_summaries": department_summaries,
        "org_layer_totals": _merge_layer_totals(department_summaries),
        "leaders": [tree for tree in trees if tree is not None],
        "leader_memories": [org_core.organization_store.agent_memory_summary(agent.agent_id) for agent in agents if agent.manager_agent_id is None],
        "collaboration_rooms": rooms,
    }


def _resolve_department(context: DispatchContext) -> dict[str, object]:
    if not context.department_id:
        return {}
    department = org_core.organization_store.get_department(context.department_id)
    if department is None:
        return {}
    agents = org_core.organization_store.list_agents(department_id=context.department_id)
    leader = next((agent for agent in agents if agent.agent_id == department.leader_agent_id), None)
    memory_summary = org_core.organization_store.department_memory_summary(context.department_id)
    return {
        "department": department,
        "leader": leader,
        "agents": agents,
        "memory_summary": memory_summary,
        "memory_layers": memory_summary.get("layer_totals", {}) if memory_summary else {},
        "child_agents": [agent for agent in agents if agent.manager_agent_id is not None],
        "parent_department": org_core.organization_store.get_department(department.parent_department_id) if department.parent_department_id else None,
    }


def _resolve_agent(context: DispatchContext) -> dict[str, object]:
    if not context.agent_id:
        return {}
    agent = org_core.organization_store.get_agent(context.agent_id)
    if agent is None:
        return {}
    memory_summary = memory_core.memory_system.agent_summary(agent.agent_id)
    memory_layers = memory_core.memory_system.agent_memory_layers(agent.agent_id)
    return {
        "agent": agent,
        "memory_summary": memory_summary,
        "memory_layers": memory_layers,
        "session_ids": memory_summary.get("session_ids", []) if memory_summary else [],
        "child_agents": [org_core.organization_store.get_agent(child_id) for child_id in agent.child_agent_ids if org_core.organization_store.get_agent(child_id) is not None],
        "collaboration_refs": [],
    }


def _resolve_session(context: DispatchContext) -> dict[str, object]:
    if not context.session_id:
        return {}
    summary = memory_core.memory_system.session_summary(context.session_id)
    if summary is None:
        return {}
    items = memory_core.memory_system.session_items(context.session_id)
    layers = memory_core.memory_system.session_memory_layers(context.session_id)
    return {
        "session_summary": summary,
        "session_items": items,
        "session_layers": layers,
        "latest_memory_id": summary.get("latest_memory_id"),
        "shared": summary.get("shared", False),
        "room_id": summary.get("room_id"),
        "project_id": summary.get("project_id"),
    }


def _resolve_collaboration(context: DispatchContext) -> dict[str, object]:
    rooms = collaboration_core.collaboration_store.list_rooms()
    selected_room = collaboration_core.collaboration_store.get_room(context.room_id) if context.room_id else None
    return {
        "rooms": rooms,
        "selected_room": selected_room,
        "room_memory_refs": list(selected_room.memory_refs) if selected_room else [],
        "agent_memory_refs": dict(selected_room.agent_memory_refs) if selected_room else {},
        "department_memory_refs": dict(selected_room.department_memory_refs) if selected_room else {},
        "message_count": len(selected_room.messages) if selected_room else 0,
        "member_count": len(selected_room.members) if selected_room else 0,
    }


def _resolve_replay_and_audit(context: DispatchContext) -> dict[str, object]:
    enabled = context.replay_hint or context.task_type in {"replay", "recovery", "audit"}
    return {
        "replay_hints": {"enabled": enabled, "reason": "task requires replay support"} if enabled else {},
        "audit_hints": {"enabled": enabled, "reason": "task requires audit support"} if enabled else {},
        "recovery_hints": {"enabled": enabled, "reason": "task may need recovery"} if enabled else {},
        "verification": {},
        "risk_level": "low",
        "latest_audit": None,
        "latest_replay": None,
    }


def _score_candidates(context: DispatchContext, org_view: dict[str, object], department_view: dict[str, object], agent_view: dict[str, object], session_view: dict[str, object], collaboration_view: dict[str, object], replay_audit_view: dict[str, object]) -> dict[str, object]:
    score_breakdown = {
        "organization_score": 1.0 if org_view.get("organization") else 0.0,
        "department_score": 1.0 if department_view.get("department") else 0.0,
        "leader_score": 1.0 if agent_view.get("agent") else 0.0,
        "agent_score": float(len(agent_view.get("child_agents") or [])) * 0.1,
        "session_score": 1.0 if session_view.get("session_summary") else 0.0,
        "collaboration_score": 1.0 if collaboration_view.get("selected_room") else 0.0,
        "memory_score": float(len(session_view.get("session_layers") or [])) * 0.05,
        "replay_score": 1.0 if replay_audit_view.get("replay_hints") else 0.0,
        "audit_score": 1.0 if replay_audit_view.get("audit_hints") else 0.0,
    }
    confidence = min(1.0, sum(score_breakdown.values()) / 5.0)
    return {"score_breakdown": score_breakdown, "confidence": confidence}


def _build_decision_path(context: DispatchContext, org_view: dict[str, object], department_view: dict[str, object], agent_view: dict[str, object], session_view: dict[str, object], collaboration_view: dict[str, object], replay_audit_view: dict[str, object], scored: dict[str, object]) -> list[DispatchDecisionPath]:
    return [
        DispatchDecisionPath(step="organization", name="resolve_organization", input={"org_id": context.org_id}, output={"found": bool(org_view.get("organization"))}, reason="Organization is top-level scope.", confidence=1.0 if org_view.get("organization") else 0.0),
        DispatchDecisionPath(step="department", name="resolve_department", input={"department_id": context.department_id}, output={"found": bool(department_view.get("department"))}, reason="Department narrows routing.", confidence=1.0 if department_view.get("department") else 0.0),
        DispatchDecisionPath(step="agent", name="resolve_agent", input={"agent_id": context.agent_id}, output={"found": bool(agent_view.get("agent"))}, reason="Agent may own the task.", confidence=1.0 if agent_view.get("agent") else 0.0),
        DispatchDecisionPath(step="session", name="resolve_session", input={"session_id": context.session_id}, output={"found": bool(session_view.get("session_summary"))}, reason="Session provides continuity.", confidence=1.0 if session_view.get("session_summary") else 0.0),
        DispatchDecisionPath(step="collaboration", name="resolve_collaboration", input={"room_id": context.room_id}, output={"found": bool(collaboration_view.get("selected_room"))}, reason="Collaboration room may already have context.", confidence=1.0 if collaboration_view.get("selected_room") else 0.0),
        DispatchDecisionPath(step="replay_audit", name="resolve_replay_and_audit", input={"replay_hint": context.replay_hint}, output={"enabled": bool(replay_audit_view.get("replay_hints"))}, reason="Replay/audit support recovery.", confidence=1.0 if replay_audit_view.get("replay_hints") else 0.0),
        DispatchDecisionPath(step="final_score", name="score_candidates", input={}, output={"confidence": scored["confidence"]}, reason="Combine all views into a dispatch decision.", confidence=scored["confidence"]),
    ]


def _build_suggestion(context: DispatchContext, org_view: dict[str, object], department_view: dict[str, object], agent_view: dict[str, object], session_view: dict[str, object], collaboration_view: dict[str, object], replay_audit_view: dict[str, object], scored: dict[str, object], decision_path: list[DispatchDecisionPath]) -> DispatchSuggestion:
    selected_room = collaboration_view.get("selected_room")
    reason = DispatchReason(
        summary="Routing based on organization, memory, and collaboration context.",
        confidence=float(scored["confidence"]),
        parts=[
            DispatchReasonPart(
                category="organization",
                label="organization_scope",
                detail="Organization scope was resolved and used as the top-level routing boundary.",
                weight=1.0 if org_view.get("organization") else 0.0,
                evidence={"org_id": context.org_id},
            ),
            DispatchReasonPart(
                category="department",
                label="department_fit",
                detail="Department context and memory summary were available for routing.",
                weight=1.0 if department_view.get("department") else 0.0,
                evidence={"department_id": context.department_id, "layer_totals": department_view.get("memory_layers", {})},
            ),
            DispatchReasonPart(
                category="agent",
                label="leader_selection",
                detail="Leader agent and child agents were discovered for delegation.",
                weight=1.0 if agent_view.get("agent") else 0.0,
                evidence={"agent_id": context.agent_id, "child_count": len(agent_view.get("child_agents") or [])},
            ),
            DispatchReasonPart(
                category="session",
                label="continuity",
                detail="Session memory was used to preserve continuity.",
                weight=1.0 if session_view.get("session_summary") else 0.0,
                evidence={"session_id": context.session_id, "latest_memory_id": session_view.get("latest_memory_id")},
            ),
            DispatchReasonPart(
                category="collaboration",
                label="shared_context",
                detail="An active collaboration room can be reused for shared context.",
                weight=1.0 if collaboration_view.get("selected_room") else 0.0,
                evidence={"room_id": context.room_id, "message_count": collaboration_view.get("message_count", 0)},
            ),
            DispatchReasonPart(
                category="replay_audit",
                label="safety_and_recovery",
                detail="Replay, audit, and recovery hints were checked for safety.",
                weight=1.0 if replay_audit_view.get("replay_hints") else 0.0,
                evidence={"task_type": context.task_type, "replay_hint": context.replay_hint},
            ),
        ],
    )
    next_actions = [
        DispatchAction(
            action="assign_to_leader",
            target=context.agent_id or (department_view.get("leader").agent_id if department_view.get("leader") else None),
            reason="Route the task to the best available leader agent.",
            priority=100,
            required_scope=["agent:run"],
            parameters={"department_id": context.department_id, "org_id": context.org_id},
        ),
        DispatchAction(
            action="attach_to_room",
            target=(selected_room.room_id if selected_room else None),
            reason="Reuse an existing collaboration room for shared context.",
            priority=80,
            required_scope=["agent:run"],
            parameters={"room_id": context.room_id},
        ),
        DispatchAction(
            action="load_session_memory",
            target=context.session_id,
            reason="Load the nearest session memory for continuity.",
            priority=70,
            required_scope=["memory:read"],
            parameters={"session_id": context.session_id},
        ),
    ]
    if replay_audit_view.get("replay_hints"):
        next_actions.append(DispatchAction(action="open_replay_view", target=context.trace_id, reason="Replay hints are available for recovery.", priority=60, required_scope=["workflow:create"], parameters={"trace_id": context.trace_id}))
    if replay_audit_view.get("audit_hints"):
        next_actions.append(DispatchAction(action="open_audit_chain", target=context.trace_id, reason="Audit hints are available for validation.", priority=55, required_scope=["audit:read"], parameters={"trace_id": context.trace_id}))
    DispatchWorkflow(
        trace_id=context.trace_id,
        task=context.task,
        steps=[
            DispatchWorkflowStep(
                step_id=f"{context.trace_id}-1",
                name=action.action,
                action=action.action,
                target=action.target,
                reason=action.reason,
                priority=action.priority,
                required_scope=action.required_scope,
                parameters=action.parameters,
                blocking_conditions=action.blocking_conditions,
            )
            for action in next_actions
        ],
    )
    return DispatchSuggestion(
        selected_org=_dump_model(org_view.get("organization")),
        selected_department=_dump_model(department_view.get("department")),
        selected_leader=_dump_model(agent_view.get("agent")),
        selected_agents=[_dump_model(agent) for agent in agent_view.get("child_agents", [])],
        selected_room=_dump_model(selected_room),
        memory_summary=department_view.get("memory_summary") or agent_view.get("memory_summary") or session_view.get("session_summary"),
        memory_layers=agent_view.get("memory_layers") or session_view.get("session_layers") or [],
        session_summary=session_view.get("session_summary"),
        agent_memory=agent_view.get("memory_summary"),
        department_memory=department_view.get("memory_summary"),
        collaboration_rooms=[_dump_model(room) for room in collaboration_view.get("rooms", [])],
        memory_refs=list(collaboration_view.get("room_memory_refs") or []),
        agent_memory_refs=dict(collaboration_view.get("agent_memory_refs") or {}),
        department_memory_refs=dict(collaboration_view.get("department_memory_refs") or {}),
        replay_hints=replay_audit_view.get("replay_hints") or {},
        audit_hints=replay_audit_view.get("audit_hints") or {},
        recovery_hints=replay_audit_view.get("recovery_hints") or {},
        confidence=float(scored["confidence"]),
        reason=reason,
        decision_path=decision_path,
        next_actions=next_actions,
    )


def workflow_from_dispatch(result: DispatchResult) -> DispatchWorkflow:
    steps = []
    for idx, action in enumerate(result.suggestion.next_actions, start=1):
        steps.append(
            DispatchWorkflowStep(
                step_id=f"{result.trace_id}-{idx}",
                name=action.action,
                action=action.action,
                target=action.target,
                reason=action.reason,
                priority=action.priority,
                required_scope=action.required_scope,
                parameters=action.parameters,
                blocking_conditions=action.blocking_conditions,
            )
        )
    return DispatchWorkflow(trace_id=result.trace_id, task=result.request.task, steps=steps)


def _merge_layer_totals(department_summaries: list[dict[str, object]]) -> dict[int, int]:
    totals: dict[int, int] = {}
    for summary in department_summaries:
        for layer, count in (summary.get("layer_totals") or {}).items():
            totals[int(layer)] = totals.get(int(layer), 0) + int(count)
    return dict(sorted(totals.items()))


def _dump_model(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value
