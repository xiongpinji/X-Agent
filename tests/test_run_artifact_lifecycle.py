from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import agents as agents_api
from backend.app.api import artifacts as artifacts_api
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.artifacts import ArtifactStorage
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import AgentRunResponse, RunStatus
from backend.app.core.run_artifacts import RunArtifactManager, get_run_artifact_manager
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal


class _CompletingAgent:
    max_iterations = 20

    async def run(self, context, task, extra_context, event_callback=None) -> AgentRunResponse:
        return AgentRunResponse(
            trace_id="run-lifecycle",
            agent_id=context.agent_id,
            status=RunStatus.COMPLETED,
            answer="<script>alert('xss')</script> useful answer",
            iterations=1,
            memory_hits=0,
        )


class _FailingAgent:
    max_iterations = 20

    async def run(self, context, task, extra_context, event_callback=None) -> AgentRunResponse:
        raise RuntimeError("PRIVATE_PROVIDER_FAILURE")


class _FailingAudit:
    def record(self, **_kwargs) -> None:
        raise RuntimeError("PRIVATE_AUDIT_FAILURE")


def _principal() -> Principal:
    return Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=list(ROLE_SCOPES["user"]),
        authenticated=True,
    )


def _final(response_text: str) -> dict:
    for block in response_text.split("\n\n"):
        if "event: completed" in block:
            data = "".join(
                line.removeprefix("data: ")
                for line in block.splitlines()
                if line.startswith("data: ")
            )
            return json.loads(data)["result"]
    raise AssertionError("missing completed SSE frame")


@pytest.fixture
def lifecycle(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, RunArtifactManager, AuditStore]]:
    storage = ArtifactStorage(tmp_path / "artifacts")
    manager = RunArtifactManager(tmp_path / "runs", artifact_storage=storage)
    audit = AuditStore(tmp_path / "audit.jsonl", hmac_secret="test-secret")
    test_app = FastAPI()
    test_app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    test_app.include_router(agents_api.router)
    test_app.include_router(artifacts_api.router)
    test_app.dependency_overrides[get_current_principal] = _principal
    test_app.dependency_overrides[get_run_artifact_manager] = lambda: manager
    monkeypatch.setattr(agents_api, "get_audit_store", lambda: audit)
    monkeypatch.setattr(artifacts_api, "get_audit_store", lambda: audit)
    with TestClient(test_app) as client:
        yield client, manager, audit


def test_successful_stream_closes_manifest_download_archive_and_audit(
    lifecycle, monkeypatch
) -> None:
    client, _manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())

    response = client.post(
        "/api/v1/agents/run/stream",
        json={"task": "create a result"},
    )
    assert response.status_code == 200
    final = _final(response.text)
    assert final["status"] == "completed"
    manifest = final["manifest"]
    assert manifest["run_id"] == manifest["trace_id"] == "run-lifecycle"
    assert manifest["tenant_id"] == "tenant-a"
    assert manifest["user_id"] == "user-a"
    assert manifest["status"] == "completed"
    assert manifest["archive"] is None
    assert len(manifest["artifacts"]) == 1

    manifest_response = client.get("/api/v1/artifacts/runs/run-lifecycle/manifest")
    assert manifest_response.status_code == 200
    artifact_id = manifest_response.json()["artifacts"][0]["artifact_id"]

    artifact_response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert artifact_response.status_code == 200
    artifact = artifact_response.json()
    assert artifact["run_id"] == artifact["trace_id"] == "run-lifecycle"
    assert artifact["tenant_id"] == "tenant-a"
    assert artifact["user_id"] == "user-a"
    assert artifact["content_sha256"] == sha256(
        artifact["content"].encode("utf-8")
    ).hexdigest()
    assert "<script>" not in artifact["content"]
    assert "&lt;script&gt;" in artifact["content"]

    render_response = client.get(f"/api/v1/artifacts/{artifact_id}/render")
    assert render_response.status_code == 200
    assert render_response.json()["html"] == artifact["content"]

    download = client.get(f"/api/v1/artifacts/{artifact_id}/download")
    assert download.status_code == 200
    assert sha256(download.content).hexdigest() == artifact["content_sha256"]
    assert "\r" not in download.headers["content-disposition"]
    assert "\n" not in download.headers["content-disposition"]

    archive_response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")
    assert archive_response.status_code == 200
    archive = archive_response.json()["archive"]
    assert archive["archive_sha256"]
    assert archive["size_bytes"] > 0
    persisted = client.get("/api/v1/artifacts/runs/run-lifecycle/manifest").json()
    assert persisted["archive"]["archive_id"] == archive["archive_id"]
    repeated = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")
    assert repeated.status_code == 200
    assert repeated.json()["archive"]["archive_id"] == archive["archive_id"]

    archive_download = client.get(
        f"/api/v1/artifacts/archives/{archive['archive_id']}/download"
    )
    assert archive_download.status_code == 200
    assert sha256(archive_download.content).hexdigest() == archive["archive_sha256"]
    with ZipFile(BytesIO(archive_download.content)) as bundle:
        assert set(bundle.namelist()) == {
            "manifest.json",
            f"artifacts/{artifact_id}.html",
        }
        bundled_manifest = json.loads(bundle.read("manifest.json"))
        assert [item["artifact_id"] for item in bundled_manifest["artifacts"]] == [
            artifact_id
        ]

    records = audit.list(limit=100, tenant_id="tenant-a", actor_id="user-a")
    actions = {record.action for record in records}
    assert {
        "artifact.created",
        "agent.run.stream",
        "artifact.downloaded",
        "run.archive.created",
        "run.archive.downloaded",
    } <= actions
    scoped_records = [record for record in records if record.run_id == "run-lifecycle"]
    assert scoped_records
    assert all(record.trace_id == "run-lifecycle" for record in scoped_records)
    final_manifest = client.get(
        "/api/v1/artifacts/runs/run-lifecycle/manifest"
    ).json()
    assert set(final_manifest["audit_ids"]) == {
        record.id for record in scoped_records
    }


