#!/usr/bin/env python3
"""Test execution and coverage analysis script."""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime


class TestExecutor:
    """Execute tests and generate coverage reports."""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
        self.results = {}

    def run_all_tests(self) -> bool:
        """Run all test files."""
        print("=" * 70)
        print("Running All Comprehensive Tests")
        print("=" * 70)

        test_files = [
            "test_policy_engine_comprehensive.py",
            "test_approval_store_comprehensive.py",
            "test_security_api_comprehensive.py",
            "test_core_modules_comprehensive.py",
            "test_integration_comprehensive.py",
            "test_exceptions_boundaries_performance.py",
        ]

        all_passed = True
        for test_file in test_files:
            print(f"\nRunning {test_file}...")
            result = self._run_test_file(test_file)
            self.results[test_file] = result
            if not result["passed"]:
                all_passed = False

        return all_passed

    def _run_test_file(self, test_file: str) -> dict:
        """Run a single test file."""
        test_path = self.test_dir / test_file
        cmd = [
            "pytest",
            str(test_path),
            "-v",
            "--tb=short",
            "-q",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            passed = result.returncode == 0
            return {
                "passed": passed,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "stdout": "",
                "stderr": "Test timeout",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "passed": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    def run_coverage_analysis(self) -> dict:
        """Run coverage analysis."""
        print("\n" + "=" * 70)
        print("Running Coverage Analysis")
        print("=" * 70)

        cmd = [
            "pytest",
            str(self.test_dir),
            "--cov=backend",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-report=json",
            "-q",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            print(result.stdout)
            if result.stderr:
                print("Warnings/Errors:", result.stderr)

            # Parse coverage report
            coverage_file = self.project_root / ".coverage"
            return {
                "passed": result.returncode == 0,
                "output": result.stdout,
                "coverage_file": str(coverage_file),
            }
        except Exception as e:
            print(f"Coverage analysis failed: {e}")
            return {
                "passed": False,
                "output": "",
                "error": str(e),
            }

    def run_performance_tests(self) -> dict:
        """Run performance tests."""
        print("\n" + "=" * 70)
        print("Running Performance Tests")
        print("=" * 70)

        cmd = [
            "pytest",
            str(self.test_dir / "test_exceptions_boundaries_performance.py::TestPerformance"),
            "-v",
            "--tb=short",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            print(result.stdout)
            return {
                "passed": result.returncode == 0,
                "output": result.stdout,
            }
        except Exception as e:
            print(f"Performance tests failed: {e}")
            return {
                "passed": False,
                "error": str(e),
            }

    def generate_report(self) -> str:
        """Generate test execution report."""
        report = []
        report.append("=" * 70)
        report.append("TEST EXECUTION REPORT")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("=" * 70)

        # Summary
        total_files = len(self.results)
        passed_files = sum(1 for r in self.results.values() if r["passed"])
        report.append(f"\nSummary:")
        report.append(f"  Total Test Files: {total_files}")
        report.append(f"  Passed: {passed_files}")
        report.append(f"  Failed: {total_files - passed_files}")

        # Details
        report.append(f"\nDetails:")
        for test_file, result in self.results.items():
            status = "PASSED" if result["passed"] else "FAILED"
            report.append(f"  {test_file}: {status}")

        # Coverage
        report.append(f"\nCoverage Analysis:")
        report.append(f"  Target: 95%+")
        report.append(f"  Status: In Progress")

        return "\n".join(report)

    def save_results(self, output_file: str = "test_results.json"):
        """Save test results to file."""
        output_path = self.project_root / output_file
        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to {output_path}")


def main():
    """Main execution."""
    executor = TestExecutor()

    # Run all tests
    all_passed = executor.run_all_tests()

    # Run coverage analysis
    coverage_result = executor.run_coverage_analysis()

    # Run performance tests
    perf_result = executor.run_performance_tests()

    # Generate report
    report = executor.generate_report()
    print("\n" + report)

    # Save results
    executor.save_results()

    # Exit with appropriate code
    if all_passed and coverage_result["passed"]:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
