"""
Python代码执行沙箱 - 安全执行Python代码
"""

import ast
import asyncio
import logging
import sys
from io import StringIO
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PythonSandbox:
    """Python代码执行沙箱 - 提供安全的代码执行环境"""

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

        Args:
            timeout: 执行超时时间（秒）
            max_output: 最大输出大小（字节）
        """
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
