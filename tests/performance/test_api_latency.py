"""API Latency Benchmark — verify P95 < 200ms for simple endpoints.

Uses in-process TestClient (no live server required).
"""
import time

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

pytestmark = pytest.mark.local_perf


@pytest.fixture(scope="module")
def client():
    with patch("backend.app.core.redis_client.init_redis", new_callable=AsyncMock) as m:
        m.return_value = MagicMock(is_available=False)
        from backend.app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestAPILatency:
    """P95 latency targets for key endpoints."""

    def _measure(self, client, method, url, n=50, **kwargs):
        latencies = []
        for _ in range(n):
            start = time.perf_counter()
            getattr(client, method)(url, **kwargs)
            latencies.append((time.perf_counter() - start) * 1000)
        latencies.sort()
        return {
            "p50": latencies[n // 2],
            "p95": latencies[int(n * 0.95)],
            "p99": latencies[int(n * 0.99)],
            "mean": sum(latencies) / n,
        }

    def test_health_latency(self, client):
        stats = self._measure(client, "get", "/health")
        print(f"\n  /health  P50={stats['p50']:.1f}ms  P95={stats['p95']:.1f}ms  P99={stats['p99']:.1f}ms  mean={stats['mean']:.1f}ms")
        assert stats["p95"] < 100, f"/health P95={stats['p95']:.1f}ms > 100ms"

    def test_goals_list_latency(self, client):
        stats = self._measure(client, "get", "/api/v1/goals")
        print(f"\n  /api/v1/goals  P50={stats['p50']:.1f}ms  P95={stats['p95']:.1f}ms  P99={stats['p99']:.1f}ms  mean={stats['mean']:.1f}ms")
        assert stats["p95"] < 200, f"/goals P95={stats['p95']:.1f}ms > 200ms"

    def test_goals_create_latency(self, client):
        stats = self._measure(client, "post", "/api/v1/goals",
                              json={"objective": "perf test"}, n=30)
        print(f"\n  POST /api/v1/goals  P50={stats['p50']:.1f}ms  P95={stats['p95']:.1f}ms  P99={stats['p99']:.1f}ms  mean={stats['mean']:.1f}ms")
        assert stats["p95"] < 200, f"POST /goals P95={stats['p95']:.1f}ms > 200ms"

    def test_tools_list_latency(self, client):
        stats = self._measure(client, "get", "/api/v1/tools")
        # Tools may require auth, accept 401 but measure latency
        print(f"\n  /api/v1/tools  P50={stats['p50']:.1f}ms  P95={stats['p95']:.1f}ms  P99={stats['p99']:.1f}ms  mean={stats['mean']:.1f}ms")
        assert stats["p95"] < 500, f"/tools P95={stats['p95']:.1f}ms > 500ms"
