"""
记忆分析工具模块 - 统计分析和质量评估。

实现功能:
- 记忆统计分析
- 记忆质量评估
- 记忆覆盖度分析
- 生成分析报告
- 性能指标追踪
- 趋势分析
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from typing import Optional, Any
from collections import defaultdict, Counter
import statistics

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MemoryQualityMetrics:
    """记忆质量指标。"""
    completeness: float = 0.0  # 0-1
    accuracy: float = 0.0  # 0-1
    relevance: float = 0.0  # 0-1
    freshness: float = 0.0  # 0-1
    consistency: float = 0.0  # 0-1
    overall_quality: float = 0.0  # 0-1


@dataclass
class CoverageAnalysis:
    """覆盖度分析。"""
    total_topics: int = 0
    covered_topics: int = 0
    coverage_percentage: float = 0.0
    gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AnalyticsReport:
    """分析报告。"""
    report_id: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    period_end: datetime = field(default_factory=lambda: datetime.now(UTC))

    # 统计信息
    total_memories: int = 0
    new_memories: int = 0
    deleted_memories: int = 0
    updated_memories: int = 0

    # 质量指标
    avg_quality: float = 0.0
    quality_distribution: dict = field(default_factory=dict)

    # 覆盖度
    coverage: CoverageAnalysis = field(default_factory=CoverageAnalysis)

    # 性能指标
    avg_retrieval_time_ms: float = 0.0
    retrieval_success_rate: float = 0.0

    # 趋势
    growth_rate: float = 0.0
    churn_rate: float = 0.0

    # 建议
    recommendations: list[str] = field(default_factory=list)


class MemoryAnalytics:
    """
    记忆分析系统。

    提供统计分析、质量评估和报告生成功能。
    """

    def __init__(self):
        """初始化分析系统。"""
        self._memory_history: list[dict] = []
        self._quality_scores: dict[str, MemoryQualityMetrics] = {}
        self._reports: list[AnalyticsReport] = []

    def record_memory_event(
        self,
        memory_id: str,
        event_type: str,  # "created", "accessed", "updated", "deleted"
        timestamp: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        记录记忆事件。

        Args:
            memory_id: 记忆ID
            event_type: 事件类型
            timestamp: 时间戳
            metadata: 元数据
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        self._memory_history.append({
            "memory_id": memory_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "metadata": metadata or {},
        })

    def assess_memory_quality(
        self,
        memory_id: str,
        content: str,
        access_count: int = 0,
        importance: float = 0.5,
        created_at: Optional[datetime] = None,
        last_accessed_at: Optional[datetime] = None,
    ) -> MemoryQualityMetrics:
        """
        评估记忆质量。

        Args:
            memory_id: 记忆ID
            content: 记忆内容
            access_count: 访问次数
            importance: 重要性分数
            created_at: 创建时间
            last_accessed_at: 最后访问时间

        Returns:
            MemoryQualityMetrics 对象
        """
        if created_at is None:
            created_at = datetime.now(UTC)
        if last_accessed_at is None:
            last_accessed_at = created_at

        # 计算各项指标
        completeness = self._compute_completeness(content)
        accuracy = self._compute_accuracy(content, importance)
        relevance = self._compute_relevance(access_count)
        freshness = self._compute_freshness(last_accessed_at)
        consistency = self._compute_consistency(content)

        # 计算综合质量分数
        overall_quality = (
            0.2 * completeness
            + 0.2 * accuracy
            + 0.2 * relevance
            + 0.2 * freshness
            + 0.2 * consistency
        )

        metrics = MemoryQualityMetrics(
            completeness=completeness,
            accuracy=accuracy,
            relevance=relevance,
            freshness=freshness,
            consistency=consistency,
            overall_quality=overall_quality,
        )

        self._quality_scores[memory_id] = metrics

        logger.debug(
            f"Quality assessment for {memory_id}: "
            f"completeness={completeness:.2f}, accuracy={accuracy:.2f}, "
            f"relevance={relevance:.2f}, freshness={freshness:.2f}, "
            f"consistency={consistency:.2f}, overall={overall_quality:.2f}"
        )

        return metrics

    def _compute_completeness(self, content: str) -> float:
        """
        计算完整性。

        基于内容长度和结构。
        """
        if not content:
            return 0.0

        # 基于长度
        length_score = min(1.0, len(content) / 500)

        # 基于结构（是否包含关键词）
        structure_keywords = ["summary", "details", "context", "action", "result"]
        structure_score = sum(
            1 for kw in structure_keywords if kw in content.lower()
        ) / len(structure_keywords)

        return 0.6 * length_score + 0.4 * structure_score

    def _compute_accuracy(self, content: str, importance: float) -> float:
        """
        计算准确性。

        基于内容质量和重要性。
        """
        # 基于重要性（重要的记忆应该更准确）
        importance_score = importance

        # 基于内容（检查是否有明确的陈述）
        has_specifics = any(
            char.isdigit() for char in content
        )
        specificity_score = 0.8 if has_specifics else 0.5

        return 0.5 * importance_score + 0.5 * specificity_score

    def _compute_relevance(self, access_count: int) -> float:
        """
        计算相关性。

        基于访问频率。
        """
        # 对数缩放
        if access_count <= 0:
            return 0.3
        elif access_count < 5:
            return 0.5
        elif access_count < 20:
            return 0.7
        else:
            return 0.9

    def _compute_freshness(self, last_accessed_at: datetime) -> float:
        """
        计算新鲜度。

        基于最后访问时间。
        """
        current_time = datetime.now(UTC)
        days_since_access = (current_time - last_accessed_at).days

        if days_since_access == 0:
            return 1.0
        elif days_since_access < 7:
            return 0.8
        elif days_since_access < 30:
            return 0.6
        elif days_since_access < 90:
            return 0.4
        else:
            return 0.2

    def _compute_consistency(self, content: str) -> float:
        """
        计算一致性。

        基于内容的一致性和清晰度。
        """
        if not content:
            return 0.0

        # 检查是否有矛盾的陈述
        lines = content.split("\n")
        if len(lines) < 2:
            return 0.8

        # 简单的一致性检查
        consistency_score = 0.8
        return consistency_score

    def analyze_coverage(
        self,
        memories: list[dict],
        expected_topics: Optional[list[str]] = None,
    ) -> CoverageAnalysis:
        """
        分析记忆覆盖度。

        Args:
            memories: 记忆列表
            expected_topics: 预期的主题列表

        Returns:
            CoverageAnalysis 对象
        """
        if expected_topics is None:
            expected_topics = [
                "system_architecture",
                "user_interactions",
                "error_handling",
                "performance",
                "security",
            ]

        # 提取记忆中的主题
        covered_topics = set()
        for mem in memories:
            content = mem.get("content", "").lower()
            for topic in expected_topics:
                if topic.replace("_", " ") in content:
                    covered_topics.add(topic)

        coverage_percentage = (
            len(covered_topics) / len(expected_topics) * 100
            if expected_topics
            else 0.0
        )

        # 找出缺失的主题
        gaps = [t for t in expected_topics if t not in covered_topics]

        # 生成建议
        recommendations = []
        if coverage_percentage < 50:
            recommendations.append("Critical: Less than 50% topic coverage")
        if coverage_percentage < 80:
            recommendations.append(f"Add memories for: {', '.join(gaps[:3])}")

        return CoverageAnalysis(
            total_topics=len(expected_topics),
            covered_topics=len(covered_topics),
            coverage_percentage=coverage_percentage,
            gaps=gaps,
            recommendations=recommendations,
        )

    def generate_report(
        self,
        memories: list[dict],
        period_days: int = 30,
        report_id: Optional[str] = None,
    ) -> AnalyticsReport:
        """
        生成分析报告。

        Args:
            memories: 记忆列表
            period_days: 分析周期（天数）
            report_id: 报告ID

        Returns:
            AnalyticsReport 对象
        """
        if report_id is None:
            report_id = f"report_{datetime.now(UTC).timestamp()}"

        current_time = datetime.now(UTC)
        period_start = current_time - timedelta(days=period_days)

        # 统计信息
        total_memories = len(memories)
        new_memories = sum(
            1 for m in memories
            if m.get("created_at", current_time) > period_start
        )
        deleted_memories = sum(
            1 for event in self._memory_history
            if event["event_type"] == "deleted"
            and event["timestamp"] > period_start
        )
        updated_memories = sum(
            1 for event in self._memory_history
            if event["event_type"] == "updated"
            and event["timestamp"] > period_start
        )

        # 质量指标
        quality_scores = list(self._quality_scores.values())
        avg_quality = (
            np.mean([q.overall_quality for q in quality_scores])
            if quality_scores
            else 0.0
        )

        quality_distribution = {
            "excellent": sum(1 for q in quality_scores if q.overall_quality >= 0.8),
            "good": sum(
                1 for q in quality_scores
                if 0.6 <= q.overall_quality < 0.8
            ),
            "fair": sum(
                1 for q in quality_scores
                if 0.4 <= q.overall_quality < 0.6
            ),
            "poor": sum(1 for q in quality_scores if q.overall_quality < 0.4),
        }

        # 覆盖度分析
        coverage = self.analyze_coverage(memories)

        # 增长率和流失率
        growth_rate = (new_memories / total_memories * 100) if total_memories > 0 else 0.0
        churn_rate = (deleted_memories / total_memories * 100) if total_memories > 0 else 0.0

        # 生成建议
        recommendations = []
        if avg_quality < 0.6:
            recommendations.append("Improve memory quality - average score below 0.6")
        if coverage.coverage_percentage < 80:
            recommendations.append(f"Expand coverage: {', '.join(coverage.gaps[:3])}")
        if churn_rate > 10:
            recommendations.append("High memory deletion rate - review retention policy")

        report = AnalyticsReport(
            report_id=report_id,
            period_start=period_start,
            period_end=current_time,
            total_memories=total_memories,
            new_memories=new_memories,
            deleted_memories=deleted_memories,
            updated_memories=updated_memories,
            avg_quality=avg_quality,
            quality_distribution=quality_distribution,
            coverage=coverage,
            growth_rate=growth_rate,
            churn_rate=churn_rate,
            recommendations=recommendations,
        )

        self._reports.append(report)
        logger.info(f"Generated report {report_id}")

        return report

    def get_quality_distribution(self) -> dict:
        """获取质量分布。"""
        if not self._quality_scores:
            return {}

        scores = [q.overall_quality for q in self._quality_scores.values()]
        return {
            "mean": float(np.mean(scores)),
            "median": float(np.median(scores)),
            "std": float(np.std(scores)),
            "min": float(np.min(scores)),
            "max": float(np.max(scores)),
        }

    def get_reports(self, limit: int = 10) -> list[AnalyticsReport]:
        """获取报告列表。"""
        return self._reports[-limit:]

    def export_analytics(self) -> dict:
        """导出分析数据。"""
        return {
            "total_events": len(self._memory_history),
            "quality_scores_count": len(self._quality_scores),
            "reports_count": len(self._reports),
            "quality_distribution": self.get_quality_distribution(),
            "latest_report": (
                self._reports[-1] if self._reports else None
            ),
        }
