"""Comprehensive tests for Security API endpoints."""
import pytest
from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.security import router
from backend.app.core.security import (
    APIKeyCreateResponse,
    APIKeyRecord,
    APIKeyStore,
    Principal,
)
from backend.app.dependencies import get_api_key_store, get_current_principal


@pytest.fixture
def mock_principal():
    """Authenticated principal with security:manage scope."""
    return Principal(
        user_id="user1",
        tenant_id="tenant1",
        role="admin",
        scopes=["security:manage"],
        authenticated=True,
    )


@pytest.fixture
def mock_api_key_store():
    """Create mock API key store."""
    return Mock(spec=APIKeyStore)


@pytest.fixture
def client(mock_principal, mock_api_key_store):
    """Test client over a bare app wired with the security router.

    The XAgentAPIError handler is registered so scope/auth failures surface as
    proper 401/403/404 JSON responses (mirrors main.py). Principal and store are
    injected via dependency_overrides — FastAPI Depends cannot be reached with
    unittest.mock.patch.
    """
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    app.dependency_overrides[get_current_principal] = lambda: mock_principal
    app.dependency_overrides[get_api_key_store] = lambda: mock_api_key_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _make_record(**overrides) -> APIKeyRecord:
    data = {
        "name": "test-key",
        "key_prefix": "xag_test",
        "key_hash": "hash-placeholder",
    }
    data.update(overrides)
    return APIKeyRecord(**data)


def _make_create_response(**record_overrides) -> APIKeyCreateResponse:
    return APIKeyCreateResponse(key="secret_key_123", record=_make_record(**record_overrides))


class TestGetMeEndpoint:
    """Test GET /api/v1/security/me endpoint."""

    def test_get_me_success(self, client):
        response = client.get("/api/v1/security/me")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user1"
        assert data["tenant_id"] == "tenant1"

    def test_get_me_returns_principal_fields(self, client):
        response = client.get("/api/v1/security/me")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "tenant_id" in data
        assert "scopes" in data


