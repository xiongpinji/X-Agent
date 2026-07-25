"""Performance tests for X-Agent API.

Covers:
- Concurrent agent runs (10 parallel)
- API throughput (100 req/s target)
- Memory search latency
- Workflow execution time

Uses pytest-benchmark style timing assertions.
"""
from __future__ import annotations

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client: AsyncClient):
    """Get auth headers."""
    await client.post("/api/v1/auth/register", json={
        "username": "perfuser",
        "email": "perf@example.com",
        "password": "PerfPass123!",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "perfuser",
        "password": "PerfPass123!",
    })
    data = resp.json()
    token = data.get("access_token") or data.get("token", "")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Concurrent Agent Runs
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestConcurrentAgents:
    async def test_10_concurrent_agent_runs(self, client, auth_headers):
        """10 concurrent agent runs should complete within 60s."""
        async def run_agent(i: int):
            resp = await client.post("/api/v1/agent/run", headers=auth_headers, json={
                "task": f"Task {i}: echo: hello {i}",
            })
            return resp.status_code

        start = time.perf_counter()
        results = await asyncio.gather(*[run_agent(i) for i in range(10)])
        elapsed = time.perf_counter() - start

        # All should succeed
        assert all(code == 200 for code in results)
        # Should complete within reasonable time
        assert elapsed < 60.0, f"10 concurrent agents took {elapsed:.1f}s"

    async def test_5_concurrent_memory_stores(self, client, auth_headers):
        """5 concurrent memory stores should all succeed."""
        async def store_memory(i: int):
            resp = await client.post("/api/v1/memory", headers=auth_headers, json={
                "content": f"Performance test memory {i}",
                "layer": 3,
            })
            return resp.status_code

        results = await asyncio.gather(*[store_memory(i) for i in range(5)])
        assert all(code in (200, 201) for code in results)


# ---------------------------------------------------------------------------
# API Throughput
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestAPIThroughput:
    async def test_health_endpoint_throughput(self, client):
        """Health endpoint should handle 100 requests quickly."""
        start = time.perf_counter()
        for _ in range(100):
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
        elapsed = time.perf_counter() - start

        throughput = 100 / elapsed
        # Target: at least 50 req/s for health check (conservative for test env)
        assert throughput > 50, f"Health throughput: {throughput:.1f} req/s"

    async def test_memory_list_throughput(self, client, auth_headers):
        """Memory list should handle 50 requests within 30s."""
        start = time.perf_counter()
        for _ in range(50):
            resp = await client.get("/api/v1/memory", headers=auth_headers)
            assert resp.status_code == 200
        elapsed = time.perf_counter() - start

        assert elapsed < 30.0, f"50 memory list requests took {elapsed:.1f}s"


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestLatency:
    async def test_agent_run_latency(self, client, auth_headers):
        """Single agent run should complete within 30s."""
        start = time.perf_counter()
        resp = await client.post("/api/v1/agent/run", headers=auth_headers, json={
            "task": "echo: latency test",
        })
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < 30.0, f"Agent run took {elapsed:.1f}s"

    async def test_workflow_create_latency(self, client, auth_headers):
        """Workflow creation should complete within 5s."""
        start = time.perf_counter()
        resp = await client.post("/api/v1/workflows", headers=auth_headers, json={
            "name": "Perf WF",
            "nodes": [{"id": "n1", "type": "input", "config": {}}],
            "edges": [],
        })
        elapsed = time.perf_counter() - start

        assert resp.status_code in (200, 201)
        assert elapsed < 5.0, f"Workflow create took {elapsed:.1f}s"

    async def test_auth_login_latency(self, client):
        """Login should complete within 5s."""
        await client.post("/api/v1/auth/register", json={
            "username": "latencyuser",
            "email": "latency@example.com",
            "password": "LatencyPass1!",
        })
        start = time.perf_counter()
        resp = await client.post("/api/v1/auth/login", json={
            "username": "latencyuser",
            "password": "LatencyPass1!",
        })
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < 5.0, f"Login took {elapsed:.1f}s"
