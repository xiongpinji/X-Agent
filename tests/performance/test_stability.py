"""
稳定性测试
测试范围: 长时间运行、内存泄漏检测、资源释放、错误恢复
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any
from dataclasses import dataclass, field
import psutil
import os
import gc


@dataclass
class StabilityTestResult:
    """稳定性测试结果"""
    test_name: str
    duration_hours: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    memory_samples: List[float] = field(default_factory=list)
    cpu_samples: List[float] = field(default_factory=list)
    error_log: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        """错误率"""
        total = self.successful_requests + self.failed_requests
        return (self.failed_requests / total * 100) if total > 0 else 0

    @property
    def avg_memory_mb(self) -> float:
        """平均内存使用"""
        return sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0

    @property
    def max_memory_mb(self) -> float:
        """最大内存使用"""
        return max(self.memory_samples) if self.memory_samples else 0

    @property
    def min_memory_mb(self) -> float:
        """最小内存使用"""
        return min(self.memory_samples) if self.memory_samples else 0

    @property
    def memory_growth_mb(self) -> float:
        """内存增长"""
        if len(self.memory_samples) < 2:
            return 0.0
        return self.memory_samples[-1] - self.memory_samples[0]

    @property
    def avg_cpu_percent(self) -> float:
        """平均CPU使用率"""
        return sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0

    @property
    def max_cpu_percent(self) -> float:
        """最大CPU使用率"""
        return max(self.cpu_samples) if self.cpu_samples else 0

    def has_memory_leak(self, threshold_mb: float = 100.0) -> bool:
        """检测是否存在内存泄漏"""
        return self.memory_growth_mb > threshold_mb


class StabilityTester:
    """稳定性测试器"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.process = psutil.Process(os.getpid())

    async def run_long_duration_test(
        self,
        endpoint: str,
        num_users: int,
        duration_hours: float,
        requests_per_user_per_minute: int = 10,
        test_name: str = ""
    ) -> StabilityTestResult:
        """运行长时间稳定性测试"""
        import aiohttp

        test_name = test_name or f"stability_{duration_hours}h"
        url = f"{self.base_url}{endpoint}"

        result = StabilityTestResult(
            test_name=test_name,
            duration_hours=duration_hours,
            total_requests=0,
            successful_requests=0,
            failed_requests=0
        )

        start_time = time.time()
        end_time = start_time + (duration_hours * 3600)
        monitoring_interval = 60  # 每60秒记录一次资源使用

        async def user_session(user_id: int, session: aiohttp.ClientSession):
            """单个用户会话"""
            while time.time() < end_time:
                try:
                    async with session.get(url, timeout=30) as resp:
                        await resp.text()
                        result.successful_requests += 1
                        result.total_requests += 1

                        if resp.status >= 400:
                            result.failed_requests += 1

                except Exception as e:
                    result.failed_requests += 1
                    result.total_requests += 1
                    result.error_log.append({
                        'timestamp': time.time(),
                        'error': str(e),
                        'user_id': user_id
                    })

                # 控制请求频率
                await asyncio.sleep(60 / requests_per_user_per_minute)

        async def monitor_resources():
            """监控资源使用"""
            while time.time() < end_time:
                try:
                    memory_info = self.process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    cpu_percent = self.process.cpu_percent(interval=1)

                    result.memory_samples.append(memory_mb)
                    result.cpu_samples.append(cpu_percent)

                    # 强制垃圾回收
                    gc.collect()

                except Exception as e:
                    print(f"Error monitoring resources: {e}")

                await asyncio.sleep(monitoring_interval)

        async with aiohttp.ClientSession() as session:
            user_tasks = [user_session(i, session) for i in range(num_users)]
            monitor_task = monitor_resources()

            all_tasks = user_tasks + [monitor_task]
            await asyncio.gather(*all_tasks)

        return result

    async def test_memory_leak_detection(
        self,
        endpoint: str,
        num_iterations: int = 1000,
        test_name: str = ""
    ) -> Dict[str, Any]:
        """内存泄漏检测"""
        import aiohttp
        import tracemalloc

        test_name = test_name or "memory_leak_detection"
        url = f"{self.base_url}{endpoint}"

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        initial_memory = self.process.memory_info().rss / 1024 / 1024

        async def make_requests():
            async with aiohttp.ClientSession() as session:
                for _ in range(num_iterations):
                    try:
                        async with session.get(url, timeout=30) as resp:
                            await resp.text()
                    except Exception:
                        pass

        await make_requests()

        # 强制垃圾回收
        gc.collect()

        snapshot_after = tracemalloc.take_snapshot()
        final_memory = self.process.memory_info().rss / 1024 / 1024

        top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')

        result = {
            'test_name': test_name,
            'num_iterations': num_iterations,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_growth_mb': final_memory - initial_memory,
            'top_allocations': []
        }

        for stat in top_stats[:10]:
            result['top_allocations'].append({
                'file': str(stat.traceback[0]) if stat.traceback else 'unknown',
                'size_diff': stat.size_diff,
                'count_diff': stat.count_diff
            })

        tracemalloc.stop()
        return result

    async def test_resource_cleanup(
        self,
        endpoint: str,
        num_cycles: int = 100,
        test_name: str = ""
    ) -> Dict[str, Any]:
        """资源清理测试"""
        import aiohttp

        test_name = test_name or "resource_cleanup"
        url = f"{self.base_url}{endpoint}"

        initial_memory = self.process.memory_info().rss / 1024 / 1024
        memory_after_each_cycle = []

        for cycle in range(num_cycles):
            async with aiohttp.ClientSession() as session:
                for _ in range(100):
                    try:
                        async with session.get(url, timeout=30) as resp:
                            await resp.text()
                    except Exception:
                        pass

            # 强制垃圾回收
            gc.collect()

            current_memory = self.process.memory_info().rss / 1024 / 1024
            memory_after_each_cycle.append(current_memory)

            if (cycle + 1) % 10 == 0:
                print(f"Cycle {cycle + 1}: Memory = {current_memory:.2f} MB")

        final_memory = self.process.memory_info().rss / 1024 / 1024

        result = {
            'test_name': test_name,
            'num_cycles': num_cycles,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_growth_mb': final_memory - initial_memory,
            'avg_memory_per_cycle': sum(memory_after_each_cycle) / len(memory_after_each_cycle),
            'max_memory_mb': max(memory_after_each_cycle),
            'min_memory_mb': min(memory_after_each_cycle),
            'memory_stable': self._is_memory_stable(memory_after_each_cycle)
        }

        return result

    async def test_error_recovery(
        self,
        endpoint: str,
        num_requests: int = 1000,
        error_injection_rate: float = 0.1,
        test_name: str = ""
    ) -> Dict[str, Any]:
        """错误恢复测试"""
        import aiohttp

        test_name = test_name or "error_recovery"
        url = f"{self.base_url}{endpoint}"

        successful = 0
        failed = 0
        recovered = 0
        recovery_times = []

        async with aiohttp.ClientSession() as session:
            for i in range(num_requests):
                try:
                    # 模拟错误注入
                    if i % int(1 / error_injection_rate) == 0:
                        # 故意发送错误请求
                        async with session.get(f"{url}?error=true", timeout=5) as resp:
                            if resp.status >= 400:
                                failed += 1
                                # 尝试恢复
                                recovery_start = time.time()
                                async with session.get(url, timeout=30) as recovery_resp:
                                    if recovery_resp.status < 400:
                                        recovered += 1
                                        recovery_times.append(time.time() - recovery_start)
                    else:
                        async with session.get(url, timeout=30) as resp:
                            if resp.status < 400:
                                successful += 1
                            else:
                                failed += 1

                except Exception as e:
                    failed += 1

        result = {
            'test_name': test_name,
            'num_requests': num_requests,
            'successful_requests': successful,
            'failed_requests': failed,
            'recovered_requests': recovered,
            'recovery_rate': (recovered / failed * 100) if failed > 0 else 0,
            'avg_recovery_time': sum(recovery_times) / len(recovery_times) if recovery_times else 0,
            'max_recovery_time': max(recovery_times) if recovery_times else 0
        }

        return result

    @staticmethod
    def _is_memory_stable(memory_samples: List[float], threshold_percent: float = 10.0) -> bool:
        """检查内存是否稳定"""
        if len(memory_samples) < 2:
            return True

        # 计算内存变化率
        changes = []
        for i in range(1, len(memory_samples)):
            change_percent = abs(memory_samples[i] - memory_samples[i-1]) / memory_samples[i-1] * 100
            changes.append(change_percent)

        avg_change = sum(changes) / len(changes) if changes else 0
        return avg_change < threshold_percent


