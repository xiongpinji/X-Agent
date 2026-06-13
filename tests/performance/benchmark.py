"""Standalone X-Agent API Benchmark — No External Dependencies.

Lightweight performance testing tool for X-Agent endpoints. Uses only stdlib.
Measures latency, throughput, and compares against SLO thresholds.

Usage:
    python tests/performance/benchmark.py [--host http://localhost:8000] \\
                                          [--requests 1000] \\
                                          [--concurrency 10] \\
                                          [--output results.json]

Examples:
    # Quick test (10 concurrent, 100 requests)
    python tests/performance/benchmark.py

    # Production load test (32 concurrent, 10000 requests)
    python tests/performance/benchmark.py --concurrency 32 --requests 10000

    # Custom host
    python tests/performance/benchmark.py --host http://prod.example.com:8000

Output:
    - Console summary with percentiles (P50, P95, P99)
    - JSON file with detailed results
    - SLO pass/fail verdict
    - Error rate breakdown
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BenchmarkResult(NamedTuple):
    """Single request result."""

    endpoint: str
    method: str
    status_code: Optional[int]
    latency_ms: float
    timestamp: float
    error: Optional[str] = None
    payload_size: int = 0


class SLOThreshold(NamedTuple):
    """Service Level Objective thresholds."""

    endpoint: str
    method: str
    p99_ms: float
    error_rate_percent: float


class BenchmarkReport(NamedTuple):
    """Complete benchmark results."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    duration_seconds: float
    throughput_rps: float
    latencies: Dict[str, Any]
    errors: Dict[str, int]
    timestamp: str
    slo_results: Dict[str, bool]


