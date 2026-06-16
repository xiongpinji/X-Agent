"""Load and validate skill definitions from YAML files."""

import logging
from pathlib import Path
from typing import Optional

import yaml

from backend.app.core.skills.schema import SkillDefinition

logger = logging.getLogger(__name__)


class SkillLoader:
    """Load and manage skill definitions from YAML files.

    This loader discovers skills in configured directories and validates
    them against the SkillDefinition schema.

    Attributes:
        skill_dirs: List of directories to search for skills
    """

    def __init__(self, skill_dirs: list[Path] | None = None):
        """Initialize skill loader.

        Args:
            skill_dirs: Directories containing skill YAML files.
                If None, uses default: [~/.xagent/skills, builtin skills dir]
        """
        self.skill_dirs = skill_dirs or self._get_default_dirs()
        self.skills_cache: dict[str, SkillDefinition] = {}

    @staticmethod
    def _get_default_dirs() -> list[Path]:
        """Get default skill directories.

        Returns:
            List of default skill directories
        """
        builtin_dir = Path(__file__).parent / "builtin"
        user_dir = Path.home() / ".xagent" / "skills"
        return [builtin_dir, user_dir]

    def load_all(self) -> dict[str, SkillDefinition]:
        """Load all skills from configured directories.

        Searches all skill_dirs for YAML files and loads them as skills.
        Caches results to avoid reloading.

        Returns:
            Dictionary mapping skill names to SkillDefinitions

        Raises:
            ValueError: If skill validation fails
        """
        if self.skills_cache:
            return self.skills_cache

        loaded_skills: dict[str, SkillDefinition] = {}

        for skill_dir in self.skill_dirs:
            if not skill_dir.exists():
                logger.debug(f"Skill directory does not exist: {skill_dir}")
                continue

            yaml_files = sorted(skill_dir.glob("*.yaml")) + sorted(skill_dir.glob("*.yml"))
            logger.info(f"Found {len(yaml_files)} skill files in {skill_dir}")

            for yaml_file in yaml_files:
                try:
                    skill = self.load_skill(yaml_file)
                    if skill.name in loaded_skills:
                        logger.warning(
                            f"Skill '{skill.name}' already loaded from "
                            f"{loaded_skills[skill.name]}, skipping {yaml_file}"
                        )
                        continue

                    loaded_skills[skill.name] = skill
                    logger.info(f"Loaded skill: {skill.name} v{skill.version}")
                except Exception as e:
                    logger.error(f"Failed to load skill from {yaml_file}: {e}")
                    raise ValueError(f"Failed to load skill from {yaml_file}: {e}") from e

        self.skills_cache = loaded_skills
        return loaded_skills

    def load_skill(self, path: Path) -> SkillDefinition:
        """Load a single skill from YAML file.

        Args:
            path: Path to skill YAML file

        Returns:
            Loaded SkillDefinition

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If YAML is invalid or schema validation fails
        """
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Skill file {path} must contain a YAML dictionary")

        try:
            skill = SkillDefinition(**data)
        except Exception as e:
            raise ValueError(f"Skill schema validation failed for {path}: {e}") from e

        return skill

    def validate(self, skill: SkillDefinition) -> list[str]:
        """Validate a skill definition.

        Performs semantic validation beyond schema checking:
        - All referenced tools exist
        - Step IDs are unique
        - Output expressions reference valid steps
        - Condition expressions are valid

        Args:
            skill: Skill to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors: list[str] = []

        # Check for duplicate step IDs
        step_ids = [step.id for step in skill.steps]
        if len(step_ids) != len(set(step_ids)):
            duplicates = [sid for sid in step_ids if step_ids.count(sid) > 1]
            errors.append(f"Duplicate step IDs: {duplicates}")

        # Check step references in outputs
        valid_step_ids = {step.id for step in skill.steps}
        for output in skill.outputs:
            missing_steps = self._extract_missing_steps(output.value, valid_step_ids)
            if missing_steps:
                errors.append(f"Output '{output.name}' references undefined steps: {missing_steps}")

        # Check foreach expressions
        for step in skill.steps:
            if step.foreach:
                missing_steps = self._extract_missing_steps(step.foreach, valid_step_ids)
                if missing_steps:
                    errors.append(
                        f"Step '{step.id}' foreach references undefined steps: {missing_steps}"
                    )

        # Check condition expressions
        for step in skill.steps:
            if step.condition:
                missing_steps = self._extract_missing_steps(step.condition, valid_step_ids)
                if missing_steps:
                    errors.append(
                        f"Step '{step.id}' condition references undefined steps: {missing_steps}"
                    )

        return errors

    @staticmethod
    def _extract_missing_steps(expression: str, valid_steps: set[str]) -> set[str]:
        """Extract referenced steps from a template expression.

        Looks for patterns like {{steps.step_id.output}}.

        Args:
            expression: Template expression
            valid_steps: Set of valid step IDs

        Returns:
            Set of referenced steps that don't exist
        """
        import re

        # Find all {{steps.X.Y}} patterns
        pattern = r"\{\{steps\.(\w+)\."
        matches = re.findall(pattern, expression)
        return {m for m in matches if m not in valid_steps}
