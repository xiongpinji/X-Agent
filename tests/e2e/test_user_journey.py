"""E2E tests for critical user journeys.

Covers:
- User journey: register → login → chat → view memory
- Workflow journey: create → edit → run → view results

Uses httpx AsyncClient against the ASGI app (no browser required).

Note: These tests are opt-in. Set XAGENT_E2E=1 to run them.
"""
from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app

# Skip all tests in this module unless XAGENT_E2E=1
pytestmark = pytest.mark.skipif(
    os.environ.get("XAGENT_E2E") != "1",
    reason="e2e tests are opt-in: set XAGENT_E2E=1"
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# User Journey: Register → Login → Agent Run → Memory
# ---------------------------------------------------------------------------

class TestUserJourney:
    async def test_full_user_journey(self, client):
        """Complete user journey from registration to agent interaction."""
        # 1. Register
        resp = await client.post("/api/v1/auth/register", json={
            "email": "journey@example.com",
            "password": "JourneyPass1!",
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        token = data.get("access_token") or data.get("token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Login (verify credentials work)
        resp = await client.post("/api/v1/auth/login", json={
            "email": "journey@example.com",
            "password": "JourneyPass1!",
        })
        assert resp.status_code == 200

        # 3. Get profile
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200

        # 4. Run agent task
        resp = await client.post("/api/v1/agent/run", headers=headers, json={
            "task": "What is the capital of France?",
        })
        assert resp.status_code == 200
        run_data = resp.json()
        assert run_data.get("status") in ("completed", "COMPLETED")
        assert run_data.get("answer")

        # 5. Check memory was created
        resp = await client.get("/api/v1/memory", headers=headers)
        assert resp.status_code == 200

    async def test_chat_history_journey(self, client):
        """User can create and retrieve chat history."""
        # Register + login
        await client.post("/api/v1/auth/register", json={
            "email": "chat@example.com",
            "password": "ChatPass1!",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "chat@example.com",
            "password": "ChatPass1!",
        })
        token = resp.json().get("access_token") or resp.json().get("token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # Create conversation
        resp = await client.post("/api/v1/chat/history", headers=headers, json={
            "title": "My First Chat",
            "messages": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi! How can I help?"},
            ],
        })
        assert resp.status_code in (200, 201)

        # List conversations
        resp = await client.get("/api/v1/chat/history", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("conversations", []))
        assert len(items) >= 1


# ---------------------------------------------------------------------------
# Workflow Journey: Create → Run → View Results
# ---------------------------------------------------------------------------

class TestWorkflowJourney:
    async def test_full_workflow_journey(self, client):
        """Complete workflow journey from creation to execution."""
        # Register + login
        await client.post("/api/v1/auth/register", json={
            "email": "wfjourney@example.com",
            "password": "WfPass123!",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "wfjourney@example.com",
            "password": "WfPass123!",
        })
        token = resp.json().get("access_token") or resp.json().get("token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create workflow
        resp = await client.post("/api/v1/workflows", headers=headers, json={
            "name": "Journey Pipeline",
            "description": "E2E test workflow",
            "nodes": [
                {"id": "input", "type": "input", "config": {}},
                {"id": "process", "type": "transform", "config": {"expression": "x * 2"}},
                {"id": "output", "type": "output", "config": {}},
            ],
            "edges": [
                {"source": "input", "target": "process"},
                {"source": "process", "target": "output"},
            ],
        })
        assert resp.status_code in (200, 201)
        wf_data = resp.json()
        wf_id = wf_data.get("id") or wf_data.get("workflow_id", "")
        assert wf_id

        # 2. Get workflow
        resp = await client.get(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 200

        # 3. Update workflow
        resp = await client.put(f"/api/v1/workflows/{wf_id}", headers=headers, json={
            "description": "Updated description",
        })
        assert resp.status_code == 200

        # 4. Run workflow
        resp = await client.post(f"/api/v1/workflows/{wf_id}/run", headers=headers, json={
            "inputs": {"value": 42},
        })
        assert resp.status_code in (200, 201, 202)

        # 5. List runs
        resp = await client.get("/api/v1/workflows/runs", headers=headers)
        assert resp.status_code == 200
