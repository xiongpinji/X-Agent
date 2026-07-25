"""
执行上下文初始化模块 - 从agent.py中提取的上下文初始化逻辑。

这个模块专门处理执行上下文的初始化和准备，降低agent.py的复杂度。
"""

from __future__ import annotations

import json

from backend.app.core.code_index import code_index
from backend.app.core.contracts import ExecutionFrame, RunContext, TaskFrame
from backend.app.core.test_mapper import test_mapper


class ExecutionContextInitializer:
    """执行上下文初始化器 - 处理所有上下文初始化相关的逻辑。"""

    @staticmethod
    def compress_context(extra_context: dict[str, object]) -> dict[str, object]:
        """
        压缩上下文以减少令牌使用。

        Args:
            extra_context: 额外上下文字典

        Returns:
            dict: 压缩后的上下文字典
        """
        keys = [
            "root",
            "path",
            "target_path",
            "file",
            "pattern",
            "limit",
            "read_limit",
            "replace_all",
            "old_text",
            "new_text",
            "replacement",
            "content",
            "goal",
            "objective",
            "patches",
            "resume_trace_id",
            "skip_observe_on_resume",
        ]
        compact: dict[str, object] = {}

        # 从顶级提取关键字段
        for key in keys:
            if key in extra_context:
                compact[key] = extra_context[key]

        # 从嵌套的context字段提取
        if "context" in extra_context and isinstance(extra_context["context"], dict):
            nested = extra_context["context"]
            for key in keys:
                if key in nested and key not in compact:
                    compact[key] = nested[key]

        # 规范化路径
        if compact.get("path") and not compact.get("target_path"):
            compact["target_path"] = compact["path"]

        # 提取任务焦点
        if compact.get("goal") or compact.get("objective"):
            compact["task_focus"] = str(
                compact.get("goal") or compact.get("objective")
            )[:240]

        # 处理补丁预览
        if compact.get("patches") and isinstance(compact["patches"], list):
            patch_preview = []
            for patch in compact["patches"][:5]:
                if isinstance(patch, dict):
                    patch_preview.append(
                        {
                            "path": patch.get("path"),
                            "replace_all": bool(patch.get("replace_all", False)),
                            "has_old_text": bool(patch.get("old_text")),
                            "has_new_text": bool(patch.get("new_text")),
                        }
                    )
            compact["patch_preview"] = patch_preview
            compact["patch_count"] = len(compact["patches"])

        return compact

    @staticmethod
    def build_code_index_context(
        compact_context: dict[str, object],
        task: str,
    ) -> dict[str, object]:
        """
        构建代码索引上下文。

        Args:
            compact_context: 压缩后的上下文
            task: 任务描述

        Returns:
            dict: 代码索引上下文
        """
        root = str(compact_context.get("root", "."))
        index_limit = int(compact_context.get("index_limit", 2000))

        indexed_repo = code_index.index(root, limit=index_limit)

        return {
            "count": indexed_repo.get("count", 0),
            "related_files": code_index.related_files(task, limit=8),
            "impact_hints": code_index.impact_hints(
                str(
                    compact_context.get("path")
                    or compact_context.get("target_path")
                    or ""
                ),
                limit=8,
            ),
            "test_files": code_index.test_files_for(task, limit=8),
        }

    @staticmethod
    def build_test_mapping_context(task: str) -> dict[str, object]:
        """
        构建测试映射上下文。

        Args:
            task: 任务描述

        Returns:
            dict: 测试映射上下文
        """
        test_mapping = test_mapper.map(task, limit=6)
        return {
            "related_files": test_mapping.related_files,
            "test_files": test_mapping.test_files,
            "impact_hints": test_mapping.impact_hints,
            "dependency_hints": test_mapping.dependency_hints,
            "recommended_commands": test_mapping.recommended_commands,
        }

    @staticmethod
    def derive_goal(task: str, extra_context: dict[str, object]) -> str:
        """
        从任务和上下文推导目标。

        Args:
            task: 任务描述
            extra_context: 额外上下文字典

        Returns:
            str: 推导出的目标字符串
        """
        # 检查显式提供的目标
        prompt = str(extra_context.get("goal") or extra_context.get("objective") or "")
        if prompt.strip():
            return prompt.strip()

        # 从任务的第一行提取
        text = task.strip().splitlines()[0] if task.strip() else ""

        # 截断长文本
        if len(text) > 240:
            text = text[:240]

        # 检查关键词
        action_keywords = [
            "fix",
            "patch",
            "edit",
            "write",
            "implement",
            "refactor",
            "update",
        ]
        if any(token in text.lower() for token in action_keywords):
            return text

        # 返回文本或默认值
        return text if text else "complete the task"

    @staticmethod
    def decompose_task(task: str, extra_context: dict[str, object]) -> list[str]:
        """
        将任务分解为子任务。

        Args:
            task: 任务描述
            extra_context: 额外上下文字典

        Returns:
            list: 子任务列表
        """
        text = f"{task}\n{json.dumps(extra_context, ensure_ascii=False, default=str)}".lower()

        # 定义子任务线索
        cues = [
            ("understand request", ["analyze", "understand", "inspect", "review", "explain", "summarize"]),
            ("locate relevant files", ["find", "search", "locate", "where", "discover"]),
            ("draft implementation plan", ["plan", "design", "approach", "strategy"]),
            ("apply modification", ["modify", "edit", "patch", "fix", "update", "refactor", "implement", "change", "write"]),
            ("verify results", ["verify", "check", "validate", "test", "confirm"]),
            ("summarize completion", ["summary", "report", "wrap up", "finalize"]),
        ]

        subtasks: list[str] = []
        for label, keywords in cues:
            if any(keyword in text for keyword in keywords):
                subtasks.append(label)

        # 如果没有匹配到任何子任务，使用默认值
        if not subtasks:
            subtasks = ["understand request", "complete task", "verify output"]

        # 去重并限制数量
        return list(dict.fromkeys(subtasks[:5]))

    @staticmethod
    def build_task_frame(
        task: str,
        context: RunContext,
        compact_context: dict[str, object],
    ) -> TaskFrame:
        """
        构建任务框架。

        Args:
            task: 任务描述
            context: 运行上下文
            compact_context: 压缩后的上下文

        Returns:
            TaskFrame: 任务框架
        """
        goal = ExecutionContextInitializer.derive_goal(task, compact_context)
        description = str(compact_context.get("task_focus") or task[:500])

        return TaskFrame(
            goal=goal,
            description=description,
            risk_level=context.risk_level,
            requires_approval=bool(compact_context.get("requires_approval", False)),
            metadata={"task": task, **compact_context},
        )

    @staticmethod
    def build_execution_frame(
        context: RunContext,
        task_frame: TaskFrame,
    ) -> ExecutionFrame:
        """
        构建执行框架。

        Args:
            context: 运行上下文
            task_frame: 任务框架

        Returns:
            ExecutionFrame: 执行框架
        """
        return ExecutionFrame(
            trace_id=context.trace_id,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
            task=task_frame,
            session_id=context.session_id,
            metadata={"session_id": context.session_id} if context.session_id else {},
        )
