"""
记忆重要性评分模块 - 多维度评分系统。

实现功能:
- 基于访问频率的评分
- 基于时间衰减的评分
- 基于关联度的评分
- 基于用户反馈的评分
- 动态权重调整
- 实时评分更新
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class ImportanceScores:
    """多维度重要性评分。"""
    access_frequency_score: float = 0.0
    temporal_decay_score: float = 0.0
    association_score: float = 0.0
    user_feedback_score: float = 0.0
    composite_score: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ImportanceWeights:
    """重要性评分权重。"""
    access_frequency_weight: float = 0.3
    temporal_decay_weight: float = 0.2
    association_weight: float = 0.3
    user_feedback_weight: float = 0.2

    def normalize(self) -> None:
        """标准化权重使其和为1。"""
        total = (
            self.access_frequency_weight
            + self.temporal_decay_weight
            + self.association_weight
            + self.user_feedback_weight
        )
        if total > 0:
            self.access_frequency_weight /= total
            self.temporal_decay_weight /= total
            self.association_weight /= total
            self.user_feedback_weight /= total


class MemoryImportanceScorer:
    """
    记忆重要性评分系统。

    基于多个维度计算记忆的重要性，支持动态权重调整。
    """

    def __init__(
        self,
        weights: ImportanceWeights | None = None,
        temporal_decay_factor: float = 0.95,
        max_access_count: int = 1000,
        feedback_scale: float = 1.0,
    ):
        """
        初始化重要性评分器。

        Args:
            weights: 评分权重
            temporal_decay_factor: 时间衰减因子 (0-1)
            max_access_count: 最大访问计数
            feedback_scale: 用户反馈缩放因子
        """
        self.weights = weights or ImportanceWeights()
        self.weights.normalize()
        self.temporal_decay_factor = temporal_decay_factor
        self.max_access_count = max_access_count
        self.feedback_scale = feedback_scale

        # 统计信息
        self._scoring_history: list[dict] = []
        self._weight_adjustments: list[dict] = []

    def compute_importance(
        self,
        memory_id: str,
        created_at: datetime,
        access_count: int = 0,
        association_count: int = 0,
        user_feedback: float = 0.0,
        current_time: datetime | None = None,
    ) -> ImportanceScores:
        """
        计算记忆的重要性评分。

        Args:
            memory_id: 记忆ID
            created_at: 创建时间
            access_count: 访问次数
            association_count: 关联数量
            user_feedback: 用户反馈 (-1 到 1)
            current_time: 当前时间

        Returns:
            ImportanceScores 对象
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        # 计算各维度评分
        access_score = self._compute_access_frequency_score(access_count)
        temporal_score = self._compute_temporal_decay_score(
            created_at, current_time
        )
        association_score = self._compute_association_score(association_count)
        feedback_score = self._compute_user_feedback_score(user_feedback)

        # 计算综合评分
        composite_score = (
            self.weights.access_frequency_weight * access_score
            + self.weights.temporal_decay_weight * temporal_score
            + self.weights.association_weight * association_score
            + self.weights.user_feedback_weight * feedback_score
        )

        scores = ImportanceScores(
            access_frequency_score=access_score,
            temporal_decay_score=temporal_score,
            association_score=association_score,
            user_feedback_score=feedback_score,
            composite_score=composite_score,
        )

        # 记录评分历史
        self._scoring_history.append({
            "memory_id": memory_id,
            "timestamp": current_time,
            "scores": scores,
        })

        logger.debug(
            f"Computed importance for {memory_id}: "
            f"access={access_score:.3f}, temporal={temporal_score:.3f}, "
            f"association={association_score:.3f}, feedback={feedback_score:.3f}, "
            f"composite={composite_score:.3f}"
        )

        return scores

    def _compute_access_frequency_score(self, access_count: int) -> float:
        """
        基于访问频率计算评分。

        使用对数缩放以避免极端值。
        """
        if access_count <= 0:
            return 0.0

        # 对数缩放
        normalized = math.log(access_count + 1) / math.log(self.max_access_count + 1)
        return min(1.0, normalized)

    def _compute_temporal_decay_score(
        self,
        created_at: datetime,
        current_time: datetime,
    ) -> float:
        """
        基于时间衰减计算评分。

        最近创建的记忆得分更高，随时间指数衰减。
        """
        if created_at > current_time:
            return 1.0

        # 计算时间差（天数）
        time_diff = (current_time - created_at).total_seconds() / (24 * 3600)

        # 指数衰减
        decay_score = math.pow(self.temporal_decay_factor, time_diff)

        return max(0.0, min(1.0, decay_score))

    def _compute_association_score(self, association_count: int) -> float:
        """
        基于关联度计算评分。

        与其他记忆关联越多，重要性越高。
        """
        if association_count <= 0:
            return 0.0

        # 对数缩放
        max_associations = 100
        normalized = math.log(association_count + 1) / math.log(max_associations + 1)
        return min(1.0, normalized)

    def _compute_user_feedback_score(self, user_feedback: float) -> float:
        """
        基于用户反馈计算评分。

        用户反馈范围: -1 (不重要) 到 1 (非常重要)
        """
        # 将反馈从 [-1, 1] 映射到 [0, 1]
        feedback_score = (user_feedback + 1) / 2
        return max(0.0, min(1.0, feedback_score))

    def adjust_weights(
        self,
        access_frequency_weight: float | None = None,
        temporal_decay_weight: float | None = None,
        association_weight: float | None = None,
        user_feedback_weight: float | None = None,
    ) -> None:
        """
        动态调整评分权重。

        Args:
            access_frequency_weight: 访问频率权重
            temporal_decay_weight: 时间衰减权重
            association_weight: 关联度权重
            user_feedback_weight: 用户反馈权重
        """
        old_weights = {
            "access_frequency": self.weights.access_frequency_weight,
            "temporal_decay": self.weights.temporal_decay_weight,
            "association": self.weights.association_weight,
            "user_feedback": self.weights.user_feedback_weight,
        }

        if access_frequency_weight is not None:
            self.weights.access_frequency_weight = access_frequency_weight
        if temporal_decay_weight is not None:
            self.weights.temporal_decay_weight = temporal_decay_weight
        if association_weight is not None:
            self.weights.association_weight = association_weight
        if user_feedback_weight is not None:
            self.weights.user_feedback_weight = user_feedback_weight

        self.weights.normalize()

        new_weights = {
            "access_frequency": self.weights.access_frequency_weight,
            "temporal_decay": self.weights.temporal_decay_weight,
            "association": self.weights.association_weight,
            "user_feedback": self.weights.user_feedback_weight,
        }

        # 记录权重调整
        self._weight_adjustments.append({
            "timestamp": datetime.now(UTC),
            "old_weights": old_weights,
            "new_weights": new_weights,
        })

        logger.info(f"Adjusted importance weights: {new_weights}")

    def batch_compute_importance(
        self,
        memories: list[dict],
        current_time: datetime | None = None,
    ) -> dict[str, ImportanceScores]:
        """
        批量计算记忆重要性。

        Args:
            memories: 记忆列表，每个包含必要的字段
            current_time: 当前时间

        Returns:
            {memory_id: ImportanceScores} 映射
        """
        if current_time is None:
            current_time = datetime.now(UTC)

        scores = {}
        for mem in memories:
            score = self.compute_importance(
                memory_id=mem.get("id", ""),
                created_at=mem.get("created_at", current_time),
                access_count=mem.get("access_count", 0),
                association_count=mem.get("association_count", 0),
                user_feedback=mem.get("user_feedback", 0.0),
                current_time=current_time,
            )
            scores[mem.get("id", "")] = score

        return scores

    def get_scoring_history(self, limit: int = 100) -> list[dict]:
        """获取评分历史。"""
        return self._scoring_history[-limit:]

    def get_weight_adjustments(self) -> list[dict]:
        """获取权重调整历史。"""
        return self._weight_adjustments.copy()

    def export_weights(self) -> dict:
        """导出当前权重配置。"""
        return {
            "access_frequency_weight": self.weights.access_frequency_weight,
            "temporal_decay_weight": self.weights.temporal_decay_weight,
            "association_weight": self.weights.association_weight,
            "user_feedback_weight": self.weights.user_feedback_weight,
            "temporal_decay_factor": self.temporal_decay_factor,
            "max_access_count": self.max_access_count,
        }

    def import_weights(self, config: dict) -> None:
        """导入权重配置。"""
        if "access_frequency_weight" in config:
            self.weights.access_frequency_weight = config["access_frequency_weight"]
        if "temporal_decay_weight" in config:
            self.weights.temporal_decay_weight = config["temporal_decay_weight"]
        if "association_weight" in config:
            self.weights.association_weight = config["association_weight"]
        if "user_feedback_weight" in config:
            self.weights.user_feedback_weight = config["user_feedback_weight"]
        if "temporal_decay_factor" in config:
            self.temporal_decay_factor = config["temporal_decay_factor"]
        if "max_access_count" in config:
            self.max_access_count = config["max_access_count"]

        self.weights.normalize()
        logger.info("Imported importance weights configuration")