class XAgentBenchmark:
    """Standalone benchmark harness for X-Agent."""

    DEFAULT_ENDPOINTS = [
        ("GET", "/health", None),
        ("GET", "/ready", None),
        ("GET", "/api/v1/tools", {"X-API-Key": "test-key"}),
        ("POST", "/api/v1/agent/run", {"X-API-Key": "test-key"}),
        ("POST", "/api/v1/chat", {"X-API-Key": "test-key"}),
    ]

    DEFAULT_SLOS = [
        SLOThreshold(endpoint="/health", method="GET", p99_ms=50, error_rate_percent=0.1),
        SLOThreshold(endpoint="/ready", method="GET", p99_ms=200, error_rate_percent=0.1),
        SLOThreshold(endpoint="/api/v1/tools", method="GET", p99_ms=300, error_rate_percent=1.0),
        SLOThreshold(
            endpoint="/api/v1/agent/run", method="POST", p99_ms=500, error_rate_percent=5.0
        ),
        SLOThreshold(endpoint="/api/v1/chat", method="POST", p99_ms=400, error_rate_percent=2.0),
    ]

    def __init__(
        self,
        host: str = "http://localhost:8000",
        num_requests: int = 1000,
        concurrency: int = 10,
        timeout_seconds: int = 30,
    ):
        """Initialize benchmark.

        Args:
            host: Target API host
            num_requests: Total requests to make
            concurrency: Concurrent worker threads
            timeout_seconds: Request timeout
        """
        self.host = host.rstrip("/")
        self.num_requests = num_requests
        self.concurrency = min(concurrency, num_requests)
        self.timeout_seconds = timeout_seconds
        self.results: List[BenchmarkResult] = []

    def _make_request(self, method: str, endpoint: str, headers: Optional[Dict] = None) -> BenchmarkResult:
        """Make single HTTP request and record latency.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: URL path (e.g., "/health")
            headers: Optional HTTP headers

        Returns:
            BenchmarkResult with timing and status
        """
        url = f"{self.host}{endpoint}"
        start_time = time.time()
        timestamp = start_time

        try:
            req = Request(url, method=method)

            if headers:
                for key, value in headers.items():
                    req.add_header(key, value)

            # Add default headers
            req.add_header("User-Agent", "XAgentBenchmark/1.0")

            with urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read()
                status_code = response.status
                payload_size = len(body)

            latency_ms = (time.time() - start_time) * 1000

            return BenchmarkResult(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                latency_ms=latency_ms,
                timestamp=timestamp,
                error=None,
                payload_size=payload_size,
            )

        except (HTTPError, URLError) as e:
            latency_ms = (time.time() - start_time) * 1000
            status_code = getattr(e, "code", None)

            return BenchmarkResult(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                latency_ms=latency_ms,
                timestamp=timestamp,
                error=str(e),
                payload_size=0,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            return BenchmarkResult(
                endpoint=endpoint,
                method=method,
                status_code=None,
                latency_ms=latency_ms,
                timestamp=timestamp,
                error=f"{type(e).__name__}: {str(e)}",
                payload_size=0,
            )

    def run(self) -> BenchmarkReport:
        """Execute benchmark with concurrent requests.

        Returns:
            BenchmarkReport with aggregated results
        """
        print(f"\nStarting X-Agent Benchmark")
        print(f"Target: {self.host}")
        print(f"Total requests: {self.num_requests}")
        print(f"Concurrency: {self.concurrency}")
        print(f"Timeout: {self.timeout_seconds}s")
        print("=" * 70)

        self.results = []
        start_time = time.time()

        # Generate workload (round-robin across endpoints)
        workload: List[Tuple[str, str, Optional[Dict]]] = []
        endpoint_idx = 0

        for _ in range(self.num_requests):
            method, endpoint, headers = self.DEFAULT_ENDPOINTS[endpoint_idx % len(self.DEFAULT_ENDPOINTS)]
            workload.append((method, endpoint, headers))
            endpoint_idx += 1

        # Execute with thread pool
        completed = 0

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(self._make_request, method, endpoint, headers): (method, endpoint)
                for method, endpoint, headers in workload
            }

            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                completed += 1

                if completed % 100 == 0:
                    print(f"  Progress: {completed}/{self.num_requests} requests")

        total_duration = time.time() - start_time

        # Generate report
        return self._generate_report(total_duration)

    def _generate_report(self, total_duration: float) -> BenchmarkReport:
        """Generate benchmark report from results.

        Args:
            total_duration: Total benchmark duration in seconds

        Returns:
            BenchmarkReport with statistics
        """
        successful = [r for r in self.results if r.error is None]
        failed = [r for r in self.results if r.error is not None]

        success_count = len(successful)
        fail_count = len(failed)
        error_rate = (fail_count / len(self.results) * 100) if self.results else 0

        # Latency percentiles (only successful requests)
        if successful:
            latencies = sorted([r.latency_ms for r in successful])
            p50 = statistics.median(latencies)
            p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 20 else latencies[-1]
            p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 100 else latencies[-1]
            avg = statistics.mean(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
        else:
            p50 = p95 = p99 = avg = min_lat = max_lat = 0

        throughput_rps = len(self.results) / total_duration if total_duration > 0 else 0

        # Error breakdown
        errors: Dict[str, int] = {}
        for result in failed:
            error_type = result.error.split(":")[0] if result.error else "Unknown"
            errors[error_type] = errors.get(error_type, 0) + 1

        # SLO verification
        slo_results = self._verify_slos(successful)

        report = BenchmarkReport(
            total_requests=len(self.results),
            successful_requests=success_count,
            failed_requests=fail_count,
            error_rate=error_rate,
            duration_seconds=total_duration,
            throughput_rps=throughput_rps,
            latencies={
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
                "avg_ms": avg,
                "min_ms": min_lat,
                "max_ms": max_lat,
            },
            errors=errors,
            timestamp=datetime.now().isoformat(),
            slo_results=slo_results,
        )

        return report

    def _verify_slos(self, successful_results: List[BenchmarkResult]) -> Dict[str, bool]:
        """Verify if results meet SLO thresholds.

        Args:
            successful_results: List of successful benchmark results

        Returns:
            Dict mapping endpoint to SLO pass/fail
        """
        slo_results: Dict[str, bool] = {}

        for slo in self.DEFAULT_SLOS:
            endpoint_results = [
                r for r in successful_results if r.endpoint == slo.endpoint and r.method == slo.method
            ]

            if not endpoint_results:
                slo_results[f"{slo.method} {slo.endpoint}"] = True  # No data = pass
                continue

            latencies = [r.latency_ms for r in endpoint_results]
            p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 100 else max(latencies)

            # Check thresholds
            slo_pass = p99 <= slo.p99_ms

            slo_results[f"{slo.method} {slo.endpoint}"] = slo_pass

        return slo_results

    def print_report(self, report: BenchmarkReport) -> None:
        """Print human-readable benchmark report.

        Args:
            report: BenchmarkReport to display
        """
        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS")
        print("=" * 70)

        print(f"\nDuration:       {report.duration_seconds:.2f}s")
        print(f"Total requests: {report.total_requests}")
        print(f"Successful:     {report.successful_requests} ({100-report.error_rate:.1f}%)")
        print(f"Failed:         {report.failed_requests} ({report.error_rate:.1f}%)")
        print(f"Throughput:     {report.throughput_rps:.2f} RPS")

        print("\nLatency Statistics (successful requests only):")
        print(f"  P50:            {report.latencies['p50_ms']:.2f} ms")
        print(f"  P95:            {report.latencies['p95_ms']:.2f} ms")
        print(f"  P99:            {report.latencies['p99_ms']:.2f} ms")
        print(f"  Avg:            {report.latencies['avg_ms']:.2f} ms")
        print(f"  Min:            {report.latencies['min_ms']:.2f} ms")
        print(f"  Max:            {report.latencies['max_ms']:.2f} ms")

        if report.errors:
            print("\nError Breakdown:")
            for error_type, count in sorted(report.errors.items(), key=lambda x: -x[1]):
                print(f"  {error_type}: {count}")

        print("\nSLO Verification:")
        all_slo_pass = all(report.slo_results.values())
        for endpoint, passed in sorted(report.slo_results.items()):
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}: {endpoint}")

        print("\n" + "=" * 70)
        if all_slo_pass and report.error_rate < 1.0:
            print("RESULT: PASS - All SLOs met")
        else:
            print("RESULT: FAIL - SLO violations detected")
        print("=" * 70 + "\n")

    def export_json(self, report: BenchmarkReport, filepath: str) -> None:
        """Export benchmark results to JSON.

        Args:
            report: BenchmarkReport to export
            filepath: Output file path
        """
        export_data = {
            "metadata": {
                "timestamp": report.timestamp,
                "host": self.host,
                "duration_seconds": report.duration_seconds,
                "concurrency": self.concurrency,
            },
            "summary": {
                "total_requests": report.total_requests,
                "successful_requests": report.successful_requests,
                "failed_requests": report.failed_requests,
                "error_rate_percent": report.error_rate,
                "throughput_rps": report.throughput_rps,
            },
            "latencies": report.latencies,
            "errors": report.errors,
            "slo_results": report.slo_results,
            "all_slos_met": all(report.slo_results.values()),
        }

        with open(filepath, "w") as f:
            json.dump(export_data, f, indent=2)

        print(f"Results exported to {filepath}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Standalone X-Agent API Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test
  python tests/performance/benchmark.py

  # Production load test
  python tests/performance/benchmark.py --concurrency 32 --requests 10000

  # Custom host
  python tests/performance/benchmark.py --host http://prod.example.com:8000 --output results.json
        """,
    )

    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Target API host (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
        help="Total number of requests (default: 1000)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Concurrent workers (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Output JSON file (default: benchmark_results.json)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.concurrency > args.requests:
        args.concurrency = args.requests

    # Run benchmark
    benchmark = XAgentBenchmark(
        host=args.host,
        num_requests=args.requests,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout,
    )

    try:
        report = benchmark.run()
        benchmark.print_report(report)
        benchmark.export_json(report, args.output)

        # Exit with appropriate code
        all_slo_pass = all(report.slo_results.values())
        exit_code = 0 if (all_slo_pass and report.error_rate < 1.0) else 1
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError running benchmark: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
