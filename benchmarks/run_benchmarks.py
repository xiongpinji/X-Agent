"""Main benchmark runner script.

Orchestrates execution of all benchmarks and generates comprehensive reports.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('benchmarks/benchmark.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def run_benchmarks():
    """Run all benchmark suites."""
    logger.info("=" * 80)
    logger.info("Starting X-Agent Performance Benchmark Suite")
    logger.info("=" * 80)

    try:
        # Import benchmark modules
        from benchmarks.agent_v2_benchmark import AgentV2Benchmark
        from benchmarks.agent_v2_integration_benchmark import AgentV2IntegrationBenchmark
        from benchmarks.report_generator import PerformanceBenchmarkReportGenerator

        # Create output directory
        output_dir = Path("benchmarks/results")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run unit benchmarks
        logger.info("Running unit benchmarks...")
        unit_benchmark = AgentV2Benchmark(str(output_dir))
        unit_results = await unit_benchmark.run_all_benchmarks()
        unit_results_path = unit_benchmark.save_results("unit_benchmark_results.json")
        logger.info(f"Unit benchmarks completed: {unit_results_path}")
        print(unit_benchmark.generate_summary())

        # Run integration benchmarks
        logger.info("Running integration benchmarks...")
        integration_benchmark = AgentV2IntegrationBenchmark(str(output_dir))
        integration_results = await integration_benchmark.run_all_benchmarks()
        integration_results_path = integration_benchmark.save_results()
        logger.info(f"Integration benchmarks completed: {integration_results_path}")
        print(integration_benchmark.generate_report())

        # Load results for report generation
        with open(unit_results_path, 'r') as f:
            unit_data = json.load(f)

        with open(integration_results_path, 'r') as f:
            integration_data = json.load(f)

        # Generate reports
        logger.info("Generating reports...")
        report_generator = PerformanceBenchmarkReportGenerator(str(output_dir))

        # Generate markdown report
        markdown_report = report_generator.generate_markdown_report(
            unit_data,
            output_filename="PERFORMANCE_BENCHMARK_REPORT.md"
        )
        logger.info(f"Markdown report generated: {markdown_report}")

        # Generate comparison table
        comparison_table = report_generator.generate_comparison_table(
            unit_data,
            output_filename="BENCHMARK_COMPARISON.txt"
        )
        logger.info(f"Comparison table generated: {comparison_table}")

        logger.info("=" * 80)
        logger.info("Benchmark suite completed successfully")
        logger.info("=" * 80)

        return {
            'unit_results': unit_results_path,
            'integration_results': integration_results_path,
            'markdown_report': markdown_report,
            'comparison_table': comparison_table,
        }

    except Exception as e:
        logger.error(f"Benchmark suite failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    try:
        results = asyncio.run(run_benchmarks())
        logger.info("All benchmarks completed successfully")
        logger.info(f"Results: {json.dumps({str(k): str(v) for k, v in results.items()}, indent=2)}")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
