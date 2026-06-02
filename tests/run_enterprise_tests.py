#!/usr/bin/env python3
"""Enterprise integration test runner and report generator.

Executes comprehensive enterprise tests and generates detailed reports.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class TestReportGenerator:
    """Generate test reports."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "test_suites": {},
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
            },
        }

    def run_tests(self, test_file: str, test_class: str | None = None) -> dict[str, Any]:
        """Run pytest and capture results."""
        cmd = ["python", "-m", "pytest", test_file, "-v", "--tb=short", "--json-report"]
        if test_class:
            cmd.append(f"-k {test_class}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Test execution timed out after 300 seconds",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def parse_pytest_output(self, output: str) -> dict[str, Any]:
        """Parse pytest output."""
        lines = output.split("\n")
        stats = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "tests": [],
        }

        for line in lines:
            if " PASSED" in line:
                stats["passed"] += 1
                stats["tests"].append({"name": line.split(" ")[0], "status": "PASSED"})
            elif " FAILED" in line:
                stats["failed"] += 1
                stats["tests"].append({"name": line.split(" ")[0], "status": "FAILED"})
            elif " SKIPPED" in line:
                stats["skipped"] += 1
                stats["tests"].append({"name": line.split(" ")[0], "status": "SKIPPED"})
            elif " ERROR" in line:
                stats["errors"] += 1
                stats["tests"].append({"name": line.split(" ")[0], "status": "ERROR"})

        return stats

    def add_test_suite(self, name: str, stats: dict[str, Any]) -> None:
        """Add test suite results."""
        self.results["test_suites"][name] = stats
        self.results["summary"]["total_tests"] += stats.get("passed", 0) + stats.get("failed", 0)
        self.results["summary"]["passed"] += stats.get("passed", 0)
        self.results["summary"]["failed"] += stats.get("failed", 0)
        self.results["summary"]["skipped"] += stats.get("skipped", 0)
        self.results["summary"]["errors"] += stats.get("errors", 0)

    def generate_report(self) -> str:
        """Generate comprehensive test report."""
        report = []
        report.append("=" * 80)
        report.append("X-AGENT ENTERPRISE INTEGRATION TEST REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary
        report.append("TEST SUMMARY")
        report.append("-" * 80)
        summary = self.results["summary"]
        report.append(f"Total Tests:    {summary['total_tests']}")
        report.append(f"Passed:         {summary['passed']}")
        report.append(f"Failed:         {summary['failed']}")
        report.append(f"Skipped:        {summary['skipped']}")
        report.append(f"Errors:         {summary['errors']}")
        report.append(f"Success Rate:   {self._calculate_success_rate():.1f}%")
        report.append("")

        # Test Suites
        report.append("TEST SUITES")
        report.append("-" * 80)
        for suite_name, stats in self.results["test_suites"].items():
            report.append(f"\n{suite_name}")
            report.append(f"  Passed:  {stats.get('passed', 0)}")
            report.append(f"  Failed:  {stats.get('failed', 0)}")
            report.append(f"  Skipped: {stats.get('skipped', 0)}")
            report.append(f"  Errors:  {stats.get('errors', 0)}")

        report.append("")
        report.append("=" * 80)
        report.append(f"Report Generated: {self.results['timestamp']}")
        report.append("=" * 80)

        return "\n".join(report)

    def _calculate_success_rate(self) -> float:
        """Calculate success rate."""
        summary = self.results["summary"]
        total = summary["total_tests"]
        if total == 0:
            return 0.0
        return (summary["passed"] / total) * 100

    def save_report(self, filename: str = "test_report.txt") -> Path:
        """Save report to file."""
        report_path = self.output_dir / filename
        report_path.write_text(self.generate_report())
        return report_path

    def save_json_report(self, filename: str = "test_report.json") -> Path:
        """Save JSON report."""
        report_path = self.output_dir / filename
        report_path.write_text(json.dumps(self.results, indent=2))
        return report_path


def run_enterprise_tests() -> int:
    """Run all enterprise integration tests."""
    test_file = "tests/test_enterprise_integration.py"
    output_dir = Path("tests/reports")

    print("Starting X-Agent Enterprise Integration Tests...")
    print(f"Test file: {test_file}")
    print(f"Output directory: {output_dir}")
    print("")

    generator = TestReportGenerator(output_dir)

    # Test suites to run
    test_suites = [
        ("RBAC System", "TestRBACSystem"),
        ("Audit Logging", "TestAuditLogging"),
        ("Data Isolation", "TestDataIsolation"),
        ("API Key Management", "TestAPIKeyManagement"),
        ("Enterprise Deployment", "TestEnterpriseDeployment"),
        ("Integration Scenarios", "TestIntegrationScenarios"),
        ("Performance & Reliability", "TestPerformanceAndReliability"),
        ("Error Handling", "TestErrorHandlingAndEdgeCases"),
    ]

    total_passed = 0
    total_failed = 0

    for suite_name, test_class in test_suites:
        print(f"Running {suite_name}...")
        result = generator.run_tests(test_file, test_class)

        if result["returncode"] == 0:
            print(f"  ✓ {suite_name} passed")
            stats = generator.parse_pytest_output(result["stdout"])
            generator.add_test_suite(suite_name, stats)
            total_passed += stats.get("passed", 0)
        else:
            print(f"  ✗ {suite_name} failed")
            print(f"    Error: {result['stderr'][:200]}")
            total_failed += 1

    print("")
    print("Generating reports...")
    report_path = generator.save_report()
    json_path = generator.save_json_report()

    print(f"Text report: {report_path}")
    print(f"JSON report: {json_path}")
    print("")
    print(generator.generate_report())

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_enterprise_tests())
