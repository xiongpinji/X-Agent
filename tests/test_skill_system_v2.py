"""
X-Agent 技能系统测试 - 验证技能系统的完整功能
"""

import pytest
import asyncio
from typing import Any, Dict

from backend.app.core.skill_system_v2 import (
    Skill,
    SkillMetadata,
    SkillExecutionContext,
    SkillExecutionResult,
    SkillParameter,
    SkillCategory,
    SkillRiskLevel,
    ExecutionStatus,
    SkillRegistry,
    SkillExecutor,
    get_skill_registry,
    get_skill_executor,
)
from backend.app.core.skill_chain import (
    SkillChain,
    ChainStep,
    ChainType,
    SkillChainExecutor,
    get_skill_chain_executor,
)
from backend.app.core.skill_review import (
    SkillReviewManager,
    ReviewStatus,
    SeverityLevel,
    get_skill_review_manager,
)


# ==================== 测试技能 ====================


class TestSkill(Skill):
    """用于测试的示例技能"""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="test-skill",
            name_zh="测试技能",
            version="1.0.0",
            description="A test skill",
            description_zh="一个测试技能",
            author="Test Author",
            category=SkillCategory.PRODUCTIVITY,
            icon_emoji="🧪",
            capabilities=["text:generate"],
            parameters=[
                SkillParameter(
                    name="input_text",
                    type="string",
                    description="Input text",
                    required=True,
                ),
                SkillParameter(
                    name="multiplier",
                    type="number",
                    description="Multiplier",
                    required=False,
                    default=1,
                    min_value=1,
                    max_value=10,
                ),
            ],
            tags=["test"],
            keywords=["test"],
            documentation_url="https://example.com/docs",
            repository_url="https://github.com/example/test-skill",
        )

    async def execute(
        self, context: SkillExecutionContext, **kwargs
    ) -> SkillExecutionResult:
        try:
            input_text = kwargs.get("input_text", "")
            multiplier = kwargs.get("multiplier", 1)

            result = input_text * multiplier

            return SkillExecutionResult(
                success=True,
                data={"result": result},
                execution_time_ms=0.0,
            )
        except Exception as e:
            return SkillExecutionResult(
                success=False,
                error=str(e),
                error_type=type(e).__name__,
            )


class FailingSkill(Skill):
    """用于测试错误处理的技能"""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="failing-skill",
            version="1.0.0",
            description="A failing skill",
            author="Test Author",
        )

    async def execute(
        self, context: SkillExecutionContext, **kwargs
    ) -> SkillExecutionResult:
        raise ValueError("Intentional error for testing")


# ==================== 技能系统测试 ====================


