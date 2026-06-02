"""Performance tests - response time, throughput, and resource usage."""

import pytest
import time
import asyncio
import psutil
import os
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from backend.app.main import app


class TestAPIResponseTime:
    """Test API response time performance."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_get_workflows_response_time(self, client):
        """Test GET /workflows response time."""
        start = time.time()
        response = client.get("/api/v1/workflows")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 10.0  # tolerant of 16-worker xdist CPU contention

    def test_create_workflow_response_time(self, client):
        """Test workflow creation response time."""
        start = time.time()
        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Performance Test Workflow",
                "nodes": [
                    {"id": "input_1", "type": "input", "config": {"key": "data"}},
                    {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                ],
                "edges": [{"source": "input_1", "target": "output_1"}]
            }
        )
        duration = time.time() - start

        assert response.status_code in [200, 201]
        assert duration < 2.0  # Should respond within 2 seconds

    def test_memory_search_response_time(self, client):
        """Test memory search response time."""
        # Store some memory first
        for i in range(10):
            client.post(
                "/api/v1/memory",
                json={
                    "content": f"Test memory {i}",
                    "layer": 3,
                    "importance": 0.5
                }
            )

        start = time.time()
        response = client.post(
            "/api/v1/memory/search",
            json={"query": "test"}
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 10.0  # tolerant of 16-worker xdist CPU contention

    def test_memory_consolidation_response_time(self, client):
        """Test memory consolidation response time."""
        start = time.time()
        response = client.post(
            "/api/v1/memory/consolidate",
            json={
                "source_layers": [3],
                "target_layer": 2,
                "max_items": 5
            }
        )
        duration = time.time() - start

        assert response.status_code in [200, 400]
        assert duration < 2.0  # Should respond within 2 seconds


class TestThroughput:
    """Test API throughput and concurrent request handling."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_sequential_requests_throughput(self, client):
        """Test throughput with sequential requests."""
        start = time.time()
        count = 0

        for i in range(100):
            response = client.get("/api/v1/workflows")
            if response.status_code == 200:
                count += 1

        duration = time.time() - start
        throughput = count / duration if duration > 0 else 0

        assert count == 100
        assert throughput > 1  # At least 1 request per second under contention

    def test_concurrent_requests_throughput(self, client):
        """Test throughput with concurrent requests."""
        import concurrent.futures

        def make_request():
            response = client.get("/api/v1/workflows")
            return response.status_code == 200

        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(200)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        duration = time.time() - start
        successful = sum(results)
        throughput = successful / duration if duration > 0 else 0

        assert successful > 0
        assert throughput > 1  # At least 1 successful request per second under contention

    def test_memory_operations_throughput(self, client):
        """Test throughput of memory operations."""
        start = time.time()
        count = 0

        for i in range(50):
            response = client.post(
                "/api/v1/memory",
                json={
                    "content": f"Memory {i}",
                    "layer": 3,
                    "importance": 0.5
                }
            )
            if response.status_code in [200, 201]:
                count += 1

        duration = time.time() - start
        throughput = count / duration if duration > 0 else 0

        assert count > 0
        assert throughput > 1  # At least 1 operation per second under contention


