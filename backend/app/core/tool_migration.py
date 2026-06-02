"""
工具系统迁移准备 - 并行执行、依赖管理、结果聚合
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4


class ExecutionStrategy(str, Enum):
    """执行策略"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BATCH = "batch"


@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    tool_id: str
    tool_name: str
    status: str  # success, failed, timeout
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDependency:
    """工具依赖"""
    tool_id: str
    depends_on: list[str] = field(default_factory=list)
    required: bool = True
    timeout_ms: int = 30000


@dataclass
class ExecutionPlan:
    """执行计划"""
    id: str
    tools: list[str]
    strategy: ExecutionStrategy
    dependencies: dict[str, ToolDependency] = field(default_factory=dict)
    max_parallel: int = 5
    timeout_ms: int = 300000
    created_at: str = ""


class ToolParallelExecutor:
    """
    工具并行执行器 - 支持最多5个工具并行执行
    """

    def __init__(self, max_parallel: int = 5):
        self.max_parallel = max_parallel
        self.execution_results: dict[str, ToolExecutionResult] = {}
        self.execution_history: list[ToolExecutionResult] = []

    async def execute_tools(
        self,
        tools: dict[str, Callable],
        strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL,
        timeout_ms: int = 300000,
    ) -> list[ToolExecutionResult]:
        """执行工具"""
        results = []

        if strategy == ExecutionStrategy.SEQUENTIAL:
            results = await self._execute_sequential(tools, timeout_ms)
        elif strategy == ExecutionStrategy.PARALLEL:
            results = await self._execute_parallel(tools, timeout_ms)
        elif strategy == ExecutionStrategy.BATCH:
            results = await self._execute_batch(tools, timeout_ms)

        self.execution_history.extend(results)
        return results

    async def execute_with_dependencies(
        self,
        tools: dict[str, Callable],
        dependencies: dict[str, ToolDependency],
        timeout_ms: int = 300000,
    ) -> list[ToolExecutionResult]:
        """执行带依赖的工具"""
        results = []
        executed = set()

        while len(executed) < len(tools):
            # 找到可以执行的工具（依赖已满足）
            ready_tools = {}
            for tool_id, tool_func in tools.items():
                if tool_id in executed:
                    continue

                dep = dependencies.get(tool_id)
                if not dep or all(d in executed for d in dep.depends_on):
                    ready_tools[tool_id] = tool_func

            if not ready_tools:
                break

            # 执行就绪的工具
            batch_results = await self._execute_parallel(
                ready_tools,
                timeout_ms,
                max_parallel=self.max_parallel,
            )
            results.extend(batch_results)

            # 更新已执行集合
            for result in batch_results:
                if result.status == "success":
                    executed.add(result.tool_id)

        self.execution_history.extend(results)
        return results

    async def _execute_sequential(
        self,
        tools: dict[str, Callable],
        timeout_ms: int,
    ) -> list[ToolExecutionResult]:
        """顺序执行"""
        results = []
        for tool_id, tool_func in tools.items():
            result = await self._execute_single(tool_id, tool_func, timeout_ms)
            results.append(result)
        return results

    async def _execute_parallel(
        self,
        tools: dict[str, Callable],
        timeout_ms: int,
        max_parallel: int | None = None,
    ) -> list[ToolExecutionResult]:
        """并行执行"""
        max_p = max_parallel or self.max_parallel
        results = []

        # 分批执行
        tool_items = list(tools.items())
        for i in range(0, len(tool_items), max_p):
            batch = tool_items[i : i + max_p]
            tasks = [
                self._execute_single(tool_id, tool_func, timeout_ms)
                for tool_id, tool_func in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch_results)

        return results

    async def _execute_batch(
        self,
        tools: dict[str, Callable],
        timeout_ms: int,
    ) -> list[ToolExecutionResult]:
        """批量执行"""
        # 批量执行与并行执行类似，但有更多的控制
        return await self._execute_parallel(tools, timeout_ms)

    async def _execute_single(
        self,
        tool_id: str,
        tool_func: Callable,
        timeout_ms: int,
    ) -> ToolExecutionResult:
        """执行单个工具"""
        start_time = datetime.now(UTC)

        try:
            # 执行工具
            if asyncio.iscoroutinefunction(tool_func):
                result = await asyncio.wait_for(
                    tool_func(),
                    timeout=timeout_ms / 1000.0,
                )
            else:
                result = tool_func()

            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            return ToolExecutionResult(
                tool_id=tool_id,
                tool_name=tool_id,
                status="success",
                result=result,
                execution_time_ms=execution_time,
                timestamp=datetime.now(UTC).isoformat(),
            )
        except asyncio.TimeoutError:
            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return ToolExecutionResult(
                tool_id=tool_id,
                tool_name=tool_id,
                status="timeout",
                error="Tool execution timeout",
                execution_time_ms=execution_time,
                timestamp=datetime.now(UTC).isoformat(),
            )
        except Exception as e:
            execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return ToolExecutionResult(
                tool_id=tool_id,
                tool_name=tool_id,
                status="failed",
                error=str(e),
                execution_time_ms=execution_time,
                timestamp=datetime.now(UTC).isoformat(),
            )

    def get_execution_summary(self) -> dict[str, Any]:
        """获取执行摘要"""
        if not self.execution_history:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "timeout": 0,
                "average_time_ms": 0.0,
            }

        successful = sum(1 for r in self.execution_history if r.status == "success")
        failed = sum(1 for r in self.execution_history if r.status == "failed")
        timeout = sum(1 for r in self.execution_history if r.status == "timeout")
        avg_time = sum(r.execution_time_ms for r in self.execution_history) / len(
            self.execution_history
        )

        return {
            "total_executions": len(self.execution_history),
            "successful": successful,
            "failed": failed,
            "timeout": timeout,
            "average_time_ms": avg_time,
            "success_rate": successful / len(self.execution_history),
        }


