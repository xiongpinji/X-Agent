"""Tests for workbench resources BFF endpoint.

Verifies the /api/v1/workbench/resources endpoint returns valid
ApiPandaResourceSnapshot compatible data for the frontend.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.app.api.workbench_resources_bff import (
    _build_agents_snapshot,
    _build_tools_snapshot,
    _build_workflows_snapshot,
    _build_knowledge_snapshot,
    _build_settings_snapshot,
    _build_automation_rules_snapshot,
    _build_projects_snapshot,
    _build_data_sources_snapshot,
    _status_to_tone,
    router,
)


class TestResourceSnapshotBuilders:
    """Test individual snapshot builder functions."""

    def test_agents_snapshot_returns_list(self):
        result = _build_agents_snapshot()
        assert isinstance(result, list)
        if result:
            agent = result[0]
            assert "id" in agent
            assert "name" in agent
            assert "role" in agent
            assert "status" in agent

    def test_tools_snapshot_returns_builtin_tools(self):
        result = _build_tools_snapshot()
        assert isinstance(result, list)
        assert len(result) >= 6  # We always return 6 builtins
        names = [t["name"] for t in result]
        assert "Web Search" in names
        assert "Read File" in names
        assert "Execute Code" in names

    def test_workflows_snapshot_returns_list(self):
        result = _build_workflows_snapshot()
        assert isinstance(result, list)
        assert len(result) >= 3
        names = [w["name"] for w in result]
        assert "Code Review" in names
        assert "Issue to PR" in names

    def test_knowledge_snapshot_returns_list(self):
        result = _build_knowledge_snapshot()
        assert isinstance(result, list)
        if result:
            ks = result[0]
            assert "id" in ks
            assert "name" in ks
            assert "kind" in ks

    def test_settings_snapshot_has_sections(self):
        result = _build_settings_snapshot()
        assert len(result) == 4
        titles = [s["title"] for s in result]
        assert "General" in titles
        assert "Security" in titles

    def test_automation_rules_from_skills(self):
        with patch("backend.app.core.skills.load_builtin_skills") as mock_load:
            mock_load.return_value = {"code_review": {}, "test_gen": {}, "refactor": {}}
            result = _build_automation_rules_snapshot()
            assert len(result) == 3
            assert all("Skill:" in r["name"] for r in result)

    def test_projects_snapshot_has_default(self):
        result = _build_projects_snapshot()
        assert len(result) >= 1
        assert result[0]["name"] == "Default Workspace"

    def test_data_sources_from_settings(self):
        with patch("backend.app.settings.get_settings") as mock_settings:
            s = MagicMock()
            s.database_url = "postgresql://localhost/xagent"
            s.redis_url = "redis://localhost:6379"
            s.qdrant_url = "http://localhost:6333"
            mock_settings.return_value = s
            result = _build_data_sources_snapshot()
            assert len(result) == 3
            names = [d["name"] for d in result]
            assert any("PostgreSQL" in n or "postgresql" in n for n in names)


class TestStatusToTone:
    """Test tone mapping utility."""

    def test_completed_is_success(self):
        assert _status_to_tone("completed") == "success"

    def test_failed_is_danger(self):
        assert _status_to_tone("failed") == "danger"

    def test_pending_is_neutral(self):
        assert _status_to_tone("pending") == "neutral"

    def test_unknown_is_neutral(self):
        assert _status_to_tone("something_else") == "neutral"


class TestBFFEndpointContract:
    """Verify the endpoint response matches ApiPandaResourceSnapshot."""

    def test_snapshot_has_all_required_keys(self):
        """The response must contain all keys from ApiPandaResourceSnapshot."""
        from starlette.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/workbench")

        client = TestClient(app)
        resp = client.get("/api/v1/workbench/resources")

        assert resp.status_code == 200
        data = resp.json()

        # These are the keys defined in snapshotApiContracts.ts
        expected_keys = {
            "tasks", "projects", "threads", "workflows",
            "workflow_nodes", "agents", "knowledge_sources",
            "tools", "data_sources", "audit_events",
            "automation_rules", "settings_sections",
        }
        assert set(data.keys()) == expected_keys

    def test_all_values_are_lists(self):
        """Every field in the snapshot must be a list."""
        from starlette.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/workbench")

        client = TestClient(app)
        resp = client.get("/api/v1/workbench/resources")
        data = resp.json()

        for key, value in data.items():
            assert isinstance(value, list), f"{key} should be a list, got {type(value)}"

    def test_response_has_cache_headers(self):
        """Response should include Cache-Control."""
        from starlette.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/workbench")

        client = TestClient(app)
        resp = client.get("/api/v1/workbench/resources")

        assert "Cache-Control" in resp.headers
        assert "X-Response-Time" in resp.headers

    def test_health_endpoint(self):
        """BFF health check works."""
        from starlette.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/workbench")

        client = TestClient(app)
        resp = client.get("/api/v1/workbench/resources/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
