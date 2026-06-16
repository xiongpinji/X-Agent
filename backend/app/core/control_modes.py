from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.app.core.coding_loop import CODING_LOOP_PHASES, build_coding_loop_plan
from backend.app.core.execution_planner import ExecutionPlan, ExecutionPlanner
from backend.app.core.storage import atomic_write_json, load_json_array


def control_utcnow() -> datetime:
    return datetime.now(UTC)


def new_control_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class PlanModeStatus(StrEnum):
    DRAFT = "draft"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELED = "canceled"


class GoalStopReason(StrEnum):
    NONE = "none"
    PLAN_APPROVAL_REQUIRED = "plan_approval_required"
    BUDGET_EXHAUSTED = "budget_exhausted"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    COMPLETION_REPORTED = "completion_reported"
    BLOCKER_REPORTED = "blocker_reported"
    EXECUTION_FAILED = "execution_failed"
    USER_CANCELED = "user_canceled"


class GoalLoopPolicy(BaseModel):
    max_iterations: int = Field(default=6, ge=1, le=100)
    token_budget: int | None = Field(default=None, ge=1)
    require_plan_approval: bool = True
    require_verification: bool = True
    stop_on_blocker: bool = True
    auto_execute: bool = False


class PlanModeDraftRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=20_000)
    root: str = "."
    limit: int = Field(default=500, ge=1, le=5_000)
    context: dict[str, Any] = Field(default_factory=dict)
    require_approval: bool = True


class PlanModeDecisionRequest(BaseModel):
    reason: str = Field(default="", max_length=2_000)


class GoalCreateRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=20_000)
    title: str = Field(default="", max_length=200)
    context: dict[str, Any] = Field(default_factory=dict)
    policy: GoalLoopPolicy = Field(default_factory=GoalLoopPolicy)


class GoalAdvanceRequest(BaseModel):
    execute: bool = False
    force: bool = False
    user_feedback: str = Field(default="", max_length=4_000)
    context: dict[str, Any] = Field(default_factory=dict)


class GoalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_control_id("event"))
    kind: str
    detail: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=control_utcnow)


class GoalIteration(BaseModel):
    iteration: int
    status: str
    task: str
    trace_id: str | None = None
    answer: str = ""
    plan_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    stop_reason: GoalStopReason = GoalStopReason.NONE
    created_at: datetime = Field(default_factory=control_utcnow)


class PlanModeRecord(BaseModel):
    plan_id: str = Field(default_factory=lambda: new_control_id("plan"))
    task: str
    status: PlanModeStatus = PlanModeStatus.DRAFT
    tenant_id: str = "default"
    user_id: str = "anonymous"
    root: str = "."
    context: dict[str, Any] = Field(default_factory=dict)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    coding_loop: dict[str, Any] = Field(default_factory=dict)
    approval_required: bool = True
    approved_by: str | None = None
    approval_reason: str = ""
    created_at: datetime = Field(default_factory=control_utcnow)
    updated_at: datetime = Field(default_factory=control_utcnow)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class GoalRecord(BaseModel):
    goal_id: str = Field(default_factory=lambda: new_control_id("goal"))
    title: str = ""
    objective: str
    tenant_id: str = "default"
    user_id: str = "anonymous"
    status: GoalStatus = GoalStatus.ACTIVE
    stop_reason: GoalStopReason = GoalStopReason.NONE
    policy: GoalLoopPolicy = Field(default_factory=GoalLoopPolicy)
    context: dict[str, Any] = Field(default_factory=dict)
    plan_id: str | None = None
    active_trace_id: str | None = None
    iterations: list[GoalIteration] = Field(default_factory=list)
    events: list[GoalEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=control_utcnow)
    updated_at: datetime = Field(default_factory=control_utcnow)
    completed_at: datetime | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)


