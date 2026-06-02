"""
反馈系统单元测试
"""
from __future__ import annotations

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from backend.app.core.feedback_analyzer import feedback_analyzer
from backend.app.models.feedback import (
    FeedbackStorePostgres,
    FeedbackType,
    FeedbackSeverity,
    FeedbackStatus,
)


class TestFeedbackAnalyzer:
    """反馈分析器测试"""

    def test_sentiment_analysis_positive(self):
        """测试正面情感分析"""
        text = "This is amazing! I love this feature. It's perfect!"
        sentiment_type, sentiment_score = feedback_analyzer.analyze_sentiment(text)

        assert sentiment_type == "positive"
        assert sentiment_score > 0

    def test_sentiment_analysis_negative(self):
        """测试负面情感分析"""
        text = "This is terrible. I hate this bug. It's broken!"
        sentiment_type, sentiment_score = feedback_analyzer.analyze_sentiment(text)

        assert sentiment_type == "negative"
        assert sentiment_score < 0

    def test_sentiment_analysis_neutral(self):
        """测试中立情感分析"""
        text = "The application works as expected."
        sentiment_type, sentiment_score = feedback_analyzer.analyze_sentiment(text)

        assert sentiment_type == "neutral"
        assert abs(sentiment_score) <= 0.1

    def test_sentiment_analysis_chinese(self):
        """测试中文情感分析"""
        text = "这个功能太棒了！我很喜欢！"
        sentiment_type, sentiment_score = feedback_analyzer.analyze_sentiment(text)

        assert sentiment_type == "positive"
        assert sentiment_score > 0

    def test_categorize_feedback_performance(self):
        """测试性能相关反馈分类"""
        text = "The application is very slow and has high latency"
        category, subcategory, tags = feedback_analyzer.categorize_feedback(text, "bug")

        assert category == "performance"
        assert "slow" in tags or "latency" in tags

    def test_categorize_feedback_usability(self):
        """测试可用性相关反馈分类"""
        text = "The UI is confusing and the navigation is unclear"
        category, subcategory, tags = feedback_analyzer.categorize_feedback(text, "improvement")

        assert category == "usability"

    def test_categorize_feedback_security(self):
        """测试安全相关反馈分类"""
        text = "I found a security vulnerability in the login page"
        category, subcategory, tags = feedback_analyzer.categorize_feedback(text, "bug")

        assert category == "security"

    def test_calculate_priority_critical_bug(self):
        """测试关键bug的优先级计算"""
        priority_score, urgency_score, impact_score = feedback_analyzer.calculate_priority(
            severity="critical",
            sentiment_score=-0.8,
            feedback_type="bug",
            category="security",
        )

        assert priority_score > 0.8
        assert urgency_score > 0.7
        assert impact_score > 0.7

    def test_calculate_priority_low_improvement(self):
        """测试低优先级改进的优先级计算"""
        priority_score, urgency_score, impact_score = feedback_analyzer.calculate_priority(
            severity="low",
            sentiment_score=0.0,
            feedback_type="improvement",
            category="documentation",
        )

        assert priority_score < 0.5
        assert urgency_score < 0.5

    def test_extract_keywords(self):
        """测试关键词提取"""
        text = "The application crashes when I try to upload large files"
        keywords = feedback_analyzer.extract_keywords(text)

        assert len(keywords) > 0
        assert "application" in keywords or "crashes" in keywords or "upload" in keywords

    def test_extract_keywords_empty(self):
        """测试空文本关键词提取"""
        keywords = feedback_analyzer.extract_keywords("")

        assert keywords == []

    def test_extract_entities(self):
        """测试实体提取"""
        text = "There is an error: connection timeout. Please add support for offline mode."
        entities = feedback_analyzer.extract_entities(text)

        assert isinstance(entities, dict)
        assert "features" in entities
        assert "errors" in entities

    @pytest.mark.asyncio
    async def test_analyze_feedback_complete(self):
        """测试完整的反馈分析"""
        result = await feedback_analyzer.analyze_feedback(
            feedback_id="test-123",
            title="Application crashes on startup",
            description="The app crashes immediately after launching on Windows 10",
            feedback_type="bug",
            severity="critical",
        )

        assert result["feedback_id"] == "test-123"
        assert "sentiment_type" in result
        assert "sentiment_score" in result
        assert "category" in result
        assert "tags" in result
        assert "priority_score" in result
        assert "urgency_score" in result
        assert "impact_score" in result
        assert "keywords" in result
        assert "entities" in result

        # 验证分数范围
        assert -1.0 <= result["sentiment_score"] <= 1.0
        assert 0.0 <= result["priority_score"] <= 1.0
        assert 0.0 <= result["urgency_score"] <= 1.0
        assert 0.0 <= result["impact_score"] <= 1.0

    def test_analyze_feedback_accuracy(self):
        """测试反馈分析准确率"""
        test_cases = [
            {
                "title": "Critical security vulnerability",
                "description": "SQL injection vulnerability in login form",
                "feedback_type": "bug",
                "severity": "critical",
                "expected_category": "security",
                "expected_sentiment": "negative",
            },
            {
                "title": "Feature request: Dark mode",
                "description": "Please add dark mode support for better user experience",
                "feedback_type": "feature",
                "severity": "low",
                "expected_category": "functionality",
                "expected_sentiment": "positive",
            },
            {
                "title": "Performance issue",
                "description": "The application is very slow when loading large datasets",
                "feedback_type": "bug",
                "severity": "high",
                "expected_category": "performance",
                "expected_sentiment": "negative",
            },
        ]

        correct_count = 0
        for test_case in test_cases:
            category, _, _ = feedback_analyzer.categorize_feedback(
                f"{test_case['title']} {test_case['description']}",
                test_case["feedback_type"],
            )
            sentiment_type, _ = feedback_analyzer.analyze_sentiment(
                f"{test_case['title']} {test_case['description']}"
            )

            if category == test_case["expected_category"]:
                correct_count += 1
            if sentiment_type == test_case["expected_sentiment"]:
                correct_count += 1

        # 准确率应该 >= 85%
        accuracy = (correct_count / (len(test_cases) * 2)) * 100
        assert accuracy >= 85, f"Accuracy {accuracy}% is below 85% threshold"


