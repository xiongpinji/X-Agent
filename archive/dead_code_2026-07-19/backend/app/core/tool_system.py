"""
Enhanced tool system for X-Agent.
Provides hot-loading, versioning, dependency management, and advanced features.

⚠️ 命名与状态说明（2026-06-02 审计标注）
------------------------------------------------------------------
本模块定义的 ``ToolRegistry`` 是一套**独立的实验性子系统**，基于抽象基类
``Tool(ABC)`` 的纯异步设计，配套 ``ToolLoader`` / ``ToolDependencyResolver``
/ ``ToolPermissionManager``。它与生产路径使用的两个同名/近名类无关：

  * ``core/tools.py::ToolRegistry``        —— 生产运行时执行器（DI 经
    ``build_default_tool_registry`` 注入；policy/approval/hooks/execute）。
  * ``core/tool_registry.py::ToolCatalog`` —— 工具 schema 目录（版本/生命周期/
    审计/持久化；旧名 ``ToolRegistry`` 现为别名）。

当前本模块**未接入生产**（api/main/dependencies 均零引用），仅被
``tests/test_capability_improvements.py`` 的 ``TestToolSystem`` 覆盖。保留作为
实验/参考实现；若确定不再演进，可连同对应测试一并移除。新代码请勿从本模块
导入 ``ToolRegistry``，以免与上述两类混淆。
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List
import importlib.util


class ToolStatus(str, Enum):
    """Tool status."""
    AVAILABLE = "available"
    LOADED = "loaded"
    EXECUTING = "executing"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ToolPermission:
    """Tool permission specification."""
    resource: str
    action: str
    conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolMetadata:
    """Tool metadata."""
    name: str
    version: str
    description: str
    author: str
    category: str
    entry_point: str
    dependencies: List[str] = field(default_factory=list)
    permissions: List[ToolPermission] = field(default_factory=list)
    timeout: float = 30.0
    max_retries: int = 3
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['permissions'] = [p.to_dict() for p in self.permissions]
        return data


@dataclass
class ToolExecutionStats:
    """Tool execution statistics."""
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_called: Optional[str] = None
    last_error: Optional[str] = None

    def record_execution(self, duration: float, success: bool, error: Optional[str] = None) -> None:
        """Record tool execution."""
        self.total_calls += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.last_called = datetime.utcnow().isoformat()

        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
            self.last_error = error

    def get_average_time(self) -> float:
        """Get average execution time."""
        if self.total_calls == 0:
            return 0.0
        return self.total_time / self.total_calls

    def get_success_rate(self) -> float:
        """Get success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_time": self.total_time,
            "min_time": self.min_time if self.min_time != float('inf') else 0,
            "max_time": self.max_time,
            "average_time": self.get_average_time(),
            "success_rate": self.get_success_rate(),
            "last_called": self.last_called,
            "last_error": self.last_error,
        }


class Tool(ABC):
    """Abstract tool interface."""

    def __init__(self, metadata: ToolMetadata):
        self.metadata = metadata
        self.status = ToolStatus.AVAILABLE
        self.stats = ToolExecutionStats(name=metadata.name)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute tool."""
        pass

    async def call(self, **kwargs) -> Any:
        """Call tool with execution tracking."""
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                self.execute(**kwargs),
                timeout=self.metadata.timeout
            )
            duration = time.time() - start_time
            self.stats.record_execution(duration, True)
            return result
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            error = f"Tool execution timeout after {self.metadata.timeout}s"
            self.stats.record_execution(duration, False, error)
            raise RuntimeError(error)
        except Exception as e:
            duration = time.time() - start_time
            self.stats.record_execution(duration, False, str(e))
            raise


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.metadata: Dict[str, ToolMetadata] = {}
        self.stats: Dict[str, ToolExecutionStats] = {}

    async def register(self, tool: Tool) -> bool:
        """Register a tool."""
        name = tool.metadata.name
        if name in self.tools:
            return False

        self.tools[name] = tool
        self.metadata[name] = tool.metadata
        self.stats[name] = tool.stats
        return True

    async def unregister(self, name: str) -> bool:
        """Unregister a tool."""
        if name not in self.tools:
            return False

        del self.tools[name]
        del self.metadata[name]
        del self.stats[name]
        return True

    async def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        return self.tools.get(name)

    async def list_tools(self, category: Optional[str] = None) -> List[ToolMetadata]:
        """List tools."""
        tools = list(self.metadata.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    async def search_tools(self, query: str) -> List[ToolMetadata]:
        """Search tools."""
        query_lower = query.lower()
        results = []

        for metadata in self.metadata.values():
            search_text = (
                f"{metadata.name} {metadata.description} "
                f"{' '.join(metadata.tags)}"
            ).lower()

            if query_lower in search_text:
                results.append(metadata)

        return results

    async def get_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """Get tool statistics."""
        if name not in self.stats:
            return None
        return self.stats[name].to_dict()

    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get all tool statistics."""
        return {name: stats.to_dict() for name, stats in self.stats.items()}


