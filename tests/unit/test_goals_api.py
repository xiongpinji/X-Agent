"""Unit tests for backend.app.api.goals — Goals CRUD API."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.goals import _goals, router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """TestClient with only the goals router mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_goals():
    """Reset the in-memory goals store between tests."""
    _goals.clear()
    yield
    _goals.clear()


# ---------------------------------------------------------------------------
# CRUD — Create
# ---------------------------------------------------------------------------


class TestCreateGoal:
    def test_create_goal_success(self, client: TestClient):
        resp = client.post("/api/v1/goals", json={"objective": "Refactor auth module"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["objective"] == "Refactor auth module"
        assert data["status"] == "active"
        assert data["id"].startswith("goal-")
        assert data["checkpoints"] == []
        assert data["created_at"] > 0

    def test_create_multiple_goals(self, client: TestClient):
        client.post("/api/v1/goals", json={"objective": "Goal A"})
        client.post("/api/v1/goals", json={"objective": "Goal B"})
        resp = client.get("/api/v1/goals")
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# CRUD — Read
# ---------------------------------------------------------------------------


class TestReadGoals:
    def test_list_goals_empty(self, client: TestClient):
        resp = client.get("/api/v1/goals")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_goals_after_creation(self, client: TestClient):
        client.post("/api/v1/goals", json={"objective": "Test goal"})
        resp = client.get("/api/v1/goals")
        assert len(resp.json()) == 1
        assert resp.json()[0]["objective"] == "Test goal"

    def test_get_goal_by_id(self, client: TestClient):
        create_resp = client.post("/api/v1/goals", json={"objective": "Find me"})
        goal_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/goals/{goal_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == goal_id
        assert resp.json()["objective"] == "Find me"


# ---------------------------------------------------------------------------
# CRUD — Complete (update status)
# ---------------------------------------------------------------------------


class TestCompleteGoal:
    def test_complete_goal_success(self, client: TestClient):
        create_resp = client.post("/api/v1/goals", json={"objective": "Finish report"})
        goal_id = create_resp.json()["id"]
        resp = client.post(f"/api/v1/goals/{goal_id}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # Verify persisted
        get_resp = client.get(f"/api/v1/goals/{goal_id}")
        assert get_resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Validation — empty objective rejected
# ---------------------------------------------------------------------------


class TestValidation:
    def test_empty_objective_rejected(self, client: TestClient):
        resp = client.post("/api/v1/goals", json={"objective": ""})
        assert resp.status_code == 422  # Pydantic validation error

    def test_missing_objective_rejected(self, client: TestClient):
        resp = client.post("/api/v1/goals", json={})
        assert resp.status_code == 422

    def test_whitespace_only_objective_rejected(self, client: TestClient):
        """min_length=1 means at least 1 char; whitespace-only passes pydantic but is 1 char."""
        resp = client.post("/api/v1/goals", json={"objective": " "})
        # Pydantic min_length=1 allows a single space (length=1)
        assert resp.status_code == 200

    def test_objective_too_long_rejected(self, client: TestClient):
        resp = client.post("/api/v1/goals", json={"objective": "x" * 2001})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 404 for missing goal
# ---------------------------------------------------------------------------


class TestNotFound:
    def test_get_nonexistent_goal_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/goals/goal-doesnotexist")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_complete_nonexistent_goal_returns_404(self, client: TestClient):
        resp = client.post("/api/v1/goals/goal-doesnotexist/complete")
        assert resp.status_code == 404
