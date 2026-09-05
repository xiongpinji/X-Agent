"""P2-12: 技能自动创建 + 自改进闭环接线测试.

覆盖闭环链路（数据流）：
轨迹喂入 → 沉淀草稿 → promote 落盘 custom-skills/ → ToolRegistry 可见可执行；
skill 执行 usage 记录 → 低成功率触发自改进 → 改进产物落盘为新版本；
ReflectionRecord 字段正确持久化（JSONL 容错加载/容量上限）；
loop.py 接线（record_trajectory / try_sediment / mount）在真实 AgentLoop 运行中生效。
"""

from __future__ import annotations

# --- 并行期防御（同 tests/test_skill_runtime_p1_11.py）------------------------
import sys as _sys
import types as _types

try:  # pragma: no cover - 取决于并行工作区状态
    import backend.app.main  # noqa: F401
except Exception:  # pragma: no cover
    if "backend.app.main" not in _sys.modules:
        _stub = _types.ModuleType("backend.app.main")
        _stub._rate_limiter = _types.SimpleNamespace(_windows={})
        _sys.modules["backend.app.main"] = _stub
# ------------------------------------------------------------------------

from pathlib import Path

import pytest

import backend.app.core.evolution as evolution_module
import backend.app.core.evolution_engine as evolution_engine_module
import backend.app.core.skill_distillation.sedimentation as sedimentation_module
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.evolution import EvolutionStore, ReflectionRecord
from backend.app.core.evolution_engine import EvolutionEngine, PromotedSkill
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.skill_distillation import (
    SkillSedimentationEngine,
    get_sedimentation_engine,
    reset_sedimentation_engine,
    sanitize_skill_name,
    write_skill_package,
)
from backend.app.core.skill_agent_adapter import register_skill_into_tool_registry
from backend.app.core.tools import ToolRegistry, build_default_tool_registry


def _trajectory(tools: list[str]) -> list[dict]:
    """构造 harvester 可识别的工具调用轨迹。"""
    return [
        {"type": "tool_call", "tool": t, "duration_ms": 5, "success": True}
        for t in tools
    ]


@pytest.fixture()
def isolated_engines(monkeypatch, tmp_path):
    """隔离进程级单例：沉淀引擎 + 进化引擎，避免跨测试污染。"""
    reset_sedimentation_engine()
    fresh_evolution = EvolutionEngine()
    monkeypatch.setattr(evolution_engine_module, "evolution_engine", fresh_evolution)
    yield fresh_evolution
    reset_sedimentation_engine()


# ─── 链路 1: 轨迹 → 沉淀草稿 → promote 落盘 → ToolRegistry 可见 ─────────────