class PlanModeService:
    """Create and approve execution plans without mutating the target system."""

    def __init__(self, planner: ExecutionPlanner | None = None) -> None:
        self._planner = planner or ExecutionPlanner()

    def draft(
        self,
        request: PlanModeDraftRequest,
        *,
        tenant_id: str,
        user_id: str,
        test_mapping: Any | None = None,
    ) -> PlanModeRecord:
        execution_plan = self._planner.build(request.task, test_mapping=test_mapping)
        coding_loop = self._build_coding_loop(request, execution_plan)
        status = (
            PlanModeStatus.WAITING_APPROVAL
            if request.require_approval
            else PlanModeStatus.APPROVED
        )
        return PlanModeRecord(
            task=request.task,
            status=status,
            tenant_id=tenant_id,
            user_id=user_id,
            root=request.root,
            context=request.context,
            execution_plan=_plan_to_payload(execution_plan),
            coding_loop=coding_loop,
            approval_required=request.require_approval,
            snapshot={
                "mode": "plan",
                "next_action": "approve_plan" if request.require_approval else "execute",
                "phase_order": list(CODING_LOOP_PHASES),
                "requires_execution": False,
            },
        )

    @staticmethod
    def _build_coding_loop(
        request: PlanModeDraftRequest,
        execution_plan: ExecutionPlan,
    ) -> dict[str, Any]:
        repo_status = {
            "branch": request.context.get("branch"),
            "git_status": request.context.get("git_status"),
            "inspected_files": request.context.get("inspected_files", []),
            "changed_files": request.context.get("changed_files", []),
            "validation_commands": execution_plan.suggested_test_commands,
            "delivery_summary": request.context.get("delivery_summary"),
        }
        tools = request.context.get(
            "available_tools",
            ("codegraph_context", "apply_patch", "pytest"),
        )
        if not isinstance(tools, (list, tuple)):
            tools = (str(tools),)
        loop_plan = build_coding_loop_plan(request.task, repo_status, tools)
        return {
            "phases": list(loop_plan.phases),
            "evidence": [
                {
                    "key": item.key,
                    "phase": item.phase,
                    "description": item.description,
                    "acceptance": item.acceptance,
                    "required": item.required,
                    "present": item.present,
                    "details": list(item.details),
                }
                for item in loop_plan.evidence
            ],
            "acceptance_conditions": list(loop_plan.acceptance_conditions),
            "available_tools": list(loop_plan.available_tools),
            "tool_gaps": list(loop_plan.tool_gaps),
            "acceptance_failures": list(loop_plan.acceptance_failures()),
            "acceptable": loop_plan.is_acceptable(),
        }