class ToolLoader:
    """Loads tools dynamically."""

    @staticmethod
    async def load_from_file(file_path: Path) -> Optional[Tool]:
        """Load tool from Python file."""
        try:
            spec = importlib.util.spec_from_file_location("tool_module", file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for Tool subclass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Tool) and attr != Tool:
                        # Instantiate tool
                        return attr()

            return None
        except Exception:
            return None

    @staticmethod
    async def load_from_directory(directory: Path) -> List[Tool]:
        """Load all tools from directory."""
        tools = []
        for file_path in directory.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            tool = await ToolLoader.load_from_file(file_path)
            if tool:
                tools.append(tool)

        return tools


class ToolDependencyResolver:
    """Resolves tool dependencies."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def resolve(self, tool_name: str) -> tuple[bool, List[str], List[str]]:
        """
        Resolve tool dependencies.
        Returns: (success, resolved_tools, errors)
        """
        tool = await self.registry.get_tool(tool_name)
        if not tool:
            return False, [], [f"Tool not found: {tool_name}"]

        resolved = []
        errors = []
        visited = set()

        async def resolve_recursive(name: str) -> bool:
            if name in visited:
                return True

            visited.add(name)

            tool = await self.registry.get_tool(name)
            if not tool:
                errors.append(f"Dependency not found: {name}")
                return False

            resolved.append(name)

            # Recursively resolve dependencies
            for dep in tool.metadata.dependencies:
                if not await resolve_recursive(dep):
                    return False

            return True

        if await resolve_recursive(tool_name):
            return True, resolved, errors
        else:
            return False, resolved, errors


class ToolPermissionManager:
    """Manages tool permissions."""

    def __init__(self):
        self.permissions: Dict[str, List[ToolPermission]] = {}

    def grant_permission(self, tool_name: str, permission: ToolPermission) -> None:
        """Grant permission to tool."""
        if tool_name not in self.permissions:
            self.permissions[tool_name] = []
        self.permissions[tool_name].append(permission)

    def revoke_permission(self, tool_name: str, resource: str, action: str) -> bool:
        """Revoke permission from tool."""
        if tool_name not in self.permissions:
            return False

        self.permissions[tool_name] = [
            p for p in self.permissions[tool_name]
            if not (p.resource == resource and p.action == action)
        ]
        return True

    def has_permission(self, tool_name: str, resource: str, action: str) -> bool:
        """Check if tool has permission."""
        if tool_name not in self.permissions:
            return False

        for perm in self.permissions[tool_name]:
            if perm.resource == resource and perm.action == action:
                return True

        return False

    def get_permissions(self, tool_name: str) -> List[ToolPermission]:
        """Get tool permissions."""
        return self.permissions.get(tool_name, [])


class ToolRecommender:
    """Recommends tools based on context."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def recommend(self, context: str, limit: int = 5) -> List[ToolMetadata]:
        """Recommend tools for context."""
        context_lower = context.lower()
        scored_tools = []

        for metadata in await self.registry.list_tools():
            score = 0

            # Score based on name match
            if context_lower in metadata.name.lower():
                score += 10

            # Score based on description match
            if context_lower in metadata.description.lower():
                score += 5

            # Score based on tags
            for tag in metadata.tags:
                if context_lower in tag.lower():
                    score += 3

            if score > 0:
                scored_tools.append((metadata, score))

        # Sort by score and return top results
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        return [tool for tool, _ in scored_tools[:limit]]


class ToolManager:
    """Main tool management interface."""

    def __init__(self, tools_dir: Optional[Path] = None):
        self.tools_dir = tools_dir or Path("~/.xagent/tools").expanduser()
        self.registry = ToolRegistry()
        self.dependency_resolver = ToolDependencyResolver(self.registry)
        self.permission_manager = ToolPermissionManager()
        self.recommender = ToolRecommender(self.registry)
        self.tools_dir.mkdir(parents=True, exist_ok=True)

    async def load_tools(self) -> List[Tool]:
        """Load all tools from directory."""
        tools = await ToolLoader.load_from_directory(self.tools_dir)
        for tool in tools:
            await self.registry.register(tool)
        return tools

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a tool."""
        tool = await self.registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Check permissions
        for resource, value in kwargs.items():
            if not self.permission_manager.has_permission(tool_name, resource, "access"):
                raise PermissionError(f"Tool {tool_name} lacks permission for {resource}")

        return await tool.call(**kwargs)

    async def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool information."""
        tool = await self.registry.get_tool(tool_name)
        if not tool:
            return None

        stats = await self.registry.get_stats(tool_name)
        return {
            "metadata": tool.metadata.to_dict(),
            "status": tool.status.value,
            "stats": stats,
            "permissions": [p.to_dict() for p in self.permission_manager.get_permissions(tool_name)],
        }
