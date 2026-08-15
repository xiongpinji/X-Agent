from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import artifacts as artifacts_api
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.artifacts import Artifact, ArtifactStorage
from backend.app.core.audit import AuditStore
from backend.app.core.run_artifacts import RunArtifactManager, get_run_artifact_manager
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal


class _FailingAudit:
    def record(self, **_kwargs) -> None:
        raise RuntimeError("PRIVATE_AUDIT_FAILURE")


def _principal(tenant_id: str, user_id: str) -> Principal:
    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        role="user",
        scopes=list(ROLE_SCOPES["user"]),
        authenticated=True,
    )


@pytest.fixture
def isolated_api(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, RunArtifactManager, dict]]:
    storage = ArtifactStorage(tmp_path / "artifacts")
    manager = RunArtifactManager(tmp_path / "runs", artifact_storage=storage)
    audit = AuditStore(tmp_path / "audit.jsonl", hmac_secret="test-secret")
    active = {"principal": _principal("tenant-a", "user-a")}
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(artifacts_api.router)
    app.dependency_overrides[get_current_principal] = lambda: active["principal"]
    app.dependency_overrides[get_run_artifact_manager] = lambda: manager
    monkeypatch.setattr(artifacts_api, "get_audit_store", lambda: audit)
    with TestClient(app) as client:
        yield client, manager, active


@pytest.mark.asyncio
async def test_all_artifact_resources_are_tenant_and_user_scoped(isolated_api) -> None:
    client, manager, active = isolated_api
    artifact = Artifact(
        name="private.html",
        type="html",
        content="<p>private</p>",
        tenant_id="tenant-a",
        user_id="user-a",
        run_id="private-run",
        trace_id="private-run",
    )
    await manager.artifact_storage.save_artifact(artifact)
    await manager.save_manifest(
        manager.completed_manifest(
            run_id="private-run",
            tenant_id="tenant-a",
            user_id="user-a",
            artifacts=[artifact],
            audit_ids=[],
        )
    )

    for principal in (
        _principal("tenant-b", "user-a"),
        _principal("tenant-a", "user-b"),
        _principal("TENANT-A", "user-a"),
    ):
        active["principal"] = principal
        assert client.get(f"/api/v1/artifacts/{artifact.id}").status_code == 404
        assert client.get(f"/api/v1/artifacts/{artifact.id}/render").status_code == 404
        assert client.get(f"/api/v1/artifacts/{artifact.id}/download").status_code == 404
        assert client.put(
            f"/api/v1/artifacts/{artifact.id}",
            json={"name": "stolen"},
        ).status_code == 404
        assert client.delete(f"/api/v1/artifacts/{artifact.id}").status_code == 404
        assert client.get("/api/v1/artifacts/runs/private-run/manifest").status_code == 404
        assert client.post("/api/v1/artifacts/runs/private-run/archive").status_code == 404
        assert client.get("/api/v1/artifacts").json()["artifacts"] == []
        assert client.get("/api/v1/artifacts/search", params={"query": "private"}).json()["results"] == []
        assert client.get("/api/v1/artifacts/stats").json()["total_artifacts"] == 0

    active["principal"] = _principal("tenant-a", "user-a")
    archive = client.post("/api/v1/artifacts/runs/private-run/archive").json()["archive"]
    active["principal"] = _principal("tenant-b", "user-b")
    assert (
        client.get(f"/api/v1/artifacts/archives/{archive['archive_id']}/download").status_code
        == 404
    )


def test_path_traversal_ids_and_header_injection_are_rejected(isolated_api) -> None:
    client, _manager, _active = isolated_api
    assert client.get("/api/v1/artifacts/..%2F..%2Fsecret/download").status_code == 404
    response = client.post(
        "/api/v1/artifacts",
        json={
            "name": "evil\r\nX-Injected: yes.html",
            "type": "html",
            "content": "safe",
            "id": "client-forged",
            "tenant_id": "tenant-b",
            "user_id": "user-b",
            "content_sha256": "forged",
        },
    )
    assert response.status_code == 201
    artifact_id = response.json()["id"]
    assert artifact_id != "client-forged"
    downloaded = client.get(f"/api/v1/artifacts/{artifact_id}/download")
    assert downloaded.status_code == 200
    assert "x-injected" not in downloaded.headers
    artifact = client.get(f"/api/v1/artifacts/{artifact_id}").json()
    assert artifact["tenant_id"] == "tenant-a"
    assert artifact["user_id"] == "user-a"
    assert artifact["content_sha256"] != "forged"


def test_render_errors_are_stable_and_do_not_expose_internal_details(isolated_api) -> None:
    client, _manager, _active = isolated_api
    created = client.post(
        "/api/v1/artifacts",
        json={"name": "bad", "type": "private-internal-type", "content": "safe"},
    )
    response = client.get(
        f"/api/v1/artifacts/{created.json()['id']}/render"
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Artifact could not be rendered."
    assert "private-internal-type" not in response.text


def test_create_rolls_back_when_required_audit_write_fails(
    isolated_api,
    monkeypatch,
) -> None:
    client, _manager, _active = isolated_api
    monkeypatch.setattr(artifacts_api, "get_audit_store", lambda: _FailingAudit())

    response = client.post(
        "/api/v1/artifacts",
        json={"name": "must-not-remain", "type": "html", "content": "private"},
    )

    assert response.status_code == 503
    assert response.json()["message"] == "Artifact creation could not be audited."
    assert "PRIVATE_AUDIT_FAILURE" not in response.text
    assert client.get("/api/v1/artifacts").json()["artifacts"] == []