class TestSkillSystem:
    """技能系统测试"""

    @pytest.mark.asyncio
    async def test_skill_registration(self):
        """测试技能注册"""
        registry = SkillRegistry()
        skill = TestSkill()

        await registry.register(skill)

        assert await registry.exists("test-skill")
        assert await registry.get("test-skill") is not None

    @pytest.mark.asyncio
    async def test_skill_unregistration(self):
        """测试技能注销"""
        registry = SkillRegistry()
        skill = TestSkill()

        await registry.register(skill)
        assert await registry.exists("test-skill")

        result = await registry.unregister("test-skill")
        assert result is True
        assert not await registry.exists("test-skill")

    @pytest.mark.asyncio
    async def test_skill_metadata(self):
        """测试技能元数据"""
        registry = SkillRegistry()
        skill = TestSkill()

        await registry.register(skill)
        metadata = await registry.get_metadata("test-skill")

        assert metadata is not None
        assert metadata.name == "test-skill"
        assert metadata.version == "1.0.0"
        assert metadata.category == SkillCategory.PRODUCTIVITY

    @pytest.mark.asyncio
    async def test_skill_execution(self):
        """测试技能执行"""
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        skill = TestSkill()

        await registry.register(skill)

        result = await executor.execute(
            skill_name="test-skill",
            input_data={"input_text": "Hello", "multiplier": 3},
            user_id="user123",
            tenant_id="tenant123",
        )

        assert result.success is True
        assert result.data["result"] == "HelloHelloHello"

    @pytest.mark.asyncio
    async def test_skill_execution_failure(self):
        """测试技能执行失败"""
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        skill = FailingSkill()

        await registry.register(skill)

        result = await executor.execute(
            skill_name="failing-skill",
            input_data={},
            user_id="user123",
            tenant_id="tenant123",
        )

        assert result.success is False
        assert "Intentional error" in result.error

    @pytest.mark.asyncio
    async def test_skill_parameter_validation(self):
        """测试技能参数验证"""
        skill = TestSkill()

        # 有效的参数
        valid, error = await skill.validate_input(
            {"input_text": "Hello", "multiplier": 5}
        )
        assert valid is True
        assert error is None

        # 缺少必需参数
        valid, error = await skill.validate_input({})
        assert valid is False
        assert "required" in error.lower()

        # 参数超出范围
        valid, error = await skill.validate_input(
            {"input_text": "Hello", "multiplier": 20}
        )
        assert valid is False
        assert "must be <=" in error

    @pytest.mark.asyncio
    async def test_skill_execution_history(self):
        """测试执行历史"""
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        skill = TestSkill()

        await registry.register(skill)

        # 执行技能
        result = await executor.execute(
            skill_name="test-skill",
            input_data={"input_text": "Test"},
            user_id="user123",
            tenant_id="tenant123",
        )

        # 获取执行历史
        history = await executor.list_execution_history("test-skill", limit=10)
        assert len(history) > 0
        assert history[0].skill_name == "test-skill"


# ==================== 技能链测试 ====================


class TestSkillChain:
    """技能链测试"""

    @pytest.mark.asyncio
    async def test_sequential_chain(self):
        """测试顺序链"""
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        chain_executor = SkillChainExecutor()

        skill = TestSkill()
        await registry.register(skill)

        chain = SkillChain(
            name="test-chain",
            chain_type=ChainType.SEQUENTIAL,
            steps=[
                ChainStep(
                    name="step1",
                    skill_name="test-skill",
                    input_mapping={"input_text": "text"},
                    output_mapping={"result": "output"},
                ),
            ],
        )

        context = await chain_executor.execute_chain(
            chain=chain,
            input_data={"text": "Hello"},
            user_id="user123",
            tenant_id="tenant123",
        )

        assert context.status == ExecutionStatus.SUCCESS
        assert "output" in context.output_data

    @pytest.mark.asyncio
    async def test_parallel_chain(self):
        """测试并行链"""
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        chain_executor = SkillChainExecutor()

        skill = TestSkill()
        await registry.register(skill)

        chain = SkillChain(
            name="parallel-chain",
            chain_type=ChainType.PARALLEL,
            steps=[
                ChainStep(name="step1", skill_name="test-skill"),
                ChainStep(name="step2", skill_name="test-skill"),
            ],
        )

        context = await chain_executor.execute_chain(
            chain=chain,
            input_data={},
            user_id="user123",
            tenant_id="tenant123",
        )

        assert context.status == ExecutionStatus.SUCCESS
        assert len(context.step_results) == 2


# ==================== 技能审核测试 ====================


