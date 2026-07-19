"""
技能加载器 - 动态加载和管理技能

X-Agent 唯一技能运行时（P1-11 架构决策，见 SKILLS_SYSTEM_README.md）。
默认技能目录指向项目根目录的真实 ``skills/`` 与 ``custom-skills/``，
目录约定::

    skills/<skill-name>/
        SKILL.md        # 技能说明（人类可读）
        main.py         # 可执行实现，必须导出 SkillImplementation 类
        （或 skill.py，与 custom-skills/README.md 约定兼容）

加载结果显式可追溯：``load_report`` 记录每个技能的成功/失败原因，
禁止静默跳过。
"""

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .skill_base import Skill
from .skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

# 技能实现文件名候选（按优先级）
SKILL_ENTRYPOINT_CANDIDATES = ("main.py", "skill.py")
# 技能实现类名约定
SKILL_IMPLEMENTATION_CLASS = "SkillImplementation"


def get_default_skills_dirs() -> List[Path]:
    """返回默认技能目录列表（项目根目录的 skills/ 与 custom-skills/）。

    仅返回实际存在的目录。路径相对本文件解析，
    不受进程工作目录影响。
    """
    project_root = Path(__file__).resolve().parents[4]
    candidates = [project_root / "skills", project_root / "custom-skills"]
    return [p for p in candidates if p.is_dir()]


