"""
执行管理器 - 统一管理代码执行
"""

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from .nodejs_executor import NodeJSExecutor
from .python_sandbox import (
    PythonSandbox,  # ⚠ P0-18 降级: AST 黑名单, 仅限可信代码, 禁止用于不可信输入
)

logger = logging.getLogger(__name__)


class ExecutionManager:
    """执行管理器 - 统一管理Python和Node.js代码执行"""

    def __init__(self, timeout: int = 30):
        """
        初始化执行管理器

        Args:
            timeout: 执行超时时间（秒）
        """
        self.timeout = timeout
        self.python_sandbox = PythonSandbox(timeout=timeout)
        self.nodejs_executor = NodeJSExecutor(timeout=timeout)
        self._execution_history: dict[str, dict[str, Any]] = {}

    async def execute(
        self,
        code: str,
        language: str = "python",
        context: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        执行代码

        Args:
            code: 要执行的代码
            language: 编程语言（python或nodejs）
            context: 执行上下文
            **kwargs: 语言特定的参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        execution_id = str(uuid4())
        start_time = datetime.now()

        try:
            if language.lower() == "python":
                result = await self.python_sandbox.execute(
                    code,
                    context=context,
                    allowed_imports=kwargs.get("allowed_imports"),
                )
            elif language.lower() in ("nodejs", "node", "js"):
                result = await self.nodejs_executor.execute(code, context=context)
            else:
                result = {
                    "success": False,
                    "error": f"Unsupported language: {language}",
                }

            # 记录执行历史
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            self._execution_history[execution_id] = {
                "id": execution_id,
                "language": language,
                "code": code[:500],  # 只保存前500个字符
                "result": result,
                "execution_time": execution_time,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            }

            result["execution_id"] = execution_id
            result["execution_time"] = execution_time

            return result

        except Exception as e:
            logger.error(f"Error executing code: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution_id,
            }

    async def execute_python(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        allowed_imports: list | None = None,
    ) -> dict[str, Any]:
        """
        执行Python代码

        Args:
            code: Python代码
            context: 执行上下文
            allowed_imports: 允许导入的模块

        Returns:
            Dict[str, Any]: 执行结果
        """
        return await self.execute(
            code,
            language="python",
            context=context,
            allowed_imports=allowed_imports,
        )

    async def execute_nodejs(
        self,
        code: str,
        modules: list | None = None,
    ) -> dict[str, Any]:
        """
        执行Node.js代码

        Args:
            code: Node.js代码
            modules: 要导入的模块

        Returns:
            Dict[str, Any]: 执行结果
        """
        if modules:
            return await self.nodejs_executor.execute_with_modules(code, modules)
        return await self.execute(code, language="nodejs")

    def get_execution_history(self, execution_id: str) -> dict[str, Any] | None:
        """
        获取执行历史

        Args:
            execution_id: 执行ID

        Returns:
            Dict[str, Any]: 执行历史，如果不存在则返回None
        """
        return self._execution_history.get(execution_id)

    def list_executions(self, limit: int = 100) -> list:
        """
        列出执行历史

        Args:
            limit: 返回的最大记录数

        Returns:
            list: 执行历史列表
        """
        items = list(self._execution_history.values())
        return sorted(items, key=lambda x: x["start_time"], reverse=True)[:limit]

    def clear_history(self) -> None:
        """清空执行历史"""
        self._execution_history.clear()