class GoalLoopService:
    """Manage persistent loop-engineering goals and one-step advancement."""

    def __init__(self, plan_service: PlanModeService | None = None) -> None:
        self._plan_service = plan_service or PlanModeService()

    def create(
        self,
        request: GoalCreateRequest,
        *,
        tenant_id: str,
        user_id: str,
    ) -> tuple[GoalRecord, PlanModeRecord]:
        plan_request = PlanModeDraftRequest(
            task=request.objective,
            root=str(request.context.get("root", ".")),
            context=request.context,
            require_approval=request.policy.require_plan_approval,
        )
        plan = self._plan_service.draft(
            plan_request,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        status = (
            GoalStatus.WAITING_APPROVAL
            if request.policy.require_plan_approval
            else GoalStatus.ACTIVE
        )
        stop_reason = (
            GoalStopReason.PLAN_APPROVAL_REQUIRED
            if request.policy.require_plan_approval
            else GoalStopReason.NONE
        )
        goal = GoalRecord(
            title=request.title or request.objective[:120],
            objective=request.objective,
            tenant_id=tenant_id,
            user_id=user_id,
            status=status,
            stop_reason=stop_reason,
            policy=request.policy,
            context=request.context,
            plan_id=plan.plan_id,
            events=[
                GoalEvent(
                    kind="goal.created",
                    detail="Goal created with initial loop-engineering plan.",
                    payload={"plan_id": plan.plan_id},
                )
            ],
            snapshot=self._goal_snapshot(
                status=status,
                stop_reason=stop_reason,
                next_action="approve_plan" if request.policy.require_plan_approval else "advance",
            ),
        )
        return goal, plan

    def advance_without_execution(
        self,
        goal: GoalRecord,
        plan: PlanModeRecord | None = None,
        *,
        force: bool = False,
        user_feedback: str = "",
    ) -> GoalRecord:
        if self._requires_plan_approval(goal, plan, force=force):
            return self._stop(
                goal,
                GoalStatus.WAITING_APPROVAL,
                GoalStopReason.PLAN_APPROVAL_REQUIRED,
                "Plan approval is required before execution.",
                {"plan_id": goal.plan_id},
            )
        limit_reason = self._limit_stop_reason(goal)
        if limit_reason is not None:
            return self._stop(
                goal,
                GoalStatus.BLOCKED,
                limit_reason,
                self._limit_detail(limit_reason),
            )

        iteration_number = len(goal.iterations) + 1
        task = self._iteration_task(goal, iteration_number, user_feedback=user_feedback)
        evidence = self._planned_iteration_evidence(goal, plan)
        iteration = GoalIteration(
            iteration=iteration_number,
            status="planned",
            task=task,
            plan_id=goal.plan_id,
            evidence=evidence,
        )
        goal.iterations.append(iteration)
        goal.status = GoalStatus.ACTIVE
        goal.stop_reason = GoalStopReason.NONE
        goal.updated_at = control_utcnow()
        goal.events.append(
            GoalEvent(
                kind="goal.advance.planned",
                detail="Next loop-engineering iteration planned. Set execute=true to run it.",
                payload={"iteration": iteration_number, "plan_id": goal.plan_id},
            )
        )
        goal.snapshot = self._goal_snapshot(
            status=goal.status,
            stop_reason=goal.stop_reason,
            next_action="execute_iteration",
        )
        return goal

    def record_execution_result(
        self,
        goal: GoalRecord,
        *,
        task: str,
        result: Any,
        plan: PlanModeRecord | None = None,
    ) -> GoalRecord:
        iteration_number = len(goal.iterations) + 1
        status_value = str(getattr(result, "status", "completed"))
        if hasattr(getattr(result, "status", None), "value"):
            status_value = str(result.status.value)
        trace_id = str(getattr(result, "trace_id", "") or "")
        answer = str(getattr(result, "answer", "") or "")
        evidence = self._execution_evidence(result, plan)
        stop_reason = self._derive_stop_reason(goal, status_value, answer, task=task)
        goal.iterations.append(
            GoalIteration(
                iteration=iteration_number,
                status=status_value,
                task=task,
                trace_id=trace_id or None,
                answer=answer[:4_000],
                plan_id=goal.plan_id,
                evidence=evidence,
                stop_reason=stop_reason,
            )
        )
        goal.active_trace_id = trace_id or goal.active_trace_id
        goal.stop_reason = stop_reason
        goal.status = self._derive_goal_status(goal, status_value, stop_reason)
        if goal.status in {GoalStatus.COMPLETED, GoalStatus.BLOCKED, GoalStatus.CANCELED}:
            goal.completed_at = control_utcnow()
        goal.updated_at = control_utcnow()
        goal.events.append(
            GoalEvent(
                kind="goal.advance.executed",
                detail="Loop-engineering iteration executed by agent.",
                payload={
                    "iteration": iteration_number,
                    "trace_id": trace_id,
                    "status": status_value,
                    "stop_reason": stop_reason.value,
                },
            )
        )
        goal.snapshot = self._goal_snapshot(
            status=goal.status,
            stop_reason=goal.stop_reason,
            next_action=self._next_action_for(goal),
        )
        return goal

    def cancel(self, goal: GoalRecord, *, reason: str = "") -> GoalRecord:
        return self._stop(
            goal,
            GoalStatus.CANCELED,
            GoalStopReason.USER_CANCELED,
            reason or "Goal canceled by user.",
        )

    @staticmethod
    def _requires_plan_approval(
        goal: GoalRecord,
        plan: PlanModeRecord | None,
        *,
        force: bool,
    ) -> bool:
        if force or not goal.policy.require_plan_approval:
            return False
        return plan is None or plan.status != PlanModeStatus.APPROVED

    @staticmethod
    def _limit_stop_reason(goal: GoalRecord) -> GoalStopReason | None:
        if len(goal.iterations) >= goal.policy.max_iterations:
            return GoalStopReason.MAX_ITERATIONS_REACHED
        if goal.policy.token_budget is not None and _estimated_goal_tokens(goal) >= goal.policy.token_budget:
            return GoalStopReason.BUDGET_EXHAUSTED
        return None

    @staticmethod
    def _limit_detail(stop_reason: GoalStopReason) -> str:
        if stop_reason == GoalStopReason.MAX_ITERATIONS_REACHED:
            return "Goal loop max_iterations limit is exhausted."
        return "Goal loop token budget is exhausted."

    @staticmethod
    def _iteration_task(goal: GoalRecord, iteration: int, *, user_feedback: str = "") -> str:
        feedback = f"\nUser feedback: {user_feedback}" if user_feedback.strip() else ""
        return (
            f"Advance goal {goal.goal_id}, iteration {iteration}.\n"
            f"Objective: {goal.objective}\n"
            f"Use loop engineering phases: {', '.join(CODING_LOOP_PHASES)}.\n"
            "Stop when the goal is complete, blocked, or requires approval."
            f"{feedback}"
        )

    @staticmethod
    def _planned_iteration_evidence(
        goal: GoalRecord,
        plan: PlanModeRecord | None,
    ) -> dict[str, Any]:
        return {
            "mode": "plan_only",
            "goal_id": goal.goal_id,
            "phase_order": list(CODING_LOOP_PHASES),
            "plan_status": plan.status.value if plan else None,
            "verification_required": goal.policy.require_verification,
        }

    @staticmethod
    def _execution_evidence(result: Any, plan: PlanModeRecord | None) -> dict[str, Any]:
        plan_records = getattr(result, "plan", []) or []
        tool_calls = getattr(result, "tool_calls", []) or []
        execution_summary = getattr(result, "execution_summary", {}) or {}
        return {
            "mode": "executed",
            "plan_id": plan.plan_id if plan else None,
            "plan_status": plan.status.value if plan else None,
            "agent_plan_steps": len(plan_records),
            "tool_call_count": len(tool_calls),
            "execution_summary": execution_summary,
            "phase_order": list(CODING_LOOP_PHASES),
        }

    @staticmethod
    def _derive_stop_reason(
        goal: GoalRecord,
        status_value: str,
        answer: str,
        *,
        task: str = "",
    ) -> GoalStopReason:
        normalized_answer = answer.lower()
        if status_value == "failed":
            return GoalStopReason.EXECUTION_FAILED
        if any(token in normalized_answer for token in ("blocked", "cannot proceed", "need user", "requires approval")):
            return GoalStopReason.BLOCKER_REPORTED
        if any(token in normalized_answer for token in ("completed", "done", "finished", "goal achieved")):
            return GoalStopReason.COMPLETION_REPORTED
        if len(goal.iterations) + 1 >= goal.policy.max_iterations:
            return GoalStopReason.MAX_ITERATIONS_REACHED
        if (
            goal.policy.token_budget is not None
            and _estimated_goal_tokens(goal, extra_text=f"{task}\n{answer}") >= goal.policy.token_budget
        ):
            return GoalStopReason.BUDGET_EXHAUSTED
        return GoalStopReason.NONE

    @staticmethod
    def _derive_goal_status(
        goal: GoalRecord,
        status_value: str,
        stop_reason: GoalStopReason,
    ) -> GoalStatus:
        if stop_reason in {
            GoalStopReason.BLOCKER_REPORTED,
            GoalStopReason.BUDGET_EXHAUSTED,
            GoalStopReason.EXECUTION_FAILED,
            GoalStopReason.MAX_ITERATIONS_REACHED,
        }:
            return GoalStatus.BLOCKED
        if stop_reason == GoalStopReason.COMPLETION_REPORTED:
            return GoalStatus.COMPLETED
        if status_value == "failed":
            return GoalStatus.BLOCKED
        return GoalStatus.ACTIVE

    @staticmethod
    def _next_action_for(goal: GoalRecord) -> str:
        if goal.status == GoalStatus.ACTIVE:
            return "advance"
        if goal.status == GoalStatus.WAITING_APPROVAL:
            return "approve_plan"
        if goal.status == GoalStatus.BLOCKED:
            return "resolve_blocker"
        return "none"

    def _stop(
        self,
        goal: GoalRecord,
        status: GoalStatus,
        stop_reason: GoalStopReason,
        detail: str,
        payload: dict[str, Any] | None = None,
    ) -> GoalRecord:
        goal.status = status
        goal.stop_reason = stop_reason
        goal.updated_at = control_utcnow()
        if status in {GoalStatus.COMPLETED, GoalStatus.BLOCKED, GoalStatus.CANCELED}:
            goal.completed_at = control_utcnow()
        goal.events.append(
            GoalEvent(
                kind="goal.stopped",
                detail=detail,
                payload=payload or {},
            )
        )
        goal.snapshot = self._goal_snapshot(
            status=status,
            stop_reason=stop_reason,
            next_action=self._next_action_for(goal),
        )
        return goal

    @staticmethod
    def _goal_snapshot(
        *,
        status: GoalStatus,
        stop_reason: GoalStopReason,
        next_action: str,
    ) -> dict[str, Any]:
        return {
            "mode": "goal",
            "loop": "engineering",
            "phase_order": list(CODING_LOOP_PHASES),
            "status": status.value,
            "stop_reason": stop_reason.value,
            "next_action": next_action,
        }


class ControlModeStore:
    """JSON-backed store for plan-mode drafts and goal-loop records."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._lock = RLock()
        self._plans: dict[str, PlanModeRecord] = {}
        self._goals: dict[str, GoalRecord] = {}
        self._load()

    def save_plan(self, record: PlanModeRecord) -> PlanModeRecord:
        record.updated_at = control_utcnow()
        with self._lock:
            self._plans[record.plan_id] = record
            self._persist()
        return record

    def get_plan(self, plan_id: str) -> PlanModeRecord | None:
        with self._lock:
            return self._plans.get(plan_id)

    def list_plans(self, *, tenant_id: str | None = None, limit: int = 50) -> list[PlanModeRecord]:
        with self._lock:
            records = list(self._plans.values())
        if tenant_id:
            records = [record for record in records if record.tenant_id == tenant_id]
        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records[:limit]

    def approve_plan(
        self,
        plan_id: str,
        *,
        actor_id: str,
        reason: str = "",
    ) -> PlanModeRecord | None:
        with self._lock:
            record = self._plans.get(plan_id)
            if record is None:
                return None
            record.status = PlanModeStatus.APPROVED
            record.approved_by = actor_id
            record.approval_reason = reason
            record.updated_at = control_utcnow()
            record.snapshot = {
                **record.snapshot,
                "next_action": "execute",
                "approved": True,
            }
            self._plans[plan_id] = record
            self._persist()
            return record

    def reject_plan(
        self,
        plan_id: str,
        *,
        actor_id: str,
        reason: str = "",
    ) -> PlanModeRecord | None:
        with self._lock:
            record = self._plans.get(plan_id)
            if record is None:
                return None
            record.status = PlanModeStatus.REJECTED
            record.approved_by = actor_id
            record.approval_reason = reason
            record.updated_at = control_utcnow()
            record.snapshot = {
                **record.snapshot,
                "next_action": "revise_plan",
                "approved": False,
            }
            self._plans[plan_id] = record
            self._persist()
            return record

    def save_goal(self, record: GoalRecord) -> GoalRecord:
        record.updated_at = control_utcnow()
        with self._lock:
            self._goals[record.goal_id] = record
            self._persist()
        return record

    def get_goal(self, goal_id: str) -> GoalRecord | None:
        with self._lock:
            return self._goals.get(goal_id)

    def list_goals(self, *, tenant_id: str | None = None, limit: int = 50) -> list[GoalRecord]:
        with self._lock:
            records = list(self._goals.values())
        if tenant_id:
            records = [record for record in records if record.tenant_id == tenant_id]
        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records[:limit]

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        for record in load_json_array(self._storage_path, _ControlStoreEnvelope):
            if record.kind == "plan":
                plan = PlanModeRecord.model_validate(record.payload)
                self._plans[plan.plan_id] = plan
            elif record.kind == "goal":
                goal = GoalRecord.model_validate(record.payload)
                self._goals[goal.goal_id] = goal

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        payload = [
            {"kind": "plan", "payload": record.model_dump(mode="json")}
            for record in self._plans.values()
        ]
        payload.extend(
            {"kind": "goal", "payload": record.model_dump(mode="json")}
            for record in self._goals.values()
        )
        atomic_write_json(self._storage_path, payload)


class _ControlStoreEnvelope(BaseModel):
    kind: str
    payload: dict[str, Any]


def _plan_to_payload(plan: ExecutionPlan) -> dict[str, Any]:
    return {
        "steps": list(plan.steps),
        "verification_steps": list(plan.verification_steps),
        "suggested_test_commands": list(plan.suggested_test_commands),
        "rollback_steps": list(plan.rollback_steps),
        "risk_notes": list(plan.risk_notes),
        "next_actions": list(plan.next_actions),
        "metadata": dict(plan.metadata),
    }


def _estimated_goal_tokens(goal: GoalRecord, *, extra_text: str = "") -> int:
    text_parts = [goal.objective, goal.title, extra_text]
    for iteration in goal.iterations:
        text_parts.extend((iteration.task, iteration.answer))
    char_count = sum(len(part) for part in text_parts if part)
    return max(1, char_count // 4) if char_count else 0


__all__ = [
    "ControlModeStore",
    "GoalAdvanceRequest",
    "GoalCreateRequest",
    "GoalLoopPolicy",
    "GoalLoopService",
    "GoalRecord",
    "GoalStatus",
    "GoalStopReason",
    "PlanModeDecisionRequest",
    "PlanModeDraftRequest",
    "PlanModeRecord",
    "PlanModeService",
    "PlanModeStatus",
]
