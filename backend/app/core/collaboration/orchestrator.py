"""P2-01: 多 Agent 协作编排器.

支持三种编排模式:
- PARALLEL: 并行 fan-out + 结果聚合
- SEQUENTIAL: 串行 pipeline (前一步输出作为后一步输入)
- HIERARCHICAL: 分层委派 (leader 拆分子任务分配给 workers)

设计原则:
- 基于现有 CollaborationDelegator 进行子任务委派
- 拓扑排序处理依赖关系
- 失败处理: retry(1次) / skip / abort
- 结果聚合与执行追踪
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class OrchestrationMode(StrEnum):
    """编排模式."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"


class SubTaskStatus(StrEnum):
    """子任务状态."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FailurePolicy(StrEnum):
    """失败处理策略."""

    RETRY = "retry"  # 重试一次
    SKIP = "skip"  # 跳过继续
    ABORT = "abort"  # 中止整个编排


@dataclass
class SubTask:
    """编排子任务."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: SubTaskStatus = SubTaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "required_capabilities": self.required_capabilities,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
        }


@dataclass
class OrchestrationPlan:
    """编排计划."""

    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str = ""
    mode: OrchestrationMode = OrchestrationMode.PARALLEL
    subtasks: list[SubTask] = field(default_factory=list)
    failure_policy: FailurePolicy = FailurePolicy.RETRY
    max_concurrency: int = 5
    timeout_seconds: int = 600
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task": self.task,
            "mode": self.mode.value,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "failure_policy": self.failure_policy.value,
            "max_concurrency": self.max_concurrency,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
        }


@dataclass
class OrchestrationResult:
    """编排执行结果."""

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    plan_id: str = ""
    status: str = "completed"  # completed / partial / failed / aborted
    total_subtasks: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    results: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "total_subtasks": self.total_subtasks,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "results": self.results,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
        }