class TestFeedbackStore:
    """反馈存储测试"""

    @pytest.fixture
    async def store(self):
        """创建反馈存储实例"""
        return FeedbackStorePostgres()

    @pytest.mark.asyncio
    async def test_create_feedback(self, store):
        """测试创建反馈"""
        feedback_id = str(uuid4())
        feedback = await store.create_feedback(
            feedback_id=feedback_id,
            user_id="user-123",
            tenant_id="tenant-123",
            feedback_type="bug",
            title="Test Bug",
            description="This is a test bug",
            severity="high",
        )

        assert feedback.id == feedback_id
        assert feedback.user_id == "user-123"
        assert feedback.feedback_type == "bug"
        assert feedback.status == "new"

    @pytest.mark.asyncio
    async def test_get_feedback_by_id(self, store):
        """测试根据ID获取反馈"""
        feedback_id = str(uuid4())
        await store.create_feedback(
            feedback_id=feedback_id,
            user_id="user-123",
            tenant_id="tenant-123",
            feedback_type="feature",
            title="Test Feature",
            description="This is a test feature",
            severity="low",
        )

        feedback = await store.get_feedback_by_id(feedback_id)

        assert feedback is not None
        assert feedback.id == feedback_id
        assert feedback.feedback_type == "feature"

    @pytest.mark.asyncio
    async def test_list_feedback(self, store):
        """测试列出反馈"""
        tenant_id = "tenant-123"
        user_id = "user-123"

        # 创建多个反馈
        for i in range(5):
            await store.create_feedback(
                feedback_id=str(uuid4()),
                user_id=user_id,
                tenant_id=tenant_id,
                feedback_type="bug",
                title=f"Test Bug {i}",
                description=f"This is test bug {i}",
                severity="medium",
            )

        feedbacks = await store.list_feedback(
            tenant_id=tenant_id,
            skip=0,
            limit=10,
        )

        assert len(feedbacks) >= 5

    @pytest.mark.asyncio
    async def test_update_feedback(self, store):
        """测试更新反馈"""
        feedback_id = str(uuid4())
        await store.create_feedback(
            feedback_id=feedback_id,
            user_id="user-123",
            tenant_id="tenant-123",
            feedback_type="bug",
            title="Test Bug",
            description="This is a test bug",
            severity="high",
        )

        updated_feedback = await store.update_feedback(
            feedback_id=feedback_id,
            status="in_progress",
            priority_score=0.8,
        )

        assert updated_feedback.status == "in_progress"
        assert updated_feedback.priority_score == 0.8

    @pytest.mark.asyncio
    async def test_create_analysis(self, store):
        """测试创建反馈分析"""
        feedback_id = str(uuid4())
        analysis_id = str(uuid4())

        analysis = await store.create_analysis(
            analysis_id=analysis_id,
            feedback_id=feedback_id,
            sentiment_score=0.7,
            sentiment_type="positive",
            category="performance",
            tags=["slow", "latency"],
            priority_score=0.8,
            urgency_score=0.7,
            impact_score=0.9,
        )

        assert analysis.id == analysis_id
        assert analysis.feedback_id == feedback_id
        assert analysis.sentiment_score == 0.7
        assert analysis.sentiment_type == "positive"

    @pytest.mark.asyncio
    async def test_get_analysis_by_feedback_id(self, store):
        """测试根据反馈ID获取分析"""
        feedback_id = str(uuid4())
        analysis_id = str(uuid4())

        await store.create_analysis(
            analysis_id=analysis_id,
            feedback_id=feedback_id,
            sentiment_score=-0.5,
            sentiment_type="negative",
            category="usability",
            tags=["confusing", "unclear"],
            priority_score=0.6,
            urgency_score=0.5,
            impact_score=0.7,
        )

        analysis = await store.get_analysis_by_feedback_id(feedback_id)

        assert analysis is not None
        assert analysis.feedback_id == feedback_id
        assert analysis.sentiment_type == "negative"

    @pytest.mark.asyncio
    async def test_count_feedback(self, store):
        """测试统计反馈"""
        tenant_id = "tenant-123"

        # 创建不同状态的反馈
        for i in range(3):
            await store.create_feedback(
                feedback_id=str(uuid4()),
                user_id="user-123",
                tenant_id=tenant_id,
                feedback_type="bug",
                title=f"Bug {i}",
                description=f"Bug description {i}",
                severity="high",
            )

        count = await store.count_feedback(tenant_id=tenant_id)

        assert count >= 3

    @pytest.mark.asyncio
    async def test_list_feedback_with_filters(self, store):
        """测试带过滤条件的反馈列表"""
        tenant_id = "tenant-123"

        # 创建不同类型的反馈
        await store.create_feedback(
            feedback_id=str(uuid4()),
            user_id="user-123",
            tenant_id=tenant_id,
            feedback_type="bug",
            title="Bug Report",
            description="This is a bug",
            severity="critical",
        )

        await store.create_feedback(
            feedback_id=str(uuid4()),
            user_id="user-123",
            tenant_id=tenant_id,
            feedback_type="feature",
            title="Feature Request",
            description="This is a feature request",
            severity="low",
        )

        # 过滤bug
        bugs = await store.list_feedback(
            tenant_id=tenant_id,
            feedback_type="bug",
        )

        assert all(f.feedback_type == "bug" for f in bugs)

        # 过滤critical
        critical = await store.list_feedback(
            tenant_id=tenant_id,
            severity="critical",
        )

        assert all(f.severity == "critical" for f in critical)


