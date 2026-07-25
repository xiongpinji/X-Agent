"""
技能注册表 - 管理已注册的技能
"""


from .skill_base import Skill, SkillMetadata


class SkillRegistry:
    """技能注册表 - 存储和管理所有已注册的技能"""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._metadata: dict[str, SkillMetadata] = {}

    def register(self, skill: Skill) -> None:
        """
        注册技能

        Args:
            skill: 要注册的技能实例

        Raises:
            ValueError: 如果技能已存在或元数据无效
        """
        metadata = skill.metadata

        if metadata.name in self._skills:
            raise ValueError(f"Skill '{metadata.name}' is already registered")

        if not metadata.name or not metadata.version:
            raise ValueError("Skill metadata must have name and version")

        self._skills[metadata.name] = skill
        self._metadata[metadata.name] = metadata

    def unregister(self, skill_name: str) -> bool:
        """
        注销技能

        Args:
            skill_name: 技能名称

        Returns:
            bool: 是否成功注销
        """
        if skill_name in self._skills:
            del self._skills[skill_name]
            del self._metadata[skill_name]
            return True
        return False

    def get(self, skill_name: str) -> Skill | None:
        """
        获取技能

        Args:
            skill_name: 技能名称

        Returns:
            Skill: 技能实例，如果不存在则返回None
        """
        return self._skills.get(skill_name)

    def get_metadata(self, skill_name: str) -> SkillMetadata | None:
        """
        获取技能元数据

        Args:
            skill_name: 技能名称

        Returns:
            SkillMetadata: 技能元数据，如果不存在则返回None
        """
        return self._metadata.get(skill_name)

    def list_skills(self) -> list[str]:
        """
        列出所有已注册的技能

        Returns:
            List[str]: 技能名称列表
        """
        return list(self._skills.keys())

    def list_metadata(self) -> list[SkillMetadata]:
        """
        列出所有技能的元数据

        Returns:
            List[SkillMetadata]: 技能元数据列表
        """
        return list(self._metadata.values())

    def exists(self, skill_name: str) -> bool:
        """
        检查技能是否存在

        Args:
            skill_name: 技能名称

        Returns:
            bool: 技能是否存在
        """
        return skill_name in self._skills

    def get_by_capability(self, capability: str) -> list[Skill]:
        """
        根据能力获取技能

        Args:
            capability: 能力名称

        Returns:
            List[Skill]: 具有该能力的技能列表
        """
        result = []
        for skill in self._skills.values():
            if capability in skill.get_capabilities():
                result.append(skill)
        return result

    def get_by_tag(self, tag: str) -> list[Skill]:
        """
        根据标签获取技能

        Args:
            tag: 标签名称

        Returns:
            List[Skill]: 具有该标签的技能列表
        """
        result = []
        for skill in self._skills.values():
            if tag in skill.metadata.tags:
                result.append(skill)
        return result

    def validate_dependencies(self, skill_name: str) -> bool:
        """
        验证技能的依赖是否都已注册

        Args:
            skill_name: 技能名称

        Returns:
            bool: 所有依赖是否都已注册
        """
        skill = self.get(skill_name)
        if not skill:
            return False

        return all(self.exists(dep) for dep in skill.get_dependencies())

    def clear(self) -> None:
        """清空所有已注册的技能"""
        self._skills.clear()
        self._metadata.clear()
