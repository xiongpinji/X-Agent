"""
向后兼容层 - 确保旧代码继续工作
"""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar

from backend.app.core.contracts import RunContext, ToolCallRecord

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CompatibilityLayer:
    """
    向后兼容层 - 确保旧代码继续工作

    功能:
    - 包装旧工具函数: 使用新架构执行旧工具
    - 迁移旧记忆数据: 将旧记忆系统数据迁移到新系统
    - 适配旧API: 提供旧API的适配器
    - 渐进式迁移: 支持新旧系统并行运行
    """

    def __init__(self):
        self._wrapped_tools: dict[str, Callable] = {}
        self._migration_status: dict[str, str] = {}
        self._adapter_cache: dict[str, Any] = {}

    @staticmethod
    def wrap_old_tool(old_tool_func: Callable) -> Callable:
        """
        包装旧工具函数使用新架构

        Args:
            old_tool_func: 旧工具函数

        Returns:
            包装后的工具函数
        """

        @functools.wraps(old_tool_func)
        async def wrapper(
            context: RunContext,
            *args: Any,
            **kwargs: Any,
        ) -> ToolCallRecord:
            """包装器函数"""
            try:
                # 调用旧工具
                if asyncio.iscoroutinefunction(old_tool_func):
                    result = await old_tool_func(*args, **kwargs)
                else:
                    result = old_tool_func(*args, **kwargs)

                # 转换为新的ToolCallRecord格式
                return ToolCallRecord(
                    tool_name=getattr(old_tool_func, "__name__", "unknown"),
                    arguments=kwargs,
                    success=True,
                    output=result,
                    latency_ms=0,
                )
            except Exception as e:
                logger.error(f"Error in wrapped tool {old_tool_func.__name__}: {e}")
                return ToolCallRecord(
                    tool_name=getattr(old_tool_func, "__name__", "unknown"),
                    arguments=kwargs,
                    success=False,
                    error=str(e),
                    latency_ms=0,
                )

        return wrapper

    @staticmethod
    def migrate_old_memory(old_memory_store: Any) -> dict[str, Any]:
        """
        迁移旧记忆数据到新系统

        Args:
            old_memory_store: 旧记忆存储

        Returns:
            迁移后的记忆数据
        """
        migrated = {
            "memories": [],
            "sessions": [],
            "metadata": {
                "source": "old_memory_store",
                "migration_status": "pending",
            },
        }

        try:
            # 提取旧记忆数据
            if hasattr(old_memory_store, "memories"):
                for memory in old_memory_store.memories:
                    migrated["memories"].append(
                        {
                            "id": getattr(memory, "id", None),
                            "content": getattr(memory, "content", ""),
                            "importance": getattr(memory, "importance", 0.5),
                            "tags": getattr(memory, "tags", []),
                            "created_at": getattr(memory, "created_at", None),
                        }
                    )

            # 提取旧会话数据
            if hasattr(old_memory_store, "sessions"):
                for session in old_memory_store.sessions:
                    migrated["sessions"].append(
                        {
                            "session_id": getattr(session, "session_id", None),
                            "title": getattr(session, "title", ""),
                            "created_at": getattr(session, "created_at", None),
                        }
                    )

            migrated["metadata"]["migration_status"] = "completed"
            logger.info(
                f"Migrated {len(migrated['memories'])} memories and "
                f"{len(migrated['sessions'])} sessions"
            )
        except Exception as e:
            logger.error(f"Error migrating old memory: {e}")
            migrated["metadata"]["migration_status"] = "failed"
            migrated["metadata"]["error"] = str(e)

        return migrated

    @staticmethod
    def create_adapter(
        old_interface: type,
        new_interface: type,
    ) -> Callable:
        """
        创建旧接口到新接口的适配器

        Args:
            old_interface: 旧接口类型
            new_interface: 新接口类型

        Returns:
            适配器函数
        """

        def adapter(old_obj: Any) -> Any:
            """适配器实现"""
            if isinstance(old_obj, new_interface):
                return old_obj

            # 创建新对象
            new_obj = new_interface()

            # 复制兼容的属性
            for attr in dir(old_obj):
                if not attr.startswith("_"):
                    try:
                        value = getattr(old_obj, attr)
                        if not callable(value):
                            setattr(new_obj, attr, value)
                    except Exception:
                        pass

            return new_obj

        return adapter

    def register_wrapped_tool(
        self,
        tool_name: str,
        old_tool_func: Callable,
    ) -> None:
        """注册包装的旧工具"""
        self._wrapped_tools[tool_name] = self.wrap_old_tool(old_tool_func)
        self._migration_status[tool_name] = "wrapped"
        logger.info(f"Registered wrapped tool: {tool_name}")

    def get_wrapped_tool(self, tool_name: str) -> Callable | None:
        """获取包装的工具"""
        return self._wrapped_tools.get(tool_name)

    def mark_tool_migrated(self, tool_name: str) -> None:
        """标记工具已迁移"""
        self._migration_status[tool_name] = "migrated"
        logger.info(f"Tool {tool_name} marked as migrated")

    def get_migration_status(self) -> dict[str, str]:
        """获取迁移状态"""
        return self._migration_status.copy()

    def get_migration_summary(self) -> dict[str, Any]:
        """获取迁移摘要"""
        total = len(self._migration_status)
        migrated = sum(
            1 for status in self._migration_status.values() if status == "migrated"
        )
        wrapped = sum(
            1 for status in self._migration_status.values() if status == "wrapped"
        )

        return {
            "total_tools": total,
            "migrated": migrated,
            "wrapped": wrapped,
            "pending": total - migrated - wrapped,
            "migration_percentage": (migrated / total * 100) if total > 0 else 0,
            "status_details": self._migration_status,
        }


