"""
多模态检索模块 - 实现跨模态搜索和检索能力

支持的检索类型:
1. 文本到图像检索 (Text-to-Image)
2. 图像到文本检索 (Image-to-Text)
3. 视频检索 (Video Retrieval)
4. 音频检索 (Audio Retrieval)
5. 混合模态检索 (Hybrid Retrieval)
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class RetrievalType(str, Enum):
    """检索类型枚举"""
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_TEXT = "image_to_text"
    TEXT_TO_VIDEO = "text_to_video"
    VIDEO_TO_TEXT = "video_to_text"
    AUDIO_TO_TEXT = "audio_to_text"
    TEXT_TO_AUDIO = "text_to_audio"
    HYBRID = "hybrid"
    CROSS_MODAL = "cross_modal"


@dataclass
class RetrievalQuery:
    """检索查询"""
    query_vector: list[float]
    query_type: RetrievalType
    modality: str  # 查询的模态
    top_k: int = 10
    threshold: float = 0.0  # 相似度阈值
    filters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """单个检索结果"""
    item_id: str
    similarity_score: float
    modality: str
    content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rank: int = 0


@dataclass
class MultimodalRetrievalResults:
    """多模态检索结果集"""
    query_id: str
    retrieval_type: RetrievalType
    results: list[RetrievalResult]
    total_count: int
    query_time_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ModalityIndexer:
    """模态索引器 - 为不同模态的内容建立索引"""

    def __init__(self, index_dim: int = 512):
        self.index_dim = index_dim
        self.indices: dict[str, dict[str, Any]] = {}
        self._initialize_indices()

    def _initialize_indices(self):
        """初始化各模态的索引"""
        modalities = ["text", "image", "video", "audio", "structured"]
        for modality in modalities:
            self.indices[modality] = {
                "vectors": [],
                "ids": [],
                "metadata": [],
                "count": 0,
            }

    def add_item(
        self,
        item_id: str,
        vector: list[float],
        modality: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """添加项目到索引"""
        if modality not in self.indices:
            self.indices[modality] = {
                "vectors": [],
                "ids": [],
                "metadata": [],
                "count": 0,
            }

        # 确保向量维度正确
        if len(vector) != self.index_dim:
            vector = self._normalize_vector(vector)

        self.indices[modality]["vectors"].append(vector)
        self.indices[modality]["ids"].append(item_id)
        self.indices[modality]["metadata"].append(metadata or {})
        self.indices[modality]["count"] += 1

    def search(
        self,
        query_vector: list[float],
        modality: str,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> list[tuple[str, float]]:
        """在指定模态中搜索"""
        if modality not in self.indices:
            return []

        index = self.indices[modality]
        if index["count"] == 0:
            return []

        # 计算相似度
        similarities = []
        for i, vector in enumerate(index["vectors"]):
            similarity = self._cosine_similarity(query_vector, vector)
            if similarity >= threshold:
                similarities.append((index["ids"][i], similarity, i))

        # 排序并返回top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [(item_id, score) for item_id, score, _ in similarities[:top_k]]

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        """将向量归一化到目标维度"""
        if len(vector) == self.index_dim:
            return vector

        if len(vector) < self.index_dim:
            # 填充
            return vector + [0.0] * (self.index_dim - len(vector))
        else:
            # 截断
            return vector[:self.index_dim]

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class CrossModalRetriever:
    """跨模态检索器"""

    def __init__(self, index_dim: int = 512):
        self.index_dim = index_dim
        self.indexer = ModalityIndexer(index_dim=index_dim)
        self._alignment_cache: dict[str, float] = {}

    async def retrieve(
        self,
        query: RetrievalQuery,
    ) -> MultimodalRetrievalResults:
        """执行检索"""
        import time
        start_time = time.time()

        results = []

        if query.query_type == RetrievalType.HYBRID:
            results = await self._hybrid_retrieve(query)
        elif query.query_type == RetrievalType.CROSS_MODAL:
            results = await self._cross_modal_retrieve(query)
        else:
            results = await self._single_modal_retrieve(query)

        query_time_ms = (time.time() - start_time) * 1000

        return MultimodalRetrievalResults(
            query_id=query.metadata.get("query_id", "unknown"),
            retrieval_type=query.query_type,
            results=results,
            total_count=len(results),
            query_time_ms=query_time_ms,
        )

    async def _single_modal_retrieve(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """单模态检索"""
        results = []

        # 确定目标模态
        target_modality = self._get_target_modality(query.query_type)

        # 搜索
        matches = self.indexer.search(
            query.query_vector,
            target_modality,
            top_k=query.top_k,
            threshold=query.threshold,
        )

        # 构建结果
        for rank, (item_id, score) in enumerate(matches, 1):
            result = RetrievalResult(
                item_id=item_id,
                similarity_score=score,
                modality=target_modality,
                rank=rank,
            )
            results.append(result)

        return results

    async def _cross_modal_retrieve(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """跨模态检索"""
        results = []

        # 在所有模态中搜索
        all_modalities = ["text", "image", "video", "audio"]

        tasks = [
            self._search_modality(query, modality)
            for modality in all_modalities
        ]

        modality_results = await asyncio.gather(*tasks)

        # 合并结果
        combined = []
        for modality, matches in zip(all_modalities, modality_results):
            for item_id, score in matches:
                combined.append((item_id, score, modality))

        # 排序
        combined.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        for rank, (item_id, score, modality) in enumerate(combined[:query.top_k], 1):
            result = RetrievalResult(
                item_id=item_id,
                similarity_score=score,
                modality=modality,
                rank=rank,
            )
            results.append(result)

        return results

    async def _hybrid_retrieve(
        self,
        query: RetrievalQuery,
    ) -> list[RetrievalResult]:
        """混合检索 - 结合多个检索策略"""
        results = []

        # 执行多个检索任务
        tasks = [
            self._single_modal_retrieve(query),
            self._cross_modal_retrieve(query),
        ]

        all_results = await asyncio.gather(*tasks)

        # 合并结果，去重
        seen = set()
        combined = []

        for result_list in all_results:
            for result in result_list:
                if result.item_id not in seen:
                    combined.append(result)
                    seen.add(result.item_id)

        # 按相似度排序
        combined.sort(key=lambda x: x.similarity_score, reverse=True)

        # 更新排名
        for rank, result in enumerate(combined[:query.top_k], 1):
            result.rank = rank
            results.append(result)

        return results

    async def _search_modality(
        self,
        query: RetrievalQuery,
        modality: str,
    ) -> list[tuple[str, float]]:
        """搜索特定模态"""
        return self.indexer.search(
            query.query_vector,
            modality,
            top_k=query.top_k,
            threshold=query.threshold,
        )

    @staticmethod
    def _get_target_modality(query_type: RetrievalType) -> str:
        """根据查询类型获取目标模态"""
        mapping = {
            RetrievalType.TEXT_TO_IMAGE: "image",
            RetrievalType.IMAGE_TO_TEXT: "text",
            RetrievalType.TEXT_TO_VIDEO: "video",
            RetrievalType.VIDEO_TO_TEXT: "text",
            RetrievalType.AUDIO_TO_TEXT: "text",
            RetrievalType.TEXT_TO_AUDIO: "audio",
        }
        return mapping.get(query_type, "text")


class MultimodalRetriever:
    """多模态检索引擎"""

    def __init__(self, index_dim: int = 512):
        self.index_dim = index_dim
        self.cross_modal_retriever = CrossModalRetriever(index_dim=index_dim)
        self._query_cache: dict[str, MultimodalRetrievalResults] = {}

    async def retrieve(
        self,
        query_vector: list[float],
        query_type: RetrievalType = RetrievalType.HYBRID,
        modality: str = "text",
        top_k: int = 10,
        threshold: float = 0.0,
        use_cache: bool = True,
    ) -> MultimodalRetrievalResults:
        """执行多模态检索"""
        query = RetrievalQuery(
            query_vector=query_vector,
            query_type=query_type,
            modality=modality,
            top_k=top_k,
            threshold=threshold,
        )

        # 检查缓存
        cache_key = self._get_cache_key(query)
        if use_cache and cache_key in self._query_cache:
            return self._query_cache[cache_key]

        # 执行检索
        results = await self.cross_modal_retriever.retrieve(query)

        # 缓存结果
        if use_cache:
            self._query_cache[cache_key] = results

        return results

    def add_item(
        self,
        item_id: str,
        vector: list[float],
        modality: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """添加项目到索引"""
        self.cross_modal_retriever.indexer.add_item(
            item_id=item_id,
            vector=vector,
            modality=modality,
            metadata=metadata,
        )

    def clear_cache(self) -> None:
        """清除查询缓存"""
        self._query_cache.clear()

    @staticmethod
    def _get_cache_key(query: RetrievalQuery) -> str:
        """生成缓存键"""
        import hashlib
        key_str = f"{query.query_type}_{query.modality}_{query.top_k}_{query.threshold}"
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()


class RetrievalEvaluator:
    """检索评估器 - 评估检索质量"""

    @staticmethod
    def compute_mrr(results: list[RetrievalResult], relevant_ids: set[str]) -> float:
        """计算平均倒数排名 (Mean Reciprocal Rank)"""
        for result in results:
            if result.item_id in relevant_ids:
                return 1.0 / result.rank
        return 0.0

    @staticmethod
    def compute_ndcg(results: list[RetrievalResult], relevant_ids: set[str], k: int = 10) -> float:
        """计算归一化折扣累积增益 (Normalized Discounted Cumulative Gain)"""
        # 计算DCG
        dcg = 0.0
        for result in results[:k]:
            if result.item_id in relevant_ids:
                dcg += 1.0 / math.log2(result.rank + 1)

        # 计算IDCG
        idcg = 0.0
        for i in range(1, min(len(relevant_ids), k) + 1):
            idcg += 1.0 / math.log2(i + 1)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    @staticmethod
    def compute_precision_at_k(
        results: list[RetrievalResult],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算P@K"""
        if k == 0:
            return 0.0

        relevant_count = sum(
            1 for result in results[:k]
            if result.item_id in relevant_ids
        )

        return relevant_count / k

    @staticmethod
    def compute_recall_at_k(
        results: list[RetrievalResult],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算R@K"""
        if not relevant_ids:
            return 0.0

        relevant_count = sum(
            1 for result in results[:k]
            if result.item_id in relevant_ids
        )

        return relevant_count / len(relevant_ids)

    @staticmethod
    def compute_map(
        results: list[RetrievalResult],
        relevant_ids: set[str],
        k: int = 10,
    ) -> float:
        """计算平均精度 (Mean Average Precision)"""
        if not relevant_ids:
            return 0.0

        ap = 0.0
        relevant_count = 0

        for result in results[:k]:
            if result.item_id in relevant_ids:
                relevant_count += 1
                precision_at_i = relevant_count / result.rank
                ap += precision_at_i

        return ap / len(relevant_ids)


# 全局检索器实例
_retriever: MultimodalRetriever | None = None


def get_retriever(index_dim: int = 512) -> MultimodalRetriever:
    """获取全局检索器"""
    global _retriever
    if _retriever is None:
        _retriever = MultimodalRetriever(index_dim=index_dim)
    return _retriever