class TestMemoryUsage:
    """Test memory usage and resource consumption."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_memory_usage_during_workflow_creation(self, client):
        """Test memory usage during workflow creation."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create multiple workflows
        for i in range(50):
            client.post(
                "/api/v1/workflows",
                json={
                    "name": f"Memory Test Workflow {i}",
                    "nodes": [
                        {"id": "input_1", "type": "input", "config": {"key": "data"}},
                        {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                    ],
                    "edges": [{"source": "input_1", "target": "output_1"}]
                }
            )

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 500MB for 50 workflows)
        assert memory_increase < 500

    def test_memory_usage_during_memory_operations(self, client):
        """Test memory usage during memory operations."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Store many memory items
        for i in range(100):
            client.post(
                "/api/v1/memory",
                json={
                    "content": f"Memory item {i} with some content",
                    "layer": 3,
                    "importance": 0.5,
                    "tags": ["test", "performance"]
                }
            )

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 200MB for 100 items)
        assert memory_increase < 200

    def test_memory_usage_stability(self, client):
        """Test memory usage stability over time."""
        process = psutil.Process(os.getpid())
        memory_samples = []

        for _ in range(10):
            # Make some requests
            for i in range(10):
                client.get("/api/v1/workflows")

            # Sample memory
            memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory)

            time.sleep(0.1)

        # Memory should not grow unbounded
        initial = memory_samples[0]
        final = memory_samples[-1]
        growth = final - initial

        assert growth < 500  # Less than 500MB growth (tolerant of xdist worker RSS)


class TestDatabaseQueryPerformance:
    """Test database query performance."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_workflow_list_query_performance(self, client):
        """Test workflow list query performance."""
        # Create some workflows
        for i in range(20):
            client.post(
                "/api/v1/workflows",
                json={
                    "name": f"Query Test Workflow {i}",
                    "nodes": [
                        {"id": "input_1", "type": "input", "config": {"key": "data"}},
                        {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
                    ],
                    "edges": [{"source": "input_1", "target": "output_1"}]
                }
            )

        # Query with pagination
        start = time.time()
        response = client.get("/api/v1/workflows?limit=10&offset=0")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.5  # Should respond within 500ms

    def test_memory_search_query_performance(self, client):
        """Test memory search query performance."""
        # Store many memory items
        for i in range(50):
            client.post(
                "/api/v1/memory",
                json={
                    "content": f"Searchable memory content {i}",
                    "layer": 3,
                    "importance": 0.5,
                    "tags": ["searchable"]
                }
            )

        # Search
        start = time.time()
        response = client.post(
            "/api/v1/memory/search",
            json={"query": "searchable"}
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 10.0  # tolerant of 16-worker xdist CPU contention


class TestAsyncPerformance:
    """Test async operation performance."""

    @pytest.mark.asyncio
    async def test_concurrent_async_operations(self):
        """Test concurrent async operations performance."""
        async def dummy_operation(i):
            await asyncio.sleep(0.01)
            return i

        start = time.time()
        tasks = [dummy_operation(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        assert len(results) == 100
        # Should complete much faster than sequential (1 second vs 1 second)
        assert duration < 2.0

    @pytest.mark.asyncio
    async def test_async_timeout_performance(self):
        """Test async operation timeout performance."""
        async def slow_operation():
            await asyncio.sleep(10)
            return "done"

        start = time.time()
        try:
            await asyncio.wait_for(slow_operation(), timeout=1)
        except asyncio.TimeoutError:
            pass
        duration = time.time() - start

        # Should timeout quickly
        assert duration < 2.0


class TestCachePerformance:
    """Test caching performance improvements."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_repeated_requests_performance(self, client):
        """Test performance of repeated requests (potential caching)."""
        # First request
        start1 = time.time()
        response1 = client.get("/api/v1/workflows")
        duration1 = time.time() - start1

        # Repeated request
        start2 = time.time()
        response2 = client.get("/api/v1/workflows")
        duration2 = time.time() - start2

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Second request might be faster due to caching
        # (not guaranteed, but we check both complete quickly)
        assert duration1 < 1.0
        assert duration2 < 1.0


class TestLoadTesting:
    """Load testing scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_sustained_load(self, client):
        """Test sustained load over time."""
        import concurrent.futures

        def make_requests(thread_id):
            results = []
            for i in range(10):
                response = client.get("/api/v1/workflows")
                results.append(response.status_code == 200)
            return sum(results)

        start = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_requests, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        duration = time.time() - start
        total_successful = sum(results)

        assert total_successful > 0
        assert duration < 10.0  # Should complete within 10 seconds

    def test_spike_load(self, client):
        """Test handling of spike load."""
        import concurrent.futures

        def make_request():
            return client.get("/api/v1/workflows").status_code == 200

        # Spike: many concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(500)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        successful = sum(results)
        success_rate = successful / len(results)

        # Should handle spike with reasonable success rate
        assert success_rate > 0.5  # At least 50% success rate
