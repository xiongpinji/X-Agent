"""
插件系统优化版 - 异步加载、懒加载、缓存管理

优化特性:
- 异步加载插件
- 懒加载和卸载
- 插件缓存
- 依赖管理
- 性能监控
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)


class PluginStatus(str, Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """插件元数据"""
    plugin_id: str
    name: str
    version: str
    author: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = ""
    memory_mb: float = 50.0


@dataclass
class PluginStats:
    """插件统计信息"""
    total_loaded: int = 0
    total_unloaded: int = 0
    total_errors: int = 0
    total_load_time_ms: float = 0.0
    total_memory_mb: float = 0.0
    active_plugins: int = 0

    @property
    def average_load_time_ms(self) -> float:
        """平均加载时间"""
        if self.total_loaded == 0:
            return 0.0
        return self.total_load_time_ms / self.total_loaded


class PluginCache:
    """插件缓存管理"""

    def __init__(self, max_memory_mb: int = 150):
        self.max_memory_mb = max_memory_mb
        self.cached_plugins: Dict[str, Any] = {}
        self.plugin_memory: Dict[str, float] = {}
        self.access_times: Dict[str, float] = {}
        self.lock = asyncio.Lock()

    async def load_plugin(
        self,
        plugin_id: str,
        loader: Callable[[], Any],
        memory_mb: float = 50.0,
    ) -> Any:
        """加载插件"""
        async with self.lock:
            # 检查缓存
            if plugin_id in self.cached_plugins:
                self.access_times[plugin_id] = time.time()
                logger.debug(f"Plugin cache hit: {plugin_id}")
                return self.cached_plugins[plugin_id]

            # 检查内存限制
            while self._get_total_memory() + memory_mb > self.max_memory_mb:
                self._evict_lru_plugin()

            # 加载插件
            logger.info(f"Loading plugin: {plugin_id}")
            plugin = await loader() if asyncio.iscoroutinefunction(loader) else loader()

            # 缓存插件
            self.cached_plugins[plugin_id] = plugin
            self.plugin_memory[plugin_id] = memory_mb
            self.access_times[plugin_id] = time.time()

            logger.info(f"Plugin loaded: {plugin_id} ({memory_mb:.1f}MB)")
            return plugin

    def _get_total_memory(self) -> float:
        """获取总内存占用"""
        return sum(self.plugin_memory.values())

    def _evict_lru_plugin(self) -> None:
        """驱逐最少使用的插件"""
        if not self.access_times:
            return

        lru_plugin = min(self.access_times, key=self.access_times.get)
        del self.cached_plugins[lru_plugin]
        del self.plugin_memory[lru_plugin]
        del self.access_times[lru_plugin]
        logger.info(f"Evicted plugin: {lru_plugin}")

    async def unload_plugin(self, plugin_id: str) -> None:
        """卸载插件"""
        async with self.lock:
            if plugin_id in self.cached_plugins:
                del self.cached_plugins[plugin_id]
                del self.plugin_memory[plugin_id]
                del self.access_times[plugin_id]
                logger.info(f"Plugin unloaded: {plugin_id}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "cached_plugins": len(self.cached_plugins),
            "total_memory_mb": self._get_total_memory(),
            "max_memory_mb": self.max_memory_mb,
            "utilization": self._get_total_memory() / self.max_memory_mb * 100,
        }


class PluginIndex:
    """插件索引"""

    def __init__(self):
        self.name_index: Dict[str, str] = {}  # name -> plugin_id
        self.category_index: Dict[str, List[str]] = defaultdict(list)  # category -> [plugin_ids]
        self.dependency_index: Dict[str, List[str]] = defaultdict(list)  # plugin_id -> [dependencies]
        self.lock = asyncio.Lock()

    async def add_plugin(
        self,
        plugin_id: str,
        name: str,
        category: str,
        dependencies: List[str],
    ) -> None:
        """添加插件到索引"""
        async with self.lock:
            self.name_index[name] = plugin_id
            self.category_index[category].append(plugin_id)
            self.dependency_index[plugin_id] = dependencies
            logger.debug(f"Plugin indexed: {plugin_id}")

    async def remove_plugin(self, plugin_id: str, name: str, category: str) -> None:
        """从索引移除插件"""
        async with self.lock:
            self.name_index.pop(name, None)
            if plugin_id in self.category_index[category]:
                self.category_index[category].remove(plugin_id)
            self.dependency_index.pop(plugin_id, None)
            logger.debug(f"Plugin removed from index: {plugin_id}")

    async def find_by_name(self, name: str) -> Optional[str]:
        """按名称查找插件"""
        async with self.lock:
            return self.name_index.get(name)

    async def find_by_category(self, category: str) -> List[str]:
        """按类别查找插件"""
        async with self.lock:
            return self.category_index.get(category, [])

    async def get_dependencies(self, plugin_id: str) -> List[str]:
        """获取插件依赖"""
        async with self.lock:
            return self.dependency_index.get(plugin_id, [])


class PluginSystemOptimized:
    """优化版插件系统"""

    def __init__(self, cache_memory_mb: int = 150):
        self.cache = PluginCache(max_memory_mb=cache_memory_mb)
        self.index = PluginIndex()
        self.plugins: Dict[str, Dict[str, Any]] = {}
        self.metadata: Dict[str, PluginMetadata] = {}
        self.stats = PluginStats()
        self.loading_tasks: Dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()

    async def register_plugin(
        self,
        metadata: PluginMetadata,
        loader: Callable[[], Any],
    ) -> bool:
        """注册插件"""
        try:
            async with self.lock:
                if metadata.plugin_id in self.metadata:
                    logger.warning(f"Plugin already registered: {metadata.plugin_id}")
                    return False

                self.metadata[metadata.plugin_id] = metadata

            # 添加到索引
            await self.index.add_plugin(
                metadata.plugin_id,
                metadata.name,
                "default",
                metadata.dependencies,
            )

            logger.info(f"Plugin registered: {metadata.plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Error registering plugin: {e}")
            self.stats.total_errors += 1
            return False

    async def load_plugin(self, plugin_id: str) -> bool:
        """加载插件"""
        try:
            if plugin_id in self.loading_tasks:
                # 等待正在进行的加载
                await self.loading_tasks[plugin_id]
                return plugin_id in self.plugins

            metadata = self.metadata.get(plugin_id)
            if not metadata:
                logger.error(f"Plugin metadata not found: {plugin_id}")
                return False

            # 创建加载任务
            async def load_task() -> None:
                start_time = time.time()

                try:
                    # 加载依赖
                    for dep_id in metadata.dependencies:
                        if dep_id not in self.plugins:
                            await self.load_plugin(dep_id)

                    # 加载插件
                    def loader() -> Any:
                        return {"plugin_id": plugin_id, "loaded_at": time.time()}

                    plugin = await self.cache.load_plugin(
                        plugin_id,
                        loader,
                        memory_mb=metadata.memory_mb,
                    )

                    async with self.lock:
                        self.plugins[plugin_id] = {
                            "metadata": metadata,
                            "instance": plugin,
                            "status": PluginStatus.LOADED,
                            "loaded_at": time.time(),
                        }

                    load_time_ms = int((time.time() - start_time) * 1000)
                    self.stats.total_loaded += 1
                    self.stats.total_load_time_ms += load_time_ms
                    self.stats.total_memory_mb += metadata.memory_mb

                    logger.info(f"Plugin loaded: {plugin_id} ({load_time_ms}ms)")

                except Exception as e:
                    logger.error(f"Error loading plugin {plugin_id}: {e}")
                    self.stats.total_errors += 1
                    async with self.lock:
                        if plugin_id in self.plugins:
                            self.plugins[plugin_id]["status"] = PluginStatus.ERROR
                finally:
                    del self.loading_tasks[plugin_id]

            task = asyncio.create_task(load_task())
            self.loading_tasks[plugin_id] = task
            await task

            return plugin_id in self.plugins

        except Exception as e:
            logger.error(f"Error in load_plugin: {e}")
            self.stats.total_errors += 1
            return False

    async def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件"""
        try:
            async with self.lock:
                if plugin_id not in self.plugins:
                    return False

                plugin_info = self.plugins[plugin_id]
                metadata = plugin_info["metadata"]

                del self.plugins[plugin_id]

            await self.cache.unload_plugin(plugin_id)

            self.stats.total_unloaded += 1
            self.stats.total_memory_mb -= metadata.memory_mb

            logger.info(f"Plugin unloaded: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Error unloading plugin: {e}")
            self.stats.total_errors += 1
            return False

    async def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """获取插件实例"""
        async with self.lock:
            if plugin_id not in self.plugins:
                return None

            plugin_info = self.plugins[plugin_id]
            if plugin_info["status"] != PluginStatus.LOADED:
                return None

            return plugin_info["instance"]

    async def find_plugins_by_name(self, name: str) -> List[str]:
        """按名称查找插件"""
        plugin_id = await self.index.find_by_name(name)
        return [plugin_id] if plugin_id else []

    async def find_plugins_by_category(self, category: str) -> List[str]:
        """按类别查找插件"""
        return await self.index.find_by_category(category)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_loaded": self.stats.total_loaded,
            "total_unloaded": self.stats.total_unloaded,
            "total_errors": self.stats.total_errors,
            "average_load_time_ms": self.stats.average_load_time_ms,
            "total_memory_mb": self.stats.total_memory_mb,
            "active_plugins": len(self.plugins),
            "cache_stats": self.cache.get_stats(),
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = PluginStats()


# 全局插件系统实例
_plugin_system: Optional[PluginSystemOptimized] = None


def get_plugin_system() -> PluginSystemOptimized:
    """获取全局插件系统"""
    global _plugin_system
    if _plugin_system is None:
        _plugin_system = PluginSystemOptimized()
    return _plugin_system
