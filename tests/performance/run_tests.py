"""
性能测试配置和运行脚本
"""
import pytest
import sys
import json
from pathlib import Path
from datetime import datetime
from tests.performance.report_generator import PerformanceReportGenerator


class PerformanceTestRunner:
    """性能测试运行器"""

    def __init__(self, output_dir: str = "performance_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def run_all_tests(self):
        """运行所有性能测试"""
        print("=" * 80)
        print("X-Agent 性能测试套件")
        print("=" * 80)

        test_suites = [
            ("性能基准测试", "tests/performance/test_benchmarks.py", "-m benchmark"),
            ("负载测试", "tests/performance/test_load.py", "-m load_test"),
            ("压力测试", "tests/performance/test_stress.py", "-m stress_test"),
            ("稳定性测试", "tests/performance/test_stability.py", "-m stability_test"),
            ("瓶颈分析", "tests/performance/test_bottleneck_analysis.py", "-m bottleneck_analysis"),
        ]

        results = {}

        for suite_name, test_file, marker in test_suites:
            print(f"\n运行: {suite_name}")
            print("-" * 80)

            result = self._run_test_suite(test_file, marker)
            results[suite_name] = result

        self._generate_summary_report(results)

    def _run_test_suite(self, test_file: str, marker: str) -> dict:
        """运行单个测试套件"""
        try:
            exit_code = pytest.main([
                test_file,
                marker,
                "-v",
                "--tb=short",
                f"--junit-xml={self.output_dir}/junit_{self.timestamp}.xml",
                f"--html={self.output_dir}/report_{self.timestamp}.html",
                "--self-contained-html"
            ])

            return {
                'status': 'passed' if exit_code == 0 else 'failed',
                'exit_code': exit_code
            }

        except Exception as e:
            print(f"Error running test suite: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def _generate_summary_report(self, results: dict):
        """生成汇总报告"""
        summary = {
            'timestamp': self.timestamp,
            'test_suites': results,
            'total_suites': len(results),
            'passed_suites': sum(1 for r in results.values() if r.get('status') == 'passed'),
            'failed_suites': sum(1 for r in results.values() if r.get('status') == 'failed'),
        }

        summary_file = self.output_dir / f"summary_{self.timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 80)
        print("测试汇总")
        print("=" * 80)
        print(f"总测试套件数: {summary['total_suites']}")
        print(f"通过: {summary['passed_suites']}")
        print(f"失败: {summary['failed_suites']}")
        print(f"汇总报告: {summary_file}")

    def run_benchmark_tests(self):
        """运行基准测试"""
        print("运行性能基准测试...")
        pytest.main([
            "tests/performance/test_benchmarks.py",
            "-m", "benchmark",
            "-v"
        ])

    def run_load_tests(self):
        """运行负载测试"""
        print("运行负载测试...")
        pytest.main([
            "tests/performance/test_load.py",
            "-m", "load_test",
            "-v"
        ])

    def run_stress_tests(self):
        """运行压力测试"""
        print("运行压力测试...")
        pytest.main([
            "tests/performance/test_stress.py",
            "-m", "stress_test",
            "-v"
        ])

    def run_stability_tests(self):
        """运行稳定性测试"""
        print("运行稳定性测试...")
        pytest.main([
            "tests/performance/test_stability.py",
            "-m", "stability_test",
            "-v"
        ])

    def run_bottleneck_analysis(self):
        """运行瓶颈分析"""
        print("运行瓶颈分析...")
        pytest.main([
            "tests/performance/test_bottleneck_analysis.py",
            "-m", "bottleneck_analysis",
            "-v"
        ])


# pytest配置
def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line(
        "markers", "benchmark: mark test as benchmark test"
    )
    config.addinivalue_line(
        "markers", "load_test: mark test as load test"
    )
    config.addinivalue_line(
        "markers", "stress_test: mark test as stress test"
    )
    config.addinivalue_line(
        "markers", "stability_test: mark test as stability test"
    )
    config.addinivalue_line(
        "markers", "bottleneck_analysis: mark test as bottleneck analysis"
    )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='X-Agent 性能测试运行器')
    parser.add_argument(
        '--suite',
        choices=['all', 'benchmark', 'load', 'stress', 'stability', 'bottleneck'],
        default='all',
        help='运行的测试套件'
    )
    parser.add_argument(
        '--output-dir',
        default='performance_reports',
        help='输出目录'
    )

    args = parser.parse_args()

    runner = PerformanceTestRunner(args.output_dir)

    if args.suite == 'all':
        runner.run_all_tests()
    elif args.suite == 'benchmark':
        runner.run_benchmark_tests()
    elif args.suite == 'load':
        runner.run_load_tests()
    elif args.suite == 'stress':
        runner.run_stress_tests()
    elif args.suite == 'stability':
        runner.run_stability_tests()
    elif args.suite == 'bottleneck':
        runner.run_bottleneck_analysis()
