"""技能自沉淀闭环（Skill Self-Distillation）模块。

任务后自动生成/改进 skill：从执行轨迹提取可复用模式 → 生成 SKILL.md + main.py → 验证入库。
"""

from backend.app.core.skill_distillation.curator import SkillCurator
from backend.app.core.skill_distillation.generator import SkillGenerator
from backend.app.core.skill_distillation.harvester import PatternHarvester

__all__ = [
    "PatternHarvester",
    "SkillCurator",
    "SkillGenerator",
]
