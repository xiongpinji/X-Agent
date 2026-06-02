"""
沙箱池化优化 - 示例应用
演示如何集成OptimizedExecutionManager到实际应用中
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from backend.app.core.execution.optimized_execution_manager import OptimizedExecutionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeExecutionService:
    """代码执行服务 - 使用优化的执行管理器"""

    def __init__(self, pool_size: int = 10):
        """初始化服务"""
        self.manager = OptimizedExecutionManager(
            timeout=30,
            pool_size=pool_size,
            warmup_enabled=True
        )
        self.execution_log: list = []

    async def initialize(self):
        """初始化服务"""
        logger.info("Initializing CodeExecutionService")
        await self.manager.initialize()
        logger.info("CodeExecutionService initialized")

    async def execute_python(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        allowed_imports: Optional[list] = None,
    ) -> Dict[str, Any]:
        """执行Python代码"""
        logger.info(f"Executing Python code ({len(code)} chars)")

        result = await self.manager.execute_python(
            code,
            context=context,
            allowed_imports=allowed_imports
        )

        # 记录执行
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "language": "python",
            "success": result.get("success"),
            "execution_time": result.get("execution_time"),
            "pool_hit": result.get("pool_hit"),
        })

        return result

    async def execute_nodejs(
        self,
        code: str,
        modules: Optional[list] = None,
    ) -> Dict[str, Any]:
        """执行Node.js代码"""
        logger.info(f"Executing Node.js code ({len(code)} chars)")

        result = await self.manager.execute_nodejs(code, modules=modules)

        # 记录执行
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "language": "nodejs",
            "success": result.get("success"),
            "execution_time": result.get("execution_time"),
            "pool_hit": result.get("pool_hit"),
        })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pool_stats = self.manager.get_pool_stats()

        return {
            "pool_stats": pool_stats,
            "execution_log_size": len(self.execution_log),
            "recent_executions": self.execution_log[-10:],
        }

    async def shutdown(self):
        """关闭服务"""
        logger.info("Shutting down CodeExecutionService")
        await self.manager.shutdown()
        logger.info("CodeExecutionService shut down")


async def demo_basic_execution():
    """演示基本执行"""
    print("\n" + "="*80)
    print("DEMO 1: Basic Execution")
    print("="*80)

    service = CodeExecutionService(pool_size=5)
    await service.initialize()

    try:
        # 执行Python代码
        print("\nExecuting Python code...")
        py_result = await service.execute_python("""
x = 0
for i in range(10):
    x += i
print(f"Sum: {x}")
""")
        print(f"Result: {py_result['output']}")
        print(f"Execution time: {py_result['execution_time']:.4f}s")
        print(f"Pool hit: {py_result['pool_hit']}")

        # 执行Node.js代码
        print("\nExecuting Node.js code...")
        js_result = await service.execute_nodejs("""
let x = 0;
for (let i = 0; i < 10; i++) {
    x += i;
}
console.log(`Sum: ${x}`);
""")
        print(f"Result: {js_result['output']}")
        print(f"Execution time: {js_result['execution_time']:.4f}s")
        print(f"Pool hit: {js_result['pool_hit']}")

    finally:
        await service.shutdown()


async def demo_concurrent_execution():
    """演示并发执行"""
    print("\n" + "="*80)
    print("DEMO 2: Concurrent Execution")
    print("="*80)

    service = CodeExecutionService(pool_size=10)
    await service.initialize()

    try:
        # 并发执行多个任务
        print("\nExecuting 10 concurrent Python tasks...")

        async def worker(task_id: int):
            code = f"""
