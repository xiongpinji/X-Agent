"""Tests for the sandbox task API — submit/poll/list + webhook signature gate.

Uses TestClient with the bootstrap admin key (has sandbox:run scope). All
execution goes through the subprocess fallback (no Docker needed).
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture(autouse=True)
def _reset_sandbox_globals():
    """Reset module-level queue/orchestrator/worker before each test.

    TaskQueue's asyncio.Lock/Condition bind to the event loop active at
    construction. Each TestClient context uses a fresh loop, so a queue
    carried over from a prior test would be bound to a dead loop and never
    deliver tasks. Resetting gives each test a clean queue on its own loop.
    """
    import backend.app.api.sandbox_tasks as st

    st._queue = None
    st._orchestrator = None
    st._results = {}
    st._status = {}
    st._worker_task = None
    st._worker_running = False
    yield


@pytest.fixture
def client():
    # Context-manager form triggers startup/shutdown events, which start the
    # persistent sandbox worker that drains the task queue.
    with TestClient(app, headers={"x-api-key": "bootstrap"}) as c:
        yield c


class TestSandboxTaskAPI:
    def test_submit_returns_task_id(self, client):
        r = client.post(
            "/api/v1/sandbox/tasks",
            json={"name": "demo", "command": "echo hi"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "task_id" in body
        assert body["status"] == "queued"

    def test_submit_poll_completes(self, client):
        r = client.post(
            "/api/v1/sandbox/tasks",
            json={"name": "compute", "command": "python3 -c \"print(6*7)\""},
        )
        task_id = r.json()["task_id"]

        # poll until completed (bg task runs async)
        status = None
        for _ in range(20):
            time.sleep(0.5)
            poll = client.get(f"/api/v1/sandbox/tasks/{task_id}")
            assert poll.status_code == 200
            status = poll.json()["status"]
            if status in ("completed", "failed", "error"):
                break
        assert status == "completed"
        steps = poll.json()["steps"]
        assert steps and "42" in steps[0]["stdout"]

    def test_failing_command_marks_failed(self, client):
        r = client.post(
            "/api/v1/sandbox/tasks",
            json={"name": "fail", "command": "exit 5"},
        )
        task_id = r.json()["task_id"]
        status = None
        for _ in range(20):
            time.sleep(0.5)
            status = client.get(f"/api/v1/sandbox/tasks/{task_id}").json()["status"]
            if status in ("completed", "failed", "error"):
                break
        assert status == "failed"

    def test_poll_unknown_task_404(self, client):
        r = client.get("/api/v1/sandbox/tasks/nonexistent-id")
        assert r.status_code == 404

    def test_list_tasks(self, client):
        client.post("/api/v1/sandbox/tasks", json={"name": "x", "command": "echo x"})
        r = client.get("/api/v1/sandbox/tasks")
        assert r.status_code == 200
        assert "tasks" in r.json()

    def test_submit_requires_auth(self):
        # no api-key -> 401/403
        with TestClient(app) as anon:
            r = anon.post("/api/v1/sandbox/tasks", json={"name": "x", "command": "echo x"})
        assert r.status_code in (401, 403)


class TestGitHubWebhook:
    def test_unsigned_rejected(self, client):
        r = client.post(
            "/api/v1/sandbox/webhook/github",
            json={"action": "assigned", "issue": {"number": 1}},
        )
        assert r.status_code == 403

    def test_valid_signature_enqueues(self, client, monkeypatch):
        import hashlib
        import hmac
        import json

        secret = "test-webhook-secret"
        monkeypatch.setenv("XAGENT_GITHUB_WEBHOOK_SECRET", secret)

        payload = {
            "action": "assigned",
            "issue": {"number": 42, "title": "Fix it", "body": "desc", "labels": []},
            "repository": {
                "full_name": "foo/bar",
                "clone_url": "https://github.com/foo/bar.git",
                "default_branch": "main",
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        r = client.post(
            "/api/v1/sandbox/webhook/github",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "queued"
        assert r.json()["issue"] == 42
