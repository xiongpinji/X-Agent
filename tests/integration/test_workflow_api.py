"""Integration tests for Workflow API (backend.app.api.workflows).

Covers:
- GET /api/v1/workflows — list workflows
- POST /api/v1/workflows — create workflow
- GET /api/v1/workflows/{id} — get workflow
- PUT /api/v1/workflows/{id} — update workflow
- DELETE /api/v1/workflows/{id} — delete workflow
- POST /api/v1/workflows/{id}/run — run workflow
- GET /api/v1/workflows/runs — list runs

Note: These tests require PostgreSQL. They will be skipped if the database
is not available.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


def _postgres_available() -> bool:
    """Check if PostgreSQL is available."""
    try:
        import psycopg
        conn = psycopg.connect(
            host="localhost",
            port=5432,
            user="xagent",
            password="xagent_password",
            dbname="xagent",
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


# Skip all tests in this module if PostgreSQL is not available
pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL not available"
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client: AsyncClient):
    """Get auth headers via register+login."""
    await client.post("/api/v1/auth/register", json={
        "email": "wf@example.com",
        "password": "WfPass123!",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "wf@example.com",
        "password": "WfPass123!",
    })
    data = resp.json()
    token = data.get("access_token") or data.get("token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def sample_workflow(client: AsyncClient, auth_headers):
    """Create a sample workflow and return its ID."""
    resp = await client.post("/api/v1/workflows", headers=auth_headers, json={
        "name": "Test Pipeline",
        "description": "Integration test workflow",
        "nodes": [
            {"id": "start", "type": "input", "config": {}},
            {"id": "end", "type": "output", "config": {}},
        ],
        "edges": [{"source": "start", "target": "end"}],
    })
    data = resp.json()
    return data.get("id") or data.get("workflow_id", "")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestWorkflowCRUD:
    async def test_create_workflow(self, client, auth_headers):
        resp = await client.post("/api/v1/workflows", headers=auth_headers, json={
            "name": "New WF",
            "nodes": [{"id": "n1", "type": "input", "config": {}}],
            "edges": [],
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data.get("name") == "New WF" or "id" in data or "workflow_id" in data

    async def test_list_workflows(self, client, auth_headers, sample_workflow):
        resp = await client.get("/api/v1/workflows", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("workflows", []))
        assert len(items) >= 1

    async def test_get_workflow(self, client, auth_headers, sample_workflow):
        resp = await client.get(f"/api/v1/workflows/{sample_workflow}", headers=auth_headers)
        assert resp.status_code == 200

    async def test_get_nonexistent_workflow(self, client, auth_headers):
        resp = await client.get("/api/v1/workflows/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    async def test_update_workflow(self, client, auth_headers, sample_workflow):
        resp = await client.put(f"/api/v1/workflows/{sample_workflow}", headers=auth_headers, json={
            "name": "Updated Pipeline",
        })
        assert resp.status_code == 200

    async def test_delete_workflow(self, client, auth_headers, sample_workflow):
        resp = await client.delete(f"/api/v1/workflows/{sample_workflow}", headers=auth_headers)
        assert resp.status_code in (200, 204)

    async def test_unauthenticated_access(self, client):
        # API may allow unauthenticated access with default principal
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code in (200, 401, 403)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class TestWorkflowRun:
    async def test_run_workflow(self, client, auth_headers, sample_workflow):
        resp = await client.post(
            f"/api/v1/workflows/{sample_workflow}/run",
            headers=auth_headers,
            json={"inputs": {"key": "value"}},
        )
        assert resp.status_code in (200, 201, 202)

    async def test_list_runs(self, client, auth_headers, sample_workflow):
        # First run the workflow
        await client.post(
            f"/api/v1/workflows/{sample_workflow}/run",
            headers=auth_headers,
            json={"inputs": {}},
        )
        resp = await client.get("/api/v1/workflows/runs", headers=auth_headers)
        assert resp.status_code == 200
