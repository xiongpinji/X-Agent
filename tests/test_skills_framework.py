"""Tests for the declarative Skills framework."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from backend.app.core.skills import (
    SkillDefinition,
    SkillExecutor,
    SkillInput,
    SkillLoader,
    SkillOutput,
    SkillStep,
    SkillTrigger,
    StepResult,
    load_builtin_skills,
)


class TestSkillLoaderYaml:
    """Test skill loading from YAML files."""

    @pytest.fixture
    def temp_skill_dir(self, tmp_path):
        """Create temporary directory with test skill YAML."""
        skill_yaml = {
            "name": "test_skill",
            "version": "1.0",
            "description": "A test skill",
            "author": "test",
            "steps": [
                {
                    "id": "step1",
                    "tool": "echo",
                    "args": {"message": "hello"},
                    "output_var": "output",
                }
            ],
        }

        yaml_file = tmp_path / "test_skill.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(skill_yaml, f)

        return tmp_path

    def test_load_skill_from_yaml(self, temp_skill_dir):
        """Test loading a single skill from YAML."""
        skill_file = temp_skill_dir / "test_skill.yaml"
        loader = SkillLoader([temp_skill_dir])
        skill = loader.load_skill(skill_file)

        assert skill.name == "test_skill"
        assert skill.version == "1.0"
        assert len(skill.steps) == 1
        assert skill.steps[0].id == "step1"

    def test_load_all_skills(self, temp_skill_dir):
        """Test loading all skills from directory."""
        # Add another skill
        skill2_yaml = {
            "name": "skill2",
            "version": "2.0",
            "description": "Second skill",
            "author": "test",
            "steps": [{"id": "s1", "tool": "echo", "args": {}}],
        }
        with open(temp_skill_dir / "skill2.yaml", "w") as f:
            yaml.dump(skill2_yaml, f)

        loader = SkillLoader([temp_skill_dir])
        skills = loader.load_all()

        assert len(skills) == 2
        assert "test_skill" in skills
        assert "skill2" in skills

    def test_load_skill_file_not_found(self):
        """Test error when skill file doesn't exist."""
        loader = SkillLoader([])
        with pytest.raises(FileNotFoundError):
            loader.load_skill(Path("/nonexistent/skill.yaml"))

    def test_load_skill_invalid_yaml(self, tmp_path):
        """Test error on invalid YAML."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("{ invalid yaml: [")

        loader = SkillLoader([tmp_path])
        with pytest.raises(ValueError, match="Invalid YAML"):
            loader.load_skill(yaml_file)

    def test_load_skill_schema_validation_fails(self, tmp_path):
        """Test error on schema validation failure."""
        invalid_skill = {
            "name": "test",
            # Missing required 'steps' field
            "version": "1.0",
        }

        yaml_file = tmp_path / "invalid_schema.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(invalid_skill, f)

        loader = SkillLoader([tmp_path])
        with pytest.raises(ValueError, match="schema validation failed"):
            loader.load_skill(yaml_file)


class TestSkillValidation:
    """Test skill definition validation."""

    def test_validate_skill_valid(self):
        """Test validation of a valid skill."""
        skill = SkillDefinition(
            name="test",
            description="Test skill",
            steps=[
                SkillStep(id="s1", tool="tool1", output_var="result1"),
                SkillStep(id="s2", tool="tool2", args={"input": "{{steps.s1.output}}"}),
            ],
            outputs=[SkillOutput(name="out1", value="{{steps.s2.output}}")],
        )

        loader = SkillLoader([])
        errors = loader.validate(skill)
        assert len(errors) == 0

    def test_validate_skill_duplicate_step_ids(self):
        """Test validation catches duplicate step IDs."""
        skill = SkillDefinition(
            name="test",
            description="Test",
            steps=[
                SkillStep(id="s1", tool="tool1"),
                SkillStep(id="s1", tool="tool2"),  # Duplicate ID
            ],
        )

        loader = SkillLoader([])
        errors = loader.validate(skill)
        assert any("Duplicate step IDs" in e for e in errors)

    def test_validate_skill_missing_output_step(self):
        """Test validation catches undefined steps in outputs."""
        skill = SkillDefinition(
            name="test",
            description="Test",
            steps=[SkillStep(id="s1", tool="tool1")],
            outputs=[SkillOutput(name="out", value="{{steps.undefined.output}}")],
        )

        loader = SkillLoader([])
        errors = loader.validate(skill)
        assert any("undefined steps" in e.lower() for e in errors)

    def test_validate_skill_missing_foreach_step(self):
        """Test validation catches undefined steps in foreach."""
        skill = SkillDefinition(
            name="test",
            description="Test",
            steps=[SkillStep(id="s1", tool="tool1", foreach="{{steps.missing.output}}")],
        )

        loader = SkillLoader([])
        errors = loader.validate(skill)
        assert any("undefined steps" in e.lower() for e in errors)


@pytest.mark.asyncio
class TestSkillExecutor:
    """Test skill execution."""

    @pytest.fixture
    def mock_tool_registry(self):
        """Create mock tool registry."""
        registry = MagicMock()

        async def get_tool(name):
            tool = AsyncMock()
            if name == "echo":
                tool.call = AsyncMock(side_effect=lambda **kwargs: kwargs.get("message", ""))
            elif name == "concat":
                tool.call = AsyncMock(
                    side_effect=lambda **kwargs: kwargs.get("a", "") + kwargs.get("b", "")
                )
            elif name == "upper":
                tool.call = AsyncMock(side_effect=lambda **kwargs: kwargs.get("text", "").upper())
            elif name == "list_items":
                tool.call = AsyncMock(side_effect=lambda **kwargs: ["a", "b", "c"])
            else:
                return None
            return tool

        registry.get_tool = get_tool
        return registry

    async def test_execute_simple_skill(self, mock_tool_registry):
        """Test executing a simple skill with one step."""
        skill = SkillDefinition(
            name="simple",
            description="Simple test",
            steps=[SkillStep(id="s1", tool="echo", args={"message": "hello"})],
            outputs=[SkillOutput(name="result", value="{{steps.s1.output}}")],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {})

        assert result.success
        assert result.outputs["result"] == "hello"
        assert len(result.step_results) == 1

    async def test_execute_with_inputs(self, mock_tool_registry):
        """Test executing skill with input substitution."""
        skill = SkillDefinition(
            name="with_inputs",
            description="Test with inputs",
            inputs=[SkillInput(name="message", type="string", required=True)],
            steps=[SkillStep(id="s1", tool="echo", args={"message": "{{inputs.message}}"})],
            outputs=[SkillOutput(name="result", value="{{steps.s1.output}}")],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {"message": "test_input"})

        assert result.success
        assert result.outputs["result"] == "test_input"

    async def test_execute_with_step_chaining(self, mock_tool_registry):
        """Test executing skill with step dependencies."""
        skill = SkillDefinition(
            name="chained",
            description="Chained steps",
            steps=[
                SkillStep(id="s1", tool="echo", args={"message": "hello"}),
                SkillStep(
                    id="s2",
                    tool="concat",
                    args={"a": "{{steps.s1.output}}", "b": "_world"},
                ),
            ],
            outputs=[SkillOutput(name="result", value="{{steps.s2.output}}")],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {})

        assert result.success
        assert result.outputs["result"] == "hello_world"

    async def test_execute_with_condition_true(self, mock_tool_registry):
        """Test conditional step execution (condition true)."""
        skill = SkillDefinition(
            name="conditional",
            description="With condition",
            steps=[
                SkillStep(id="s1", tool="echo", args={"message": "yes"}),
                SkillStep(
                    id="s2",
                    tool="echo",
                    args={"message": "executed"},
                    condition="true",
                ),
            ],
            outputs=[SkillOutput(name="result", value="{{steps.s2.output}}")],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {})

        assert result.success
        assert len(result.step_results) == 2

    async def test_execute_with_condition_false(self, mock_tool_registry):
        """Test conditional step execution (condition false)."""
        skill = SkillDefinition(
            name="conditional",
            description="With condition",
            steps=[
                SkillStep(id="s1", tool="echo", args={"message": "yes"}),
                SkillStep(
                    id="s2",
                    tool="echo",
                    args={"message": "skipped"},
                    condition="false",
                ),
            ],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {})

        # Second step should be skipped
        assert len(result.step_results) == 1

    async def test_execute_with_foreach(self, mock_tool_registry):
        """Test foreach iteration."""
        skill = SkillDefinition(
            name="foreach",
            description="With foreach",
            steps=[
                SkillStep(
                    id="s1",
                    tool="list_items",
                    args={},
                    output_var="items",
                ),
                SkillStep(
                    id="s2",
                    tool="upper",
                    args={"text": "{{item}}"},
                    foreach="{{steps.s1.output}}",
                ),
            ],
            outputs=[SkillOutput(name="results", value="{{steps.s2.output}}")],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {})

        assert result.success
        assert result.outputs["results"] == ["A", "B", "C"]

    async def test_execute_step_failure(self, mock_tool_registry):
        """Test handling step failure."""
        skill = SkillDefinition(
            name="with_failure",
            description="Step fails",
            steps=[
                SkillStep(id="s1", tool="nonexistent", args={}),
            ],
        )

        executor = SkillExecutor(mock_tool_registry)
        result = await executor.execute(skill, {})

        assert not result.success
        assert len(result.errors) > 0
        assert not result.step_results[0].success


class TestTemplateResolution:
    """Test template variable resolution."""

    def test_resolve_template_simple(self):
        """Test resolving simple template."""
        executor = SkillExecutor(None)
        variables = {"inputs": {"name": "test"}}
        result = executor._resolve_template("{{inputs.name}}", variables)
        assert result == "test"

    def test_resolve_template_nested(self):
        """Test resolving nested variable."""
        executor = SkillExecutor(None)
        variables = {"steps": {"s1": {"output": "value"}}}
        result = executor._resolve_template("{{steps.s1.output}}", variables)
        assert result == "value"

    def test_resolve_template_no_substitution(self):
        """Test template without substitution."""
        executor = SkillExecutor(None)
        result = executor._resolve_template("plain string", {})
        assert result == "plain string"

    def test_resolve_template_undefined_variable(self):
        """Test error on undefined variable."""
        executor = SkillExecutor(None)
        with pytest.raises(ValueError, match="Undefined variable"):
            executor._resolve_template("{{undefined.var}}", {})

    def test_resolve_template_inline(self):
        """Test inline template substitution."""
        executor = SkillExecutor(None)
        variables = {"inputs": {"name": "Alice"}}
        result = executor._resolve_template("Hello {{inputs.name}}!", variables)
        assert result == "Hello Alice!"


class TestBuiltinSkills:
    """Test loading built-in skills."""

    def test_load_builtin_skills(self):
        """Test loading all built-in skills."""
        skills = load_builtin_skills()
        assert isinstance(skills, dict)
        # Built-in skills should be available
        expected_skills = {"code_review", "test_gen", "refactor"}
        loaded_names = set(skills.keys())
        assert expected_skills.issubset(loaded_names)

    def test_builtin_skills_valid(self):
        """Test that built-in skills are valid."""
        skills = load_builtin_skills()
        loader = SkillLoader()

        for skill_name, skill_def in skills.items():
            errors = loader.validate(skill_def)
            assert len(errors) == 0, f"Skill {skill_name} has validation errors: {errors}"
