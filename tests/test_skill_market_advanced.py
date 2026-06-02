"""技能市场高级功能测试套件"""

import pytest
from datetime import datetime, UTC
from backend.app.core.skill_version_manager import (
    get_skill_version_manager, VersionCompatibility
)
from backend.app.core.skill_review_system import (
    get_skill_review_system, ReviewStatus, ReportReason
)
from backend.app.core.skill_search_engine import get_skill_search_engine
from backend.app.core.skill_dependency_manager import (
    get_skill_dependency_manager, DependencyType, ConflictType
)
from backend.app.core.skill_update_manager import (
    get_skill_update_manager, UpdatePriority
)


class TestSkillVersionManager:
    """版本管理器测试"""

    def setup_method(self):
        self.manager = get_skill_version_manager()

    def test_create_version(self):
        """测试创建版本"""
        success, error, version = self.manager.create_version(
            skill_id="test-skill",
            version="1.0.0",
            changes="Initial release",
        )
        assert success
        assert error is None
        assert version.version == "1.0.0"
        assert version.skill_id == "test-skill"

    def test_invalid_version_format(self):
        """测试无效版本格式"""
        success, error, version = self.manager.create_version(
            skill_id="test-skill",
            version="invalid",
            changes="Test",
        )
        assert not success
        assert error is not None

    def test_duplicate_version(self):
        """测试重复版本"""
        self.manager.create_version(
            skill_id="test-skill",
            version="1.0.0",
            changes="First",
        )
        success, error, version = self.manager.create_version(
            skill_id="test-skill",
            version="1.0.0",
            changes="Second",
        )
        assert not success

    def test_get_versions(self):
        """测试获取版本列表"""
        self.manager.create_version("test-skill", "1.0.0", "First")
        self.manager.create_version("test-skill", "1.1.0", "Second")

        versions = self.manager.get_versions("test-skill")
        assert len(versions) == 2
        assert versions[0].version == "1.1.0"  # 按版本号排序

    def test_rollback_version(self):
        """测试版本回滚"""
        self.manager.create_version("test-skill", "1.0.0", "First")
        self.manager.create_version("test-skill", "1.1.0", "Second")

        success, error = self.manager.rollback_version("test-skill", "1.0.0")
        assert success

        current = self.manager.get_current_version("test-skill")
        assert current.version == "1.0.0"

    def test_compare_versions(self):
        """测试版本比较"""
        self.manager.create_version("test-skill", "1.0.0", "First")
        self.manager.create_version("test-skill", "2.0.0", "Second")

        success, error, comparison = self.manager.compare_versions(
            "test-skill", "2.0.0", "1.0.0"
        )
        assert success
        assert comparison["v1_newer"] is True


class TestSkillReviewSystem:
    """评论评分系统测试"""

    def setup_method(self):
        self.system = get_skill_review_system()
        # Reset singleton state to avoid cross-test pollution
        self.system.reviews.clear()
        self.system.user_reviews.clear()
        self.system.reports.clear()
        self.system.helpful_votes.clear()
        self.system.unhelpful_votes.clear()

    def test_add_review(self):
        """测试添加评论"""
        success, error, review = self.system.add_review(
            skill_id="test-skill",
            user_id="user1",
            user_name="User One",
            rating=5,
            title="Great skill",
            comment="Very useful",
        )
        assert success
        assert review.rating == 5
        assert review.status == ReviewStatus.PENDING

    def test_invalid_rating(self):
        """测试无效评分"""
        success, error, review = self.system.add_review(
            skill_id="test-skill",
            user_id="user1",
            user_name="User One",
            rating=10,  # 无效
            title="Test",
        )
        assert not success

    def test_duplicate_review(self):
        """测试重复评论"""
        self.system.add_review(
            skill_id="test-skill",
            user_id="user1",
            user_name="User One",
            rating=5,
            title="First",
        )
        success, error, review = self.system.add_review(
            skill_id="test-skill",
            user_id="user1",
            user_name="User One",
            rating=4,
            title="Second",
        )
        assert not success

    def test_get_average_rating(self):
        """测试获取平均评分"""
        self.system.add_review("test-skill", "user1", "User1", 5, "Great")
        self.system.add_review("test-skill", "user2", "User2", 3, "OK")

        # 批准评论
        reviews = self.system.reviews["test-skill"]
        for r in reviews:
            r.status = ReviewStatus.APPROVED

        avg = self.system.get_average_rating("test-skill")
        assert avg == 4.0

    def test_mark_helpful(self):
        """测试标记为有用"""
        success, error, review = self.system.add_review(
            "test-skill", "user1", "User1", 5, "Great"
        )

        success, error = self.system.mark_helpful(review.id, "user2")
        assert success
        assert review.helpful_count == 1

    def test_report_review(self):
        """测试举报评论"""
        success, error, review = self.system.add_review(
            "test-skill", "user1", "User1", 5, "Great"
        )

        success, error, report = self.system.report_review(
            review.id,
            "user2",
            ReportReason.SPAM,
            "This is spam",
        )
        assert success
        assert report.reason == ReportReason.SPAM


