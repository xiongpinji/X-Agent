"""技能自沉淀闭环（Skill Self-Distillation）模块。

任务后自动生成/改进 skill：从执行轨迹提取可复用模式 → 生成 SKILL.md + main.py → 验证入库。
P2-12: promote 落盘 custom-skills/ 并热加载注册（promotion.py + sedimentation.mount_promoted_skills）。
"""

from backend.app.core.skill_distillation.curator import SkillCurator
from backend.app.core.skill_distillation.generator import SkillGenerator
from backend.app.core.skill_distillation.harvester import PatternHarvester
from backend.app.core.skill_distillation.promotion import (
    persist_improved_skill,
    sanitize_skill_name,
    write_skill_package,
)
from backend.app.core.skill_distillation.sedimentation import (
    SkillSedimentationEngine,
    get_sedimentation_engine,
    reset_sedimentation_engine,
)

__all__ = [
    "PatternHarvester",
    "SkillCurator",
    "SkillGenerator",
    "SkillSedimentationEngine",
    "get_sedimentation_engine",
    "persist_improved_skill",
    "reset_sedimentation_engine",
    "sanitize_skill_name",
    "write_skill_package",
]
