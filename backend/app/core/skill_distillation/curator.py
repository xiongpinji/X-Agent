"""技能管理器 - 防膨胀：去重、合并、淘汰。"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.app.core.skill_distillation.generator import SkillDraft

logger = logging.getLogger(__name__)


@dataclass
class CuratorStats:
    """管理统计。"""

    total_skills: int = 0
    promoted: int = 0
    rejected: int = 0
    merged: int = 0
    pruned: int = 0


class SkillCurator:
    """技能库管理：去重、合并相似技能、淘汰低使用率技能。"""

    def __init__(self, max_skills: int = 100, similarity_threshold: float = 0.8) -> None:
        self._max_skills = max_skills
        self._similarity_threshold = similarity_threshold
        self._skills: dict[str, SkillDraft] = {}
        self._stats = CuratorStats()

    @property
    def stats(self) -> CuratorStats:
        self._stats.total_skills = len(self._skills)
        return self._stats

    def add_candidate(self, draft: SkillDraft) -> str:
        """添加候选技能，返回状态（added / duplicate / merged）。"""
        # 去重检查
        for existing_name, existing in self._skills.items():
            sim = self._similarity(draft, existing)
            if sim >= self._similarity_threshold:
                logger.info(f"技能 '{draft.name}' 与 '{existing_name}' 相似度 {sim:.0%}，跳过")
                return "duplicate"

        self._skills[draft.name] = draft
        return "added"

    def promote(self, name: str) -> bool:
        """人工确认入库。"""
        if name in self._skills:
            self._skills[name].status = "promoted"
            self._stats.promoted += 1
            return True
        return False

    def reject(self, name: str) -> bool:
        """拒绝候选。"""
        if name in self._skills:
            self._skills[name].status = "rejected"
            self._stats.rejected += 1
            return True
        return False

    def prune_low_usage(self, min_usage: int = 1) -> int:
        """淘汰低使用率技能。"""
        to_remove = [
            name for name, skill in self._skills.items()
            if skill.status == "promoted" and hasattr(skill, "usage_count")
            and getattr(skill, "usage_count", 0) < min_usage
        ]
        for name in to_remove:
            del self._skills[name]
            self._stats.pruned += 1
        return len(to_remove)

    def list_candidates(self) -> list[SkillDraft]:
        """获取待审核候选。"""
        return [s for s in self._skills.values() if s.status == "draft"]

    def list_all(self) -> list[SkillDraft]:
        return list(self._skills.values())

    def _similarity(self, a: SkillDraft, b: SkillDraft) -> float:
        """计算两个技能草稿的相似度（基于步骤重叠）。"""
        if not a.steps or not b.steps:
            return 0.0
        set_a = set(a.steps)
        set_b = set(b.steps)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
