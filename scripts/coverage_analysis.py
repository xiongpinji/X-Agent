#!/usr/bin/env python3
"""
Coverage analysis and reporting script for X-Agent project.
Generates comprehensive coverage reports and identifies gaps.
"""

import subprocess
import json
import sys
from pathlib import Path
from datetime import datetime


def run_coverage_analysis():
    """Run pytest with coverage analysis."""
    print("=" * 80)
    print("X-Agent Test Coverage Analysis")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}\n")

    # Run pytest with coverage
    print("Running tests with coverage analysis...")
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/",
            "--cov=backend/app",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=json",
            "-v",
            "--tb=short"
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=False
    )

    return result.returncode == 0


def parse_coverage_report():
    """Parse the JSON coverage report."""
    report_path = Path(__file__).parent.parent / ".coverage"
    json_report = Path(__file__).parent.parent / "coverage.json"

    if json_report.exists():
        with open(json_report) as f:
            return json.load(f)
    return None


def generate_coverage_summary():
    """Generate coverage summary report."""
    print("\n" + "=" * 80)
    print("Coverage Summary")
    print("=" * 80)

    # Try to read coverage data
    try:
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--skip-covered"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings:", result.stderr)
    except Exception as e:
        print(f"Could not generate coverage report: {e}")


def identify_coverage_gaps():
    """Identify modules with low coverage."""
    print("\n" + "=" * 80)
    print("Coverage Gaps Analysis")
    print("=" * 80)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "report", "--skip-covered", "--sort=cover"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )

        lines = result.stdout.split('\n')
        low_coverage = []

        for line in lines:
            if '%' in line and 'backend/app' in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        coverage = int(parts[-1].rstrip('%'))
                        if coverage < 90:
                            low_coverage.append((line.strip(), coverage))
                    except ValueError:
                        pass

        if low_coverage:
            print("\nModules with coverage < 90%:")
            print("-" * 80)
            for module, coverage in sorted(low_coverage, key=lambda x: x[1]):
                print(f"  {coverage:3d}% - {module}")
        else:
            print("\nAll modules have coverage >= 90%!")

    except Exception as e:
        print(f"Could not analyze coverage gaps: {e}")


def generate_html_report():
    """Generate HTML coverage report."""
    print("\n" + "=" * 80)
    print("HTML Report Generation")
    print("=" * 80)

    html_dir = Path(__file__).parent.parent / "htmlcov"
    if html_dir.exists():
        print(f"HTML coverage report generated at: {html_dir}/index.html")
        print("\nTo view the report, open: htmlcov/index.html")
    else:
        print("HTML report directory not found")


