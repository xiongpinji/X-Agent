"""证据收集器 - 从执行轨迹中收集证据。"""
from __future__ import annotations

import logging
from typing import Any

from backend.app.core.evidence.contracts import (
    CompletionEvidence,
    EvidenceItem,
    EvidenceKind,
)

logger = logging.getLogger(__name__)


class EvidenceCollector:
    """从 Agent 运行轨迹中收集证据。"""

    def __init__(self, run_id: str) -> None:
        self._evidence = CompletionEvidence(run_id=run_id)

    @property
    def evidence(self) -> CompletionEvidence:
        return self._evidence

    def collect_test_result(self, output: str, passed: bool, **meta: Any) -> None:
        """收集测试结果证据。"""
        self._evidence.add_item(
            EvidenceItem(
                kind=EvidenceKind.TEST_RESULT,
                content=output,
                metadata={"passed": passed, **meta},
            )
        )
        logger.info(f"[{self._evidence.run_id}] 收集测试证据: passed={passed}")

    def collect_diff(self, diff_text: str, file_path: str = "", **meta: Any) -> None:
        """收集代码 diff 证据。"""
        self._evidence.add_item(
            EvidenceItem(
                kind=EvidenceKind.DIFF,
                content=diff_text,
                metadata={"file_path": file_path, **meta},
            )
        )

    def collect_log(self, log_content: str, level: str = "INFO", **meta: Any) -> None:
        """收集日志证据。"""
        self._evidence.add_item(
            EvidenceItem(
                kind=EvidenceKind.LOG,
                content=log_content,
                metadata={"level": level, **meta},
            )
        )

    def collect_screenshot(self, image_data: bytes, description: str = "", **meta: Any) -> None:
        """收集截图证据。"""
        self._evidence.add_item(
            EvidenceItem(
                kind=EvidenceKind.SCREENSHOT,
                content=image_data,
                metadata={"description": description, **meta},
            )
        )

    def collect_metric(self, name: str, value: float, unit: str = "", **meta: Any) -> None:
        """收集指标证据。"""
        self._evidence.add_item(
            EvidenceItem(
                kind=EvidenceKind.METRIC,
                content=f"{name}={value}{unit}",
                metadata={"name": name, "value": value, "unit": unit, **meta},
            )
        )

    def collect_from_trajectory(self, trajectory: list[dict[str, Any]]) -> None:
        """从完整执行轨迹批量提取证据。"""
        for step in trajectory:
            step_type = step.get("type", "")
            if step_type == "tool_call":
                tool_name = step.get("tool", "unknown")
                result = step.get("result", "")
                self.collect_log(
                    f"Tool: {tool_name}\nResult: {result[:500]}",
                    level="DEBUG",
                    tool=tool_name,
                )
            elif step_type == "test_execution":
                self.collect_test_result(
                    step.get("output", ""),
                    step.get("passed", False),
                )
            elif step_type == "file_change":
                self.collect_diff(
                    step.get("diff", ""),
                    file_path=step.get("path", ""),
                )

    def finalize(self) -> CompletionEvidence:
        """完成收集，返回证据包。"""
        logger.info(
            f"[{self._evidence.run_id}] 证据收集完成: {self._evidence.item_count} 条"
        )
        return self._evidence
