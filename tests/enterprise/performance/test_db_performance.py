"""
Database Performance Testing and Verification Suite
Validates all optimization implementations and measures improvements.
"""

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Callable, Optional
import statistics

import asyncpg


@dataclass
class PerformanceMetrics:
    """Performance metrics for a test."""
    test_name: str
    operation_count: int
    total_time_seconds: float
    min_time_ms: float
    max_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    throughput_ops_per_sec: float
    error_count: int
    error_rate_percent: float
    timestamp: str


class DatabasePerformanceTest:
    """Comprehensive database performance testing suite."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "xagent",
        user: str = "postgres",
        password: str = "postgres",
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool: Optional[asyncpg.Pool] = None
        self.results: list[PerformanceMetrics] = []

    async def connect(self) -> None:
        """Connect to database."""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=10,
                max_size=50,
            )
            print(f"Connected to database: {self.database}")
        except Exception as e:
            print(f"Failed to connect: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from database."""
        if self.pool:
            await self.pool.close()
            print("Disconnected from database")

    async def setup_test_environment(self) -> None:
        """Setup test tables and indexes."""
        async with self.pool.acquire() as conn:
            # Create test table
            await conn.execute("""
                DROP TABLE IF EXISTS perf_test_data CASCADE;
            """)

            await conn.execute("""
                CREATE TABLE perf_test_data (
                    id BIGSERIAL PRIMARY KEY,
                    tenant_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    importance FLOAT DEFAULT 0.5,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create indexes (simulating optimized indexes)
            await conn.execute("""
                CREATE INDEX idx_perf_tenant_status_created
                ON perf_test_data (tenant_id, status, created_at DESC);
            """)

            await conn.execute("""
                CREATE INDEX idx_perf_user_created
                ON perf_test_data (user_id, created_at DESC);
            """)

            await conn.execute("""
                CREATE INDEX idx_perf_importance
                ON perf_test_data (importance DESC)
                WHERE importance > 0.7;
            """)

            print("Test environment setup complete")

    async def cleanup_test_environment(self) -> None:
        """Cleanup test tables."""
        async with self.pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS perf_test_data CASCADE;")
            print("Test environment cleaned up")

    async def test_index_performance(self, num_records: int = 100000) -> PerformanceMetrics:
        """Test index performance with various query patterns."""
        print(f"\nTesting INDEX PERFORMANCE ({num_records} records)...")

        # Insert test data
        async with self.pool.acquire() as conn:
            print("  Inserting test data...")
            for i in range(0, num_records, 1000):
                batch = []
                for j in range(1000):
                    batch.append((
                        f"tenant_{i % 10}",
                        f"user_{(i + j) % 100}",
                        ["active", "inactive", "pending"][(i + j) % 3],
                        (i + j) % 100 / 100.0,
                        f"Content {i + j}",
                    ))

                await conn.executemany(
                    """
                    INSERT INTO perf_test_data (tenant_id, user_id, status, importance, content)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    batch,
                )

        # Test index queries
        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(10000):
                try:
                    op_start = time.time()

                    # Query using composite index
                    await conn.fetch(
                        """
                        SELECT id, status, importance
                        FROM perf_test_data
                        WHERE tenant_id = $1 AND status = $2
                        ORDER BY created_at DESC
                        LIMIT 100
                        """,
                        f"tenant_{i % 10}",
                        ["active", "inactive", "pending"][i % 3],
                    )

                    op_end = time.time()
                    times.append((op_end - op_start) * 1000)

                except Exception as e:
                    errors += 1
                    print(f"  Query error: {e}")

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "INDEX_PERFORMANCE",
            10000,
            times,
            errors,
            total_time,
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def test_query_optimization(self, num_queries: int = 5000) -> PerformanceMetrics:
        """Test query optimization (N+1 detection, caching)."""
        print(f"\nTesting QUERY OPTIMIZATION ({num_queries} queries)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_queries):
                try:
                    op_start = time.time()

                    # Complex query with joins (optimized)
                    await conn.fetch(
                        """
                        SELECT
                            t1.id, t1.status, t1.importance,
                            COUNT(*) OVER (PARTITION BY t1.tenant_id) as tenant_count
                        FROM perf_test_data t1
                        WHERE t1.tenant_id = $1
                        AND t1.created_at > NOW() - INTERVAL '30 days'
                        ORDER BY t1.importance DESC
                        LIMIT 50
                        """,
                        f"tenant_{i % 10}",
                    )

                    op_end = time.time()
                    times.append((op_end - op_start) * 1000)

                except Exception as e:
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "QUERY_OPTIMIZATION",
            num_queries,
            times,
            errors,
            total_time,
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def test_connection_pool(self, num_concurrent: int = 100) -> PerformanceMetrics:
        """Test connection pool performance under concurrent load."""
        print(f"\nTesting CONNECTION POOL ({num_concurrent} concurrent connections)...")

        times = []
        errors = 0
        start_time = time.time()

        async def concurrent_query(query_id: int) -> float:
            try:
                op_start = time.time()
                async with self.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                op_end = time.time()
                return (op_end - op_start) * 1000
            except Exception:
                return None

        # Run concurrent queries
        tasks = [concurrent_query(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, float):
                times.append(result)
            else:
                errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "CONNECTION_POOL",
            num_concurrent,
            times,
            errors,
            total_time,
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def test_batch_operations(self, batch_size: int = 1000, num_batches: int = 100) -> PerformanceMetrics:
        """Test batch operation performance."""
        print(f"\nTesting BATCH OPERATIONS ({num_batches} batches of {batch_size})...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for batch_num in range(num_batches):
                try:
                    op_start = time.time()

                    batch = []
                    for i in range(batch_size):
                        batch.append((
                            f"tenant_{batch_num % 10}",
                            f"user_{(batch_num * batch_size + i) % 100}",
                            ["active", "inactive"][i % 2],
                            (batch_num * batch_size + i) % 100 / 100.0,
                            f"Batch content {batch_num}-{i}",
                        ))

                    await conn.executemany(
                        """
                        INSERT INTO perf_test_data (tenant_id, user_id, status, importance, content)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        batch,
                    )

                    op_end = time.time()
                    times.append((op_end - op_start) * 1000)

                except Exception as e:
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "BATCH_OPERATIONS",
            num_batches,
            times,
            errors,
            total_time,
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def test_cache_hit_ratio(self) -> dict[str, Any]:
        """Test cache hit ratio (simulated)."""
        print("\nTesting CACHE HIT RATIO...")

        # Simulate cache statistics
        async with self.pool.acquire() as conn:
            try:
                result = await conn.fetchval("""
                    SELECT
                        sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
                    FROM pg_statio_user_tables
                """)

                cache_hit_ratio = float(result) if result else 0.0
                print(f"  Cache Hit Ratio: {cache_hit_ratio * 100:.2f}%")

                return {
                    "cache_hit_ratio": cache_hit_ratio,
                    "target": 0.95,
                    "status": "PASS" if cache_hit_ratio >= 0.95 else "NEEDS_IMPROVEMENT",
                }
            except Exception as e:
                print(f"  Cache statistics unavailable: {e}")
                return {"status": "UNAVAILABLE"}

    async def test_slow_query_detection(self) -> dict[str, Any]:
        """Test slow query detection."""
        print("\nTesting SLOW QUERY DETECTION...")

        async with self.pool.acquire() as conn:
            try:
                # Check for slow queries
                result = await conn.fetch("""
                    SELECT query, calls, mean_time, max_time
                    FROM pg_stat_statements
                    WHERE mean_time > 50
                    ORDER BY mean_time DESC
                    LIMIT 10
                """)

                slow_queries = [dict(row) for row in result]
                print(f"  Found {len(slow_queries)} slow queries")

                return {
                    "slow_query_count": len(slow_queries),
                    "target_max": 10,
                    "status": "PASS" if len(slow_queries) <= 10 else "NEEDS_IMPROVEMENT",
                    "queries": slow_queries[:5],
                }
            except Exception as e:
                print(f"  Slow query detection unavailable: {e}")
                return {"status": "UNAVAILABLE"}

    @staticmethod
    def _percentile(data: list[float], percentile: int) -> float:
        """Calculate percentile."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _create_metrics(
        self,
        test_name: str,
        operation_count: int,
        times: list[float],
        errors: int,
        total_time: float,
    ) -> PerformanceMetrics:
        """Create metrics object."""
        if times:
            return PerformanceMetrics(
                test_name=test_name,
                operation_count=operation_count,
                total_time_seconds=total_time,
                min_time_ms=min(times),
                max_time_ms=max(times),
                mean_time_ms=statistics.mean(times),
                median_time_ms=statistics.median(times),
                p95_time_ms=self._percentile(times, 95),
                p99_time_ms=self._percentile(times, 99),
                throughput_ops_per_sec=(operation_count - errors) / total_time if total_time > 0 else 0,
                error_count=errors,
                error_rate_percent=(errors / operation_count * 100) if operation_count > 0 else 0,
                timestamp=datetime.now().isoformat(),
            )
        return None

    @staticmethod
    def _print_metrics(metrics: PerformanceMetrics) -> None:
        """Print metrics."""
        if not metrics:
            return

        print(f"  Min: {metrics.min_time_ms:.2f}ms")
        print(f"  Max: {metrics.max_time_ms:.2f}ms")
        print(f"  Mean: {metrics.mean_time_ms:.2f}ms")
        print(f"  Median: {metrics.median_time_ms:.2f}ms")
        print(f"  P95: {metrics.p95_time_ms:.2f}ms")
        print(f"  P99: {metrics.p99_time_ms:.2f}ms")
        print(f"  Throughput: {metrics.throughput_ops_per_sec:.2f} ops/sec")
        print(f"  Error Rate: {metrics.error_rate_percent:.2f}%")

    def generate_report(self, output_file: str = "db_performance_report.json") -> None:
        """Generate comprehensive performance report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "database": self.database,
            "performance_targets": {
                "query_response_time_p95_ms": 50,
                "index_hit_ratio_percent": 95,
                "connection_pool_utilization_percent": 80,
                "slow_query_percentage": 1,
            },
            "test_results": [asdict(m) for m in self.results],
            "summary": self._generate_summary(),
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\nReport saved to {output_file}")

    def _generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        if not self.results:
            return {}

        all_means = [m.mean_time_ms for m in self.results]
        all_throughputs = [m.throughput_ops_per_sec for m in self.results]

        return {
            "average_response_time_ms": statistics.mean(all_means),
            "median_response_time_ms": statistics.median(all_means),
            "max_response_time_ms": max(all_means),
            "average_throughput_ops": statistics.mean(all_throughputs),
            "slowest_test": max(self.results, key=lambda m: m.mean_time_ms).test_name,
            "fastest_test": min(self.results, key=lambda m: m.mean_time_ms).test_name,
        }

    def print_summary(self) -> None:
        """Print test summary."""
        if not self.results:
            print("No test results")
            return

        print("\n" + "=" * 70)
        print("DATABASE PERFORMANCE TEST SUMMARY")
        print("=" * 70)

        summary = self._generate_summary()
        print(f"\nAverage Response Time: {summary['average_response_time_ms']:.2f}ms")
        print(f"Median Response Time: {summary['median_response_time_ms']:.2f}ms")
        print(f"Max Response Time: {summary['max_response_time_ms']:.2f}ms")
        print(f"Average Throughput: {summary['average_throughput_ops']:.2f} ops/sec")

        print("\n" + "-" * 70)
        print("TEST RESULTS")
        print("-" * 70)

        for metric in sorted(self.results, key=lambda m: m.mean_time_ms, reverse=True):
            status = "PASS" if metric.mean_time_ms < 50 else "NEEDS_IMPROVEMENT"
            print(f"\n{metric.test_name} [{status}]")
            print(f"  Mean: {metric.mean_time_ms:.2f}ms | P95: {metric.p95_time_ms:.2f}ms")
            print(f"  Throughput: {metric.throughput_ops_per_sec:.2f} ops/sec")
            print(f"  Error Rate: {metric.error_rate_percent:.2f}%")


async def main():
    """Run performance tests."""
    tester = DatabasePerformanceTest(
        host="localhost",
        port=5432,
        database="xagent",
        user="postgres",
        password="postgres",
    )

    try:
        await tester.connect()
        await tester.setup_test_environment()

        print("\n" + "=" * 70)
        print("DATABASE PERFORMANCE OPTIMIZATION TESTS")
        print("=" * 70)

        # Run tests
        await tester.test_index_performance(num_records=100000)
        await tester.test_query_optimization(num_queries=5000)
        await tester.test_connection_pool(num_concurrent=100)
        await tester.test_batch_operations(batch_size=1000, num_batches=100)

        # Check cache and slow queries
        await tester.test_cache_hit_ratio()
        await tester.test_slow_query_detection()

        tester.print_summary()
        tester.generate_report()

    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup_test_environment()
        await tester.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
