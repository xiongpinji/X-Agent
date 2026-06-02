"""Performance testing and benchmarking for code execution sandboxes."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from backend.app.core.sandbox import (
    ExecutionLanguage,
    get_sandbox_manager,
    SecurityPolicy,
)

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""

    test_name: str
    language: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    success_rate: float
    throughput_ops_per_sec: float


class SandboxBenchmark:
    """Benchmark suite for sandbox performance."""

    # Test cases
    PYTHON_TESTS = {
        "simple_arithmetic": """
result = 1 + 2 + 3 + 4 + 5
_result = result
""",
        "list_operations": """
data = [1, 2, 3, 4, 5]
result = sum(data)
_result = result
""",
        "string_operations": """
text = "Hello, World!"
result = text.upper()
_result = result
""",
        "dict_operations": """
data = {"a": 1, "b": 2, "c": 3}
result = sum(data.values())
_result = result
""",
        "json_parsing": """
import json
data = '{"name": "test", "value": 42}'
parsed = json.loads(data)
_result = parsed["value"]
""",
        "math_operations": """
import math
result = math.sqrt(16) + math.sin(0) + math.cos(0)
_result = result
""",
        "list_comprehension": """
result = [x * 2 for x in range(100)]
_result = len(result)
""",
        "nested_loops": """
result = 0
for i in range(10):
    for j in range(10):
        result += i * j
_result = result
""",
        "function_definition": """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

_result = fibonacci(10)
""",
        "class_definition": """
class Calculator:
    def add(self, a, b):
        return a + b
    def multiply(self, a, b):
        return a * b

calc = Calculator()
_result = calc.add(5, 3) + calc.multiply(2, 4)
""",
    }

    JAVASCRIPT_TESTS = {
        "simple_arithmetic": """
const result = 1 + 2 + 3 + 4 + 5;
_result = result;
""",
        "array_operations": """
const data = [1, 2, 3, 4, 5];
const result = data.reduce((a, b) => a + b, 0);
_result = result;
""",
        "string_operations": """
const text = "Hello, World!";
const result = text.toUpperCase();
_result = result;
""",
        "object_operations": """
const data = {a: 1, b: 2, c: 3};
const result = Object.values(data).reduce((a, b) => a + b, 0);
_result = result;
""",
        "json_parsing": """
const data = '{"name": "test", "value": 42}';
const parsed = JSON.parse(data);
_result = parsed.value;
""",
        "math_operations": """
const result = Math.sqrt(16) + Math.sin(0) + Math.cos(0);
_result = result;
""",
        "array_map": """
const result = Array.from({length: 100}, (_, i) => i * 2);
_result = result.length;
""",
        "nested_loops": """
let result = 0;
for (let i = 0; i < 10; i++) {
    for (let j = 0; j < 10; j++) {
        result += i * j;
    }
}
_result = result;
""",
        "function_definition": """
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2);
}
_result = fibonacci(10);
""",
        "class_definition": """
