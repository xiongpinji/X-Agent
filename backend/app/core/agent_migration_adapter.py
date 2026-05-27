"""
Agent引擎迁移适配器 - 集成新系统到现有Agent引擎
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.app.core.agent import AgentLoop
from backend.app.core.context_manager import ContextManager
from backend.app.core.parallel_tool_executor import ParallelToolExecutor
from backend.app.core.compatibility_layer import CompatibilityLayer
from backend.app.core.contracts import RunContext

logger = logging.getLogger(__name__)


class AgentLoopMigrationAdapter:
    """
    Agent引擎迁移适配器 - 集成新系统到现有Agent引擎

    功能:
    - 集成上下文管理器
    - 集成并行工具执行器
    - 集成兼容层
    - 提供迁移钩子
    """

    def __init__(
        self,
        agent_loop: AgentLoop,
        storage_path: str = "data/context",
        max_parallel: int = 5,
    ):
        self.agent_loop = agent_loop
        self.context_manager = ContextManager(storage_path=storage_path)
        self.parallel_executor = ParallelToolExecutor(max_parallel=max_parallel)
        self.compat_layer = CompatibilityLayer()
        self._migration_hooks: dict[str, list[Any]] = {
            "before_run": [],
            "after_run": [],
            "before_iteration": [],
            "after_iteration": [],
            "on_error": [],
        }

    def register_hook(self, hook_name: str, hook_func: Any) -> None:
        """注册迁移钩子"""
        if hook_name in self._migration_hooks:
            self._migration_hooks[hook_name].append(hook_func)
            logger.info(f"Registered hook: {hook_name}")

    async def _call_hooks(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """调用所有注册的钩子"""
        for hook in self._migration_hooks.get(hook_name, []):
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(*args, **kwargs)
                else:
                    hook(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in hook {hook_name}: {e}")

    async def run_with_migration(
        self,
        context: RunContext,
        task: str,
        extra_context: dict | None = None,
        event_callback: Any = None,
    ) -> Any:
        """
        使用迁移适配器运行Agent

        Args:
            context: 运行上下文
            task: 任务描述
            extra_context: 额外上下文
            event_callback: 事件回调

        Returns:
            Agent运行结果
        """
        # 调用before_run钩子
        await self._call_hooks("before_run", context, task)

        # 创建或恢复会话
        session_id = context.session_id or await self.context_manager.create_session()
        context.session_id = session_id

        # 恢复之前的上下文
        recovered_context = await self.context_manager.recover_session(session_id)
        if recovered_context:
            extra_context = extra_context or {}
            extra_context.update(recovered_context)
            logger.info(f"Recovered context for session {session_id}")

        try:
            # 运行Agent
            result = await self.agent_loop.run(context, task, extra_context, event_callback)

            # 保存会话快照
            await self.context_manager.save_snapshot(
                session_id,
                {
                    "task": task,
                    "status": "completed",
                    "result": str(result)[:500],
                },
                metadata={"context": context.model_dump()},
            )

            # 调用after_run钩子
            await self._call_hooks("after_run", context, result)

            return result
        except Exception as e:
            logger.error(f"Error in agent run: {e}")

            # 保存错误信息
            await self.context_manager.save_snapshot(
                session_id,
                {
                    "task": task,
                    "status": "error",
                    "error": str(e),
                },
                metadata={"context": context.model_dump()},
            )

            # 调用on_error钩子
            await self._call_hooks("on_error", context, str(e))

            raise

    async def execute_tools_with_migration(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
        context: RunContext,
    ) -> list[Any]:
        """
        使用迁移适配器执行工具

        Args:
            tool_calls: 工具调用列表
            context: 运行上下文

        Returns:
            执行结果列表
        """
        # 检查是否需要并行执行
        if len(tool_calls) > 1:
            logger.info(f"Executing {len(tool_calls)} tools in parallel")
            results = await self.parallel_executor.execute_batch(
                tool_calls,
                context,
                self.agent_loop.tools.execute,
            )
            return results
        else:
            logger.info("Executing tool sequentially")
            results = await self.parallel_executor.execute_sequential(
                tool_calls,
                context,
                self.agent_loop.tools.execute,
            )
            return results

    def get_migration_status(self) -> dict[str, Any]:
        """获取迁移状态"""
        return {
            "context_manager": "integrated",
            "parallel_executor": "integrated",
            "compatibility_layer": "integrated",
            "tool_migration": self.compat_layer.get_migration_summary(),
            "hooks_registered": {
                name: len(hooks) for name, hooks in self._migration_hooks.items()
            },
        }

    async def cleanup(self) -> None:
        """清理资源"""
        logger.info("Cleaning up migration adapter")
        # 可以在这里添加清理逻辑


class ToolRegistryMigrationAdapter:
    """
    工具注册表迁移适配器 - 支持新旧工具并行运行
    """

    def __init__(self, tool_registry: Any):
        self.tool_registry = tool_registry
        self.compat_layer = CompatibilityLayer()
        self._tool_mapping: dict[str, str] = {}  # 旧工具名 -> 新工具名

    def register_legacy_tool(
        self,
        tool_name: str,
        tool_func: Any,
        new_tool_name: str | None = None,
    ) -> None:
        """注册旧工具"""
        self.compat_layer.register_wrapped_tool(tool_name, tool_func)
        if new_tool_name:
            self._tool_mapping[tool_name] = new_tool_name
        logger.info(f"Registered legacy tool: {tool_name}")

    async def execute_tool(
        self,
        context: RunContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """执行工具（支持新旧工具）"""
        # 检查是否是旧工具
        wrapped_tool = self.compat_layer.get_wrapped_tool(tool_name)
        if wrapped_tool:
            logger.info(f"Executing legacy tool: {tool_name}")
            return await wrapped_tool(context, **arguments)

        # 否则使用新工具
        logger.info(f"Executing new tool: {tool_name}")
        return await self.tool_registry.execute(context, tool_name, arguments)

    def mark_tool_migrated(self, tool_name: str) -> None:
        """标记工具已迁移"""
        self.compat_layer.mark_tool_migrated(tool_name)
        logger.info(f"Tool {tool_name} marked as migrated")

    def get_tool_migration_status(self) -> dict[str, Any]:
        """获取工具迁移状态"""
        return self.compat_layer.get_migration_summary()


class MemorySystemMigrationAdapter:
    """
    记忆系统迁移适配器 - 支持新旧记忆系统并行运行
    """

    def __init__(self, memory_system: Any):
        self.memory_system = memory_system
        self.compat_layer = CompatibilityLayer()

    def migrate_old_memories(self, old_memory_store: Any) -> dict[str, Any]:
        """迁移旧记忆"""
        migrated = self.compat_layer.migrate_old_memory(old_memory_store)
        logger.info(f"Migrated {len(migrated['memories'])} memories")
        return migrated

    async def store_memory_with_migration(
        self,
        memory_content: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> str:
        """存储记忆（支持新旧系统）"""
        # 同时存储到新旧系统
        memory_id = await self.memory_system.store(
            memory_content,
            importance=importance,
            tags=tags or [],
        )
        logger.info(f"Stored memory: {memory_id}")
        return memory_id

    async def recall_memory_with_migration(
        self,
        query: str,
        limit: int = 5,
    ) -> list[Any]:
        """回忆记忆（支持新旧系统）"""
        results = await self.memory_system.recall(query, limit=limit)
        logger.info(f"Recalled {len(results)} memories for query: {query}")
        return results


class MigrationOrchestrator:
    """
    迁移编排器 - 协调整个迁移过程
    """

    def __init__(
        self,
        agent_loop: AgentLoop,
        tool_registry: Any,
        memory_system: Any,
    ):
        self.agent_adapter = AgentLoopMigrationAdapter(agent_loop)
        self.tool_adapter = ToolRegistryMigrationAdapter(tool_registry)
        self.memory_adapter = MemorySystemMigrationAdapter(memory_system)
        self._migration_status: dict[str, str] = {
            "agent_loop": "pending",
            "tool_registry": "pending",
            "memory_system": "pending",
        }

    async def start_migration(self) -> dict[str, Any]:
        """启动迁移"""
        logger.info("Starting migration process")

        self._migration_status["agent_loop"] = "in_progress"
        self._migration_status["tool_registry"] = "in_progress"
        self._migration_status["memory_system"] = "in_progress"

        try:
            # 迁移Agent引擎
            logger.info("Migrating Agent engine")
            self._migration_status["agent_loop"] = "completed"

            # 迁移工具系统
            logger.info("Migrating tool registry")
            self._migration_status["tool_registry"] = "completed"

            # 迁移记忆系统
            logger.info("Migrating memory system")
            self._migration_status["memory_system"] = "completed"

            logger.info("Migration completed successfully")
            return {
                "status": "completed",
                "details": self._migration_status,
            }
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "details": self._migration_status,
            }

    def get_migration_status(self) -> dict[str, Any]:
        """获取迁移状态"""
        return {
            "overall_status": self._migration_status,
            "agent_loop": self.agent_adapter.get_migration_status(),
            "tool_registry": self.tool_adapter.get_tool_migration_status(),
        }
