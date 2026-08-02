"""
反馈系统集成测试配置
"""
import pytest
import asyncio
from httpx import ASGITransport, AsyncClient
from uuid import uuid4

from backend.app.main import app
from backend.app.core.feedback_analyzer import feedback_analyzer
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal
from backend.app.models.feedback import FeedbackStorePostgres


@pytest.fixture
async def client():
    """创建测试客户端。

    默认带 x-api-key: bootstrap 头：CSRF 中间件对 header-based API-key auth
    豁免(见 main.py _request_has_valid_api_key),否则所有 POST/PATCH 被
    方法级 CSRF 检查 403 挡下。实际 principal 由 dependency_overrides 注入,
    与此豁免路径相互独立。
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-api-key": "bootstrap"},
    ) as client:
        yield client
    # 清理本测试注入的依赖覆盖,避免跨测试污染
    app.dependency_overrides.pop(get_current_principal, None)


@pytest.fixture
def mock_principal():
    """创建模拟的 principal(已认证的普通用户)"""
    return Principal(
        user_id="test-user-123",
        tenant_id="test-tenant-123",
        role="user",
        authenticated=True,
    )


@pytest.fixture
def admin_principal():
    """创建模拟的管理员 principal"""
    return Principal(
        user_id="admin-user-123",
        tenant_id="test-tenant-123",
        role="admin",
        authenticated=True,
    )


class TestFeedbackAPIIntegration:
    """反馈API集成测试"""

    @pytest.mark.asyncio
    async def test_create_feedback_success(self, client, mock_principal):
        """测试成功创建反馈"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "应用程序启动时崩溃",
                "description": "在Windows 10上启动应用程序后立即崩溃",
                "severity": "critical",
                "metadata": {"os": "Windows 10", "version": "1.0.0"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "bug"
        assert data["severity"] == "critical"
        assert data["status"] == "new"
        assert "id" in data
        assert "priority_score" in data

    @pytest.mark.asyncio
    async def test_create_feedback_invalid_type(self, client, mock_principal):
        """测试创建反馈时使用无效类型"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "invalid_type",
                "title": "Test",
                "description": "Test description",
                "severity": "high",
            },
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_feedback_invalid_severity(self, client, mock_principal):
        """测试创建反馈时使用无效严重程度"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "Test",
                "description": "Test description",
                "severity": "invalid_severity",
            },
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_feedback_success(self, client, mock_principal):
        """测试成功获取反馈"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 先创建反馈
        create_response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "feature",
                "title": "新功能请求",
                "description": "请添加深色模式支持",
                "severity": "low",
            },
        )

        feedback_id = create_response.json()["id"]

        # 获取反馈
        get_response = await client.get(f"/api/v1/feedback/{feedback_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == feedback_id
        assert data["feedback_type"] == "feature"

    @pytest.mark.asyncio
    async def test_get_feedback_not_found(self, client, mock_principal):
        """测试获取不存在的反馈"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        response = await client.get(f"/api/v1/feedback/{str(uuid4())}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_feedback_success(self, client, mock_principal):
        """测试成功列出反馈"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建多个反馈
        for i in range(3):
            await client.post(
                "/api/v1/feedback/",
                json={
                    "feedback_type": "bug",
                    "title": f"Bug {i}",
                    "description": f"Bug description {i}",
                    "severity": "medium",
                },
            )

        # 列出反馈
        response = await client.get("/api/v1/feedback/")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert "skip" in data
        assert "limit" in data

    @pytest.mark.asyncio
    async def test_list_feedback_with_filters(self, client, mock_principal):
        """测试带过滤条件的反馈列表"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建不同类型的反馈
        await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "Bug Report",
                "description": "This is a bug",
                "severity": "critical",
            },
        )

        await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "feature",
                "title": "Feature Request",
                "description": "This is a feature request",
                "severity": "low",
            },
        )

        # 过滤bug
        response = await client.get("/api/v1/feedback/?feedback_type=bug")

        assert response.status_code == 200
        data = response.json()
        assert all(item["feedback_type"] == "bug" for item in data["items"])

    @pytest.mark.asyncio
    async def test_get_feedback_analysis(self, client, mock_principal):
        """测试获取反馈分析"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建反馈
        create_response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "应用程序性能缓慢",
                "description": "应用程序加载大型数据集时非常缓慢",
                "severity": "high",
            },
        )

        feedback_id = create_response.json()["id"]

        # 获取分析
        analysis_response = await client.get(f"/api/v1/feedback/{feedback_id}/analysis")

        assert analysis_response.status_code == 200
        data = analysis_response.json()
        assert data["feedback_id"] == feedback_id
        assert "sentiment_type" in data
        assert "sentiment_score" in data
        assert "category" in data
        assert "priority_score" in data
        assert "urgency_score" in data
        assert "impact_score" in data

    @pytest.mark.asyncio
    async def test_update_feedback_status(self, client, mock_principal):
        """测试更新反馈状态"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建反馈
        create_response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "Test Bug",
                "description": "Test description",
                "severity": "high",
            },
        )

        feedback_id = create_response.json()["id"]

        # 更新状态
        update_response = await client.patch(
            f"/api/v1/feedback/{feedback_id}?status=in_progress"
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_update_feedback_invalid_status(self, client, mock_principal):
        """测试使用无效状态更新反馈"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建反馈
        create_response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "Test Bug",
                "description": "Test description",
                "severity": "high",
            },
        )

        feedback_id = create_response.json()["id"]

        # 使用无效状态更新
        update_response = await client.patch(
            f"/api/v1/feedback/{feedback_id}?status=invalid_status"
        )

        assert update_response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_feedback_stats(self, client, mock_principal):
        """测试获取反馈统计"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建不同类型和严重程度的反馈
        for severity in ["low", "medium", "high", "critical"]:
            await client.post(
                "/api/v1/feedback/",
                json={
                    "feedback_type": "bug",
                    "title": f"Bug - {severity}",
                    "description": f"Bug with {severity} severity",
                    "severity": severity,
                },
            )

        # 获取统计
        response = await client.get("/api/v1/feedback/stats/summary")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_status" in data
        assert "by_severity" in data
        assert "by_type" in data
        assert "critical_count" in data

    @pytest.mark.asyncio
    async def test_permission_check_non_admin(self, client, mock_principal):
        """测试非管理员权限检查"""
        app.dependency_overrides[get_current_principal] = lambda: mock_principal

        # 创建反馈
        create_response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "Test Bug",
                "description": "Test description",
                "severity": "high",
            },
        )

        feedback_id = create_response.json()["id"]

        # 创建另一个用户
        other_principal = Principal(
            user_id="other-user-123",
            tenant_id="test-tenant-123",
            role="user",
            authenticated=True,
        )
        app.dependency_overrides[get_current_principal] = lambda: other_principal

        # 尝试获取其他用户的反馈
        response = await client.get(f"/api/v1/feedback/{feedback_id}")

        # 应该被拒绝或返回404
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_permission_check_admin(self, client, admin_principal):
        """测试管理员权限检查"""
        # 先用普通用户创建反馈
        user_principal = Principal(
            user_id="test-user-123",
            tenant_id="test-tenant-123",
            role="user",
            authenticated=True,
        )
        app.dependency_overrides[get_current_principal] = lambda: user_principal

        create_response = await client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "bug",
                "title": "Test Bug",
                "description": "Test description",
                "severity": "high",
            },
        )

        feedback_id = create_response.json()["id"]

        # 用管理员账户获取反馈
        app.dependency_overrides[get_current_principal] = lambda: admin_principal

        response = await client.get(f"/api/v1/feedback/{feedback_id}")

        # 管理员应该能访问
        assert response.status_code == 200