class Calculator {
    add(a, b) { return a + b; }
    multiply(a, b) { return a * b; }
}
const calc = new Calculator();
_result = calc.add(5, 3) + calc.multiply(2, 4);
""",
    }

    def __init__(self):
        """Initialize benchmark suite."""
        self.results: list[BenchmarkResult] = []

    async def run_python_benchmarks(
        self,
        iterations: int = 10,
        security_policy: Optional[SecurityPolicy] = None,
    ) -> list[BenchmarkResult]:
        """Run Python benchmarks.

        Args:
            iterations: Number of iterations per test
            security_policy: Security policy

        Returns:
            List of benchmark results
        """
        manager = await get_sandbox_manager(security_policy=security_policy)
        results = []

        for test_name, code in self.PYTHON_TESTS.items():
            logger.info(f"Running Python benchmark: {test_name}")

            times = []
            successes = 0

            for _ in range(iterations):
                start = time.perf_counter()
                result = await manager.execute(code, language=ExecutionLanguage.PYTHON)
                elapsed = (time.perf_counter() - start) * 1000

                if result.success:
                    successes += 1
                    times.append(elapsed)
                else:
                    logger.warning(f"Python test {test_name} failed: {result.error_message}")

            if times:
                benchmark = BenchmarkResult(
                    test_name=test_name,
                    language="python",
                    iterations=len(times),
                    total_time_ms=sum(times),
                    avg_time_ms=sum(times) / len(times),
                    min_time_ms=min(times),
                    max_time_ms=max(times),
                    success_rate=successes / iterations,
                    throughput_ops_per_sec=1000 / (sum(times) / len(times)),
                )
                results.append(benchmark)
                self.results.append(benchmark)

        return results

    async def run_javascript_benchmarks(
        self,
        iterations: int = 10,
        security_policy: Optional[SecurityPolicy] = None,
    ) -> list[BenchmarkResult]:
        """Run JavaScript benchmarks.

        Args:
            iterations: Number of iterations per test
            security_policy: Security policy

        Returns:
            List of benchmark results
        """
        manager = await get_sandbox_manager(security_policy=security_policy)
        results = []

        for test_name, code in self.JAVASCRIPT_TESTS.items():
            logger.info(f"Running JavaScript benchmark: {test_name}")

            times = []
            successes = 0

            for _ in range(iterations):
                start = time.perf_counter()
                result = await manager.execute(code, language=ExecutionLanguage.NODEJS)
                elapsed = (time.perf_counter() - start) * 1000

                if result.success:
                    successes += 1
                    times.append(elapsed)
                else:
                    logger.warning(f"JavaScript test {test_name} failed: {result.error_message}")

            if times:
                benchmark = BenchmarkResult(
                    test_name=test_name,
                    language="javascript",
                    iterations=len(times),
                    total_time_ms=sum(times),
                    avg_time_ms=sum(times) / len(times),
                    min_time_ms=min(times),
                    max_time_ms=max(times),
                    success_rate=successes / iterations,
                    throughput_ops_per_sec=1000 / (sum(times) / len(times)),
                )
                results.append(benchmark)
                self.results.append(benchmark)

        return results

    async def run_all_benchmarks(
        self,
        iterations: int = 10,
        security_policy: Optional[SecurityPolicy] = None,
    ) -> dict[str, Any]:
        """Run all benchmarks.

        Args:
            iterations: Number of iterations per test
            security_policy: Security policy

        Returns:
            Dictionary with all benchmark results
        """
        logger.info("Starting comprehensive sandbox benchmarks")

        python_results = await self.run_python_benchmarks(iterations, security_policy)
        javascript_results = await self.run_javascript_benchmarks(iterations, security_policy)

        return {
            "python": [
                {
                    "test_name": r.test_name,
                    "iterations": r.iterations,
                    "total_time_ms": r.total_time_ms,
                    "avg_time_ms": round(r.avg_time_ms, 2),
                    "min_time_ms": round(r.min_time_ms, 2),
                    "max_time_ms": round(r.max_time_ms, 2),
                    "success_rate": round(r.success_rate, 2),
                    "throughput_ops_per_sec": round(r.throughput_ops_per_sec, 2),
                }
                for r in python_results
            ],
            "javascript": [
                {
                    "test_name": r.test_name,
                    "iterations": r.iterations,
                    "total_time_ms": r.total_time_ms,
                    "avg_time_ms": round(r.avg_time_ms, 2),
                    "min_time_ms": round(r.min_time_ms, 2),
                    "max_time_ms": round(r.max_time_ms, 2),
                    "success_rate": round(r.success_rate, 2),
                    "throughput_ops_per_sec": round(r.throughput_ops_per_sec, 2),
                }
                for r in javascript_results
            ],
            "summary": {
                "total_tests": len(python_results) + len(javascript_results),
                "python_avg_time_ms": round(
                    sum(r.avg_time_ms for r in python_results) / len(python_results), 2
                )
                if python_results
                else 0,
                "javascript_avg_time_ms": round(
                    sum(r.avg_time_ms for r in javascript_results) / len(javascript_results), 2
                )
                if javascript_results
                else 0,
            },
        }

    def print_results(self) -> None:
        """Print benchmark results in a formatted table."""
        if not self.results:
            print("No benchmark results available")
            return

        print("\n" + "=" * 100)
        print("SANDBOX PERFORMANCE BENCHMARK RESULTS")
        print("=" * 100)

        for language in ["python", "javascript"]:
            lang_results = [r for r in self.results if r.language == language]
            if not lang_results:
                continue

            print(f"\n{language.upper()} BENCHMARKS:")
            print("-" * 100)
            print(
                f"{'Test Name':<30} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'Ops/sec':<12} {'Success':<10}"
            )
            print("-" * 100)

            for result in lang_results:
                print(
                    f"{result.test_name:<30} {result.avg_time_ms:<12.2f} {result.min_time_ms:<12.2f} "
                    f"{result.max_time_ms:<12.2f} {result.throughput_ops_per_sec:<12.2f} {result.success_rate:<10.0%}"
                )

        print("\n" + "=" * 100)
