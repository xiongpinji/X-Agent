"""技能生成器 - 从模式生成 SKILL.md + main.py。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.app.core.skill_distillation.harvester import ToolCallPattern

logger = logging.getLogger(__name__)


@dataclass
class SkillDraft:
    """技能草稿。"""

    name: str
    description: str
    trigger_conditions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    parameters: list[dict[str, str]] = field(default_factory=list)
    source_pattern: str = ""
    status: str = "draft"  # draft / validated / promoted / rejected
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_skill_md(self) -> str:
        """生成 SKILL.md 内容。"""
        lines = [
            f"# {self.name}",
            "",
            f"{self.description}",
            "",
            "## 触发条件",
            "",
        ]
        for cond in self.trigger_conditions:
            lines.append(f"- {cond}")
        lines += ["", "## 执行步骤", ""]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. {step}")
        if self.parameters:
            lines += ["", "## 参数", ""]
            for p in self.parameters:
                lines.append(f"- `{p.get('name', '')}` ({p.get('type', 'str')}): {p.get('description', '')}")
        lines += ["", "---", f"*来源模式: {self.source_pattern}*", f"*生成时间: {self.created_at.isoformat()}*"]
        return "\n".join(lines)

    def to_main_py(self) -> str:
        """生成 main.py 骨架。"""
        step_comments = "\n".join(f"    # Step {i+1}: {s}" for i, s in enumerate(self.steps))
        return f'''"""自动生成的技能: {self.name}"""


async def execute(context: dict) -> dict:
    """执行技能。"""
{step_comments}
    return {{"status": "completed", "skill": "{self.name}"}}
'''

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "trigger_conditions": self.trigger_conditions,
            "steps": self.steps,
            "parameters": self.parameters,
            "source_pattern": self.source_pattern,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class SkillGenerator:
    """从工具调用模式生成技能草稿。"""

    def generate_from_pattern(self, pattern: ToolCallPattern) -> SkillDraft:
        """从单个模式生成技能草稿。"""
        name = self._derive_name(pattern)
        steps = [f"调用工具 `{tool}`" for tool in pattern.sequence]
        trigger = [
            f"当需要执行 {pattern.signature} 序列时",
            f"历史频率: {pattern.frequency} 次, 成功率: {pattern.success_rate:.0%}",
        ]

        draft = SkillDraft(
            name=name,
            description=f"自动化执行 {pattern.signature} 工具调用序列",
            trigger_conditions=trigger,
            steps=steps,
            source_pattern=pattern.signature,
        )
        logger.info(f"生成技能草稿: {name}")
        return draft

    def generate_batch(self, patterns: list[ToolCallPattern]) -> list[SkillDraft]:
        """批量生成。"""
        return [self.generate_from_pattern(p) for p in patterns]

    def _derive_name(self, pattern: ToolCallPattern) -> str:
        """从工具序列推导技能名。"""
        parts = [t.replace("_", "-") for t in pattern.sequence[:3]]
        return "-".join(parts) + "-workflow"
