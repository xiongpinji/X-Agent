"""从执行轨迹提取可复用模式。"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCallPattern:
    """工具调用模式。"""

    sequence: list[str]
    frequency: int = 1
    avg_duration_ms: float = 0.0
    success_rate: float = 1.0
    context_hints: list[str] = field(default_factory=list)

    @property
    def signature(self) -> str:
        return " → ".join(self.sequence)


@dataclass
class HarvestResult:
    """模式提取结果。"""

    patterns: list[ToolCallPattern] = field(default_factory=list)
    total_trajectories_analyzed: int = 0
    reusable_candidates: int = 0


class PatternHarvester:
    """从执行轨迹中提取可复用的工具调用模式。"""

    def __init__(self, min_frequency: int = 3, min_sequence_length: int = 2) -> None:
        self._min_frequency = min_frequency
        self._min_sequence_length = min_sequence_length

    def harvest(self, trajectories: list[list[dict[str, Any]]]) -> HarvestResult:
        """分析多条执行轨迹，提取重复模式。"""
        result = HarvestResult(total_trajectories_analyzed=len(trajectories))
        sequence_counter: Counter[str] = Counter()
        sequence_map: dict[str, list[str]] = {}
        sequence_durations: dict[str, list[float]] = {}
        sequence_successes: dict[str, list[bool]] = {}

        for trajectory in trajectories:
            tool_calls = [
                step.get("tool", step.get("name", ""))
                for step in trajectory
                if step.get("type") == "tool_call" or "tool" in step
            ]
            # 提取 n-gram 子序列
            for n in range(self._min_sequence_length, min(len(tool_calls) + 1, 6)):
                for i in range(len(tool_calls) - n + 1):
                    sub = tool_calls[i : i + n]
                    sig = " → ".join(sub)
                    sequence_counter[sig] += 1
                    sequence_map[sig] = sub
                    # 记录耗时和成功率
                    dur = trajectory[i].get("duration_ms", 0) if i < len(trajectory) else 0
                    sequence_durations.setdefault(sig, []).append(dur)
                    success = trajectory[i].get("success", True) if i < len(trajectory) else True
                    sequence_successes.setdefault(sig, []).append(success)

        # 筛选高频模式
        for sig, count in sequence_counter.items():
            if count >= self._min_frequency:
                durations = sequence_durations.get(sig, [0])
                successes = sequence_successes.get(sig, [True])
                pattern = ToolCallPattern(
                    sequence=sequence_map[sig],
                    frequency=count,
                    avg_duration_ms=sum(durations) / len(durations) if durations else 0,
                    success_rate=sum(1 for s in successes if s) / len(successes) if successes else 0,
                )
                result.patterns.append(pattern)

        # 按频率排序
        result.patterns.sort(key=lambda p: p.frequency, reverse=True)
        result.reusable_candidates = len(result.patterns)
        logger.info(f"模式提取完成: {result.reusable_candidates} 个候选 (共分析 {result.total_trajectories_analyzed} 条轨迹)")
        return result
