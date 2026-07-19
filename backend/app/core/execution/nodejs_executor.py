"""
Node.js代码执行器 - 执行Node.js代码
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class NodeJSExecutor:
    """Node.js代码执行器 - 提供Node.js代码执行能力"""

    def __init__(self, timeout: int = 30, max_output: int = 1000000):
        """
        初始化Node.js执行器

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
    ) -> Dict[str, Any]:
        """
        执行Node.js代码

        Args:
            code: 要执行的Node.js代码
            context: 执行上下文（变量）

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".js",
                delete=False,
                encoding="utf-8",
            ) as f:
                temp_file = f.name
                f.write(code)

            try:
                # 执行Node.js代码
                result = await self._run_nodejs(temp_file)
                return result

            finally:
                # 清理临时文件
                Path(temp_file).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Error executing Node.js code: {e}")
            return {"success": False, "error": str(e)}

    async def _run_nodejs(self, file_path: str) -> Dict[str, Any]:
        """
        运行Node.js文件

        Args:
            file_path: Node.js文件路径

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "node",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "success": False,
                    "error": f"Execution timeout after {self.timeout} seconds",
                }

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            # 检查输出大小
            if len(output) > self.max_output:
                output = output[: self.max_output] + "\n... (output truncated)"

            return {
                "success": process.returncode == 0,
                "output": output,
                "error": error if error else None,
                "return_code": process.returncode,
            }

        except FileNotFoundError:
            return {
                "success": False,
                "error": "Node.js is not installed or not in PATH",
            }
        except Exception as e:
            logger.error(f"Error running Node.js: {e}")
            return {"success": False, "error": str(e)}

    async def execute_with_modules(
        self,
        code: str,
        modules: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        执行Node.js代码并支持模块

        Args:
            code: 要执行的Node.js代码
            modules: 要导入的模块列表

        Returns:
            Dict[str, Any]: 执行结果
        """
        # 添加模块导入
        imports = ""
        if modules:
            for module in modules:
                imports += f"const {module} = require('{module}');\n"

        full_code = imports + "\n" + code
        return await self.execute(full_code)
