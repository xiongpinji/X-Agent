"""
Database Performance Tests for X-Agent

Tests database operations including queries, inserts, updates, and transactions.
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg


@dataclass
class DatabaseMetrics:
    """Database operation metrics."""
    operation: str
    num_operations: int
    min_time: float
    max_time: float
    mean_time: float
    median_time: float
    p95_time: float
    p99_time: float
    throughput_ops: float
    error_count: int
    error_rate: float
    timestamp: str


class DatabaseBenchmark:
    """Database performance benchmark suite."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "xagent",
        user: str = "postgres",
        password: str = "postgres"
    ):
        """Initialize database benchmark.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool: Optional[asyncpg.Pool] = None
        self.results: List[DatabaseMetrics] = []

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
                max_size=20
            )
            print(f"Connected to database: {self.database}")
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from database."""
        if self.pool:
            await self.pool.close()
            print("Disconnected from database")

    async def setup_test_tables(self) -> None:
        """Create test tables."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DROP TABLE IF EXISTS perf_test_data CASCADE;
            """)

            await conn.execute("""
                CREATE TABLE perf_test_data (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    value INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await conn.execute("""
                CREATE INDEX idx_perf_test_name ON perf_test_data(name);
            """)

            await conn.execute("""
                CREATE INDEX idx_perf_test_value ON perf_test_data(value);
            """)

            print("Test tables created")

    async def cleanup_test_tables(self) -> None:
        """Drop test tables."""
        async with self.pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS perf_test_data CASCADE;")
            print("Test tables cleaned up")

    async def benchmark_insert(self, num_inserts: int = 10000) -> DatabaseMetrics:
        """Benchmark INSERT operations.

        Args:
            num_inserts: Number of inserts to perform

        Returns:
            DatabaseMetrics object
        """
        print(f"\nBenchmarking INSERT operations ({num_inserts} inserts)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_inserts):
                try:
                    op_start = time.time()
                    await conn.execute(
                        """
                        INSERT INTO perf_test_data (name, description, value)
                        VALUES ($1, $2, $3)
                        """,
                        f"test_record_{i}",
                        f"Description for record {i}",
                        i % 1000
                    )
                    op_end = time.time()
                    times.append(op_end - op_start)
                except Exception as e:
                    print(f"Insert error: {e}")
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "INSERT",
            num_inserts,
            times,
            errors,
            total_time
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def benchmark_select(self, num_selects: int = 10000) -> DatabaseMetrics:
        """Benchmark SELECT operations.

        Args:
            num_selects: Number of selects to perform

        Returns:
            DatabaseMetrics object
        """
        print(f"\nBenchmarking SELECT operations ({num_selects} selects)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_selects):
                try:
                    op_start = time.time()
                    await conn.fetch(
                        "SELECT * FROM perf_test_data WHERE id = $1",
                        (i % 1000) + 1
                    )
                    op_end = time.time()
                    times.append(op_end - op_start)
                except Exception as e:
                    print(f"Select error: {e}")
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "SELECT",
            num_selects,
            times,
            errors,
            total_time
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def benchmark_update(self, num_updates: int = 5000) -> DatabaseMetrics:
        """Benchmark UPDATE operations.

        Args:
            num_updates: Number of updates to perform

        Returns:
            DatabaseMetrics object
        """
        print(f"\nBenchmarking UPDATE operations ({num_updates} updates)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_updates):
                try:
                    op_start = time.time()
                    await conn.execute(
                        """
                        UPDATE perf_test_data
                        SET value = $1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                        """,
                        i % 1000,
                        (i % 1000) + 1
                    )
                    op_end = time.time()
                    times.append(op_end - op_start)
                except Exception as e:
                    print(f"Update error: {e}")
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "UPDATE",
            num_updates,
            times,
            errors,
            total_time
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def benchmark_delete(self, num_deletes: int = 1000) -> DatabaseMetrics:
        """Benchmark DELETE operations.

        Args:
            num_deletes: Number of deletes to perform

        Returns:
            DatabaseMetrics object
        """
        print(f"\nBenchmarking DELETE operations ({num_deletes} deletes)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_deletes):
                try:
                    op_start = time.time()
                    await conn.execute(
                        "DELETE FROM perf_test_data WHERE id = $1",
                        (i % 1000) + 1
                    )
                    op_end = time.time()
                    times.append(op_end - op_start)
                except Exception as e:
                    print(f"Delete error: {e}")
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "DELETE",
            num_deletes,
            times,
            errors,
            total_time
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def benchmark_complex_query(self, num_queries: int = 1000) -> DatabaseMetrics:
        """Benchmark complex queries.

        Args:
            num_queries: Number of complex queries to perform

        Returns:
            DatabaseMetrics object
        """
        print(f"\nBenchmarking COMPLEX QUERY operations ({num_queries} queries)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_queries):
                try:
                    op_start = time.time()
                    await conn.fetch(
                        """
                        SELECT id, name, value, COUNT(*) OVER () as total
                        FROM perf_test_data
                        WHERE value > $1
                        ORDER BY created_at DESC
                        LIMIT 100
                        """,
                        i % 500
                    )
                    op_end = time.time()
                    times.append(op_end - op_start)
                except Exception as e:
                    print(f"Complex query error: {e}")
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "COMPLEX_QUERY",
            num_queries,
            times,
            errors,
            total_time
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    async def benchmark_transaction(self, num_transactions: int = 1000) -> DatabaseMetrics:
        """Benchmark transaction operations.

        Args:
            num_transactions: Number of transactions to perform

        Returns:
            DatabaseMetrics object
        """
        print(f"\nBenchmarking TRANSACTION operations ({num_transactions} transactions)...")

        times = []
        errors = 0
        start_time = time.time()

        async with self.pool.acquire() as conn:
            for i in range(num_transactions):
                try:
                    op_start = time.time()
                    async with conn.transaction():
                        await conn.execute(
                            """
                            INSERT INTO perf_test_data (name, description, value)
                            VALUES ($1, $2, $3)
                            """,
                            f"txn_record_{i}",
                            f"Transaction record {i}",
                            i % 1000
                        )
                        await conn.execute(
                            """
                            UPDATE perf_test_data
                            SET value = value + 1
                            WHERE id = $1
                            """,
                            (i % 100) + 1
                        )
                    op_end = time.time()
                    times.append(op_end - op_start)
                except Exception as e:
                    print(f"Transaction error: {e}")
                    errors += 1

        total_time = time.time() - start_time

        metrics = self._create_metrics(
            "TRANSACTION",
            num_transactions,
            times,
            errors,
            total_time
        )

        self._print_metrics(metrics)
        self.results.append(metrics)
        return metrics

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def _create_metrics(
        self,
        operation: str,
        num_operations: int,
        times: List[float],
        errors: int,
        total_time: float
    ) -> DatabaseMetrics:
        """Create metrics object."""
        if times:
            return DatabaseMetrics(
                operation=operation,
                num_operations=num_operations,
                min_time=min(times) * 1000,  # Convert to ms
                max_time=max(times) * 1000,
                mean_time=statistics.mean(times) * 1000,
                median_time=statistics.median(times) * 1000,
                p95_time=self._percentile(times, 95) * 1000,
                p99_time=self._percentile(times, 99) * 1000,
                throughput_ops=(num_operations - errors) / total_time if total_time > 0 else 0,
                error_count=errors,
                error_rate=errors / num_operations if num_operations > 0 else 0,
                timestamp=datetime.now().isoformat()
            )
        return None

    @staticmethod
    def _print_metrics(metrics: DatabaseMetrics) -> None:
        """Print metrics."""
        if not metrics:
            return

        print(f"  Min: {metrics.min_time:.2f}ms")
        print(f"  Max: {metrics.max_time:.2f}ms")
        print(f"  Mean: {metrics.mean_time:.2f}ms")
        print(f"  Median: {metrics.median_time:.2f}ms")
        print(f"  P95: {metrics.p95_time:.2f}ms")
        print(f"  P99: {metrics.p99_time:.2f}ms")
        print(f"  Throughput: {metrics.throughput_ops:.2f} ops/sec")
        print(f"  Error Rate: {metrics.error_rate:.2%}")

    def generate_report(self, output_file: str = "database_benchmark_report.json") -> None:
        """Generate database benchmark report.

        Args:
            output_file: Output file path
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "database": self.database,
            "total_operations_tested": len(self.results),
            "operations": [asdict(m) for m in self.results],
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
        all_throughputs = [m.throughput_ops for m in self.results]
        all_error_rates = [m.error_rate for m in self.results]

        return {
            "average_operation_time_ms": statistics.mean(all_means),
            "median_operation_time_ms": statistics.median(all_means),
            "max_operation_time_ms": max(all_means),
            "average_throughput_ops": statistics.mean(all_throughputs),
            "total_error_rate": statistics.mean(all_error_rates),
            "slowest_operation": max(self.results, key=lambda m: m.mean_time).operation,
            "fastest_operation": min(self.results, key=lambda m: m.mean_time).operation,
            "highest_throughput_operation": max(self.results, key=lambda m: m.throughput_ops).operation
        }

    def print_summary(self) -> None:
        """Print database benchmark summary."""
        if not self.results:
            print("No results to summarize")
            return

        print("\n" + "=" * 60)
        print("DATABASE PERFORMANCE SUMMARY")
        print("=" * 60)

        summary = self._generate_summary()
        print(f"\nAverage Operation Time: {summary['average_operation_time_ms']:.2f}ms")
        print(f"Median Operation Time: {summary['median_operation_time_ms']:.2f}ms")
        print(f"Max Operation Time: {summary['max_operation_time_ms']:.2f}ms")
        print(f"Average Throughput: {summary['average_throughput_ops']:.2f} ops/sec")
        print(f"Total Error Rate: {summary['total_error_rate']:.2%}")
        print(f"\nSlowest Operation: {summary['slowest_operation']}")
        print(f"Fastest Operation: {summary['fastest_operation']}")
        print(f"Highest Throughput: {summary['highest_throughput_operation']}")

        print("\n" + "-" * 60)
        print("OPERATION DETAILS")
        print("-" * 60)

        for metric in sorted(self.results, key=lambda m: m.mean_time, reverse=True):
            print(f"\n{metric.operation}")
            print(f"  Mean: {metric.mean_time:.2f}ms | P95: {metric.p95_time:.2f}ms | "
                  f"Throughput: {metric.throughput_ops:.2f} ops/sec | "
                  f"Error Rate: {metric.error_rate:.2%}")


async def main():
    """Run database benchmarks."""
    benchmark = DatabaseBenchmark(
        host="localhost",
        port=5432,
        database="xagent",
        user="postgres",
        password="postgres"
    )

    try:
        await benchmark.connect()
        await benchmark.setup_test_tables()

        print("\n" + "=" * 60)
        print("DATABASE PERFORMANCE BENCHMARKS")
        print("=" * 60)

        await benchmark.benchmark_insert(10000)
        await benchmark.benchmark_select(10000)
        await benchmark.benchmark_update(5000)
        await benchmark.benchmark_complex_query(1000)
        await benchmark.benchmark_transaction(1000)
        await benchmark.benchmark_delete(1000)

        benchmark.print_summary()
        benchmark.generate_report()

    except Exception as e:
        print(f"Benchmark error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await benchmark.cleanup_test_tables()
        await benchmark.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
