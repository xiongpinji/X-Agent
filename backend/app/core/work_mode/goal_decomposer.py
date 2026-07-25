"""Work Mode 目标分解器 — 将高层目标拆分为可执行里程碑。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MilestoneSpec:
    """里程碑规格（分解器输出）。"""

    title: str = ""
    description: str = ""
    estimated_minutes: int = 30
    dependencies: list[int] = field(default_factory=list)  # 依赖的里程碑索引
    deliverable: str = ""  # 预期产出描述


class GoalDecomposer:
    """目标分解器 — 使用 LLM 将高层目标拆分为里程碑序列。

    Args:
        llm_router: LLMRouter 实例（None 时使用启发式分解）
    """

    def __init__(self, llm_router: Any | None = None) -> None:
        self._router = llm_router

    async def decompose(
        self,
        goal: str,
        max_milestones: int = 6,
        context: dict[str, Any] | None = None,
    ) -> list[MilestoneSpec]:
        """将目标分解为里程碑列表。

        Args:
            goal: 高层目标描述
            max_milestones: 最大里程碑数
            context: 额外上下文

        Returns:
            里程碑规格列表（按执行顺序）
        """
        if self._router is not None:
            try:
                return await self._llm_decompose(goal, max_milestones, context or {})
            except Exception as exc:
                logger.warning("LLM decompose failed, using heuristic: %s", exc)

        return self._heuristic_decompose(goal, max_milestones)

    async def _llm_decompose(
        self, goal: str, max_milestones: int, context: dict[str, Any]
    ) -> list[MilestoneSpec]:
        """LLM 辅助分解。"""
        prompt = (
            f"将以下工作目标分解为最多 {max_milestones} 个可执行的里程碑。\n"
            f"每个里程碑应该是 30-120 分钟可完成的独立工作单元。\n\n"
            f"目标: {goal}\n\n"
            f"以 JSON 数组格式返回，每个元素包含:\n"
            f'- "title": 里程碑标题（简短）\n'
            f'- "description": 具体工作内容\n'
            f'- "estimated_minutes": 预估耗时（分钟）\n'
            f'- "deliverable": 预期产出\n'
            f'- "dependencies": 依赖的其他里程碑索引数组（0-based）\n\n'
            f"只返回 JSON 数组。"
        )

        response = await self._router.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=[],
        )
        content = (response.content or "").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0]

        items = json.loads(content)
        milestones = []
        for item in items[:max_milestones]:
            milestones.append(MilestoneSpec(
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                estimated_minutes=int(item.get("estimated_minutes", 30)),
                deliverable=str(item.get("deliverable", "")),
                dependencies=list(item.get("dependencies", [])),
            ))
        return milestones

    def _heuristic_decompose(self, goal: str, max_milestones: int) -> list[MilestoneSpec]:
        """启发式分解：按关键词/句子拆分。"""
        # 尝试按分号或句号拆分
        parts = [p.strip() for p in goal.replace("；", ";").replace("。", ";").split(";") if p.strip()]
        if len(parts) < 2:
            parts = [p.strip() for p in goal.split("，") if p.strip()]
        if len(parts) < 2:
            # 单任务 → 生成 研究/实现/验证 三阶段
            phases = [
                MilestoneSpec(title="研究与分析", description=f"分析目标: {goal}", estimated_minutes=20, deliverable="分析报告"),
                MilestoneSpec(title="实现与执行", description=f"执行: {goal}", estimated_minutes=60, dependencies=[0], deliverable="实现产出"),
                MilestoneSpec(title="验证与总结", description=f"验证目标达成: {goal}", estimated_minutes=20, dependencies=[1], deliverable="验证报告"),
            ]
            return phases[:max_milestones]

        milestones = []
        for i, part in enumerate(parts[:max_milestones]):
            deps = [i - 1] if i > 0 else []
            milestones.append(MilestoneSpec(
                title=f"步骤 {i + 1}: {part[:30]}",
                description=part,
                estimated_minutes=30,
                dependencies=deps,
                deliverable=f"完成: {part[:50]}",
            ))
        return milestones