class TestSedimentationToRegistry:
    async def test_full_chain(self, isolated_engines, tmp_path):
        custom_dir = tmp_path / "custom-skills"
        engine = SkillSedimentationEngine(min_frequency=2, custom_skills_dir=custom_dir)

        # 1. 轨迹喂入（跨迭代缓冲）+ 任务成功后 try_sediment
        pattern = ["search_web", "read_file", "write_file"]
        engine.record_trajectory("trace-1", _trajectory(pattern))
        engine.record_trajectory("trace-2", _trajectory(pattern))
        event = await engine.try_sediment("trace-3", "demo task", _trajectory(pattern), success=True)

        assert event.decision == "sedimented"
        assert event.drafts_accepted >= 1
        assert event.skill_names

        # 2. promote 落盘 custom-skills/<name>/
        skill_name = event.skill_names[0]
        safe_name = sanitize_skill_name(skill_name)
        assert engine.promote_skill(skill_name) is True
        skill_dir = custom_dir / safe_name
        assert (skill_dir / "SKILL.md").is_file()
        assert (skill_dir / "main.py").is_file()
        main_py = (skill_dir / "main.py").read_text(encoding="utf-8")
        assert "class SkillImplementation" in main_py
        assert safe_name in (skill_dir / "SKILL.md").read_text(encoding="utf-8")

        # 3. 热加载 + 增量注册进 ToolRegistry
        registry = ToolRegistry()
        engine.bind_tool_registry(registry)
        mounted = await engine.mount_promoted_skills()
        assert mounted == [f"skill__{safe_name}"]

        tool_name = f"skill__{safe_name}"
        assert registry.get(tool_name) is not None
        llm_defs = {d["function"]["name"] for d in registry.definitions_for_llm()}
        assert tool_name in llm_defs

        # 4. 经 ToolRegistry 真实执行（与 AgentLoop 消费路径一致）
        record = await registry.execute(RunContext(), tool_name, {})
        assert record.success, record.error
        assert record.result["success"] is True

        # 5. 重复挂载被版本去重（不重复注册）
        assert await engine.mount_promoted_skills() == []

    def test_promote_missing_skill_fails(self, isolated_engines, tmp_path):
        engine = SkillSedimentationEngine(custom_skills_dir=tmp_path / "custom-skills")
        assert engine.promote_skill("no-such-skill") is False

    async def test_mount_without_registry_is_noop(self, isolated_engines, tmp_path):
        engine = SkillSedimentationEngine(custom_skills_dir=tmp_path / "custom-skills")
        assert await engine.mount_promoted_skills() == []


# ─── 链路 2: skill 执行 usage 记录 → 低成功率触发自改进 → 落盘新版本 ────────


class _FakeRouter:
    """返回固定改进代码的假 LLM 路由（evolution_engine 只用 chat().content）。"""

    def __init__(self, improved_code: str) -> None:
        self._code = improved_code
        self.calls = 0

    async def chat(self, messages, tools, **kwargs):
        class _Resp:
            content = f"```python\n{self._code}\n```"

        self.calls += 1
        return _Resp()


_FAILING_SKILL_MAIN = '''"""故意失败的技能（测试 usage/自改进数据源）。"""

from __future__ import annotations

from backend.app.core.skills import Skill, SkillContext, SkillMetadata, SkillResult


class SkillImplementation(Skill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="flaky-skill",
            version="1.0.0",
            description="always fails",
            author="test",
        )

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        return SkillResult(success=False, error="flaky failure")
'''


