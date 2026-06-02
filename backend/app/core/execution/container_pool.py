"""
容器池管理器 - 管理Python和Node.js容器的生命周期和复用
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ContainerState(Enum):
    """容器状态"""
    IDLE = "idle"  # 空闲
    RUNNING = "running"  # 运行中
    WARMING = "warming"  # 预热中
    UNHEALTHY = "unhealthy"  # 不健康
    TERMINATED = "terminated"  # 已终止


@dataclass
class ContainerMetrics:
    """容器指标"""
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime = field(default_factory=datetime.now)
    execution_count: int = 0
    total_execution_time: float = 0.0
    error_count: int = 0
    health_check_count: int = 0
    health_check_failures: int = 0

    def update_execution(self, execution_time: float, success: bool = True):
        """更新执行指标"""
        self.last_used_at = datetime.now()
        self.execution_count += 1
        self.total_execution_time += execution_time
        if not success:
            self.error_count += 1

    def get_avg_execution_time(self) -> float:
        """获取平均执行时间"""
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time / self.execution_count

    def get_error_rate(self) -> float:
        """获取错误率"""
        if self.execution_count == 0:
            return 0.0
        return self.error_count / self.execution_count


@dataclass
class Container:
    """容器对象"""
    container_id: str
    language: str  # "python" 或 "nodejs"
    state: ContainerState = ContainerState.IDLE
    metrics: ContainerMetrics = field(default_factory=ContainerMetrics)
    last_error: Optional[str] = None

    def is_available(self) -> bool:
        """检查容器是否可用"""
        return self.state == ContainerState.IDLE

    def is_healthy(self) -> bool:
        """检查容器是否健康"""
        if self.state == ContainerState.UNHEALTHY:
            return False
        # 如果错误率超过20%，标记为不健康
        if self.metrics.get_error_rate() > 0.2:
            return False
        return True


class ContainerPool:
    """容器池 - 管理容器的创建、复用和回收"""

    def __init__(
        self,
        pool_size: int = 10,
        language: str = "python",
        warmup_enabled: bool = True,
        health_check_interval: int = 60,
    ):
        """
        初始化容器池

        Args:
            pool_size: 池大小
            language: 编程语言（python或nodejs）
            warmup_enabled: 是否启用预热
            health_check_interval: 健康检查间隔（秒）
        """
        self.pool_size = pool_size
        self.language = language
        self.warmup_enabled = warmup_enabled
        self.health_check_interval = health_check_interval

        self.containers: List[Container] = []
        self.lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._warmup_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_acquisitions": 0,
            "total_releases": 0,
            "pool_hits": 0,
            "pool_misses": 0,
            "warmup_count": 0,
            "health_check_count": 0,
        }

    async def initialize(self):
        """初始化容器池"""
        logger.info(f"Initializing {self.language} container pool with size {self.pool_size}")

        async with self.lock:
            # 创建初始容器
            for i in range(self.pool_size):
                container = Container(
                    container_id=f"{self.language}-{i}-{int(time.time() * 1000)}",
                    language=self.language,
                )
                self.containers.append(container)

        # 启动预热任务
        if self.warmup_enabled:
            self._warmup_task = asyncio.create_task(self._warmup_containers())

        # 启动健康检查任务
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info(f"{self.language} container pool initialized with {len(self.containers)} containers")

    async def acquire(self, timeout: float = 5.0) -> Optional[Container]:
        """
        获取一个可用的容器

        Args:
            timeout: 获取超时时间（秒）

        Returns:
            Container: 可用的容器，如果超时则返回None
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            async with self.lock:
                # 查找可用的健康容器
                for container in self.containers:
                    if container.is_available() and container.is_healthy():
                        container.state = ContainerState.RUNNING
                        self._stats["total_acquisitions"] += 1
                        self._stats["pool_hits"] += 1
                        logger.debug(f"Acquired container {container.container_id}")
                        return container

            # 如果没有可用容器，等待一段时间后重试
            await asyncio.sleep(0.1)

        self._stats["pool_misses"] += 1
        logger.warning(f"Failed to acquire {self.language} container within {timeout}s")
        return None

    async def release(self, container: Container, success: bool = True, execution_time: float = 0.0):
        """
        释放容器回到池中

        Args:
            container: 要释放的容器
            success: 执行是否成功
            execution_time: 执行时间（秒）
        """
        async with self.lock:
            container.state = ContainerState.IDLE
            container.metrics.update_execution(execution_time, success)
            self._stats["total_releases"] += 1
            logger.debug(f"Released container {container.container_id}")

    async def _warmup_containers(self):
        """预热容器"""
        try:
            logger.info(f"Starting warmup for {self.language} containers")

            # 等待初始化完成
            await asyncio.sleep(1)

            async with self.lock:
                containers_to_warmup = [c for c in self.containers if c.state == ContainerState.IDLE]

            # 并行预热容器
            warmup_tasks = []
            for container in containers_to_warmup:
                warmup_tasks.append(self._warmup_single_container(container))

            results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)

            self._stats["warmup_count"] = success_count
            logger.info(f"Warmup completed: {success_count}/{len(containers_to_warmup)} containers warmed up")

        except Exception as e:
            logger.error(f"Error during container warmup: {e}")

    async def _warmup_single_container(self, container: Container) -> bool:
        """预热单个容器"""
        try:
            async with self.lock:
                if container.state != ContainerState.IDLE:
                    return False
                container.state = ContainerState.WARMING

            # 执行简单的预热代码
            if self.language == "python":
                warmup_code = "x = 1 + 1"
            else:  # nodejs
                warmup_code = "const x = 1 + 1;"

            # 这里会由执行管理器调用实际的执行逻辑
            # 现在只是标记为已预热
            await asyncio.sleep(0.01)  # 模拟预热时间

            async with self.lock:
                container.state = ContainerState.IDLE
                container.metrics.update_execution(0.01, True)

            logger.debug(f"Warmed up container {container.container_id}")
            return True

        except Exception as e:
            logger.error(f"Error warming up container {container.container_id}: {e}")
            async with self.lock:
                container.state = ContainerState.UNHEALTHY
                container.last_error = str(e)
            return False

    async def _health_check_loop(self):
        """健康检查循环"""
        try:
            while True:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_checks()
        except asyncio.CancelledError:
            logger.info(f"Health check loop cancelled for {self.language}")
        except Exception as e:
            logger.error(f"Error in health check loop: {e}")

    async def _perform_health_checks(self):
        """执行健康检查"""
        try:
            async with self.lock:
                containers_to_check = [c for c in self.containers if c.state == ContainerState.IDLE]

            logger.debug(f"Performing health checks on {len(containers_to_check)} {self.language} containers")

            # 并行执行健康检查
            check_tasks = []
            for container in containers_to_check:
                check_tasks.append(self._health_check_single_container(container))

            results = await asyncio.gather(*check_tasks, return_exceptions=True)
            healthy_count = sum(1 for r in results if r is True)

            self._stats["health_check_count"] += 1
            logger.debug(f"Health check completed: {healthy_count}/{len(containers_to_check)} containers healthy")

        except Exception as e:
            logger.error(f"Error performing health checks: {e}")

    async def _health_check_single_container(self, container: Container) -> bool:
        """检查单个容器的健康状态"""
        try:
            # 检查容器是否在合理的时间内没有被使用
            idle_time = (datetime.now() - container.metrics.last_used_at).total_seconds()

            # 如果容器空闲时间过长（超过5分钟），标记为需要重新预热
            if idle_time > 300:
                logger.debug(f"Container {container.container_id} idle for {idle_time}s, marking for warmup")
                container.state = ContainerState.WARMING
                await self._warmup_single_container(container)

            # 检查错误率
            if not container.is_healthy():
                logger.warning(f"Container {container.container_id} marked as unhealthy")
                return False

            container.metrics.health_check_count += 1
            return True

        except Exception as e:
            logger.error(f"Error health checking container {container.container_id}: {e}")
            return False

    async def shutdown(self):
        """关闭容器池"""
        logger.info(f"Shutting down {self.language} container pool")

        # 取消后台任务
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._warmup_task:
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass

        async with self.lock:
            # 标记所有容器为已终止
            for container in self.containers:
                container.state = ContainerState.TERMINATED

        logger.info(f"{self.language} container pool shut down")

    def get_stats(self) -> Dict[str, Any]:
        """获取池统计信息"""
        async_stats = {
            "pool_size": self.pool_size,
            "language": self.language,
            "total_containers": len(self.containers),
            "idle_containers": sum(1 for c in self.containers if c.state == ContainerState.IDLE),
            "running_containers": sum(1 for c in self.containers if c.state == ContainerState.RUNNING),
            "unhealthy_containers": sum(1 for c in self.containers if c.state == ContainerState.UNHEALTHY),
        }

        async_stats.update(self._stats)

        # 计算池利用率
        if self._stats["total_acquisitions"] > 0:
            hit_rate = self._stats["pool_hits"] / self._stats["total_acquisitions"]
            async_stats["hit_rate"] = hit_rate
        else:
            async_stats["hit_rate"] = 0.0

        # 计算平均执行时间
        total_exec_time = sum(c.metrics.total_execution_time for c in self.containers)
        total_exec_count = sum(c.metrics.execution_count for c in self.containers)
        if total_exec_count > 0:
            async_stats["avg_execution_time"] = total_exec_time / total_exec_count
        else:
            async_stats["avg_execution_time"] = 0.0

        return async_stats

    def get_container_stats(self) -> List[Dict[str, Any]]:
        """获取所有容器的详细统计信息"""
        stats = []
        for container in self.containers:
            stats.append({
                "container_id": container.container_id,
                "state": container.state.value,
                "execution_count": container.metrics.execution_count,
                "avg_execution_time": container.metrics.get_avg_execution_time(),
                "error_rate": container.metrics.get_error_rate(),
                "health_check_count": container.metrics.health_check_count,
                "last_used_at": container.metrics.last_used_at.isoformat(),
            })
        return stats
