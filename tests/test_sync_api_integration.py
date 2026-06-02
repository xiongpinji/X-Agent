"""
X-Agent Sync API Integration Tests

Tests for sync API endpoints.

These tests exercise the sync router as it is actually wired into the production
``app`` (``backend.app.api.sync`` is included in ``main.py``). FastAPI ``Depends``
targets cannot be replaced with ``unittest.mock.patch`` — the callable is captured
at import time inside the ``Annotated`` type — so we override them through
``app.dependency_overrides`` instead. Requests carry the bootstrap API key, which
the CSRF middleware treats as CSRF-immune (header auth), so state-changing POSTs
reach the route instead of being rejected with a 403 by the cookie-based CSRF check.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, MagicMock

from backend.app.main import app
from backend.app.api.sync import get_local_database, get_sync_client
from backend.app.dependencies import get_current_principal
from backend.local.database import LocalDatabase
from backend.app.core.security import Principal

# Bootstrap API key is CSRF-exempt (header auth) so POST/PUT/DELETE reach the route.
AUTH_HEADERS = {"x-api-key": "bootstrap"}


def _principal(scopes: list[str]) -> Principal:
    """Build a real authenticated principal (RBAC checks .authenticated + .scopes)."""
    return Principal(
        user_id="user_123",
        tenant_id="tenant_123",
        role="admin",
        scopes=scopes,
        authenticated=True,
    )


@pytest.fixture
def mock_db():
    """Create mock local database."""
    db = Mock(spec=LocalDatabase)
    db.enqueue_sync.return_value = "queue_123"
    db.get_pending_syncs.return_value = []
    db.get_unresolved_conflicts.return_value = []
    db.get_sync_stats.return_value = {
        "pending_syncs": 0,
        "failed_syncs": 0,
        "unresolved_conflicts": 0,
        "offline_operations": 0,
    }
    db.get_database_size.return_value = {
        "database_size_bytes": 1024000,
        "database_size_mb": 1.0,
    }
    return db


@pytest.fixture
def client(mock_db):
    """Test client over the real app with sync dependencies overridden.

    Overrides get_local_database / get_sync_client / get_current_principal via
    dependency_overrides (the only way to substitute FastAPI Depends targets).
    A full-scope authenticated principal is the default; permission tests can
    re-point get_current_principal to a no-scope principal.
    """
    mock_sync_client = Mock()
    app.dependency_overrides[get_local_database] = lambda: mock_db
    app.dependency_overrides[get_sync_client] = lambda: mock_sync_client
    app.dependency_overrides[get_current_principal] = lambda: _principal(
        ["sync:read", "sync:write", "sync:admin"]
    )
    with TestClient(app) as test_client:
        test_client._mock_sync_client = mock_sync_client  # expose for assertions
        yield test_client
    app.dependency_overrides.clear()


class TestSyncAPI:
    """Happy-path coverage for the sync router wired into the real app."""

    def test_enqueue_sync(self, client, mock_db):
        resp = client.post(
            "/api/v1/sync/enqueue",
            json={
                "entity_type": "task",
                "entity_id": "task_1",
                "operation": "CREATE",
                "data": {"title": "demo"},
                "priority": 1,
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["queue_id"] == "queue_123"
        assert body["status"] == "pending"
        mock_db.enqueue_sync.assert_called_once()

    def test_get_sync_status(self, client, mock_db):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            "queue_123", "task", "task_1", "CREATE", "pending",
            "2026-05-31T00:00:00+00:00", "2026-05-31T00:00:00+00:00", 0, None,
        )
        conn.cursor.return_value = cursor
        mock_db._get_connection.return_value = conn

        resp = client.get("/api/v1/sync/status/queue_123", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["queue_id"] == "queue_123"
        assert body["status"] == "pending"

    def test_list_conflicts(self, client, mock_db):
        mock_db.get_unresolved_conflicts.return_value = [
            {
                "id": "conflict_1",
                "entity_type": "task",
                "entity_id": "task_1",
                "conflict_type": "version_mismatch",
                "local_version": 2,
                "cloud_version": 3,
                "local_data": {"title": "local"},
                "cloud_data": {"title": "cloud"},
                "resolved_at": None,
                "resolution_strategy": None,
            }
        ]
        resp = client.get("/api/v1/sync/conflicts", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == "conflict_1"

    def test_resolve_conflict(self, client, mock_db):
        mock_db.resolve_conflict.return_value = None
        resp = client.post(
            "/api/v1/sync/conflicts/conflict_1/resolve",
            json={
                "resolution_strategy": "local_wins",
                "resolved_data": {"title": "local"},
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["conflict_id"] == "conflict_1"
        assert body["status"] == "resolved"
        mock_db.resolve_conflict.assert_called_once()

    def test_enable_offline_mode(self, client):
        resp = client.post("/api/v1/sync/offline/enable", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        client._mock_sync_client.set_offline_mode.assert_called_once_with(True)

    def test_get_sync_stats(self, client):
        resp = client.get("/api/v1/sync/stats", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["pending_syncs"] == 0
        assert body["database_size_mb"] == 1.0

    def test_get_sync_health(self, client):
        resp = client.get("/api/v1/sync/health", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["health_score"] == 100


class TestSyncAPIErrors:
    """Error-path coverage: enqueue failures map to 500, missing rows to 404."""

    def test_enqueue_sync_error(self, client, mock_db):
        mock_db.enqueue_sync.side_effect = Exception("boom")
        resp = client.post(
            "/api/v1/sync/enqueue",
            json={
                "entity_type": "task",
                "entity_id": "task_1",
                "operation": "CREATE",
                "data": {},
                "priority": 0,
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 500

    def test_get_sync_status_not_found(self, client, mock_db):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        mock_db._get_connection.return_value = conn

        resp = client.get("/api/v1/sync/status/missing", headers=AUTH_HEADERS)
        assert resp.status_code == 404


class TestSyncAPIPermissions:
    """A principal without sync scopes is authenticated but rejected with 403."""

    def test_enqueue_sync_permission_denied(self, client):
        # Re-point the principal override to an authenticated, no-scope principal
        # so enforce_scope passes the authn check but fails the scope check (403).
        app.dependency_overrides[get_current_principal] = lambda: _principal([])
        resp = client.post(
            "/api/v1/sync/enqueue",
            json={
                "entity_type": "task",
                "entity_id": "task_1",
                "operation": "CREATE",
                "data": {},
                "priority": 0,
            },
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 403
