from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.capabilities import router
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.second_batch_capabilities import build_second_batch_capability_manifest
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal
from backend.app.main import app as main_app


def _principal(role: str = "developer", scopes: list[str] | None = None) -> Principal:
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        role=role,
        authenticated=True,
        api_key_id="test-key",
        permission_scope=scopes or list(ROLE_SCOPES[role]),
        scopes=scopes or list(ROLE_SCOPES[role]),
    )


def _app(principal: Principal) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    app.dependency_overrides[get_current_principal] = lambda: principal
    return app


def test_second_batch_capability_manifest_contract() -> None:
    manifest = build_second_batch_capability_manifest()
    capabilities = {item["capability_id"]: item for item in manifest["capabilities"]}

    assert manifest["status"] == "locally_verified_contracts"
    assert manifest["full_release_claimed"] is False
    assert manifest["external_api_first"] is True
    assert manifest["local_model_runtime_supported"] is False
    assert manifest["network_mutation_allowed"] is False
    assert capabilities["external_llm_governance"]["external_api_only"] is True
    assert capabilities["api_only_rag"]["external_api_only"] is True
    assert capabilities["provider_preflight"]["surfaces"] == [
        {"method": "GET", "path": "/api/v1/providers/preflight"}
    ]
    assert capabilities["creative_video_protocol"]["status"] == "reserved_owner_gated"
    assert capabilities["creative_video_protocol"]["owner_gated_live_use"] is True
    assert "second_batch_quality_gate" in {
        evidence_type
        for item in manifest["capabilities"]
        for evidence_type in item["evidence_types"]
    }


def test_second_batch_capabilities_requires_audit_read_scope() -> None:
    client = TestClient(_app(_principal(role="user", scopes=["agent:run"])))

    response = client.get("/api/v1/capabilities/second-batch")

    assert response.status_code == 403
    assert "audit:read" in response.text


def test_second_batch_capabilities_endpoint_returns_manifest() -> None:
    client = TestClient(_app(_principal()))

    response = client.get("/api/v1/capabilities/second-batch")

    assert response.status_code == 200
    payload = response.json()
    capability_ids = {item["capability_id"] for item in payload["capabilities"]}
    assert payload["summary"]["capability_count"] == len(payload["capabilities"])
    assert "external_llm_governance" in capability_ids
    assert "provider_preflight" in capability_ids
    assert "creative_video_protocol" in capability_ids
    assert payload["full_release_claimed"] is False


def test_main_app_mounts_second_batch_capabilities_route() -> None:
    routes = {
        getattr(route, "path", "")
        for route in main_app.routes
        if hasattr(route, "path")
    }

    assert "/api/v1/capabilities/second-batch" in routes
