"""
技能系统模块 - X-Agent 唯一技能运行时（P1-11 架构决策）

- Skill/SkillMetadata/SkillContext/SkillResult: 技能契约
- SkillLoader: 目录扫描加载器，默认指向项目根 skills/ 与 custom-skills/
- SkillRegistry: 技能注册表

历史实现 backend/app/core/skills_*（扁平栈）与 skill_system_v2 为 legacy，
仅保留兼容，不再作为运行时入口。见 SKILLS_SYSTEM_README.md。
"""

from .skill_base import Skill, SkillMetadata, SkillContext, SkillResult
from .skill_loader import (
    SkillLoader,
    get_default_skills_dirs,
    SKILL_ENTRYPOINT_CANDIDATES,
    SKILL_IMPLEMENTATION_CLASS,
)
from .skill_registry import SkillRegistry

__all__ = [
    "Skill",
    "SkillMetadata",
    "SkillContext",
    "SkillResult",
    "SkillLoader",
    "SkillRegistry",
    "get_default_skills_dirs",
    "SKILL_ENTRYPOINT_CANDIDATES",
    "SKILL_IMPLEMENTATION_CLASS",
]
