"""
X-Agent 性能测试套件

测试覆盖:
1. API响应时间
2. 数据库查询性能
3. 缓存效率
4. 并发处理能力
5. 内存使用
"""

import asyncio
import time
import logging
from typing import Any, Callable
import random
import string

logger = logging.getLogger(__name__)


class PerformanceTestSuite:
    """性能测试套件"""

    def __init__(self):
        self.results = {}

    async def test_api_response_time(
        self,
        api_func: Callable,
        iterations: int = 100,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """测试API响应时间"""
        logger.info(f"测试API响应时间 ({iterations}次迭代)...")

        times = []
        for _ in range(iterations):
            start = time.time()
            try:
                await api_func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                times.append(duration)
            except Exception as e:
                logger.error(f"API调用失败: {e}")

        if not times:
            return {"error": "No successful calls"}

        sorted_times = sorted(times)
        result = {
            "iterations": iterations,
            "avg_ms": round(sum(times) / len(times), 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "p50_ms": round(sorted_times[int(len(sorted_times) * 0.50)], 2),
            "p95_ms": round(sorted_times[int(len(sorted_times) * 0.95)], 2),
            "p99_ms": round(sorted_times[int(len(sorted_times) * 0.99)], 2),
            "target_met": round(sorted_times[int(len(sorted_times) * 0.95)], 2) < 100,
        }

        logger.info(f"API响应时间测试完成: P95={result['p95_ms']}ms")
        return result

    async def test_database_query_performance(
        self,
        query_func: Callable,
        iterations: int = 100,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """测试数据库查询性能"""
        logger.info(f"测试数据库查询性能 ({iterations}次迭代)...")

        times = []
        for _ in range(iterations):
            start = time.time()
            try:
                await query_func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                times.append(duration)
            except Exception as e:
                logger.error(f"查询失败: {e}")

        if not times:
            return {"error": "No successful queries"}

        sorted_times = sorted(times)
        result = {
            "iterations": iterations,
            "avg_ms": round(sum(times) / len(times), 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "p50_ms": round(sorted_times[int(len(sorted_times) * 0.50)], 2),
            "p95_ms": round(sorted_times[int(len(sorted_times) * 0.95)], 2),
            "p99_ms": round(sorted_times[int(len(sorted_times) * 0.99)], 2),
            "target_met": round(sorted_times[int(len(sorted_times) * 0.95)], 2) < 50,
        }

        logger.info(f"数据库查询性能测试完成: P95={result['p95_ms']}ms")
        return result

    async def test_cache_hit_rate(
        self,
        cache_get: Callable,
        cache_set: Callable,
        iterations: int = 1000,
    ) -> dict[str, Any]:
        """测试缓存命中率"""
        logger.info(f"测试缓存命中率 ({iterations}次迭代)...")

        # 预热缓存
        for i in range(100):
            key = f"test_key_{i % 10}"
            await cache_set(key, f"value_{i}", ttl_seconds=3600)

        # 测试命中率
        hits = 0
        misses = 0
        for i in range(iterations):
            key = f"test_key_{i % 10}"
            value = await cache_get(key)
            if value is not None:
                hits += 1
            else:
                misses += 1

        hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0

        result = {
            "iterations": iterations,
            "hits": hits,
            "misses": misses,
            "hit_rate_percent": round(hit_rate, 2),
            "target_met": hit_rate > 90,
        }

        logger.info(f"缓存命中率测试完成: {result['hit_rate_percent']}%")
        return result

    async def test_concurrent_requests(
        self,
        api_func: Callable,
        concurrent_count: int = 100,
        duration_seconds: int = 10,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """测试并发处理能力"""
        logger.info(f"测试并发处理 ({concurrent_count}并发, {duration_seconds}秒)...")

        start_time = time.time()
        request_count = 0
        error_count = 0
        response_times = []

        async def make_request():
            nonlocal request_count, error_count
            try:
                req_start = time.time()
                await api_func(*args, **kwargs)
                duration = (time.time() - req_start) * 1000
                response_times.append(duration)
                request_count += 1
            except Exception as e:
                error_count += 1
                logger.debug(f"请求失败: {e}")

        # 创建并发任务
        tasks = []
        while time.time() - start_time < duration_seconds:
            # 保持并发数
            while len(tasks) < concurrent_count:
                task = asyncio.create_task(make_request())
                tasks.append(task)

            # 等待任何任务完成
            done, tasks = await asyncio.wait(
                tasks,
                timeout=0.1,
                return_when=asyncio.FIRST_COMPLETED,
            )

        # 等待所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time
        rps = request_count / elapsed

        result = {
            "concurrent_count": concurrent_count,
            "duration_seconds": duration_seconds,
            "total_requests": request_count,
            "errors": error_count,
            "rps": round(rps, 2),
            "avg_response_ms": round(
                sum(response_times) / len(response_times), 2
            ) if response_times else 0,
            "target_met": rps > 1000,
        }

        logger.info(f"并发处理测试完成: {result['rps']} RPS")
        return result

    async def test_memory_usage(
        self,
        operation_func: Callable,
        iterations: int = 1000,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        """测试内存使用"""
        logger.info(f"测试内存使用 ({iterations}次迭代)...")

        import psutil
        import gc

        process = psutil.Process()

        # 获取初始内存
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024

        # 执行操作
        for _ in range(iterations):
            try:
                await operation_func(*args, **kwargs)
            except Exception as e:
                logger.debug(f"操作失败: {e}")

        # 获取最终内存
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024

        result = {
            "iterations": iterations,
            "initial_memory_mb": round(initial_memory, 2),
            "final_memory_mb": round(final_memory, 2),
            "memory_increase_mb": round(final_memory - initial_memory, 2),
            "target_met": final_memory < 500,
        }

        logger.info(f"内存使用测试完成: {result['final_memory_mb']}MB")
        return result

    async def run_all_tests(
        self,
        api_func: Callable,
        query_func: Callable,
        cache_get: Callable,
        cache_set: Callable,
        operation_func: Callable,
    ) -> dict[str, Any]:
        """运行所有性能测试"""
        logger.info("开始运行性能测试套件...")

        results = {
            "api_response_time": await self.test_api_response_time(api_func),
            "database_query": await self.test_database_query_performance(query_func),
            "cache_hit_rate": await self.test_cache_hit_rate(cache_get, cache_set),
            "concurrent_requests": await self.test_concurrent_requests(api_func),
            "memory_usage": await self.test_memory_usage(operation_func),
        }

        self.results = results
        return results

    def generate_report(self) -> str:
        """生成测试报告"""
        report = []
        report.append("=" * 80)
        report.append("X-AGENT 性能测试报告")
        report.append("=" * 80)
        report.append("")

        if not self.results:
            report.append("暂无测试结果")
            return "\n".join(report)

        # API响应时间
        if "api_response_time" in self.results:
            api_result = self.results["api_response_time"]
            report.append("API响应时间测试:")
            report.append(f"  平均: {api_result.get('avg_ms', 'N/A')}ms")
            report.append(f"  P95: {api_result.get('p95_ms', 'N/A')}ms (目标: <100ms)")
            report.append(f"  P99: {api_result.get('p99_ms', 'N/A')}ms")
            report.append(f"  目标达成: {'✓' if api_result.get('target_met') else '✗'}")
            report.append("")

        # 数据库查询
        if "database_query" in self.results:
            db_result = self.results["database_query"]
            report.append("数据库查询性能测试:")
            report.append(f"  平均: {db_result.get('avg_ms', 'N/A')}ms")
            report.append(f"  P95: {db_result.get('p95_ms', 'N/A')}ms (目标: <50ms)")
            report.append(f"  P99: {db_result.get('p99_ms', 'N/A')}ms")
            report.append(f"  目标达成: {'✓' if db_result.get('target_met') else '✗'}")
            report.append("")

        # 缓存命中率
        if "cache_hit_rate" in self.results:
            cache_result = self.results["cache_hit_rate"]
            report.append("缓存命中率测试:")
            report.append(f"  命中率: {cache_result.get('hit_rate_percent', 'N/A')}% (目标: >90%)")
            report.append(f"  命中: {cache_result.get('hits', 'N/A')}")
            report.append(f"  未命中: {cache_result.get('misses', 'N/A')}")
            report.append(f"  目标达成: {'✓' if cache_result.get('target_met') else '✗'}")
            report.append("")

        # 并发处理
        if "concurrent_requests" in self.results:
            concurrent_result = self.results["concurrent_requests"]
            report.append("并发处理能力测试:")
            report.append(f"  RPS: {concurrent_result.get('rps', 'N/A')} (目标: >1000)")
            report.append(f"  总请求: {concurrent_result.get('total_requests', 'N/A')}")
            report.append(f"  错误: {concurrent_result.get('errors', 'N/A')}")
            report.append(f"  平均响应: {concurrent_result.get('avg_response_ms', 'N/A')}ms")
            report.append(f"  目标达成: {'✓' if concurrent_result.get('target_met') else '✗'}")
            report.append("")

        # 内存使用
        if "memory_usage" in self.results:
            memory_result = self.results["memory_usage"]
            report.append("内存使用测试:")
            report.append(f"  初始: {memory_result.get('initial_memory_mb', 'N/A')}MB")
            report.append(f"  最终: {memory_result.get('final_memory_mb', 'N/A')}MB (目标: <500MB)")
            report.append(f"  增长: {memory_result.get('memory_increase_mb', 'N/A')}MB")
            report.append(f"  目标达成: {'✓' if memory_result.get('target_met') else '✗'}")
            report.append("")

        # 总体评分
        report.append("总体评分:")
        targets_met = sum(
            1 for result in self.results.values()
            if result.get("target_met", False)
        )
        total_tests = len(self.results)
        score = (targets_met / total_tests * 100) if total_tests > 0 else 0
        report.append(f"  {targets_met}/{total_tests} 目标达成 ({score:.0f}%)")
        report.append("")

        report.append("=" * 80)
        return "\n".join(report)


# 使用示例
"""
async def main():
    suite = PerformanceTestSuite()

    # 定义测试函数
    async def test_api():
        # 模拟API调用
        await asyncio.sleep(0.01)

    async def test_query():
        # 模拟数据库查询
        await asyncio.sleep(0.02)

    async def test_cache_get(key):
        # 模拟缓存获取
        await asyncio.sleep(0.001)
        return "value"

    async def test_cache_set(key, value, ttl_seconds):
        # 模拟缓存设置
        await asyncio.sleep(0.001)

    async def test_operation():
        # 模拟操作
        await asyncio.sleep(0.005)

    # 运行测试
    results = await suite.run_all_tests(
        api_func=test_api,
        query_func=test_query,
        cache_get=test_cache_get,
        cache_set=test_cache_set,
        operation_func=test_operation,
    )

    # 生成报告
    report = suite.generate_report()
    print(report)

if __name__ == "__main__":
    asyncio.run(main())
"""