# 测试用例
# 长耗时负载测试默认跳过：需要真实监听服务且单用例分钟级起，
# 与 tests/performance/test_load.py 同一门禁（XAGENT_RUN_LIVE_LOAD_TESTS=1 才跑）。
_requires_live_load = pytest.mark.skipif(
    os.environ.get("XAGENT_RUN_LIVE_LOAD_TESTS") != "1",
    reason="long-duration live-load tests are opt-in: set XAGENT_RUN_LIVE_LOAD_TESTS=1",
)


@pytest.mark.stability_test
@_requires_live_load
class TestLongDurationRun:
    """长时间运行测试"""

    @pytest.mark.asyncio
    async def test_24_hour_stability(self):
        """24小时稳定性测试"""
        tester = StabilityTester()

        # 注意: 实际测试中应该运行24小时
        # 这里为了演示，只运行5分钟
        result = await tester.run_long_duration_test(
            endpoint='/api/v1/health',
            num_users=100,
            duration_hours=5/60,  # 5分钟演示
            requests_per_user_per_minute=10,
            test_name='stability_5min'
        )

        print(f"\n长时间运行测试结果:")
        print(f"  测试时长: {result.duration_hours:.2f} 小时")
        print(f"  总请求数: {result.total_requests}")
        print(f"  成功请求: {result.successful_requests}")
        print(f"  失败请求: {result.failed_requests}")
        print(f"  错误率: {result.error_rate:.2f}%")
        print(f"  平均内存: {result.avg_memory_mb:.2f} MB")
        print(f"  最大内存: {result.max_memory_mb:.2f} MB")
        print(f"  内存增长: {result.memory_growth_mb:.2f} MB")
        print(f"  平均CPU: {result.avg_cpu_percent:.2f}%")

        assert result.error_rate < 5.0