class SkillLoader:
    """技能加载器 - 从文件系统动态加载技能"""

    def __init__(
        self,
        skills_dir: Optional[str | Path | List[str | Path]] = None,
        registry: Optional[SkillRegistry] = None,
    ):
        """
        初始化技能加载器

        Args:
            skills_dir: 技能目录路径（单个或多个）。缺省时指向项目根目录的
                        ``skills/`` 与 ``custom-skills/``（存在的才生效）。
            registry: 技能注册表实例
        """
        if skills_dir is None:
            dirs: List[Path] = get_default_skills_dirs()
        elif isinstance(skills_dir, (str, Path)):
            dirs = [Path(skills_dir)]
        else:
            dirs = [Path(d) for d in skills_dir]

        self.skills_dirs: List[Path] = dirs
        # 兼容旧代码读取 loader.skills_dir 的场景（取第一个目录）
        self.skills_dir: Optional[Path] = dirs[0] if dirs else None
        self.registry = registry or SkillRegistry()
        self._loaded_skills: Dict[str, Skill] = {}
        # 加载报告：{skill_name: {"status": "loaded"|"failed", "error": str|None, "path": str|None}}
        self._load_report: Dict[str, Dict[str, object]] = {}

    async def load_skill(self, skill_name: str) -> Optional[Skill]:
        """
        加载单个技能

        Args:
            skill_name: 技能名称（技能目录名）

        Returns:
            Skill: 加载的技能实例，如果加载失败则返回None
            （失败原因记录在 load_report 中，不会静默）
        """
        try:
            # 尝试从已加载的技能中获取
            if skill_name in self._loaded_skills:
                return self._loaded_skills[skill_name]

            # 尝试从注册表中获取
            skill = self.registry.get(skill_name)
            if skill:
                self._loaded_skills[skill_name] = skill
                self._record_load(skill_name, "loaded", path=None, note="from_registry")
                return skill

            # 在技能目录中查找并加载
            skill_path = self._find_skill_dir(skill_name)
            if skill_path is not None:
                skill = await self._load_from_directory(skill_name, skill_path)
                if skill:
                    try:
                        self.registry.register(skill)
                    except ValueError:
                        # 同名技能已注册（例如多目录同名），以首个为准并显式记录
                        self._record_load(
                            skill_name, "failed",
                            error=f"duplicate skill name '{skill_name}', first one wins",
                            path=str(skill_path),
                        )
                        return self.registry.get(skill_name)
                    self._loaded_skills[skill_name] = skill
                    self._record_load(skill_name, "loaded", path=str(skill_path))
                    return skill
                # _load_from_directory 已记录失败原因
                return None

            error = f"skill directory not found in {[str(d) for d in self.skills_dirs]}"
            logger.warning(f"Failed to load skill '{skill_name}': {error}")
            self._record_load(skill_name, "failed", error=error)
            return None

        except Exception as e:
            logger.error(f"Error loading skill '{skill_name}': {e}")
            self._record_load(skill_name, "failed", error=str(e))
            return None

    async def load_all_skills(self) -> List[Skill]:
        """
        加载所有技能目录下的技能

        Returns:
            List[Skill]: 加载的技能列表。
            每个技能的成败可在 ``load_report`` 中追溯（不静默跳过）。
        """
        skills: List[Skill] = []

        if not self.skills_dirs:
            logger.warning("No skills directories configured or none exist")
            return skills

        for base in self.skills_dirs:
            if not base.exists():
                logger.warning(f"Skills directory does not exist: {base}")
                continue
            try:
                for skill_dir in sorted(base.iterdir()):
                    if skill_dir.is_dir() and not skill_dir.name.startswith(("_", ".")):
                        skill = await self.load_skill(skill_dir.name)
                        if skill:
                            skills.append(skill)
            except Exception as e:
                logger.error(f"Error scanning skills directory '{base}': {e}")

        return skills

    @property
    def load_report(self) -> Dict[str, Dict[str, object]]:
        """每个技能的加载结果（status/error/path），供审计与排障。"""
        return dict(self._load_report)

    def _find_skill_dir(self, skill_name: str) -> Optional[Path]:
        """在所有技能目录中查找技能子目录"""
        for base in self.skills_dirs:
            skill_path = base / skill_name
            if skill_path.exists() and skill_path.is_dir():
                return skill_path
        return None

    def _find_entrypoint(self, skill_path: Path) -> Optional[Path]:
        """按约定查找技能实现文件（main.py 优先，其次 skill.py）"""
        for candidate in SKILL_ENTRYPOINT_CANDIDATES:
            entry = skill_path / candidate
            if entry.exists():
                return entry
        return None

    async def _load_from_directory(self, skill_name: str, skill_path: Path) -> Optional[Skill]:
        """
        从目录加载技能

        Args:
            skill_name: 技能名称
            skill_path: 技能目录路径

        Returns:
            Skill: 加载的技能实例，如果加载失败则返回None（原因写入 load_report）
        """
        try:
            main_file = self._find_entrypoint(skill_path)
            if main_file is None:
                error = (
                    f"no executable entrypoint found in {skill_path} "
                    f"(expected one of {SKILL_ENTRYPOINT_CANDIDATES})"
                )
                logger.warning(f"Skill '{skill_name}': {error}")
                self._record_load(skill_name, "failed", error=error, path=str(skill_path))
                return None

            # 动态导入模块（模块名带命名空间，避免与业务模块/其他技能冲突）
            module_name = f"xagent_user_skills.{skill_name.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, main_file)
            if not spec or not spec.loader:
                error = f"failed to create module spec for {main_file}"
                logger.error(f"Skill '{skill_name}': {error}")
                self._record_load(skill_name, "failed", error=error, path=str(skill_path))
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(module_name, None)
                raise

            # 查找 SkillImplementation 类
            if not hasattr(module, SKILL_IMPLEMENTATION_CLASS):
                error = f"no {SKILL_IMPLEMENTATION_CLASS} class found in {main_file}"
                logger.error(f"Skill '{skill_name}': {error}")
                self._record_load(skill_name, "failed", error=error, path=str(skill_path))
                return None

            skill_class = getattr(module, SKILL_IMPLEMENTATION_CLASS)
            skill = skill_class()

            if not isinstance(skill, Skill):
                error = (
                    f"{SKILL_IMPLEMENTATION_CLASS} in {main_file} must subclass "
                    f"backend.app.core.skills.Skill"
                )
                logger.error(f"Skill '{skill_name}': {error}")
                self._record_load(skill_name, "failed", error=error, path=str(skill_path))
                return None

            # 初始化技能
            await skill.initialize()

            return skill

        except Exception as e:
            logger.error(f"Error loading skill from directory '{skill_path}': {e}")
            self._record_load(skill_name, "failed", error=str(e), path=str(skill_path))
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
                module_name = f"xagent_user_skills.{skill_name.replace('-', '_')}"
                sys.modules.pop(module_name, None)
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

    def _record_load(
        self,
        skill_name: str,
        status: str,
        error: Optional[str] = None,
        path: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """记录加载结果（显式可追溯，禁止静默跳过）"""
        entry: Dict[str, object] = {"status": status, "error": error, "path": path}
        if note:
            entry["note"] = note
        self._load_report[skill_name] = entry
