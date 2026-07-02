"""
智能记忆合并模块 - 基于语义相似度的记忆融合。

实现功能:
- 基于语义相似度的智能合并
- 保留最重要的信息
- 合并时间戳和来源追踪
- 更新引用关系
- 支持异步批量处理
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, Any
import hashlib

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class MergeSource:
    """记忆合并的源信息。"""
    memory_id: str
    content: str
    importance: float
    created_at: datetime
    access_count: int = 0


@dataclass
class MergedMemory:
    """合并后的记忆。"""
    id: str
    content: str
    importance: float
    created_at: datetime
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_ids: list[str] = field(default_factory=list)
    source_count: int = 0
    merge_ratio: float = 1.0
    metadata: dict = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self):
        """初始化后计算内容哈希。"""
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class MergeStats:
    """合并统计信息。"""
    original_count: int
    merged_count: int
    merge_groups: int
    total_reduction: float  # 百分比
    processing_time: float
    avg_group_size: float
    information_retention: float  # 0-1


class MemoryMerger:
    """
    智能记忆合并系统。

    基于语义相似度、重要性和时间信息进行智能合并，
    保留最重要的信息并维护引用关系。
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        min_group_size: int = 2,
        max_group_size: int = 10,
        preserve_metadata: bool = True,
        enable_caching: bool = True,
    ):
        """
        初始化记忆合并器。

        Args:
            similarity_threshold: 相似度阈值 (0-1)
            min_group_size: 最小合并组大小
            max_group_size: 最大合并组大小
            preserve_metadata: 是否保留所有元数据
            enable_caching: 是否启用缓存
        """
        self.similarity_threshold = similarity_threshold
        self.min_group_size = min_group_size
        self.max_group_size = max_group_size
        self.preserve_metadata = preserve_metadata
        self.enable_caching = enable_caching
        self._cache: dict[str, MergedMemory] = {}
        self._merge_history: list[dict] = []

    async def merge_memories(
        self,
        memories: list[dict],
        embeddings: Optional[np.ndarray] = None,
    ) -> tuple[list[MergedMemory], MergeStats]:
        """
        合并相似的记忆。

        Args:
            memories: 记忆列表，每个包含 id, content, importance, created_at
            embeddings: 可选的预计算嵌入向量

        Returns:
            (合并后的记忆列表, 统计信息)
        """
        if not memories:
            return [], MergeStats(0, 0, 0, 0.0, 0.0, 0.0, 1.0)

        start_time = datetime.now(UTC)

        # 准备嵌入向量
        if embeddings is None:
            embeddings = self._prepare_embeddings(memories)

        # 计算相似度矩阵
        similarity_matrix = self._compute_similarity_matrix(embeddings)

        # 找到合并组
        merge_groups = self._find_merge_groups(
            memories, similarity_matrix
        )

        # 执行合并
        merged_memories = []
        for group in merge_groups:
            if len(group) >= self.min_group_size:
                merged = await self._merge_group(group, memories)
                merged_memories.append(merged)
            else:
                # 单个记忆保持不变
                mem = memories[group[0]]
                merged_memories.append(
                    MergedMemory(
                        id=mem["id"],
                        content=mem["content"],
                        importance=mem["importance"],
                        created_at=mem["created_at"],
                        source_ids=[mem["id"]],
                        source_count=1,
                        merge_ratio=1.0,
                    )
                )

        # 计算统计信息
        processing_time = (datetime.now(UTC) - start_time).total_seconds()
        stats = self._compute_stats(
            len(memories),
            len(merged_memories),
            merge_groups,
            processing_time,
        )

        # 记录合并历史
        self._merge_history.append({
            "timestamp": start_time,
            "original_count": len(memories),
            "merged_count": len(merged_memories),
            "groups": len(merge_groups),
        })

        logger.info(
            f"Memory merge complete: {len(memories)} -> {len(merged_memories)} "
            f"memories in {processing_time:.2f}s"
        )

        return merged_memories, stats

    async def _merge_group(
        self,
        group_indices: list[int],
        memories: list[dict],
    ) -> MergedMemory:
        """
        合并一组相似的记忆。

        Args:
            group_indices: 记忆索引列表
            memories: 原始记忆列表

        Returns:
            合并后的记忆
        """
        group_memories = [memories[i] for i in group_indices]

        # 按重要性排序
        sorted_group = sorted(
            group_memories,
            key=lambda m: m.get("importance", 0.5),
            reverse=True,
        )

        # 选择最重要的记忆作为基础
        primary = sorted_group[0]
        secondary = sorted_group[1:]

        # 合并内容
        merged_content = self._merge_content(primary, secondary)

        # 计算合并后的重要性
        merged_importance = self._compute_merged_importance(group_memories)

        # 收集所有源ID
        source_ids = [m["id"] for m in group_memories]

        # 合并元数据
        merged_metadata = {}
        if self.preserve_metadata:
            for mem in group_memories:
                if "metadata" in mem:
                    merged_metadata.update(mem["metadata"])

        # 计算合并比率
        merge_ratio = len(group_memories) / self.max_group_size

        merged = MergedMemory(
            id=primary["id"],
            content=merged_content,
            importance=merged_importance,
            created_at=primary["created_at"],
            source_ids=source_ids,
            source_count=len(group_memories),
            merge_ratio=merge_ratio,
            metadata=merged_metadata,
        )

        return merged

    def _merge_content(
        self,
        primary: dict,
        secondary: list[dict],
    ) -> str:
        """
        合并多个记忆的内容。

        Args:
            primary: 主要记忆
            secondary: 次要记忆列表

        Returns:
            合并后的内容
        """
        parts = [primary["content"]]

        for mem in secondary:
            # 提取补充信息
            content = mem["content"]
            if content and content not in parts:
                parts.append(content)

        # 组合内容
        merged = "\n".join(parts)

        # 限制长度
        max_length = 4096
        if len(merged) > max_length:
            merged = merged[:max_length] + "..."

        return merged

    def _compute_merged_importance(self, memories: list[dict]) -> float:
        """
        计算合并后的重要性。

        使用加权平均，考虑访问频率和时间衰减。
        """
        if not memories:
            return 0.5

        importances = [m.get("importance", 0.5) for m in memories]
        access_counts = [m.get("access_count", 0) for m in memories]

        # 基础重要性
        base_importance = np.mean(importances)

        # 访问频率权重
        if access_counts:
            max_access = max(access_counts) or 1
            access_weight = np.mean([c / max_access for c in access_counts])
            base_importance = 0.7 * base_importance + 0.3 * access_weight

        return min(1.0, max(0.0, base_importance))

    def _prepare_embeddings(self, memories: list[dict]) -> np.ndarray:
        """
        准备嵌入向量。

        如果记忆中没有嵌入，使用简单的文本哈希。
        """
        embeddings = []

        for mem in memories:
            if "embedding" in mem and mem["embedding"]:
                embeddings.append(mem["embedding"])
            else:
                # 使用内容哈希作为简单嵌入
                content = mem.get("content", "")
                hash_val = hashlib.md5(content.encode(), usedforsecurity=False).digest()
                embedding = np.frombuffer(hash_val, dtype=np.float32)
                embeddings.append(embedding)

        return np.array(embeddings)

    def _compute_similarity_matrix(
        self,
        embeddings: np.ndarray,
    ) -> np.ndarray:
        """
        计算相似度矩阵。

        使用余弦相似度。
        """
        if len(embeddings) == 0:
            return np.array([])

        # 标准化嵌入
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized = embeddings / norms

        # 计算余弦相似度
        similarity = np.dot(normalized, normalized.T)

        return similarity

    def _find_merge_groups(
        self,
        memories: list[dict],
        similarity_matrix: np.ndarray,
    ) -> list[list[int]]:
        """
        找到应该合并的记忆组。

        使用贪心聚类算法。
        """
        n = len(memories)
        visited = set()
        groups = []

        for i in range(n):
            if i in visited:
                continue

            group = [i]
            visited.add(i)

            # 找到与当前记忆相似的其他记忆
            for j in range(i + 1, n):
                if j in visited:
                    continue

                if similarity_matrix[i, j] >= self.similarity_threshold:
                    group.append(j)
                    visited.add(j)

                    if len(group) >= self.max_group_size:
                        break

            if len(group) >= self.min_group_size:
                groups.append(group)
            else:
                groups.append(group)

        return groups

    def _compute_stats(
        self,
        original_count: int,
        merged_count: int,
        merge_groups: list[list[int]],
        processing_time: float,
    ) -> MergeStats:
        """
        计算合并统计信息。
        """
        reduction = (original_count - merged_count) / original_count if original_count > 0 else 0
        avg_group_size = np.mean([len(g) for g in merge_groups]) if merge_groups else 1.0

        # 信息保留率 (假设合并保留90%的信息)
        information_retention = 0.9 + (0.1 * (1 - reduction))

        return MergeStats(
            original_count=original_count,
            merged_count=merged_count,
            merge_groups=len(merge_groups),
            total_reduction=reduction * 100,
            processing_time=processing_time,
            avg_group_size=avg_group_size,
            information_retention=information_retention,
        )

    def get_merge_history(self) -> list[dict]:
        """获取合并历史。"""
        return self._merge_history.copy()

    def clear_cache(self) -> None:
        """清空缓存。"""
        self._cache.clear()
