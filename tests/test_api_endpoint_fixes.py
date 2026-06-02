"""Tests for API endpoint fixes and improvements."""

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.core.contracts import ErrorCode


def _client() -> TestClient:
    """Create test client with API key."""
    return TestClient(app, headers={"x-api-key": "bootstrap"})


class TestPaginationEndpoints:
    """Test pagination functionality across endpoints."""

    def test_user_activity_pagination(self) -> None:
        """Test user activity endpoint with pagination."""
        client = _client()
        # Create a test user first
        user_response = client.post(
            "/api/v1/users",
            json={"email": "test@example.com", "display_name": "Test User"},
        )
        assert user_response.status_code == 200
        user_id = user_response.json()["id"]

        # Get user activity with pagination
        response = client.get(
            f"/api/v1/users/{user_id}/activity",
            params={"limit": 10, "offset": 0},
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "pagination" in body
        assert body["pagination"]["limit"] == 10
        assert body["pagination"]["offset"] == 0
        assert "has_more" in body["pagination"]

    def test_audit_logs_pagination(self) -> None:
        """Test audit logs endpoint with pagination."""
        client = _client()
        response = client.get(
            "/api/v1/audit-logs",
            params={"limit": 25, "offset": 0},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert "pagination" in body
        assert body["pagination"]["limit"] == 25
        assert body["pagination"]["offset"] == 0

    def test_pagination_limit_validation(self) -> None:
        """Test pagination limit validation."""
        client = _client()
        # Test limit too high
        response = client.get(
            "/api/v1/audit-logs",
            params={"limit": 500},
        )
        # Should either reject or cap at 200
        assert response.status_code in [200, 422]


class TestErrorHandling:
    """Test unified error response format."""

    def test_not_found_error_format(self) -> None:
        """Test 404 error response format."""
        client = _client()
        response = client.get("/api/v1/users/nonexistent-id")
        assert response.status_code == 404
        body = response.json()
        assert "code" in body
        assert body["code"] == ErrorCode.RESOURCE_NOT_FOUND
        assert "message" in body
        assert "details" in body

    def test_validation_error_format(self) -> None:
        """Test validation error response format."""
        client = _client()
        response = client.post(
            "/api/v1/users",
            json={"email": "invalid"},  # Missing required fields
        )
        assert response.status_code == 422
        body = response.json()
        assert "code" in body
        assert "message" in body

    def test_authentication_error_format(self) -> None:
        """Test authentication error response format."""
        client = TestClient(app)  # No API key
        response = client.get("/api/v1/users")
        assert response.status_code == 401
        body = response.json()
        assert "code" in body
        assert "message" in body


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_oauth_login_unsupported_provider(self) -> None:
        """Test OAuth login with unsupported provider."""
        client = _client()
        response = client.post(
            "/api/v1/auth/login/oauth",
            params={"provider": "unsupported", "code": "test-code"},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["code"] == ErrorCode.VALIDATION_ERROR
        assert "unsupported" in body["message"].lower()

    def test_oauth_login_missing_code(self) -> None:
        """Test OAuth login without authorization code."""
        client = _client()
        response = client.post(
            "/api/v1/auth/login/oauth",
            params={"provider": "google"},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["code"] == ErrorCode.VALIDATION_ERROR

    def test_verify_email_missing_token(self) -> None:
        """Test email verification without token."""
        client = _client()
        response = client.post("/api/v1/auth/verify-email", params={})
        assert response.status_code == 400
        body = response.json()
        assert body["code"] == ErrorCode.VALIDATION_ERROR

    def test_reset_password_invalid_request(self) -> None:
        """Test password reset with invalid parameters."""
        client = _client()
        response = client.post(
            "/api/v1/auth/reset-password",
            params={},
        )
        assert response.status_code == 400
        body = response.json()
        assert body["code"] == ErrorCode.VALIDATION_ERROR

    def test_reset_password_weak_password(self) -> None:
        """Test password reset with weak password."""
        client = _client()
        response = client.post(
            "/api/v1/auth/reset-password",
            params={
                "token": "test-token",
                "new_password": "weak",  # Too short, no uppercase, no digit
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert body["code"] == ErrorCode.VALIDATION_ERROR


class TestTenantEndpoints:
    """Test tenant management endpoints."""

    def test_tenant_usage_statistics(self) -> None:
        """Test tenant usage statistics endpoint."""
        client = _client()
        # Create a test tenant first
        tenant_response = client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant"},
        )
        assert tenant_response.status_code == 200
        tenant_id = tenant_response.json()["id"]

        # Get usage statistics
        response = client.get(
            f"/api/v1/tenants/{tenant_id}/usage",
            params={"period": "month"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == tenant_id
        assert body["period"] == "month"
        assert "usage" in body
        assert "runs" in body["usage"]
        assert "agents" in body["usage"]

    def test_tenant_usage_invalid_period(self) -> None:
        """Test tenant usage with invalid period."""
        client = _client()
        tenant_response = client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant"},
        )
        tenant_id = tenant_response.json()["id"]

        response = client.get(
            f"/api/v1/tenants/{tenant_id}/usage",
            params={"period": "invalid"},
        )
        assert response.status_code == 422

    def test_tenant_billing_information(self) -> None:
        """Test tenant billing endpoint."""
        client = _client()
        tenant_response = client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant"},
        )
        tenant_id = tenant_response.json()["id"]

        response = client.get(f"/api/v1/tenants/{tenant_id}/billing")
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == tenant_id
        assert "plan" in body
        assert "billing" in body
        assert "currency" in body["billing"]

    def test_tenant_billing_specific_month(self) -> None:
        """Test tenant billing for specific month."""
        client = _client()
        tenant_response = client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant"},
        )
        tenant_id = tenant_response.json()["id"]

        response = client.get(
            f"/api/v1/tenants/{tenant_id}/billing",
            params={"month": "2026-05"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["billing_month"] == "2026-05"

    def test_tenant_billing_invalid_month(self) -> None:
        """Test tenant billing with invalid month format."""
        client = _client()
        tenant_response = client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant"},
        )
        tenant_id = tenant_response.json()["id"]

        response = client.get(
            f"/api/v1/tenants/{tenant_id}/billing",
            params={"month": "invalid"},
        )
        assert response.status_code == 400


class TestAuditLogExport:
    """Test audit log export functionality."""

    def test_export_audit_logs_csv(self) -> None:
        """Test exporting audit logs as CSV."""
        client = _client()
        response = client.get("/api/v1/audit-logs/export/csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_export_audit_logs_json(self) -> None:
        """Test exporting audit logs as JSON."""
        client = _client()
        response = client.get("/api/v1/audit-logs/export/json")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert "count" in body
        assert isinstance(body["data"], list)

    def test_export_audit_logs_with_filters(self) -> None:
        """Test exporting audit logs with filters."""
        client = _client()
        response = client.get(
            "/api/v1/audit-logs/export/json",
            params={"action": "create", "resource_type": "user"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body


class TestAuditLogFiltering:
    """Test audit log filtering."""

    def test_filter_by_action(self) -> None:
        """Test filtering audit logs by action."""
        client = _client()
        response = client.get(
            "/api/v1/audit-logs",
            params={"action": "create"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body

    def test_filter_by_resource_type(self) -> None:
        """Test filtering audit logs by resource type."""
        client = _client()
        response = client.get(
            "/api/v1/audit-logs",
            params={"resource_type": "user"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body

    def test_filter_by_outcome(self) -> None:
        """Test filtering audit logs by outcome."""
        client = _client()
        response = client.get(
            "/api/v1/audit-logs",
            params={"outcome": "success"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body

    def test_multiple_filters(self) -> None:
        """Test filtering audit logs with multiple criteria."""
        client = _client()
        response = client.get(
            "/api/v1/audit-logs",
            params={
                "action": "create",
                "resource_type": "user",
                "outcome": "success",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body


class TestAuditChainVerification:
    """Test audit chain verification."""

    def test_verify_audit_chain(self) -> None:
        """Test audit chain verification endpoint."""
        client = _client()
        response = client.get("/api/v1/audit-logs/verify")
        assert response.status_code == 200
        body = response.json()
        assert "valid" in body
        assert "checked" in body
        assert "signed" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