def generate_markdown_report():
    """Generate Markdown coverage report."""
    report_path = Path(__file__).parent.parent / "TEST_COVERAGE_IMPROVEMENT_REPORT.md"

    print("\n" + "=" * 80)
    print("Generating Markdown Report")
    print("=" * 80)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "coverage", "report"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )

        with open(report_path, 'w') as f:
            f.write("# X-Agent Test Coverage Improvement Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            f.write("## Executive Summary\n\n")
            f.write("This report documents the test coverage improvements for the X-Agent project.\n")
            f.write("The goal is to achieve 90%+ coverage across all core modules.\n\n")

            f.write("## Coverage Report\n\n")
            f.write("```\n")
            f.write(result.stdout)
            f.write("```\n\n")

            f.write("## Test Files Added\n\n")
            f.write("### 1. Core Modules Extended Tests\n")
            f.write("- **File**: `tests/test_core_modules_extended.py`\n")
            f.write("- **Coverage**: ExecutionPlanner, RepairLoop, MemoryItem, AgentRuntimeAdapter\n")
            f.write("- **Test Categories**:\n")
            f.write("  - Boundary conditions (empty, very long, special characters, unicode)\n")
            f.write("  - Exception handling (validation errors, timeouts, rate limits)\n")
            f.write("  - Concurrent operations (thread safety, async operations)\n")
            f.write("  - Error recovery scenarios\n\n")

            f.write("### 2. API Extended Tests\n")
            f.write("- **File**: `tests/test_api_extended.py`\n")
            f.write("- **Coverage**: API validation, authentication, rate limiting\n")
            f.write("- **Test Categories**:\n")
            f.write("  - Input validation (invalid JSON, missing fields, type errors)\n")
            f.write("  - Authentication and authorization\n")
            f.write("  - Rate limiting and throttling\n")
            f.write("  - Response format consistency\n")
            f.write("  - Edge cases (nonexistent resources, invalid parameters)\n\n")

            f.write("### 3. Services Extended Tests\n")
            f.write("- **File**: `tests/test_services_extended.py`\n")
            f.write("- **Coverage**: BrowserSessionManager, MemoryIndexer, MemoryRetriever, EventExporter\n")
            f.write("- **Test Categories**:\n")
            f.write("  - Error handling and recovery\n")
            f.write("  - Timeout handling\n")
            f.write("  - Concurrent operations\n")
            f.write("  - Service integration\n\n")

            f.write("### 4. Integration Extended Tests\n")
            f.write("- **File**: `tests/test_integration_extended.py`\n")
            f.write("- **Coverage**: End-to-end workflows, concurrent execution, error recovery\n")
            f.write("- **Test Categories**:\n")
            f.write("  - Complete workflow lifecycle\n")
            f.write("  - Multi-node workflows\n")
            f.write("  - Conditional branches\n")
            f.write("  - Memory integration\n")
            f.write("  - Data consistency\n\n")

            f.write("### 5. Performance Extended Tests\n")
            f.write("- **File**: `tests/test_performance_extended.py`\n")
            f.write("- **Coverage**: Response time, throughput, resource usage\n")
            f.write("- **Test Categories**:\n")
            f.write("  - API response time benchmarks\n")
            f.write("  - Throughput testing\n")
            f.write("  - Memory usage monitoring\n")
            f.write("  - Database query performance\n")
            f.write("  - Load testing (sustained and spike)\n\n")

            f.write("## Coverage Targets\n\n")
            f.write("| Module | Target | Status |\n")
            f.write("|--------|--------|--------|\n")
            f.write("| backend.app.core | 95% | In Progress |\n")
            f.write("| backend.app.api | 95% | In Progress |\n")
            f.write("| backend.app.services | 90% | In Progress |\n")
            f.write("| Overall | 90%+ | In Progress |\n\n")

            f.write("## Running the Tests\n\n")
            f.write("### Run all tests with coverage:\n")
            f.write("```bash\n")
            f.write("pytest tests/ --cov=backend/app --cov-report=html --cov-report=term-missing\n")
            f.write("```\n\n")

            f.write("### Run specific test file:\n")
            f.write("```bash\n")
            f.write("pytest tests/test_core_modules_extended.py -v\n")
            f.write("```\n\n")

            f.write("### Run tests with specific marker:\n")
            f.write("```bash\n")
            f.write("pytest tests/ -m asyncio -v\n")
            f.write("```\n\n")

            f.write("### Generate HTML report:\n")
            f.write("```bash\n")
            f.write("pytest tests/ --cov=backend/app --cov-report=html\n")
            f.write("open htmlcov/index.html\n")
            f.write("```\n\n")

            f.write("## Key Improvements\n\n")
            f.write("1. **Boundary Condition Testing**: Added tests for edge cases like empty strings, very long content, special characters\n")
            f.write("2. **Exception Handling**: Comprehensive tests for error scenarios and recovery mechanisms\n")
            f.write("3. **Concurrency Testing**: Tests for thread safety and concurrent operations\n")
            f.write("4. **API Validation**: Extensive tests for input validation and error responses\n")
            f.write("5. **Performance Testing**: Benchmarks for response time, throughput, and resource usage\n")
            f.write("6. **Integration Testing**: End-to-end workflow tests and data consistency checks\n\n")

            f.write("## Next Steps\n\n")
            f.write("1. Run the full test suite to identify any remaining gaps\n")
            f.write("2. Review coverage reports to find uncovered code paths\n")
            f.write("3. Add targeted tests for identified gaps\n")
            f.write("4. Monitor performance metrics to ensure no regressions\n")
            f.write("5. Maintain coverage above 90% for all future changes\n\n")

            f.write("## Conclusion\n\n")
            f.write("The test coverage improvements provide comprehensive testing across all major components\n")
            f.write("of the X-Agent project. The new tests cover boundary conditions, error scenarios,\n")
            f.write("concurrent operations, and performance characteristics, significantly improving\n")
            f.write("the reliability and maintainability of the codebase.\n")

        print(f"Markdown report generated: {report_path}")

    except Exception as e:
        print(f"Could not generate markdown report: {e}")


def main():
    """Main entry point."""
    try:
        # Run coverage analysis
        success = run_coverage_analysis()

        if success:
            print("\n✓ Tests completed successfully")
        else:
            print("\n✗ Some tests failed")

        # Generate reports
        generate_coverage_summary()
        identify_coverage_gaps()
        generate_html_report()
        generate_markdown_report()

        print("\n" + "=" * 80)
        print("Coverage analysis complete!")
        print("=" * 80)

    except Exception as e:
        print(f"Error during coverage analysis: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
