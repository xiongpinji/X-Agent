#!/usr/bin/env python3
"""
API Endpoints Testing Script

Tests all 66 new API endpoints for accessibility and basic functionality.
Generates a comprehensive test report.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EndpointStatus(Enum):
    """Endpoint test status."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class EndpointTest:
    """Test result for a single endpoint."""
    name: str
    method: str
    path: str
    status: EndpointStatus
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class APIEndpointTester:
    """Test all API endpoints."""

    # All 66 new API endpoints organized by system
    ENDPOINTS = {
        "streaming": [
            ("GET", "/api/v1/agent/stream/{run_id}", "Stream agent execution"),
            ("POST", "/api/v1/agent/stream/subscribe", "Subscribe to stream"),
            ("DELETE", "/api/v1/agent/stream/{run_id}", "Unsubscribe from stream"),
            ("GET", "/api/v1/agent/stream/status", "Get stream status"),
        ],
        "tasks_ui": [
            ("GET", "/api/v1/tasks", "List all tasks"),
            ("POST", "/api/v1/tasks", "Create new task"),
            ("GET", "/api/v1/tasks/{task_id}", "Get task details"),
            ("PUT", "/api/v1/tasks/{task_id}", "Update task"),
            ("DELETE", "/api/v1/tasks/{task_id}", "Delete task"),
            ("POST", "/api/v1/tasks/{task_id}/complete", "Mark task complete"),
            ("GET", "/api/v1/tasks/filter", "Filter tasks"),
            ("POST", "/api/v1/tasks/batch", "Batch task operations"),
        ],
        "questions": [
            ("POST", "/api/v1/questions/ask", "Ask interactive question"),
            ("GET", "/api/v1/questions/{question_id}", "Get question details"),
            ("POST", "/api/v1/questions/{question_id}/answer", "Submit answer"),
            ("GET", "/api/v1/questions/pending", "Get pending questions"),
            ("DELETE", "/api/v1/questions/{question_id}", "Dismiss question"),
            ("POST", "/api/v1/questions/batch", "Batch question operations"),
        ],
        "file_preview": [
            ("GET", "/api/v1/files/preview/{file_id}", "Preview file"),
            ("POST", "/api/v1/files/preview/generate", "Generate preview"),
            ("GET", "/api/v1/files/preview/formats", "Get supported formats"),
            ("POST", "/api/v1/files/preview/cache", "Cache preview"),
            ("DELETE", "/api/v1/files/preview/{file_id}", "Clear preview cache"),
        ],
        "parallel_agents": [
            ("POST", "/api/v1/agents/parallel/spawn", "Spawn parallel agents"),
            ("GET", "/api/v1/agents/parallel/{batch_id}/status", "Get batch status"),
            ("GET", "/api/v1/agents/parallel/{batch_id}/results", "Get batch results"),
            ("POST", "/api/v1/agents/parallel/{batch_id}/cancel", "Cancel batch"),
            ("GET", "/api/v1/agents/parallel/batches", "List all batches"),
            ("POST", "/api/v1/agents/parallel/communicate", "Inter-agent communication"),
            ("GET", "/api/v1/agents/parallel/{batch_id}/logs", "Get batch logs"),
        ],
        "browser_advanced": [
            ("GET", "/api/v1/browser/advanced/network", "Get network requests"),
            ("GET", "/api/v1/browser/advanced/performance", "Get performance metrics"),
            ("GET", "/api/v1/browser/advanced/console", "Get console logs"),
            ("POST", "/api/v1/browser/advanced/record", "Start recording"),
            ("POST", "/api/v1/browser/advanced/stop-record", "Stop recording"),
            ("GET", "/api/v1/browser/advanced/har", "Export HAR file"),
            ("POST", "/api/v1/browser/advanced/screenshot", "Take screenshot"),
            ("GET", "/api/v1/browser/advanced/dom", "Get DOM snapshot"),
        ],
        "workspace": [
            ("POST", "/api/v1/workspace/create", "Create workspace"),
            ("GET", "/api/v1/workspace/{workspace_id}", "Get workspace info"),
            ("DELETE", "/api/v1/workspace/{workspace_id}", "Delete workspace"),
            ("POST", "/api/v1/workspace/{workspace_id}/mount", "Mount directory"),
            ("POST", "/api/v1/workspace/{workspace_id}/unmount", "Unmount directory"),
            ("GET", "/api/v1/workspace/{workspace_id}/files", "List workspace files"),
            ("POST", "/api/v1/workspace/{workspace_id}/upload", "Upload file"),
            ("GET", "/api/v1/workspace/list", "List all workspaces"),
        ],
        "tools_batch": [
            ("POST", "/api/v1/tools/batch/execute", "Execute batch tools"),
            ("GET", "/api/v1/tools/batch/{batch_id}/status", "Get batch status"),
            ("GET", "/api/v1/tools/batch/{batch_id}/results", "Get batch results"),
            ("POST", "/api/v1/tools/batch/{batch_id}/cancel", "Cancel batch"),
            ("GET", "/api/v1/tools/batch/history", "Get batch history"),
            ("POST", "/api/v1/tools/batch/validate", "Validate batch request"),
        ],
        "memory_enhanced": [
            ("POST", "/api/v1/memory/store", "Store memory"),
            ("GET", "/api/v1/memory/recall", "Recall memory"),
            ("GET", "/api/v1/memory/search", "Search memories"),
            ("POST", "/api/v1/memory/relate", "Create memory relationship"),
            ("GET", "/api/v1/memory/related/{memory_id}", "Get related memories"),
            ("POST", "/api/v1/memory/merge", "Merge memories"),
            ("GET", "/api/v1/memory/stats", "Get memory statistics"),
            ("DELETE", "/api/v1/memory/{memory_id}", "Delete memory"),
            ("POST", "/api/v1/memory/export", "Export memories"),
            ("POST", "/api/v1/memory/import", "Import memories"),
        ],
    }

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 10):
        """Initialize tester.

        Args:
            base_url: Base URL of the API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results: List[EndpointTest] = []
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    async def test_endpoint(
        self,
        method: str,
        path: str,
        description: str,
        tags: List[str],
        skip: bool = False,
    ) -> EndpointTest:
        """Test a single endpoint.

        Args:
            method: HTTP method
            path: Endpoint path
            description: Endpoint description
            tags: Endpoint tags
            skip: Whether to skip this test

        Returns:
            EndpointTest result
        """
        if skip:
            return EndpointTest(
                name=description,
                method=method,
                path=path,
                status=EndpointStatus.SKIP,
                tags=tags,
            )

        url = f"{self.base_url}{path}"
        start_time = datetime.now()

        try:
            # Replace path parameters with dummy values
            test_url = url.replace("{run_id}", "test-run-id")
            test_url = test_url.replace("{batch_id}", "test-batch-id")
            test_url = test_url.replace("{task_id}", "test-task-id")
            test_url = test_url.replace("{question_id}", "test-question-id")
            test_url = test_url.replace("{file_id}", "test-file-id")
            test_url = test_url.replace("{workspace_id}", "test-workspace-id")
            test_url = test_url.replace("{memory_id}", "test-memory-id")

            # Make request
            if method == "GET":
                response = await self.client.get(test_url)
            elif method == "POST":
                response = await self.client.post(test_url, json={})
            elif method == "PUT":
                response = await self.client.put(test_url, json={})
            elif method == "DELETE":
                response = await self.client.delete(test_url)
            else:
                raise ValueError(f"Unsupported method: {method}")

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Determine status
            if response.status_code < 500:
                status = EndpointStatus.PASS
            else:
                status = EndpointStatus.FAIL

            return EndpointTest(
                name=description,
                method=method,
                path=path,
                status=status,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                tags=tags,
            )

        except httpx.ConnectError as e:
            return EndpointTest(
                name=description,
                method=method,
                path=path,
                status=EndpointStatus.ERROR,
                error_message=f"Connection error: {str(e)}",
                tags=tags,
            )
        except httpx.TimeoutException as e:
            return EndpointTest(
                name=description,
                method=method,
                path=path,
                status=EndpointStatus.ERROR,
                error_message=f"Timeout: {str(e)}",
                tags=tags,
            )
        except Exception as e:
            return EndpointTest(
                name=description,
                method=method,
                path=path,
                status=EndpointStatus.ERROR,
                error_message=f"Error: {str(e)}",
                tags=tags,
            )

    async def run_all_tests(self) -> List[EndpointTest]:
        """Run all endpoint tests.

        Returns:
            List of test results
        """
        logger.info(f"Starting API endpoint tests against {self.base_url}")
        logger.info(f"Total endpoints to test: {sum(len(v) for v in self.ENDPOINTS.values())}")

        for system, endpoints in self.ENDPOINTS.items():
            logger.info(f"Testing {system} system ({len(endpoints)} endpoints)...")
            for method, path, description in endpoints:
                result = await self.test_endpoint(
                    method=method,
                    path=path,
                    description=description,
                    tags=[system],
                )
                self.results.append(result)
                logger.debug(f"  {method} {path}: {result.status.value}")

        return self.results

    def generate_report(self) -> Dict[str, Any]:
        """Generate test report.

        Returns:
            Report dictionary
        """
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == EndpointStatus.PASS)
        failed = sum(1 for r in self.results if r.status == EndpointStatus.FAIL)
        errors = sum(1 for r in self.results if r.status == EndpointStatus.ERROR)
        skipped = sum(1 for r in self.results if r.status == EndpointStatus.SKIP)

        avg_response_time = (
            sum(r.response_time_ms for r in self.results if r.response_time_ms > 0)
            / max(1, sum(1 for r in self.results if r.response_time_ms > 0))
        )

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_endpoints": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "pass_rate": f"{(passed / max(1, total - skipped) * 100):.1f}%",
                "avg_response_time_ms": f"{avg_response_time:.2f}",
            },
            "results_by_system": {},
            "failed_endpoints": [],
            "error_endpoints": [],
            "all_results": [asdict(r) for r in self.results],
        }

        # Group results by system
        for system in self.ENDPOINTS.keys():
            system_results = [r for r in self.results if system in r.tags]
            system_passed = sum(1 for r in system_results if r.status == EndpointStatus.PASS)
            report["results_by_system"][system] = {
                "total": len(system_results),
                "passed": system_passed,
                "pass_rate": f"{(system_passed / max(1, len(system_results)) * 100):.1f}%",
            }

        # Collect failed and error endpoints
        for result in self.results:
            if result.status == EndpointStatus.FAIL:
                report["failed_endpoints"].append({
                    "method": result.method,
                    "path": result.path,
                    "status_code": result.status_code,
                })
            elif result.status == EndpointStatus.ERROR:
                report["error_endpoints"].append({
                    "method": result.method,
                    "path": result.path,
                    "error": result.error_message,
                })

        return report

    def save_report(self, output_path: Path) -> None:
        """Save report to file.

        Args:
            output_path: Path to save report
        """
        report = self.generate_report()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {output_path}")

    def print_summary(self) -> None:
        """Print test summary."""
        report = self.generate_report()
        summary = report["summary"]

        print("\n" + "=" * 60)
        print("API ENDPOINT TEST REPORT")
        print("=" * 60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"\nSummary:")
        print(f"  Total Endpoints: {summary['total_endpoints']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Errors: {summary['errors']}")
        print(f"  Skipped: {summary['skipped']}")
        print(f"  Pass Rate: {summary['pass_rate']}")
        print(f"  Avg Response Time: {summary['avg_response_time_ms']}ms")

        print(f"\nResults by System:")
        for system, stats in report["results_by_system"].items():
            print(f"  {system}: {stats['passed']}/{stats['total']} ({stats['pass_rate']})")

        if report["failed_endpoints"]:
            print(f"\nFailed Endpoints:")
            for endpoint in report["failed_endpoints"]:
                print(f"  {endpoint['method']} {endpoint['path']} (HTTP {endpoint['status_code']})")

        if report["error_endpoints"]:
            print(f"\nError Endpoints:")
            for endpoint in report["error_endpoints"]:
                print(f"  {endpoint['method']} {endpoint['path']}: {endpoint['error']}")

        print("=" * 60 + "\n")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test X-Agent API endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API server",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("api_test_report.json"),
        help="Output report file path",
    )

    args = parser.parse_args()

    async with APIEndpointTester(
        base_url=args.base_url,
        timeout=args.timeout,
    ) as tester:
        await tester.run_all_tests()
        tester.print_summary()
        tester.save_report(args.output)

        # Exit with appropriate code
        report = tester.generate_report()
        if report["summary"]["failed"] > 0 or report["summary"]["errors"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
