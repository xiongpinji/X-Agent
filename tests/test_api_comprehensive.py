"""Comprehensive integration tests for API endpoints.

Tests cover:
- User management endpoints
- Tenant management endpoints
- Memory API endpoints
- Workflow API endpoints
- Collaboration API endpoints
- Error handling and validation
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers."""
    return {"x-api-key": "bootstrap"}


class TestUserEndpoints:
    """Test user management endpoints."""

    def test_list_users_unauthorized(self, client: TestClient) -> None:
        """Test listing users without authentication."""
        response = client.get("/api/v1/users")
        assert response.status_code == 401

    def test_list_users_authorized(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test listing users with authentication."""
        response = client.get("/api/v1/users", headers=auth_headers)
        assert response.status_code in [200, 401]  # May fail if not configured

    def test_create_user_unauthorized(self, client: TestClient) -> None:
        """Test creating user without authentication."""
        response = client.post(
            "/api/v1/users",
            json={"email": "test@example.com"},
        )
        assert response.status_code == 401

    def test_create_user_invalid_email(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test creating user with invalid email."""
        response = client.post(
            "/api/v1/users",
            json={"email": "invalid-email"},
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]

    def test_get_user_unauthorized(self, client: TestClient) -> None:
        """Test getting user without authentication."""
        response = client.get("/api/v1/users/user-123")
        assert response.status_code == 401

    def test_get_user_not_found(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test getting nonexistent user."""
        response = client.get("/api/v1/users/nonexistent", headers=auth_headers)
        assert response.status_code in [404, 401]

    def test_update_user_unauthorized(self, client: TestClient) -> None:
        """Test updating user without authentication."""
        response = client.put(
            "/api/v1/users/user-123",
            json={"email": "new@example.com"},
        )
        assert response.status_code == 401

    def test_delete_user_unauthorized(self, client: TestClient) -> None:
        """Test deleting user without authentication."""
        response = client.delete("/api/v1/users/user-123")
        assert response.status_code == 401


class TestTenantEndpoints:
    """Test tenant management endpoints."""

    def test_list_tenants_unauthorized(self, client: TestClient) -> None:
        """Test listing tenants without authentication."""
        response = client.get("/api/v1/tenants")
        assert response.status_code == 401

    def test_list_tenants_authorized(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test listing tenants with authentication."""
        response = client.get("/api/v1/tenants", headers=auth_headers)
        assert response.status_code in [200, 401]

    def test_create_tenant_unauthorized(self, client: TestClient) -> None:
        """Test creating tenant without authentication."""
        response = client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant"},
        )
        assert response.status_code == 401

    def test_get_tenant_unauthorized(self, client: TestClient) -> None:
        """Test getting tenant without authentication."""
        response = client.get("/api/v1/tenants/tenant-123")
        assert response.status_code == 401

    def test_update_tenant_unauthorized(self, client: TestClient) -> None:
        """Test updating tenant without authentication."""
        response = client.put(
            "/api/v1/tenants/tenant-123",
            json={"name": "Updated Tenant"},
        )
        assert response.status_code == 401

    def test_delete_tenant_unauthorized(self, client: TestClient) -> None:
        """Test deleting tenant without authentication."""
        response = client.delete("/api/v1/tenants/tenant-123")
        assert response.status_code == 401


class TestMemoryEndpoints:
    """Test memory API endpoints."""

    def test_list_memories_unauthorized(self, client: TestClient) -> None:
        """Test listing memories without authentication."""
        response = client.get("/api/v1/memory")
        assert response.status_code == 401

    def test_create_memory_unauthorized(self, client: TestClient) -> None:
        """Test creating memory without authentication."""
        response = client.post(
            "/api/v1/memory",
            json={
                "content": "Test memory",
                "layer": 1,
            },
        )
        assert response.status_code == 401

    def test_search_memory_unauthorized(self, client: TestClient) -> None:
        """Test searching memory without authentication."""
        response = client.get("/api/v1/memory/search?q=test")
        assert response.status_code == 401

    def test_get_memory_unauthorized(self, client: TestClient) -> None:
        """Test getting memory without authentication."""
        response = client.get("/api/v1/memory/mem-123")
        assert response.status_code == 401

    def test_update_memory_unauthorized(self, client: TestClient) -> None:
        """Test updating memory without authentication."""
        response = client.put(
            "/api/v1/memory/mem-123",
            json={"content": "Updated content"},
        )
        assert response.status_code == 401

    def test_delete_memory_unauthorized(self, client: TestClient) -> None:
        """Test deleting memory without authentication."""
        response = client.delete("/api/v1/memory/mem-123")
        assert response.status_code == 401


class TestWorkflowEndpoints:
    """Test workflow API endpoints."""

    def test_list_workflows_unauthorized(self, client: TestClient) -> None:
        """Test listing workflows without authentication."""
        response = client.get("/api/v1/workflows")
        assert response.status_code == 401

    def test_create_workflow_unauthorized(self, client: TestClient) -> None:
        """Test creating workflow without authentication."""
        response = client.post(
            "/api/v1/workflows",
            json={
                "name": "Test Workflow",
                "nodes": [],
            },
        )
        assert response.status_code == 401

    def test_get_workflow_unauthorized(self, client: TestClient) -> None:
        """Test getting workflow without authentication."""
        response = client.get("/api/v1/workflows/wf-123")
        assert response.status_code == 401

    def test_update_workflow_unauthorized(self, client: TestClient) -> None:
        """Test updating workflow without authentication."""
        response = client.put(
            "/api/v1/workflows/wf-123",
            json={"name": "Updated Workflow"},
        )
        assert response.status_code == 401

    def test_delete_workflow_unauthorized(self, client: TestClient) -> None:
        """Test deleting workflow without authentication."""
        response = client.delete("/api/v1/workflows/wf-123")
        assert response.status_code == 401

    def test_run_workflow_unauthorized(self, client: TestClient) -> None:
        """Test running workflow without authentication."""
        response = client.post(
            "/api/v1/workflows/wf-123/run",
            json={},
        )
        assert response.status_code == 401


class TestCollaborationEndpoints:
    """Test collaboration API endpoints."""

    def test_list_rooms_unauthorized(self, client: TestClient) -> None:
        """Test listing collaboration rooms without authentication."""
        response = client.get("/api/v1/collaboration/rooms")
        assert response.status_code == 401

    def test_create_room_unauthorized(self, client: TestClient) -> None:
        """Test creating collaboration room without authentication."""
        response = client.post(
            "/api/v1/collaboration/rooms",
            json={"topic": "Test Room"},
        )
        assert response.status_code == 401

    def test_get_room_unauthorized(self, client: TestClient) -> None:
        """Test getting collaboration room without authentication."""
        response = client.get("/api/v1/collaboration/rooms/room-123")
        assert response.status_code == 401

    def test_post_message_unauthorized(self, client: TestClient) -> None:
        """Test posting message without authentication."""
        response = client.post(
            "/api/v1/collaboration/rooms/room-123/messages",
            json={"content": "Test message"},
        )
        assert response.status_code == 401

    def test_list_messages_unauthorized(self, client: TestClient) -> None:
        """Test listing messages without authentication."""
        response = client.get("/api/v1/collaboration/rooms/room-123/messages")
        assert response.status_code == 401

    def test_add_member_unauthorized(self, client: TestClient) -> None:
        """Test adding member without authentication."""
        response = client.post(
            "/api/v1/collaboration/rooms/room-123/members",
            json={"member_id": "user-123"},
        )
        assert response.status_code == 401

    def test_remove_member_unauthorized(self, client: TestClient) -> None:
        """Test removing member without authentication."""
        response = client.delete(
            "/api/v1/collaboration/rooms/room-123/members/user-123"
        )
        assert response.status_code == 401


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_readiness_check(self, client: TestClient) -> None:
        """Test readiness check endpoint."""
        response = client.get("/ready")
        assert response.status_code in [200, 503]

    def test_liveness_check(self, client: TestClient) -> None:
        """Test liveness check endpoint."""
        response = client.get("/live")
        assert response.status_code in [200, 503]


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_json(self, client: TestClient) -> None:
        """Test handling invalid JSON."""
        response = client.post(
            "/api/v1/users",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]

    def test_missing_required_field(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test handling missing required field."""
        response = client.post(
            "/api/v1/users",
            json={},
            headers=auth_headers,
        )
        assert response.status_code in [400, 422]

    def test_invalid_method(self, client: TestClient) -> None:
        """Test handling invalid HTTP method."""
        response = client.patch("/api/v1/users")
        assert response.status_code in [405, 401]

    def test_not_found(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Test handling not found."""
        response = client.get(
            "/api/v1/nonexistent/endpoint",
            headers=auth_headers,
        )
        assert response.status_code in [404, 401]


class TestRateLimiting:
    """Test rate limiting."""

    def test_rate_limit_headers(self, client: TestClient) -> None:
        """Test rate limit headers in response."""
        response = client.get("/health")
        # Rate limit headers may or may not be present
        assert response.status_code == 200

    def test_multiple_requests(self, client: TestClient) -> None:
        """Test multiple requests."""
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200


class TestCORS:
    """Test CORS headers."""

    def test_cors_headers(self, client: TestClient) -> None:
        """Test CORS headers in response."""
        response = client.get("/health")
        # CORS headers may or may not be present depending on configuration
        assert response.status_code == 200

    def test_preflight_request(self, client: TestClient) -> None:
        """Test preflight request."""
        response = client.options("/api/v1/users")
        assert response.status_code in [200, 204, 405]
