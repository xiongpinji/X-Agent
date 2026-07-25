"""
向量检索优化模块 - 混合检索和重排序。

实现功能:
- 混合检索 (向量 + 关键词)
- 查询扩展
- 重排序 (reranking)
- 批量检索优化
- 缓存层
- 性能监控
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果。"""
    memory_id: str
    content: str
    score: float
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0
    rank: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalStats:
    """检索统计信息。"""
    query_count: int = 0
    total_latency: float = 0.0
    avg_latency: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    results_returned: int = 0
    avg_results_per_query: float = 0.0


class RetrieverOptimizer:
    """
    向量检索优化系统。

    实现混合检索、查询扩展、重排序等高级功能。
    """

    def __init__(
        self,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        cache_size: int = 1000,
        enable_query_expansion: bool = True,
        enable_reranking: bool = True,
    ):
        """
        初始化检索优化器。

        Args:
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            cache_size: 缓存大小
            enable_query_expansion: 是否启用查询扩展
            enable_reranking: 是否启用重排序
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.cache_size = cache_size
        self.enable_query_expansion = enable_query_expansion
        self.enable_reranking = enable_reranking

        # 缓存
        self._cache: dict[str, list[RetrievalResult]] = {}
        self._cache_order: list[str] = []

        # 统计信息
        self.stats = RetrievalStats()

    async def hybrid_retrieve(
        self,
        query: str,
        memories: list[dict],
        embeddings: np.ndarray | None = None,
        top_k: int = 10,
        use_cache: bool = True,
    ) -> list[RetrievalResult]:
        """
        执行混合检索。

        Args:
            query: 查询文本
            memories: 记忆列表
            embeddings: 记忆的嵌入向量
            top_k: 返回结果数量
            use_cache: 是否使用缓存

        Returns:
            检索结果列表
        """
        # 检查缓存
        cache_key = self._compute_cache_key(query)
        if use_cache and cache_key in self._cache:
            self.stats.cache_hits += 1
            return self._cache[cache_key][:top_k]

        self.stats.cache_misses += 1
        start_time = datetime.now(UTC)

        # 查询扩展
        queries = [query]
        if self.enable_query_expansion:
            queries.extend(self._expand_query(query))

        # 向量检索
        vector_results = await self._vector_retrieve(
            queries, memories, embeddings, top_k * 2
        )

        # 关键词检索
        keyword_results = self._keyword_retrieve(
            queries, memories, top_k * 2
        )

        # 合并结果
        combined_results = self._combine_results(
            vector_results, keyword_results, top_k
        )

        # 重排序
        if self.enable_reranking:
            combined_results = await self._rerank_results(
                query, combined_results
            )

        # 排序并返回
        combined_results.sort(key=lambda r: r.score, reverse=True)
        final_results = combined_results[:top_k]

        # 添加排名
        for i, result in enumerate(final_results):
            result.rank = i + 1

        # 更新统计信息
        latency = (datetime.now(UTC) - start_time).total_seconds()
        self.stats.query_count += 1
        self.stats.total_latency += latency
        self.stats.avg_latency = self.stats.total_latency / self.stats.query_count
        self.stats.results_returned += len(final_results)
        self.stats.avg_results_per_query = (
            self.stats.results_returned / self.stats.query_count
        )

        # 缓存结果
        if use_cache:
            self._add_to_cache(cache_key, final_results)

        logger.debug(
            f"Hybrid retrieval for '{query}': {len(final_results)} results "
            f"in {latency:.3f}s"
        )

        return final_results

    async def _vector_retrieve(
        self,
        queries: list[str],
        memories: list[dict],
        embeddings: np.ndarray | None,
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        执行向量检索。

        Args:
            queries: 查询列表
            memories: 记忆列表
            embeddings: 嵌入向量
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        if embeddings is None or len(embeddings) == 0:
            return []

        results = []
        seen_ids = set()

        embeddings = np.asarray(embeddings)
        target_dim = embeddings.shape[1] if embeddings.ndim == 2 else len(embeddings[0])
        if target_dim <= 0:
            return []

        for query in queries:
            # 获取查询嵌入(维度与记忆嵌入对齐,避免 cosine_similarity 维度不匹配)
            query_embedding = self._get_query_embedding(query, dim=target_dim)

            # 计算相似度
            similarities = cosine_similarity(
                [query_embedding], embeddings
            )[0]

            # 获取top-k
            top_indices = np.argsort(similarities)[::-1][:top_k]

            for idx in top_indices:
                mem_id = memories[idx].get("id", "")
                if mem_id not in seen_ids:
                    results.append(
                        RetrievalResult(
                            memory_id=mem_id,
                            content=memories[idx].get("content", ""),
                            score=float(similarities[idx]),
                            vector_score=float(similarities[idx]),
                            metadata=memories[idx].get("metadata", {}),
                        )
                    )
                    seen_ids.add(mem_id)

        return results

    def _keyword_retrieve(
        self,
        queries: list[str],
        memories: list[dict],
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        执行关键词检索。

        Args:
            queries: 查询列表
            memories: 记忆列表
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        results = []
        scores = {}

        for query in queries:
            query_terms = set(query.lower().split())

            for _i, mem in enumerate(memories):
                mem_id = mem.get("id", "")
                content = mem.get("content", "").lower()
                content_terms = set(content.split())

                # 计算Jaccard相似度
                intersection = len(query_terms & content_terms)
                union = len(query_terms | content_terms)
                similarity = intersection / union if union > 0 else 0.0

                if mem_id not in scores:
                    scores[mem_id] = {
                        "score": 0.0,
                        "content": mem.get("content", ""),
                        "metadata": mem.get("metadata", {}),
                    }

                scores[mem_id]["score"] = max(
                    scores[mem_id]["score"], similarity
                )

        # 转换为结果列表
        for mem_id, data in scores.items():
            if data["score"] > 0:
                results.append(
                    RetrievalResult(
                        memory_id=mem_id,
                        content=data["content"],
                        score=data["score"],
                        keyword_score=data["score"],
                        metadata=data["metadata"],
                    )
                )

        # 排序并返回top-k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _combine_results(
        self,
        vector_results: list[RetrievalResult],
        keyword_results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        合并向量和关键词检索结果。

        Args:
            vector_results: 向量检索结果
            keyword_results: 关键词检索结果
            top_k: 返回结果数量

        Returns:
            合并后的结果列表
        """
        combined = {}

        # 添加向量结果
        for result in vector_results:
            combined[result.memory_id] = result
            result.score = (
                self.vector_weight * result.vector_score
                + self.keyword_weight * result.keyword_score
            )

        # 合并关键词结果
        for result in keyword_results:
            if result.memory_id in combined:
                combined[result.memory_id].keyword_score = result.keyword_score
                combined[result.memory_id].score = (
                    self.vector_weight * combined[result.memory_id].vector_score
                    + self.keyword_weight * result.keyword_score
                )
            else:
                result.score = (
                    self.vector_weight * 0.0
                    + self.keyword_weight * result.keyword_score
                )
                combined[result.memory_id] = result

        # 排序并返回
        results = list(combined.values())
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k * 2]

    async def _rerank_results(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        重排序检索结果。

        使用更复杂的相关性模型。

        Args:
            query: 查询文本
            results: 检索结果

        Returns:
            重排序后的结果
        """
        for result in results:
            # 计算查询和内容的相关性
            relevance = self._compute_relevance(query, result.content)
            result.rerank_score = relevance
            result.score = (
                0.5 * result.score + 0.5 * relevance
            )

        return results

    def _compute_relevance(self, query: str, content: str) -> float:
        """
        计算查询和内容的相关性。

        Args:
            query: 查询文本
            content: 内容文本

        Returns:
            相关性分数 (0-1)
        """
        query_terms = set(query.lower().split())
        content_terms = set(content.lower().split())

        # 计算Jaccard相似度
        intersection = len(query_terms & content_terms)
        union = len(query_terms | content_terms)
        jaccard = intersection / union if union > 0 else 0.0

        # 计算BM25-like分数
        term_frequency = sum(
            1 for term in query_terms if term in content_terms
        )
        bm25_score = term_frequency / len(query_terms) if query_terms else 0.0

        # 组合分数
        relevance = 0.4 * jaccard + 0.6 * bm25_score
        return min(1.0, max(0.0, relevance))

    def _expand_query(self, query: str) -> list[str]:
        """
        扩展查询。

        Args:
            query: 原始查询

        Returns:
            扩展的查询列表
        """
        expanded = []

        # 简单的同义词扩展
        synonyms = {
            "memory": ["memories", "recall", "remember"],
            "important": ["critical", "significant", "key"],
            "find": ["search", "locate", "discover"],
        }

        for term, syns in synonyms.items():
            if term in query.lower():
                for syn in syns:
                    expanded.append(query.replace(term, syn))

        return expanded

    def _get_query_embedding(self, query: str, dim: int | None = None) -> np.ndarray:
        """
        获取查询的嵌入向量。

        使用基于查询哈希的确定性方法生成向量。当提供 ``dim`` 时,
        生成与记忆嵌入同维度的向量,避免 cosine_similarity 因维度
        不一致而报错;同一查询始终生成相同向量(便于缓存与复现)。

        Args:
            query: 查询文本
            dim: 目标向量维度。None 时回退到 16 字节哈希派生的 4 维向量。

        Returns:
            嵌入向量
        """
        if dim is None:
            hash_val = hashlib.md5(query.encode()).digest()
            embedding = np.frombuffer(hash_val, dtype=np.float32).copy()
        else:
            # 用查询哈希做确定性随机种子,生成目标维度向量
            seed = int.from_bytes(
                hashlib.md5(query.encode()).digest()[:8], "little", signed=False
            )
            rng = np.random.default_rng(seed)
            embedding = rng.standard_normal(int(dim)).astype(np.float32)
        # 标准化
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    def _compute_cache_key(self, query: str) -> str:
        """计算缓存键。"""
        return hashlib.md5(query.encode()).hexdigest()

    def _add_to_cache(
        self,
        key: str,
        results: list[RetrievalResult],
    ) -> None:
        """添加到缓存。"""
        if len(self._cache) >= self.cache_size:
            # 移除最旧的缓存项
            oldest_key = self._cache_order.pop(0)
            del self._cache[oldest_key]

        self._cache[key] = results
        self._cache_order.append(key)

    def get_stats(self) -> RetrievalStats:
        """获取检索统计信息。"""
        return self.stats

    def clear_cache(self) -> None:
        """清空缓存。"""
        self._cache.clear()
        self._cache_order.clear()

    def reset_stats(self) -> None:
        """重置统计信息。"""
        self.stats = RetrievalStats()
