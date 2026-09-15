"""P1-2「技能自学习闭环」的证明性测试。

缺陷背景：`SkillSedimentationEngine` 的 ``auto_promote`` 默认 False。后果是——
轨迹里确实发现了可复用模式、也生成了技能草稿，但草稿只躺在 curator 的**内存**里：
既不落盘 custom-skills/，进程重启后也无从加载。用户侧看到的"技能库"永远是空的，
"自学习"只是内存里的一次性烟花。

验收标准（本文件断言）：
1. 默认配置下，任务成功后沉淀出的技能**自动**落盘（无需人工调 promote_skill）。
2. 落盘产物能被**启动期加载路径**（`register_skills_into_tool_registry` + 默认
   SkillLoader）发现并注册为 ``skill__<name>`` 工具——即跨进程重启依然可用。
3. ``auto_promote=False`` 时行为回归旧语义：只进内存、不落盘（开关有效）。
4. 落盘失败不得中断沉淀（best-effort 语义保持）。
"""

from __future__ import annotations

from backend.app.core.skill_agent_adapter import register_skills_into_tool_registry
from backend.app.core.skill_distillation import (
    SkillSedimentationEngine,
    get_sedimentation_engine,
    reset_sedimentation_engine,
    sanitize_skill_name,
)
from backend.app.core.skills import SkillLoader, get_custom_skills_dir
from backend.app.core.tools import ToolRegistry

# 高区分度的工具序列：避免与仓库既有技能目录 / 其它测试产物撞名。
_PATTERN = ["p1_2_probe_read", "p1_2_probe_search", "p1_2_probe_write"]


def _trajectory(tools: list[str]) -> list[dict]:
    """构造 harvester 可识别的工具调用轨迹。"""
    return [
        {"type": "tool_call", "tool": t, "duration_ms": 5, "success": True}
        for t in tools
    ]


def _isolate(monkeypatch, tmp_path):
    """隔离进程级单例 + custom-skills 落盘目录。"""
    reset_sedimentation_engine()
    monkeypatch.setenv("XAGENT_CUSTOM_SKILLS_DIR", str(tmp_path / "custom-skills").replace("\\", "/"))
    return tmp_path / "custom-skills"


async def _sediment(engine, *, pattern: list[str]):
    """喂入 2 条相同轨迹（跨迭代缓冲）+ 当前轨迹，触发一次成功的沉淀。"""
    engine.record_trajectory("trace-1", _trajectory(pattern))
    engine.record_trajectory("trace-2", _trajectory(pattern))
    return await engine.try_sediment("trace-3", "demo task", _trajectory(pattern), success=True)


async def test_auto_promote_writes_skill_to_disk_without_manual_promote(monkeypatch, tmp_path) -> None:
    """默认配置：沉淀即落盘，无需任何人工 promote 调用。"""
    custom_dir = _isolate(monkeypatch, tmp_path)
    engine = SkillSedimentationEngine(min_frequency=2)

    # 先固化"旧行为"的失败前提：不显式 promote 就不该有磁盘产物。
    assert not custom_dir.exists() or not any(custom_dir.iterdir())

    event = await _sediment(engine, pattern=_PATTERN)

    assert event.decision == "sedimented"
    assert event.drafts_accepted >= 1
    assert event.skill_names, "sedimentation must report the accepted draft names"

    for name in event.skill_names:
        skill_dir = custom_dir / sanitize_skill_name(name)
        assert (skill_dir / "SKILL.md").is_file(), f"SKILL.md missing for auto-promoted '{name}'"
        assert (skill_dir / "main.py").is_file(), f"main.py missing for auto-promoted '{name}'"
        assert "class SkillImplementation" in (skill_dir / "main.py").read_text(encoding="utf-8")


async def test_auto_promoted_skill_is_available_after_restart(monkeypatch, tmp_path) -> None:
    """跨进程重启：新进程走启动期加载路径，仍能拿到学到的技能工具。"""
    custom_dir = _isolate(monkeypatch, tmp_path)
    engine = SkillSedimentationEngine(min_frequency=2)
    event = await _sediment(engine, pattern=_PATTERN)
    assert event.skill_names

    # —— 模拟进程重启 ——
    # 1) 沉淀引擎单例重置：curator 内存中的草稿/promoted 状态全部消失。
    reset_sedimentation_engine()
    assert get_sedimentation_engine().list_skills() == []

    # 2) 启动期路径：默认 SkillLoader 依 env 解析到同一 custom-skills/ 目录。
    assert get_custom_skills_dir() == custom_dir

    registry = ToolRegistry()
    registered = await register_skills_into_tool_registry(registry, loader=SkillLoader())

    expected = {f"skill__{sanitize_skill_name(n)}" for n in event.skill_names}
    assert expected & set(registered), (
        "auto-promoted skill must be re-discovered by the startup loading path after a "
        f"restart; expected one of {sorted(expected)}, got {sorted(registered)}"
    )
    for tool_name in expected & set(registered):
        assert registry.get(tool_name) is not None


async def test_auto_promote_disabled_keeps_drafts_in_memory_only(monkeypatch, tmp_path) -> None:
    """auto_promote=False：草稿仅存内存、不落盘（开关语义有效）。"""
    custom_dir = _isolate(monkeypatch, tmp_path)
    engine = SkillSedimentationEngine(min_frequency=2, auto_promote=False)

    event = await _sediment(engine, pattern=_PATTERN)

    assert event.decision == "sedimented"
    assert event.skill_names
    # 草稿在 curator 内存里可见……
    assert engine.list_skills(status="draft"), "draft should still be tracked in memory"
    # ……但磁盘上什么都没有（这正是 P1-2 修复前的行为）。
    assert not any(custom_dir.iterdir()) if custom_dir.exists() else True
    assert engine.list_skills(status="promoted") == []


async def test_auto_promote_write_failure_does_not_abort_sedimentation(monkeypatch, tmp_path) -> None:
    """落盘失败必须降级记日志，不能让沉淀（及其调用方主循环）崩溃。"""
    _isolate(monkeypatch, tmp_path)
    engine = SkillSedimentationEngine(min_frequency=2)

    def _boom(draft, base_dir=None):  # noqa: ANN001
        raise OSError("disk full")

    monkeypatch.setattr("backend.app.core.skill_distillation.sedimentation.write_skill_package", _boom)

    event = await _sediment(engine, pattern=_PATTERN)

    # 草稿仍被接受并留在内存，但 promote 未成功（状态不是 promoted）。
    assert event.drafts_accepted >= 1
    assert engine.list_skills(status="promoted") == []
