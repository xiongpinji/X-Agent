"""P1-13 残留收尾：UnifiedMemorySystem 接入 Agent 主循环的回归测试。

背景：dependencies.get_agent() 早已注入 unified_memory，但 loop.py 仅赋值
从未消费（增强层空转）。本次接线：运行结束镜像存储 + 相关记忆检索合并。
"""

from __future__ import annotations

from backend.app.core.agent import AgentLoop, AgentTrajectory
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry
from backend.app.core.unified_memory import MemoryType, UnifiedMemorySystem


def _build_agent(unified: UnifiedMemorySystem) -> AgentLoop:
    return AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
        unified_memory=unified,
    )


async def test_run_mirrors_answer_into_unified_memory() -> None:
    unified = UnifiedMemorySystem()  # 无嵌入 provider → 显式降级 keyword-only
    agent = _build_agent(unified)

    result = await agent.run(RunContext(), "创建一个 Python 函数计算斐波那契数列")

    assert result.status == RunStatus.COMPLETED
    stats = await unified.get_memory_stats()
    assert stats["total_memories"] >= 1
    stored = list(unified.memories.values())
    assert any(r.memory_type == MemoryType.EXPERIENCE for r in stored)


async def test_retrieve_related_memory_merges_unified_hits() -> None:
    unified = UnifiedMemorySystem()
    await unified.store_memory(
        content="X-Agent 支持插件运行时与技能注册",
        memory_type=MemoryType.FACT,
        tags=["xagent"],
    )
    agent = _build_agent(unified)
    trajectory = AgentTrajectory(task="X-Agent 插件", goal="X-Agent 插件", stage="observing")

    results = await agent._retrieve_related_memory(RunContext(), trajectory, {})

    unified_hits = [r for r in results if r["layer"] == "unified"]
    assert unified_hits, "unified memory hit should be merged into related memory"
    assert "插件" in unified_hits[0]["content"]


async def test_unified_memory_failure_does_not_break_run() -> None:
    class _BrokenUnified:
        async def store_memory(self, *a, **k):
            raise RuntimeError("boom")

        async def retrieve_memories(self, *a, **k):
            raise RuntimeError("boom")

    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
        unified_memory=_BrokenUnified(),
    )

    result = await agent.run(RunContext(), "介绍一下 X-Agent")

    assert result.status == RunStatus.COMPLETED
