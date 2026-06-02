"""
性能基准测试
测试范围: 响应时间、吞吐量、资源使用、并发能力
"""
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import json
from datetime import datetime


class APIBenchmark:
    """API性能基准测试"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []

    async def benchmark_endpoint(
        self,
        method: str,
        endpoint: str,
        num_requests: int = 100,
        concurrent: int = 10,
        payload: Dict = None
    ) -> Dict[str, Any]:
        """基准测试单个端点"""
        import aiohttp

        results = {
            'endpoint': endpoint,
            'method': method,
            'num_requests': num_requests,
            'concurrent': concurrent,
            'response_times': [],
            'errors': 0,
            'success': 0,
            'status_codes': {}
        }

        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            tasks = []
            for i in range(num_requests):
                if method.upper() == 'GET':
                    task = self._make_get_request(session, url)
                elif method.upper() == 'POST':
                    task = self._make_post_request(session, url, payload)
                else:
                    continue

                tasks.append(task)

                # 控制并发数
                if len(tasks) >= concurrent:
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    for resp in responses:
                        if isinstance(resp, Exception):
                            results['errors'] += 1
                        else:
                            results['response_times'].append(resp['time'])
                            results['success'] += 1
                            status = resp['status']
                            results['status_codes'][status] = results['status_codes'].get(status, 0) + 1

                    tasks = []

            # 处理剩余任务
            if tasks:
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                for resp in responses:
                    if isinstance(resp, Exception):
                        results['errors'] += 1
                    else:
                        results['response_times'].append(resp['time'])
                        results['success'] += 1
                        status = resp['status']
                        results['status_codes'][status] = results['status_codes'].get(status, 0) + 1

        results['total_time'] = time.time() - start_time
        results['throughput'] = results['success'] / results['total_time'] if results['total_time'] > 0 else 0
        results['avg_response_time'] = sum(results['response_times']) / len(results['response_times']) if results['response_times'] else 0
        results['p95_response_time'] = self._calculate_percentile(results['response_times'], 0.95)
        results['p99_response_time'] = self._calculate_percentile(results['response_times'], 0.99)
        results['error_rate'] = (results['errors'] / num_requests * 100) if num_requests > 0 else 0

        self.results.append(results)
        return results

    async def _make_get_request(self, session, url):
        """发送GET请求"""
        try:
            start = time.time()
            async with session.get(url, timeout=30) as resp:
                await resp.text()
                return {
                    'time': time.time() - start,
                    'status': resp.status
                }
        except Exception as e:
            raise e

    async def _make_post_request(self, session, url, payload):
        """发送POST请求"""
        try:
            start = time.time()
            async with session.post(url, json=payload, timeout=30) as resp:
                await resp.text()
                return {
                    'time': time.time() - start,
                    'status': resp.status
                }
        except Exception as e:
            raise e

    @staticmethod
    def _calculate_percentile(values: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        idx = int(len(sorted_values) * percentile)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        if not self.results:
            return {}

        total_requests = sum(r['num_requests'] for r in self.results)
        total_success = sum(r['success'] for r in self.results)
        total_errors = sum(r['errors'] for r in self.results)
        total_time = sum(r['total_time'] for r in self.results)

        return {
            'total_endpoints': len(self.results),
            'total_requests': total_requests,
            'total_success': total_success,
            'total_errors': total_errors,
            'total_time': total_time,
            'overall_throughput': total_success / total_time if total_time > 0 else 0,
            'overall_error_rate': (total_errors / total_requests * 100) if total_requests > 0 else 0,
            'endpoints': self.results
        }


class DatabaseBenchmark:
    """数据库性能基准测试"""

    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string
        self.results = []

    async def benchmark_query(
        self,
        query: str,
        num_iterations: int = 100,
        description: str = ""
    ) -> Dict[str, Any]:
        """基准测试数据库查询"""
        import asyncpg

        results = {
            'description': description,
            'query': query[:100],  # 只保存前100个字符
            'num_iterations': num_iterations,
            'execution_times': [],
            'errors': 0
        }

        try:
            conn = await asyncpg.connect(self.connection_string)

            for _ in range(num_iterations):
                start = time.time()
                try:
                    await conn.fetch(query)
                    results['execution_times'].append(time.time() - start)
                except Exception as e:
                    results['errors'] += 1

            await conn.close()

            if results['execution_times']:
                results['avg_time'] = sum(results['execution_times']) / len(results['execution_times'])
                results['p95_time'] = self._calculate_percentile(results['execution_times'], 0.95)
                results['p99_time'] = self._calculate_percentile(results['execution_times'], 0.99)
                results['min_time'] = min(results['execution_times'])
                results['max_time'] = max(results['execution_times'])

            self.results.append(results)

        except Exception as e:
            results['error'] = str(e)

        return results

    @staticmethod
    def _calculate_percentile(values: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        idx = int(len(sorted_values) * percentile)
        return sorted_values[min(idx, len(sorted_values) - 1)]


class MemoryBenchmark:
    """内存性能基准测试"""

    def __init__(self):
        self.results = []

    def benchmark_memory_usage(
        self,
        operation_func,
        num_iterations: int = 1000,
        description: str = ""
    ) -> Dict[str, Any]:
        """基准测试内存使用"""
        import tracemalloc

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        start_time = time.time()
        for _ in range(num_iterations):
            operation_func()

        snapshot_after = tracemalloc.take_snapshot()
        elapsed_time = time.time() - start_time

        top_stats = snapshot_after.compare_to(snapshot_before, 'lineno')

        results = {
            'description': description,
            'num_iterations': num_iterations,
            'elapsed_time': elapsed_time,
            'time_per_iteration': elapsed_time / num_iterations if num_iterations > 0 else 0,
            'top_allocations': []
        }

        for stat in top_stats[:10]:
            results['top_allocations'].append({
                'file': str(stat.traceback[0]) if stat.traceback else 'unknown',
                'size_diff': stat.size_diff,
                'count_diff': stat.count_diff
            })

        tracemalloc.stop()
        self.results.append(results)
        return results


# 测试用例
@pytest.mark.benchmark
class TestAPIBenchmark:
    """API性能基准测试"""

    @pytest.mark.asyncio
    async def test_health_check_benchmark(self):
        """健康检查端点基准测试"""
        benchmark = APIBenchmark()
        results = await benchmark.benchmark_endpoint(
            method='GET',
            endpoint='/api/v1/health',
            num_requests=1000,
            concurrent=50
        )

        assert results['success'] > 0
        assert results['error_rate'] < 5.0  # 错误率 < 5%
        assert results['avg_response_time'] < 1.0  # 平均响应时间 < 1秒

    @pytest.mark.asyncio
    async def test_list_agents_benchmark(self):
        """列表代理端点基准测试"""
        benchmark = APIBenchmark()
        results = await benchmark.benchmark_endpoint(
            method='GET',
            endpoint='/api/v1/agents',
            num_requests=500,
            concurrent=25
        )

        assert results['success'] > 0
        assert results['error_rate'] < 10.0
        assert results['throughput'] > 10  # 吞吐量 > 10 RPS

    @pytest.mark.asyncio
    async def test_concurrent_requests_benchmark(self):
        """并发请求基准测试"""
        benchmark = APIBenchmark()

        # 测试不同并发级别
        for concurrent in [10, 50, 100, 200]:
            results = await benchmark.benchmark_endpoint(
                method='GET',
                endpoint='/api/v1/health',
                num_requests=500,
                concurrent=concurrent
            )

            print(f"\nConcurrency: {concurrent}")
            print(f"  Throughput: {results['throughput']:.2f} RPS")
            print(f"  Avg Response Time: {results['avg_response_time']:.3f}s")
            print(f"  P95 Response Time: {results['p95_response_time']:.3f}s")
            print(f"  Error Rate: {results['error_rate']:.2f}%")


@pytest.mark.benchmark
class TestDatabaseBenchmark:
    """数据库性能基准测试"""

    @pytest.mark.asyncio
    async def test_simple_query_benchmark(self):
        """简单查询基准测试"""
        benchmark = DatabaseBenchmark()
        results = await benchmark.benchmark_query(
            query="SELECT 1",
            num_iterations=1000,
            description="Simple SELECT query"
        )

        assert results['errors'] == 0 or results['errors'] < 10
        if results['execution_times']:
            assert results['avg_time'] < 0.1  # 平均执行时间 < 100ms


@pytest.mark.benchmark
class TestMemoryBenchmark:
    """内存性能基准测试"""

    def test_list_creation_memory(self):
        """列表创建内存基准测试"""
        benchmark = MemoryBenchmark()

        def create_list():
            return [i for i in range(1000)]

        results = benchmark.benchmark_memory_usage(
            operation_func=create_list,
            num_iterations=1000,
            description="Create list with 1000 elements"
        )

        assert results['time_per_iteration'] < 0.01  # 每次迭代 < 10ms
