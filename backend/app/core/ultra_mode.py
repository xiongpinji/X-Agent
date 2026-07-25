"""Ultra Mode — 4-Agent 并行协调执行（对标 Codex Ultra 模式）。

协调者将复杂任务拆分为 N 个独立子任务，并行委派给 N 个 Agent，
结果通过 LLM 综合/拼接/投票聚合为最终答案。

用法:
    from backend.app.core.ultra_mode import UltraOrchestrator, UltraConfig

    orchestrator = UltraOrchestrator(agent_factory=factory, llm_router=router)
    result = await orchestrator.execute("复杂任务", context, UltraConfig(max_agents=4))
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ─── 数据模型 ─────────────────────────────────────────────────────────────────


@dataclass
class UltraConfig:
    """Ultra 模式配置."""

    max_agents: int = 4
    budget_tokens_per_agent: int = 50000
    timeout_seconds: int = 600
    merge_strategy: str = "synthesize"  # synthesize | concat | vote


@dataclass
class UltraSubTask:
    """协调者拆分出的子任务."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    focus_area: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class UltraAgentResult:
    """单个子 Agent 的执行结果."""

    task_id: str
    agent_id: str = ""
    status: str = "pending"  # pending | running | completed | failed | timeout
    output: str = ""
    error: str | None = None
    tokens_used: int = 0
    duration_seconds: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class UltraResult:
    """Ultra 模式最终结果."""

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    subtasks: list[UltraSubTask] = field(default_factory=list)
    results: list[UltraAgentResult] = field(default_factory=list)
    merged_answer: str = ""
    merge_strategy: str = "synthesize"
    total_tokens: int = 0
    total_duration_seconds: float = 0.0
    agents_used: int = 0
    status: str = "completed"  # completed | partial | failed
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "task": self.task,
            "subtasks": [
                {"task_id": st.task_id, "description": st.description, "focus_area": st.focus_area}
                for st in self.subtasks
            ],
            "results": [
                {
                    "task_id": r.task_id,
                    "status": r.status,
                    "output": r.output[:2000],
                    "tokens_used": r.tokens_used,
                    "duration_seconds": r.duration_seconds,
                }
                for r in self.results
            ],
            "merged_answer": self.merged_answer,
            "merge_strategy": self.merge_strategy,
            "total_tokens": self.total_tokens,
            "total_duration_seconds": self.total_duration_seconds,
            "agents_used": self.agents_used,
            "status": self.status,
        }


# ─── 核心编排器 ───────────────────────────────────────────────────────────────


