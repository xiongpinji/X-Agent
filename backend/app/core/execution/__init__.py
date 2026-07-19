"""
代码执行模块 - 提供安全的代码执行能力

⚠ P0-18: `python_sandbox.PythonSandbox` 为 AST 黑名单沙箱, 已降级为"仅限可信
代码, 禁止用于不可信输入"; 不可信代码必须走 Docker 隔离
(backend.app.core.sandbox.docker_sandbox / backend.app.core.sandbox.python_sandbox)。
"""

from .python_sandbox import PythonSandbox  # ⚠ P0-18 降级: 仅限可信代码, 禁止用于不可信输入
from .nodejs_executor import NodeJSExecutor
from .execution_manager import ExecutionManager

__all__ = [
    "PythonSandbox",
    "NodeJSExecutor",
    "ExecutionManager",
]