class TestSkillSearchEngine:
    """搜索引擎测试"""

    def setup_method(self):
        self.engine = get_skill_search_engine()

        # 索引测试技能
        self.engine.index_skill(
            skill_id="skill1",
            name="Python Helper",
            name_zh="Python助手",
            description="Python programming assistant",
            description_zh="Python编程助手",
            keywords=["python", "programming", "code"],
            category="development",
            tags=["coding", "automation"],
        )

        self.engine.index_skill(
            skill_id="skill2",
            name="Data Analyzer",
            name_zh="数据分析器",
            description="Data analysis tool",
            description_zh="数据分析工具",
            keywords=["data", "analysis", "visualization"],
            category="data",
            tags=["analytics", "reporting"],
        )

    def test_exact_search(self):
        """测试精确搜索"""
        results = self.engine._exact_search("Python Helper")
        assert len(results) > 0
        assert results[0].skill_id == "skill1"

    def test_partial_search(self):
        """测试部分匹配搜索"""
        results = self.engine._partial_search("python")
        assert len(results) > 0

    def test_fuzzy_search(self):
        """测试模糊搜索"""
        results = self.engine.fuzzy_search("pyton")  # 拼写错误
        assert len(results) > 0

    def test_semantic_search(self):
        """测试语义搜索"""
        results = self.engine.semantic_search("coding")
        assert len(results) > 0

    def test_search_suggestions(self):
        """测试搜索建议"""
        self.engine._record_search("python")
        self.engine._record_search("python")
        self.engine._record_search("data")

        suggestions = self.engine.get_suggestions("py")
        assert "python" in suggestions or len(suggestions) > 0


class TestSkillDependencyManager:
    """依赖管理器测试"""

    def setup_method(self):
        self.manager = get_skill_dependency_manager()

    def test_add_dependency(self):
        """测试添加依赖"""
        success, error = self.manager.add_dependency(
            skill_id="skill1",
            dep_skill_id="skill2",
            version_spec=">=1.0.0",
        )
        assert success

    def test_circular_dependency(self):
        """测试循环依赖检测"""
        self.manager.add_dependency("skill1", "skill2")
        success, error = self.manager.add_dependency("skill2", "skill1")
        assert not success  # 应该检测到循环依赖

    def test_get_dependencies(self):
        """测试获取依赖"""
        self.manager.add_dependency("skill1", "skill2")
        self.manager.add_dependency("skill1", "skill3")

        deps = self.manager.get_dependencies("skill1")
        assert len(deps) == 2

    def test_dependency_tree(self):
        """测试依赖树"""
        self.manager.add_dependency("skill1", "skill2")
        self.manager.add_dependency("skill2", "skill3")

        tree = self.manager.get_dependency_tree("skill1")
        assert tree["skill_id"] == "skill1"
        assert len(tree["children"]) > 0

    def test_resolve_conflicts(self):
        """测试解决冲突"""
        self.manager.add_dependency("skill1", "skill3", "1.0.0")
        self.manager.add_dependency("skill2", "skill3", "2.0.0")

        success, error, conflicts = self.manager.resolve_conflicts(["skill1", "skill2"])
        # 可能有版本冲突
        assert isinstance(conflicts, list)


class TestSkillUpdateManager:
    """更新管理器测试"""

    def setup_method(self):
        self.manager = get_skill_update_manager()
        self.manager.installed_versions["test-skill"] = "1.0.0"

    def test_register_update(self):
        """测试注册更新"""
        success, error = self.manager.register_available_update(
            skill_id="test-skill",
            current_version="1.0.0",
            new_version="1.1.0",
            changelog="Bug fixes",
            priority=UpdatePriority.MEDIUM,
        )
        assert success

    def test_check_updates(self):
        """测试检查更新"""
        self.manager.register_available_update(
            "test-skill", "1.0.0", "1.1.0", "Bug fixes"
        )

        success, error, update = self.manager.check_updates("test-skill")
        assert success
        assert update is not None
        assert update.new_version == "1.1.0"

    def test_update_skill(self):
        """测试更新技能"""
        self.manager.register_available_update(
            "test-skill", "1.0.0", "1.1.0", "Bug fixes"
        )

        success, error, update = self.manager.update_skill(
            "test-skill", "1.1.0"
        )
        assert success
        assert self.manager.installed_versions["test-skill"] == "1.1.0"

    def test_auto_update(self):
        """测试自动更新"""
        success, error = self.manager.enable_auto_update("test-skill")
        assert success
        assert self.manager.is_auto_update_enabled("test-skill")

    def test_notifications(self):
        """测试通知"""
        self.manager.register_available_update(
            "test-skill", "1.0.0", "1.1.0", "Bug fixes"
        )

        update = self.manager.available_updates["test-skill"]
        success, error, notification = self.manager.create_notification(
            "test-skill", "user1", update
        )
        assert success

        notifications = self.manager.get_notifications("user1")
        assert len(notifications) > 0


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        # 1. 创建版本
        version_mgr = get_skill_version_manager()
        success, _, version = version_mgr.create_version(
            "test-skill", "1.0.0", "Initial release"
        )
        assert success

        # 2. 添加评论
        review_sys = get_skill_review_system()
        success, _, review = review_sys.add_review(
            "test-skill", "user1", "User1", 5, "Great"
        )
        assert success

        # 3. 索引搜索
        search_engine = get_skill_search_engine()
        search_engine.index_skill(
            "test-skill", "Test Skill", "测试技能",
            "A test skill", "一个测试技能",
            ["test"], "development", ["testing"]
        )
        results = search_engine.search("test")
        assert len(results) > 0

        # 4. 添加依赖
        dep_mgr = get_skill_dependency_manager()
        success, _ = dep_mgr.add_dependency("test-skill", "dep-skill")
        assert success

        # 5. 注册更新
        update_mgr = get_skill_update_manager()
        update_mgr.installed_versions["test-skill"] = "1.0.0"
        success, _ = update_mgr.register_available_update(
            "test-skill", "1.0.0", "1.1.0", "Bug fixes"
        )
        assert success


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