def test_failed_stream_persists_failed_manifest_without_artifact(
    lifecycle, monkeypatch
) -> None:
    client, _manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _FailingAgent())

    response = client.post("/api/v1/agents/run/stream", json={"task": "fail safely"})

    assert response.status_code == 200
    assert "PRIVATE_PROVIDER_FAILURE" not in response.text
    final = _final(response.text)
    assert final["status"] == "failed"
    assert final["manifest"]["status"] == "failed"
    assert final["manifest"]["artifacts"] == []
    assert final["manifest"]["error_code"] == "agent_execution_failed"
    manifest_response = client.get(
        f"/api/v1/artifacts/runs/{final['trace_id']}/manifest"
    )
    assert manifest_response.status_code == 200
    assert manifest_response.json() == final["manifest"]
    failures = audit.list(
        limit=10,
        tenant_id="tenant-a",
        actor_id="user-a",
        action="agent.run.stream",
        outcome="failure",
    )
    assert len(failures) == 1
    assert failures[0].run_id == failures[0].trace_id == final["trace_id"]


def test_archive_refuses_artifact_content_that_no_longer_matches_manifest(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    artifact_id = final["manifest"]["artifacts"][0]["artifact_id"]
    artifact_file = next(
        manager.artifact_storage.storage_path.rglob(f"{artifact_id}.json")
    )
    payload = json.loads(artifact_file.read_text(encoding="utf-8"))
    payload["content"] = "tampered after manifest creation"
    artifact_file.write_text(json.dumps(payload), encoding="utf-8")

    response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert response.status_code == 409
    assert response.json()["message"] == "Run archive integrity check failed."
    assert "tampered" not in response.text


def test_archive_is_rolled_back_when_required_audit_write_fails(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    monkeypatch.setattr(artifacts_api, "get_audit_store", lambda: _FailingAudit())

    response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert response.status_code == 503
    assert response.json()["message"] == "Run archive could not be audited."
    assert "PRIVATE_AUDIT_FAILURE" not in response.text
    manifest = asyncio.run(
        manager.get_manifest(
            final["trace_id"],
            "tenant-a",
            "user-a",
        )
    )
    assert manifest is not None
    assert manifest.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []


def test_artifact_routes_are_mounted_and_reachable_in_production_app(
    tmp_path,
) -> None:
    from backend.app.main import app

    manager = RunArtifactManager(
        tmp_path / "mounted-runs",
        artifact_storage=ArtifactStorage(tmp_path / "mounted-artifacts"),
    )
    manifest = manager.failed_manifest(
        run_id="mounted-run",
        tenant_id="tenant-a",
        user_id="user-a",
        error_code="agent_execution_failed",
        audit_ids=[],
    )
    asyncio.run(manager.save_manifest(manifest))
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[get_run_artifact_manager] = lambda: manager
    try:
        with TestClient(app) as client:
            paths = app.openapi()["paths"]
            assert "/api/v1/artifacts/runs/{run_id}/manifest" in paths
            assert "/api/v1/artifacts/{artifact_id}/download" in paths
            response = client.get(
                "/api/v1/artifacts/runs/mounted-run/manifest",
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == 200
            assert response.json()["run_id"] == "mounted-run"
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
        app.dependency_overrides.pop(get_run_artifact_manager, None)
