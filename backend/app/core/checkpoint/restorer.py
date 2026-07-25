"""状态恢复器。"""
from __future__ import annotations

import logging
from typing import Any

from backend.app.core.checkpoint.snapshot import ExecutionSnapshot

logger = logging.getLogger(__name__)


class StateRestorer:
    """从检查点恢复执行状态。

    恢复流程：
    1. 加载最近有效检查点
    2. 验证上下文一致性（LLM 模型版本、工具可用性）
    3. 恢复 trajectory + plan + tool_calls 状态
    4. 从断点继续执行，跳过已完成步骤
    5. 合并部分结果到最终响应
    """

    def validate_context(self, snapshot: ExecutionSnapshot, current_context: dict[str, Any]) -> tuple[bool, list[str]]:
        """验证检查点上下文与当前环境的一致性。"""
        issues: list[str] = []

        # 检查模型版本
        ckpt_model = snapshot.context.get("model_version", "")
        current_model = current_context.get("model_version", "")
        if ckpt_model and current_model and ckpt_model != current_model:
            issues.append(f"模型版本不一致: checkpoint={ckpt_model}, current={current_model}")

        # 检查工具可用性
        ckpt_tools = set(snapshot.context.get("available_tools", []))
        current_tools = set(current_context.get("available_tools", []))
        if ckpt_tools and current_tools:
            missing = ckpt_tools - current_tools
            if missing:
                issues.append(f"工具不可用: {', '.join(missing)}")

        valid = len(issues) == 0
        if not valid:
            logger.warning(f"上下文验证失败: {issues}")
        return valid, issues

    def restore(self, snapshot: ExecutionSnapshot) -> dict[str, Any]:
        """从快照恢复执行状态，返回可注入 AgentLoop 的上下文。"""
        restored = {
            "run_id": snapshot.run_id,
            "resume_from_step": snapshot.step_index,
            "trajectory": snapshot.trajectory,
            "plan": snapshot.plan,
            "tool_calls": snapshot.tool_calls,
            "partial_results": snapshot.partial_results,
            "context": snapshot.context,
            "is_resumed": True,
        }
        logger.info(
            f"[{snapshot.run_id}] 状态恢复: step={snapshot.step_index}, "
            f"trajectory={len(snapshot.trajectory)} items"
        )
        return restored

    def merge_partial_results(
        self, partial: dict[str, Any], final: dict[str, Any]
    ) -> dict[str, Any]:
        """合并部分结果到最终响应。"""
        merged = {**partial, **final}
        merged["_merged_from_checkpoint"] = True
        return merged