class TestSkillReview:
    """技能审核测试"""

    @pytest.mark.asyncio
    async def test_security_check(self):
        """测试安全检查"""
        manager = SkillReviewManager()
        checker = manager.security_checker

        metadata = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test skill",
            "author": "Test Author",
            "risk_level": "medium",
            "dependencies": {},
            "capabilities": [],
            "allowed_actions": ["read"],
        }

        result = await checker.check_security(metadata)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_performance_check(self):
        """测试性能检查"""
        manager = SkillReviewManager()
        checker = manager.security_checker

        metadata = {
            "timeout_seconds": 300,
            "max_memory_mb": 512,
            "max_cpu_percent": 50.0,
        }

        result = await checker.check_performance(metadata)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_functionality_check(self):
        """测试功能检查"""
        manager = SkillReviewManager()
        checker = manager.security_checker

        metadata = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "Test skill",
            "author": "Test Author",
            "parameters": [{"name": "input", "type": "string"}],
            "capabilities": ["text:generate"],
        }

        result = await checker.check_functionality(metadata)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_documentation_check(self):
        """测试文档检查"""
        manager = SkillReviewManager()
        checker = manager.security_checker

        metadata = {
            "description": "This is a comprehensive description of the test skill",
            "documentation_url": "https://example.com/docs",
            "repository_url": "https://github.com/example/test-skill",
        }

        result = await checker.check_documentation(metadata)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_compatibility_check(self):
        """测试兼容性检查"""
        manager = SkillReviewManager()
        checker = manager.security_checker

        metadata = {
            "version": "1.0.0",
            "license": "MIT",
        }

        result = await checker.check_compatibility(metadata)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_create_review(self):
        """测试创建审核记录"""
        manager = SkillReviewManager()

        metadata = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "This is a comprehensive test skill description",
            "author": "Test Author",
            "risk_level": "medium",
            "dependencies": {},
            "capabilities": ["text:generate"],
            "parameters": [{"name": "input", "type": "string"}],
            "timeout_seconds": 300,
            "max_memory_mb": 512,
            "max_cpu_percent": 50.0,
            "documentation_url": "https://example.com/docs",
            "repository_url": "https://github.com/example/test-skill",
            "license": "MIT",
        }

        review = await manager.create_review(
            skill_id="skill123",
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_metadata=metadata,
        )

        assert review.skill_id == "skill123"
        assert review.overall_score > 0
        assert review.status in [
            ReviewStatus.APPROVED,
            ReviewStatus.APPROVED_WITH_CONDITIONS,
        ]

    @pytest.mark.asyncio
    async def test_approve_review(self):
        """测试批准审核"""
        manager = SkillReviewManager()

        metadata = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "This is a comprehensive test skill description",
            "author": "Test Author",
            "risk_level": "medium",
            "dependencies": {},
            "capabilities": ["text:generate"],
            "parameters": [{"name": "input", "type": "string"}],
            "timeout_seconds": 300,
            "max_memory_mb": 512,
            "max_cpu_percent": 50.0,
            "documentation_url": "https://example.com/docs",
            "repository_url": "https://github.com/example/test-skill",
            "license": "MIT",
        }

        review = await manager.create_review(
            skill_id="skill123",
            skill_name="test-skill",
            skill_version="1.0.0",
            skill_metadata=metadata,
        )

        approved_review = await manager.approve_review(
            review_id=review.review_id,
            reviewer_id="reviewer123",
            reviewer_name="Test Reviewer",
            comments="Looks good!",
        )

        assert approved_review.status == ReviewStatus.APPROVED
        assert approved_review.reviewer_id == "reviewer123"


# ==================== 集成测试 ====================


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self):
        """测试端到端工作流"""
        # 1. 注册技能
        registry = SkillRegistry()
        skill = TestSkill()
        await registry.register(skill)

        # 2. 执行技能
        executor = SkillExecutor(registry)
        result = await executor.execute(
            skill_name="test-skill",
            input_data={"input_text": "Test", "multiplier": 2},
            user_id="user123",
            tenant_id="tenant123",
        )
        assert result.success is True

        # 3. 创建审核
        manager = SkillReviewManager()
        metadata = skill.metadata.to_dict()
        review = await manager.create_review(
            skill_id=metadata["skill_id"],
            skill_name=metadata["name"],
            skill_version=metadata["version"],
            skill_metadata=metadata,
        )
        assert review.overall_score > 0

        # 4. 批准审核
        approved = await manager.approve_review(
            review_id=review.review_id,
            reviewer_id="reviewer123",
            reviewer_name="Test Reviewer",
        )
        assert approved.status == ReviewStatus.APPROVED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
