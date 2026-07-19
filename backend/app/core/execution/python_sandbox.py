"""
[降级标注 — 仅限可信代码, 禁止用于不可信输入] Python 代码执行沙箱

⚠ 安全警告 (P0-18): 本模块基于 AST 黑名单 + 同进程 exec 实现, 不构成任何安全
边界。属性链 / 字节码 / 内置对象图等绕过手段是公开常识, 黑名单式"安全"在
Python 下形同虚设。

- 仅限执行可信的、内部生成的代码(例如受信内部工具链)。
- 不可信输入(LLM 生成代码、用户提交代码、第三方插件代码)必须走 Docker
  隔离: ``backend.app.core.sandbox.docker_sandbox.DockerSandbox``
  或 ``backend.app.core.sandbox.python_sandbox.PythonSandbox``。

保留原因: ``ExecutionManager`` / ``OptimizedExecutionManager`` 及既有测试仍
引用本模块; 直接删除属于更大范围重构。在统一迁移到 Docker 隔离之前, 本模块
在实例化时会发出运行时警告。
"""

import ast
import asyncio
import logging
import sys
import warnings
from io import StringIO
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 每进程只发一次降级警告, 避免刷屏。
_TRUSTED_ONLY_WARNING_EMITTED = False

_TRUSTED_ONLY_MESSAGE = (
    "core.execution.python_sandbox.PythonSandbox 已降级 (P0-18): AST 黑名单"
    "不构成安全边界, 仅限可信代码, 禁止用于不可信输入。不可信代码必须走 "
    "Docker 隔离 (backend.app.core.sandbox.docker_sandbox / "
    "backend.app.core.sandbox.python_sandbox)。"
)


def _emit_trusted_only_warning() -> None:
    """发出一次性降级运行时警告 (logger + DeprecationWarning)。"""
    global _TRUSTED_ONLY_WARNING_EMITTED
    if _TRUSTED_ONLY_WARNING_EMITTED:
        return
    _TRUSTED_ONLY_WARNING_EMITTED = True
    logger.warning(_TRUSTED_ONLY_MESSAGE)
    warnings.warn(_TRUSTED_ONLY_MESSAGE, DeprecationWarning, stacklevel=3)


class PythonSandbox:
    """[仅限可信代码] Python代码执行沙箱 - 提供受限的代码执行环境。

    ⚠ P0-18 降级标注: 本类基于 AST 黑名单, 不能隔离不可信代码。
    不可信输入请使用 Docker 隔离沙箱
    (``backend.app.core.sandbox.docker_sandbox.DockerSandbox`` /
    ``backend.app.core.sandbox.python_sandbox.PythonSandbox``)。
    """

    # 禁止的操作
    FORBIDDEN_NAMES = {
        "eval",
        "exec",
        "__import__",
        "open",
        "compile",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "__builtins__",
    }

    # 禁止的模块
    FORBIDDEN_MODULES = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "urllib",
        "requests",
        "shutil",
        "tempfile",
    }

    def __init__(self, timeout: int = 30, max_output: int = 1000000):
        """
        初始化Python沙箱

        ⚠ 仅限可信代码 (P0-18); 不可信输入必须走 Docker 隔离沙箱。

        Args:
            timeout: 执行超时时间（秒）
            max_output: 最大输出大小（字节）
        """
        _emit_trusted_only_warning()
        self.timeout = timeout
        self.max_output = max_output

    async def execute(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        allowed_imports: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        执行Python代码

        Args:
            code: 要执行的Python代码
            context: 执行上下文（变量）
            allowed_imports: 允许导入的模块列表

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            # 安全检查
            if not self._is_safe(code, allowed_imports):
                return {
                    "success": False,
                    "error": "Code contains forbidden operations",
                }

            # 准备执行环境
            exec_globals = self._prepare_globals(context or {}, allowed_imports)

            # 捕获输出
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = StringIO()
            sys.stderr = StringIO()

            try:
                # 执行代码
                exec(code, exec_globals)

                output = sys.stdout.getvalue()
                error = sys.stderr.getvalue()

                # 检查输出大小
                if len(output) > self.max_output:
                    output = output[: self.max_output] + "\n... (output truncated)"

                return {
                    "success": True,
                    "output": output,
                    "error": error,
                    "globals": {
                        k: v
                        for k, v in exec_globals.items()
                        if not k.startswith("_") and k not in ("__builtins__",)
                    },
                }

            except Exception as e:
                error = sys.stderr.getvalue()
                return {
                    "success": False,
                    "error": str(e),
                    "stderr": error,
                }

            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        except Exception as e:
            logger.error(f"Error executing Python code: {e}")
            return {"success": False, "error": str(e)}

    def _is_safe(self, code: str, allowed_imports: Optional[list] = None) -> bool:
        """
        检查代码是否安全

        Args:
            code: 要检查的代码
            allowed_imports: 允许导入的模块列表

        Returns:
            bool: 代码是否安全
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        allowed_imports = allowed_imports or []

        for node in ast.walk(tree):
            # 检查禁止的名称
            if isinstance(node, ast.Name) and node.id in self.FORBIDDEN_NAMES:
                logger.warning(f"Forbidden name used: {node.id}")
                return False

            # 检查禁止的属性访问
            if isinstance(node, ast.Attribute):
                if node.attr in self.FORBIDDEN_NAMES:
                    logger.warning(f"Forbidden attribute accessed: {node.attr}")
                    return False

            # 检查导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in self.FORBIDDEN_MODULES and module_name not in allowed_imports:
                        logger.warning(f"Forbidden module imported: {module_name}")
                        return False

            if isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    if module_name in self.FORBIDDEN_MODULES and module_name not in allowed_imports:
                        logger.warning(f"Forbidden module imported: {module_name}")
                        return False

        return True

    def _prepare_globals(
        self,
        context: Dict[str, Any],
        allowed_imports: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        准备执行全局变量

        Args:
            context: 用户提供的上下文
            allowed_imports: 允许导入的模块列表

        Returns:
            Dict[str, Any]: 执行全局变量
        """
        allowed_imports = allowed_imports or []

        # 安全的导入函数：仅允许显式列入 allowed_imports 的模块在运行时导入。
        # 这比 FORBIDDEN_MODULES 黑名单更严格（白名单），且 _is_safe 已在 AST 层
        # 拦截禁用模块，此处提供运行时纵深防御。
        _real_import = __import__
        _allowed = set(allowed_imports)

        def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            base = name.split(".")[0]
            if base not in _allowed:
                raise ImportError(f"Import of '{name}' is not allowed in sandbox")
            return _real_import(name, globals, locals, fromlist, level)

        # 创建安全的全局变量
        safe_globals = {
            "__builtins__": {
                "__import__": _safe_import,
                "print": print,
                "len": len,
                "range": range,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "sum": sum,
                "min": min,
                "max": max,
                "sorted": sorted,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "abs": abs,
                "round": round,
                "pow": pow,
                "isinstance": isinstance,
                "type": type,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "KeyError": KeyError,
                "IndexError": IndexError,
            }
        }

        # 添加用户提供的上下文
        safe_globals.update(context)

        # 添加允许的模块
        for module_name in allowed_imports:
            try:
                module = __import__(module_name)
                safe_globals[module_name] = module
            except ImportError:
                logger.warning(f"Failed to import allowed module: {module_name}")

        return safe_globals