class UltraOrchestrator:
    """Ultra 模式编排器 — 拆分 → 并行执行 → 聚合.

    Args:
        agent_factory: 创建 AgentLoop 实例的工厂函数 (async callable(task, context) -> response)
        llm_router: LLMRouter 实例，用于任务拆分和结果聚合
    """

    def __init__(
        self,
        agent_factory: Callable | None = None,
        llm_router: Any | None = None,
    ) -> None:
        self._factory = agent_factory
        self._router = llm_router

    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        config: UltraConfig | None = None,
    ) -> UltraResult:
        """执行 Ultra 模式：拆分 → 并行 → 聚合.

        Args:
            task: 复杂任务描述
            context: 执行上下文 (tenant_id, user_id 等)
            config: Ultra 配置

        Returns:
            UltraResult 包含子任务、各 Agent 结果和聚合答案
        """
        config = config or UltraConfig()
        context = context or {}
        start_time = time.time()

        result = UltraResult(task=task, merge_strategy=config.merge_strategy)

        # 1. 协调者拆分任务
        subtasks = await self._decompose(task, config.max_agents)
        result.subtasks = subtasks

        if not subtasks:
            result.status = "failed"
            result.merged_answer = "任务拆分失败：无法生成子任务"
            return result

        # 2. 并行执行子任务
        agent_results = await asyncio.gather(
            *[
                self._run_agent(st, context, config)
                for st in subtasks
            ],
            return_exceptions=True,
        )

        # 处理异常
        processed_results: list[UltraAgentResult] = []
        for i, ar in enumerate(agent_results):
            if isinstance(ar, Exception):
                processed_results.append(UltraAgentResult(
                    task_id=subtasks[i].task_id,
                    status="failed",
                    error=str(ar),
                ))
            else:
                processed_results.append(ar)

        result.results = processed_results
        result.agents_used = len([r for r in processed_results if r.status == "completed"])

        # 3. 聚合结果
        successful_outputs = [r.output for r in processed_results if r.status == "completed" and r.output]
        if successful_outputs:
            result.merged_answer = await self._merge(task, successful_outputs, config.merge_strategy)
            result.status = "completed" if result.agents_used == len(subtasks) else "partial"
        else:
            result.merged_answer = ""
            result.status = "failed"

        # 4. 统计
        result.total_tokens = sum(r.tokens_used for r in processed_results)
        result.total_duration_seconds = time.time() - start_time

        logger.info(
            "Ultra execution %s: %d/%d agents completed in %.1fs",
            result.execution_id, result.agents_used, len(subtasks),
            result.total_duration_seconds,
        )
        return result

    async def _decompose(self, task: str, max_agents: int) -> list[UltraSubTask]:
        """使用 LLM 将复杂任务拆分为 N 个独立可并行的子任务."""
        if self._router is None:
            # 无 LLM 时按简单规则拆分
            return self._heuristic_decompose(task, max_agents)

        decompose_prompt = (
            f"将以下复杂任务拆分为最多 {max_agents} 个独立的、可并行执行的子任务。\n"
            f"每个子任务应该是自包含的，可以独立完成。\n\n"
            f"任务: {task}\n\n"
            f"以 JSON 数组格式返回，每个元素包含:\n"
            f'- "description": 子任务描述\n'
            f'- "focus_area": 关注领域\n\n'
            f"只返回 JSON 数组，不要其他内容。"
        )

        try:
            response = await self._router.chat(
                messages=[{"role": "user", "content": decompose_prompt}],
                tools=[],
            )
            content = response.content or ""
            # 解析 JSON
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
            items = json.loads(content)
            subtasks = []
            for item in items[:max_agents]:
                subtasks.append(UltraSubTask(
                    description=str(item.get("description", "")),
                    focus_area=str(item.get("focus_area", "")),
                ))
            return subtasks
        except Exception as exc:
            logger.warning("LLM decompose failed, using heuristic: %s", exc)
            return self._heuristic_decompose(task, max_agents)

    def _heuristic_decompose(self, task: str, max_agents: int) -> list[UltraSubTask]:
        """无 LLM 时的启发式拆分."""
        # 按句子/分号拆分
        parts = [p.strip() for p in task.replace("；", ";").split(";") if p.strip()]
        if len(parts) < 2:
            parts = [p.strip() for p in task.split("，") if p.strip()]
        if len(parts) < 2:
            parts = [task]

        subtasks = []
        for i, part in enumerate(parts[:max_agents]):
            subtasks.append(UltraSubTask(
                description=part,
                focus_area=f"part_{i + 1}",
            ))
        return subtasks

    async def _run_agent(
        self,
        subtask: UltraSubTask,
        context: dict[str, Any],
        config: UltraConfig,
    ) -> UltraAgentResult:
        """执行单个子 Agent."""
        agent_result = UltraAgentResult(
            task_id=subtask.task_id,
            agent_id=f"ultra-agent-{subtask.task_id[:8]}",
            status="running",
            started_at=datetime.now(UTC),
        )

        try:
            if self._factory is None:
                raise RuntimeError("No agent_factory configured for Ultra mode")

            # 带超时执行
            response = await asyncio.wait_for(
                self._factory(subtask.description, context),
                timeout=config.timeout_seconds,
            )

            # 解析 AgentLoop 响应
            if hasattr(response, "answer"):
                agent_result.output = response.answer or ""
                agent_result.tokens_used = getattr(response, "memory_hits", 0)
            elif isinstance(response, dict):
                agent_result.output = str(response.get("answer", response.get("output", "")))
            else:
                agent_result.output = str(response)

            agent_result.status = "completed"

        except TimeoutError:
            agent_result.status = "timeout"
            agent_result.error = f"Agent timed out after {config.timeout_seconds}s"
        except Exception as exc:
            agent_result.status = "failed"
            agent_result.error = str(exc)

        agent_result.completed_at = datetime.now(UTC)
        if agent_result.started_at:
            agent_result.duration_seconds = (
                agent_result.completed_at - agent_result.started_at
            ).total_seconds()

        return agent_result

    async def _merge(self, task: str, outputs: list[str], strategy: str) -> str:
        """聚合多个 Agent 的输出."""
        if len(outputs) == 1:
            return outputs[0]

        if strategy == "concat":
            return "\n\n---\n\n".join(outputs)

        if strategy == "vote":
            # 简单多数投票：选最长的作为主答案（启发式）
            return max(outputs, key=len)

        # synthesize: 使用 LLM 综合
        if self._router is not None:
            merge_prompt = (
                f"原始任务: {task}\n\n"
                f"以下是 {len(outputs)} 个独立 Agent 的执行结果，"
                f"请综合所有结果生成一个完整、连贯的最终答案：\n\n"
            )
            for i, output in enumerate(outputs, 1):
                merge_prompt += f"--- Agent {i} 结果 ---\n{output[:3000]}\n\n"
            merge_prompt += "请综合以上结果，输出最终答案："

            try:
                response = await self._router.chat(
                    messages=[{"role": "user", "content": merge_prompt}],
                    tools=[],
                )
                return response.content or "\n\n".join(outputs)
            except Exception as exc:
                logger.warning("LLM merge failed, falling back to concat: %s", exc)

        return "\n\n---\n\n".join(outputs)


# ─── 全局单例 ─────────────────────────────────────────────────────────────────

_ultra_orchestrator: UltraOrchestrator | None = None


def get_ultra_orchestrator() -> UltraOrchestrator:
    """获取全局 Ultra 编排器单例."""
    global _ultra_orchestrator
    if _ultra_orchestrator is None:
        _ultra_orchestrator = UltraOrchestrator()
    return _ultra_orchestrator