class TestSkillUsageAndImprovement:
    async def test_handler_records_usage_into_evolution_engine(
        self, isolated_engines, tmp_path
    ):
        custom_dir = tmp_path / "custom-skills"
        skill_dir = custom_dir / "flaky-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "main.py").write_text(_FAILING_SKILL_MAIN, encoding="utf-8")

        # 预登记 PromotedSkill（模拟 sedimentation promote 后的登记）
        isolated_engines.register_promoted_skill(
            PromotedSkill(id="flaky-skill", name="flaky-skill", code=_FAILING_SKILL_MAIN)
        )

        registry = ToolRegistry()
        ok = await register_skill_into_tool_registry(
            registry, "flaky-skill", base_dir=str(custom_dir)
        )
        assert ok is True

        # 经 ToolRegistry 执行（handler 内部 best-effort 记录 usage）
        record = await registry.execute(RunContext(), "skill__flaky-skill", {})
        assert record.result["success"] is False

        tracked = next(
            s for s in isolated_engines.promoted_skills if s.name == "flaky-skill"
        )
        assert tracked.usage_count == 1
        assert tracked.success_rate == 0.0

    async def test_low_success_rate_triggers_improvement_and_persists(
        self, isolated_engines, tmp_path
    ):
        from backend.app.core.skill_distillation.generator import SkillDraft

        custom_dir = tmp_path / "custom-skills"
        draft = SkillDraft(
            name="flaky-skill",
            description="improvement candidate",
            steps=["step a", "step b"],
            source_pattern="a → b",
        )
        original_code = write_skill_package(draft, base_dir=custom_dir) / "main.py"
        original_code_text = original_code.read_text(encoding="utf-8")

        improved_code = original_code_text.replace(
            '"generated_by": "skill_distillation"',
            '"generated_by": "self-improvement-v2"',
        )
        engine = EvolutionEngine(llm_router=_FakeRouter(improved_code))
        engine.skills_base_dir = str(custom_dir)
        engine.register_promoted_skill(
            PromotedSkill(id="flaky-skill", name="flaky-skill", code=original_code_text)
        )

        # 3 次失败 → needs_improvement 阈值（usage>=3 且 success_rate<0.7）
        for _ in range(3):
            result = await engine.record_skill_usage("flaky-skill", False)

        assert result["improvement_triggered"] is True
        assert result["improvement"]["success"] is True
        assert result["improvement"]["new_version"] == 2
        assert "persisted_path" in result["improvement"]

        # 改进产物落盘为新版本
        persisted = Path(result["improvement"]["persisted_path"])
        assert persisted == original_code
        assert "self-improvement-v2" in persisted.read_text(encoding="utf-8")
        skill_md = (custom_dir / "flaky-skill" / "SKILL.md").read_text(encoding="utf-8")
        assert "*改进版本: v2*" in skill_md

        tracked = next(s for s in engine.promoted_skills if s.name == "flaky-skill")
        assert tracked.version == 2
        assert len(tracked.improvement_history) == 1

    async def test_usage_by_name_matches_promoted_skill(self, isolated_engines):
        engine = EvolutionEngine()
        engine.promoted_skills.append(
            PromotedSkill(id="uuid-1", name="named-skill", code="x = 1")
        )
        result = await engine.record_skill_usage("named-skill", True)
        assert result["status"] == "recorded"
        assert result["usage_count"] == 1


# ─── 链路 3: ReflectionRecord 字段正确持久化 ────────────────────────────────