class TestCreateAPIKeyEndpoint:
    """Test POST /api/v1/security/api-keys endpoint."""

    def test_create_api_key_success(self, client, mock_api_key_store):
        request_data = {"name": "test-key"}
        mock_api_key_store.create.return_value = _make_create_response(id="key1", name="test-key")
        response = client.post("/api/v1/security/api-keys", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["record"]["id"] == "key1"
        assert data["key"] == "secret_key_123"

    def test_create_api_key_requires_scope(self, client, mock_principal, mock_api_key_store):
        mock_principal.scopes = []  # No scope
        response = client.post("/api/v1/security/api-keys", json={"name": "test-key"})
        assert response.status_code in [403, 400]

    def test_create_api_key_with_expiration(self, client, mock_api_key_store):
        request_data = {"name": "test-key", "expires_in_days": 30}
        mock_api_key_store.create.return_value = _make_create_response(id="key1", name="test-key")
        response = client.post("/api/v1/security/api-keys", json=request_data)
        assert response.status_code == 200


class TestListAPIKeysEndpoint:
    """Test GET /api/v1/security/api-keys endpoint."""

    def test_list_api_keys_empty(self, client, mock_api_key_store):
        mock_api_key_store.list.return_value = []
        response = client.get("/api/v1/security/api-keys")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_api_keys_multiple(self, client, mock_api_key_store):
        mock_api_key_store.list.return_value = [
            _make_record(id="key1", name="key1"),
            _make_record(id="key2", name="key2"),
        ]
        response = client.get("/api/v1/security/api-keys")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_api_keys_requires_scope(self, client, mock_principal, mock_api_key_store):
        mock_principal.scopes = []
        response = client.get("/api/v1/security/api-keys")
        assert response.status_code in [403, 400]


class TestGetAPIKeyEndpoint:
    """Test GET /api/v1/security/api-keys/{key_id} endpoint."""

    def test_get_api_key_success(self, client, mock_api_key_store):
        mock_api_key_store.list.return_value = [_make_record(id="key1", name="test-key")]
        response = client.get("/api/v1/security/api-keys/key1")
        assert response.status_code == 200
        assert response.json()["id"] == "key1"

    def test_get_api_key_not_found(self, client, mock_api_key_store):
        mock_api_key_store.list.return_value = []
        response = client.get("/api/v1/security/api-keys/nonexistent")
        assert response.status_code == 404

    def test_get_api_key_requires_scope(self, client, mock_principal, mock_api_key_store):
        mock_principal.scopes = []
        response = client.get("/api/v1/security/api-keys/key1")
        assert response.status_code in [403, 400]


class TestDeleteAPIKeyEndpoint:
    """Test DELETE /api/v1/security/api-keys/{key_id} endpoint."""

    def test_delete_api_key_success(self, client, mock_api_key_store):
        mock_api_key_store.revoke.return_value = _make_record(id="key1", name="test-key")
        response = client.delete("/api/v1/security/api-keys/key1")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

    def test_delete_api_key_not_found(self, client, mock_api_key_store):
        mock_api_key_store.revoke.return_value = None
        response = client.delete("/api/v1/security/api-keys/nonexistent")
        assert response.status_code == 404

    def test_delete_api_key_requires_scope(self, client, mock_principal, mock_api_key_store):
        mock_principal.scopes = []
        response = client.delete("/api/v1/security/api-keys/key1")
        assert response.status_code in [403, 400]


class TestRevokeAPIKeyEndpoint:
    """Test POST /api/v1/security/api-keys/{key_id}/revoke endpoint."""

    def test_revoke_api_key_success(self, client, mock_api_key_store):
        mock_api_key_store.revoke.return_value = _make_record(id="key1", name="test-key")
        response = client.post("/api/v1/security/api-keys/key1/revoke")
        assert response.status_code == 200
        assert response.json()["id"] == "key1"

    def test_revoke_api_key_not_found(self, client, mock_api_key_store):
        mock_api_key_store.revoke.return_value = None
        response = client.post("/api/v1/security/api-keys/nonexistent/revoke")
        assert response.status_code == 404

    def test_revoke_api_key_requires_scope(self, client, mock_principal, mock_api_key_store):
        mock_principal.scopes = []
        response = client.post("/api/v1/security/api-keys/key1/revoke")
        assert response.status_code in [403, 400]


class TestSecurityAPIEdgeCases:
    """Test edge cases for security API."""

    def test_api_key_id_with_special_characters(self, client, mock_api_key_store):
        mock_api_key_store.list.return_value = [_make_record(id="key-123_test.id", name="test-key")]
        response = client.get("/api/v1/security/api-keys/key-123_test.id")
        assert response.status_code == 200

    def test_api_key_name_with_unicode(self, client, mock_api_key_store):
        request_data = {"name": "测试密钥"}
        mock_api_key_store.create.return_value = _make_create_response(id="key1", name="测试密钥")
        response = client.post("/api/v1/security/api-keys", json=request_data)
        assert response.status_code == 200

    def test_very_long_api_key_name(self, client, mock_api_key_store):
        long_name = "a" * 1000
        mock_api_key_store.create.return_value = _make_create_response(id="key1", name=long_name)
        response = client.post("/api/v1/security/api-keys", json={"name": long_name})
        assert response.status_code == 200


class TestSecurityAPIIntegration:
    """Test integration scenarios."""

    def test_create_and_list_api_keys(self, client, mock_api_key_store):
        mock_api_key_store.create.return_value = _make_create_response(id="key1", name="test-key")
        response = client.post("/api/v1/security/api-keys", json={"name": "test-key"})
        assert response.status_code == 200
        mock_api_key_store.list.return_value = [_make_record(id="key1", name="test-key")]
        response = client.get("/api/v1/security/api-keys")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_get_and_delete_api_key(self, client, mock_api_key_store):
        mock_api_key_store.create.return_value = _make_create_response(id="key1", name="test-key")
        response = client.post("/api/v1/security/api-keys", json={"name": "test-key"})
        assert response.status_code == 200
        mock_api_key_store.list.return_value = [_make_record(id="key1", name="test-key")]
        response = client.get("/api/v1/security/api-keys/key1")
        assert response.status_code == 200
        mock_api_key_store.revoke.return_value = _make_record(id="key1", name="test-key")
        response = client.delete("/api/v1/security/api-keys/key1")
        assert response.status_code == 200