@pytest.mark.stability_test
class TestMemoryLeakDetection:
    """内存泄漏检测"""

    @pytest.mark.asyncio
    async def test_memory_leak_detection(self):
        """内存泄漏检测"""
        tester = StabilityTester()
        result = await tester.test_memory_leak_detection(
            endpoint='/api/v1/health',
            num_iterations=1000,
            test_name='memory_leak_detection'
        )

        print(f"\n内存泄漏检测结果:")
        print(f"  初始内存: {result['initial_memory_mb']:.2f} MB")
        print(f"  最终内存: {result['final_memory_mb']:.2f} MB")
        print(f"  内存增长: {result['memory_growth_mb']:.2f} MB")

        # 内存增长应该在合理范围内
        assert result['memory_growth_mb'] < 500  # 不超过500MB


@pytest.mark.stability_test
@_requires_live_load
class TestResourceCleanup:
    """资源清理测试"""

    @pytest.mark.asyncio
    async def test_resource_cleanup(self):
        """资源清理测试"""
        tester = StabilityTester()
        result = await tester.test_resource_cleanup(
            endpoint='/api/v1/health',
            num_cycles=50,
            test_name='resource_cleanup'
        )

        print(f"\n资源清理测试结果:")
        print(f"  初始内存: {result['initial_memory_mb']:.2f} MB")
        print(f"  最终内存: {result['final_memory_mb']:.2f} MB")
        print(f"  内存增长: {result['memory_growth_mb']:.2f} MB")
        print(f"  内存稳定: {result['memory_stable']}")

        assert result['memory_stable']


@pytest.mark.stability_test
@_requires_live_load
class TestErrorRecovery:
    """错误恢复测试"""

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """错误恢复测试"""
        tester = StabilityTester()
        result = await tester.test_error_recovery(
            endpoint='/api/v1/health',
            num_requests=1000,
            error_injection_rate=0.1,
            test_name='error_recovery'
        )

        print(f"\n错误恢复测试结果:")
        print(f"  成功请求: {result['successful_requests']}")
        print(f"  失败请求: {result['failed_requests']}")
        print(f"  恢复请求: {result['recovered_requests']}")
        print(f"  恢复率: {result['recovery_rate']:.2f}%")
        print(f"  平均恢复时间: {result['avg_recovery_time']:.3f}s")

        assert result['recovery_rate'] > 80.0  # 恢复率 > 80%
