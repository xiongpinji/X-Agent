from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.enterprise import (
    _enforce_tenant_access,
    get_enterprise_service,
    router,
)
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.enterprise import EnterpriseService, EnterpriseTenant
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal


def _principal(
    *,
    tenant_id: str = "tenant-a",
    role: str = "admin",
    scopes: list[str] | None = None,
) -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=f"{role}-user",
        role=role,
        scopes=scopes if scopes is not None else ["security:manage"],
        authenticated=True,
    )


@pytest.fixture
def enterprise_service() -> EnterpriseService:
    service = EnterpriseService()
    service.tenants.create(EnterpriseTenant(id="tenant-a", name="Tenant A"))
    service.tenants.create(EnterpriseTenant(id="tenant-b", name="Tenant B"))
    return service


@pytest.fixture
def client(enterprise_service: EnterpriseService):
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.dependency_overrides[get_enterprise_service] = lambda: enterprise_service
    with TestClient(app) as test_client:
        yield test_client, app
    app.dependency_overrides.clear()


def test_enterprise_create_tenant_requires_credentials(client) -> None:
    test_client, _ = client

    response = test_client.post("/api/v1/enterprise/tenants", json={"name": "blocked"})

    assert response.status_code == 401


def test_enterprise_create_tenant_rejects_viewer(client) -> None:
    test_client, app = client
    app.dependency_overrides[get_current_principal] = lambda: _principal(
        role="viewer",
        scopes=["audit:read"],
    )

    response = test_client.post("/api/v1/enterprise/tenants", json={"name": "blocked"})

    assert response.status_code == 403


def test_enterprise_cross_tenant_access_is_rejected_for_non_admin() -> None:
    principal = _principal(tenant_id="tenant-a", role="developer", scopes=["security:manage"])

    with pytest.raises(XAgentAPIError) as exc_info:
        _enforce_tenant_access(principal, "tenant-b")

    assert exc_info.value.status_code == 403


def test_enterprise_admin_can_create_tenant(client) -> None:
    test_client, app = client
    app.dependency_overrides[get_current_principal] = lambda: _principal(role="admin")

    response = test_client.post(
        "/api/v1/enterprise/tenants",
        json={"name": "Customer", "plan": "enterprise"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Customer"
    assert payload["plan"] == "enterprise"
