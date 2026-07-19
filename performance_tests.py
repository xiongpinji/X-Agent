"""
X-Agent Performance Benchmark Tests

This module provides comprehensive performance testing for X-Agent API endpoints,
database operations, and resource utilization.
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single request."""
    endpoint: str
    method: str
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    p95_time: float
    p99_time: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    throughput_rps: float
    timestamp: str


class PerformanceBenchmark:
    """Performance benchmark suite for X-Agent."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """Initialize benchmark suite.

        Args:
            base_url: Base URL of the API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self.results: List[PerformanceMetrics] = []
        self.auth_token: Optional[str] = None

    async def setup(self) -> None:
        """Setup benchmark environment (e.g., authentication)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Try to login
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={
                        "email": "test@example.com",
                        "password": "Test1234"
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token") or data.get("token")
                    print(f"Authentication successful. Token: {self.auth_token[:20]}...")
                else:
                    print(f"Authentication failed: {response.status_code}")
        except Exception as e:
            print(f"Setup warning: {e}")

    async def measure_endpoint(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> float:
        """Measure single request response time.

        Args:
            method: HTTP method
            url: Full URL
            **kwargs: Additional arguments for httpx.request

        Returns:
            Response time in seconds
        """
        headers = kwargs.pop("headers", {})
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            start = time.time()
            try:
                await client.request(method, url, headers=headers, **kwargs)
                end = time.time()
                return end - start
            except Exception as e:
                print(f"Request error: {e}")
                return None

    async def benchmark_endpoint(
        self,
        method: str,
        url: str,
        num_requests: int = 1000,
        concurrency: int = 10,
        **kwargs
    ) -> PerformanceMetrics:
        """Benchmark a single endpoint.

        Args:
            method: HTTP method
            url: Full URL
            num_requests: Total number of requests
            concurrency: Number of concurrent requests
            **kwargs: Additional arguments for httpx.request

        Returns:
            PerformanceMetrics object
        """
        print(f"\nBenchmarking {method} {url}")
        print(f"  Requests: {num_requests}, Concurrency: {concurrency}")

        times = []
        failed = 0
        start_time = time.time()

        # Create tasks
        tasks = []
        for _ in range(num_requests):
            task = self.measure_endpoint(method, url, **kwargs)
            tasks.append(task)

        # Execute with concurrency limit
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_task(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*[bounded_task(t) for t in tasks], return_exceptions=True)

        # Process results
        for result in results:
            if result is None or isinstance(result, Exception):
                failed += 1
            else:
                times.append(result)

        total_time = time.time() - start_time
        successful = len(times)

        # Calculate statistics
        if times:
            metrics = PerformanceMetrics(
                endpoint=url.replace(self.base_url, ""),
                method=method,
                min_time=min(times),
                max_time=max(times),
                mean_time=statistics.mean(times),
                median_time=statistics.median(times),
                p95_time=self._percentile(times, 95),
                p99_time=self._percentile(times, 99),
                total_requests=num_requests,
                successful_requests=successful,
                failed_requests=failed,
                error_rate=failed / num_requests if num_requests > 0 else 0,
                throughput_rps=num_requests / total_time if total_time > 0 else 0,
                timestamp=datetime.now().isoformat()
            )

            # Print results
            print(f"  Min: {metrics.min_time:.4f}s")
            print(f"  Max: {metrics.max_time:.4f}s")
            print(f"  Mean: {metrics.mean_time:.4f}s")
            print(f"  Median: {metrics.median_time:.4f}s")
            print(f"  P95: {metrics.p95_time:.4f}s")
            print(f"  P99: {metrics.p99_time:.4f}s")
            print(f"  Throughput: {metrics.throughput_rps:.2f} RPS")
            print(f"  Error Rate: {metrics.error_rate:.2%}")

            self.results.append(metrics)
            return metrics
        else:
            print(f"  ERROR: All requests failed!")
            return None

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    async def run_api_benchmarks(self) -> None:
        """Run API performance benchmarks."""
        print("\n" + "=" * 60)
        print("API PERFORMANCE BENCHMARKS")
        print("=" * 60)

        # Health check endpoint
        await self.benchmark_endpoint(
            "GET",
            f"{self.base_url}/health",
            num_requests=5000,
            concurrency=50
        )

        # Auth endpoints
        await self.benchmark_endpoint(
            "POST",
            f"{self.base_url}/api/v1/auth/login",
            num_requests=500,
            concurrency=10,
            json={
                "email": "test@example.com",
                "password": "Test1234"
            }
        )

        # Workflow endpoints
        await self.benchmark_endpoint(
            "GET",
            f"{self.base_url}/api/v1/workflows",
            num_requests=2000,
            concurrency=20
        )

        await self.benchmark_endpoint(
            "POST",
            f"{self.base_url}/api/v1/workflows",
            num_requests=500,
            concurrency=10,
            json={
                "name": "perf-test-workflow",
                "description": "Performance test workflow"
            }
        )

        # Agent endpoints
        await self.benchmark_endpoint(
            "GET",
            f"{self.base_url}/api/v1/agents",
            num_requests=2000,
            concurrency=20
        )

        await self.benchmark_endpoint(
            "POST",
            f"{self.base_url}/api/v1/agents",
            num_requests=500,
            concurrency=10,
            json={
                "name": "perf-test-agent",
                "description": "Performance test agent"
            }
        )

    async def run_concurrent_load_test(self) -> None:
        """Run concurrent load test."""
        print("\n" + "=" * 60)
        print("CONCURRENT LOAD TEST")
        print("=" * 60)

        concurrency_levels = [10, 50, 100, 200]

        for concurrency in concurrency_levels:
            print(f"\nTesting with {concurrency} concurrent users...")
            await self.benchmark_endpoint(
                "GET",
                f"{self.base_url}/api/v1/workflows",
                num_requests=1000,
                concurrency=concurrency
            )

    async def run_stress_test(self) -> None:
        """Run stress test with increasing load."""
        print("\n" + "=" * 60)
        print("STRESS TEST")
        print("=" * 60)

        load_levels = [100, 500, 1000, 2000]

        for load in load_levels:
            print(f"\nStress test with {load} requests...")
            await self.benchmark_endpoint(
                "GET",
                f"{self.base_url}/health",
                num_requests=load,
                concurrency=min(load // 10, 100)
            )

    def generate_report(self, output_file: str = "performance_benchmark_report.json") -> None:
        """Generate performance report.

        Args:
            output_file: Output file path
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "total_endpoints_tested": len(self.results),
            "endpoints": [asdict(m) for m in self.results],
            "summary": self._generate_summary()
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to {output_file}")

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not self.results:
            return {}

        all_means = [m.mean_time for m in self.results]
        all_p95s = [m.p95_time for m in self.results]
        all_throughputs = [m.throughput_rps for m in self.results]
        all_error_rates = [m.error_rate for m in self.results]

        return {
            "average_response_time": statistics.mean(all_means),
            "median_response_time": statistics.median(all_means),
            "max_response_time": max(all_means),
            "average_p95": statistics.mean(all_p95s),
            "average_throughput_rps": statistics.mean(all_throughputs),
            "total_error_rate": statistics.mean(all_error_rates),
            "slowest_endpoint": max(self.results, key=lambda m: m.mean_time).endpoint,
            "fastest_endpoint": min(self.results, key=lambda m: m.mean_time).endpoint,
            "highest_throughput_endpoint": max(self.results, key=lambda m: m.throughput_rps).endpoint
        }

    def print_summary(self) -> None:
        """Print performance summary."""
        if not self.results:
            print("No results to summarize")
            return

        print("\n" + "=" * 60)
        print("PERFORMANCE SUMMARY")
        print("=" * 60)

        summary = self._generate_summary()
        print(f"\nAverage Response Time: {summary['average_response_time']:.4f}s")
        print(f"Median Response Time: {summary['median_response_time']:.4f}s")
        print(f"Max Response Time: {summary['max_response_time']:.4f}s")
        print(f"Average P95: {summary['average_p95']:.4f}s")
        print(f"Average Throughput: {summary['average_throughput_rps']:.2f} RPS")
        print(f"Total Error Rate: {summary['total_error_rate']:.2%}")
        print(f"\nSlowest Endpoint: {summary['slowest_endpoint']}")
        print(f"Fastest Endpoint: {summary['fastest_endpoint']}")
        print(f"Highest Throughput: {summary['highest_throughput_endpoint']}")

        print("\n" + "-" * 60)
        print("ENDPOINT DETAILS")
        print("-" * 60)

        for metric in sorted(self.results, key=lambda m: m.mean_time, reverse=True):
            print(f"\n{metric.method} {metric.endpoint}")
            print(f"  Mean: {metric.mean_time:.4f}s | P95: {metric.p95_time:.4f}s | "
                  f"Throughput: {metric.throughput_rps:.2f} RPS | "
                  f"Error Rate: {metric.error_rate:.2%}")


async def main():
    """Run all benchmarks."""
    benchmark = PerformanceBenchmark(base_url="http://localhost:8000")

    try:
        await benchmark.setup()
        await benchmark.run_api_benchmarks()
        await benchmark.run_concurrent_load_test()
        await benchmark.run_stress_test()
        benchmark.print_summary()
        benchmark.generate_report()
    except Exception as e:
        print(f"Benchmark error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