class TestReflectionRecordPersistence:
    def test_fields_roundtrip(self, tmp_path):
        store_path = tmp_path / "evolution_reflections.jsonl"
        store = EvolutionStore(storage_path=store_path)
        store.add_reflection(
            ReflectionRecord(
                tenant_id="tenant-a",
                agent_id="agent-1",
                trace_id="trace-9",
                task_summary="修复登录超时问题 @ step_2_reflect",
                strengths=["completed tool calls: 6"],
                weaknesses=["auth module", "session module"],
                lessons=["token 刷新需在中间件前置"],
                next_actions=["auth module"],
            )
        )

        # 新实例（模拟进程重启）从磁盘加载
        reloaded = EvolutionStore(storage_path=store_path)
        records = reloaded.list_reflections(agent_id="agent-1")
        assert len(records) == 1
        rec = records[0]
        assert rec.task_summary == "修复登录超时问题 @ step_2_reflect"
        assert rec.strengths == ["completed tool calls: 6"]
        assert rec.weaknesses == ["auth module", "session module"]
        assert rec.lessons == ["token 刷新需在中间件前置"]
        assert rec.next_actions == ["auth module"]
        assert rec.tenant_id == "tenant-a"
        assert rec.trace_id == "trace-9"

    def test_loop_style_fields_not_silently_dropped(self, tmp_path):
        """回归：loop.py 此前传 domain/prompt/reflection/confidence 被静默丢弃。"""
        store_path = tmp_path / "evolution_reflections.jsonl"
        store = EvolutionStore(storage_path=store_path)
        store.add_reflection(
            ReflectionRecord(
                task_summary="task @ stage",
                lessons=["lesson-1"],
                next_actions=["action-1"],
            )
        )
        line = store_path.read_text(encoding="utf-8").strip()
        assert "task @ stage" in line
        assert "lesson-1" in line

    def test_corrupt_line_tolerated(self, tmp_path):
        store_path = tmp_path / "evolution_reflections.jsonl"
        store_path.write_text(
            "{ torn json line\n"
            + ReflectionRecord(task_summary="good").model_dump_json() + "\n",
            encoding="utf-8",
        )
        reloaded = EvolutionStore(storage_path=store_path)
        records = reloaded.list_reflections()
        assert len(records) == 1
        assert records[0].task_summary == "good"

    def test_capacity_cap_trims_and_compacts(self, tmp_path, monkeypatch):
        monkeypatch.setattr(evolution_module, "_MAX_REFLECTIONS", 3)
        store_path = tmp_path / "evolution_reflections.jsonl"
        store = EvolutionStore(storage_path=store_path)
        for i in range(6):
            store.add_reflection(ReflectionRecord(task_summary=f"t{i}"))

        assert len(store.list_reflections()) == 3
        lines = [
            ln for ln in store_path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        assert len(lines) == 3  # 磁盘同步压缩，不只内存裁剪

    def test_env_override_path(self, tmp_path, monkeypatch):
        override = tmp_path / "isolated" / "reflections.jsonl"
        monkeypatch.setenv("XAGENT_EVOLUTION_STORE_PATH", str(override))
        store = EvolutionStore()
        store.add_reflection(ReflectionRecord(task_summary="env"))
        assert override.is_file()


# ─── 链路 4: loop.py 接线在真实 AgentLoop 运行中生效 ────────────────────────


class TestLoopWiring:
    async def test_run_feeds_sedimentation(self, monkeypatch, isolated_engines, tmp_path):
        """完整管线的任务运行后，沉淀引擎收到轨迹并产生沉淀事件。"""
        custom_dir = tmp_path / "custom-skills"  # 隔离落盘目录
        engine = SkillSedimentationEngine(min_frequency=2, custom_skills_dir=custom_dir)
        # 直接替换模块级单例（loop.py 经 get_sedimentation_engine() 取用）
        monkeypatch.setattr(sedimentation_module, "_engine", engine)

        agent = _build_agent()
        result = await agent.run(RunContext(permission_scope=["tools:read"]), "echo: hello")
        assert result.status == RunStatus.COMPLETED

        # 任务完成钩子已产生沉淀事件（决策可以是 no_pattern，但事件必须存在）
        assert engine.events, "try_sediment should have recorded an event"
        assert engine.events[-1].decision in (
            "sedimented", "no_pattern", "all_duplicate", "task_failed",
        )

    async def test_feed_sedimentation_is_incremental_and_silent(self, isolated_engines):
        agent = _build_agent()

        class _FakeToolCall:
            tool_name = "echo"
            success = True
            latency_ms = 3.0

        engine = get_sedimentation_engine()
        calls = [_FakeToolCall(), _FakeToolCall()]
        seen = agent._feed_sedimentation(RunContext(), calls, 0)
        assert seen == 2
        assert len(engine._trajectory_buffer) == 1
        # 增量：无新增调用时不重复喂入
        seen = agent._feed_sedimentation(RunContext(), calls, 2)
        assert seen == 2
        assert len(engine._trajectory_buffer) == 1

        # 引擎异常时静默降级（不抛出）
        import backend.app.core.skill_distillation as sd_pkg

        def _boom():
            raise RuntimeError("boom")

        monkeypatch_holder = _MonkeyAttr(sd_pkg, "get_sedimentation_engine", _boom)
        try:
            # loop 内部 from package import get_sedimentation_engine → 打补丁于包属性
            assert agent._feed_sedimentation(RunContext(), calls + [_FakeToolCall()], 2) == 3
        finally:
            monkeypatch_holder.restore()


class _MonkeyAttr:
    """最小属性替换器（避免引入 pytest fixture 到非 fixture 位置）。"""

    def __init__(self, obj, name, value):
        self._obj = obj
        self._name = name
        self._saved = getattr(obj, name)
        setattr(obj, name, value)

    def restore(self):
        setattr(self._obj, self._name, self._saved)


def _build_agent():
    from backend.app.core.agent import AgentLoop

    return AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
