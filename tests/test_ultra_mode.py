"""Tests for Ultra Mode — 4-Agent 并行协调执行。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.ultra_mode import (
    UltraConfig,
    UltraOrchestrator,
    UltraResult,
    UltraSubTask,
    UltraAgentResult,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_llm_router(decompose_response: str = "", merge_response: str = "merged"):
    """Create a mock LLM router for Ultra orchestrator."""
    router = AsyncMock()

    call_count = {"n": 0}

    async def fake_chat(messages, tools, **kwargs):
        call_count["n"] += 1
        resp = MagicMock()
        # First call is decompose, second is merge
        if call_count["n"] == 1:
            resp.content = decompose_response or _default_decompose_json()
        else:
            resp.content = merge_response
        resp.tokens_used = 200
        resp.cost = 0.002
        resp.model = "test-model"
        resp.latency_ms = 100.0
        return resp

    router.chat = fake_chat
    return router


def _default_decompose_json() -> str:
    import json
    return json.dumps([
        {"description": "Subtask 1: research", "focus_area": "research"},
        {"description": "Subtask 2: implement", "focus_area": "implementation"},
    ])


# ─── Tests ────────────────────────────────────────────────────────────────────


class TestUltraConfig:
    def test_defaults(self):
        cfg = UltraConfig()
        assert cfg.max_agents == 4
        assert cfg.merge_strategy == "synthesize"
        assert cfg.timeout_seconds == 600

    def test_custom(self):
        cfg = UltraConfig(max_agents=2, merge_strategy="concat")
        assert cfg.max_agents == 2
        assert cfg.merge_strategy == "concat"


class TestUltraOrchestrator:
    async def test_execute_basic(self):
        """Basic execution: decompose → parallel agents → merge."""
        outputs = iter(["result-1", "result-2"])

        async def agent_factory(task_desc: str, context: dict) -> str:
            return next(outputs)

        router = _make_llm_router()
        orch = UltraOrchestrator(agent_factory=agent_factory, llm_router=router)
        config = UltraConfig(max_agents=2, merge_strategy="synthesize")

        result = await orch.execute("Build a web app", {}, config)

        assert isinstance(result, UltraResult)
        assert result.status in ("completed", "partial")
        assert len(result.subtasks) >= 1
        assert result.merged_answer  # non-empty

    async def test_execute_concat_strategy(self):
        """Concat strategy joins outputs."""
        async def agent_factory(task_desc: str, context: dict) -> str:
            return f"output-for: {task_desc[:20]}"

        router = _make_llm_router()
        orch = UltraOrchestrator(agent_factory=agent_factory, llm_router=router)
        config = UltraConfig(max_agents=2, merge_strategy="concat")

        result = await orch.execute("Multi-part task", {}, config)
        assert result.merge_strategy == "concat"
        assert result.merged_answer

    async def test_execute_with_agent_failure(self):
        """If one agent fails, others still complete."""
        call_count = {"n": 0}

        async def agent_factory(task_desc: str, context: dict) -> str:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Agent crashed")
            return "successful output"

        router = _make_llm_router()
        orch = UltraOrchestrator(agent_factory=agent_factory, llm_router=router)
        config = UltraConfig(max_agents=2, merge_strategy="concat")

        result = await orch.execute("Task with failure", {}, config)
        # Should still produce a result (partial)
        assert result.status in ("completed", "partial")

    async def test_execute_all_agents_fail(self):
        """If all agents fail, status is failed."""
        async def agent_factory(task_desc: str, context: dict) -> str:
            raise RuntimeError("total failure")

        router = _make_llm_router()
        orch = UltraOrchestrator(agent_factory=agent_factory, llm_router=router)
        config = UltraConfig(max_agents=2, merge_strategy="concat")

        result = await orch.execute("Doomed task", {}, config)
        assert result.status == "failed"

    async def test_result_to_dict(self):
        """UltraResult.to_dict() produces valid structure."""
        result = UltraResult(
            task="test",
            subtasks=[UltraSubTask(description="st1", focus_area="area1")],
            results=[UltraAgentResult(task_id="t1", status="completed", output="out")],
            merged_answer="merged",
            merge_strategy="concat",
            agents_used=1,
        )
        d = result.to_dict()
        assert d["task"] == "test"
        assert len(d["subtasks"]) == 1
        assert d["merged_answer"] == "merged"

    async def test_decompose_respects_max_agents(self):
        """Decompose should not produce more subtasks than max_agents."""
        import json
        many_tasks = json.dumps([
            {"description": f"Task {i}", "focus_area": f"area{i}"}
            for i in range(10)
        ])
        router = _make_llm_router(decompose_response=many_tasks)

        async def agent_factory(task_desc: str, context: dict) -> str:
            return "done"

        orch = UltraOrchestrator(agent_factory=agent_factory, llm_router=router)
        config = UltraConfig(max_agents=3)

        result = await orch.execute("Big task", {}, config)
        assert len(result.subtasks) <= 3
