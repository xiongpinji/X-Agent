"""Tests for context retrieval module."""

import pytest
from datetime import datetime, timedelta, timezone
import math

from backend.app.core.context.retrieval import (
    ContextRetriever,
    ContextItem,
    RetrievalWeights,
)
from backend.app.core.context.session_recovery import Message


class TestContextRetriever:
    """ContextRetriever 类的测试套件。"""

    @pytest.fixture
    def sample_messages(self):
        """创建示例消息列表。"""
        now = datetime.now(timezone.utc)
        return [
            Message(
                id="msg1",
                role="user",
                content="用户询问了系统的功能",
                timestamp=now - timedelta(hours=3),
                importance=0.8,
            ),
            Message(
                id="msg2",
                role="assistant",
                content="系统返回了详细的功能说明",
                timestamp=now - timedelta(hours=2),
                importance=0.7,
            ),
            Message(
                id="msg3",
                role="user",
                content="用户提出了一个错误报告",
                timestamp=now - timedelta(hours=1),
                importance=0.9,
            ),
            Message(
                id="msg4",
                role="assistant",
                content="系统分析了错误并提供了解决方案",
                timestamp=now - timedelta(minutes=30),
                importance=0.85,
            ),
            Message(
                id="msg5",
                role="user",
                content="用户确认了解决方案有效",
                timestamp=now,
                importance=0.6,
            ),
        ]

    @pytest.fixture
    def retriever(self, sample_messages):
        """创建检索器实例。"""
        return ContextRetriever(messages=sample_messages)

    def test_retrieve_by_relevance(self, retriever):
        """测试基于相关性的检索。

        验证能够根据查询文本的相关性检索消息，
        并按相关性分数排序。
        """
        query = "系统功能"
        results = retriever.retrieve_by_relevance(query, top_k=3)

        assert isinstance(results, list)
        assert len(results) <= 3
        assert all(isinstance(item, ContextItem) for item in results)

        # 验证结果按相关性分数排序
        for i in range(len(results) - 1):
            assert results[i].relevance_score >= results[i + 1].relevance_score

    def test_retrieve_by_relevance_empty_query(self, retriever):
        """测试空查询的相关性检索。

        验证空查询返回空结果。
        """
        results = retriever.retrieve_by_relevance("", top_k=10)
        assert results == []

    def test_retrieve_by_time(self, sample_messages):
        """测试基于时间范围的检索。

        验证能够根据时间范围检索消息。
        """
        retriever = ContextRetriever(messages=sample_messages)
        now = datetime.now(timezone.utc)

        # 检索最近 2 小时的消息
        start = now - timedelta(hours=2)
        end = now
        results = retriever.retrieve_by_time(start, end)

        assert isinstance(results, list)
        assert len(results) > 0

        # 验证所有结果都在时间范围内
        for item in results:
            assert start <= item.timestamp <= end

    def test_retrieve_by_time_sort_order(self, sample_messages):
        """测试时间检索的排序顺序。

        验证能够按升序或降序排序时间范围内的消息。
        """
        retriever = ContextRetriever(messages=sample_messages)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=5)
        end = now

        # 降序排列
        results_desc = retriever.retrieve_by_time(start, end, sort_order="desc")
        for i in range(len(results_desc) - 1):
            assert results_desc[i].timestamp >= results_desc[i + 1].timestamp

        # 升序排列
        results_asc = retriever.retrieve_by_time(start, end, sort_order="asc")
        for i in range(len(results_asc) - 1):
            assert results_asc[i].timestamp <= results_asc[i + 1].timestamp

    def test_retrieve_by_importance(self, retriever):
        """测试基于重要性的检索。

        验证能够根据优先级阈值检索消息，
        并按重要性排序。
        """
        results = retriever.retrieve_by_importance(min_priority=0.7, top_k=5)

        assert isinstance(results, list)
        assert len(results) > 0

        # 验证所有结果的优先级都不低于阈值
        for item in results:
            assert item.priority >= 0.7

        # 验证结果按优先级排序
        for i in range(len(results) - 1):
            assert results[i].priority >= results[i + 1].priority

    def test_retrieve_by_importance_with_top_k(self, retriever):
        """测试重要性检索的 top_k 限制。

        验证 top_k 参数能够正确限制返回结果数量。
        """
        results = retriever.retrieve_by_importance(min_priority=0.5, top_k=2)
        assert len(results) <= 2

    def test_retrieve_by_importance_no_limit(self, retriever):
        """测试重要性检索不限制数量。

        验证当 top_k 为 None 时返回所有符合条件的结果。
        """
        results = retriever.retrieve_by_importance(min_priority=0.5, top_k=None)
        assert len(results) > 0

    def test_retrieve_hybrid(self, retriever):
        """测试混合检索策略。

        验证混合检索能够组合相关性、时间和重要性三种策略。
        """
        query = "系统错误"
        results = retriever.retrieve_hybrid(query, top_k=5)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(item, ContextItem) for item in results)

        # 验证结果按混合分数排序
        for i in range(len(results) - 1):
            assert results[i].relevance_score >= results[i + 1].relevance_score

    def test_retrieve_hybrid_with_time_window(self, retriever, sample_messages):
        """测试混合检索的时间窗口。

        验证时间窗口参数能够正确过滤消息。
        """
        query = "系统"
        results = retriever.retrieve_hybrid(
            query,
            top_k=10,
            time_window_hours=1,
        )

        assert isinstance(results, list)

        # 验证所有结果都在时间窗口内
        latest_message_time = max(message.timestamp for message in sample_messages)
        time_start = latest_message_time - timedelta(hours=1)
        for item in results:
            assert item.timestamp >= time_start

    def test_retrieve_hybrid_with_min_priority(self, retriever):
        """测试混合检索的最小优先级。

        验证最小优先级参数能够正确过滤消息。
        """
        query = "系统"
        results = retriever.retrieve_hybrid(
            query,
            top_k=10,
            min_priority=0.7,
        )

        # 验证所有结果的优先级都不低于阈值
        for item in results:
            assert item.priority >= 0.7

    def test_retrieval_weights_normalization(self):
        """测试检索权重的自动归一化。

        验证权重总和不为 1.0 时能够自动归一化。
        """
        # 创建权重总和不为 1.0 的配置
        weights = RetrievalWeights(relevance=0.6, recency=0.3, importance=0.2)

        # 验证权重已被归一化
        total = weights.relevance + weights.recency + weights.importance
        assert math.isclose(total, 1.0, abs_tol=0.01)

    def test_retrieval_weights_valid(self):
        """测试有效的检索权重。

        验证权重总和为 1.0 时不会被修改。
        """
        weights = RetrievalWeights(relevance=0.5, recency=0.3, importance=0.2)
        total = weights.relevance + weights.recency + weights.importance
        assert math.isclose(total, 1.0, abs_tol=0.01)

    def test_update_messages(self, sample_messages):
        """测试消息列表更新。

        验证能够更新消息列表并重建索引。
        """
        retriever = ContextRetriever()
        assert len(retriever.messages) == 0

        retriever.update_messages(sample_messages)
        assert len(retriever.messages) == len(sample_messages)

        # 验证索引已重建
        assert len(retriever._vocabulary) > 0

    def test_add_message(self, sample_messages):
        """测试单条消息添加。

        验证能够添加单条消息并更新索引。
        """
        retriever = ContextRetriever(messages=sample_messages[:2])
        initial_count = len(retriever.messages)

        new_message = Message(
            id="msg_new",
            role="user",
            content="新的消息内容",
            importance=0.8,
        )
        retriever.add_message(new_message)

        assert len(retriever.messages) == initial_count + 1
        assert retriever.messages[-1].id == "msg_new"

    def test_empty_retriever(self):
        """测试边界情况：空检索器。

        验证空检索器能够正确处理各种检索操作。
        """
        retriever = ContextRetriever()

        # 相关性检索
        results = retriever.retrieve_by_relevance("查询")
        assert results == []

        # 时间检索
        now = datetime.now(timezone.utc)
        results = retriever.retrieve_by_time(
            now - timedelta(hours=1),
            now,
        )
        assert results == []

        # 重要性检索
        results = retriever.retrieve_by_importance(min_priority=0.5)
        assert results == []

        # 混合检索
        results = retriever.retrieve_hybrid("查询")
        assert results == []

    def test_context_item_to_dict(self, retriever):
        """测试 ContextItem 的字典转换。

        验证 ContextItem 能够正确转换为字典格式。
        """
        results = retriever.retrieve_by_relevance("系统", top_k=1)
        if results:
            item = results[0]
            item_dict = item.to_dict()

            assert isinstance(item_dict, dict)
            assert "content" in item_dict
            assert "timestamp" in item_dict
            assert "priority" in item_dict
            assert "relevance_score" in item_dict
            assert "message_id" in item_dict
            assert "role" in item_dict
            assert "metadata" in item_dict

    def test_retrieve_by_relevance_top_k_limit(self, retriever):
        """测试相关性检索的 top_k 限制。

        验证 top_k 参数能够正确限制返回结果数量。
        """
        results_1 = retriever.retrieve_by_relevance("系统", top_k=1)
        results_3 = retriever.retrieve_by_relevance("系统", top_k=3)

        assert len(results_1) <= 1
        assert len(results_3) <= 3
        assert len(results_1) <= len(results_3)

    def test_tokenize_chinese_text(self, retriever):
        """测试中文文本分词。

        验证分词器能够正确处理中文文本。
        """
        text = "这是一个测试文本"
        tokens = retriever._tokenize(text)

        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(token, str) for token in tokens)

    def test_tokenize_english_text(self, retriever):
        """测试英文文本分词。

        验证分词器能够正确处理英文文本。
        """
        text = "This is a test text"
        tokens = retriever._tokenize(text)

        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_compute_tf(self, retriever):
        """测试词频计算。

        验证 TF 计算的正确性。
        """
        text = "系统 系统 错误 错误 错误"
        tf = retriever._compute_tf(text)

        assert isinstance(tf, dict)
        assert len(tf) > 0

        # 验证词频总和为 1.0
        total_tf = sum(tf.values())
        assert math.isclose(total_tf, 1.0, abs_tol=0.01)

    def test_cosine_similarity(self, retriever):
        """测试余弦相似度计算。

        验证余弦相似度计算的正确性。
        """
        vector1 = {"word1": 0.5, "word2": 0.5}
        vector2 = {"word1": 0.5, "word2": 0.5}

        similarity = retriever._cosine_similarity(vector1, vector2)

        # 相同向量的相似度应该是 1.0
        assert math.isclose(similarity, 1.0, abs_tol=0.01)

    def test_cosine_similarity_orthogonal(self, retriever):
        """测试正交向量的余弦相似度。

        验证正交向量的相似度为 0。
        """
        vector1 = {"word1": 1.0}
        vector2 = {"word2": 1.0}

        similarity = retriever._cosine_similarity(vector1, vector2)

        # 正交向量的相似度应该是 0.0
        assert math.isclose(similarity, 0.0, abs_tol=0.01)

    def test_retrieve_hybrid_empty_query(self, retriever):
        """测试混合检索的空查询。

        混合检索 = relevance + recency + importance 加权。空查询使
        relevance 分量为 0，但 recency/importance 仍是有效信号，因此
        混合检索会优雅降级为按时间/重要性排序，而非返回空（这与纯
        relevance 检索 retrieve_by_relevance 的空查询返回 [] 不同——
        那是有意的设计区分）。
        """
        results = retriever.retrieve_hybrid("", top_k=10)
        # 有消息时空查询应返回按 recency/importance 排序的结果，不是空
        assert len(results) > 0
        # relevance 分量为 0，但 hybrid 分数由 recency/importance 贡献
        for item in results:
            assert item.relevance_score >= 0.0

    def test_clear_retriever(self, sample_messages):
        """测试清空检索器。

        验证能够清空所有数据。
        """
        retriever = ContextRetriever(messages=sample_messages)
        assert len(retriever.messages) > 0

        retriever.clear()

        assert len(retriever.messages) == 0
        assert len(retriever._vocabulary) == 0
        assert len(retriever._idf_cache) == 0
