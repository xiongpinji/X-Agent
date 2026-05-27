"""Benchmark configuration and constants."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""

    # Performance targets
    SIMPLE_TASK_TARGET_TIME: float = 0.2  # seconds
    MEDIUM_TASK_TARGET_TIME: float = 0.5  # seconds
    COMPLEX_TASK_TARGET_TIME: float = 2.0  # seconds

    # Memory targets (MB)
    BASELINE_MEMORY_TARGET: float = 100.0
    PEAK_MEMORY_TARGET: float = 500.0
    MEMORY_DELTA_TARGET: float = 200.0

    # CPU targets (%)
    AVERAGE_CPU_TARGET: float = 50.0
    PEAK_CPU_TARGET: float = 80.0

    # Benchmark iterations
    SIMPLE_TASK_ITERATIONS: int = 10
    MEDIUM_TASK_ITERATIONS: int = 5
    COMPLEX_TASK_ITERATIONS: int = 3
    ERROR_RECOVERY_ITERATIONS: int = 5
    MEMORY_INTENSIVE_ITERATIONS: int = 5
    CONCURRENT_OPERATIONS_ITERATIONS: int = 5

    # Monitoring
    MONITOR_SAMPLE_INTERVAL: float = 0.1  # seconds
    MONITOR_ENABLED: bool = True

    # Output
    OUTPUT_DIR: str = "benchmarks/results"
    RESULTS_FILENAME: str = "benchmark_results.json"
    REPORT_FILENAME: str = "PERFORMANCE_BENCHMARK_REPORT.md"
    COMPARISON_FILENAME: str = "BENCHMARK_COMPARISON.txt"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "benchmarks/benchmark.log"


# Scenario definitions
BENCHMARK_SCENARIOS: Dict[str, Dict[str, any]] = {
    "simple_task": {
        "name": "Simple Task",
        "complexity": "simple",
        "tool_calls": 1,
        "iterations": 10,
        "target_time": 0.2,
        "description": "Single tool call with minimal processing",
    },
    "medium_task": {
        "name": "Medium Task",
        "complexity": "medium",
        "tool_calls": 7,
        "iterations": 5,
        "target_time": 0.5,
        "description": "Multiple tool calls with moderate processing",
    },
    "complex_task": {
        "name": "Complex Task",
        "complexity": "complex",
        "tool_calls": 20,
        "iterations": 3,
        "target_time": 2.0,
        "description": "Many tool calls with intensive processing",
    },
    "error_recovery": {
        "name": "Error Recovery",
        "complexity": "medium",
        "tool_calls": 3,
        "iterations": 5,
        "target_time": 0.5,
        "description": "Error handling and recovery scenario",
    },
    "memory_intensive": {
        "name": "Memory Intensive",
        "complexity": "complex",
        "tool_calls": 1,
        "iterations": 5,
        "target_time": 1.0,
        "description": "Large data processing and memory management",
    },
    "concurrent_operations": {
        "name": "Concurrent Operations",
        "complexity": "medium",
        "tool_calls": 5,
        "iterations": 5,
        "target_time": 0.5,
        "description": "Parallel execution of multiple operations",
    },
}

# Phase names
PHASES: List[str] = [
    "initialization",
    "planning",
    "execution",
    "recovery",
    "completion",
]

# Metric thresholds for warnings
METRIC_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "timing": {
        "warning_multiplier": 1.5,  # 50% over target
        "critical_multiplier": 2.0,  # 100% over target
    },
    "memory": {
        "warning_multiplier": 1.2,  # 20% over target
        "critical_multiplier": 1.5,  # 50% over target
    },
    "cpu": {
        "warning_multiplier": 1.2,  # 20% over target
        "critical_multiplier": 1.5,  # 50% over target
    },
}

# Default configuration instance
default_config = BenchmarkConfig()
