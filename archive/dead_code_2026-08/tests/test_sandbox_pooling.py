"""
沙箱池化性能测试 - 测试容器池的性能改进
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import logging

from backend.app.core.execution.execution_manager import ExecutionManager
from backend.app.core.execution.optimized_execution_manager import OptimizedExecutionManager

logger = logging.getLogger(__name__)


class PerformanceTester:
    """性能测试器"""

    def __init__(self):
        self.results: Dict[str, Any] = {}

    async def test_original_execution_manager(
        self,
        num_executions: int = 50,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        测试原始执行管理器的性能

        Args:
            num_executions: 执行次数
            language: 编程语言

        Returns:
            Dict[str, Any]: 测试结果
        """
        logger.info(f"Testing original ExecutionManager with {num_executions} {language} executions")

        manager = ExecutionManager(timeout=30)
        execution_times = []
        errors = 0

        # 测试代码
        if language == "python":
            test_code = """
x = 0
for i in range(100):
    x += i
result = x
"""
        else:  # nodejs
            test_code = """
let x = 0;
for (let i = 0; i < 100; i++) {
    x += i;
}
console.log(x);
"""

        start_time = time.time()

        for i in range(num_executions):
            exec_start = time.time()
            result = await manager.execute(test_code, language=language)
            exec_time = time.time() - exec_start
            execution_times.append(exec_time)

            if not result.get("success"):
                errors += 1

        total_time = time.time() - start_time

        return {
            "manager": "original",
            "language": language,
            "num_executions": num_executions,
            "total_time": total_time,
            "avg_time": statistics.mean(execution_times),
            "min_time": min(execution_times),
            "max_time": max(execution_times),
            "median_time": statistics.median(execution_times),
            "stdev_time": statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            "errors": errors,
            "throughput": num_executions / total_time,
        }

    async def test_optimized_execution_manager(
        self,
        num_executions: int = 50,
        language: str = "python",
        pool_size: int = 10,
    ) -> Dict[str, Any]:
        """
        测试优化的执行管理器的性能

        Args:
            num_executions: 执行次数
            language: 编程语言
            pool_size: 容器池大小

        Returns:
            Dict[str, Any]: 测试结果
        """
        logger.info(f"Testing OptimizedExecutionManager with {num_executions} {language} executions")

        manager = OptimizedExecutionManager(timeout=30, pool_size=pool_size, warmup_enabled=True)
        await manager.initialize()

        execution_times = []
        pool_hits = 0
        errors = 0

        # 测试代码
        if language == "python":
            test_code = """
x = 0
for i in range(100):
    x += i
result = x
"""
        else:  # nodejs
            test_code = """
let x = 0;
for (let i = 0; i < 100; i++) {
    x += i;
}
console.log(x);
"""

        start_time = time.time()

        for i in range(num_executions):
            exec_start = time.time()
            result = await manager.execute(test_code, language=language)
            exec_time = time.time() - exec_start
            execution_times.append(exec_time)

            if result.get("pool_hit"):
                pool_hits += 1

            if not result.get("success"):
                errors += 1

        total_time = time.time() - start_time

        await manager.shutdown()

        return {
            "manager": "optimized",
            "language": language,
            "pool_size": pool_size,
            "num_executions": num_executions,
            "total_time": total_time,
            "avg_time": statistics.mean(execution_times),
            "min_time": min(execution_times),
            "max_time": max(execution_times),
            "median_time": statistics.median(execution_times),
            "stdev_time": statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            "errors": errors,
            "pool_hits": pool_hits,
            "pool_hit_rate": pool_hits / num_executions if num_executions > 0 else 0,
            "throughput": num_executions / total_time,
        }

    async def test_concurrent_executions(
        self,
        num_concurrent: int = 10,
        num_iterations: int = 5,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        测试并发执行性能

        Args:
            num_concurrent: 并发数
            num_iterations: 每个并发的迭代次数
            language: 编程语言

        Returns:
            Dict[str, Any]: 测试结果
        """
        logger.info(f"Testing concurrent executions: {num_concurrent} concurrent, {num_iterations} iterations")

        manager = OptimizedExecutionManager(timeout=30, pool_size=num_concurrent, warmup_enabled=True)
        await manager.initialize()

        # 测试代码
        if language == "python":
            test_code = """
x = 0
for i in range(100):
    x += i
result = x
"""
        else:  # nodejs
            test_code = """
let x = 0;
for (let i = 0; i < 100; i++) {
    x += i;
}
console.log(x);
"""

        async def worker(worker_id: int) -> List[float]:
            times = []
            for i in range(num_iterations):
                exec_start = time.time()
                result = await manager.execute(test_code, language=language)
                exec_time = time.time() - exec_start
                times.append(exec_time)
            return times

        start_time = time.time()

        # 并发执行
        tasks = [worker(i) for i in range(num_concurrent)]
        all_times = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # 展平时间列表
        flat_times = [t for times in all_times for t in times]

        await manager.shutdown()

        return {
            "test": "concurrent",
            "language": language,
            "num_concurrent": num_concurrent,
            "num_iterations": num_iterations,
            "total_executions": num_concurrent * num_iterations,
            "total_time": total_time,
            "avg_time": statistics.mean(flat_times),
            "min_time": min(flat_times),
            "max_time": max(flat_times),
            "median_time": statistics.median(flat_times),
            "throughput": (num_concurrent * num_iterations) / total_time,
        }

    async def test_pool_warmup_effectiveness(
        self,
        pool_size: int = 10,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        测试预热机制的有效性

        Args:
            pool_size: 容器池大小
            language: 编程语言

        Returns:
            Dict[str, Any]: 测试结果
        """
        logger.info(f"Testing pool warmup effectiveness for {language}")

        manager = OptimizedExecutionManager(timeout=30, pool_size=pool_size, warmup_enabled=True)

        # 测试代码
        if language == "python":
            test_code = "x = 1 + 1"
        else:  # nodejs
            test_code = "const x = 1 + 1;"

        # 初始化前的执行时间
        init_start = time.time()
        await manager.initialize()
        init_time = time.time() - init_start

        # 等待预热完成
        await asyncio.sleep(2)

        # 第一批执行（应该使用预热的容器）
        first_batch_times = []
        for i in range(pool_size):
            exec_start = time.time()
            result = await manager.execute(test_code, language=language)
            exec_time = time.time() - exec_start
            first_batch_times.append(exec_time)

        # 第二批执行（应该更快，因为容器已经预热）
        second_batch_times = []
        for i in range(pool_size):
            exec_start = time.time()
            result = await manager.execute(test_code, language=language)
            exec_time = time.time() - exec_start
            second_batch_times.append(exec_time)

        await manager.shutdown()

        return {
            "test": "warmup_effectiveness",
            "language": language,
            "pool_size": pool_size,
            "init_time": init_time,
            "first_batch_avg": statistics.mean(first_batch_times),
            "second_batch_avg": statistics.mean(second_batch_times),
            "improvement": (statistics.mean(first_batch_times) - statistics.mean(second_batch_times)) / statistics.mean(first_batch_times) * 100,
        }

    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有性能测试"""
        logger.info("Starting comprehensive performance tests")

        results = {
            "timestamp": time.time(),
            "tests": {},
        }

        # 测试1: Python执行性能对比
        logger.info("Test 1: Python execution performance comparison")
        original_python = await self.test_original_execution_manager(num_executions=50, language="python")
        optimized_python = await self.test_optimized_execution_manager(num_executions=50, language="python", pool_size=10)

        results["tests"]["python_comparison"] = {
            "original": original_python,
            "optimized": optimized_python,
            "improvement": {
                "avg_time_reduction": (original_python["avg_time"] - optimized_python["avg_time"]) / original_python["avg_time"] * 100,
                "throughput_improvement": (optimized_python["throughput"] - original_python["throughput"]) / original_python["throughput"] * 100,
            },
        }

        # 测试2: Node.js执行性能对比
        logger.info("Test 2: Node.js execution performance comparison")
        original_nodejs = await self.test_original_execution_manager(num_executions=50, language="nodejs")
        optimized_nodejs = await self.test_optimized_execution_manager(num_executions=50, language="nodejs", pool_size=10)

        results["tests"]["nodejs_comparison"] = {
            "original": original_nodejs,
            "optimized": optimized_nodejs,
            "improvement": {
                "avg_time_reduction": (original_nodejs["avg_time"] - optimized_nodejs["avg_time"]) / original_nodejs["avg_time"] * 100,
                "throughput_improvement": (optimized_nodejs["throughput"] - original_nodejs["throughput"]) / original_nodejs["throughput"] * 100,
            },
        }

        # 测试3: 并发执行性能
        logger.info("Test 3: Concurrent execution performance")
        concurrent_python = await self.test_concurrent_executions(num_concurrent=10, num_iterations=5, language="python")
        concurrent_nodejs = await self.test_concurrent_executions(num_concurrent=10, num_iterations=5, language="nodejs")

        results["tests"]["concurrent"] = {
            "python": concurrent_python,
            "nodejs": concurrent_nodejs,
        }

        # 测试4: 预热有效性
        logger.info("Test 4: Warmup effectiveness")
        warmup_python = await self.test_pool_warmup_effectiveness(pool_size=10, language="python")
        warmup_nodejs = await self.test_pool_warmup_effectiveness(pool_size=10, language="nodejs")

        results["tests"]["warmup"] = {
            "python": warmup_python,
            "nodejs": warmup_nodejs,
        }

        return results


async def main():
    """主测试函数"""
    logging.basicConfig(level=logging.INFO)

    tester = PerformanceTester()
    results = await tester.run_all_tests()

    # 打印结果
    print("\n" + "="*80)
    print("PERFORMANCE TEST RESULTS")
    print("="*80)

    # Python对比
    python_comp = results["tests"]["python_comparison"]
    print("\nPython Execution Performance:")
    print(f"  Original avg time: {python_comp['original']['avg_time']:.4f}s")
    print(f"  Optimized avg time: {python_comp['optimized']['avg_time']:.4f}s")
    print(f"  Improvement: {python_comp['improvement']['avg_time_reduction']:.2f}%")
    print(f"  Pool hit rate: {python_comp['optimized']['pool_hit_rate']:.2%}")

    # Node.js对比
    nodejs_comp = results["tests"]["nodejs_comparison"]
    print("\nNode.js Execution Performance:")
    print(f"  Original avg time: {nodejs_comp['original']['avg_time']:.4f}s")
    print(f"  Optimized avg time: {nodejs_comp['optimized']['avg_time']:.4f}s")
    print(f"  Improvement: {nodejs_comp['improvement']['avg_time_reduction']:.2f}%")
    print(f"  Pool hit rate: {nodejs_comp['optimized']['pool_hit_rate']:.2%}")

    # 并发性能
    concurrent = results["tests"]["concurrent"]
    print("\nConcurrent Execution Performance:")
    print(f"  Python throughput: {concurrent['python']['throughput']:.2f} exec/s")
    print(f"  Node.js throughput: {concurrent['nodejs']['throughput']:.2f} exec/s")

    # 预热有效性
    warmup = results["tests"]["warmup"]
    print("\nWarmup Effectiveness:")
    print(f"  Python improvement: {warmup['python']['improvement']:.2f}%")
    print(f"  Node.js improvement: {warmup['nodejs']['improvement']:.2f}%")

    print("\n" + "="*80)

    return results


if __name__ == "__main__":
    asyncio.run(main())
