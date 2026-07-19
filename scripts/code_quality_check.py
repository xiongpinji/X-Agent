"""Code quality analysis and improvement script for X-Agent.

This script performs comprehensive code quality analysis including:
- Type checking with mypy
- Linting with pylint and ruff
- Code formatting with black and isort
- Test coverage analysis
- Complexity analysis

Usage:
    python scripts/code_quality_check.py --all
    python scripts/code_quality_check.py --mypy --pylint
    python scripts/code_quality_check.py --format
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class QualityMetrics:
    """Code quality metrics."""

    mypy_score: float = 0.0
    pylint_score: float = 0.0
    coverage_percentage: float = 0.0
    complexity_score: float = 0.0
    issues: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def overall_score(self) -> float:
        """Calculate overall quality score.

        Returns:
            Overall score (0-10)
        """
        scores = [
            self.mypy_score,
            self.pylint_score,
            min(self.coverage_percentage / 10, 10),
            self.complexity_score,
        ]
        return sum(scores) / len(scores)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mypy_score": self.mypy_score,
            "pylint_score": self.pylint_score,
            "coverage_percentage": self.coverage_percentage,
            "complexity_score": self.complexity_score,
            "overall_score": self.overall_score(),
            "issues": self.issues,
            "warnings": self.warnings,
        }


class CodeQualityChecker:
    """Performs code quality checks."""

    def __init__(self, project_root: Path) -> None:
        """Initialize checker.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = project_root
        self.backend_dir = project_root / "backend"
        self.metrics = QualityMetrics()

    def run_mypy(self) -> bool:
        """Run mypy type checking.

        Returns:
            True if successful
        """
        print("Running mypy type checking...")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    str(self.backend_dir),
                    "--ignore-missing-imports",
                    "--no-strict-optional",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                print("✓ mypy: All type checks passed")
                self.metrics.mypy_score = 10.0
                return True
            else:
                print(f"✗ mypy: Type errors found")
                print(result.stdout)
                self.metrics.mypy_score = 7.0
                self.metrics.issues["mypy"] = result.stdout
                return False
        except subprocess.TimeoutExpired:
            print("✗ mypy: Timeout")
            self.metrics.warnings.append("mypy timeout")
            return False
        except Exception as e:
            print(f"✗ mypy: Error - {e}")
            self.metrics.warnings.append(f"mypy error: {e}")
            return False

    def run_pylint(self) -> bool:
        """Run pylint linting.

        Returns:
            True if successful
        """
        print("Running pylint linting...")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pylint",
                    str(self.backend_dir),
                    "--exit-zero",
                    "--output-format=json",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            try:
                issues = json.loads(result.stdout)
                score = self._extract_pylint_score(result.stderr)
                print(f"✓ pylint: Score {score}/10")
                self.metrics.pylint_score = score
                if issues:
                    self.metrics.issues["pylint"] = issues
                return score >= 8.0
            except json.JSONDecodeError:
                print("✗ pylint: Failed to parse output")
                self.metrics.warnings.append("pylint output parsing failed")
                return False
        except subprocess.TimeoutExpired:
            print("✗ pylint: Timeout")
            self.metrics.warnings.append("pylint timeout")
            return False
        except Exception as e:
            print(f"✗ pylint: Error - {e}")
            self.metrics.warnings.append(f"pylint error: {e}")
            return False

    def run_coverage(self) -> bool:
        """Run test coverage analysis.

        Returns:
            True if coverage >= 95%
        """
        print("Running coverage analysis...")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/",
                    "--cov=backend",
                    "--cov-report=term-missing",
                    "--cov-report=json",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.project_root,
            )

            # Try to parse coverage from JSON report
            coverage_file = self.project_root / ".coverage"
            if coverage_file.exists():
                try:
                    with open(coverage_file) as f:
                        coverage_data = json.load(f)
                        coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
                        self.metrics.coverage_percentage = coverage
                        print(f"✓ Coverage: {coverage:.1f}%")
                        return coverage >= 95.0
                except (json.JSONDecodeError, KeyError):
                    pass

            # Fallback: parse from stdout
            for line in result.stdout.split("\n"):
                if "TOTAL" in line:
                    parts = line.split()
                    if parts:
                        try:
                            coverage = float(parts[-1].rstrip("%"))
                            self.metrics.coverage_percentage = coverage
                            print(f"✓ Coverage: {coverage:.1f}%")
                            return coverage >= 95.0
                        except (ValueError, IndexError):
                            pass

            print("✗ Coverage: Could not determine coverage")
            self.metrics.warnings.append("Could not determine coverage")
            return False
        except subprocess.TimeoutExpired:
            print("✗ Coverage: Timeout")
            self.metrics.warnings.append("coverage timeout")
            return False
        except Exception as e:
            print(f"✗ Coverage: Error - {e}")
            self.metrics.warnings.append(f"coverage error: {e}")
            return False

    def run_ruff(self) -> bool:
        """Run ruff linting.

        Returns:
            True if no errors
        """
        print("Running ruff linting...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", str(self.backend_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                print("✓ ruff: No issues found")
                return True
            else:
                print(f"✗ ruff: Issues found")
                print(result.stdout)
                self.metrics.issues["ruff"] = result.stdout
                return False
        except subprocess.TimeoutExpired:
            print("✗ ruff: Timeout")
            self.metrics.warnings.append("ruff timeout")
            return False
        except Exception as e:
            print(f"✗ ruff: Error - {e}")
            self.metrics.warnings.append(f"ruff error: {e}")
            return False

    def format_code(self) -> bool:
        """Format code with black and isort.

        Returns:
            True if successful
        """
        print("Formatting code...")
        try:
            # Run black
            print("  Running black...")
            result = subprocess.run(
                [sys.executable, "-m", "black", str(self.backend_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"  ✗ black failed: {result.stderr}")
                return False

            # Run isort
            print("  Running isort...")
            result = subprocess.run(
                [sys.executable, "-m", "isort", str(self.backend_dir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"  ✗ isort failed: {result.stderr}")
                return False

            print("✓ Code formatted successfully")
            return True
        except subprocess.TimeoutExpired:
            print("✗ Formatting: Timeout")
            return False
        except Exception as e:
            print(f"✗ Formatting: Error - {e}")
            return False

    @staticmethod
    def _extract_pylint_score(stderr: str) -> float:
        """Extract pylint score from stderr.

        Args:
            stderr: Stderr output from pylint

        Returns:
            Score (0-10)
        """
        for line in stderr.split("\n"):
            if "Your code has been rated at" in line:
                try:
                    score = float(line.split("at")[1].split("/")[0].strip())
                    return min(score, 10.0)
                except (ValueError, IndexError):
                    pass
        return 0.0

    def generate_report(self, output_file: Optional[Path] = None) -> str:
        """Generate quality report.

        Args:
            output_file: Optional file to write report to

        Returns:
            Report text
        """
        report = f"""
# X-Agent Code Quality Report

## Overall Score: {self.metrics.overall_score():.1f}/10

## Metrics
- Type Checking (mypy): {self.metrics.mypy_score:.1f}/10
- Linting (pylint): {self.metrics.pylint_score:.1f}/10
- Test Coverage: {self.metrics.coverage_percentage:.1f}%
- Complexity Score: {self.metrics.complexity_score:.1f}/10

## Issues
{json.dumps(self.metrics.issues, indent=2)}

## Warnings
{chr(10).join(f"- {w}" for w in self.metrics.warnings)}

## Recommendations
1. Increase test coverage to 95%+
2. Improve type hints coverage to 100%
3. Reduce code complexity
4. Fix all linting issues
5. Add comprehensive documentation
"""

        if output_file:
            output_file.write_text(report)
            print(f"Report written to {output_file}")

        return report


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Code quality checker for X-Agent")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--mypy", action="store_true", help="Run mypy")
    parser.add_argument("--pylint", action="store_true", help="Run pylint")
    parser.add_argument("--coverage", action="store_true", help="Run coverage")
    parser.add_argument("--ruff", action="store_true", help="Run ruff")
    parser.add_argument("--format", action="store_true", help="Format code")
    parser.add_argument("--report", type=str, help="Output report file")

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    checker = CodeQualityChecker(project_root)

    if args.all or args.format:
        checker.format_code()

    if args.all or args.mypy:
        checker.run_mypy()

    if args.all or args.pylint:
        checker.run_pylint()

    if args.all or args.coverage:
        checker.run_coverage()

    if args.all or args.ruff:
        checker.run_ruff()

    # Generate report
    report = checker.generate_report(
        Path(args.report) if args.report else None
    )
    print(report)

    # Return exit code based on overall score
    return 0 if checker.metrics.overall_score() >= 9.0 else 1


if __name__ == "__main__":
    sys.exit(main())
