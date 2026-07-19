"""X-Agent Test Execution Orchestrator.

This module provides comprehensive test execution, categorization,
and reporting capabilities for the X-Agent project.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from test_config import (
    COVERAGE_CONFIG,
    COVERAGE_DIR,
    PYTEST_CONFIG,
    REPORTS_DIR,
    TEST_CATEGORIES,
    TEST_ENV_VARS,
    TESTS_DIR,
    setup_test_environment,
)


class TestExecutor:
    """Orchestrates test execution and reporting."""

    def __init__(self):
        """Initialize test executor."""
        self.project_root = Path(__file__).parent.parent
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results: Dict[str, Any] = {}
        setup_test_environment()

    def run_command(
        self, cmd: List[str], cwd: Optional[Path] = None
    ) -> Tuple[int, str, str]:
        """Run a shell command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out after 3600 seconds"
        except Exception as e:
            return 1, "", str(e)

    def check_environment(self) -> bool:
        """Check if test environment is properly configured."""
        print("\n" + "=" * 60)
        print("ENVIRONMENT CHECK")
        print("=" * 60)

        # Check Python version
        version_cmd = [sys.executable, "--version"]
        code, stdout, stderr = self.run_command(version_cmd)
        version = stdout or stderr
        print(f"✓ Python version: {version.strip()}")

        # Check pytest
        pytest_cmd = [sys.executable, "-m", "pytest", "--version"]
        code, stdout, stderr = self.run_command(pytest_cmd)
        if code != 0:
            print("✗ pytest not installed")
            return False
        print(f"✓ pytest: {stdout.strip()}")

        # Check pytest-cov
        cov_cmd = [sys.executable, "-m", "pip", "show", "pytest-cov"]
        code, stdout, stderr = self.run_command(cov_cmd)
        if code != 0:
            print("✗ pytest-cov not installed")
            return False
        print("✓ pytest-cov installed")

        # Check pytest-asyncio
        async_cmd = [sys.executable, "-m", "pip", "show", "pytest-asyncio"]
        code, stdout, stderr = self.run_command(async_cmd)
        if code != 0:
            print("✗ pytest-asyncio not installed")
            return False
        print("✓ pytest-asyncio installed")

        # Create report directories
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"✓ Report directories created")

        return True

    def run_test_category(
        self, category: str, test_files: List[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Run tests for a specific category."""
        print(f"\n{'=' * 60}")
        print(f"RUNNING {category.upper()} TESTS ({len(test_files)} files)")
        print(f"{'=' * 60}")

        report_file = REPORTS_DIR / f"{category}_{self.timestamp}.json"
        junit_file = REPORTS_DIR / f"{category}_{self.timestamp}.xml"
        log_file = REPORTS_DIR / f"{category}_{self.timestamp}.log"

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            *test_files,
            "--tb=short",
            "--verbose",
            f"--junit-xml={junit_file}",
            "-v",
        ]

        print(f"Command: {' '.join(cmd)}\n")

        code, stdout, stderr = self.run_command(cmd)

        # Save output
        with open(log_file, "w") as f:
            f.write(stdout)
            if stderr:
                f.write("\n--- STDERR ---\n")
                f.write(stderr)

        # Parse results
        passed = "passed" in stdout
        failed = "failed" in stdout or code != 0

        result = {
            "category": category,
            "status": "passed" if code == 0 else "failed",
            "exit_code": code,
            "test_count": len(test_files),
            "log_file": str(log_file),
            "junit_file": str(junit_file),
        }

        if code == 0:
            print(f"✓ {category} tests passed")
        else:
            print(f"✗ {category} tests failed")
            print(f"  Log: {log_file}")

        return code == 0, result

    def run_all_tests_with_coverage(self) -> Tuple[bool, Dict[str, Any]]:
        """Run all tests with coverage reporting."""
        print(f"\n{'=' * 60}")
        print("RUNNING ALL TESTS WITH COVERAGE")
        print(f"{'=' * 60}")

        coverage_file = COVERAGE_DIR / f"coverage_{self.timestamp}.json"
        html_dir = COVERAGE_DIR / f"html_{self.timestamp}"
        log_file = REPORTS_DIR / f"coverage_{self.timestamp}.log"

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--cov=backend",
            "--cov=data",
            "--cov=scripts",
            f"--cov-report=json:{coverage_file}",
            f"--cov-report=html:{html_dir}",
            "--cov-report=term-missing",
            "--cov-report=term",
            "--tb=short",
            "-v",
            "--durations=10",
        ]

        print(f"Command: {' '.join(cmd)}\n")

        code, stdout, stderr = self.run_command(cmd)

        # Save output
        with open(log_file, "w") as f:
            f.write(stdout)
            if stderr:
                f.write("\n--- STDERR ---\n")
                f.write(stderr)

        result = {
            "status": "passed" if code == 0 else "failed",
            "exit_code": code,
            "coverage_file": str(coverage_file),
            "html_dir": str(html_dir),
            "log_file": str(log_file),
        }

        if code == 0:
            print(f"✓ All tests passed with coverage")
            print(f"  Coverage HTML: {html_dir}/index.html")
        else:
            print(f"✗ Tests failed")
            print(f"  Log: {log_file}")

        return code == 0, result

    def generate_test_summary(self) -> None:
        """Generate comprehensive test summary report."""
        summary_file = REPORTS_DIR / f"TEST_SUMMARY_{self.timestamp}.md"

        content = f"""# X-Agent Test Execution Summary

## Execution Information
- **Date**: {datetime.now().isoformat()}
- **Timestamp**: {self.timestamp}
- **Project**: X-Agent Core
- **Python**: {sys.version}

## Test Categories

### Unit Tests
- **Purpose**: Individual component testing
- **Isolation**: High (mocked dependencies)
- **Parallelizable**: Yes
- **Typical Duration**: 5-10 minutes

### Integration Tests
- **Purpose**: Component interaction testing
- **Isolation**: Medium (real database connections)
- **Parallelizable**: No
- **Typical Duration**: 10-15 minutes

### Contract Tests
- **Purpose**: API contract validation
- **Isolation**: High (schema validation)
- **Parallelizable**: Yes
- **Typical Duration**: 5 minutes

### Runtime Tests
- **Purpose**: Runtime behavior validation
- **Isolation**: Medium
- **Parallelizable**: No
- **Typical Duration**: 5 minutes

### E2E Tests
- **Purpose**: End-to-end workflow testing
- **Isolation**: Low (full system)
- **Parallelizable**: No
- **Typical Duration**: 15-30 minutes

## Coverage Targets

| Module | Target | Status |
|--------|--------|--------|
| backend/app | 85% | TBD |
| backend/core | 90% | TBD |
| data | 80% | TBD |
| scripts | 75% | TBD |

## Test Execution Plan

1. **Phase 1**: Environment validation
2. **Phase 2**: Unit tests (fast feedback)
3. **Phase 3**: Integration tests
4. **Phase 4**: Contract tests
5. **Phase 5**: Runtime tests
6. **Phase 6**: E2E tests (optional)
7. **Phase 7**: Coverage analysis

## Estimated Execution Time

- Unit Tests: ~5-10 minutes
- Integration Tests: ~10-15 minutes
- Contract Tests: ~5 minutes
- Runtime Tests: ~5 minutes
- E2E Tests: ~15-30 minutes (optional)
- **Total**: ~40-65 minutes

## Report Locations

- Test Reports: `test-reports/`
- Coverage Reports: `coverage-reports/`
- HTML Coverage: `coverage-reports/html_*/index.html`

## Test Results

{json.dumps(self.results, indent=2)}

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run Tests
  run: python scripts/test_executor.py all
```

### GitLab CI
```yaml
test:
  script:
    - python scripts/test_executor.py all
```

## Failure Handling

- Unit test failures: Block merge
- Integration test failures: Block merge
- Contract test failures: Block merge
- E2E test failures: Warning only
- Coverage below target: Warning

## Next Steps

1. Review coverage reports
2. Identify low-coverage areas
3. Add tests for critical paths
4. Update coverage targets
5. Integrate into CI/CD pipeline

---
Generated by X-Agent Test Executor
"""

        with open(summary_file, "w") as f:
            f.write(content)

        print(f"\n✓ Summary generated: {summary_file}")

    def generate_coverage_analysis(self) -> None:
        """Generate coverage analysis report."""
        analysis_file = COVERAGE_DIR / f"COVERAGE_ANALYSIS_{self.timestamp}.md"

        content = """# Coverage Analysis Report

## Summary
- Generated: {datetime}
- Project: X-Agent Core

## Coverage by Module

### backend/app
- Core application logic
- Target: 85%
- Critical paths: API handlers, auth, workflows

### backend/core
- Core business logic
- Target: 90%
- Critical paths: Agent loop, memory, tools

### data
- Data models and persistence
- Target: 80%
- Critical paths: Database operations

### scripts
- Utility scripts
- Target: 75%
- Critical paths: Deployment, monitoring

## Low Coverage Areas

Areas requiring additional test coverage:
1. Error handling paths
2. Edge cases in data validation
3. Async operation failures
4. Resource cleanup scenarios
5. Concurrent access patterns

## Recommendations

### Increase Unit Test Coverage
- Add tests for error paths
- Test edge cases
- Mock external dependencies

### Improve Integration Tests
- Test database transactions
- Verify async operations
- Test concurrent access

### Add Contract Tests
- Validate API schemas
- Test request/response formats
- Verify error responses

### E2E Test Scenarios
- Complete workflows
- Multi-step operations
- Error recovery

## Coverage Improvement Plan

| Phase | Target | Timeline |
|-------|--------|----------|
| Phase 1 | 70% | Week 1 |
| Phase 2 | 80% | Week 2 |
| Phase 3 | 85% | Week 3 |
| Phase 4 | 90% | Week 4 |

## Action Items

1. [ ] Review low-coverage files
2. [ ] Create test plan for critical paths
3. [ ] Implement missing tests
4. [ ] Verify coverage improvements
5. [ ] Update CI/CD thresholds

---
Generated by X-Agent Test Executor
""".format(datetime=datetime.now().isoformat())

        with open(analysis_file, "w") as f:
            f.write(content)

        print(f"✓ Coverage analysis generated: {analysis_file}")

    def run_all(self) -> bool:
        """Run complete test suite."""
        if not self.check_environment():
            return False

        all_passed = True

        # Run categorized tests
        for category, config in TEST_CATEGORIES.items():
            if category == "e2e":
                continue  # Skip E2E by default

            # Get test files for category
            test_files = self._get_test_files_for_category(category)
            if not test_files:
                print(f"⚠ No test files found for {category}")
                continue

            passed, result = self.run_test_category(category, test_files)
            self.results[category] = result
            all_passed = all_passed and passed

        # Run with coverage
        passed, result = self.run_all_tests_with_coverage()
        self.results["coverage"] = result
        all_passed = all_passed and passed

        # Generate reports
        self.generate_test_summary()
        self.generate_coverage_analysis()

        return all_passed

    def _get_test_files_for_category(self, category: str) -> List[str]:
        """Get test files for a specific category."""
        # This is a simplified version - in practice, you'd parse test markers
        test_dir = TESTS_DIR
        test_files = []

        if category == "unit":
            patterns = [
                "test_llm_router.py",
                "test_persistence.py",
                "test_postgres_trace.py",
                "test_postgres_memory.py",
                "test_memory_vector.py",
                "test_tools.py",
                "test_observability.py",
                "test_security.py",
                "test_audit.py",
                "test_approvals.py",
            ]
        elif category == "integration":
            patterns = [
                "test_api.py",
                "test_runs.py",
                "test_workflow_worker.py",
                "test_browser_service.py",
                "test_memory_api.py",
                "test_workflow_run_detail.py",
            ]
        elif category == "contracts":
            patterns = [
                "test_api_contracts.py",
                "test_end_to_end_contracts.py",
                "test_open_source_contracts.py",
            ]
        elif category == "runtime":
            patterns = ["runtime/"]
        elif category == "e2e":
            patterns = ["e2e/"]
        else:
            return []

        for pattern in patterns:
            if pattern.endswith("/"):
                # Directory pattern
                subdir = test_dir / pattern
                if subdir.exists():
                    test_files.extend(
                        [str(f) for f in subdir.glob("test_*.py")]
                    )
            else:
                # File pattern
                test_file = test_dir / pattern
                if test_file.exists():
                    test_files.append(str(test_file))

        return test_files

    def run_category(self, category: str) -> bool:
        """Run tests for a specific category."""
        if not self.check_environment():
            return False

        test_files = self._get_test_files_for_category(category)
        if not test_files:
            print(f"✗ No test files found for {category}")
            return False

        passed, result = self.run_test_category(category, test_files)
        self.results[category] = result
        return passed


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="X-Agent Test Execution Orchestrator"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["all", "unit", "integration", "contracts", "runtime", "e2e", "coverage"],
        help="Test command to run",
    )

    args = parser.parse_args()

    executor = TestExecutor()

    if args.command == "all":
        success = executor.run_all()
    elif args.command == "coverage":
        success, _ = executor.run_all_tests_with_coverage()
    else:
        success = executor.run_category(args.command)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
