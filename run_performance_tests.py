"""
Performance Testing Quick Start Guide

This script provides a quick way to run all performance tests.
"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime


class PerformanceTestRunner:
    """Orchestrates all performance tests."""

    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None

    def print_header(self, title: str) -> None:
        """Print formatted header."""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def print_section(self, title: str) -> None:
        """Print formatted section."""
        print(f"\n{title}")
        print("-" * 70)

    def run_api_tests(self) -> bool:
        """Run API performance tests."""
        self.print_section("Running API Performance Tests...")

        try:
            result = subprocess.run(
                [sys.executable, "performance_tests.py"],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                print("✓ API tests completed successfully")
                self.results["api_tests"] = "PASSED"

                # Try to load the report
                if Path("performance_benchmark_report.json").exists():
                    with open("performance_benchmark_report.json") as f:
                        self.results["api_report"] = json.load(f)
                return True
            else:
                print(f"✗ API tests failed: {result.stderr}")
                self.results["api_tests"] = "FAILED"
                return False

        except subprocess.TimeoutExpired:
            print("✗ API tests timed out")
            self.results["api_tests"] = "TIMEOUT"
            return False
        except Exception as e:
            print(f"✗ API tests error: {e}")
            self.results["api_tests"] = "ERROR"
            return False

    def run_database_tests(self) -> bool:
        """Run database performance tests."""
        self.print_section("Running Database Performance Tests...")

        try:
            result = subprocess.run(
                [sys.executable, "database_benchmark.py"],
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                print("✓ Database tests completed successfully")
                self.results["database_tests"] = "PASSED"

                # Try to load the report
                if Path("database_benchmark_report.json").exists():
                    with open("database_benchmark_report.json") as f:
                        self.results["database_report"] = json.load(f)
                return True
            else:
                print(f"✗ Database tests failed: {result.stderr}")
                self.results["database_tests"] = "FAILED"
                return False

        except subprocess.TimeoutExpired:
            print("✗ Database tests timed out")
            self.results["database_tests"] = "TIMEOUT"
            return False
        except Exception as e:
            print(f"✗ Database tests error: {e}")
            self.results["database_tests"] = "ERROR"
            return False

    def run_locust_tests(self, users: int = 100, spawn_rate: int = 10, run_time: str = "5m") -> bool:
        """Run Locust load tests.

        Args:
            users: Number of concurrent users
            spawn_rate: User spawn rate
            run_time: Test duration
        """
        self.print_section("Running Locust Load Tests...")

        try:
            cmd = [
                "locust",
                "-f", "locustfile.py",
                "--host=http://localhost:8000",
                f"--users={users}",
                f"--spawn-rate={spawn_rate}",
                f"--run-time={run_time}",
                "--headless",
                "--csv=locust_results"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900
            )

            if result.returncode == 0:
                print("✓ Locust tests completed successfully")
                self.results["locust_tests"] = "PASSED"
                return True
            else:
                print(f"✗ Locust tests failed: {result.stderr}")
                self.results["locust_tests"] = "FAILED"
                return False

        except subprocess.TimeoutExpired:
            print("✗ Locust tests timed out")
            self.results["locust_tests"] = "TIMEOUT"
            return False
        except FileNotFoundError:
            print("✗ Locust not found. Install with: pip install locust")
            self.results["locust_tests"] = "NOT_INSTALLED"
            return False
        except Exception as e:
            print(f"✗ Locust tests error: {e}")
            self.results["locust_tests"] = "ERROR"
            return False

    def generate_summary(self) -> None:
        """Generate test summary."""
        self.print_header("PERFORMANCE TEST SUMMARY")

        print("\nTest Results:")
        for test_name, status in self.results.items():
            if test_name.endswith("_tests"):
                status_symbol = "✓" if status == "PASSED" else "✗"
                print(f"  {status_symbol} {test_name}: {status}")

        print("\nGenerated Reports:")
        if Path("performance_benchmark_report.json").exists():
            print("  ✓ performance_benchmark_report.json")
        if Path("database_benchmark_report.json").exists():
            print("  ✓ database_benchmark_report.json")
        if Path("locust_results_stats.csv").exists():
            print("  ✓ locust_results_stats.csv")

        print("\nNext Steps:")
        print("  1. Review the generated reports")
        print("  2. Analyze performance metrics")
        print("  3. Identify bottlenecks")
        print("  4. Plan optimizations")

    def run_all(self, skip_locust: bool = False) -> None:
        """Run all performance tests.

        Args:
            skip_locust: Skip Locust tests if True
        """
        self.print_header("X-AGENT PERFORMANCE BENCHMARK SUITE")

        print("\nStarting performance tests...")
        print(f"Timestamp: {datetime.now().isoformat()}")

        self.start_time = datetime.now()

        # Run tests
        api_passed = self.run_api_tests()
        db_passed = self.run_database_tests()

        if not skip_locust:
            locust_passed = self.run_locust_tests()
        else:
            print("\nSkipping Locust tests (use --with-locust to include)")
            locust_passed = None

        self.end_time = datetime.now()

        # Generate summary
        self.generate_summary()

        # Print timing
        duration = (self.end_time - self.start_time).total_seconds()
        print(f"\nTotal Duration: {duration:.1f} seconds")

        # Exit code
        if api_passed and db_passed:
            print("\n✓ All critical tests passed!")
            sys.exit(0)
        else:
            print("\n✗ Some tests failed. Please review the output above.")
            sys.exit(1)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="X-Agent Performance Benchmark Suite"
    )
    parser.add_argument(
        "--with-locust",
        action="store_true",
        help="Include Locust load tests"
    )
    parser.add_argument(
        "--locust-users",
        type=int,
        default=100,
        help="Number of Locust users (default: 100)"
    )
    parser.add_argument(
        "--locust-spawn-rate",
        type=int,
        default=10,
        help="Locust spawn rate (default: 10)"
    )
    parser.add_argument(
        "--locust-time",
        type=str,
        default="5m",
        help="Locust test duration (default: 5m)"
    )

    args = parser.parse_args()

    runner = PerformanceTestRunner()

    try:
        if args.with_locust:
            runner.run_all(skip_locust=False)
        else:
            runner.run_all(skip_locust=True)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
