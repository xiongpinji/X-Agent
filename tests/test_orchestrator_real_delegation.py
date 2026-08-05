"""P1-09 批次 E-lite：orchestrator 真实委派的回归测试。

背景：_delegate_subtask 原为 sleep(0.01) + 编造 "Completed: ..." 的假实现
（直接挂载即重蹈 P0-12 假成功）。本次真实化为 CollaborationDelegator 路径
（真实子 AgentLoop），失败经 DelegationError 交由 failure_policy 裁决。
api/multi_agent.py 同步补齐鉴权（备用不挂载，G3 路由预算评审后再挂）。
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.core.collaboration.orchestrator import (
    FailurePolicy,
    MultiAgentOrchestrator,
    OrchestrationMode,
    OrchestrationPlan,
    SubTask,
)


async def test_execute_runs_real_delegation() -> None:
    """编排执行必须产出真实委派证据（delegation_id + assigned_agent_id），
    且输出不再是编造的 'Completed: ...' 格式。"""
    orchestrator = MultiAgentOrchestrator()
    plan = OrchestrationPlan(
        task="演示真实委派",
        mode=OrchestrationMode.PARALLEL,
        subtasks=[
            SubTask(description="介绍一下 X-Agent"),
            SubTask(description="什么是 FastAPI"),
        ],
        failure_policy=FailurePolicy.ABORT,
    )

    result = await orchestrator.execute(plan)

    assert result.status == "completed"
    assert result.completed == 2
    for sub in plan.subtasks:
        assert sub.status.value == "completed"
        assert sub.result is not None
        assert sub.result["delegation_id"].startswith("dlg_")
        assert sub.result["assigned_agent_id"]
        assert not str(sub.result["output"]).startswith("Completed: ")


async def test_no_capable_candidate_feeds_failure_policy() -> None:
    """无满足能力要求的候选 → DelegationError → failure_policy=skip 置 SKIPPED。"""
    orchestrator = MultiAgentOrchestrator()
    plan = OrchestrationPlan(
        task="能力缺失场景",
        mode=OrchestrationMode.PARALLEL,
        subtasks=[
            SubTask(description="需要不存在的能力", required_capabilities=["no-such-capability"]),
            SubTask(description="介绍一下 X-Agent"),
        ],
        failure_policy=FailurePolicy.SKIP,
    )

    result = await orchestrator.execute(plan)

    impossible, normal = plan.subtasks
    assert impossible.status.value == "skipped"
    assert impossible.error is not None
    assert normal.status.value == "completed"
    assert result.skipped == 1
    assert result.completed == 1


def test_multi_agent_api_requires_auth() -> None:
    """api/multi_agent（备用不挂载）自构子 app 时鉴权必须生效。"""
    from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
    from backend.app.api.multi_agent import router

    sub_app = FastAPI()
    sub_app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    sub_app.include_router(router)

    with TestClient(sub_app) as client:
        unauthenticated = client.post(
            "/api/v1/multi-agent/decompose", json={"task": "写一个函数"}
        )
        authenticated = client.post(
            "/api/v1/multi-agent/decompose",
            json={"task": "写一个函数"},
            headers={"X-API-Key": "bootstrap"},
        )

    assert unauthenticated.status_code in (401, 403)
    assert authenticated.status_code == 200
    body = authenticated.json()
    assert body["plan_id"]
    assert body["subtasks"]
