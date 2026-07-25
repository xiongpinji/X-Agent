"""智能上下文检索模块。

提供基于相关性、时间、重要性和混合策略的上下文检索功能。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.core.context.session_recovery import Message

logger = logging.getLogger(__name__)


@dataclass
class ContextItem:
    """上下文项目，包含内容和元数据。"""

    content: str
    timestamp: datetime
    priority: float
    relevance_score: float = 0.0
    message_id: str = ""
    role: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "relevance_score": self.relevance_score,
            "message_id": self.message_id,
            "role": self.role,
            "metadata": self.metadata,
        }


@dataclass
class RetrievalWeights:
    """检索权重配置。"""

    relevance: float = 0.5
    recency: float = 0.3
    importance: float = 0.2

    def __post_init__(self) -> None:
        """验证权重总和为1.0。"""
        total = self.relevance + self.recency + self.importance
        if not math.isclose(total, 1.0, abs_tol=0.01):
            logger.warning(
                f"检索权重总和为 {total}，建议总和为 1.0。"
                f"将自动归一化。"
            )
            if total > 0:
                self.relevance /= total
                self.recency /= total
                self.importance /= total


class ContextRetriever:
    """智能上下文检索器。

    支持多种检索策略：
    - 基于相关性的检索：使用 TF-IDF 和余弦相似度
    - 基于时间的检索：按时间戳范围过滤
    - 基于重要性的检索：按优先级排序
    - 混合检索：组合多种策略
    """

    def __init__(self, messages: list[Message] | None = None) -> None:
        """初始化检索器。

        Args:
            messages: 消息列表（可选）
        """
        self.messages = messages or []
        self._vocabulary: dict[str, int] = {}
        self._idf_cache: dict[str, float] = {}
        self._build_vocabulary()

    def _build_vocabulary(self) -> None:
        """构建词汇表和 IDF 缓存。"""
        self._vocabulary.clear()
        self._idf_cache.clear()

        word_doc_count: dict[str, int] = {}
        total_docs = len(self.messages)

        if total_docs == 0:
            return

        for message in self.messages:
            words = self._tokenize(message.content)
            seen_words = set(words)

            for word in seen_words:
                word_doc_count[word] = word_doc_count.get(word, 0) + 1

        for word, doc_count in word_doc_count.items():
            if word not in self._vocabulary:
                self._vocabulary[word] = len(self._vocabulary)

            self._idf_cache[word] = math.log(total_docs / (1 + doc_count))

    def _tokenize(self, text: str) -> list[str]:
        """简单的分词器。

        Args:
            text: 输入文本

        Returns:
            词列表
        """
        import re

        text = text.lower()
        text = re.sub(r"[^\w\s一-鿿]", " ", text)
        words = text.split()
        return [w for w in words if len(w) > 1]

    def _compute_tf(self, text: str) -> dict[str, float]:
        """计算词频 (TF)。

        Args:
            text: 输入文本

        Returns:
            词频字典
        """
        words = self._tokenize(text)
        tf: dict[str, float] = {}
        total_words = len(words)

        if total_words == 0:
            return tf

        for word in words:
            tf[word] = tf.get(word, 0) + 1

        for word in tf:
            tf[word] /= total_words

        return tf

    def _compute_tfidf_vector(self, text: str) -> dict[str, float]:
        """计算 TF-IDF 向量。

        Args:
            text: 输入文本

        Returns:
            TF-IDF 向量
        """
        tf = self._compute_tf(text)
        tfidf: dict[str, float] = {}

        for word, tf_value in tf.items():
            idf_value = self._idf_cache.get(word, 0.0)
            tfidf[word] = tf_value * idf_value

        return tfidf

    def _cosine_similarity(
        self, vector1: dict[str, float], vector2: dict[str, float]
    ) -> float:
        """计算两个向量的余弦相似度。

        Args:
            vector1: 第一个向量
            vector2: 第二个向量

        Returns:
            相似度分数 (0.0-1.0)
        """
        dot_product = 0.0
        for word in vector1:
            if word in vector2:
                dot_product += vector1[word] * vector2[word]

        magnitude1 = math.sqrt(sum(v**2 for v in vector1.values()))
        magnitude2 = math.sqrt(sum(v**2 for v in vector2.values()))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def retrieve_by_relevance(
        self, query: str, top_k: int = 10
    ) -> list[ContextItem]:
        """基于相关性检索。

        使用 TF-IDF 和余弦相似度计算查询与消息的相关性。

        Args:
            query: 查询文本
            top_k: 返回的最大结果数

        Returns:
            按相关性排序的上下文项目列表
        """
        if not self.messages:
            return []

        query_vector = self._compute_tfidf_vector(query)

        if not query_vector:
            logger.warning("查询向量为空，无法进行相关性检索")
            return []

        results: list[tuple[ContextItem, float]] = []

        for message in self.messages:
            message_vector = self._compute_tfidf_vector(message.content)
            similarity = self._cosine_similarity(query_vector, message_vector)

            if similarity > 0:
                item = ContextItem(
                    content=message.content,
                    timestamp=message.timestamp,
                    priority=message.importance,
                    relevance_score=similarity,
                    message_id=message.id,
                    role=message.role,
                    metadata=message.metadata,
                )
                results.append((item, similarity))

        results.sort(key=lambda x: x[1], reverse=True)

        return [item for item, _ in results[:top_k]]

    def retrieve_by_time(
        self,
        start: datetime,
        end: datetime,
        sort_order: str = "desc",
    ) -> list[ContextItem]:
        """基于时间范围检索。

        Args:
            start: 开始时间
            end: 结束时间
            sort_order: 排序顺序 ('asc' 或 'desc')

        Returns:
            在时间范围内的上下文项目列表
        """
        if not self.messages:
            return []

        results: list[ContextItem] = []

        for message in self.messages:
            if start <= message.timestamp <= end:
                item = ContextItem(
                    content=message.content,
                    timestamp=message.timestamp,
                    priority=message.importance,
                    message_id=message.id,
                    role=message.role,
                    metadata=message.metadata,
                )
                results.append(item)

        reverse = sort_order.lower() == "desc"
        results.sort(key=lambda x: x.timestamp, reverse=reverse)

        return results

    def retrieve_by_importance(
        self, min_priority: float = 0.5, top_k: int | None = None
    ) -> list[ContextItem]:
        """基于重要性检索。

        Args:
            min_priority: 最小优先级阈值 (0.0-1.0)
            top_k: 返回的最大结果数（None 表示返回所有）

        Returns:
            按优先级排序的上下文项目列表
        """
        if not self.messages:
            return []

        min_priority = max(0.0, min(1.0, min_priority))

        results: list[ContextItem] = []

        for message in self.messages:
            if message.importance >= min_priority:
                item = ContextItem(
                    content=message.content,
                    timestamp=message.timestamp,
                    priority=message.importance,
                    message_id=message.id,
                    role=message.role,
                    metadata=message.metadata,
                )
                results.append(item)

        results.sort(key=lambda x: x.priority, reverse=True)

        if top_k:
            results = results[:top_k]

        return results

    def retrieve_hybrid(
        self,
        query: str,
        weights: RetrievalWeights | None = None,
        top_k: int = 10,
        time_window_hours: int | None = None,
        min_priority: float = 0.0,
    ) -> list[ContextItem]:
        """混合检索策略。

        组合相关性、时间和重要性三种策略，使用加权评分。

        Args:
            query: 查询文本
            weights: 检索权重配置
            top_k: 返回的最大结果数
            time_window_hours: 时间窗口（小时），None 表示不限制
            min_priority: 最小优先级阈值

        Returns:
            按混合分数排序的上下文项目列表
        """
        if not self.messages:
            return []

        if weights is None:
            weights = RetrievalWeights()

        now = datetime.now(UTC)
        if time_window_hours:
            time_start = now - timedelta(hours=time_window_hours)
        else:
            time_start = min(msg.timestamp for msg in self.messages)

        query_vector = self._compute_tfidf_vector(query)

        results: list[tuple[ContextItem, float]] = []

        for message in self.messages:
            if not (time_start <= message.timestamp <= now):
                continue

            if message.importance < min_priority:
                continue

            message_vector = self._compute_tfidf_vector(message.content)
            relevance_score = self._cosine_similarity(query_vector, message_vector)

            time_diff = (now - message.timestamp).total_seconds()
            max_time_diff = (now - time_start).total_seconds()
            recency_score = 1.0 - time_diff / max_time_diff if max_time_diff > 0 else 1.0

            importance_score = message.importance

            hybrid_score = (
                weights.relevance * relevance_score
                + weights.recency * recency_score
                + weights.importance * importance_score
            )

            if hybrid_score > 0:
                item = ContextItem(
                    content=message.content,
                    timestamp=message.timestamp,
                    priority=message.importance,
                    relevance_score=hybrid_score,
                    message_id=message.id,
                    role=message.role,
                    metadata=message.metadata,
                )
                results.append((item, hybrid_score))

        results.sort(key=lambda x: x[1], reverse=True)

        return [item for item, _ in results[:top_k]]

    def update_messages(self, messages: list[Message]) -> None:
        """更新消息列表并重建索引。

        Args:
            messages: 新的消息列表
        """
        self.messages = messages
        self._build_vocabulary()
        logger.debug(f"已更新 {len(messages)} 条消息的检索索引")

    def add_message(self, message: Message) -> None:
        """添加单条消息。

        Args:
            message: 要添加的消息
        """
        self.messages.append(message)
        words = self._tokenize(message.content)
        for word in set(words):
            if word not in self._vocabulary:
                self._vocabulary[word] = len(self._vocabulary)
                word_doc_count = sum(
                    1
                    for msg in self.messages
                    if word in self._tokenize(msg.content)
                )
                self._idf_cache[word] = math.log(
                    len(self.messages) / (1 + word_doc_count)
                )

    def clear(self) -> None:
        """清空所有数据。"""
        self.messages.clear()
        self._vocabulary.clear()
        self._idf_cache.clear()
        logger.debug("已清空检索器数据")
