"""API Performance Testing Suite

Comprehensive performance testing for X-Agent APIs:
- Load testing
- Stress testing
- Latency profiling
- Throughput measurement
- Resource utilization monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("xagent.perf_test")


@dataclass
class LoadTestResult:
    """Load test result."""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    requests_per_second: float
    error_rate: float

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class LoadTester:
    """Load testing for APIs."""

    def __init__(self, concurrent_users: int = 10, duration_seconds: int = 60):
        self.concurrent_users = concurrent_users
        self.duration_seconds = duration_seconds
        self.response_times: list[float] = []
        self.errors: list[str] = []

    async def run_test(
        self,
        test_name: str,
        request_fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> LoadTestResult:
        """Run load test."""
        logger.info(f"Starting load test: {test_name}")
        logger.info(f"Concurrent users: {self.concurrent_users}, Duration: {self.duration_seconds}s")

        self.response_times.clear()
        self.errors.clear()

        start_time = time.time()
        tasks = []

        for _ in range(self.concurrent_users):
            task = asyncio.create_task(
                self._user_session(request_fn, start_time, *args, **kwargs)
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        return self._calculate_result(test_name, total_time)

    async def _user_session(
        self,
        request_fn: Callable,
        start_time: float,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Simulate a user session."""
        while time.time() - start_time < self.duration_seconds:
            try:
                request_start = time.time()
                await request_fn(*args, **kwargs)
                response_time = (time.time() - request_start) * 1000
                self.response_times.append(response_time)
            except Exception as e:
                self.errors.append(str(e))

    def _calculate_result(self, test_name: str, total_time: float) -> LoadTestResult:
        """Calculate test result."""
        total_requests = len(self.response_times) + len(self.errors)
        successful_requests = len(self.response_times)
        failed_requests = len(self.errors)

        if not self.response_times:
            return LoadTestResult(
                test_name=test_name,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                total_time_seconds=total_time,
                avg_response_time_ms=0.0,
                p50_response_time_ms=0.0,
                p95_response_time_ms=0.0,
                p99_response_time_ms=0.0,
                max_response_time_ms=0.0,
                min_response_time_ms=0.0,
                requests_per_second=0.0,
                error_rate=1.0 if total_requests > 0 else 0.0,
            )

        response_times_sorted = sorted(self.response_times)
        n = len(response_times_sorted)

        return LoadTestResult(
            test_name=test_name,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_time_seconds=total_time,
            avg_response_time_ms=sum(self.response_times) / len(self.response_times),
            p50_response_time_ms=response_times_sorted[n // 2],
            p95_response_time_ms=response_times_sorted[int(n * 0.95)],
            p99_response_time_ms=response_times_sorted[int(n * 0.99)],
            max_response_time_ms=max(self.response_times),
            min_response_time_ms=min(self.response_times),
            requests_per_second=successful_requests / total_time if total_time > 0 else 0.0,
            error_rate=failed_requests / total_requests if total_requests > 0 else 0.0,
        )


class StressTester:
    """Stress testing for APIs."""

    def __init__(self, max_concurrent_users: int = 1000, ramp_up_seconds: int = 60):
        self.max_concurrent_users = max_concurrent_users
        self.ramp_up_seconds = ramp_up_seconds
        self.response_times: list[float] = []
        self.errors: list[str] = []

    async def run_test(
        self,
        test_name: str,
        request_fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run stress test."""
        logger.info(f"Starting stress test: {test_name}")
        logger.info(f"Max users: {self.max_concurrent_users}, Ramp-up: {self.ramp_up_seconds}s")

        self.response_times.clear()
        self.errors.clear()

        start_time = time.time()
        tasks = []
        current_users = 0
        ramp_up_step = self.max_concurrent_users / (self.ramp_up_seconds * 10)

        while current_users < self.max_concurrent_users:
            # Add new users gradually
            for _ in range(int(ramp_up_step)):
                task = asyncio.create_task(
                    self._user_session(request_fn, *args, **kwargs)
                )
                tasks.append(task)
                current_users += 1

            await asyncio.sleep(0.1)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        return self._calculate_result(test_name, total_time)

    async def _user_session(
        self,
        request_fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Simulate a user session."""
        try:
            request_start = time.time()
            await request_fn(*args, **kwargs)
            response_time = (time.time() - request_start) * 1000
            self.response_times.append(response_time)
        except Exception as e:
            self.errors.append(str(e))

    def _calculate_result(self, test_name: str, total_time: float) -> dict[str, Any]:
        """Calculate test result."""
        total_requests = len(self.response_times) + len(self.errors)
        successful_requests = len(self.response_times)
        failed_requests = len(self.errors)

        if not self.response_times:
            return {
                "test_name": test_name,
                "status": "FAILED",
                "reason": "No successful requests",
            }

        response_times_sorted = sorted(self.response_times)
        n = len(response_times_sorted)

        return {
            "test_name": test_name,
            "status": "PASSED" if failed_requests == 0 else "DEGRADED",
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "total_time_seconds": total_time,
            "avg_response_time_ms": sum(self.response_times) / len(self.response_times),
            "p95_response_time_ms": response_times_sorted[int(n * 0.95)],
            "p99_response_time_ms": response_times_sorted[int(n * 0.99)],
            "max_response_time_ms": max(self.response_times),
            "requests_per_second": successful_requests / total_time if total_time > 0 else 0.0,
            "error_rate": failed_requests / total_requests if total_requests > 0 else 0.0,
        }


class LatencyProfiler:
    """Profile API latency."""

    def __init__(self):
        self.latencies: dict[str, list[float]] = {}

    async def profile_endpoint(
        self,
        endpoint_name: str,
        request_fn: Callable,
        iterations: int = 100,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Profile endpoint latency."""
        logger.info(f"Profiling {endpoint_name} ({iterations} iterations)")

        latencies = []
        for _ in range(iterations):
            try:
                start = time.time()
                await request_fn(*args, **kwargs)
                latency = (time.time() - start) * 1000
                latencies.append(latency)
            except Exception as e:
                logger.error(f"Error during profiling: {e}")

        self.latencies[endpoint_name] = latencies
        return self._calculate_stats(endpoint_name, latencies)

    def _calculate_stats(self, endpoint_name: str, latencies: list[float]) -> dict[str, Any]:
        """Calculate latency statistics."""
        if not latencies:
            return {}

        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)

        return {
            "endpoint": endpoint_name,
            "iterations": n,
            "avg_latency_ms": sum(latencies) / n,
            "p50_latency_ms": latencies_sorted[n // 2],
            "p95_latency_ms": latencies_sorted[int(n * 0.95)],
            "p99_latency_ms": latencies_sorted[int(n * 0.99)],
            "max_latency_ms": max(latencies),
            "min_latency_ms": min(latencies),
            "stddev_latency_ms": self._calculate_stddev(latencies),
        }

    @staticmethod
    def _calculate_stddev(values: list[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5


class ThroughputMeasurer:
    """Measure API throughput."""

    async def measure_throughput(
        self,
        operation_name: str,
        operation_fn: Callable,
        duration_seconds: int = 60,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Measure throughput of an operation."""
        logger.info(f"Measuring throughput for {operation_name} ({duration_seconds}s)")

        operation_count = 0
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            try:
                await operation_fn(*args, **kwargs)
                operation_count += 1
            except Exception as e:
                logger.error(f"Error during throughput measurement: {e}")

        total_time = time.time() - start_time
        throughput = operation_count / total_time if total_time > 0 else 0.0

        return {
            "operation": operation_name,
            "total_operations": operation_count,
            "duration_seconds": total_time,
            "throughput_ops_per_sec": throughput,
        }


class PerformanceTestSuite:
    """Complete performance test suite."""

    def __init__(self):
        self.load_tester = LoadTester()
        self.stress_tester = StressTester()
        self.latency_profiler = LatencyProfiler()
        self.throughput_measurer = ThroughputMeasurer()
        self.results: list[dict[str, Any]] = []

    async def run_all_tests(
        self,
        test_name: str,
        request_fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run all performance tests."""
        logger.info(f"Running complete performance test suite: {test_name}")

        results = {
            "test_name": test_name,
            "load_test": None,
            "stress_test": None,
            "latency_profile": None,
            "throughput": None,
        }

        # Run load test
        try:
            load_result = await self.load_tester.run_test(
                f"{test_name}_load",
                request_fn,
                *args,
                **kwargs,
            )
            results["load_test"] = load_result.__dict__
        except Exception as e:
            logger.error(f"Load test failed: {e}")

        # Run stress test
        try:
            stress_result = await self.stress_tester.run_test(
                f"{test_name}_stress",
                request_fn,
                *args,
                **kwargs,
            )
            results["stress_test"] = stress_result
        except Exception as e:
            logger.error(f"Stress test failed: {e}")

        # Profile latency
        try:
            latency_result = await self.latency_profiler.profile_endpoint(
                f"{test_name}_latency",
                request_fn,
                iterations=100,
                *args,
                **kwargs,
            )
            results["latency_profile"] = latency_result
        except Exception as e:
            logger.error(f"Latency profiling failed: {e}")

        # Measure throughput
        try:
            throughput_result = await self.throughput_measurer.measure_throughput(
                f"{test_name}_throughput",
                request_fn,
                duration_seconds=30,
                *args,
                **kwargs,
            )
            results["throughput"] = throughput_result
        except Exception as e:
            logger.error(f"Throughput measurement failed: {e}")

        self.results.append(results)
        return results

    def get_summary(self) -> dict[str, Any]:
        """Get test summary."""
        return {
            "total_tests": len(self.results),
            "results": self.results,
        }
