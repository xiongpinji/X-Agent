"""
技能加载器 - 动态加载和管理技能
"""

import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .skill_base import Skill
from .skill_registry import SkillRegistry

logger = logging.getLogger(__name__)


class SkillLoader:
    """技能加载器 - 从文件系统动态加载技能"""

    def __init__(self, skills_dir: Optional[str] = None, registry: Optional[SkillRegistry] = None):
        """
        初始化技能加载器

        Args:
            skills_dir: 技能目录路径
            registry: 技能注册表实例
        """
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self.registry = registry or SkillRegistry()
        self._loaded_skills: Dict[str, Skill] = {}

    async def load_skill(self, skill_name: str) -> Optional[Skill]:
        """
        加载单个技能

        Args:
            skill_name: 技能名称

        Returns:
            Skill: 加载的技能实例，如果加载失败则返回None
        """
        try:
            # 尝试从已加载的技能中获取
            if skill_name in self._loaded_skills:
                return self._loaded_skills[skill_name]

            # 尝试从注册表中获取
            skill = self.registry.get(skill_name)
            if skill:
                self._loaded_skills[skill_name] = skill
                return skill

            # 如果指定了技能目录，尝试从文件系统加载
            if self.skills_dir:
                skill_path = self.skills_dir / skill_name
                if skill_path.exists() and skill_path.is_dir():
                    skill = await self._load_from_directory(skill_name, skill_path)
                    if skill:
                        self.registry.register(skill)
                        self._loaded_skills[skill_name] = skill
                        return skill

            logger.warning(f"Failed to load skill: {skill_name}")
            return None

        except Exception as e:
            logger.error(f"Error loading skill '{skill_name}': {e}")
            return None

    async def load_all_skills(self) -> List[Skill]:
        """
        加载所有技能

        Returns:
            List[Skill]: 加载的技能列表
        """
        skills = []

        if not self.skills_dir or not self.skills_dir.exists():
            logger.warning(f"Skills directory does not exist: {self.skills_dir}")
            return skills

        try:
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
                    skill = await self.load_skill(skill_dir.name)
                    if skill:
                        skills.append(skill)
        except Exception as e:
            logger.error(f"Error loading all skills: {e}")

        return skills

    async def _load_from_directory(self, skill_name: str, skill_path: Path) -> Optional[Skill]:
        """
        从目录加载技能

        Args:
            skill_name: 技能名称
            skill_path: 技能目录路径

        Returns:
            Skill: 加载的技能实例，如果加载失败则返回None
        """
        try:
            # 查找main.py文件
            main_file = skill_path / "main.py"
            if not main_file.exists():
                logger.warning(f"No main.py found in {skill_path}")
                return None

            # 动态导入模块
            module_name = f"backend.app.core.skills.{skill_name}.main"
            spec = importlib.util.spec_from_file_location(module_name, main_file)
            if not spec or not spec.loader:
                logger.error(f"Failed to create module spec for {skill_name}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找SkillImplementation类
            if not hasattr(module, "SkillImplementation"):
                logger.error(f"No SkillImplementation class found in {skill_name}")
                return None

            skill_class = getattr(module, "SkillImplementation")
            skill = skill_class()

            # 初始化技能
            await skill.initialize()

            return skill

        except Exception as e:
            logger.error(f"Error loading skill from directory '{skill_path}': {e}")
            return None

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """
        获取已加载的技能

        Args:
            skill_name: 技能名称

        Returns:
            Skill: 技能实例，如果不存在则返回None
        """
        return self._loaded_skills.get(skill_name) or self.registry.get(skill_name)

    def list_loaded_skills(self) -> List[str]:
        """
        列出所有已加载的技能

        Returns:
            List[str]: 技能名称列表
        """
        return list(self._loaded_skills.keys())

    async def unload_skill(self, skill_name: str) -> bool:
        """
        卸载技能

        Args:
            skill_name: 技能名称

        Returns:
            bool: 是否成功卸载
        """
        try:
            if skill_name in self._loaded_skills:
                skill = self._loaded_skills[skill_name]
                await skill.cleanup()
                del self._loaded_skills[skill_name]
                self.registry.unregister(skill_name)
                return True
            return False
        except Exception as e:
            logger.error(f"Error unloading skill '{skill_name}': {e}")
            return False

    async def reload_skill(self, skill_name: str) -> Optional[Skill]:
        """
        重新加载技能

        Args:
            skill_name: 技能名称

        Returns:
            Skill: 重新加载的技能实例，如果加载失败则返回None
        """
        await self.unload_skill(skill_name)
        return await self.load_skill(skill_name)
