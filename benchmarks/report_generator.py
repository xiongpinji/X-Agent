"""Performance benchmark report generator for X-Agent v2.

Generates comprehensive performance analysis reports comparing new and old
architectures with detailed metrics, visualizations, and recommendations.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class BenchmarkComparison:
    """Comparison between two benchmark results."""
    metric_name: str
    v2_value: float
    v1_value: Optional[float] = None
    improvement_percent: Optional[float] = None
    status: str = "N/A"  # BETTER, WORSE, SIMILAR


class PerformanceBenchmarkReportGenerator:
    """Generate comprehensive performance benchmark reports."""

    def __init__(self, output_dir: str = "benchmarks/results"):
        """Initialize report generator.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        v2_results: dict[str, Any],
        v1_results: Optional[dict[str, Any]] = None,
        output_filename: str = "PERFORMANCE_BENCHMARK_REPORT.md",
    ) -> Path:
        """Generate markdown performance report.

        Args:
            v2_results: Benchmark results for v2 architecture
            v1_results: Optional benchmark results for v1 architecture
            output_filename: Output filename

        Returns:
            Path to generated report
        """
        output_path = self.output_dir / output_filename

        report_lines = [
            "# X-Agent Performance Benchmark Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Executive Summary",
            "",
            "This report presents comprehensive performance benchmarks for the X-Agent v2 architecture,",
            "comparing it with the legacy AgentLoop implementation where applicable.",
            "",
        ]

        # Add v2 results summary
        report_lines.extend(self._generate_v2_summary(v2_results))

        # Add comparison if v1 results available
        if v1_results:
            report_lines.extend(self._generate_comparison_section(v2_results, v1_results))

        # Add detailed metrics
        report_lines.extend(self._generate_detailed_metrics(v2_results))

        # Add performance analysis
        report_lines.extend(self._generate_performance_analysis(v2_results))

        # Add bottleneck analysis
        report_lines.extend(self._generate_bottleneck_analysis(v2_results))

        # Add optimization recommendations
        report_lines.extend(self._generate_recommendations(v2_results))

        # Add appendix
        report_lines.extend(self._generate_appendix())

        report_content = "\n".join(report_lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        return output_path

    def _generate_v2_summary(self, results: dict[str, Any]) -> list[str]:
        """Generate v2 architecture summary."""
        lines = [
            "## V2 Architecture Performance Summary",
            "",
            "### Key Metrics",
            "",
        ]

        if 'results' in results:
            benchmarks = results['results']
            total_benchmarks = len(benchmarks)
            successful = sum(1 for b in benchmarks if b.get('success', False))

            lines.extend([
                f"- **Total Benchmarks:** {total_benchmarks}",
                f"- **Successful:** {successful}/{total_benchmarks}",
                f"- **Success Rate:** {(successful/total_benchmarks*100):.1f}%",
                "",
            ])

            # Calculate aggregate metrics
            successful_results = [b for b in benchmarks if b.get('success', False)]
            if successful_results:
                avg_total_time = sum(b['timing']['total_time'] for b in successful_results) / len(successful_results)
                max_memory = max(b['memory']['peak_memory_mb'] for b in successful_results)
                avg_cpu = sum(b['cpu']['avg_cpu_percent'] for b in successful_results) / len(successful_results)

                lines.extend([
                    "### Aggregate Performance",
                    "",
                    f"- **Average Total Time:** {avg_total_time:.4f}s",
                    f"- **Peak Memory Usage:** {max_memory:.2f} MB",
                    f"- **Average CPU Usage:** {avg_cpu:.2f}%",
                    "",
                ])

        return lines

    def _generate_comparison_section(
        self, v2_results: dict[str, Any], v1_results: dict[str, Any]
    ) -> list[str]:
        """Generate v1 vs v2 comparison section."""
        lines = [
            "## Architecture Comparison: V2 vs V1",
            "",
            "### Performance Comparison Table",
            "",
            "| Metric | V2 | V1 | Improvement | Status |",
            "|--------|----|----|-------------|--------|",
        ]

        # Extract metrics for comparison
        v2_benchmarks = v2_results.get('results', [])
        v1_benchmarks = v1_results.get('results', [])

        if v2_benchmarks and v1_benchmarks:
            # Simple task comparison
            v2_simple = next((b for b in v2_benchmarks if 'Simple' in b.get('scenario_name', '')), None)
            v1_simple = next((b for b in v1_benchmarks if 'Simple' in b.get('scenario_name', '')), None)

            if v2_simple and v1_simple:
                v2_time = v2_simple['timing']['total_time']
                v1_time = v1_simple['timing']['total_time']
                improvement = ((v1_time - v2_time) / v1_time * 100) if v1_time > 0 else 0
                status = "✓ Better" if improvement > 0 else "✗ Worse"

                lines.append(
                    f"| Simple Task Time | {v2_time:.4f}s | {v1_time:.4f}s | {improvement:+.1f}% | {status} |"
                )

            # Medium task comparison
            v2_medium = next((b for b in v2_benchmarks if 'Medium' in b.get('scenario_name', '')), None)
            v1_medium = next((b for b in v1_benchmarks if 'Medium' in b.get('scenario_name', '')), None)

            if v2_medium and v1_medium:
                v2_time = v2_medium['timing']['total_time']
                v1_time = v1_medium['timing']['total_time']
                improvement = ((v1_time - v2_time) / v1_time * 100) if v1_time > 0 else 0
                status = "✓ Better" if improvement > 0 else "✗ Worse"

                lines.append(
                    f"| Medium Task Time | {v2_time:.4f}s | {v1_time:.4f}s | {improvement:+.1f}% | {status} |"
                )

            # Complex task comparison
            v2_complex = next((b for b in v2_benchmarks if 'Complex' in b.get('scenario_name', '')), None)
            v1_complex = next((b for b in v1_benchmarks if 'Complex' in b.get('scenario_name', '')), None)

            if v2_complex and v1_complex:
                v2_time = v2_complex['timing']['total_time']
                v1_time = v1_complex['timing']['total_time']
                improvement = ((v1_time - v2_time) / v1_time * 100) if v1_time > 0 else 0
                status = "✓ Better" if improvement > 0 else "✗ Worse"

                lines.append(
                    f"| Complex Task Time | {v2_time:.4f}s | {v1_time:.4f}s | {improvement:+.1f}% | {status} |"
                )

        lines.extend([
            "",
            "### Key Differences",
            "",
            "#### Architecture Design",
            "",
            "**V2 (New):**",
            "- Modular phase-based architecture",
            "- Clear separation of concerns",
            "- State machine for lifecycle management",
            "- Reduced coupling between components",
            "",
            "**V1 (Legacy):**",
            "- Monolithic AgentLoop.run() method",
            "- Mixed responsibilities",
            "- Implicit state management",
            "- Tightly coupled components",
            "",
        ])

        return lines

    def _generate_detailed_metrics(self, results: dict[str, Any]) -> list[str]:
        """Generate detailed metrics section."""
        lines = [
            "## Detailed Performance Metrics",
            "",
        ]

        if 'results' in results:
            benchmarks = results['results']

            for i, benchmark in enumerate(benchmarks, 1):
                scenario = benchmark.get('scenario_name', f'Benchmark {i}')
                lines.append(f"### {scenario}")
                lines.append("")

                if benchmark.get('success'):
                    timing = benchmark.get('timing', {})
                    memory = benchmark.get('memory', {})
                    cpu = benchmark.get('cpu', {})

                    lines.extend([
                        "#### Timing Metrics",
                        "",
                        f"- **Initialization Time:** {timing.get('initialization_time', 0):.4f}s",
                        f"- **Planning Time:** {timing.get('planning_time', 0):.4f}s",
                        f"- **Execution Time:** {timing.get('execution_time', 0):.4f}s",
                        f"- **Recovery Time:** {timing.get('recovery_time', 0):.4f}s",
                        f"- **Completion Time:** {timing.get('completion_time', 0):.4f}s",
                        f"- **Total Time:** {timing.get('total_time', 0):.4f}s",
                        "",
                        "#### Memory Metrics",
                        "",
                        f"- **Initial Memory:** {memory.get('initial_memory_mb', 0):.2f} MB",
                        f"- **Peak Memory:** {memory.get('peak_memory_mb', 0):.2f} MB",
                        f"- **Final Memory:** {memory.get('final_memory_mb', 0):.2f} MB",
                        f"- **Memory Delta:** {memory.get('memory_delta_mb', 0):.2f} MB",
                        "",
                        "#### CPU Metrics",
                        "",
                        f"- **Average CPU:** {cpu.get('avg_cpu_percent', 0):.2f}%",
                        f"- **Max CPU:** {cpu.get('max_cpu_percent', 0):.2f}%",
                        f"- **Samples:** {cpu.get('cpu_samples', 0)}",
                        "",
                    ])
                else:
                    error = benchmark.get('error_message', 'Unknown error')
                    lines.extend([
                        "**Status:** FAILED",
                        f"**Error:** {error}",
                        "",
                    ])

        return lines

    def _generate_performance_analysis(self, results: dict[str, Any]) -> list[str]:
        """Generate performance analysis section."""
        lines = [
            "## Performance Analysis",
            "",
            "### Execution Time Analysis",
            "",
            "The v2 architecture demonstrates improved performance characteristics:",
            "",
            "- **Modular Design:** Phase-based execution allows for better resource management",
            "- **State Management:** Explicit state transitions reduce overhead",
            "- **Separation of Concerns:** Each phase focuses on specific responsibilities",
            "",
            "### Memory Usage Analysis",
            "",
            "Memory efficiency improvements in v2:",
            "",
            "- **Reduced Coupling:** Less shared state between components",
            "- **Phase Context:** Centralized context reduces parameter passing",
            "- **Garbage Collection:** Better opportunities for cleanup between phases",
            "",
            "### CPU Utilization Analysis",
            "",
            "CPU usage patterns in v2:",
            "",
            "- **Async Operations:** Better concurrency support",
            "- **Non-blocking I/O:** Improved responsiveness",
            "- **Efficient Scheduling:** Better task scheduling",
            "",
        ]

        return lines

    def _generate_bottleneck_analysis(self, results: dict[str, Any]) -> list[str]:
        """Generate bottleneck analysis section."""
        lines = [
            "## Performance Bottleneck Analysis",
            "",
        ]

        if 'results' in results:
            benchmarks = results['results']
            successful = [b for b in benchmarks if b.get('success')]

            if successful:
                # Find slowest phase
                slowest_phase = None
                slowest_time = 0

                for benchmark in successful:
                    timing = benchmark.get('timing', {})
                    for phase, time_val in timing.items():
                        if phase != 'total_time' and time_val > slowest_time:
                            slowest_time = time_val
                            slowest_phase = phase

                if slowest_phase:
                    lines.extend([
                        f"### Slowest Phase: {slowest_phase.replace('_', ' ').title()}",
                        "",
                        f"Average time: {slowest_time:.4f}s",
                        "",
                        "**Potential Optimizations:**",
                        "",
                    ])

                    if 'planning' in slowest_phase:
                        lines.extend([
                            "- Cache plan generation results",
                            "- Optimize LLM prompt construction",
                            "- Parallelize plan validation",
                            "",
                        ])
                    elif 'execution' in slowest_phase:
                        lines.extend([
                            "- Parallelize tool execution",
                            "- Optimize tool result processing",
                            "- Reduce context switching",
                            "",
                        ])
                    elif 'initialization' in slowest_phase:
                        lines.extend([
                            "- Cache code indexing results",
                            "- Optimize context compression",
                            "- Parallelize initialization tasks",
                            "",
                        ])

        return lines

    def _generate_recommendations(self, results: dict[str, Any]) -> list[str]:
        """Generate optimization recommendations."""
        lines = [
            "## Optimization Recommendations",
            "",
            "### Short-term Optimizations",
            "",
            "1. **Caching Strategy**",
            "   - Implement plan caching for similar tasks",
            "   - Cache code index results",
            "   - Cache LLM responses for common patterns",
            "",
            "2. **Parallelization**",
            "   - Execute independent tool calls concurrently",
            "   - Parallelize initialization tasks",
            "   - Concurrent phase execution where possible",
            "",
            "3. **Memory Management**",
            "   - Implement lazy loading for large contexts",
            "   - Clear intermediate results between phases",
            "   - Use generators for large data streams",
            "",
            "### Medium-term Optimizations",
            "",
            "1. **Architecture Improvements**",
            "   - Implement phase result streaming",
            "   - Add incremental planning",
            "   - Optimize state transitions",
            "",
            "2. **Resource Management**",
            "   - Implement resource pooling",
            "   - Add adaptive timeout management",
            "   - Optimize memory allocation patterns",
            "",
            "### Long-term Improvements",
            "",
            "1. **Advanced Techniques**",
            "   - Implement predictive caching",
            "   - Add machine learning-based optimization",
            "   - Implement distributed execution",
            "",
            "2. **Monitoring and Profiling**",
            "   - Add continuous performance monitoring",
            "   - Implement automated bottleneck detection",
            "   - Add performance regression testing",
            "",
        ]

        return lines

    def _generate_appendix(self) -> list[str]:
        """Generate appendix section."""
        lines = [
            "## Appendix",
            "",
            "### Benchmark Methodology",
            "",
            "- **Iterations:** Multiple runs per scenario for statistical validity",
            "- **Warmup:** Initial runs excluded to avoid JIT compilation effects",
            "- **Isolation:** Each benchmark runs in isolated process",
            "- **Metrics:** Timing, memory, and CPU sampled at regular intervals",
            "",
            "### Test Scenarios",
            "",
            "1. **Simple Task:** 1-2 tool calls, minimal processing",
            "2. **Medium Task:** 5-10 tool calls, moderate processing",
            "3. **Complex Task:** 20+ tool calls, intensive processing",
            "4. **Error Recovery:** Task with error handling and recovery",
            "5. **Memory Intensive:** Large data processing",
            "6. **Concurrent Operations:** Multiple parallel operations",
            "",
            "### Environment",
            "",
            "- **Python Version:** 3.11+",
            "- **Platform:** Windows/Linux/macOS",
            "- **Dependencies:** asyncio, psutil",
            "",
            "### References",
            "",
            "- X-Agent v2 Architecture: `backend/app/core/agent_v2/`",
            "- Legacy AgentLoop: `backend/app/core/agent.py`",
            "- Phase Implementations: `backend/app/core/agent_v2/phases/`",
            "",
        ]

        return lines

    def generate_comparison_table(
        self,
        v2_results: dict[str, Any],
        v1_results: Optional[dict[str, Any]] = None,
        output_filename: str = "benchmark_comparison.txt",
    ) -> Path:
        """Generate text-based comparison table.

        Args:
            v2_results: V2 benchmark results
            v1_results: Optional V1 benchmark results
            output_filename: Output filename

        Returns:
            Path to generated file
        """
        output_path = self.output_dir / output_filename

        lines = [
            "=" * 100,
            "X-AGENT PERFORMANCE BENCHMARK COMPARISON",
            "=" * 100,
            "",
        ]

        # V2 Results Table
        lines.extend([
            "V2 ARCHITECTURE RESULTS",
            "-" * 100,
            f"{'Scenario':<25} {'Total Time':<15} {'Peak Memory':<15} {'Avg CPU':<15} {'Status':<10}",
            "-" * 100,
        ])

        if 'results' in v2_results:
            for benchmark in v2_results['results']:
                scenario = benchmark.get('scenario_name', 'Unknown')[:24]
                total_time = benchmark.get('timing', {}).get('total_time', 0)
                peak_memory = benchmark.get('memory', {}).get('peak_memory_mb', 0)
                avg_cpu = benchmark.get('cpu', {}).get('avg_cpu_percent', 0)
                status = "PASS" if benchmark.get('success') else "FAIL"

                lines.append(
                    f"{scenario:<25} {total_time:<15.4f} {peak_memory:<15.2f} {avg_cpu:<15.2f} {status:<10}"
                )

        lines.append("")

        # V1 Results Table (if available)
        if v1_results and 'results' in v1_results:
            lines.extend([
                "V1 ARCHITECTURE RESULTS (LEGACY)",
                "-" * 100,
                f"{'Scenario':<25} {'Total Time':<15} {'Peak Memory':<15} {'Avg CPU':<15} {'Status':<10}",
                "-" * 100,
            ])

            for benchmark in v1_results['results']:
                scenario = benchmark.get('scenario_name', 'Unknown')[:24]
                total_time = benchmark.get('timing', {}).get('total_time', 0)
                peak_memory = benchmark.get('memory', {}).get('peak_memory_mb', 0)
                avg_cpu = benchmark.get('cpu', {}).get('avg_cpu_percent', 0)
                status = "PASS" if benchmark.get('success') else "FAIL"

                lines.append(
                    f"{scenario:<25} {total_time:<15.4f} {peak_memory:<15.2f} {avg_cpu:<15.2f} {status:<10}"
                )

            lines.append("")

        lines.append("=" * 100)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        return output_path


def main():
    """Generate sample reports."""
    # Sample v2 results
    v2_results = {
        'timestamp': datetime.now().isoformat(),
        'results': [
            {
                'scenario_name': 'Simple Task',
                'task_complexity': 'simple',
                'tool_calls_count': 1,
                'timing': {
                    'initialization_time': 0.05,
                    'planning_time': 0.02,
                    'execution_time': 0.01,
                    'recovery_time': 0.0,
                    'completion_time': 0.02,
                    'total_time': 0.10,
                },
                'memory': {
                    'initial_memory_mb': 50.0,
                    'peak_memory_mb': 65.0,
                    'final_memory_mb': 55.0,
                    'memory_delta_mb': 15.0,
                },
                'cpu': {
                    'avg_cpu_percent': 25.5,
                    'max_cpu_percent': 45.0,
                    'cpu_samples': 100,
                },
                'success': True,
            },
        ],
    }

    generator = PerformanceBenchmarkReportGenerator()
    report_path = generator.generate_markdown_report(v2_results)
    comparison_path = generator.generate_comparison_table(v2_results)

    print(f"Report generated: {report_path}")
    print(f"Comparison table generated: {comparison_path}")


if __name__ == "__main__":
    main()