class LegacyToolAdapter:
    """旧工具适配器 - 支持旧工具的执行"""

    def __init__(self, compatibility_layer: CompatibilityLayer):
        self.compat = compatibility_layer

    async def execute_legacy_tool(
        self,
        context: RunContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolCallRecord:
        """执行旧工具"""
        wrapped_tool = self.compat.get_wrapped_tool(tool_name)
        if wrapped_tool:
            return await wrapped_tool(context, **arguments)

        raise ValueError(f"Tool {tool_name} not found in compatibility layer")

    def register_legacy_tool(
        self,
        tool_name: str,
        tool_func: Callable,
    ) -> None:
        """注册旧工具"""
        self.compat.register_wrapped_tool(tool_name, tool_func)


class MigrationHelper:
    """迁移助手 - 帮助迁移过程"""

    def __init__(self, compatibility_layer: CompatibilityLayer):
        self.compat = compatibility_layer

    def get_migration_checklist(self) -> list[dict[str, Any]]:
        """获取迁移检查清单"""
        return [
            {
                "step": 1,
                "title": "包装旧工具",
                "description": "使用CompatibilityLayer.wrap_old_tool包装所有旧工具",
                "status": "pending",
            },
            {
                "step": 2,
                "title": "迁移记忆数据",
                "description": "使用CompatibilityLayer.migrate_old_memory迁移旧记忆",
                "status": "pending",
            },
            {
                "step": 3,
                "title": "更新Agent引擎",
                "description": "集成新的上下文管理器和并行执行器",
                "status": "pending",
            },
            {
                "step": 4,
                "title": "测试兼容性",
                "description": "运行兼容性测试确保旧功能继续工作",
                "status": "pending",
            },
            {
                "step": 5,
                "title": "逐步迁移工具",
                "description": "逐个迁移工具到新架构",
                "status": "pending",
            },
            {
                "step": 6,
                "title": "性能优化",
                "description": "优化新架构的性能",
                "status": "pending",
            },
            {
                "step": 7,
                "title": "生产部署",
                "description": "部署到生产环境",
                "status": "pending",
            },
        ]

    def get_migration_guide(self) -> str:
        """获取迁移指南"""
        return """
# X-Agent 迁移指南

## 概述
本指南说明如何将现有的Agent引擎、工具系统和记忆系统迁移到新的7个核心系统。

## 迁移步骤

### 1. 准备阶段
- 备份现有系统
- 创建测试环境
- 准备回滚方案

### 2. 上下文管理系统迁移
```python
from backend.app.core.context_manager import ContextManager

# 初始化新的上下文管理器
context_manager = ContextManager(
    storage_path="data/context",
    max_tokens=150000,
    compression_threshold=0.8
)

# 在Agent引擎中集成
agent_loop.context_manager = context_manager
```

### 3. 工具系统迁移
```python
from backend.app.core.parallel_tool_executor import ParallelToolExecutor

# 初始化并行执行器
parallel_executor = ParallelToolExecutor(
    max_parallel=5,
    timeout=30
)

# 在工具注册表中集成
tool_registry.parallel_executor = parallel_executor
```

### 4. 记忆系统迁移
```python
from backend.app.core.hybrid_memory_system import HybridMemorySystem

# 初始化混合记忆系统
hybrid_memory = HybridMemorySystem(
    hot_storage_path="data/memory/hot",
    qdrant_client=qdrant_client,
    neo4j_client=neo4j_client
)

# 在记忆系统中集成
memory_system.hybrid_memory = hybrid_memory
```

### 5. 文件系统迁移
```python
from backend.app.core.filesystem_manager import FileSystemManager

# 初始化文件系统管理器
fs_manager = FileSystemManager()

# 在工具中使用
real_path = fs_manager.path_mapper.map_virtual_to_real(path, user_id)
```

### 6. 兼容层集成
```python
from backend.app.core.compatibility_layer import CompatibilityLayer

# 创建兼容层
compat = CompatibilityLayer()

# 包装旧工具
compat.register_wrapped_tool("old_tool", old_tool_func)

# 迁移旧记忆
migrated_memory = compat.migrate_old_memory(old_memory_store)
```

### 7. 测试验证
- 运行单元测试
- 运行集成测试
- 性能基准测试
- 向后兼容性测试

### 8. 逐步迁移
- 迁移一个模块
- 验证功能
- 监控性能
- 重复直到完成

### 9. 生产部署
- 灰度发布
- 监控指标
- 准备回滚
- 完全切换

## 回滚方案

如果迁移出现问题，可以按以下步骤回滚：

1. 停止新系统
2. 恢复旧系统备份
3. 验证功能
4. 分析问题
5. 修复后重新迁移

## 常见问题

### Q: 迁移期间如何保证服务可用性？
A: 使用兼容层支持新旧系统并行运行，逐步迁移工具。

### Q: 如何处理旧数据？
A: 使用CompatibilityLayer.migrate_old_memory迁移旧记忆数据。

### Q: 性能会受到影响吗？
A: 新系统通过并行执行和智能缓存提高性能。

### Q: 如何验证迁移成功？
A: 运行完整的测试套件，包括兼容性测试。

## 支持

如有问题，请参考：
- 迁移测试: tests/test_migration.py
- 兼容性测试: tests/test_compatibility.py
- 性能测试: tests/test_performance.py
"""
