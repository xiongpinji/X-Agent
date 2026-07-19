from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.linked_summary import build_linked_summary
from backend.app.api.recovery_helpers import build_recovery_context, build_recovery_payload
from backend.app.api.workflow_helpers import build_workflow_shell
from backend.app.core.code_index import code_index
from backend.app.core.dispatch import DispatchRequest, dispatch
from backend.app.core.execution_planner import execution_planner
from backend.app.core.security import Principal
from backend.app.core.test_mapper import test_mapper
from backend.app.core.verification import VerificationEngine
from backend.app.dependencies import (
    enforce_scope,
    get_agent,
    get_approval_store,
    get_current_principal,
    get_memory,
    get_run_store,
    get_trace_store,
    get_workflow_repository,
)

router = APIRouter(prefix="/api/v1/overview", tags=["overview"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
_verification_engine = VerificationEngine()


@router.get("")
async def get_overview(principal: PrincipalDependency) -> dict[str, object]:
    """聚合可观测性总览：traces / runs / approvals / workflows / memory / tools。

    与 /api/v1/ops/summary 共用同一组 store getter，但本端点面向前端总览面板，
    返回各核心域的轻量计数快照（而非 ops 的健康判定）。每个子键都是 dict，便于
    前端按域展开；调用方(test_observability_shapes / test_api_contracts)只断言
    六个顶层域键存在。
    """
    enforce_scope(principal, "audit:read")
    trace_store = get_trace_store()
    run_store = get_run_store()
    approval_store = get_approval_store()
    workflow_repository = get_workflow_repository()
    agent = get_agent()
    memory = get_memory()

    memory_count: object = 0
    try:
        snapshot = memory.snapshot() if hasattr(memory, "snapshot") else {}
        memory_count = snapshot.get("count", memory.count())
        if hasattr(memory_count, "__await__"):
            memory_count = await memory_count
    except Exception:  # noqa: BLE001 - 总览面板不应因单域故障而 500
        memory_count = 0

    return {
        "traces": {"count": trace_store.event_count(), "latest_count": len(trace_store.list_summaries(limit=10)), "last_event": trace_store.list_summaries(limit=1)[0].last_event if trace_store.list_summaries(limit=1) else None},
        "runs": {"count": run_store.count(), "recent_count": len(run_store.list(limit=10))},
        "approvals": {"count": approval_store.count(), "pending": approval_store.pending_count(), "recent_count": len(approval_store.list(limit=10))},
        "workflows": {
            "count": len(workflow_repository.list_definitions()),
            "runs": len(workflow_repository.list_runs(limit=200)),
        },
        "memory": {"count": int(memory_count or 0)},
        "tools": {"count": len(agent.tools.manifest())},
    }


@router.post("/draft")
async def draft_overview(payload: dict[str, object], principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    task = str(payload.get("task", ""))
    root = str(payload.get("root", "."))
    limit = int(payload.get("limit", 10))
    indexed = code_index.index(root=root, limit=max(20, limit * 20))
    mapping = test_mapper.map(task, limit=limit)
    plan = execution_planner.build(task, test_mapping=mapping)
    verification = _verification_engine.summarize_run([], test_mapping=mapping)
    dispatch_result = dispatch(DispatchRequest(task=task, summary=task[:240], mode="suggest", replay_hint=True))
    workflow_shell = build_workflow_shell(
        run=type("_RunShell", (), {
            "workflow_id": task,
            "workflow_name": task[:64] or "overview",
            "status": type("_S", (), {"value": "draft"})(),
            "node_results": [],
            "snapshot": {"last_agent_recovery_branch": verification.get("recovery_plan", {}).get("branch"), "last_agent_execution_summary": verification.get("recovery_plan", {})},
        })(),
        failure_chain=[],
        compensation_chain=[],
        trace_ids=[],
    )
    recovery_plan = verification.get("recovery_plan", {})
    recovery = build_recovery_context(
        status=verification.get("status", "draft"),
        resource_type="overview", 
        resource_id=task,
        next_actions=verification.get("next_actions", []),
        recovery_plan=recovery_plan,
        branch=workflow_shell.get("recovery_branch"),
        retryable=bool(verification.get("retryable_failures", 0)),
        confidence=float(verification.get("confidence", 0.6) or 0.6),
        tool_name="draft_overview",
        follow_up=["review execution plan", "inspect verification summary"],
        status_detail=f"overview {verification.get('status', 'draft')}",
        remediation="review execution plan and verification summary",
    )
    primary = {
        "task": task,
        "dispatch": dispatch_result.model_dump(mode="json"),
        "code_index": {
            "count": indexed["count"],
            "related_files": code_index.related_files(task, limit=limit),
            "impact_hints": code_index.impact_hints(task, limit=limit),
            "dependency_hints": code_index.dependency_hints(task, limit=limit),
            "test_files": code_index.test_files_for(task, limit=limit),
        },
        "test_mapping": mapping.__dict__,
        "execution_plan": {"steps": plan.steps, "verification_steps": plan.verification_steps, "suggested_test_commands": plan.suggested_test_commands, "rollback_steps": plan.rollback_steps, "risk_notes": plan.risk_notes, "next_actions": plan.next_actions, "metadata": plan.metadata},
        "verification": verification,
        "recovery": build_recovery_payload(
            status=verification.get("status", "draft"),
            resource_type="overview",
            resource_id=task,
            next_actions=verification.get("next_actions", []),
            recovery_plan=recovery_plan,
            branch=workflow_shell.get("recovery_branch"),
            retryable=bool(verification.get("retryable_failures", 0)),
            confidence=float(verification.get("confidence", 0.6) or 0.6),
            tool_name="draft_overview",
            follow_up=["review execution plan", "inspect verification summary"],
            status_detail=f"overview {verification.get('status', 'draft')}",
            remediation="review execution plan and verification summary",
        ),
        "workflow_shell": workflow_shell,
        "summary": {
            "planned_steps": len(plan.steps),
            "suggested_test_commands": plan.suggested_test_commands,
            "mapped_tests": len(mapping.test_files),
            "impact_hints": len(mapping.impact_hints),
            "dependency_hints": len(mapping.dependency_hints),
            "rollback_steps": len(plan.rollback_steps),
            "next_actions": plan.next_actions,
            "retryable_failures": verification.get("retryable_failures", 0),
            "repair_retry_count": verification.get("retryable_failures", 0),
        },
    }
    return build_linked_summary(
        resource_type="overview_draft",
        resource_id=task,
        primary=primary,
        workflow={"data": {"workflow_shell": workflow_shell, "execution_plan": primary["execution_plan"]}, "summary": {"task": task, "planned_steps": len(plan.steps)}},
        trace={"data": {"verification": verification, "dispatch": primary["dispatch"]}, "summary": {"status": verification.get("status", "draft"), "retryable_failures": verification.get("retryable_failures", 0)}},
        memory={"data": {"code_index": primary["code_index"], "test_mapping": primary["test_mapping"]}, "summary": {"mapped_tests": len(mapping.test_files), "impact_hints": len(mapping.impact_hints)}},
        audit={"data": {"recovery": primary["recovery"]}, "summary": {"branch": workflow_shell.get("recovery_branch"), "retryable": bool(verification.get("retryable_failures", 0))}},
        extra={"summary": primary["summary"], "task": task},
    )