class TestFeedbackAnalyzerAccuracy:
    """反馈分析器准确率测试"""

    @pytest.mark.asyncio
    async def test_sentiment_analysis_accuracy(self):
        """测试情感分析准确率"""
        test_cases = [
            ("This is amazing! I love it!", "positive"),
            ("This is terrible. I hate it.", "negative"),
            ("The application works as expected.", "neutral"),
            ("这个功能太棒了！我很喜欢！", "positive"),
            ("这个bug很讨厌，应该立即修复。", "negative"),
        ]

        correct = 0
        for text, expected_sentiment in test_cases:
            sentiment_type, _ = feedback_analyzer.analyze_sentiment(text)
            if sentiment_type == expected_sentiment:
                correct += 1

        accuracy = (correct / len(test_cases)) * 100
        assert accuracy >= 80, f"Sentiment analysis accuracy {accuracy}% is below 80%"

    @pytest.mark.asyncio
    async def test_categorization_accuracy(self):
        """测试分类准确率"""
        test_cases = [
            ("The application is very slow", "performance"),
            ("The UI is confusing", "usability"),
            ("I found a security vulnerability", "security"),
            ("The app crashes on startup", "functionality"),
        ]

        correct = 0
        for text, expected_category in test_cases:
            category, _, _ = feedback_analyzer.categorize_feedback(text, "bug")
            if category == expected_category:
                correct += 1

        accuracy = (correct / len(test_cases)) * 100
        assert accuracy >= 75, f"Categorization accuracy {accuracy}% is below 75%"

    @pytest.mark.asyncio
    async def test_priority_calculation_critical(self):
        """测试关键bug的优先级计算"""
        priority_score, urgency_score, impact_score = feedback_analyzer.calculate_priority(
            severity="critical",
            sentiment_score=-0.9,
            feedback_type="bug",
            category="security",
        )

        assert priority_score > 0.8, "Critical bug priority should be > 0.8"
        assert urgency_score > 0.8, "Critical bug urgency should be > 0.8"
        assert impact_score > 0.7, "Critical bug impact should be > 0.7"

    @pytest.mark.asyncio
    async def test_priority_calculation_low(self):
        """测试低优先级改进的优先级计算"""
        priority_score, urgency_score, impact_score = feedback_analyzer.calculate_priority(
            severity="low",
            sentiment_score=0.0,
            feedback_type="improvement",
            category="documentation",
        )

        assert priority_score < 0.5, "Low priority improvement should be < 0.5"
        assert urgency_score < 0.5, "Low priority urgency should be < 0.5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
