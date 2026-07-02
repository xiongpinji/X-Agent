"""Authentication & authorization tests for the workspace API.

Covers (per the workspace security hardening):
* 401 for unauthenticated callers on every endpoint
* 403 for authenticated-but-under-privileged callers (viewer role)
* cross-tenant 403 on delete / unmount (ownership enforcement)
* mount allowlist 403 (host path outside workspace roots)
* per-principal isolation (no shared ``user_id="default"`` namespace)
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import workspace
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal


def _set_workspace_root(monkeypatch, tmp_path) -> None:
    """Point the workspace allowlist root at an isolated temp dir.

    ``get_workspace_roots()`` lazily reads ``settings.PROJECT_ROOT`` and
    appends ``/workspaces``, so patching that attribute redirects both the
    per-user workspace base and the mount allowlist in one place.
    """
    import backend.app.settings as settings_module

    monkeypatch.setattr(settings_module, "PROJECT_ROOT", tmp_path)


@pytest.fixture(autouse=True)
def _isolate_workspace_root(tmp_path_factory, monkeypatch):
    """Redirect PROJECT_ROOT for every test so none touches the real repo.

    Tests that need to inspect created files re-point it at their own
    ``tmp_path`` via ``_set_workspace_root``; this autouse default simply
    guarantees the parametrized auth-only tests never ``mkdir`` the real
    project ``workspaces/`` directory.
    """
    import backend.app.settings as settings_module

    base = tmp_path_factory.mktemp("ws_root_default")
    monkeypatch.setattr(settings_module, "PROJECT_ROOT", base)


def _principal(
    role: str = "developer",
    *,
    tenant_id: str = "tenant-a",
    user_id: str | None = None,
    authenticated: bool = True,
) -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=user_id or f"{role}-user",
        role=role,
        scopes=list(ROLE_SCOPES.get(role, [])),
        authenticated=authenticated,
    )


@pytest.fixture
def app_factory():
    def make_app(principal: Principal | None) -> FastAPI:
        app = FastAPI()
        app.include_router(workspace.router)
        app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
        if principal is not None:
            app.dependency_overrides[get_current_principal] = lambda: principal
        else:
            # Simulate the unauthenticated principal the real dependency
            # returns in non-production when no credentials are supplied.
            app.dependency_overrides[get_current_principal] = (
                lambda: Principal(authenticated=False, scopes=[])
            )
        return app

    return make_app


# --- 401: unauthenticated ---------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/v1/workspace/create", {"workspace_type": "project"}),
        ("get", "/api/v1/workspace/list", None),
        ("delete", "/api/v1/workspace/some-id", None),
        ("post", "/api/v1/workspace/mount", {"host_path": "/tmp"}),
        ("delete", "/api/v1/workspace/mount/some-id", None),
        ("get", "/api/v1/workspace/mounts", None),
        ("post", "/api/v1/workspace/validate-path", {"path": "/x", "operation": "read"}),
        ("get", "/api/v1/workspace/audit-logs", None),
        ("post", "/api/v1/workspace/cleanup-expired", None),
    ],
)
def test_all_endpoints_reject_unauthenticated(app_factory, method, path, body) -> None:
    client = TestClient(app_factory(None))
    response = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert response.status_code == 401


# --- 403: authenticated but missing scope (viewer) --------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/v1/workspace/create", {"workspace_type": "project"}),
        ("get", "/api/v1/workspace/list", None),
        ("delete", "/api/v1/workspace/some-id", None),
        ("post", "/api/v1/workspace/mount", {"host_path": "/tmp"}),
        ("delete", "/api/v1/workspace/mount/some-id", None),
        ("get", "/api/v1/workspace/mounts", None),
        ("post", "/api/v1/workspace/validate-path", {"path": "/x", "operation": "read"}),
        ("get", "/api/v1/workspace/audit-logs", None),
        ("post", "/api/v1/workspace/cleanup-expired", None),
    ],
)
def test_all_endpoints_reject_viewer_scope(app_factory, method, path, body) -> None:
    # viewer has no agent:read / agent:run scopes.
    client = TestClient(app_factory(_principal("viewer")))
    response = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert response.status_code == 403


# --- happy path: developer can create + list --------------------------------


def test_developer_can_create_and_list_workspace(app_factory, tmp_path, monkeypatch) -> None:
    # Point workspaces at an isolated temp dir so the test never touches the
    # real project workspaces directory.
    _set_workspace_root(monkeypatch, tmp_path)
    client = TestClient(app_factory(_principal("developer")))

    created = client.post(
        "/api/v1/workspace/create",
        json={"workspace_type": "project"},
    )
    assert created.status_code == 200
    workspace_id = created.json()["workspace_id"]

    listed = client.get("/api/v1/workspace/list")
    assert listed.status_code == 200
    assert any(ws["workspace_id"] == workspace_id for ws in listed.json())


# --- cross-tenant 403 on delete ---------------------------------------------


def test_delete_workspace_cross_tenant_forbidden(app_factory, tmp_path, monkeypatch) -> None:
    _set_workspace_root(monkeypatch, tmp_path)

    # Owner (tenant-a) creates a workspace.
    owner = _principal("developer", tenant_id="tenant-a", user_id="alice")
    owner_client = TestClient(app_factory(owner))
    created = owner_client.post("/api/v1/workspace/create", json={"workspace_type": "project"})
    assert created.status_code == 200
    workspace_id = created.json()["workspace_id"]

    # A different tenant tries to delete it.
    attacker = _principal("developer", tenant_id="tenant-b", user_id="mallory")
    attacker_client = TestClient(app_factory(attacker))
    resp = attacker_client.delete(f"/api/v1/workspace/{workspace_id}")
    assert resp.status_code == 403

    # And the workspace is still listed for the real owner.
    still_there = owner_client.get("/api/v1/workspace/list")
    assert any(ws["workspace_id"] == workspace_id for ws in still_there.json())


# --- per-principal isolation: no shared "default" namespace -----------------


def test_workspaces_isolated_per_principal(app_factory, tmp_path, monkeypatch) -> None:
    _set_workspace_root(monkeypatch, tmp_path)

    alice = _principal("developer", tenant_id="tenant-a", user_id="alice")
    bob = _principal("developer", tenant_id="tenant-b", user_id="bob")

    alice_client = TestClient(app_factory(alice))
    bob_client = TestClient(app_factory(bob))

    alice_client.post("/api/v1/workspace/create", json={"workspace_type": "project"})

    # Bob must not see Alice's workspace.
    bob_list = bob_client.get("/api/v1/workspace/list")
    assert bob_list.status_code == 200
    assert bob_list.json() == []


def test_namespace_never_default() -> None:
    # The shared legacy "default" namespace must never be produced.
    p = _principal("developer", tenant_id="default", user_id="default")
    ns = workspace._principal_namespace(p)
    assert ns != "default"
    assert "default__default" == ns


# --- mount allowlist 403 ----------------------------------------------------


def test_mount_outside_allowlist_forbidden(app_factory, tmp_path, monkeypatch) -> None:
    _set_workspace_root(monkeypatch, tmp_path)
    client = TestClient(app_factory(_principal("developer")))

    # /tmp (or any host dir outside PROJECT_ROOT/workspaces) is not allowlisted.
    outside = tmp_path / "outside_root"
    outside.mkdir()
    resp = client.post("/api/v1/workspace/mount", json={"host_path": str(outside)})
    assert resp.status_code == 403


def test_mount_within_allowlist_succeeds(app_factory, tmp_path, monkeypatch) -> None:
    _set_workspace_root(monkeypatch, tmp_path)
    client = TestClient(app_factory(_principal("developer")))

    # A directory inside PROJECT_ROOT/workspaces is allowed.
    target = tmp_path / "workspaces" / "shared_data"
    target.mkdir(parents=True)
    resp = client.post("/api/v1/workspace/mount", json={"host_path": str(target)})
    assert resp.status_code == 200
    assert resp.json()["host_path"].endswith("shared_data")


def test_unmount_cross_tenant_forbidden(app_factory, tmp_path, monkeypatch) -> None:
    _set_workspace_root(monkeypatch, tmp_path)

    target = tmp_path / "workspaces" / "owned"
    target.mkdir(parents=True)

    owner = _principal("developer", tenant_id="tenant-a", user_id="alice")
    owner_client = TestClient(app_factory(owner))
    mounted = owner_client.post("/api/v1/workspace/mount", json={"host_path": str(target)})
    assert mounted.status_code == 200
    mount_id = mounted.json()["mount_id"]

    attacker = _principal("developer", tenant_id="tenant-b", user_id="mallory")
    attacker_client = TestClient(app_factory(attacker))
    resp = attacker_client.delete(f"/api/v1/workspace/mount/{mount_id}")
    assert resp.status_code == 403
