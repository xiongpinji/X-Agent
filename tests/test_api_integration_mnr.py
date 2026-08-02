"""Q: API Integration Tests — validates new endpoints end-to-end.

Run: pytest tests/test_api_integration_mnr.py -v
Uses FastAPI TestClient (in-process); no live server required.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

# conftest.py sets XAGENT_BOOTSTRAP_API_KEY=bootstrap before app import;
# routers are registered idempotently at test-session import time.
HEADERS = {"X-API-Key": "bootstrap"}


@pytest.fixture(scope="module")
def client():
    # NOTE: no lifespan (`with`) here — routers are registered eagerly by
    # tests/conftest.py, and running full startup/shutdown would tear down
    # shared app state (agent, pools) for other tests in the same session.
    return TestClient(app, headers=HEADERS)


# ─── M: Security endpoints ────────────────────────────────────────────────────


class TestSecurityPosture:
    def test_posture_returns_200(self, client):
        r = client.get("/api/v1/security/posture")
        assert r.status_code == 200
        data = r.json()
        assert "prompt_guard" in data
        assert "security_headers" in data
        assert "hardening" in data

    def test_secret_scan(self, client):
        r = client.post("/api/v1/security/secret-scan")
        assert r.status_code == 200
        data = r.json()
        assert "files_scanned" in data
        assert "findings_count" in data
        assert data["status"] in ("clean", "warnings_found")

    def test_audit_chain(self, client):
        r = client.get("/api/v1/security/audit-chain")
        assert r.status_code == 200
        data = r.json()
        assert "chain_length" in data
        assert "integrity" in data


# ─── N: Tenant isolation endpoints ───────────────────────────────────────────


class TestTenantIsolation:
    def test_quotas(self, client):
        r = client.get("/api/v1/security/tenant-isolation/quotas")
        assert r.status_code == 200
        data = r.json()
        assert "tenant_id" in data
        assert "quotas" in data

    def test_usage(self, client):
        r = client.get("/api/v1/security/tenant-isolation/usage")
        assert r.status_code == 200
        data = r.json()
        assert "usage" in data
        assert "total_runs" in data["usage"]

    def test_rbac_matrix(self, client):
        r = client.get("/api/v1/security/tenant-isolation/rbac-matrix")
        assert r.status_code == 200
        data = r.json()
        assert "roles" in data
        assert "admin" in data["roles"]
        assert "developer" in data["roles"]


# ─── P: Model routing endpoint ───────────────────────────────────────────────


class TestModelRouting:
    def test_model_routing_status(self, client):
        r = client.get("/api/v1/agents/model-routing")
        assert r.status_code == 200
        data = r.json()
        assert "router" in data
        assert "fallback" in data
        assert "quota" in data


# ─── L: Performance & queue endpoints ────────────────────────────────────────


class TestPerformanceAndQueue:
    def test_performance_dashboard(self, client):
        r = client.get("/api/v1/agents/performance")
        assert r.status_code == 200
        data = r.json()
        assert "spawner" in data
        assert "memory" in data
        assert "parallel_pool" in data

    def test_queue_stats(self, client):
        r = client.get("/api/v1/agents/parallel/queue/stats")
        assert r.status_code == 200
        data = r.json()
        assert "pool" in data
        assert "throughput" in data
        assert "utilization_percent" in data["pool"]

    def test_queue_health(self, client):
        r = client.get("/api/v1/agents/parallel/queue/health")
        assert r.status_code == 200
        data = r.json()
        assert "cpu_percent" in data
        assert "recommendation" in data
        assert data["recommendation"] in ("scale_up", "scale_down", "stable")
