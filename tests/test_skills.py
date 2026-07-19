"""
技能系统测试
"""

import pytest
from backend.app.core.skills import Skill, SkillMetadata, SkillContext, SkillRegistry, SkillLoader


class MockSkill(Skill):
    """测试用的模拟技能"""

    def __init__(self, name: str = "mock_skill"):
        super().__init__()
        self._name = name

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self._name,
            version="1.0.0",
            description="Mock skill for testing",
            author="Test",
            capabilities=["test"],
            tags=["test"],
        )

    async def execute(self, context: SkillContext, **kwargs):
        from backend.app.core.skills.skill_base import SkillResult
        return SkillResult(
            success=True,
            data={"message": "Mock skill executed"},
        )


class TestSkillRegistry:
    """技能注册表测试"""

    def test_register_skill(self):
        """测试注册技能"""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        assert registry.exists("mock_skill")
        assert registry.get("mock_skill") == skill

    def test_unregister_skill(self):
        """测试注销技能"""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        assert registry.unregister("mock_skill")
        assert not registry.exists("mock_skill")

    def test_list_skills(self):
        """测试列出技能"""
        registry = SkillRegistry()
        skill1 = MockSkill("mock_skill_1")
        skill2 = MockSkill("mock_skill_2")

        registry.register(skill1)
        registry.register(skill2)

        skills = registry.list_skills()
        assert len(skills) == 2  # 两个不同名技能各注册一次

    def test_get_by_capability(self):
        """测试根据能力获取技能"""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        skills = registry.get_by_capability("test")
        assert len(skills) == 1
        assert skills[0] == skill

    def test_get_by_tag(self):
        """测试根据标签获取技能"""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        skills = registry.get_by_tag("test")
        assert len(skills) == 1
        assert skills[0] == skill

    def test_duplicate_registration(self):
        """测试重复注册"""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        with pytest.raises(ValueError):
            registry.register(skill)

    def test_clear_registry(self):
        """测试清空注册表"""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        registry.clear()
        assert len(registry.list_skills()) == 0


class TestSkillExecution:
    """技能执行测试"""

    @pytest.mark.asyncio
    async def test_execute_skill(self):
        """测试执行技能"""
        skill = MockSkill()
        context = SkillContext(
            skill_name="mock_skill",
            execution_id="test-123",
        )

        result = await skill.execute(context)
        assert result.success
        assert result.data["message"] == "Mock skill executed"

    @pytest.mark.asyncio
    async def test_skill_validation(self):
        """测试技能验证"""
        skill = MockSkill()
        context = SkillContext(
            skill_name="mock_skill",
            execution_id="test-123",
        )

        is_valid = await skill.validate(context)
        assert is_valid

    @pytest.mark.asyncio
    async def test_skill_health_check(self):
        """测试技能健康检查"""
        skill = MockSkill()
        is_healthy = await skill.health_check()
        assert is_healthy