class ToolDependencyGraph:
    """
    工具依赖图 - 管理工具之间的依赖关系
    """

    def __init__(self):
        self.dependencies: dict[str, ToolDependency] = {}
        self.graph: dict[str, list[str]] = {}

    def add_dependency(
        self,
        tool_id: str,
        depends_on: list[str] | None = None,
        required: bool = True,
    ) -> None:
        """添加依赖"""
        if tool_id not in self.dependencies:
            self.dependencies[tool_id] = ToolDependency(
                tool_id=tool_id,
                depends_on=depends_on or [],
                required=required,
            )
        else:
            self.dependencies[tool_id].depends_on = depends_on or []
            self.dependencies[tool_id].required = required

        # 更新图
        if tool_id not in self.graph:
            self.graph[tool_id] = []
        self.graph[tool_id] = depends_on or []

    def get_execution_order(self, tools: list[str]) -> list[list[str]] | None:
        """获取执行顺序"""
        # 拓扑排序
        visited = set()
        order = []

        def visit(tool_id: str, visiting: set[str]) -> bool:
            if tool_id in visited:
                return True
            if tool_id in visiting:
                return False  # 循环依赖

            visiting.add(tool_id)

            dep = self.dependencies.get(tool_id)
            if dep:
                for d in dep.depends_on:
                    if not visit(d, visiting):
                        return False

            visiting.remove(tool_id)
            visited.add(tool_id)
            order.append(tool_id)
            return True

        for tool_id in tools:
            if not visit(tool_id, set()):
                return None  # 存在循环依赖

        # 分组为可并行执行的批次
        batches = []
        remaining = set(tools)

        while remaining:
            batch = []
            for tool_id in remaining:
                dep = self.dependencies.get(tool_id)
                if not dep or all(d not in remaining for d in dep.depends_on):
                    batch.append(tool_id)

            if not batch:
                break

            batches.append(batch)
            remaining -= set(batch)

        return batches if not remaining else None

    def has_circular_dependency(self) -> bool:
        """检查是否有循环依赖"""
        visited = set()
        rec_stack = set()

        def has_cycle(tool_id: str) -> bool:
            visited.add(tool_id)
            rec_stack.add(tool_id)

            dep = self.dependencies.get(tool_id)
            if dep:
                for d in dep.depends_on:
                    if d not in visited:
                        if has_cycle(d):
                            return True
                    elif d in rec_stack:
                        return True

            rec_stack.remove(tool_id)
            return False

        for tool_id in self.dependencies:
            if tool_id not in visited:
                if has_cycle(tool_id):
                    return True

        return False


class ToolResultAggregator:
    """
    工具结果聚合器 - 聚合多个工具的执行结果
    """

    def __init__(self):
        self.results: dict[str, ToolExecutionResult] = {}
        self.aggregations: dict[str, dict[str, Any]] = {}

    def add_result(self, result: ToolExecutionResult) -> None:
        """添加结果"""
        self.results[result.tool_id] = result

    def aggregate_results(
        self,
        tool_ids: list[str],
        aggregation_strategy: str = "merge",
    ) -> dict[str, Any]:
        """聚合结果"""
        results = [self.results[tid] for tid in tool_ids if tid in self.results]

        if aggregation_strategy == "merge":
            return self._merge_results(results)
        elif aggregation_strategy == "combine":
            return self._combine_results(results)
        elif aggregation_strategy == "summary":
            return self._summarize_results(results)
        else:
            return {}

    def _merge_results(self, results: list[ToolExecutionResult]) -> dict[str, Any]:
        """合并结果"""
        merged = {}
        for result in results:
            if result.status == "success":
                merged[result.tool_id] = result.result

        return merged

    def _combine_results(self, results: list[ToolExecutionResult]) -> dict[str, Any]:
        """组合结果"""
        combined = {
            "successful": [],
            "failed": [],
            "timeout": [],
        }

        for result in results:
            if result.status == "success":
                combined["successful"].append({
                    "tool_id": result.tool_id,
                    "result": result.result,
                })
            elif result.status == "failed":
                combined["failed"].append({
                    "tool_id": result.tool_id,
                    "error": result.error,
                })
            elif result.status == "timeout":
                combined["timeout"].append({
                    "tool_id": result.tool_id,
                })

        return combined

    def _summarize_results(self, results: list[ToolExecutionResult]) -> dict[str, Any]:
        """总结结果"""
        successful = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        timeout = sum(1 for r in results if r.status == "timeout")
        avg_time = sum(r.execution_time_ms for r in results) / len(results) if results else 0

        return {
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "timeout": timeout,
            "success_rate": successful / len(results) if results else 0,
            "average_execution_time_ms": avg_time,
        }

    def get_result(self, tool_id: str) -> ToolExecutionResult | None:
        """获取单个结果"""
        return self.results.get(tool_id)

    def get_all_results(self) -> dict[str, ToolExecutionResult]:
        """获取所有结果"""
        return self.results.copy()