class MultiAgentOrchestrator:
    """多 Agent 协作编排器.

    将复杂任务分解为子任务, 按编排模式调度执行,
    支持并行/串行/分层三种模式, 带失败恢复和结果聚合。
    """

    def __init__(
        self,
        max_concurrency: int = 5,
        timeout_seconds: int = 600,
        failure_policy: FailurePolicy = FailurePolicy.RETRY,
        delegator: Any | None = None,
    ):
        self._max_concurrency = max_concurrency
        self._timeout = timeout_seconds
        self._failure_policy = failure_policy
        # 可注入委派器（默认 get_delegator() 全局实例），便于测试与集成波接线
        self._delegator = delegator
        self._executions: dict[str, OrchestrationResult] = {}
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def executions(self) -> dict[str, OrchestrationResult]:
        return dict(self._executions)

    def decompose_task(self, task: str, context: dict[str, Any] | None = None) -> OrchestrationPlan:
        """基于规则的任务分解.

        根据任务描述中的关键词匹配子任务模板,
        生成编排计划。
        """
        context = context or {}
        lower = task.lower()
        subtasks: list[SubTask] = []

        # 代码相关任务分解
        if any(kw in lower for kw in ["代码", "code", "开发", "实现", "implement"]):
            subtasks = [
                SubTask(description=f"分析需求: {task}", required_capabilities=["analysis"]),
                SubTask(description=f"编写代码: {task}", required_capabilities=["coding"], depends_on=[]),
                SubTask(description=f"测试验证: {task}", required_capabilities=["testing"], depends_on=[]),
            ]
            # 设置依赖: coding 依赖 analysis, testing 依赖 coding
            if len(subtasks) >= 3:
                subtasks[1].depends_on = [subtasks[0].task_id]
                subtasks[2].depends_on = [subtasks[1].task_id]
            mode = OrchestrationMode.SEQUENTIAL

        # 研究/分析类任务
        elif any(kw in lower for kw in ["研究", "分析", "调研", "research", "analyze"]):
            subtasks = [
                SubTask(description=f"收集资料: {task}", required_capabilities=["search"]),
                SubTask(description=f"深度分析: {task}", required_capabilities=["analysis"]),
                SubTask(description=f"生成报告: {task}", required_capabilities=["writing"]),
            ]
            if len(subtasks) >= 3:
                subtasks[1].depends_on = [subtasks[0].task_id]
                subtasks[2].depends_on = [subtasks[1].task_id]
            mode = OrchestrationMode.SEQUENTIAL

        # 多文件/多模块任务 → 并行
        elif any(kw in lower for kw in ["批量", "多个", "并行", "batch", "parallel", "multi"]):
            subtasks = [
                SubTask(description=f"子任务-{i+1}: {task}", required_capabilities=["general"])
                for i in range(3)
            ]
            mode = OrchestrationMode.PARALLEL

        # 默认: 单任务
        else:
            subtasks = [
                SubTask(description=task, required_capabilities=["general"]),
            ]
            mode = OrchestrationMode.SEQUENTIAL

        return OrchestrationPlan(
            task=task,
            mode=mode,
            subtasks=subtasks,
            failure_policy=self._failure_policy,
            max_concurrency=self._max_concurrency,
            timeout_seconds=self._timeout,
            context=context,
        )

    async def execute(self, plan: OrchestrationPlan) -> OrchestrationResult:
        """执行编排计划.

        按模式调度子任务:
        - PARALLEL: 无依赖的子任务并行执行
        - SEQUENTIAL: 按拓扑顺序逐个执行
        - HIERARCHICAL: 第一个子任务为 leader, 其余为 workers
        """
        start_time = datetime.now(UTC)
        result = OrchestrationResult(
            plan_id=plan.plan_id,
            total_subtasks=len(plan.subtasks),
            started_at=start_time.isoformat(),
        )
        self._semaphore = asyncio.Semaphore(plan.max_concurrency)

        try:
            if plan.mode == OrchestrationMode.PARALLEL:
                await self._execute_parallel(plan, result)
            elif plan.mode == OrchestrationMode.SEQUENTIAL:
                await self._execute_sequential(plan, result)
            elif plan.mode == OrchestrationMode.HIERARCHICAL:
                await self._execute_hierarchical(plan, result)
        except OrchestrationAborted as e:
            result.status = "aborted"
            logger.warning("Orchestration aborted: %s", e)

        # 统计
        result.completed = sum(1 for st in plan.subtasks if st.status == SubTaskStatus.COMPLETED)
        result.failed = sum(1 for st in plan.subtasks if st.status == SubTaskStatus.FAILED)
        result.skipped = sum(1 for st in plan.subtasks if st.status == SubTaskStatus.SKIPPED)
        result.results = {st.task_id: st.result for st in plan.subtasks if st.result}

        if result.failed == 0 and result.skipped == 0:
            result.status = "completed"
        elif result.completed > 0:
            result.status = "partial"
        else:
            result.status = "failed"

        end_time = datetime.now(UTC)
        result.completed_at = end_time.isoformat()
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        self._executions[result.execution_id] = result
        return result

    async def _execute_parallel(self, plan: OrchestrationPlan, result: OrchestrationResult) -> None:
        """并行执行: 按依赖层级分批并行."""
        layers = self._topological_layers(plan.subtasks)
        for layer in layers:
            tasks = [self._run_subtask(st, plan) for st in layer]
            await asyncio.gather(*tasks, return_exceptions=True)
            # 检查是否需要中止
            if plan.failure_policy == FailurePolicy.ABORT:
                if any(st.status == SubTaskStatus.FAILED for st in layer):
                    raise OrchestrationAborted("Subtask failed with ABORT policy")

    async def _execute_sequential(self, plan: OrchestrationPlan, result: OrchestrationResult) -> None:
        """串行执行: 按拓扑顺序逐个."""
        ordered = self._topological_sort(plan.subtasks)
        for st in ordered:
            # 检查依赖是否满足
            deps_ok = all(
                next((s for s in plan.subtasks if s.task_id == dep), None) is not None
                and next(s for s in plan.subtasks if s.task_id == dep).status == SubTaskStatus.COMPLETED
                for dep in st.depends_on
            )
            if not deps_ok:
                st.status = SubTaskStatus.SKIPPED
                st.error = "Dependency not satisfied"
                continue
            await self._run_subtask(st, plan)
            if st.status == SubTaskStatus.FAILED and plan.failure_policy == FailurePolicy.ABORT:
                raise OrchestrationAborted(f"Subtask {st.task_id} failed with ABORT policy")

    async def _execute_hierarchical(self, plan: OrchestrationPlan, result: OrchestrationResult) -> None:
        """分层执行: 第一个为 leader, 其余并行."""
        if not plan.subtasks:
            return
        leader = plan.subtasks[0]
        workers = plan.subtasks[1:]

        # Leader 先执行
        await self._run_subtask(leader, plan)
        if leader.status == SubTaskStatus.FAILED:
            for w in workers:
                w.status = SubTaskStatus.SKIPPED
            return

        # Workers 并行
        tasks = [self._run_subtask(w, plan) for w in workers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_subtask(self, subtask: SubTask, plan: OrchestrationPlan) -> None:
        """执行单个子任务 (带重试)."""
        async with self._semaphore:
            subtask.status = SubTaskStatus.RUNNING
            subtask.started_at = datetime.now(UTC).isoformat()

            try:
                # 模拟执行 (实际生产中调用 delegator.delegate)
                subtask_result = await self._delegate_subtask(subtask, plan)
                subtask.result = subtask_result
                subtask.status = SubTaskStatus.COMPLETED
            except Exception as e:
                subtask.error = str(e)
                # 重试策略
                if plan.failure_policy == FailurePolicy.RETRY and subtask.retry_count < 1:
                    subtask.retry_count += 1
                    try:
                        subtask_result = await self._delegate_subtask(subtask, plan)
                        subtask.result = subtask_result
                        subtask.status = SubTaskStatus.COMPLETED
                        subtask.error = None
                    except Exception as retry_err:
                        subtask.status = SubTaskStatus.FAILED
                        subtask.error = str(retry_err)
                elif plan.failure_policy == FailurePolicy.SKIP:
                    subtask.status = SubTaskStatus.SKIPPED
                else:
                    subtask.status = SubTaskStatus.FAILED
            finally:
                subtask.completed_at = datetime.now(UTC).isoformat()

    async def _delegate_subtask(self, subtask: SubTask, plan: OrchestrationPlan) -> dict[str, Any]:
        """委派子任务到 Agent —— 真实实现（P1-09 批次 E-lite，2026-08-04）。

        经 CollaborationDelegator 跑真实子 AgentLoop（与 /delegate 端点同一
        运行时路径）。``plan.context`` 可携带 candidates / room_id / org_id /
        department_id / tenant_id / user_id / isolation / timeout_seconds /
        max_iterations / metadata。

        诚实性：子 agent 未成功（无候选 / failed / timeout）一律抛
        DelegationError，由上层 failure_policy（retry/skip/abort）裁决——
        绝不编造输出（取代此前 sleep(0.01) + 编造 "Completed: ..." 的假实现）。
        """
        from backend.app.core.collaboration.delegation import (
            CandidateSpec,
            DelegationError,
            DelegationRequest,
            get_delegator,
        )

        delegator = self._delegator or get_delegator()
        ctx = dict(plan.context or {})
        candidates = [
            CandidateSpec(**c) if isinstance(c, dict) else c
            for c in (ctx.get("candidates") or [])
        ]
        request = DelegationRequest(
            task=subtask.description or plan.task,
            required_capabilities=list(subtask.required_capabilities),
            candidates=candidates,
            org_id=ctx.get("org_id"),
            department_id=ctx.get("department_id"),
            room_id=ctx.get("room_id"),
            tenant_id=str(ctx.get("tenant_id") or "default"),
            user_id=str(ctx.get("user_id") or "system"),
            isolation=ctx.get("isolation"),
            wait=True,
            timeout_seconds=int(ctx.get("timeout_seconds") or plan.timeout_seconds),
            max_iterations=int(ctx.get("max_iterations") or 10),
            metadata={
                "delegator": "multi-agent-orchestrator",
                "plan_id": plan.plan_id,
                **dict(ctx.get("metadata") or {}),
            },
        )
        result = await delegator.delegate(request)
        if result.status != "completed":
            raise DelegationError(
                f"Subtask '{subtask.task_id}' delegation ended with status "
                f"'{result.status}': {result.error or 'no error detail'}"
            )
        output: Any = result.result
        if isinstance(output, dict) and "answer" in output:
            output = output["answer"]
        return {
            "task_id": subtask.task_id,
            "description": subtask.description,
            "output": output,
            "capabilities_used": subtask.required_capabilities,
            "delegation_id": result.delegation_id,
            "assigned_agent_id": result.spawned_agent_id,
        }

    def get_execution(self, execution_id: str) -> OrchestrationResult | None:
        """获取执行结果."""
        return self._executions.get(execution_id)

    def list_executions(self, limit: int = 20) -> list[OrchestrationResult]:
        """列出执行历史."""
        items = list(self._executions.values())
        items.sort(key=lambda r: r.started_at, reverse=True)
        return items[:limit]

    # ─── 拓扑排序工具 ─────────────────────────────────────────────────────────

    @staticmethod
    def _topological_sort(subtasks: list[SubTask]) -> list[SubTask]:
        """Kahn 拓扑排序."""
        task_map = {st.task_id: st for st in subtasks}
        in_degree = {st.task_id: 0 for st in subtasks}
        adj: dict[str, list[str]] = {st.task_id: [] for st in subtasks}

        for st in subtasks:
            for dep in st.depends_on:
                if dep in task_map:
                    adj[dep].append(st.task_id)
                    in_degree[st.task_id] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        ordered: list[SubTask] = []

        while queue:
            tid = queue.pop(0)
            ordered.append(task_map[tid])
            for neighbor in adj[tid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 处理环 (不应发生, 但防御性处理)
        if len(ordered) < len(subtasks):
            remaining = [st for st in subtasks if st.task_id not in {s.task_id for s in ordered}]
            ordered.extend(remaining)

        return ordered

    @staticmethod
    def _topological_layers(subtasks: list[SubTask]) -> list[list[SubTask]]:
        """按依赖层级分组 (同层可并行)."""
        task_map = {st.task_id: st for st in subtasks}
        in_degree = {st.task_id: 0 for st in subtasks}
        adj: dict[str, list[str]] = {st.task_id: [] for st in subtasks}

        for st in subtasks:
            for dep in st.depends_on:
                if dep in task_map:
                    adj[dep].append(st.task_id)
                    in_degree[st.task_id] += 1

        layers: list[list[SubTask]] = []
        remaining = set(in_degree.keys())

        while remaining:
            layer_ids = [tid for tid in remaining if in_degree[tid] == 0]
            if not layer_ids:
                # 环: 全部放入一层
                layer_ids = list(remaining)
            layers.append([task_map[tid] for tid in layer_ids])
            for tid in layer_ids:
                remaining.discard(tid)
                for neighbor in adj[tid]:
                    in_degree[neighbor] -= 1

        return layers


class OrchestrationAborted(Exception):
    """编排中止异常."""


# ─── 单例 ─────────────────────────────────────────────────────────────────────

_orchestrator: MultiAgentOrchestrator | None = None


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    """获取多Agent编排器单例."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentOrchestrator()
    return _orchestrator


def reset_multi_agent_orchestrator() -> None:
    """重置编排器 (测试用)."""
    global _orchestrator
    _orchestrator = None
