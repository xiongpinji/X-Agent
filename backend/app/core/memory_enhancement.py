"""
增强的记忆去重和融合算法 - 语义去重、向量检索优化、图谱关联
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Set, Tuple
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """记忆项"""
    memory_id: str
    content: str
    embedding: List[float]
    importance_score: float = 0.0
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "importance_score": self.importance_score,
            "access_count": self.access_count,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "metadata": self.metadata,
            "tags": list(self.tags),
        }


@dataclass
class DeduplicationResult:
    """去重结果"""
    original_count: int
    deduplicated_count: int
    removed_count: int
    removed_items: List[str]
    merge_groups: List[List[str]]
    deduplication_ratio: float = 0.0

    def __post_init__(self):
        """计算去重比率"""
        if self.original_count > 0:
            self.deduplication_ratio = self.removed_count / self.original_count


class SimilarityCalculator:
    """相似度计算器"""

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    @staticmethod
    def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
        """计算Jaccard相似度"""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """计算Levenshtein距离"""
        if len(s1) < len(s2):
            return SimilarityCalculator.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def text_similarity(text1: str, text2: str) -> float:
        """计算文本相似度"""
        # 标准化文本
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        if text1 == text2:
            return 1.0

        # 计算Levenshtein距离
        distance = SimilarityCalculator.levenshtein_distance(text1, text2)
        max_length = max(len(text1), len(text2))

        if max_length == 0:
            return 1.0

        return 1.0 - (distance / max_length)


class MemoryDeduplicator:
    """记忆去重器"""

    def __init__(self, similarity_threshold: float = 0.85):
        """初始化去重器"""
        self.similarity_threshold = similarity_threshold
        self.similarity_calc = SimilarityCalculator()

    async def deduplicate(
        self,
        memories: List[MemoryItem],
        use_embedding: bool = True,
        use_text: bool = True
    ) -> DeduplicationResult:
        """去重记忆"""
        if not memories:
            return DeduplicationResult(
                original_count=0,
                deduplicated_count=0,
                removed_count=0,
                removed_items=[],
                merge_groups=[]
            )

        # 找到相似的记忆组
        merge_groups = await self._find_similar_groups(memories, use_embedding, use_text)

        # 为每个组选择代表性记忆
        removed_items = []
        deduplicated_memories = []

        for group in merge_groups:
            if len(group) > 1:
                # 选择最重要的记忆作为代表
                representative = max(group, key=lambda m: m.importance_score)
                deduplicated_memories.append(representative)

                # 其他记忆标记为移除
                for memory in group:
                    if memory.memory_id != representative.memory_id:
                        removed_items.append(memory.memory_id)
            else:
                deduplicated_memories.append(group[0])

        return DeduplicationResult(
            original_count=len(memories),
            deduplicated_count=len(deduplicated_memories),
            removed_count=len(removed_items),
            removed_items=removed_items,
            merge_groups=[[m.memory_id for m in group] for group in merge_groups]
        )

    async def _find_similar_groups(
        self,
        memories: List[MemoryItem],
        use_embedding: bool,
        use_text: bool
    ) -> List[List[MemoryItem]]:
        """找到相似的记忆组"""
        groups = []
        visited = set()

        for i, memory1 in enumerate(memories):
            if memory1.memory_id in visited:
                continue

            group = [memory1]
            visited.add(memory1.memory_id)

            for j, memory2 in enumerate(memories[i + 1:], i + 1):
                if memory2.memory_id in visited:
                    continue

                similarity = await self._calculate_similarity(
                    memory1, memory2, use_embedding, use_text
                )

                if similarity >= self.similarity_threshold:
                    group.append(memory2)
                    visited.add(memory2.memory_id)

            groups.append(group)

        return groups

    async def _calculate_similarity(
        self,
        memory1: MemoryItem,
        memory2: MemoryItem,
        use_embedding: bool,
        use_text: bool
    ) -> float:
        """计算两个记忆的相似度"""
        similarities = []

        if use_embedding and memory1.embedding and memory2.embedding:
            embedding_sim = self.similarity_calc.cosine_similarity(
                memory1.embedding, memory2.embedding
            )
            similarities.append(embedding_sim)

        if use_text:
            text_sim = self.similarity_calc.text_similarity(
                memory1.content, memory2.content
            )
            similarities.append(text_sim)

        if not similarities:
            return 0.0

        # 返回平均相似度
        return sum(similarities) / len(similarities)


class MemoryGraphBuilder:
    """记忆图谱构建器"""

    def __init__(self):
        """初始化图谱构建器"""
        self.graph: Dict[str, Set[str]] = defaultdict(set)
        self.edge_weights: Dict[Tuple[str, str], float] = {}
        self.node_importance: Dict[str, float] = {}

    def add_memory(self, memory_id: str, importance: float = 0.0) -> None:
        """添加记忆节点"""
        self.node_importance[memory_id] = importance

    def add_relation(
        self,
        memory_id1: str,
        memory_id2: str,
        weight: float = 1.0
    ) -> None:
        """添加记忆关系"""
        self.graph[memory_id1].add(memory_id2)
        self.graph[memory_id2].add(memory_id1)

        edge_key = tuple(sorted([memory_id1, memory_id2]))
        self.edge_weights[edge_key] = weight

    def get_related_memories(
        self,
        memory_id: str,
        depth: int = 2,
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """获取相关记忆"""
        visited = set()
        queue = [(memory_id, 0, 1.0)]
        results = []

        while queue:
            current_id, current_depth, current_weight = queue.pop(0)

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            if current_id != memory_id:
                results.append((current_id, current_weight))

            if current_depth < depth:
                for neighbor_id in self.graph.get(current_id, set()):
                    if neighbor_id not in visited:
                        edge_key = tuple(sorted([current_id, neighbor_id]))
                        edge_weight = self.edge_weights.get(edge_key, 1.0)
                        new_weight = current_weight * edge_weight

                        queue.append((neighbor_id, current_depth + 1, new_weight))

        # 按权重排序并限制结果数量
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        return {
            "total_nodes": len(self.node_importance),
            "total_edges": len(self.edge_weights),
            "average_degree": (
                2 * len(self.edge_weights) / len(self.node_importance)
                if self.node_importance else 0
            ),
            "densest_node": max(
                self.graph.items(),
                key=lambda x: len(x[1]),
                default=("", set())
            )[0],
        }


class MemoryImportanceScorer:
    """记忆重要性评分器"""

    def __init__(self):
        """初始化评分器"""
        self.weights = {
            "recency": 0.2,
            "frequency": 0.3,
            "relevance": 0.3,
            "user_rating": 0.2,
        }

    def calculate_importance(
        self,
        memory: MemoryItem,
        current_time: float,
        max_age_days: int = 30
    ) -> float:
        """计算记忆重要性"""
        scores = {}

        # 新近性评分
        age_days = (current_time - memory.created_at) / (24 * 3600)
        recency_score = max(0.0, 1.0 - (age_days / max_age_days))
        scores["recency"] = recency_score

        # 频率评分
        frequency_score = min(1.0, memory.access_count / 10.0)
        scores["frequency"] = frequency_score

        # 相关性评分（从元数据获取）
        relevance_score = memory.metadata.get("relevance_score", 0.5)
        scores["relevance"] = min(1.0, max(0.0, relevance_score))

        # 用户评分
        user_rating = memory.metadata.get("user_rating", 0.5)
        scores["user_rating"] = min(1.0, max(0.0, user_rating))

        # 计算加权平均
        importance = sum(
            scores[key] * self.weights[key]
            for key in self.weights.keys()
        )

        return importance

    def update_importance_scores(
        self,
        memories: List[MemoryItem],
        current_time: Optional[float] = None
    ) -> None:
        """更新所有记忆的重要性评分"""
        if current_time is None:
            current_time = time.time()

        for memory in memories:
            memory.importance_score = self.calculate_importance(memory, current_time)


class MemoryArchiver:
    """记忆归档器"""

    def __init__(self, archive_threshold: float = 0.3):
        """初始化归档器"""
        self.archive_threshold = archive_threshold
        self.archived_memories: Dict[str, MemoryItem] = {}

    def archive_low_importance_memories(
        self,
        memories: List[MemoryItem]
    ) -> Tuple[List[MemoryItem], List[MemoryItem]]:
        """归档低重要性记忆"""
        active = []
        archived = []

        for memory in memories:
            if memory.importance_score < self.archive_threshold:
                archived.append(memory)
                self.archived_memories[memory.memory_id] = memory
            else:
                active.append(memory)

        logger.info(f"Archived {len(archived)} memories")
        return active, archived

    def restore_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """恢复归档的记忆"""
        memory = self.archived_memories.pop(memory_id, None)
        if memory:
            logger.info(f"Restored memory: {memory_id}")
        return memory

    def get_archived_memories(self) -> List[MemoryItem]:
        """获取所有归档的记忆"""
        return list(self.archived_memories.values())


class EnhancedMemorySystem:
    """增强的记忆系统"""

    def __init__(self):
        """初始化记忆系统"""
        self.deduplicator = MemoryDeduplicator()
        self.graph_builder = MemoryGraphBuilder()
        self.importance_scorer = MemoryImportanceScorer()
        self.archiver = MemoryArchiver()
        self.memories: Dict[str, MemoryItem] = {}

    async def add_memory(self, memory: MemoryItem) -> None:
        """添加记忆"""
        self.memories[memory.memory_id] = memory
        self.graph_builder.add_memory(memory.memory_id, memory.importance_score)

    async def process_memories(self) -> Dict[str, Any]:
        """处理记忆（去重、评分、归档）"""
        memories = list(self.memories.values())

        # 更新重要性评分
        self.importance_scorer.update_importance_scores(memories)

        # 去重
        dedup_result = await self.deduplicator.deduplicate(memories)

        # 移除重复的记忆
        for removed_id in dedup_result.removed_items:
            self.memories.pop(removed_id, None)

        # 归档低重要性记忆
        active, archived = self.archiver.archive_low_importance_memories(
            list(self.memories.values())
        )

        # 更新记忆字典
        self.memories = {m.memory_id: m for m in active}

        return {
            "deduplication": dedup_result.__dict__,
            "archived_count": len(archived),
            "active_count": len(active),
            "graph_stats": self.graph_builder.get_graph_stats(),
        }

    def get_related_memories(
        self,
        memory_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取相关记忆"""
        related = self.graph_builder.get_related_memories(memory_id, limit=limit)
        return [
            {
                "memory_id": mem_id,
                "content": self.memories.get(mem_id, {}).content if mem_id in self.memories else "",
                "weight": weight,
            }
            for mem_id, weight in related
        ]

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        memories = list(self.memories.values())
        return {
            "total_memories": len(memories),
            "average_importance": (
                sum(m.importance_score for m in memories) / len(memories)
                if memories else 0.0
            ),
            "archived_memories": len(self.archiver.archived_memories),
            "graph_stats": self.graph_builder.get_graph_stats(),
        }


# 全局记忆系统实例
_memory_system: Optional[EnhancedMemorySystem] = None


def get_memory_system() -> EnhancedMemorySystem:
    """获取全局记忆系统"""
    global _memory_system
    if _memory_system is None:
        _memory_system = EnhancedMemorySystem()
    return _memory_system
