"""P2-11: 技能自沉淀引擎.

闭环流程:
1. 任务成功完成后, 从执行轨迹提取工具调用模式
2. 高频模式自动生成 SkillDraft
3. Curator 去重/质量门控
4. 通过的候选存入技能库 (待人工 promote 或自动 promote)
5. P2-12: promote 落盘 custom-skills/<name>/ + SkillLoader 热加载
   + ToolRegistry 增量注册（最后一公里，见 promotion.py / mount_promoted_skills）

设计原则:
- best-effort: 沉淀失败不阻断主循环
- 防膨胀: 相似度去重 + 最大技能数限制 + 低使用率淘汰
- 可审计: 每次沉淀记录来源轨迹和决策理由
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.core.skill_distillation.curator import SkillCurator
from backend.app.core.skill_distillation.generator import SkillDraft, SkillGenerator
from backend.app.core.skill_distillation.harvester import PatternHarvester
from backend.app.core.skill_distillation.promotion import (
    sanitize_skill_name,
    write_skill_package,
)

logger = logging.getLogger(__name__)


def _skill_main_py_exists(safe_name: str, base_dir: str | Path | None) -> bool:
    """检查技能包 main.py 是否已落盘（默认目录为项目 custom-skills/）。"""
    if base_dir is not None:
        skill_dir = Path(base_dir) / safe_name
    else:
        from backend.app.core.skills import get_custom_skills_dir

        skill_dir = get_custom_skills_dir() / safe_name
    return (skill_dir / "main.py").is_file()


@dataclass
class SedimentationEvent:
    """一次沉淀事件记录."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id: str = ""
    task: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    patterns_found: int = 0
    drafts_generated: int = 0
    drafts_accepted: int = 0
    drafts_rejected_duplicate: int = 0
    skill_names: list[str] = field(default_factory=list)
    decision: str = ""  # "sedimented" | "no_pattern" | "all_duplicate"


