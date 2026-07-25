"""P2-11: 技能自沉淀引擎.

闭环流程:
1. 任务成功完成后, 从执行轨迹提取工具调用模式
2. 高频模式自动生成 SkillDraft
3. Curator 去重/质量门控
4. 通过的候选存入技能库 (待人工 promote 或自动 promote)

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
from typing import Any

from backend.app.core.skill_distillation.curator import SkillCurator
from backend.app.core.skill_distillation.generator import SkillGenerator
from backend.app.core.skill_distillation.harvester import PatternHarvester

logger = logging.getLogger(__name__)


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
                    self._curator.promote(draft.name)
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
        """人工确认技能入库."""
        return self._curator.promote(name)

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
