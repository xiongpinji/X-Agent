"""Analyze and report test coverage gaps."""

import json
import subprocess
from pathlib import Path
from typing import Any


def run_coverage_analysis(output_dir: str = "coverage-reports") -> dict[str, Any]:
    """Run pytest with coverage analysis."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Run pytest with coverage
    cmd = [
        "pytest",
        "tests/",
        f"--cov=backend",
        f"--cov-report=json:{output_path}/coverage.json",
        f"--cov-report=html:{output_path}/html",
        f"--cov-report=term-missing",
        "-v",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse coverage report
    coverage_file = output_path / "coverage.json"
    if coverage_file.exists():
        with open(coverage_file) as f:
            coverage_data = json.load(f)
        return coverage_data

    return {}


def analyze_coverage_gaps(coverage_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze coverage gaps and identify critical areas."""
    summary = coverage_data.get("totals", {})
    files = coverage_data.get("files", {})

    # Identify files with low coverage
    low_coverage_files = []
    for file_path, file_data in files.items():
        coverage_pct = file_data.get("summary", {}).get("percent_covered", 0)
        if coverage_pct < 70:
            low_coverage_files.append(
                {
                    "file": file_path,
                    "coverage": coverage_pct,
                    "lines": file_data.get("summary", {}).get("num_statements", 0),
                    "missing": file_data.get("summary", {}).get("missing_lines", 0),
                }
            )

    # Sort by coverage percentage
    low_coverage_files.sort(key=lambda x: x["coverage"])

    return {
        "overall_coverage": summary.get("percent_covered", 0),
        "total_lines": summary.get("num_statements", 0),
        "covered_lines": summary.get("num_statements", 0)
        - summary.get("missing_lines", 0),
        "missing_lines": summary.get("missing_lines", 0),
        "low_coverage_files": low_coverage_files,
    }


def generate_coverage_report(
    analysis: dict[str, Any], output_file: str = "COVERAGE_REPORT.md"
) -> None:
    """Generate a markdown coverage report."""
    with open(output_file, "w") as f:
        f.write("# Test Coverage Report\n\n")

        f.write("## Summary\n\n")
        f.write(f"- **Overall Coverage**: {analysis['overall_coverage']:.1f}%\n")
        f.write(f"- **Total Lines**: {analysis['total_lines']}\n")
        f.write(f"- **Covered Lines**: {analysis['covered_lines']}\n")
        f.write(f"- **Missing Lines**: {analysis['missing_lines']}\n\n")

        # Coverage target
        target = 85
        current = analysis["overall_coverage"]
        gap = target - current

        if current >= target:
            f.write(f"✅ **Target Met**: Coverage is {current:.1f}% (target: {target}%)\n\n")
        else:
            f.write(
                f"⚠️ **Gap to Target**: {gap:.1f}% (current: {current:.1f}%, target: {target}%)\n\n"
            )

        # Low coverage files
        if analysis["low_coverage_files"]:
            f.write("## Files with Low Coverage (<70%)\n\n")
            f.write("| File | Coverage | Lines | Missing |\n")
            f.write("|------|----------|-------|----------|\n")

            for file_info in analysis["low_coverage_files"]:
                f.write(
                    f"| {file_info['file']} | {file_info['coverage']:.1f}% | "
                    f"{file_info['lines']} | {file_info['missing']} |\n"
                )

            f.write("\n")

        # Recommendations
        f.write("## Recommendations\n\n")

        if current < 70:
            f.write("### Critical Priority\n")
            f.write("- Coverage is below 70%. Focus on core modules first.\n")
            f.write("- Add tests for critical paths in low-coverage files.\n\n")

        if current < 85:
            f.write("### High Priority\n")
            f.write("- Add integration tests for API endpoints.\n")
            f.write("- Add tests for error handling and edge cases.\n")
            f.write("- Focus on files with <50% coverage.\n\n")

        f.write("### Medium Priority\n")
        f.write("- Add performance tests for critical operations.\n")
        f.write("- Add security tests for authentication/authorization.\n")
        f.write("- Add tests for concurrent operations.\n\n")

        f.write("### Low Priority\n")
        f.write("- Add tests for utility functions.\n")
        f.write("- Add tests for logging and monitoring.\n")

    print(f"Coverage report saved to {output_file}")


def identify_critical_modules() -> list[str]:
    """Identify critical modules that need high coverage."""
    critical_modules = [
        "backend/app/core/security.py",
        "backend/app/core/llm.py",
        "backend/app/core/memory_postgres.py",
        "backend/app/api/auth.py",
        "backend/app/api/agents.py",
        "backend/app/api/workflows.py",
        "backend/app/services/browser/automation.py",
        "backend/app/services/memory/retriever.py",
        "backend/app/core/audit.py",
    ]
    return critical_modules


def generate_coverage_targets() -> dict[str, int]:
    """Generate coverage targets for each module."""
    targets = {
        # Core security modules - must be 100%
        "backend/app/core/security.py": 100,
        "backend/app/api/auth.py": 100,
        "backend/app/core/audit.py": 95,
        # Core business logic - 90%+
        "backend/app/core/llm.py": 90,
        "backend/app/core/memory_postgres.py": 90,
        "backend/app/api/agents.py": 85,
        "backend/app/api/workflows.py": 85,
        # Services - 85%+
        "backend/app/services/browser/automation.py": 85,
        "backend/app/services/memory/retriever.py": 85,
        # Utilities - 70%+
        "backend/app/core/tracing.py": 70,
        "backend/app/services/observability/langfuse_client.py": 70,
    }
    return targets


if __name__ == "__main__":
    print("Running coverage analysis...")
    coverage_data = run_coverage_analysis()

    if coverage_data:
        print("Analyzing coverage gaps...")
        analysis = analyze_coverage_gaps(coverage_data)

        print("Generating coverage report...")
        generate_coverage_report(analysis)

        print("\nCritical modules requiring high coverage:")
        for module in identify_critical_modules():
            print(f"  - {module}")

        print("\nCoverage targets by module:")
        targets = generate_coverage_targets()
        for module, target in targets.items():
            print(f"  - {module}: {target}%")

        print("\nCoverage analysis complete!")
    else:
        print("Failed to generate coverage data")
