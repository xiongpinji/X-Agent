"""
记忆图谱增强模块 - 自动实体识别和关系推理。

实现功能:
- 自动实体识别和链接
- 关系推理
- 图谱可视化数据生成
- 社区检测
- 路径查询
- 图谱统计分析
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional, Any
import math

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """图谱中的实体。"""
    id: str
    name: str
    entity_type: str
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)
    created_at: str = ""


@dataclass
class Relation:
    """图谱中的关系。"""
    source_id: str
    target_id: str
    relation_type: str
    strength: float = 1.0
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphStats:
    """图谱统计信息。"""
    node_count: int = 0
    edge_count: int = 0
    avg_degree: float = 0.0
    density: float = 0.0
    clustering_coefficient: float = 0.0
    diameter: int = 0
    communities: int = 0


class GraphEnhancer:
    """
    记忆图谱增强系统。

    实现自动实体识别、关系推理和图谱分析。
    """

    def __init__(
        self,
        enable_entity_extraction: bool = True,
        enable_relation_inference: bool = True,
        enable_community_detection: bool = True,
    ):
        """
        初始化图谱增强器。

        Args:
            enable_entity_extraction: 是否启用实体提取
            enable_relation_inference: 是否启用关系推理
            enable_community_detection: 是否启用社区检测
        """
        self.enable_entity_extraction = enable_entity_extraction
        self.enable_relation_inference = enable_relation_inference
        self.enable_community_detection = enable_community_detection

        # 图谱数据
        self.entities: dict[str, Entity] = {}
        self.relations: dict[str, list[Relation]] = defaultdict(list)
        self.reverse_relations: dict[str, list[Relation]] = defaultdict(list)

        # 统计信息
        self.stats = GraphStats()
        self._update_history: list[dict] = []

    def add_memory_to_graph(
        self,
        memory_id: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        将记忆添加到图谱。

        Args:
            memory_id: 记忆ID
            content: 记忆内容
            metadata: 元数据
        """
        # 创建记忆节点
        entity = Entity(
            id=memory_id,
            name=content[:100],
            entity_type="memory",
            metadata=metadata or {},
        )
        self.entities[memory_id] = entity

        # 提取实体
        if self.enable_entity_extraction:
            extracted_entities = self._extract_entities(content)
            for ent in extracted_entities:
                self.entities[ent.id] = ent
                # 创建关系
                relation = Relation(
                    source_id=memory_id,
                    target_id=ent.id,
                    relation_type="mentions",
                    strength=ent.confidence,
                )
                self.relations[memory_id].append(relation)
                self.reverse_relations[ent.id].append(relation)

        # 推理关系
        if self.enable_relation_inference:
            self._infer_relations(memory_id, content)

        # 更新统计信息
        self._update_stats()

    def _extract_entities(self, text: str) -> list[Entity]:
        """
        从文本中提取实体。

        Args:
            text: 文本内容

        Returns:
            实体列表
        """
        entities = []

        # 提取大写词组（可能是实体）
        capitalized_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        for match in re.finditer(capitalized_pattern, text):
            entity_name = match.group()
            entity_id = f"entity_{hash(entity_name) % 10000000}"

            if entity_id not in self.entities:
                entity = Entity(
                    id=entity_id,
                    name=entity_name,
                    entity_type="named_entity",
                    confidence=0.8,
                )
                entities.append(entity)

        # 提取技术术语
        tech_terms = [
            "API", "database", "algorithm", "framework", "library",
            "service", "module", "component", "system", "architecture"
        ]
        for term in tech_terms:
            if term.lower() in text.lower():
                entity_id = f"entity_{hash(term) % 10000000}"
                if entity_id not in self.entities:
                    entity = Entity(
                        id=entity_id,
                        name=term,
                        entity_type="technical_term",
                        confidence=0.7,
                    )
                    entities.append(entity)

        return entities

    def _infer_relations(self, memory_id: str, content: str) -> None:
        """
        推理记忆之间的关系。

        Args:
            memory_id: 记忆ID
            content: 记忆内容
        """
        # 查找相似的记忆
        for other_id, other_entity in self.entities.items():
            if other_id == memory_id or other_entity.entity_type != "memory":
                continue

            # 计算相似度
            similarity = self._compute_text_similarity(
                content,
                other_entity.name,
            )

            if similarity > 0.5:
                relation_type = "related_to"
                if similarity > 0.8:
                    relation_type = "similar_to"

                relation = Relation(
                    source_id=memory_id,
                    target_id=other_id,
                    relation_type=relation_type,
                    strength=similarity,
                    confidence=0.7,
                )
                self.relations[memory_id].append(relation)
                self.reverse_relations[other_id].append(relation)

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度。

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度分数 (0-1)
        """
        # 简单的词汇重叠相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def find_related_memories(
        self,
        memory_id: str,
        depth: int = 2,
        limit: int = 20,
    ) -> list[tuple[str, float]]:
        """
        查找相关的记忆。

        Args:
            memory_id: 记忆ID
            depth: 搜索深度
            limit: 返回结果数量

        Returns:
            (记忆ID, 相关性分数) 列表
        """
        visited = set()
        queue = deque([(memory_id, 0, 1.0)])
        results = []

        while queue:
            current_id, current_depth, current_score = queue.popleft()

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            if current_id != memory_id:
                results.append((current_id, current_score))

            # 添加相邻节点
            for relation in self.relations.get(current_id, []):
                if relation.target_id not in visited:
                    new_score = current_score * relation.strength
                    queue.append(
                        (relation.target_id, current_depth + 1, new_score)
                    )

        # 排序并返回
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 5,
    ) -> list[list[str]]:
        """
        查找两个节点之间的路径。

        Args:
            source_id: 源节点ID
            target_id: 目标节点ID
            max_length: 最大路径长度

        Returns:
            路径列表
        """
        paths = []
        visited = set()

        def dfs(current_id: str, target: str, path: list[str]) -> None:
            if len(path) > max_length:
                return

            if current_id == target:
                paths.append(path.copy())
                return

            visited.add(current_id)

            for relation in self.relations.get(current_id, []):
                if relation.target_id not in visited:
                    path.append(relation.target_id)
                    dfs(relation.target_id, target, path)
                    path.pop()

            visited.remove(current_id)

        dfs(source_id, target_id, [source_id])
        return paths

    def detect_communities(self) -> list[list[str]]:
        """
        检测图谱中的社区。

        使用简单的标签传播算法。

        Returns:
            社区列表，每个社区是节点ID列表
        """
        if not self.entities:
            return []

        # 初始化标签
        labels = {node_id: node_id for node_id in self.entities.keys()}

        # 迭代更新标签
        for _ in range(10):
            new_labels = labels.copy()

            for node_id in self.entities.keys():
                # 获取邻居的标签
                neighbor_labels = defaultdict(int)

                for relation in self.relations.get(node_id, []):
                    neighbor_id = relation.target_id
                    neighbor_label = labels[neighbor_id]
                    neighbor_labels[neighbor_label] += 1

                for relation in self.reverse_relations.get(node_id, []):
                    neighbor_id = relation.source_id
                    neighbor_label = labels[neighbor_id]
                    neighbor_labels[neighbor_label] += 1

                # 选择最常见的标签
                if neighbor_labels:
                    most_common_label = max(
                        neighbor_labels.items(),
                        key=lambda x: x[1],
                    )[0]
                    new_labels[node_id] = most_common_label

            labels = new_labels

        # 分组社区
        communities = defaultdict(list)
        for node_id, label in labels.items():
            communities[label].append(node_id)

        return list(communities.values())

    def _update_stats(self) -> None:
        """更新图谱统计信息。"""
        node_count = len(self.entities)
        edge_count = sum(len(rels) for rels in self.relations.values())

        # 计算平均度数
        avg_degree = (2 * edge_count / node_count) if node_count > 0 else 0

        # 计算密度
        max_edges = node_count * (node_count - 1) / 2
        density = edge_count / max_edges if max_edges > 0 else 0

        # 计算聚类系数
        clustering_coeff = self._compute_clustering_coefficient()

        # 计算直径
        diameter = self._compute_diameter()

        # 检测社区
        communities = self.detect_communities() if self.enable_community_detection else []

        self.stats = GraphStats(
            node_count=node_count,
            edge_count=edge_count,
            avg_degree=avg_degree,
            density=density,
            clustering_coefficient=clustering_coeff,
            diameter=diameter,
            communities=len(communities),
        )

    def _compute_clustering_coefficient(self) -> float:
        """计算聚类系数。"""
        if len(self.entities) < 3:
            return 0.0

        coefficients = []

        for node_id in self.entities.keys():
            neighbors = set()

            for relation in self.relations.get(node_id, []):
                neighbors.add(relation.target_id)

            for relation in self.reverse_relations.get(node_id, []):
                neighbors.add(relation.source_id)

            if len(neighbors) < 2:
                continue

            # 计算邻居之间的边数
            edges_between_neighbors = 0
            for neighbor1 in neighbors:
                for relation in self.relations.get(neighbor1, []):
                    if relation.target_id in neighbors:
                        edges_between_neighbors += 1

            # 计算聚类系数
            possible_edges = len(neighbors) * (len(neighbors) - 1) / 2
            if possible_edges > 0:
                coeff = edges_between_neighbors / possible_edges
                coefficients.append(coeff)

        return np.mean(coefficients) if coefficients else 0.0

    def _compute_diameter(self) -> int:
        """计算图的直径。"""
        if len(self.entities) < 2:
            return 0

        max_distance = 0

        for start_id in list(self.entities.keys())[:10]:  # 采样以提高性能
            distances = self._bfs_distances(start_id)
            if distances:
                max_distance = max(max_distance, max(distances.values()))

        return max_distance

    def _bfs_distances(self, start_id: str) -> dict[str, int]:
        """使用BFS计算距离。"""
        distances = {start_id: 0}
        queue = deque([start_id])

        while queue:
            current_id = queue.popleft()

            for relation in self.relations.get(current_id, []):
                if relation.target_id not in distances:
                    distances[relation.target_id] = distances[current_id] + 1
                    queue.append(relation.target_id)

        return distances

    def get_visualization_data(self) -> dict:
        """
        获取用于可视化的图谱数据。

        Returns:
            包含节点和边的字典
        """
        nodes = []
        edges = []

        for entity_id, entity in self.entities.items():
            nodes.append({
                "id": entity_id,
                "label": entity.name,
                "type": entity.entity_type,
                "confidence": entity.confidence,
            })

        for source_id, relations in self.relations.items():
            for relation in relations:
                edges.append({
                    "source": source_id,
                    "target": relation.target_id,
                    "type": relation.relation_type,
                    "strength": relation.strength,
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": self.stats.node_count,
                "edge_count": self.stats.edge_count,
                "density": self.stats.density,
                "clustering_coefficient": self.stats.clustering_coefficient,
            },
        }

    def get_stats(self) -> GraphStats:
        """获取图谱统计信息。"""
        return self.stats
