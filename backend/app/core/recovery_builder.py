"""
代理恢复框架构建模块 - 从agent.py中提取的恢复逻辑。

这个模块专门处理恢复框架的构建，降低agent.py的复杂度。
"""

from __future__ import annotations

from typing import Any

from backend.app.core.contracts import RecoveryFrame


class RecoveryFrameBuilder:
    """恢复框架构建器 - 处理所有恢复框架相关的逻辑。"""

    @staticmethod
    def build_initial_recovery(tool_name: str | None = None) -> RecoveryFrame:
        """
        构建初始恢复框架。

        Args:
            tool_name: 工具名称

        Returns:
            RecoveryFrame: 初始恢复框架
        """
        return RecoveryFrame(
            branch="continue",
            retryable=False,
            confidence=0.5,
            tool_name=tool_name,
            follow_up=["continue planning", "execute selected tool"],
            status_detail="initial agent recovery frame",
            remediation="continue with plan execution",
        )

    @staticmethod
    def merge_recovery_from_repair(
        recovery: RecoveryFrame,
        repair_suggestion: object,
        retry_tool: str,
    ) -> RecoveryFrame:
        """
        从修复建议合并恢复框架。

        Args:
            recovery: 现有恢复框架
            repair_suggestion: 修复建议对象
            retry_tool: 重试工具名称

        Returns:
            RecoveryFrame: 合并后的恢复框架
        """
        follow_up = list(getattr(repair_suggestion, "follow_up", []) or [])
        recovery.tool_name = retry_tool
        recovery.retryable = True
        recovery.confidence = max(
            float(recovery.confidence or 0.5),
            float(getattr(repair_suggestion, "confidence", 0.5) or 0.5),
        )
        recovery.follow_up = list(dict.fromkeys((recovery.follow_up or []) + follow_up))
        recovery.remediation = (
            str(getattr(repair_suggestion, "reason", None) or recovery.remediation or "")
            or recovery.remediation
        )
        recovery.status_detail = f"retry scheduled for {retry_tool}"
        return recovery

    @staticmethod
    def build_final_recovery_frame(
        execution_summary: dict[str, object],
        recovery_branch: str,
    ) -> RecoveryFrame:
        """
        构建最终恢复框架。

        这个方法处理复杂的执行摘要解析和恢复分支确定逻辑。

        Args:
            execution_summary: 执行摘要字典
            recovery_branch: 恢复分支

        Returns:
            RecoveryFrame: 最终恢复框架
        """
        # 提取状态信息
        repair_summary = RecoveryFrameBuilder._extract_dict(
            execution_summary, "repair_summary"
        )
        approval_state = RecoveryFrameBuilder._extract_dict(
            execution_summary, "approval_state"
        )
        workflow_state = RecoveryFrameBuilder._extract_dict(
            execution_summary, "workflow_state"
        )
        browser_state = RecoveryFrameBuilder._extract_dict(
            execution_summary, "browser_state"
        )
        desktop_state = RecoveryFrameBuilder._extract_dict(
            execution_summary, "desktop_state"
        )

        # 确定恢复分支
        recovery_branch = RecoveryFrameBuilder._determine_recovery_branch(
            recovery_branch, workflow_state, approval_state, browser_state, desktop_state
        )

        # 构建恢复框架
        return RecoveryFrame(
            branch=recovery_branch,
            reason=RecoveryFrameBuilder._extract_string(execution_summary, "reason"),
            next_action=RecoveryFrameBuilder._extract_string(
                execution_summary, "next_action"
            ),
            next_actions=RecoveryFrameBuilder._extract_list(
                execution_summary, "next_actions"
            ),
            recovery_plan=RecoveryFrameBuilder._extract_dict(
                execution_summary, "recovery_plan"
            ),
            status=RecoveryFrameBuilder._extract_string(execution_summary, "status"),
            pending_count=RecoveryFrameBuilder._extract_int(
                approval_state, "pending_count"
            ),
            latest_decision=RecoveryFrameBuilder._extract_string(
                approval_state, "approval_status"
            ),
            resource_type="workflow" if execution_summary.get("workflow_state") else None,
            resource_id=RecoveryFrameBuilder._extract_string(
                workflow_state, "workflow_id"
            ),
            retryable=bool(
                execution_summary.get("retryable_failures", 0)
                or (
                    repair_summary.get("retry_count", 0)
                    if isinstance(repair_summary, dict)
                    else 0
                )
            ),
            confidence=RecoveryFrameBuilder._extract_confidence(execution_summary),
            tool_name=RecoveryFrameBuilder._extract_tool_name(execution_summary),
            follow_up=RecoveryFrameBuilder._extract_list(repair_summary, "follow_up"),
            status_detail=RecoveryFrameBuilder._extract_status_detail(
                execution_summary, recovery_branch
            ),
            remediation=RecoveryFrameBuilder._extract_remediation(execution_summary),
        )

    @staticmethod
    def _determine_recovery_branch(
        current_branch: str,
        workflow_state: dict[str, object],
        approval_state: dict[str, object],
        browser_state: dict[str, object],
        desktop_state: dict[str, object],
    ) -> str:
        """
        根据各种状态确定恢复分支。

        Args:
            current_branch: 当前分支
            workflow_state: 工作流状态
            approval_state: 审批状态
            browser_state: 浏览器状态
            desktop_state: 桌面状态

        Returns:
            str: 确定的恢复分支
        """
        if workflow_state.get("workflow_status") == "needs_approval":
            return "approval_wait"
        if approval_state.get("pending_count"):
            return "approval_wait"
        if (
            workflow_state.get("workflow_node_type") == "browser"
            or browser_state.get("active_count", 0)
        ):
            return "browser_observe"
        if (
            workflow_state.get("workflow_node_type") == "desktop"
            or desktop_state.get("active_count", 0)
        ):
            return "desktop_observe"
        return current_branch

    @staticmethod
    def _extract_dict(data: dict[str, object], key: str) -> dict[str, object]:
        """安全地从字典中提取字典值。"""
        value = data.get(key, {})
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _extract_string(data: dict[str, object], key: str) -> str | None:
        """安全地从字典中提取字符串值。"""
        value = data.get(key)
        return str(value) if value else None

    @staticmethod
    def _extract_int(data: dict[str, object], key: str, default: int = 0) -> int:
        """安全地从字典中提取整数值。"""
        value = data.get(key, default)
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _extract_list(data: dict[str, object], key: str) -> list[str]:
        """安全地从字典中提取列表值。"""
        value = data.get(key, [])
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    @staticmethod
    def _extract_confidence(execution_summary: dict[str, object]) -> float:
        """从执行摘要中提取置信度。"""
        tool_decision = execution_summary.get("orchestrator_tool_decision", {})
        if isinstance(tool_decision, dict):
            try:
                return float(tool_decision.get("confidence", 0.5) or 0.5)
            except (ValueError, TypeError):
                return 0.5
        return 0.5

    @staticmethod
    def _extract_tool_name(execution_summary: dict[str, object]) -> str | None:
        """从执行摘要中提取工具名称。"""
        tool_decision = execution_summary.get("orchestrator_tool_decision", {})
        if isinstance(tool_decision, dict):
            tool_name = tool_decision.get("preferred_tool")
            return str(tool_name) if tool_name else None
        return None

    @staticmethod
    def _extract_status_detail(
        execution_summary: dict[str, object], recovery_branch: str
    ) -> str:
        """从执行摘要中提取状态详情。"""
        branch_note = execution_summary.get("branch_note")
        status = execution_summary.get("status")
        if branch_note:
            return str(branch_note)
        if status:
            return str(status)
        return recovery_branch

    @staticmethod
    def _extract_remediation(execution_summary: dict[str, object]) -> str:
        """从执行摘要中提取补救措施。"""
        next_action = execution_summary.get("next_action")
        reason = execution_summary.get("reason")
        if next_action:
            return str(next_action)
        if reason:
            return str(reason)
        return "continue execution"
