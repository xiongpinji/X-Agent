"""Tests for prompt system integration."""

import pytest
from pathlib import Path

from backend.app.core.prompt_schema import (
    PromptMetadata,
    PromptSchema,
    PromptInput,
    PromptOutput,
    PromptConstraint,
)
from backend.app.core.prompt_loader import PromptLoader, PromptVersionManager
from backend.app.core.prompt_registry import PromptRegistry
from backend.app.core.prompt_manager import PromptManager, PromptContext


class TestPromptVersionManager:
    """Test semantic versioning."""

    def test_parse_version(self):
        """Test version parsing."""
        major, minor, patch = PromptVersionManager.parse_version("1.2.3")
        assert major == 1
        assert minor == 2
        assert patch == 3

    def test_parse_version_invalid(self):
        """Test invalid version format."""
        with pytest.raises(ValueError):
            PromptVersionManager.parse_version("1.2")

    def test_increment_patch(self):
        """Test patch version increment."""
        new_version = PromptVersionManager.increment_version("1.0.0", "patch")
        assert new_version == "1.0.1"

    def test_increment_minor(self):
        """Test minor version increment."""
        new_version = PromptVersionManager.increment_version("1.0.0", "minor")
        assert new_version == "1.1.0"

    def test_increment_major(self):
        """Test major version increment."""
        new_version = PromptVersionManager.increment_version("1.0.0", "major")
        assert new_version == "2.0.0"

    def test_compare_versions(self):
        """Test version comparison."""
        assert PromptVersionManager.compare_versions("1.0.0", "1.1.0") == -1
        assert PromptVersionManager.compare_versions("1.1.0", "1.0.0") == 1
        assert PromptVersionManager.compare_versions("1.0.0", "1.0.0") == 0


class TestPromptSchema:
    """Test prompt schema."""

    def test_create_schema(self):
        """Test creating a prompt schema."""
        metadata = PromptMetadata(
            id="test_prompt",
            name="Test Prompt",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(
            metadata=metadata,
            content="Test content",
        )
        assert schema.metadata.id == "test_prompt"
        assert schema.content == "Test content"

    def test_schema_to_dict(self):
        """Test schema serialization."""
        metadata = PromptMetadata(
            id="test_prompt",
            name="Test Prompt",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(
            metadata=metadata,
            content="Test content",
            inputs=[PromptInput(name="input1", type="string", description="Test input")],
        )
        schema_dict = schema.to_dict()
        assert schema_dict["metadata"]["id"] == "test_prompt"
        assert len(schema_dict["inputs"]) == 1


class TestPromptRegistry:
    """Test prompt registry."""

    def test_register_prompt(self):
        """Test registering a prompt."""
        registry = PromptRegistry()
        metadata = PromptMetadata(
            id="test_prompt",
            name="Test Prompt",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(metadata=metadata, content="Test")
        registry.register_prompt(schema)

        retrieved = registry.get_prompt("test_prompt")
        assert retrieved is not None
        assert retrieved.metadata.id == "test_prompt"

    def test_get_prompts_by_scope(self):
        """Test retrieving prompts by scope."""
        registry = PromptRegistry()

        # Register prompts in different scopes
        for scope in ["system", "roles", "tools"]:
            metadata = PromptMetadata(
                id=f"prompt_{scope}",
                name=f"Prompt {scope}",
                version="1.0.0",
                purpose="Testing",
                scope=scope,
            )
            schema = PromptSchema(metadata=metadata, content="Test")
            registry.register_prompt(schema)

        # Retrieve by scope
        system_prompts = registry.get_prompts_by_scope("system")
        assert len(system_prompts) == 1
        assert system_prompts[0].metadata.scope == "system"

    def test_validate_prompt(self):
        """Test prompt validation."""
        registry = PromptRegistry()

        # Valid prompt
        metadata = PromptMetadata(
            id="test_prompt",
            name="Test Prompt",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(metadata=metadata, content="Test content here")
        is_valid, errors = registry.validate_prompt(schema)
        assert is_valid
        assert len(errors) == 0

        # Invalid prompt (missing ID)
        metadata_invalid = PromptMetadata(
            id="",
            name="Test",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema_invalid = PromptSchema(metadata=metadata_invalid, content="Test")
        is_valid, errors = registry.validate_prompt(schema_invalid)
        assert not is_valid
        assert len(errors) > 0


class TestPromptContext:
    """Test prompt context."""

    def test_render_without_variables(self):
        """Test rendering prompt without variables."""
        metadata = PromptMetadata(
            id="test",
            name="Test",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(metadata=metadata, content="Hello world")
        ctx = PromptContext(schema)
        assert ctx.render() == "Hello world"

    def test_render_with_variables(self):
        """Test rendering prompt with variables."""
        metadata = PromptMetadata(
            id="test",
            name="Test",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(metadata=metadata, content="Hello {{name}}")
        ctx = PromptContext(schema, {"name": "World"})
        # Note: This requires prompt_loader to be properly initialized
        # For now, we test the context creation
        assert ctx.variables["name"] == "World"

    def test_get_metadata(self):
        """Test getting metadata from context."""
        metadata = PromptMetadata(
            id="test",
            name="Test Prompt",
            version="1.0.0",
            purpose="Testing",
            scope="system",
        )
        schema = PromptSchema(metadata=metadata, content="Test")
        ctx = PromptContext(schema)
        meta = ctx.get_metadata()
        assert meta["id"] == "test"
        assert meta["name"] == "Test Prompt"
        assert meta["version"] == "1.0.0"


class TestPromptManager:
    """Test prompt manager."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = PromptManager()
        assert not manager._loaded

    def test_get_system_prompt_not_found(self):
        """Test getting system prompt when not loaded."""
        manager = PromptManager()
        with pytest.raises(ValueError):
            manager.get_system_prompt()

    def test_build_messages(self):
        """Test building messages for LLM."""
        manager = PromptManager()

        # Create test prompts
        sys_metadata = PromptMetadata(
            id="system",
            name="System",
            version="1.0.0",
            purpose="System",
            scope="system",
        )
        sys_schema = PromptSchema(metadata=sys_metadata, content="You are helpful")
        sys_ctx = PromptContext(sys_schema)

        role_metadata = PromptMetadata(
            id="planner",
            name="Planner",
            version="1.0.0",
            purpose="Planning",
            scope="roles",
        )
        role_schema = PromptSchema(metadata=role_metadata, content="Plan the task")
        role_ctx = PromptContext(role_schema)

        messages = manager.build_messages(sys_ctx, "Do something", role_ctx)
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "Do something"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
