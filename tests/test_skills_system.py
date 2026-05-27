"""Tests for the skill system"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import json

from backend.app.core.skills_core import (
    SkillMetadata,
    SkillCapability,
    SkillRiskLevel,
    SkillExecutionContext,
)
from backend.app.core.skills_registry import SkillRegistry
from backend.app.core.skills_sandbox import SkillSandbox, ResourceLimits
from backend.app.core.skills_marketplace import SkillMarketplace
from backend.app.core.skills_manager import SkillSystemManager


class TestSkillMetadata:
    """Test skill metadata"""

    def test_metadata_creation(self):
        """Test creating skill metadata"""
        metadata = SkillMetadata(
            name="Test Skill",
            version="1.0.0",
            description="A test skill",
            author="Test Author",
            capabilities=[SkillCapability.TEXT_EXTRACT],
        )

        assert metadata.name == "Test Skill"
        assert metadata.version == "1.0.0"
        assert SkillCapability.TEXT_EXTRACT in metadata.capabilities

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary"""
        metadata = SkillMetadata(
            name="Test Skill",
            version="1.0.0",
            capabilities=[SkillCapability.TEXT_EXTRACT],
        )

        data = metadata.to_dict()
        assert data["name"] == "Test Skill"
        assert data["version"] == "1.0.0"
        assert "text:extract" in data["capabilities"]


class TestSkillRegistry:
    """Test skill registry"""

    @pytest.mark.asyncio
    async def test_register_skill(self):
        """Test registering a skill"""
        registry = SkillRegistry()
        metadata = SkillMetadata(
            name="Test Skill",
            version="1.0.0",
            capabilities=[SkillCapability.TEXT_EXTRACT],
        )

        success, error = await registry.register_skill(metadata)
        assert success
        assert error is None

        retrieved = registry.get_skill(metadata.skill_id)
        assert retrieved is not None
        assert retrieved.name == "Test Skill"

    @pytest.mark.asyncio
    async def test_search_skills(self):
        """Test searching for skills"""
        registry = SkillRegistry()

        for i in range(3):
            metadata = SkillMetadata(
                name=f"Test Skill {i}",
                version="1.0.0",
                description=f"A test skill for searching {i}",
                tags=["test", "search"],
            )
            await registry.register_skill(metadata)

        results = registry.search_skills("test")
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_find_by_capability(self):
        """Test finding skills by capability"""
        registry = SkillRegistry()

        metadata = SkillMetadata(
            name="Text Skill",
            version="1.0.0",
            capabilities=[SkillCapability.TEXT_EXTRACT],
        )
        await registry.register_skill(metadata)

        skills = registry.find_by_capability(SkillCapability.TEXT_EXTRACT)
        assert len(skills) > 0
        assert any(s.name == "Text Skill" for s in skills)

    @pytest.mark.asyncio
    async def test_rate_skill(self):
        """Test rating a skill"""
        registry = SkillRegistry()

        metadata = SkillMetadata(name="Test Skill", version="1.0.0")
        await registry.register_skill(metadata)

        success, error = await registry.rate_skill(metadata.skill_id, 4.5)
        assert success

        rating = registry.get_skill_rating(metadata.skill_id)
        assert rating is not None
        assert rating.average_rating == 4.5
        assert rating.total_ratings == 1


class TestSkillSandbox:
    """Test skill sandbox"""

    @pytest.mark.asyncio
    async def test_sandbox_execution(self):
        """Test executing code in sandbox"""
        sandbox = SkillSandbox()
        context = SkillExecutionContext()

        async def test_coro():
            return {"result": "success"}

        result = await sandbox.execute(test_coro(), context)
        assert result.success
        assert result.output == {"result": "success"}

    @pytest.mark.asyncio
    async def test_sandbox_timeout(self):
        """Test sandbox timeout"""
        limits = ResourceLimits(timeout_seconds=1)
        sandbox = SkillSandbox(limits)
        context = SkillExecutionContext()

        async def slow_coro():
            await asyncio.sleep(5)
            return {"result": "success"}

        result = await sandbox.execute(slow_coro(), context)
        assert not result.success
        assert "timeout" in result.error.lower()

    def test_file_access_validation(self):
        """Test file access validation"""
        limits = ResourceLimits(
            allowed_paths=["/home/user/skills"],
            blocked_paths=["/etc", "/root"],
        )
        sandbox = SkillSandbox(limits)

        success, error = sandbox.validate_file_access("/etc/passwd")
        assert not success

        success, error = sandbox.validate_file_access("/home/user/skills/test.py")
        assert success


class TestSkillMarketplace:
    """Test skill marketplace"""

    @pytest.mark.asyncio
    async def test_marketplace_operations(self):
        """Test marketplace operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            marketplace = SkillMarketplace(tmpdir)

            skill_file = Path(tmpdir) / "test_skill.py"
            skill_file.write_text("# Test skill")

            metadata = SkillMetadata(
                name="Test Skill",
                version="1.0.0",
                description="A test skill",
            )

            success, error = await marketplace.publish_skill(
                metadata,
                str(skill_file),
                author="Test Author",
            )

            assert success
            assert error is None

            package = marketplace.get_package(metadata.skill_id)
            assert package is not None
            assert package.name == "Test Skill"


class TestSkillSystemManager:
    """Test skill system manager"""

    @pytest.mark.asyncio
    async def test_system_health(self):
        """Test getting system health"""
        manager = SkillSystemManager()
        health = await manager.get_system_health()

        assert "loaded_skills" in health
        assert "registered_skills" in health
        assert "installed_skills" in health
        assert "marketplace_stats" in health

    @pytest.mark.asyncio
    async def test_discover_skills(self):
        """Test discovering skills"""
        manager = SkillSystemManager()

        metadata = SkillMetadata(
            name="Test Skill",
            version="1.0.0",
            capabilities=[SkillCapability.TEXT_EXTRACT],
            tags=["test"],
        )
        await manager.registry.register_skill(metadata)

        skills = await manager.discover_skills(capability=SkillCapability.TEXT_EXTRACT)
        assert len(skills) > 0

        skills = await manager.discover_skills(tag="test")
        assert len(skills) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
