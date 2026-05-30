"""Performance tests for context compactor optimization.

Tests verify:
- Compression time meets target (45ms for typical workloads)
- Compression ratio remains consistent (62-68%)
- Information retention rate (>90%)
- Memory efficiency improvements
"""

import time
import sys
from pathlib import Path

from backend.app.core.context_compactor import ContextCompactor, CompactionMetrics


def generate_test_messages(size_kb: int, num_messages: int = 50) -> list[dict[str, str]]:
    """Generate test messages of specified size.

    Args:
        size_kb: Target size in kilobytes
        num_messages: Number of messages to generate

    Returns:
        List of test messages
    """
    messages = []
    content_per_msg = (size_kb * 1024) // num_messages

    roles = ["user", "assistant", "tool", "system"]
    role_idx = 0

    for i in range(num_messages):
        role = roles[role_idx % len(roles)]
        role_idx += 1

        # Create varied content
        if role == "tool":
            content = f"Tool result {i}: " + "x" * (content_per_msg - 50)
        elif role == "assistant":
            if i % 5 == 0:
                content = f"Tool call executed: function_call_result_{i} " + "y" * (content_per_msg - 100)
            else:
                content = f"Response {i}: " + "z" * (content_per_msg - 50)
        elif role == "user":
            content = f"User instruction {i}: " + "a" * (content_per_msg - 50)
        else:  # system
            content = f"System message {i}: " + "b" * (content_per_msg - 50)

        messages.append({
            "role": role,
            "content": content,
        })

    return messages


def measure_compression_time():
    """Test compression time for different message sizes."""
    print("\n" + "=" * 70)
    print("COMPRESSION TIME PERFORMANCE TEST")
    print("=" * 70)

    compactor = ContextCompactor(
        model="gpt-4",
        token_limit=128_000,
        compression_threshold=0.85,
    )

    test_sizes = [10, 50, 100, 200, 500]  # KB
    results = []

    for size_kb in test_sizes:
        messages = generate_test_messages(size_kb)

        # Warm up
        _ = compactor.compress(messages)

        # Measure compression time
        start_time = time.perf_counter()
        result = compactor.compress(messages)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        results.append({
            "size_kb": size_kb,
            "time_ms": elapsed_ms,
            "messages_before": result.metrics.messages_before,
            "messages_after": result.metrics.messages_after,
            "compression_ratio": result.metrics.compression_ratio,
        })

        print(f"\nSize: {size_kb:3d}KB | Time: {elapsed_ms:6.2f}ms | "
              f"Messages: {result.metrics.messages_before:3d} → {result.metrics.messages_after:3d} | "
              f"Ratio: {result.metrics.compression_ratio:.2%}")

    # Analyze results
    print("\n" + "-" * 70)
    print("PERFORMANCE ANALYSIS")
    print("-" * 70)

    avg_time = sum(r["time_ms"] for r in results) / len(results)
    max_time = max(r["time_ms"] for r in results)
    min_time = min(r["time_ms"] for r in results)

    print(f"Average compression time: {avg_time:.2f}ms")
    print(f"Min compression time:     {min_time:.2f}ms")
    print(f"Max compression time:     {max_time:.2f}ms")
    print(f"Target time:              45.00ms")

    if avg_time <= 45:
        print(f"✓ PASS: Average time {avg_time:.2f}ms <= 45ms target")
    else:
        print(f"✗ FAIL: Average time {avg_time:.2f}ms > 45ms target")

    return results


def measure_compression_ratio():
    """Test that compression ratio remains consistent."""
    print("\n" + "=" * 70)
    print("COMPRESSION RATIO CONSISTENCY TEST")
    print("=" * 70)

    compactor = ContextCompactor(
        model="gpt-4",
        token_limit=128_000,
        compression_threshold=0.85,
    )

    test_sizes = [10, 50, 100, 200, 500]  # KB
    ratios = []

    for size_kb in test_sizes:
        messages = generate_test_messages(size_kb)
        result = compactor.compress(messages)
        ratios.append(result.metrics.compression_ratio)

        print(f"Size: {size_kb:3d}KB | Compression ratio: {result.metrics.compression_ratio:.2%}")

    # Analyze consistency
    print("\n" + "-" * 70)
    print("RATIO ANALYSIS")
    print("-" * 70)

    avg_ratio = sum(ratios) / len(ratios)
    min_ratio = min(ratios)
    max_ratio = max(ratios)

    print(f"Average compression ratio: {avg_ratio:.2%}")
    print(f"Min ratio:                 {min_ratio:.2%}")
    print(f"Max ratio:                 {max_ratio:.2%}")
    print(f"Target range:              62% - 68%")

    if 0.62 <= avg_ratio <= 0.68:
        print(f"✓ PASS: Average ratio {avg_ratio:.2%} within target range")
    else:
        print(f"✗ FAIL: Average ratio {avg_ratio:.2%} outside target range")

    return ratios


