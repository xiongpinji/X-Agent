"""
压力测试
测试范围: 系统破裂点、资源耗尽、极限并发、大数据量
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
import json
import random
import string


@dataclass
class StressTestResult:
    """压力测试结果"""
    test_name: str
    breaking_point: int  # 系统破裂点
    max_throughput: float
    max_response_time: float
    resource_exhaustion_point: Dict[str, Any]
    errors_at_breaking_point: Dict[str, int]
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_name': self.test_name,
            'breaking_point': self.breaking_point,
            'max_throughput': self.max_throughput,
            'max_response_time': self.max_response_time,
            'resource_exhaustion_point': self.resource_exhaustion_point,
            'errors_at_breaking_point': self.errors_at_breaking_point,
            'timestamp': self.timestamp
        }


class StressTester:
    """压力测试器"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[StressTestResult] = []

    async def find_breaking_point(
        self,
        endpoint: str,
        initial_users: int = 100,
        max_users: int = 50000,
        step_size: int = 100,
        duration_per_step: int = 30,
        error_threshold: float = 50.0,
        test_name: str = ""
    ) -> StressTestResult:
        """找到系统破裂点"""
        import aiohttp

        test_name = test_name or f"breaking_point_{max_users}users"
        url = f"{self.base_url}{endpoint}"

        breaking_point = initial_users
        max_throughput = 0
        max_response_time = 0
        resource_exhaustion = {}
        errors_at_breaking = {}

        current_users = initial_users

        while current_users <= max_users:
            print(f"Testing with {current_users} users...")

            response_times = []
            errors = {}
            successful = 0
            failed = 0

            start_time = time.time()

            async def user_session(user_id: int, session: aiohttp.ClientSession):
                nonlocal successful, failed
                end_time = time.time() + duration_per_step

                while time.time() < end_time:
                    try:
                        req_start = time.time()
                        async with session.get(url, timeout=30) as resp:
                            await resp.text()
                            response_time = time.time() - req_start
                            response_times.append(response_time)

                            if resp.status >= 400:
                                failed += 1
                                error_key = f"HTTP_{resp.status}"
                                errors[error_key] = errors.get(error_key, 0) + 1
                            else:
                                successful += 1

                    except asyncio.TimeoutError:
                        failed += 1
                        errors['TIMEOUT'] = errors.get('TIMEOUT', 0) + 1
                    except Exception as e:
                        failed += 1
                        error_key = type(e).__name__
                        errors[error_key] = errors.get(error_key, 0) + 1

                    await asyncio.sleep(0.01)

            async with aiohttp.ClientSession() as session:
                tasks = [user_session(i, session) for i in range(current_users)]
                await asyncio.gather(*tasks)

            elapsed = time.time() - start_time
            throughput = successful / elapsed if elapsed > 0 else 0
            error_rate = (failed / (successful + failed) * 100) if (successful + failed) > 0 else 0

            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)

            print(f"  Throughput: {throughput:.2f} RPS")
            print(f"  Error Rate: {error_rate:.2f}%")
            print(f"  Avg Response Time: {avg_response_time:.3f}s")

            # 检查是否达到破裂点
            if error_rate > error_threshold:
                breaking_point = current_users
                errors_at_breaking = errors
                resource_exhaustion = {
                    'error_rate': error_rate,
                    'failed_requests': failed,
                    'successful_requests': successful
                }
                break

            max_throughput = max(max_throughput, throughput)
            current_users += step_size

        result = StressTestResult(
            test_name=test_name,
            breaking_point=breaking_point,
            max_throughput=max_throughput,
            max_response_time=max_response_time,
            resource_exhaustion_point=resource_exhaustion,
            errors_at_breaking_point=errors_at_breaking,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

        self.results.append(result)
        return result

    async def test_resource_exhaustion(
        self,
        endpoint: str,
        num_users: int = 10000,
        duration: int = 60,
        test_name: str = ""
    ) -> Dict[str, Any]:
        """资源耗尽测试"""
        import aiohttp
        import psutil

        test_name = test_name or f"resource_exhaustion_{num_users}users"
        url = f"{self.base_url}{endpoint}"

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        response_times = []
        errors = 0
        successful = 0

        start_time = time.time()

        async def user_session(user_id: int, session: aiohttp.ClientSession):
            nonlocal successful, errors
            end_time = time.time() + duration

            while time.time() < end_time:
                try:
                    req_start = time.time()
                    async with session.get(url, timeout=30) as resp:
                        await resp.text()
                        response_time = time.time() - req_start
                        response_times.append(response_time)
                        successful += 1
                except Exception:
                    errors += 1

                await asyncio.sleep(0.01)

        async with aiohttp.ClientSession() as session:
            tasks = [user_session(i, session) for i in range(num_users)]
            await asyncio.gather(*tasks)

        elapsed = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        result = {
            'test_name': test_name,
            'num_users': num_users,
            'duration': duration,
            'successful_requests': successful,
            'failed_requests': errors,
            'throughput': successful / elapsed if elapsed > 0 else 0,
            'error_rate': (errors / (successful + errors) * 100) if (successful + errors) > 0 else 0,
            'initial_memory_mb': initial_memory,
            'final_memory_mb': final_memory,
            'memory_increase_mb': memory_increase,
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0
        }

        return result

    async def test_large_data_volume(
        self,
        endpoint: str,
        data_size_mb: int = 100,
        num_requests: int = 100,
        test_name: str = ""
    ) -> Dict[str, Any]:
        """大数据量测试"""
        import aiohttp

        test_name = test_name or f"large_data_{data_size_mb}mb"
        url = f"{self.base_url}{endpoint}"

        # 生成大数据
        large_data = ''.join(random.choices(string.ascii_letters + string.digits, k=data_size_mb * 1024 * 1024))

        response_times = []
        errors = 0
        successful = 0

        start_time = time.time()

        async def send_large_data(session: aiohttp.ClientSession):
            nonlocal successful, errors
            try:
                req_start = time.time()
                async with session.post(
                    url,
                    data=large_data,
                    timeout=300
                ) as resp:
                    await resp.text()
                    response_time = time.time() - req_start
                    response_times.append(response_time)
                    successful += 1
            except Exception as e:
                errors += 1

        async with aiohttp.ClientSession() as session:
            tasks = [send_large_data(session) for _ in range(num_requests)]
            await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        result = {
            'test_name': test_name,
            'data_size_mb': data_size_mb,
            'num_requests': num_requests,
            'successful_requests': successful,
            'failed_requests': errors,
            'throughput': successful / elapsed if elapsed > 0 else 0,
            'error_rate': (errors / (successful + errors) * 100) if (successful + errors) > 0 else 0,
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0,
            'total_time': elapsed
        }

        return result


# 测试用例
@pytest.mark.stress_test
class TestBreakingPoint:
    """系统破裂点测试"""

    @pytest.mark.asyncio
    async def test_find_breaking_point_health_check(self):
        """找到健康检查端点的破裂点"""
        tester = StressTester()
        result = await tester.find_breaking_point(
            endpoint='/api/v1/health',
            initial_users=100,
            max_users=10000,
            step_size=500,
            duration_per_step=20,
            error_threshold=50.0,
            test_name='breaking_point_health_check'
        )

        print(f"\n系统破裂点测试结果:")
        print(f"  破裂点 (用户数): {result.breaking_point}")
        print(f"  最大吞吐量: {result.max_throughput:.2f} RPS")
        print(f"  最大响应时间: {result.max_response_time:.3f}s")
        print(f"  资源耗尽点: {result.resource_exhaustion_point}")

        assert result.breaking_point > 0

    @pytest.mark.asyncio
    async def test_find_breaking_point_list_agents(self):
        """找到列表代理端点的破裂点"""
        tester = StressTester()
        result = await tester.find_breaking_point(
            endpoint='/api/v1/agents',
            initial_users=100,
            max_users=5000,
            step_size=200,
            duration_per_step=20,
            error_threshold=50.0,
            test_name='breaking_point_list_agents'
        )

        assert result.breaking_point > 0


@pytest.mark.stress_test
class TestResourceExhaustion:
    """资源耗尽测试"""

    @pytest.mark.asyncio
    async def test_memory_exhaustion(self):
        """内存耗尽测试"""
        tester = StressTester()
        result = await tester.test_resource_exhaustion(
            endpoint='/api/v1/health',
            num_users=5000,
            duration=60,
            test_name='memory_exhaustion'
        )

        print(f"\n资源耗尽测试结果:")
        print(f"  初始内存: {result['initial_memory_mb']:.2f} MB")
        print(f"  最终内存: {result['final_memory_mb']:.2f} MB")
        print(f"  内存增长: {result['memory_increase_mb']:.2f} MB")
        print(f"  吞吐量: {result['throughput']:.2f} RPS")
        print(f"  错误率: {result['error_rate']:.2f}%")

        # 内存增长应该在合理范围内
        assert result['memory_increase_mb'] < 1000  # 不超过1GB增长


@pytest.mark.stress_test
class TestLargeDataVolume:
    """大数据量测试"""

    @pytest.mark.asyncio
    async def test_large_payload_handling(self):
        """大数据量处理测试"""
        tester = StressTester()
        result = await tester.test_large_data_volume(
            endpoint='/api/v1/health',
            data_size_mb=10,
            num_requests=10,
            test_name='large_payload_10mb'
        )

        print(f"\n大数据量测试结果:")
        print(f"  数据大小: {result['data_size_mb']} MB")
        print(f"  请求数: {result['num_requests']}")
        print(f"  成功请求: {result['successful_requests']}")
        print(f"  失败请求: {result['failed_requests']}")
        print(f"  平均响应时间: {result['avg_response_time']:.3f}s")
        print(f"  错误率: {result['error_rate']:.2f}%")

        assert result['error_rate'] < 50.0


@pytest.mark.stress_test
class TestConcurrencyLimits:
    """并发限制测试"""

    @pytest.mark.asyncio
    async def test_extreme_concurrency(self):
        """极限并发测试"""
        tester = StressTester()
        result = await tester.test_resource_exhaustion(
            endpoint='/api/v1/health',
            num_users=20000,
            duration=30,
            test_name='extreme_concurrency'
        )

        print(f"\n极限并发测试结果:")
        print(f"  并发用户数: 20000")
        print(f"  吞吐量: {result['throughput']:.2f} RPS")
        print(f"  错误率: {result['error_rate']:.2f}%")
        print(f"  平均响应时间: {result['avg_response_time']:.3f}s")