class TestFeedbackIntegration:
    """反馈系统集成测试"""

    @pytest.mark.asyncio
    async def test_end_to_end_feedback_workflow(self):
        """测试端到端反馈工作流"""
        store = FeedbackStorePostgres()
        feedback_id = str(uuid4())

        # 1. 创建反馈
        feedback = await store.create_feedback(
            feedback_id=feedback_id,
            user_id="user-123",
            tenant_id="tenant-123",
            feedback_type="bug",
            title="Critical Bug",
            description="The application crashes on startup",
            severity="critical",
        )

        assert feedback.status == "new"

        # 2. 分析反馈
        analysis_result = await feedback_analyzer.analyze_feedback(
            feedback_id=feedback_id,
            title=feedback.title,
            description=feedback.description,
            feedback_type=feedback.feedback_type,
            severity=feedback.severity,
        )

        assert analysis_result["priority_score"] > 0.7

        # 3. 更新反馈
        updated_feedback = await store.update_feedback(
            feedback_id=feedback_id,
            status="acknowledged",
            sentiment=analysis_result["sentiment_type"],
            sentiment_score=analysis_result["sentiment_score"],
            priority_score=analysis_result["priority_score"],
        )

        assert updated_feedback.status == "acknowledged"
        assert updated_feedback.priority_score > 0.7

        # 4. 创建分析记录
        analysis_id = str(uuid4())
        analysis = await store.create_analysis(
            analysis_id=analysis_id,
            feedback_id=feedback_id,
            sentiment_score=analysis_result["sentiment_score"],
            sentiment_type=analysis_result["sentiment_type"],
            category=analysis_result["category"],
            tags=analysis_result["tags"],
            priority_score=analysis_result["priority_score"],
            urgency_score=analysis_result["urgency_score"],
            impact_score=analysis_result["impact_score"],
        )

        assert analysis.feedback_id == feedback_id

        # 5. 获取反馈和分析
        retrieved_feedback = await store.get_feedback_by_id(feedback_id)
        retrieved_analysis = await store.get_analysis_by_feedback_id(feedback_id)

        assert retrieved_feedback.id == feedback_id
        assert retrieved_analysis.feedback_id == feedback_id
