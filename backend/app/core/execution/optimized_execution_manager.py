"""
优化的执行管理器 - 集成容器池和预热机制
"""

import logging
import asyncio
from typing import Any, Dict, Optional
from uuid import uuid4
from datetime import datetime

from .python_sandbox import PythonSandbox
from .nodejs_executor import NodeJSExecutor
from .container_pool import ContainerPool

logger = logging.getLogger(__name__)


class OptimizedExecutionManager:
    """优化的执行管理器 - 使用容器池提高性能"""

    def __init__(
        self,
        timeout: int = 30,
        pool_size: int = 10,
        warmup_enabled: bool = True,
    ):
        """
        初始化优化的执行管理器

        Args:
            timeout: 执行超时时间（秒）
            pool_size: 容器池大小
            warmup_enabled: 是否启用预热
        """
        self.timeout = timeout
        self.pool_size = pool_size
        self.warmup_enabled = warmup_enabled

        # 创建容器池
        self.python_pool = ContainerPool(
            pool_size=pool_size,
            language="python",
            warmup_enabled=warmup_enabled,
        )
        self.nodejs_pool = ContainerPool(
            pool_size=pool_size,
            language="nodejs",
            warmup_enabled=warmup_enabled,
        )

        # 创建执行器
        self.python_sandbox = PythonSandbox(timeout=timeout)
        self.nodejs_executor = NodeJSExecutor(timeout=timeout)

        # 执行历史
        self._execution_history: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self):
        """初始化执行管理器和容器池"""
        if self._initialized:
            return

        logger.info("Initializing OptimizedExecutionManager")

        # 初始化容器池
        await asyncio.gather(
            self.python_pool.initialize(),
            self.nodejs_pool.initialize(),
        )

        self._initialized = True
        logger.info("OptimizedExecutionManager initialized")

    async def execute(
        self,
        code: str,
        language: str = "python",
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        执行代码（使用容器池）

        Args:
            code: 要执行的代码
            language: 编程语言（python或nodejs）
            context: 执行上下文
            **kwargs: 语言特定的参数

        Returns:
            Dict[str, Any]: 执行结果
        """
        if not self._initialized:
            await self.initialize()

        execution_id = str(uuid4())
        start_time = datetime.now()
        container = None
        pool_hit = False

        try:
            if language.lower() == "python":
                # 从Python池获取容器
                container = await self.python_pool.acquire(timeout=self.timeout)
                if container:
                    pool_hit = True
                    logger.debug(f"Acquired Python container {container.container_id}")

                # 执行Python代码
                exec_start = datetime.now()
                result = await self.python_sandbox.execute(
                    code,
                    context=context,
                    allowed_imports=kwargs.get("allowed_imports"),
                )
                exec_time = (datetime.now() - exec_start).total_seconds()

                # 释放容器
                if container:
                    await self.python_pool.release(
                        container,
                        success=result.get("success", False),
                        execution_time=exec_time,
                    )

            elif language.lower() in ("nodejs", "node", "js"):
                # 从Node.js池获取容器
                container = await self.nodejs_pool.acquire(timeout=self.timeout)
                if container:
                    pool_hit = True
                    logger.debug(f"Acquired Node.js container {container.container_id}")

                # 执行Node.js代码
                exec_start = datetime.now()
                if kwargs.get("modules"):
                    result = await self.nodejs_executor.execute_with_modules(
                        code,
                        modules=kwargs.get("modules"),
                    )
                else:
                    result = await self.nodejs_executor.execute(code, context=context)
                exec_time = (datetime.now() - exec_start).total_seconds()

                # 释放容器
                if container:
                    await self.nodejs_pool.release(
                        container,
                        success=result.get("success", False),
                        execution_time=exec_time,
                    )

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
                "code": code[:500],
                "result": result,
                "execution_time": execution_time,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "pool_hit": pool_hit,
                "container_id": container.container_id if container else None,
            }

            result["execution_id"] = execution_id
            result["execution_time"] = execution_time
            result["pool_hit"] = pool_hit

            return result

        except Exception as e:
            logger.error(f"Error executing code: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution_id,
                "pool_hit": pool_hit,
            }

    async def execute_python(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        allowed_imports: Optional[list] = None,
    ) -> Dict[str, Any]:
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
        modules: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        执行Node.js代码

        Args:
            code: Node.js代码
            modules: 要导入的模块

        Returns:
            Dict[str, Any]: 执行结果
        """
        return await self.execute(
            code,
            language="nodejs",
            modules=modules,
        )

    def get_execution_history(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        获取执行历史

        Args:
            execution_id: 执行ID

        Returns:
            Dict[str, Any]: 执行历史
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

    def get_pool_stats(self) -> Dict[str, Any]:
        """获取容器池统计信息"""
        return {
            "python_pool": self.python_pool.get_stats(),
            "nodejs_pool": self.nodejs_pool.get_stats(),
        }

    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细的统计信息"""
        return {
            "python_pool": {
                "summary": self.python_pool.get_stats(),
                "containers": self.python_pool.get_container_stats(),
            },
            "nodejs_pool": {
                "summary": self.nodejs_pool.get_stats(),
                "containers": self.nodejs_pool.get_container_stats(),
            },
        }

    async def shutdown(self):
        """关闭执行管理器"""
        logger.info("Shutting down OptimizedExecutionManager")

        await asyncio.gather(
            self.python_pool.shutdown(),
            self.nodejs_pool.shutdown(),
        )

        logger.info("OptimizedExecutionManager shut down")
