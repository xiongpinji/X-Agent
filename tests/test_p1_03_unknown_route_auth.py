from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.route_auth_audit import audit_routes


@dataclass
class _Principal:
    role: str


UNKNOWN_ROUTE_MODULES = (
    "backend.app.api.enterprise_audit",
    "backend.app.api.enterprise_cluster",
    "backend.app.api.enterprise_migration",
    "backend.app.api.enterprise_sso",
    "backend.app.api.i18n",
    "backend.app.api.partners",
    "backend.app.api.plugin_marketplace",
)


def _app_with_router(module_name: str, *, role: str = "viewer") -> FastAPI:
    module = importlib.import_module(module_name)
    app = FastAPI()

    @app.middleware("http")
    async def _principal_middleware(request, call_next):  # type: ignore[no-untyped-def]
        request.state.principal = _Principal(role=role)
        return await call_next(request)

    app.include_router(module.router)
    return app


@pytest.mark.parametrize("module_name", UNKNOWN_ROUTE_MODULES)
def test_p1_03_unknown_route_modules_import_and_pass_route_auth_audit(module_name: str) -> None:
    assert audit_routes(_app_with_router(module_name, role="admin")) == []


@pytest.mark.parametrize(
    ("module_name", "method", "path", "payload"),
    [
        ("backend.app.api.enterprise_audit", "post", "/api/v1/enterprise/audit/logs/create", {}),
        ("backend.app.api.enterprise_cluster", "post", "/api/v1/enterprise/cluster/register", {}),
        ("backend.app.api.enterprise_migration", "post", "/api/v1/enterprise/migration/plan", {}),
        ("backend.app.api.enterprise_sso", "post", "/api/v1/enterprise/sso/saml/config", {}),
        ("backend.app.api.partners", "post", "/api/v1/partners/register", {}),
        ("backend.app.api.plugin_marketplace", "post", "/api/v1/plugins/install", {}),
    ],
)
def test_p1_03_enterprise_partner_plugin_unknown_routes_require_admin(
    module_name: str,
    method: str,
    path: str,
    payload: dict[str, Any],
) -> None:
    client = TestClient(_app_with_router(module_name, role="developer"))

    response = getattr(client, method)(path, json=payload)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/i18n/set-locale", {"language": "en", "region": "US"}),
        ("post", "/api/i18n/format-date", None),
        ("post", "/api/i18n/format-currency", None),
        ("post", "/api/i18n/format-number", None),
    ],
)
def test_p1_03_i18n_unknown_write_routes_require_developer(
    method: str,
    path: str,
    payload: dict[str, Any] | None,
) -> None:
    client = TestClient(_app_with_router("backend.app.api.i18n", role="viewer"))

    response = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)

    assert response.status_code == 403


def test_p1_03_public_auth_entrypoints_remain_declared_public() -> None:
    from scripts.route_auth_audit import PUBLIC_ROUTES

    assert ("POST", "/api/v1/auth/login") in PUBLIC_ROUTES
    assert ("POST", "/api/v1/auth/login/oauth") in PUBLIC_ROUTES
