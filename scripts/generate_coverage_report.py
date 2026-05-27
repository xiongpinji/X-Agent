"""Script to generate test coverage report."""
import subprocess
import sys
from pathlib import Path


def run_coverage_report():
    """Generate coverage report and HTML output."""
    project_root = Path(__file__).parent.parent

    # Run pytest with coverage
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--cov=backend/app",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-report=json",
        "-v",
    ]

    print("Running coverage analysis...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode == 0:
        print("\nCoverage report generated successfully!")
        print(f"HTML report: {project_root}/htmlcov/index.html")
    else:
        print(f"\nCoverage analysis failed with return code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    run_coverage_report()