class SkillSedimentationEngine:
    """技能自沉淀引擎.

    在任务成功完成后调用, 自动从执行轨迹中提取可复用模式并生成技能。
    """

    def __init__(
        self,
        min_frequency: int = 2,
        min_sequence_length: int = 2,
        max_skills: int = 200,
        similarity_threshold: float = 0.75,
        auto_promote: bool = False,
        custom_skills_dir: str | Path | None = None,
    ):
        self._harvester = PatternHarvester(
            min_frequency=min_frequency,
            min_sequence_length=min_sequence_length,
        )
        self._generator = SkillGenerator()
        self._curator = SkillCurator(
            max_skills=max_skills,
            similarity_threshold=similarity_threshold,
        )
        self._auto_promote = auto_promote
        self._events: list[SedimentationEvent] = []
        self._trajectory_buffer: list[list[dict[str, Any]]] = []
        # P2-12: promote 落盘目录与热加载注册目标
        self._custom_skills_dir = Path(custom_skills_dir) if custom_skills_dir else None
        self._tool_registry: Any | None = None
        self._mounted_versions: dict[str, int] = {}

    @property
    def curator(self) -> SkillCurator:
        return self._curator

    @property
    def events(self) -> list[SedimentationEvent]:
        return list(self._events)

    def record_trajectory(self, trace_id: str, steps: list[dict[str, Any]]) -> None:
        """记录一次执行轨迹到缓冲区.

        在 Agent Loop 每次迭代结束后调用。
        """
        self._trajectory_buffer.append(steps)
        # 限制缓冲区大小
        if len(self._trajectory_buffer) > 100:
            self._trajectory_buffer = self._trajectory_buffer[-50:]

    async def try_sediment(
        self,
        trace_id: str,
        task: str,
        trajectory: list[dict[str, Any]],
        success: bool = True,
    ) -> SedimentationEvent:
        """尝试从成功的任务轨迹中沉淀技能.

        Args:
            trace_id: 执行追踪 ID
            task: 任务描述
            trajectory: 工具调用轨迹 [{"tool": "xxx", "success": True, ...}]
            success: 任务是否成功

        Returns:
            SedimentationEvent 沉淀事件记录
        """
        event = SedimentationEvent(trace_id=trace_id, task=task)

        if not success:
            event.decision = "task_failed"
            self._events.append(event)
            return event

        if not trajectory or len(trajectory) < 2:
            event.decision = "no_pattern"
            self._events.append(event)
            return event

        # 将当前轨迹加入缓冲区一起分析
        trajectories = [*self._trajectory_buffer, trajectory]

        # 1. 提取模式
        harvest_result = self._harvester.harvest(trajectories)
        event.patterns_found = harvest_result.reusable_candidates

        if not harvest_result.patterns:
            event.decision = "no_pattern"
            self._events.append(event)
            return event

        # 2. 生成技能草稿
        drafts = self._generator.generate_batch(harvest_result.patterns)
        event.drafts_generated = len(drafts)

        # 3. Curator 去重/质量门控
        for draft in drafts:
            status = self._curator.add_candidate(draft)
            if status == "added":
                event.drafts_accepted += 1
                event.skill_names.append(draft.name)
                if self._auto_promote:
                    self.promote_skill(draft.name)
            elif status == "duplicate":
                event.drafts_rejected_duplicate += 1

        # 4. 决策
        if event.drafts_accepted > 0:
            event.decision = "sedimented"
        elif event.drafts_rejected_duplicate > 0:
            event.decision = "all_duplicate"
        else:
            event.decision = "no_pattern"

        self._events.append(event)
        logger.info(
            "skill sedimentation: trace=%s patterns=%d accepted=%d duplicate=%d decision=%s",
            trace_id, event.patterns_found, event.drafts_accepted,
            event.drafts_rejected_duplicate, event.decision,
        )
        return event

    def get_stats(self) -> dict[str, Any]:
        """获取沉淀引擎统计."""
        curator_stats = self._curator.stats
        return {
            "total_events": len(self._events),
            "sedimented_count": sum(1 for e in self._events if e.decision == "sedimented"),
            "trajectory_buffer_size": len(self._trajectory_buffer),
            "total_skills": curator_stats.total_skills,
            "promoted": curator_stats.promoted,
            "rejected": curator_stats.rejected,
            "pruned": curator_stats.pruned,
        }

    def list_skills(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出技能库中的技能."""
        if status:
            skills = [s for s in self._curator.list_all() if s.status == status]
        else:
            skills = self._curator.list_all()
        return [s.to_dict() for s in skills]

    def promote_skill(self, name: str) -> bool:
        """人工确认技能入库（P2-12: 同时落盘 custom-skills/<name>/）.

        落盘失败返回 False 且技能保持 draft 状态——promote 的语义是
        "可在磁盘上被 SkillLoader 加载"，写不进磁盘就不算 promote 成功。
        """
        draft = next((d for d in self._curator.list_all() if d.name == name), None)
        if draft is None:
            return False
        try:
            write_skill_package(draft, base_dir=self._custom_skills_dir)
        except Exception as e:
            logger.error("Skill promote disk-write failed for '%s': %s", name, e)
            return False
        if not self._curator.promote(name):
            return False
        self._register_in_evolution_engine(draft)
        return True

    def bind_tool_registry(self, tool_registry: Any) -> None:
        """绑定 AgentLoop 的 ToolRegistry，供 mount_promoted_skills 增量注册。"""
        self._tool_registry = tool_registry

    async def mount_promoted_skills(
        self,
        tool_registry: Any | None = None,
        loader: Any | None = None,
        force: bool = False,
    ) -> list[str]:
        """把已 promote 且已落盘的技能热加载并增量注册进 ToolRegistry。

        - 只处理 curator 状态为 promoted 的技能；
        - 版本去重：工具已注册且挂载版本 >= 当前版本时跳过（force 可强制重挂），
          evolution_engine 自改进提升版本后会在下一次挂载时热更新；
        - best-effort：单个技能失败记日志跳过，不影响其余技能。

        Returns:
            本次成功挂载（新注册或热更新）的工具名列表。
        """
        from backend.app.core.skill_agent_adapter import register_skill_into_tool_registry

        registry = tool_registry or self._tool_registry
        if registry is None:
            return []

        mounted: list[str] = []
        for skill in self._curator.list_all():
            if skill.status != "promoted":
                continue
            safe_name = sanitize_skill_name(skill.name)
            current_version = self._promoted_version(safe_name)
            if (
                not force
                and getattr(registry, "get", lambda _n: None)(f"skill__{safe_name}") is not None
                and self._mounted_versions.get(safe_name, 1) >= current_version
            ):
                continue
            try:
                # 包缺失（如落盘后被删除）时补写
                base_dir = self._custom_skills_dir
                if not _skill_main_py_exists(safe_name, base_dir):
                    write_skill_package(skill, base_dir=base_dir)
                ok = await register_skill_into_tool_registry(
                    registry, safe_name, loader=loader, base_dir=base_dir
                )
            except Exception as e:
                logger.warning("Skill mount failed for '%s': %s", skill.name, e)
                continue
            if ok:
                self._mounted_versions[safe_name] = current_version
                mounted.append(f"skill__{safe_name}")
                logger.info("Skill mounted into tool registry: skill__%s (v%s)", safe_name, current_version)
        return mounted

    def _promoted_version(self, safe_name: str) -> int:
        """查询 evolution_engine 中该技能的当前版本（未登记为 1）。"""
        try:
            from backend.app.core.evolution_engine import evolution_engine

            for s in evolution_engine.promoted_skills:
                if s.name == safe_name:
                    return int(s.version)
        except Exception:
            pass
        return 1

    def _register_in_evolution_engine(self, draft: SkillDraft) -> None:
        """把落盘技能登记进 evolution_engine，纳入 usage 统计与自改进闭环。"""
        try:
            from backend.app.core.evolution_engine import PromotedSkill, evolution_engine

            main_py = draft.to_runtime_main_py()
            evolution_engine.register_promoted_skill(
                PromotedSkill(
                    id=sanitize_skill_name(draft.name),
                    name=sanitize_skill_name(draft.name),
                    description=draft.description,
                    trigger_pattern=",".join(draft.trigger_conditions[:3]),
                    code=main_py,
                    tool_sequence=[s.strip() for s in draft.source_pattern.split("→")],
                )
            )
        except Exception as e:
            logger.warning("Failed to register promoted skill in evolution engine: %s", e)

    def reject_skill(self, name: str) -> bool:
        """拒绝技能."""
        return self._curator.reject(name)

    def prune(self, min_usage: int = 1) -> int:
        """淘汰低使用率技能."""
        return self._curator.prune_low_usage(min_usage)


# ─── 单例 ─────────────────────────────────────────────────────────────────────

_engine: SkillSedimentationEngine | None = None


def get_sedimentation_engine() -> SkillSedimentationEngine:
    """获取技能自沉淀引擎单例."""
    global _engine
    if _engine is None:
        _engine = SkillSedimentationEngine()
    return _engine


def reset_sedimentation_engine() -> None:
    """重置引擎 (测试用)."""
    global _engine
    _engine = None
