"""X-Agent Skills framework - declarative, composable agent task templates.

Supports both imperative skill objects (Skill base class) and declarative
YAML-based skill templates (SkillDefinition).
"""

# Existing skill system
from .skill_base import Skill, SkillContext, SkillMetadata, SkillResult
from .skill_loader import SkillLoader as LegacySkillLoader
from .skill_registry import SkillRegistry

# New declarative skill system
from .executor import SkillExecutor
from .loader import SkillLoader
from .schema import (
    SkillDefinition,
    SkillInput,
    SkillOutput,
    SkillResult as DeclarativeSkillResult,
    SkillStep,
    SkillTrigger,
    StepResult,
)

__all__ = [
    # Existing (imperative)
    "Skill",
    "SkillMetadata",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    "LegacySkillLoader",
    # New (declarative)
    "SkillDefinition",
    "SkillStep",
    "SkillTrigger",
    "SkillInput",
    "SkillOutput",
    "DeclarativeSkillResult",
    "StepResult",
    "SkillLoader",
    "SkillExecutor",
    "load_builtin_skills",
]


def load_builtin_skills(loader: SkillLoader | None = None) -> dict[str, SkillDefinition]:
    """Load all built-in skills from the builtin directory.

    Args:
        loader: SkillLoader instance. If None, creates a new one.

    Returns:
        Dictionary mapping skill names to SkillDefinitions
    """
    if loader is None:
        loader = SkillLoader()

    return loader.load_all()