result = {task_id} * 2
print(f"Task {task_id}: {{result}}")
"""
            return await service.execute_python(code)

        tasks = [worker(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r.get("success"))
        avg_time = sum(r.get("execution_time", 0) for r in results) / len(results)
        pool_hits = sum(1 for r in results if r.get("pool_hit"))

        print(f"Completed: {success_count}/{len(results)} tasks")
        print(f"Average execution time: {avg_time:.4f}s")
        print(f"Pool hits: {pool_hits}/{len(results)}")

    finally:
        await service.shutdown()


async def demo_performance_comparison():
    """演示性能对比"""
    print("\n" + "="*80)
    print("DEMO 3: Performance Comparison")
    print("="*80)

    service = CodeExecutionService(pool_size=10)
    await service.initialize()

    try:
        # 执行多个任务并收集统计
        print("\nExecuting 20 Python tasks...")

        execution_times = []
        pool_hits = 0

        for i in range(20):
            result = await service.execute_python("x = 1 + 1")
            execution_times.append(result.get("execution_time", 0))
            if result.get("pool_hit"):
                pool_hits += 1

        # 计算统计
        import statistics

        avg_time = statistics.mean(execution_times)
        min_time = min(execution_times)
        max_time = max(execution_times)
        median_time = statistics.median(execution_times)

        print(f"\nExecution Statistics:")
        print(f"  Average: {avg_time*1000:.2f}ms")
        print(f"  Min: {min_time*1000:.2f}ms")
        print(f"  Max: {max_time*1000:.2f}ms")
        print(f"  Median: {median_time*1000:.2f}ms")
        print(f"  Pool hit rate: {pool_hits/20:.1%}")

    finally:
        await service.shutdown()


async def demo_monitoring():
    """演示监控"""
    print("\n" + "="*80)
    print("DEMO 4: Monitoring")
    print("="*80)

    service = CodeExecutionService(pool_size=5)
    await service.initialize()

    try:
        # 执行一些任务
        print("\nExecuting tasks...")
        for i in range(10):
            await service.execute_python("x = 1 + 1")

        # 获取统计信息
        stats = service.get_stats()

        print("\nPool Statistics:")
        py_pool = stats["pool_stats"]["python_pool"]
        print(f"  Total containers: {py_pool['total_containers']}")
        print(f"  Idle containers: {py_pool['idle_containers']}")
        print(f"  Running containers: {py_pool['running_containers']}")
        print(f"  Hit rate: {py_pool['hit_rate']:.1%}")
        print(f"  Avg execution time: {py_pool['avg_execution_time']*1000:.2f}ms")
        print(f"  Throughput: {py_pool['throughput']:.2f} exec/s")

        print("\nRecent Executions:")
        for exec_log in stats["recent_executions"][-5:]:
            print(f"  {exec_log['language']}: {exec_log['execution_time']*1000:.2f}ms "
                  f"(pool_hit={exec_log['pool_hit']})")

    finally:
        await service.shutdown()


async def demo_error_handling():
    """演示错误处理"""
    print("\n" + "="*80)
    print("DEMO 5: Error Handling")
    print("="*80)

    service = CodeExecutionService(pool_size=5)
    await service.initialize()

    try:
        # 执行有错误的代码
        print("\nExecuting code with error...")
        result = await service.execute_python("""
x = 1 / 0  # Division by zero
""")

        if not result.get("success"):
            print(f"Error: {result.get('error')}")
        else:
            print(f"Output: {result.get('output')}")

        # 执行禁止的操作
        print("\nExecuting code with forbidden operation...")
        result = await service.execute_python("""
import os
os.system('ls')
""")

        if not result.get("success"):
            print(f"Error: {result.get('error')}")
        else:
            print(f"Output: {result.get('output')}")

    finally:
        await service.shutdown()


async def main():
    """运行所有演示"""
    print("\n" + "="*80)
    print("X-Agent Sandbox Pooling Optimization - Demo Application")
    print("="*80)

    # 运行演示
    await demo_basic_execution()
    await demo_concurrent_execution()
    await demo_performance_comparison()
    await demo_monitoring()
    await demo_error_handling()

    print("\n" + "="*80)
    print("All demos completed!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
