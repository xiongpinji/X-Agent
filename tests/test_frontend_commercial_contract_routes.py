from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal
from backend.app.main import app


FRONTEND_COMMERCIAL_PATHS = [
    "/api/v1/forum/posts",
    "/api/v1/forum/posts/1",
    "/api/v1/analytics/realtime",
    "/api/v1/analytics/costs",
    "/api/v1/analytics/performance",
    "/api/v1/marketplace/plugins",
    "/api/v1/marketplace/skills",
    "/api/v1/marketplace/templates",
    "/api/v1/templates",
    "/api/v1/sessions",
    "/api/v1/skills",
    "/api/v1/enterprise/tenants",
    "/api/v1/creative/projects",
    "/api/v1/billing/plans",
]


def _admin_principal() -> Principal:
    return Principal(
        tenant_id="tenant_a",
        user_id="admin-a",
        role="admin",
        scopes=list(ROLE_SCOPES["admin"]),
        authenticated=True,
    )


def test_frontend_commercial_paths_are_mounted_for_authenticated_admin() -> None:
    async def override_principal() -> Principal:
        return _admin_principal()

    app.dependency_overrides[get_current_principal] = override_principal
    try:
        client = TestClient(app)
        failures = []
        for path in FRONTEND_COMMERCIAL_PATHS:
            response = client.get(path)
            if response.status_code != 200:
                failures.append(f"{path} -> {response.status_code}: {response.text[:120]}")

        assert failures == []
    finally:
        app.dependency_overrides.pop(get_current_principal, None)


def test_frontend_commercial_paths_do_not_allow_anonymous_access() -> None:
    client = TestClient(app)
    failures = []
    for path in FRONTEND_COMMERCIAL_PATHS:
        response = client.get(path)
        if response.status_code not in {401, 403}:
            failures.append(f"{path} -> {response.status_code}: {response.text[:120]}")

    assert failures == []
