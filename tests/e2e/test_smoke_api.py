"""E2E Smoke Test — 验证全部 API 路由可访问 (无 500).

Note: This test is opt-in. Set XAGENT_E2E=1 to run it.
"""
import os

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a TestClient from the REAL app with heavy deps mocked."""
    # Use memory/file backends so no external DB is needed
    env_overrides = {
        "XAGENT_MEMORY_BACKEND": "memory",
        "XAGENT_TRACE_BACKEND": "memory",
        "XAGENT_WORKFLOW_STORE_BACKEND": "file",
        "XAGENT_REQUIRE_API_KEY": "false",
        "XAGENT_APP_MODE": "development",
        "XAGENT_ADMIN_STORE_BACKEND": "memory",
    }
    with patch.dict(os.environ, env_overrides):
        # Clear ALL cached settings and dependency singletons
        from backend.app.settings import get_settings
        get_settings.cache_clear()

        # Clear dependency caches so they re-resolve with new settings
        from backend.app import dependencies as deps
        for fn_name in ("get_memory", "get_trace_store", "get_run_store",
                        "get_audit_store", "get_workflow_repository",
                        "get_browser_store", "get_tool_execution_store"):
            fn = getattr(deps, fn_name, None)
            if fn and hasattr(fn, "cache_clear"):
                fn.cache_clear()

        # Patch Redis init to avoid needing a real Redis server
        with patch(
            "backend.app.core.redis_client.init_redis", new_callable=AsyncMock
        ) as mock_redis:
            mock_redis.return_value = MagicMock(is_available=False)

            # Patch MCP manager to skip external MCP server connections
            with patch(
                "backend.app.core.mcp.manager.initialize_mcp_manager",
                new_callable=AsyncMock,
            ) as mock_mcp:
                mock_mcp.return_value = None

                # Patch sandbox worker (background asyncio task)
                with patch(
                    "backend.app.api.sandbox_tasks.start_sandbox_worker",
                    new_callable=AsyncMock,
                ):
                    with patch(
                        "backend.app.api.sandbox_tasks.stop_sandbox_worker",
                        new_callable=AsyncMock,
                    ):
                        from backend.app.main import app

                        with TestClient(app, raise_server_exceptions=False) as c:
                            yield c

        # Cleanup caches after test module
        get_settings.cache_clear()
        for fn_name in ("get_memory", "get_trace_store", "get_run_store",
                        "get_audit_store", "get_workflow_repository",
                        "get_browser_store", "get_tool_execution_store"):
            fn = getattr(deps, fn_name, None)
            if fn and hasattr(fn, "cache_clear"):
                fn.cache_clear()


# Bearer token header bypasses CSRF middleware for POST requests.
# Routes that require auth will return 401/403 — that's acceptable (not 500).
AUTH_HEADERS = {"Authorization": "Bearer smoke-test-token"}


class TestSmokeEndpoints:
    """Verify critical endpoints don't return 500."""

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_ready(self, client):
        resp = client.get("/ready")
        # May be 200 or 503 depending on component availability — not 500
        assert resp.status_code in (200, 503)

    def test_goals_crud(self, client):
        # Create
        resp = client.post(
            "/api/v1/goals",
            json={"objective": "Test goal"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200, f"Create goal failed: {resp.text}"
        data = resp.json()
        assert data["objective"] == "Test goal"
        assert data["status"] == "active"
        goal_id = data["id"]

        # List
        resp = client.get("/api/v1/goals")
        assert resp.status_code == 200

        # Get
        resp = client.get(f"/api/v1/goals/{goal_id}")
        assert resp.status_code == 200

        # Complete
        resp = client.post(
            f"/api/v1/goals/{goal_id}/complete",
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200

    def test_evolution_stats(self, client):
        resp = client.get("/api/v1/evolution/stats")
        assert resp.status_code in (200, 401, 403, 404)

    def test_code_review_file(self, client):
        resp = client.post(
            "/api/v1/code-review/file",
            json={
                "file_path": "test.py",
                "content": "def hello():\n    print('world')\n",
                "language": "python",
            },
            headers=AUTH_HEADERS,
        )
        # May fail due to no LLM, but should not be 500
        assert resp.status_code in (200, 401, 403, 422, 503), f"Got {resp.status_code}: {resp.text}"

    def test_sso_status(self, client):
        resp = client.get("/api/v1/sso/status")
        assert resp.status_code in (200, 401, 403)

    def test_workflows_list(self, client):
        resp = client.get("/api/v1/workflows")
        assert resp.status_code in (200, 401, 403)

    def test_agents_list(self, client):
        resp = client.get("/api/v1/agents")
        assert resp.status_code in (200, 401, 403)

    def test_memory_layers(self, client):
        resp = client.get("/api/v1/memory/layers")
        assert resp.status_code in (200, 401, 403)

    def test_tools_list(self, client):
        resp = client.get("/api/v1/tools")
        assert resp.status_code in (200, 401, 403)

    def test_sessions_list(self, client):
        resp = client.get("/api/v1/sessions")
        assert resp.status_code in (200, 401, 403, 404)

    def test_runs_list(self, client):
        resp = client.get("/api/v1/runs")
        assert resp.status_code in (200, 401, 403)

    def test_audit_list(self, client):
        resp = client.get("/api/v1/audit-logs")
        assert resp.status_code in (200, 401, 403)

    def test_notifications(self, client):
        resp = client.get("/api/v1/notifications")
        assert resp.status_code in (200, 401, 403, 404)

    def test_skills_list(self, client):
        resp = client.get("/api/v1/skills")
        assert resp.status_code in (200, 401, 403, 404)

    def test_no_500_on_unknown_api_path(self, client):
        resp = client.get("/api/v1/nonexistent-endpoint")
        # Should be 404, not 500
        assert resp.status_code in (404, 401, 403)
