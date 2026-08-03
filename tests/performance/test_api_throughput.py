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
    # httpx ASGITransport 不触发 FastAPI lifespan，而本项目路由在 startup 事件中
    # 惰性注册（main.py::_register_all_routers），必须手动触发，否则全部 404。
    import asyncio as _asyncio

    for handler in app.router.on_startup:
        result = handler()
        if _asyncio.iscoroutine(result):
            await result
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client: AsyncClient):
    """Auth headers.

    register/login 端点已在 2026-08 API 收敛（C2）中移除，统一改用 bootstrap
    API Key（与 tests/conftest.py 的 XAGENT_BOOTSTRAP_API_KEY=bootstrap 对齐）。
    """
    return {"X-API-Key": "bootstrap"}


# ---------------------------------------------------------------------------
# Concurrent Agent Runs
# ---------------------------------------------------------------------------

@pytest.mark.performance
class TestConcurrentAgents:
    async def test_10_concurrent_agent_runs(self, client, auth_headers):
        """10 concurrent agent runs should complete within 60s."""
        async def run_agent(i: int):
            resp = await client.post("/api/v1/agents/run", headers=auth_headers, json={
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
            resp = await client.get("/health")
            assert resp.status_code == 200
        elapsed = time.perf_counter() - start

        throughput = 100 / elapsed
        # Target: at least 50 req/s for health check (conservative for test env)
        assert throughput > 50, f"Health throughput: {throughput:.1f} req/s"

    async def test_memory_list_throughput(self, client, auth_headers):
        """Memory list should handle 50 requests within 30s."""
        start = time.perf_counter()
        for _ in range(50):
            resp = await client.get("/api/v1/memory/stats", headers=auth_headers)
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
        resp = await client.post("/api/v1/agents/run", headers=auth_headers, json={
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
            "nodes": [],
            "edges": [],
        })
        elapsed = time.perf_counter() - start

        assert resp.status_code in (200, 201)
        assert elapsed < 5.0, f"Workflow create took {elapsed:.1f}s"

    async def test_auth_login_latency(self, client):
        """Bootstrap API key auth (entry) should complete within 5s.

        register/login 端点在 2026-08 API 收敛中移除，改为测量 API key 认证链路延迟。
        """
        start = time.perf_counter()
        resp = await client.get("/api/v1/entry", headers={"X-API-Key": "bootstrap"})
        elapsed = time.perf_counter() - start

        assert resp.status_code == 200
        assert elapsed < 5.0, f"Auth entry took {elapsed:.1f}s"
