from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.security import router as security_router
from backend.app.api.users import router as users_router
from backend.app.core.admin import UserCreateRequest, user_store
from backend.app.core.audit import AuditStore
from backend.app.core.security import (
    APIKeyCreateRequest,
    APIKeyStore,
    Principal,
    ROLE_SCOPES,
)
from backend.app.dependencies import (
    get_api_key_store,
    get_audit_store,
    get_current_principal,
)


def _tenant_admin(tenant_id: str = "tenant-a") -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=f"{tenant_id}-admin",
        role="admin",
        scopes=list(ROLE_SCOPES["admin"]),
        authenticated=True,
        api_key_id=f"{tenant_id}-admin-key",
    )


def _platform_admin() -> Principal:
    return Principal(
        tenant_id="default",
        user_id="bootstrap-admin",
        role="admin",
        scopes=list(ROLE_SCOPES["admin"]),
        authenticated=True,
        api_key_id="bootstrap",
    )


@pytest.fixture
def api_key_store() -> APIKeyStore:
    return APIKeyStore()


@pytest.fixture
def audit_store() -> AuditStore:
    return AuditStore()


@pytest.fixture
def principal_holder() -> dict[str, Principal]:
    return {"principal": _tenant_admin("tenant-a")}


@pytest.fixture
def client(
    principal_holder: dict[str, Principal],
    api_key_store: APIKeyStore,
    audit_store: AuditStore,
) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(security_router)
    app.include_router(users_router)
    app.dependency_overrides[get_current_principal] = (
        lambda: principal_holder["principal"]
    )
    app.dependency_overrides[get_api_key_store] = lambda: api_key_store
    app.dependency_overrides[get_audit_store] = lambda: audit_store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_key(
    store: APIKeyStore,
    *,
    name: str,
    tenant_id: str,
    user_id: str,
) -> str:
    response = store.create(
        APIKeyCreateRequest(
            name=name,
            tenant_id=tenant_id,
            user_id=user_id,
            role="developer",
            scopes=["memory:read"],
        )
    )
    return response.record.id


def test_tenant_admin_lists_only_own_tenant_api_keys(
    client: TestClient,
    api_key_store: APIKeyStore,
) -> None:
    own_id = _create_key(
        api_key_store,
        name="own-key",
        tenant_id="tenant-a",
        user_id="tenant-a-user",
    )
    other_id = _create_key(
        api_key_store,
        name="other-key",
        tenant_id="tenant-b",
        user_id="tenant-b-user",
    )

    response = client.get("/api/v1/security/api-keys")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert own_id in ids
    assert other_id not in ids


def test_tenant_admin_cannot_get_or_revoke_other_tenant_api_key(
    client: TestClient,
    api_key_store: APIKeyStore,
) -> None:
    other_id = _create_key(
        api_key_store,
        name="other-key",
        tenant_id="tenant-b",
        user_id="tenant-b-user",
    )

    get_response = client.get(f"/api/v1/security/api-keys/{other_id}")
    revoke_response = client.post(f"/api/v1/security/api-keys/{other_id}/revoke")
    record = next(item for item in api_key_store.list() if item.id == other_id)

    assert get_response.status_code == 404
    assert revoke_response.status_code == 404
    assert record.revoked is False


def test_tenant_admin_created_api_key_is_bound_to_principal_tenant(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/security/api-keys",
        json={
            "name": "forged",
            "tenant_id": "tenant-b",
            "user_id": "other-user",
            "role": "admin",
            "scopes": ["security:manage", "tools:*"],
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["tenant_id"] == "tenant-a"
    assert record["user_id"] == "tenant-a-admin"
    assert record["role"] == "custom"
    assert record["scopes"] == ["security:manage", "tools:*"]


def test_platform_admin_can_list_cross_tenant_api_keys(
    client: TestClient,
    principal_holder: dict[str, Principal],
    api_key_store: APIKeyStore,
) -> None:
    principal_holder["principal"] = _platform_admin()
    own_id = _create_key(
        api_key_store,
        name="tenant-a-key",
        tenant_id="tenant-a",
        user_id="tenant-a-user",
    )
    other_id = _create_key(
        api_key_store,
        name="tenant-b-key",
        tenant_id="tenant-b",
        user_id="tenant-b-user",
    )

    response = client.get("/api/v1/security/api-keys")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert {own_id, other_id} <= ids


def _create_user(email: str, tenant_id: str) -> str:
    return user_store.create(
        UserCreateRequest(email=email, tenant_id=tenant_id, role="developer")
    ).id


def test_tenant_admin_lists_only_own_tenant_users(client: TestClient) -> None:
    own_id = _create_user("own@example.com", "tenant-a")
    other_id = _create_user("other@example.com", "tenant-b")

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert own_id in ids
    assert other_id not in ids


def test_tenant_admin_cannot_get_update_or_delete_other_tenant_user(
    client: TestClient,
) -> None:
    other_id = _create_user("other@example.com", "tenant-b")

    get_response = client.get(f"/api/v1/users/{other_id}")
    update_response = client.put(
        f"/api/v1/users/{other_id}",
        json={"display_name": "Cross Tenant Edit"},
    )
    delete_response = client.delete(f"/api/v1/users/{other_id}")
    record = user_store.get(other_id)

    assert get_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404
    assert record is not None
    assert record.display_name != "Cross Tenant Edit"


def test_tenant_admin_create_and_update_user_stays_in_principal_tenant(
    client: TestClient,
) -> None:
    create_response = client.post(
        "/api/v1/users",
        json={
            "email": "created@example.com",
            "display_name": "Created",
            "tenant_id": "tenant-b",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["tenant_id"] == "tenant-a"

    update_response = client.put(
        f"/api/v1/users/{created['id']}",
        json={"tenant_id": "tenant-b", "display_name": "Updated"},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["tenant_id"] == "tenant-a"
    assert updated["display_name"] == "Updated"


def test_user_activity_is_tenant_scoped(
    client: TestClient,
    audit_store: AuditStore,
) -> None:
    user_id = _create_user("own@example.com", "tenant-a")
    audit_store.record(
        tenant_id="tenant-a",
        actor_id=user_id,
        action="login",
        resource_type="user",
    )
    audit_store.record(
        tenant_id="tenant-b",
        actor_id=user_id,
        action="cross-tenant",
        resource_type="user",
    )

    response = client.get(f"/api/v1/users/{user_id}/activity")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["tenant_id"] for item in items] == ["tenant-a"]
    assert [item["action"] for item in items] == ["login"]


def test_platform_admin_can_read_cross_tenant_user(
    client: TestClient,
    principal_holder: dict[str, Principal],
) -> None:
    principal_holder["principal"] = _platform_admin()
    other_id = _create_user("other@example.com", "tenant-b")

    response = client.get(f"/api/v1/users/{other_id}")

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-b"
