"""P1-1「记忆系统真正接通」的证明性测试。

缺陷背景（实测三处缺口，缺一即用户看到的"记忆功能"形同虚设）：

1. 主管线写读键不匹配：`_plan` 里 `_build_platform_context()` 是同步方法，从未写入
   `platform_context["related_memory_preview"]`；而 `_build_user_prompt()` 正是读这个键
   （loop.py 的 "Related memory:" 一行）。于是检索在跑、结果被丢弃，prompt 恒为空。
2. 快路径不读记忆：`_is_simple_question` 会把"记住 X"/"X 是什么"判为简单问题并走
   `_fast_path_answer`，该路径不构建规划 prompt、完全不召回记忆——而这恰恰是最依赖
   记忆的一类提问。
3. 快路径不写记忆：写记忆只发生在 `_finalize_execution`（主管线尾段），快路径提前
   return，导致"请记住：X"这一轮的事实彻底丢失，后续轮次永远看不到。

验收标准（本文件断言）：
1. 同一 agent + 同一 tenant 连跑两次（均走快路径），第二次的 prompt 必须带上第一次
   写入的记忆（端到端可见）。
2. 主管线（`_plan`）的 prompt 必须带上已存记忆。
3. 记忆检索抛异常时必须降级为空预览，且不得中断主循环。
"""

from __future__ import annotations

import json

import pytest

from backend.app.core.agent import AgentLoop, AgentTrajectory
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm import BaseLLMBackend, LLMResponse, LLMRouter
from backend.app.core.memory import MemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry

# 一个高区分度的标记：只有跨运行记忆生效时，它才可能在第二次的 prompt 里出现。
MARKER = "P1_1_MEMORY_MARKER_FALCON9"


class _RecordingBackend(BaseLLMBackend):
    """Records every message list sent to the LLM and answers with a fixed string."""

    name = "recording"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def chat(self, messages, tools, *, response_format=None):  # noqa: ANN001
        self.prompts.append("\n".join(str(m.get("content", "")) for m in messages))
        return LLMResponse(content=f"结论：项目代号 {MARKER}。", model="recording")


def _related_memory_payloads(prompts: list[str]) -> list[list[dict]]:
    """Extract the JSON payloads following each `Related memory: ` line."""
    payloads: list[list[dict]] = []
    for prompt in prompts:
        for line in prompt.splitlines():
            marker = "Related memory: "
            idx = line.find(marker)
            if idx == -1:
                continue
            try:
                parsed = json.loads(line[idx + len(marker) :].strip())
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                payloads.append(parsed)
    return payloads


def _build_agent(memory, backend: _RecordingBackend) -> AgentLoop:
    return AgentLoop(
        llm_router=LLMRouter(backends=[backend]),
        memory=memory,
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )


def test_marker_task_hits_the_fast_path() -> None:
    """守卫测试：本文件的核心场景必须落在快路径上。

    若哪天 `_is_simple_question` 的判定变化把该任务推回主管线，下面两条端到端断言就
    不再能证明"快路径"被修复——此守卫会让改动者立刻察觉。
    """
    agent = _build_agent(MemorySystem(), _RecordingBackend())
    assert agent._is_simple_question(f"请记住项目代号 {MARKER} 并给出结论") is True
    assert agent._is_simple_question(f"项目代号 {MARKER} 是什么？") is True


async def test_second_run_prompt_carries_first_run_memory(tmp_path) -> None:  # noqa: ANN001
    """两次快路径运行：第二次的 prompt 必须包含第一次写入的记忆内容。"""
    memory = MemorySystem(storage_path=tmp_path / "memory.jsonl")
    backend = _RecordingBackend()
    agent = _build_agent(memory, backend)
    context = RunContext(tenant_id="tenant-p1-1", agent_id="agent-p1-1")

    # —— 第一次运行：把 MARKER 写进记忆（快路径现在也会 store(…, layer=3)）——
    backend.prompts.clear()
    first = await agent.run(context, f"请记住项目代号 {MARKER} 并给出结论")
    assert first.status == RunStatus.COMPLETED, "first run should complete"

    # 第一次运行期间尚无历史记忆，召回应为空（基线断言，防止"测试永远为真"）。
    assert not any(_related_memory_payloads(backend.prompts)), (
        "first run should have no recalled memory yet"
    )

    # —— 第二次运行：同 agent / 同 tenant，应召回第一次写入的内容 ——
    backend.prompts.clear()
    second = await agent.run(context, f"项目代号 {MARKER} 是什么？")
    assert second.status == RunStatus.COMPLETED, "second run should complete"

    payloads = _related_memory_payloads(backend.prompts)
    assert payloads, "second run prompt should include a `Related memory:` section"
    flattened = json.dumps(payloads, ensure_ascii=False)
    assert MARKER in flattened, (
        "recalled memory must be injected into the second run's prompt; "
        f"got payloads={flattened[:500]}"
    )


async def test_plan_prompt_carries_recalled_memory(tmp_path) -> None:  # noqa: ANN001
    """主管线（`_plan`）的 prompt 必须带上已存记忆。"""
    memory = MemorySystem(storage_path=tmp_path / "memory.jsonl")
    seed_context = RunContext(tenant_id="tenant-p1-1", agent_id="agent-p1-1")
    await memory.store(seed_context, content=f"项目代号 {MARKER}", layer=3, tags=["qa"])

    backend = _RecordingBackend()
    agent = _build_agent(memory, backend)
    trajectory = AgentTrajectory(task=f"把 {MARKER} 写进配置文件", goal="", stage="planning")

    await agent._plan(seed_context, trajectory, {})

    payloads = _related_memory_payloads(backend.prompts)
    assert payloads, "planning prompt should include a `Related memory:` section"
    assert MARKER in json.dumps(payloads, ensure_ascii=False), (
        f"planning prompt must carry the stored memory; got {payloads}"
    )


async def test_memory_retrieval_failure_degrades_to_empty_preview(tmp_path) -> None:  # noqa: ANN001
    """检索异常时必须降级为空预览，且主循环照常完成。"""

    class _BrokenSearchMemory(MemorySystem):
        async def search_with_scores(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("boom")

    memory = _BrokenSearchMemory(storage_path=tmp_path / "memory.jsonl")
    backend = _RecordingBackend()
    agent = _build_agent(memory, backend)

    # 1) 降级契约：召回入口自身不得把异常抛给调用方。
    preview = await agent._recall_memory_preview(
        RunContext(tenant_id="t", agent_id="a"), query="随便问一句"
    )
    assert preview == []

    # 2) 端到端：检索坏掉时，简单问题仍能正常得到回答。
    result = await agent.run(RunContext(tenant_id="t", agent_id="a"), "随便问一句")
    assert result.status == RunStatus.COMPLETED
    assert result.answer, "fast path must still answer when memory recall fails"


async def test_broken_memory_write_does_not_break_answer(tmp_path) -> None:  # noqa: ANN001
    """记忆写入失败时不得吞掉回答（快路径新增写入点的回归保护）。"""

    class _BrokenStoreMemory(MemorySystem):
        async def store(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("store boom")

    memory = _BrokenStoreMemory(storage_path=tmp_path / "memory.jsonl")
    backend = _RecordingBackend()
    agent = _build_agent(memory, backend)

    result = await agent.run(RunContext(tenant_id="t", agent_id="a"), "随便问一句")

    assert result.status == RunStatus.COMPLETED
    assert result.answer, "a failing memory write must not swallow the answer"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