def measure_information_retention():
    """Test that important information is retained."""
    print("\n" + "=" * 70)
    print("INFORMATION RETENTION TEST")
    print("=" * 70)

    compactor = ContextCompactor(
        model="gpt-4",
        token_limit=128_000,
        compression_threshold=0.85,
    )

    # Create messages with critical information
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Please help me with this task."},
        {"role": "assistant", "content": "I'll help. Let me call a tool."},
        {"role": "assistant", "content": "Executing tool_call: analyze_data"},
        {"role": "tool", "content": "Tool result: analysis complete"},
        {"role": "assistant", "content": "Analysis shows error in data format"},
        {"role": "user", "content": "Can you fix the error?"},
        {"role": "assistant", "content": "Yes, I'll fix it now."},
        {"role": "assistant", "content": "Executing function_call: fix_data"},
        {"role": "tool", "content": "Tool result: data fixed successfully"},
    ]

    # Add filler messages
    for i in range(40):
        messages.append({
            "role": "assistant" if i % 2 == 0 else "user",
            "content": f"Filler message {i}: " + "x" * 500,
        })

    result = compactor.compress(messages)

    # Check retention of critical information
    compressed_content = " ".join(msg["content"] for msg in result.messages)

    critical_terms = [
        "tool_call",
        "function_call",
        "error",
        "tool result",
        "Context compressed",
    ]

    retained_terms = sum(1 for term in critical_terms if term.lower() in compressed_content.lower())
    retention_rate = retained_terms / len(critical_terms)

    print(f"\nMessages before: {result.metrics.messages_before}")
    print(f"Messages after:  {result.metrics.messages_after}")
    print(f"Compression ratio: {result.metrics.compression_ratio:.2%}")

    print(f"\nCritical terms retained: {retained_terms}/{len(critical_terms)}")
    print(f"Information retention rate: {retention_rate:.2%}")
    print(f"Target retention rate: >90%")

    if retention_rate >= 0.90:
        print(f"✓ PASS: Retention rate {retention_rate:.2%} >= 90% target")
    else:
        print(f"✗ FAIL: Retention rate {retention_rate:.2%} < 90% target")

    return retention_rate


def measure_memory_efficiency():
    """Test memory efficiency of optimized implementation."""
    print("\n" + "=" * 70)
    print("MEMORY EFFICIENCY TEST")
    print("=" * 70)

    import tracemalloc

    compactor = ContextCompactor(
        model="gpt-4",
        token_limit=128_000,
        compression_threshold=0.85,
    )

    messages = generate_test_messages(100)  # 100KB

    # Measure memory usage
    tracemalloc.start()
    result = compactor.compress(messages)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\nCompression of 100KB messages:")
    print(f"Current memory: {current / 1024:.2f}KB")
    print(f"Peak memory:    {peak / 1024:.2f}KB")
    print(f"Messages compressed: {result.metrics.messages_before} → {result.metrics.messages_after}")

    return peak / 1024


def run_all_tests():
    """Run all performance tests."""
    print("\n" + "=" * 70)
    print("X-AGENT CONTEXT COMPACTOR PERFORMANCE TEST SUITE")
    print("=" * 70)

    try:
        # Run tests
        time_results = measure_compression_time()
        ratio_results = measure_compression_ratio()
        retention_rate = measure_information_retention()
        peak_memory = measure_memory_efficiency()

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        avg_time = sum(r["time_ms"] for r in time_results) / len(time_results)
        avg_ratio = sum(ratio_results) / len(ratio_results)

        print(f"\n✓ Compression time:      {avg_time:.2f}ms (target: 45ms)")
        print(f"✓ Compression ratio:     {avg_ratio:.2%} (target: 62-68%)")
        print(f"✓ Information retention: {retention_rate:.2%} (target: >90%)")
        print(f"✓ Peak memory usage:     {peak_memory:.2f}KB")

        # Overall result
        time_pass = avg_time <= 45
        ratio_pass = 0.62 <= avg_ratio <= 0.68
        retention_pass = retention_rate >= 0.90

        if time_pass and ratio_pass and retention_pass:
            print("\n" + "=" * 70)
            print("✓ ALL TESTS PASSED")
            print("=" * 70)
            return True
        else:
            print("\n" + "=" * 70)
            print("✗ SOME TESTS FAILED")
            print("=" * 70)
            return False

    except Exception as e:
        print(f"\n✗ Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
