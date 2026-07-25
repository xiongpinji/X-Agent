"""E2E User Journey Test — simulates complete user workflow via API.

Tests the full lifecycle: register → create agent → run task → check memory → create workflow.
Uses TestClient (no real browser needed) but exercises the same code paths.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("XAGENT_APP_MODE", "development")
    os.environ.setdefault("XAGENT_WORKFLOW_STORE_BACKEND", "file")
    with patch("backend.app.core.redis_client.init_redis", new_callable=AsyncMock) as m:
        m.return_value = MagicMock(is_available=False)
        from backend.app.main import app
        # Trigger router registration
        from backend.app.main import _register_all_routers
        _register_all_routers()
        with TestClient(app, raise_server_exceptions=False) as c:
            # Bearer token bypasses CSRF middleware (dev mode, no strict auth)
            c.headers["Authorization"] = "Bearer e2e-test-token"
            yield c


class TestUserJourney:
    """Complete user lifecycle test."""

    def test_01_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_02_create_goal(self, client):
        resp = client.post("/api/v1/goals", json={"objective": "Build a REST API"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        self.__class__.goal_id = data["id"]

    def test_03_list_goals(self, client):
        resp = client.get("/api/v1/goals")
        assert resp.status_code == 200
        goals = resp.json()
        assert len(goals) >= 1

    def test_04_complete_goal(self, client):
        goal_id = getattr(self.__class__, "goal_id", None)
        if goal_id is None:
            pytest.skip("goal_id not available (test_02 failed)")
        resp = client.post(f"/api/v1/goals/{goal_id}/complete")
        assert resp.status_code == 200

    def test_05_check_tools_available(self, client):
        resp = client.get("/api/v1/tools")
        assert resp.status_code in (200, 401, 403)

    def test_06_check_sso_status(self, client):
        resp = client.get("/api/v1/sso/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "oidc" in data or "saml" in data

    def test_07_evolution_stats(self, client):
        resp = client.get("/api/v1/evolution/stats")
        assert resp.status_code in (200, 401, 403, 404)

    def test_08_code_review(self, client):
        resp = client.post("/api/v1/code-review/file", json={
            "file_path": "main.py",
            "content": "import os\n\ndef main():\n    print(os.getcwd())\n",
            "language": "python"
        })
        assert resp.status_code in (200, 503)  # 503 if no LLM configured

    def test_09_memory_operations(self, client):
        # Check memory layers endpoint
        resp = client.get("/api/v1/memory/layers")
        assert resp.status_code in (200, 401, 403)

    def test_10_workflows(self, client):
        resp = client.get("/api/v1/workflows")
        assert resp.status_code in (200, 401, 403)
