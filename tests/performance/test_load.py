"""
负载测试
测试范围: 正常负载、高负载、峰值负载、持续负载
"""
import pytest
import asyncio
import time
from typing import List, Dict, Any
from dataclasses import dataclass, field
import json
from datetime import datetime, timedelta


@dataclass
class LoadTestResult:
    """负载测试结果"""
    test_name: str
    num_users: int
    duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    response_times: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = field(default_factory=datetime.now)

    @property
    def throughput(self) -> float:
        """吞吐量 (请求/秒)"""
        return self.successful_requests / self.duration if self.duration > 0 else 0

    @property
    def error_rate(self) -> float:
        """错误率 (%)"""
        total = self.successful_requests + self.failed_requests
        return (self.failed_requests / total * 100) if total > 0 else 0

    @property
    def avg_response_time(self) -> float:
        """平均响应时间"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0

    @property
    def p95_response_time(self) -> float:
        """P95响应时间"""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]

    @property
    def p99_response_time(self) -> float:
        """P99响应时间"""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx]

    @property
    def max_response_time(self) -> float:
        """最大响应时间"""
        return max(self.response_times) if self.response_times else 0

    @property
    def min_response_time(self) -> float:
        """最小响应时间"""
        return min(self.response_times) if self.response_times else 0


class LoadTester:
    """负载测试器"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[LoadTestResult] = []

    async def run_load_test(
        self,
        endpoint: str,
        num_users: int,
        duration_seconds: int,
        requests_per_user: int = None,
        test_name: str = ""
    ) -> LoadTestResult:
        """运行负载测试"""
        import aiohttp

        test_name = test_name or f"load_test_{num_users}users"
        url = f"{self.base_url}{endpoint}"

        result = LoadTestResult(
            test_name=test_name,
            num_users=num_users,
            duration=duration_seconds,
            total_requests=0,
            successful_requests=0,
            failed_requests=0
        )

        start_time = time.time()
        result.start_time = datetime.now()

        async def user_session(user_id: int, session: aiohttp.ClientSession):
            """单个用户会话"""
            request_count = 0
            while time.time() - start_time < duration_seconds:
                try:
                    req_start = time.time()
                    async with session.get(url, timeout=30) as resp:
                        await resp.text()
                        response_time = time.time() - req_start
                        result.response_times.append(response_time)
                        result.successful_requests += 1

                        if resp.status >= 400:
                            error_key = f"HTTP_{resp.status}"
                            result.errors[error_key] = result.errors.get(error_key, 0) + 1
                            result.failed_requests += 1

                except asyncio.TimeoutError:
                    result.errors['TIMEOUT'] = result.errors.get('TIMEOUT', 0) + 1
                    result.failed_requests += 1
                except Exception as e:
                    error_key = type(e).__name__
                    result.errors[error_key] = result.errors.get(error_key, 0) + 1
                    result.failed_requests += 1

                request_count += 1
                result.total_requests += 1

                if requests_per_user and request_count >= requests_per_user:
                    break

                await asyncio.sleep(0.01)  # 避免过度占用

        # 运行负载测试
        async with aiohttp.ClientSession() as session:
            tasks = [user_session(i, session) for i in range(num_users)]
            await asyncio.gather(*tasks)

        result.end_time = datetime.now()
        self.results.append(result)
        return result

    async def run_ramp_up_test(
        self,
        endpoint: str,
        max_users: int,
        ramp_up_duration: int,
        test_duration: int,
        test_name: str = ""
    ) -> List[LoadTestResult]:
        """运行渐进式负载测试"""
        import aiohttp

        test_name = test_name or f"ramp_up_test_{max_users}users"
        url = f"{self.base_url}{endpoint}"
        results = []

        users_per_step = max(1, max_users // 10)
        step_duration = ramp_up_duration // 10

        current_users = 0
        start_time = time.time()

        async def user_session(user_id: int, session: aiohttp.ClientSession, end_time: float):
            """单个用户会话"""
            while time.time() < end_time:
                try:
                    req_start = time.time()
                    async with session.get(url, timeout=30) as resp:
                        await resp.text()
                        response_time = time.time() - req_start
                        # 记录响应时间
                except Exception:
                    pass

                await asyncio.sleep(0.01)

        async with aiohttp.ClientSession() as session:
            tasks = []
            test_end_time = time.time() + ramp_up_duration + test_duration

            for step in range(11):
                current_users = min(step * users_per_step, max_users)

                # 添加新用户
                for i in range(current_users - len(tasks)):
                    task = user_session(len(tasks) + i, session, test_end_time)
                    tasks.append(asyncio.create_task(task))

                # 等待步骤持续时间
                await asyncio.sleep(step_duration)

                # 记录当前状态
                result = LoadTestResult(
                    test_name=f"{test_name}_step_{step}",
                    num_users=current_users,
                    duration=step_duration,
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0
                )
                results.append(result)

            # 等待所有任务完成
            await asyncio.gather(*tasks)

        return results

    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        if not self.results:
            return {}

        return {
            'total_tests': len(self.results),
            'tests': [
                {
                    'name': r.test_name,
                    'num_users': r.num_users,
                    'duration': r.duration,
                    'total_requests': r.total_requests,
                    'successful_requests': r.successful_requests,
                    'failed_requests': r.failed_requests,
                    'throughput': r.throughput,
                    'error_rate': r.error_rate,
                    'avg_response_time': r.avg_response_time,
                    'p95_response_time': r.p95_response_time,
                    'p99_response_time': r.p99_response_time,
                    'max_response_time': r.max_response_time,
                    'min_response_time': r.min_response_time,
                    'errors': r.errors
                }
                for r in self.results
            ]
        }


# 测试用例
@pytest.mark.load_test
class TestNormalLoad:
    """正常负载测试 (100用户)"""

    @pytest.mark.asyncio
    async def test_normal_load_health_check(self):
        """正常负载: 健康检查端点"""
        tester = LoadTester()
        result = await tester.run_load_test(
            endpoint='/api/v1/health',
            num_users=100,
            duration_seconds=60,
            test_name='normal_load_health_check'
        )

        print(f"\n正常负载测试结果:")
        print(f"  用户数: {result.num_users}")
        print(f"  总请求数: {result.total_requests}")
        print(f"  成功请求: {result.successful_requests}")
        print(f"  失败请求: {result.failed_requests}")
        print(f"  吞吐量: {result.throughput:.2f} RPS")
        print(f"  错误率: {result.error_rate:.2f}%")
        print(f"  平均响应时间: {result.avg_response_time:.3f}s")
        print(f"  P95响应时间: {result.p95_response_time:.3f}s")
        print(f"  P99响应时间: {result.p99_response_time:.3f}s")

        assert result.error_rate < 5.0  # 错误率 < 5%
        assert result.throughput > 50  # 吞吐量 > 50 RPS

    @pytest.mark.asyncio
    async def test_normal_load_list_agents(self):
        """正常负载: 列表代理端点"""
        tester = LoadTester()
        result = await tester.run_load_test(
            endpoint='/api/v1/agents',
            num_users=100,
            duration_seconds=60,
            test_name='normal_load_list_agents'
        )

        assert result.error_rate < 10.0
        assert result.throughput > 20


@pytest.mark.load_test
class TestHighLoad:
    """高负载测试 (1000用户)"""

    @pytest.mark.asyncio
    async def test_high_load_health_check(self):
        """高负载: 健康检查端点"""
        tester = LoadTester()
        result = await tester.run_load_test(
            endpoint='/api/v1/health',
            num_users=1000,
            duration_seconds=60,
            test_name='high_load_health_check'
        )

        print(f"\n高负载测试结果:")
        print(f"  用户数: {result.num_users}")
        print(f"  吞吐量: {result.throughput:.2f} RPS")
        print(f"  错误率: {result.error_rate:.2f}%")
        print(f"  平均响应时间: {result.avg_response_time:.3f}s")
        print(f"  P95响应时间: {result.p95_response_time:.3f}s")

        assert result.error_rate < 15.0  # 错误率 < 15%


@pytest.mark.load_test
class TestPeakLoad:
    """峰值负载测试 (5000用户)"""

    @pytest.mark.asyncio
    async def test_peak_load_health_check(self):
        """峰值负载: 健康检查端点"""
        tester = LoadTester()
        result = await tester.run_load_test(
            endpoint='/api/v1/health',
            num_users=5000,
            duration_seconds=30,
            test_name='peak_load_health_check'
        )

        print(f"\n峰值负载测试结果:")
        print(f"  用户数: {result.num_users}")
        print(f"  吞吐量: {result.throughput:.2f} RPS")
        print(f"  错误率: {result.error_rate:.2f}%")
        print(f"  平均响应时间: {result.avg_response_time:.3f}s")

        # 峰值负载下允许更高的错误率
        assert result.error_rate < 30.0


@pytest.mark.load_test
class TestSustainedLoad:
    """持续负载测试 (24小时)"""

    @pytest.mark.asyncio
    async def test_sustained_load_24h(self):
        """持续负载: 24小时测试"""
        tester = LoadTester()

        # 注意: 实际测试中应该运行24小时
        # 这里为了演示，只运行5分钟
        result = await tester.run_load_test(
            endpoint='/api/v1/health',
            num_users=500,
            duration_seconds=300,  # 5分钟演示
            test_name='sustained_load_5min'
        )

        print(f"\n持续负载测试结果:")
        print(f"  用户数: {result.num_users}")
        print(f"  持续时间: {result.duration}秒")
        print(f"  吞吐量: {result.throughput:.2f} RPS")
        print(f"  错误率: {result.error_rate:.2f}%")

        assert result.error_rate < 10.0


@pytest.mark.load_test
class TestRampUpLoad:
    """渐进式负载测试"""

    @pytest.mark.asyncio
    async def test_ramp_up_to_peak(self):
        """渐进式负载: 从0到5000用户"""
        tester = LoadTester()
        results = await tester.run_ramp_up_test(
            endpoint='/api/v1/health',
            max_users=5000,
            ramp_up_duration=300,  # 5分钟渐进
            test_duration=60,  # 1分钟稳定
            test_name='ramp_up_to_peak'
        )

        print(f"\n渐进式负载测试结果:")
        print(f"  总步骤数: {len(results)}")
        for i, result in enumerate(results):
            print(f"  步骤 {i}: {result.num_users} 用户")
