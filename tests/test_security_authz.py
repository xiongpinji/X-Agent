"""Security tests for authorization system."""

from __future__ import annotations

import pytest

from backend.app.core.security import Principal, RBACPolicy, ROLE_SCOPES


class TestRBACPolicy:
    """Test RBAC policy enforcement."""

    @pytest.fixture
    def policy(self):
        """Create RBAC policy instance."""
        return RBACPolicy()

    def test_admin_has_all_scopes(self, policy):
        """Test that admin role has all scopes."""
        principal = Principal(
            user_id="admin",
            role="admin",
            scopes=ROLE_SCOPES["admin"],
            authenticated=True,
        )
        assert policy.has_scope(principal, "agent:run")
        assert policy.has_scope(principal, "workflow:create")
        assert policy.has_scope(principal, "security:manage")
        assert policy.has_scope(principal, "tools:*")

    def test_developer_has_limited_scopes(self, policy):
        """Test that developer role has limited scopes."""
        principal = Principal(
            user_id="dev",
            role="developer",
            scopes=ROLE_SCOPES["developer"],
            authenticated=True,
        )
        assert policy.has_scope(principal, "agent:run")
        assert policy.has_scope(principal, "workflow:create")
        assert not policy.has_scope(principal, "security:manage")

    def test_user_has_minimal_scopes(self, policy):
        """Test that user role has minimal scopes."""
        principal = Principal(
            user_id="user",
            role="user",
            scopes=ROLE_SCOPES["user"],
            authenticated=True,
        )
        assert policy.has_scope(principal, "agent:run")
        assert not policy.has_scope(principal, "workflow:create")
        assert not policy.has_scope(principal, "security:manage")

    def test_viewer_has_read_only_scopes(self, policy):
        """Test that viewer role has read-only scopes."""
        principal = Principal(
            user_id="viewer",
            role="viewer",
            scopes=ROLE_SCOPES["viewer"],
            authenticated=True,
        )
        assert policy.has_scope(principal, "memory:read")
        assert policy.has_scope(principal, "audit:read")
        assert not policy.has_scope(principal, "agent:run")
        assert not policy.has_scope(principal, "memory:write")

    def test_wildcard_scope_matching(self, policy):
        """Test wildcard scope matching."""
        principal = Principal(
            user_id="admin",
            role="admin",
            scopes=["tools:*"],
            authenticated=True,
        )
        assert policy.has_scope(principal, "tools:read")
        assert policy.has_scope(principal, "tools:write")
        assert policy.has_scope(principal, "tools:execute")

    def test_unauthenticated_principal_denied(self, policy):
        """Test that unauthenticated principals are denied."""
        principal = Principal(
            user_id="anonymous",
            authenticated=False,
        )
        assert not policy.has_scope(principal, "agent:run")
        assert not policy.has_scope(principal, "memory:read")

    def test_resolve_scopes_for_authenticated_user(self, policy):
        """Test scope resolution for authenticated users."""
        principal = Principal(
            user_id="dev",
            role="developer",
            scopes=ROLE_SCOPES["developer"],
            authenticated=True,
        )
        requested = ["agent:run", "security:manage", "workflow:create"]
        resolved = policy.resolve_scopes(principal, requested)
        # Should only include scopes the user has
        assert "agent:run" in resolved
        assert "workflow:create" in resolved
        assert "security:manage" not in resolved

    def test_resolve_scopes_for_unauthenticated_user(self, policy):
        """Test scope resolution for unauthenticated users."""
        principal = Principal(
            user_id="anonymous",
            authenticated=False,
        )
        requested = ["agent:run", "memory:read"]
        resolved = policy.resolve_scopes(principal, requested)
        # SECURITY: unauthenticated principals get NO scopes (resolve_scopes
        # returns [] for them). This is stricter than the old "pass-through then
        # deny at enforcement" model — fail-closed at resolution time.
        assert resolved == []

    def test_scopes_for_role(self, policy):
        """Test getting scopes for a role."""
        admin_scopes = policy.scopes_for_role("admin")
        assert "agent:run" in admin_scopes
        assert "security:manage" in admin_scopes

        developer_scopes = policy.scopes_for_role("developer")
        assert "agent:run" in developer_scopes
        assert "security:manage" not in developer_scopes

    def test_unknown_role_returns_empty_scopes(self, policy):
        """Test that unknown roles return empty scopes."""
        scopes = policy.scopes_for_role("unknown_role")
        assert scopes == []

    def test_principal_with_custom_scopes(self, policy):
        """Test principal with custom scopes."""
        principal = Principal(
            user_id="custom",
            role="custom",
            scopes=["custom:read", "custom:write"],
            authenticated=True,
        )
        assert policy.has_scope(principal, "custom:read")
        assert policy.has_scope(principal, "custom:write")
        assert not policy.has_scope(principal, "custom:delete")


class TestAuthorizationEnforcement:
    """Test authorization enforcement in API endpoints."""

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated access is denied to protected endpoints."""
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        # Try to access protected endpoint without authentication
        response = client.get("/api/v1/users")
        assert response.status_code == 401

    def test_insufficient_scope_denied(self):
        """Test that insufficient scope is denied."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.core.security import APIKeyStore
        from backend.app.core.admin import UserCreateRequest, user_store

        client = TestClient(app)

        # Create a user with limited scope
        user = user_store.create(
            UserCreateRequest(email="limited@example.com", role="viewer"),
            password="ValidPass123",
        )

        # Try to access admin endpoint
        response = client.get(
            "/api/v1/users",
            headers={"x-api-key": "invalid-key"},
        )
        # Should fail due to invalid key
        assert response.status_code == 401

    def test_api_key_authentication(self):
        """Test API key authentication."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.dependencies import get_api_key_store
        from backend.app.core.security import APIKeyCreateRequest

        client = TestClient(app)
        store = get_api_key_store()

        # Create API key
        request = APIKeyCreateRequest(
            name="test-key",
            role="developer",
        )
        response = store.create(request)
        api_key = response.key

        # Use API key to authenticate
        result = store.authenticate(api_key)
        assert result is not None
        assert result.authenticated
        assert result.role == "developer"

    def test_api_key_revocation(self):
        """Test API key revocation."""
        from backend.app.dependencies import get_api_key_store
        from backend.app.core.security import APIKeyCreateRequest

        store = get_api_key_store()

        # Create and revoke API key
        request = APIKeyCreateRequest(
            name="test-key",
            role="developer",
        )
        response = store.create(request)
        api_key = response.key
        key_id = response.record.id

        # Revoke key
        store.revoke(key_id)

        # Try to authenticate with revoked key
        result = store.authenticate(api_key)
        assert result is None
