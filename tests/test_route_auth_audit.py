from __future__ import annotations

from fastapi import Depends, FastAPI

from backend.app.dependencies import get_current_principal
from backend.app.main import app
from scripts.route_auth_audit import audit_routes, issues_to_dicts, load_app


def test_real_mounted_routes_have_auth_or_declared_public_strategy() -> None:
    assert audit_routes(app) == []


def test_audit_uses_backend_main_mounted_routes() -> None:
    assert load_app("backend.app.main:app") is app


def test_audit_detects_mounted_private_route_without_principal() -> None:
    test_app = FastAPI()

    @test_app.get("/api/v1/private")
    async def private_route() -> dict[str, bool]:
        return {"ok": True}

    issues = audit_routes(test_app, public_routes=set(), signature_routes=set())

    issue = issues_to_dicts(issues)
    assert issue[0]["method"] == "GET"
    assert issue[0]["path"] == "/api/v1/private"
    assert issue[0]["endpoint"].endswith(
        "test_route_auth_audit.test_audit_detects_mounted_private_route_without_principal.<locals>.private_route"
    )
    assert issue[0]["reason"] == "mounted API route lacks get_current_principal or an equivalent auth strategy"


def test_audit_allows_mounted_route_with_principal_dependency() -> None:
    test_app = FastAPI()

    @test_app.get("/api/v1/private")
    async def private_route(principal=Depends(get_current_principal)) -> dict[str, bool]:
        return {"authenticated": principal.authenticated}

    assert audit_routes(test_app, public_routes=set(), signature_routes=set()) == []
