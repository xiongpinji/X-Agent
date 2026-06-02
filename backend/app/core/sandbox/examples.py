"""Usage examples for X-Agent code execution sandbox."""

import asyncio
from backend.app.core.sandbox import (
    ExecutionLanguage,
    SecurityPolicy,
    get_sandbox_manager,
    execute_code,
    validate_python_code,
    validate_javascript_code,
)
from backend.app.core.sandbox.code_execution_tool import get_code_execution_tool
from backend.app.core.sandbox.benchmark import SandboxBenchmark


async def example_basic_python_execution():
    """Example: Basic Python code execution."""
    print("\n=== Example 1: Basic Python Execution ===")

    code = """
import math

# Calculate circle area
radius = 5
area = math.pi * radius ** 2
_result = area
"""

    result = await execute_code(code, language=ExecutionLanguage.PYTHON)
    print(f"Success: {result.success}")
    print(f"Result: {result.return_value}")
    print(f"Execution time: {result.execution_time_ms:.2f}ms")


async def example_basic_javascript_execution():
    """Example: Basic JavaScript code execution."""
    print("\n=== Example 2: Basic JavaScript Execution ===")

    code = """
// Calculate circle area
const radius = 5;
const area = Math.PI * radius * radius;
_result = area;
"""

    result = await execute_code(code, language=ExecutionLanguage.NODEJS)
    print(f"Success: {result.success}")
    print(f"Result: {result.return_value}")
    print(f"Execution time: {result.execution_time_ms:.2f}ms")


async def example_python_with_variables():
    """Example: Python execution with variable injection."""
    print("\n=== Example 3: Python with Variables ===")

    code = """
# Use injected variables
total = sum(numbers)
average = total / len(numbers)
_result = {"total": total, "average": average}
"""

    variables = {"numbers": [1, 2, 3, 4, 5]}

    result = await execute_code(
        code, language=ExecutionLanguage.PYTHON, variables=variables
    )
    print(f"Success: {result.success}")
    print(f"Result: {result.return_value}")


async def example_javascript_with_variables():
    """Example: JavaScript execution with variable injection."""
    print("\n=== Example 4: JavaScript with Variables ===")

    code = """
// Use injected variables
const total = numbers.reduce((a, b) => a + b, 0);
const average = total / numbers.length;
_result = {total, average};
"""

    variables = {"numbers": [1, 2, 3, 4, 5]}

    result = await execute_code(
        code, language=ExecutionLanguage.NODEJS, variables=variables
    )
    print(f"Success: {result.success}")
    print(f"Result: {result.return_value}")


async def example_code_validation():
    """Example: Code validation before execution."""
    print("\n=== Example 5: Code Validation ===")

    # Safe code
    safe_code = """
result = 1 + 2 + 3
_result = result
"""

    is_safe, violations = validate_python_code(safe_code)
    print(f"Safe code - Is safe: {is_safe}, Violations: {len(violations)}")

    # Unsafe code
    unsafe_code = """
import os
os.system('ls')
"""

    is_safe, violations = validate_python_code(unsafe_code)
    print(f"Unsafe code - Is safe: {is_safe}, Violations: {len(violations)}")
    for v in violations:
        print(f"  - {v.risk_level.value}: {v.message}")


async def example_security_policy():
    """Example: Custom security policy."""
    print("\n=== Example 6: Custom Security Policy ===")

    policy = SecurityPolicy(
        allow_network=False,
        allow_file_system=False,
        timeout_seconds=60.0,
        memory_limit_mb=1024,
        require_approval=False,
        log_execution=True,
    )

    manager = await get_sandbox_manager(security_policy=policy)

    code = """
import json
data = {"name": "test", "value": 42}
_result = json.dumps(data)
"""

    result = await manager.execute(code, language=ExecutionLanguage.PYTHON)
    print(f"Success: {result.success}")
    print(f"Result: {result.return_value}")


async def example_code_execution_tool():
    """Example: Using CodeExecutionTool."""
    print("\n=== Example 7: Code Execution Tool ===")

    tool = await get_code_execution_tool()

    # Execute Python
    python_result = await tool.execute_python(
        code="""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

_result = fibonacci(10)
"""
    )
    print(f"Python result: {python_result['result']}")

    # Execute JavaScript
    js_result = await tool.execute_javascript(
        code="""
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n-1) + fibonacci(n-2);
}
_result = fibonacci(10);
"""
    )
    print(f"JavaScript result: {js_result['result']}")

    # Get stats
    stats = await tool.get_execution_stats()
    print(f"Execution stats: {stats}")


async def example_error_handling():
    """Example: Error handling."""
    print("\n=== Example 8: Error Handling ===")

    # Timeout error
    code = """
import time
time.sleep(60)
"""

    result = await execute_code(code, language=ExecutionLanguage.PYTHON)
    print(f"Timeout - Success: {result.success}, Error: {result.error_message}")

    # Runtime error
    code = """
result = 1 / 0
"""

    result = await execute_code(code, language=ExecutionLanguage.PYTHON)
    print(f"Runtime error - Success: {result.success}, Error: {result.error_message}")

    # Security error
    code = """
import os
os.system('ls')
"""

    result = await execute_code(code, language=ExecutionLanguage.PYTHON)
    print(f"Security error - Success: {result.success}, Error: {result.error_message}")


async def example_performance_benchmark():
    """Example: Performance benchmarking."""
    print("\n=== Example 9: Performance Benchmark ===")

    benchmark = SandboxBenchmark()
    results = await benchmark.run_all_benchmarks(iterations=5)

    print(f"Total tests: {results['summary']['total_tests']}")
    print(f"Python avg time: {results['summary']['python_avg_time_ms']:.2f}ms")
    print(f"JavaScript avg time: {results['summary']['javascript_avg_time_ms']:.2f}ms")

    benchmark.print_results()


async def example_execution_history():
    """Example: Execution history and statistics."""
    print("\n=== Example 10: Execution History ===")

    tool = await get_code_execution_tool()

    # Execute multiple times
    for i in range(3):
        await tool.execute_python(code=f"_result = {i} * 2")

    # Get history
    history = await tool.get_execution_history(limit=10)
    print(f"Total executions: {history['count']}")
    for record in history["history"]:
        print(f"  - {record['language']}: {record['success']}")

    # Get stats
    stats = await tool.get_execution_stats()
    print(f"Success rate: {stats['success_rate']:.0%}")
    print(f"Average time: {stats['average_execution_time_ms']:.2f}ms")


async def main():
    """Run all examples."""
    print("X-Agent Code Execution Sandbox - Usage Examples")
    print("=" * 60)

    try:
        await example_basic_python_execution()
        await example_basic_javascript_execution()
        await example_python_with_variables()
        await example_javascript_with_variables()
        await example_code_validation()
        await example_security_policy()
        await example_code_execution_tool()
        await example_error_handling()
        await example_performance_benchmark()
        await example_execution_history()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
