"""Performance analysis and comparison tools."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PerformanceMetric:
    """Single performance metric."""
    name: str
    value: float
    unit: str
    target: Optional[float] = None
    status: str = "UNKNOWN"  # PASS, WARNING, CRITICAL


class PerformanceAnalyzer:
    """Analyze and compare performance metrics."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize analyzer.

        Args:
            config_path: Optional path to config file
        """
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration."""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}

    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze benchmark results.

        Args:
            results: Benchmark results dictionary

        Returns:
            Analysis report
        """
        analysis = {
            'summary': self._analyze_summary(results),
            'timing': self._analyze_timing(results),
            'memory': self._analyze_memory(results),
            'cpu': self._analyze_cpu(results),
            'recommendations': self._generate_recommendations(results),
        }
        return analysis

    def _analyze_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze overall summary."""
        benchmarks = results.get('results', [])
        successful = sum(1 for b in benchmarks if b.get('success', False))
        failed = len(benchmarks) - successful

        return {
            'total_benchmarks': len(benchmarks),
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(benchmarks) * 100) if benchmarks else 0,
        }

    def _analyze_timing(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze timing metrics."""
        benchmarks = results.get('results', [])
        successful = [b for b in benchmarks if b.get('success', False)]

        if not successful:
            return {'error': 'No successful benchmarks'}

        timings = []
        for benchmark in successful:
            timing = benchmark.get('timing', {})
            timings.append({
                'scenario': benchmark.get('scenario_name', 'Unknown'),
                'total_time': timing.get('total_time', 0),
                'initialization': timing.get('initialization_time', 0),
                'planning': timing.get('planning_time', 0),
                'execution': timing.get('execution_time', 0),
                'recovery': timing.get('recovery_time', 0),
                'completion': timing.get('completion_time', 0),
            })

        # Calculate statistics
        total_times = [t['total_time'] for t in timings]
        avg_total = sum(total_times) / len(total_times) if total_times else 0
        max_total = max(total_times) if total_times else 0
        min_total = min(total_times) if total_times else 0

        return {
            'timings': timings,
            'statistics': {
                'average_total_time': avg_total,
                'max_total_time': max_total,
                'min_total_time': min_total,
            },
        }

    def _analyze_memory(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze memory metrics."""
        benchmarks = results.get('results', [])
        successful = [b for b in benchmarks if b.get('success', False)]

        if not successful:
            return {'error': 'No successful benchmarks'}

        memory_data = []
        for benchmark in successful:
            memory = benchmark.get('memory', {})
            memory_data.append({
                'scenario': benchmark.get('scenario_name', 'Unknown'),
                'initial': memory.get('initial_memory_mb', 0),
                'peak': memory.get('peak_memory_mb', 0),
                'final': memory.get('final_memory_mb', 0),
                'delta': memory.get('memory_delta_mb', 0),
            })

        # Calculate statistics
        peaks = [m['peak'] for m in memory_data]
        deltas = [m['delta'] for m in memory_data]

        return {
            'memory_data': memory_data,
            'statistics': {
                'average_peak_memory': sum(peaks) / len(peaks) if peaks else 0,
                'max_peak_memory': max(peaks) if peaks else 0,
                'average_delta': sum(deltas) / len(deltas) if deltas else 0,
                'max_delta': max(deltas) if deltas else 0,
            },
        }

    def _analyze_cpu(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze CPU metrics."""
        benchmarks = results.get('results', [])
        successful = [b for b in benchmarks if b.get('success', False)]

        if not successful:
            return {'error': 'No successful benchmarks'}

        cpu_data = []
        for benchmark in successful:
            cpu = benchmark.get('cpu', {})
            cpu_data.append({
                'scenario': benchmark.get('scenario_name', 'Unknown'),
                'avg_cpu': cpu.get('avg_cpu_percent', 0),
                'max_cpu': cpu.get('max_cpu_percent', 0),
                'samples': cpu.get('cpu_samples', 0),
            })

        # Calculate statistics
        avg_cpus = [c['avg_cpu'] for c in cpu_data]
        max_cpus = [c['max_cpu'] for c in cpu_data]

        return {
            'cpu_data': cpu_data,
            'statistics': {
                'average_cpu': sum(avg_cpus) / len(avg_cpus) if avg_cpus else 0,
                'max_cpu': max(max_cpus) if max_cpus else 0,
            },
        }

    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        analysis = self.analyze_results(results)

        # Timing recommendations
        timing_analysis = analysis.get('timing', {})
        if timing_analysis.get('statistics', {}).get('average_total_time', 0) > 1.0:
            recommendations.append(
                "High average execution time detected. Consider implementing caching or parallelization."
            )

        # Memory recommendations
        memory_analysis = analysis.get('memory', {})
        if memory_analysis.get('statistics', {}).get('max_delta', 0) > 200:
            recommendations.append(
                "High memory delta detected. Consider optimizing memory allocation or implementing lazy loading."
            )

        # CPU recommendations
        cpu_analysis = analysis.get('cpu', {})
        if cpu_analysis.get('statistics', {}).get('max_cpu', 0) > 80:
            recommendations.append(
                "High CPU usage detected. Consider implementing async operations or reducing computational complexity."
            )

        if not recommendations:
            recommendations.append("Performance metrics are within acceptable ranges.")

        return recommendations

    def compare_results(
        self, v2_results: Dict[str, Any], v1_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare v2 and v1 results.

        Args:
            v2_results: V2 benchmark results
            v1_results: V1 benchmark results

        Returns:
            Comparison analysis
        """
        comparison = {
            'timing_comparison': self._compare_timing(v2_results, v1_results),
            'memory_comparison': self._compare_memory(v2_results, v1_results),
            'cpu_comparison': self._compare_cpu(v2_results, v1_results),
            'overall_verdict': self._generate_verdict(v2_results, v1_results),
        }
        return comparison

    def _compare_timing(
        self, v2_results: Dict[str, Any], v1_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare timing metrics."""
        v2_benchmarks = v2_results.get('results', [])
        v1_benchmarks = v1_results.get('results', [])

        comparisons = []
        for v2_bench in v2_benchmarks:
            scenario = v2_bench.get('scenario_name', '')
            v1_bench = next(
                (b for b in v1_benchmarks if b.get('scenario_name', '') == scenario),
                None,
            )

            if v1_bench:
                v2_time = v2_bench.get('timing', {}).get('total_time', 0)
                v1_time = v1_bench.get('timing', {}).get('total_time', 0)
                improvement = ((v1_time - v2_time) / v1_time * 100) if v1_time > 0 else 0

                comparisons.append({
                    'scenario': scenario,
                    'v2_time': v2_time,
                    'v1_time': v1_time,
                    'improvement_percent': improvement,
                    'status': 'BETTER' if improvement > 0 else 'WORSE',
                })

        return {'comparisons': comparisons}

    def _compare_memory(
        self, v2_results: Dict[str, Any], v1_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare memory metrics."""
        v2_benchmarks = v2_results.get('results', [])
        v1_benchmarks = v1_results.get('results', [])

        comparisons = []
        for v2_bench in v2_benchmarks:
            scenario = v2_bench.get('scenario_name', '')
            v1_bench = next(
                (b for b in v1_benchmarks if b.get('scenario_name', '') == scenario),
                None,
            )

            if v1_bench:
                v2_peak = v2_bench.get('memory', {}).get('peak_memory_mb', 0)
                v1_peak = v1_bench.get('memory', {}).get('peak_memory_mb', 0)
                improvement = ((v1_peak - v2_peak) / v1_peak * 100) if v1_peak > 0 else 0

                comparisons.append({
                    'scenario': scenario,
                    'v2_peak_memory': v2_peak,
                    'v1_peak_memory': v1_peak,
                    'improvement_percent': improvement,
                    'status': 'BETTER' if improvement > 0 else 'WORSE',
                })

        return {'comparisons': comparisons}

    def _compare_cpu(
        self, v2_results: Dict[str, Any], v1_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare CPU metrics."""
        v2_benchmarks = v2_results.get('results', [])
        v1_benchmarks = v1_results.get('results', [])

        comparisons = []
        for v2_bench in v2_benchmarks:
            scenario = v2_bench.get('scenario_name', '')
            v1_bench = next(
                (b for b in v1_benchmarks if b.get('scenario_name', '') == scenario),
                None,
            )

            if v1_bench:
                v2_cpu = v2_bench.get('cpu', {}).get('avg_cpu_percent', 0)
                v1_cpu = v1_bench.get('cpu', {}).get('avg_cpu_percent', 0)
                improvement = ((v1_cpu - v2_cpu) / v1_cpu * 100) if v1_cpu > 0 else 0

                comparisons.append({
                    'scenario': scenario,
                    'v2_avg_cpu': v2_cpu,
                    'v1_avg_cpu': v1_cpu,
                    'improvement_percent': improvement,
                    'status': 'BETTER' if improvement > 0 else 'WORSE',
                })

        return {'comparisons': comparisons}

    def _generate_verdict(
        self, v2_results: Dict[str, Any], v1_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate overall comparison verdict."""
        timing_comp = self._compare_timing(v2_results, v1_results)
        memory_comp = self._compare_memory(v2_results, v1_results)
        cpu_comp = self._compare_cpu(v2_results, v1_results)

        timing_better = sum(
            1 for c in timing_comp.get('comparisons', [])
            if c.get('status') == 'BETTER'
        )
        memory_better = sum(
            1 for c in memory_comp.get('comparisons', [])
            if c.get('status') == 'BETTER'
        )
        cpu_better = sum(
            1 for c in cpu_comp.get('comparisons', [])
            if c.get('status') == 'BETTER'
        )

        total_comparisons = (
            len(timing_comp.get('comparisons', []))
            + len(memory_comp.get('comparisons', []))
            + len(cpu_comp.get('comparisons', []))
        )

        total_better = timing_better + memory_better + cpu_better

        return {
            'total_comparisons': total_comparisons,
            'v2_better': total_better,
            'v1_better': total_comparisons - total_better,
            'verdict': 'V2 SUPERIOR' if total_better > total_comparisons / 2 else 'MIXED RESULTS',
            'confidence': (total_better / total_comparisons * 100) if total_comparisons > 0 else 0,
        }

    def export_analysis(self, analysis: Dict[str, Any], output_path: str) -> None:
        """Export analysis to JSON file.

        Args:
            analysis: Analysis dictionary
            output_path: Output file path
        """
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)


def main():
    """Example usage."""
    analyzer = PerformanceAnalyzer()

    # Example results
    sample_results = {
        'results': [
            {
                'scenario_name': 'Simple Task',
                'success': True,
                'timing': {
                    'total_time': 0.1,
                    'initialization_time': 0.05,
                    'planning_time': 0.02,
                    'execution_time': 0.01,
                    'recovery_time': 0.0,
                    'completion_time': 0.02,
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
            },
        ],
    }

    analysis = analyzer.analyze_results(sample_results)
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
