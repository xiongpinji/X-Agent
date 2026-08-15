from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import Iterator
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import agents as agents_api
from backend.app.api import artifacts as artifacts_api
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core import run_artifacts as run_artifacts_core
from backend.app.core.artifacts import ArtifactStorage
from backend.app.core.artifacts import storage as artifact_storage_core
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


class _NoIdAudit:
    def record(self, **_kwargs) -> None:
        return None


class _RollbackFailingAudit:
    def __init__(self, delegate: AuditStore, mode: str) -> None:
        self.delegate = delegate
        self.mode = mode

    def record(self, **kwargs):
        if kwargs.get("action") == "run.archive.rollback":
            if self.mode == "none":
                return None
            raise RuntimeError("PRIVATE_ROLLBACK_AUDIT_FAILURE")
        return self.delegate.record(**kwargs)


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
    client, manager, audit = lifecycle
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
    audit_ids_before_repeat = list(persisted["audit_ids"])
    first_archive_bytes = asyncio.run(
        manager.archive_bytes(
            archive["archive_id"],
            "tenant-a",
            "user-a",
        )
    )[1]
    repeated = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")
    assert repeated.status_code == 200
    assert repeated.json()["archive"]["archive_id"] == archive["archive_id"]
    assert repeated.json()["archive"]["archive_sha256"] == archive["archive_sha256"]
    repeated_manifest = client.get(
        "/api/v1/artifacts/runs/run-lifecycle/manifest"
    ).json()
    assert repeated_manifest["audit_ids"] == audit_ids_before_repeat
    second_archive_bytes = asyncio.run(
        manager.archive_bytes(
            archive["archive_id"],
            "tenant-a",
            "user-a",
        )
    )[1]
    assert second_archive_bytes == first_archive_bytes

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
        "artifact.download.requested",
        "run.archive.created",
        "run.archive.download.requested",
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
    assert sum(record.action == "run.archive.created" for record in records) == 1


def test_concurrent_archive_creation_converges_on_one_archive(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    second_manager = RunArtifactManager(
        manager.root_path,
        artifact_storage=ArtifactStorage(manager.artifact_storage.storage_path),
    )

    async def _record_created(manifest) -> str:
        assert manifest.archive is not None
        record = await asyncio.to_thread(
            audit.record,
            action="run.archive.created",
            resource_type="run_archive",
            resource_id=manifest.archive.archive_id,
            tenant_id="tenant-a",
            actor_id="user-a",
            trace_id=manifest.trace_id,
            run_id=manifest.run_id,
            details={"status": "created", "size_bytes": manifest.archive.size_bytes},
        )
        return str(record.id)

    async def _record_rollback(manifest, created_audit_id: str) -> str:
        assert manifest.archive is not None
        record = await asyncio.to_thread(
            audit.record,
            action="run.archive.rollback",
            resource_type="run_archive",
            resource_id=manifest.archive.archive_id,
            tenant_id="tenant-a",
            actor_id="user-a",
            outcome="failure",
            trace_id=manifest.trace_id,
            run_id=manifest.run_id,
            details={
                "status": "rolled_back",
                "created_audit_id": created_audit_id,
            },
        )
        return str(record.id)

    async def _create_both():
        return await asyncio.gather(
            manager.create_archive(
                final["trace_id"],
                "tenant-a",
                "user-a",
                audit_callback=_record_created,
                rollback_audit_callback=_record_rollback,
            ),
            second_manager.create_archive(
                final["trace_id"],
                "tenant-a",
                "user-a",
                audit_callback=_record_created,
                rollback_audit_callback=_record_rollback,
            ),
        )

    first, second = asyncio.run(_create_both())

    assert first is not None
    assert second is not None
    first_manifest, first_created = first
    second_manifest, second_created = second
    assert sorted((first_created, second_created)) == [False, True]
    assert first_manifest.archive is not None
    assert second_manifest.archive is not None
    assert first_manifest.archive.archive_id == second_manifest.archive.archive_id
    assert first_manifest.archive.archive_sha256 == second_manifest.archive.archive_sha256
    assert len(list(manager.archive_path.rglob("*.zip"))) == 1
    persisted = asyncio.run(
        manager.get_manifest(final["trace_id"], "tenant-a", "user-a")
    )
    assert persisted is not None
    assert persisted.archive == first_manifest.archive
    first_bytes = asyncio.run(
        manager.archive_bytes(
            first_manifest.archive.archive_id,
            "tenant-a",
            "user-a",
        )
    )
    second_bytes = asyncio.run(
        second_manager.archive_bytes(
            second_manifest.archive.archive_id,
            "tenant-a",
            "user-a",
        )
    )
    assert first_bytes is not None
    assert second_bytes is not None
    assert first_bytes[1] == second_bytes[1]
    created_records = audit.list(
        limit=100,
        tenant_id="tenant-a",
        actor_id="user-a",
        action="run.archive.created",
    )
    assert len(created_records) == 1
    assert created_records[0].id in persisted.audit_ids


def test_concurrent_audit_id_updates_merge_from_authoritative_manifest(
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
    second_manager = RunArtifactManager(
        manager.root_path,
        artifact_storage=ArtifactStorage(manager.artifact_storage.storage_path),
    )
    stale_one = asyncio.run(
        manager.get_manifest(final["trace_id"], "tenant-a", "user-a")
    )
    stale_two = asyncio.run(
        second_manager.get_manifest(final["trace_id"], "tenant-a", "user-a")
    )
    assert stale_one is not None
    assert stale_two is not None

    async def _merge_both() -> None:
        await asyncio.gather(
            manager.add_audit_id(stale_one, "concurrent-audit-one"),
            second_manager.add_audit_id(stale_two, "concurrent-audit-two"),
        )

    asyncio.run(_merge_both())

    persisted = asyncio.run(
        manager.get_manifest(final["trace_id"], "tenant-a", "user-a")
    )
    assert persisted is not None
    assert {"concurrent-audit-one", "concurrent-audit-two"}.issubset(
        persisted.audit_ids
    )


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
    assert final["persistence_status"] == "persisted"
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


def test_failed_stream_does_not_claim_manifest_when_persistence_fails(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _FailingAgent())

    async def _fail_save(_manifest):
        raise OSError("PRIVATE_PERSISTENCE_FAILURE")

    monkeypatch.setattr(manager, "save_manifest", _fail_save)
    response = client.post("/api/v1/agents/run/stream", json={"task": "fail safely"})

    assert response.status_code == 200
    assert "PRIVATE_PERSISTENCE_FAILURE" not in response.text
    final = _final(response.text)
    assert final["status"] == "failed"
    assert final["manifest"] is None
    assert final["persistence_status"] == "failed"
    assert asyncio.run(
        RunArtifactManager.get_manifest(
            manager,
            final["trace_id"],
            "tenant-a",
            "user-a",
        )
    ) is None


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


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("trace_id", "different-trace"),
        ("status", "running"),
        ("run_id", "different-run"),
        ("tenant_id", "tenant-b"),
        ("user_id", "user-b"),
    ],
)
def test_manifest_reads_and_archives_reject_tampered_invariants(
    lifecycle,
    monkeypatch,
    field,
    replacement,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    archive = client.post(
        "/api/v1/artifacts/runs/run-lifecycle/archive"
    ).json()["archive"]
    manifest_file = next(manager.manifest_path.rglob("run-lifecycle.json"))
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    payload[field] = replacement
    manifest_file.write_text(json.dumps(payload), encoding="utf-8")

    assert client.get("/api/v1/artifacts/runs/run-lifecycle/manifest").status_code == 404
    assert client.post("/api/v1/artifacts/runs/run-lifecycle/archive").status_code == 404
    assert client.get(
        f"/api/v1/artifacts/archives/{archive['archive_id']}/download"
    ).status_code == 404
    assert asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    ) is None
    assert asyncio.run(
        manager.archive_bytes(
            archive["archive_id"],
            "tenant-a",
            "user-a",
        )
    ) is None


def test_archive_audit_failure_releases_lock_rolls_back_and_allows_retry(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
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
    assert list(manager.lock_path.rglob("*.lock")) == []

    monkeypatch.setattr(artifacts_api, "get_audit_store", lambda: audit)
    retry = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert retry.status_code == 200
    assert len(list(manager.archive_path.rglob("*.zip"))) == 1
    assert list(manager.lock_path.rglob("*.lock")) == []
    created_records = audit.list(
        limit=100,
        tenant_id="tenant-a",
        actor_id="user-a",
        action="run.archive.created",
    )
    assert len(created_records) == 1


def test_archive_manifest_commit_failure_records_compensating_audit(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    baseline_ids = set(final["manifest"]["audit_ids"])
    original_save = manager._save_manifest_unlocked

    async def _fail_after_created_audit(manifest):
        if manifest.archive is not None and set(manifest.audit_ids) - baseline_ids:
            raise OSError("PRIVATE_FINAL_MANIFEST_FAILURE")
        return await original_save(manifest)

    monkeypatch.setattr(manager, "_save_manifest_unlocked", _fail_after_created_audit)
    response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert response.status_code == 503
    assert "PRIVATE_FINAL_MANIFEST_FAILURE" not in response.text
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []
    persisted = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert persisted is not None
    assert persisted.archive is None
    records = audit.list(limit=100, tenant_id="tenant-a", actor_id="user-a")
    created = [record for record in records if record.action == "run.archive.created"]
    rolled_back = [record for record in records if record.action == "run.archive.rollback"]
    assert len(created) == 1
    assert len(rolled_back) == 1
    assert rolled_back[0].outcome == "failure"
    assert rolled_back[0].details["created_audit_id"] == created[0].id
    assert {created[0].id, rolled_back[0].id}.issubset(persisted.audit_ids)


def test_archive_cancellation_during_audit_rolls_back_without_created_audit(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )

    async def _cancel_during_audit() -> None:
        audit_started = asyncio.Event()
        never_finish = asyncio.Event()
        staged_archive_id: str | None = None

        async def _blocked_created_audit(manifest) -> str:
            nonlocal staged_archive_id
            assert manifest.archive is not None
            staged_archive_id = manifest.archive.archive_id
            audit_started.set()
            await never_finish.wait()
            raise AssertionError("unreachable")

        async def _unexpected_rollback_audit(_manifest, _created_id) -> str:
            raise AssertionError("created audit id does not exist")

        task = asyncio.create_task(
            manager.create_archive(
                "run-lifecycle",
                "tenant-a",
                "user-a",
                audit_callback=_blocked_created_audit,
                rollback_audit_callback=_unexpected_rollback_audit,
            )
        )
        await asyncio.wait_for(audit_started.wait(), timeout=2)
        published = await manager.get_manifest(
            "run-lifecycle",
            "tenant-a",
            "user-a",
        )
        assert published is not None
        published_archive = published.archive
        assert staged_archive_id is not None
        staged_download = client.get(
            f"/api/v1/artifacts/archives/{staged_archive_id}/download"
        )
        staged_download_status = staged_download.status_code
        assert len(list(manager.archive_path.rglob("*.zip"))) == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert published_archive is None
        assert staged_download_status == 404

    asyncio.run(_cancel_during_audit())

    authoritative = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert authoritative is not None
    assert authoritative.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []
    assert audit.list(
        limit=100,
        tenant_id="tenant-a",
        actor_id="user-a",
        action="run.archive.created",
    ) == []


def test_archive_cancellation_after_created_audit_records_rollback(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    baseline_ids = set(final["manifest"]["audit_ids"])

    async def _cancel_during_audit_id_commit() -> None:
        final_save_started = asyncio.Event()
        never_finish = asyncio.Event()
        original_save = manager._save_manifest_unlocked

        async def _controlled_save(manifest):
            if manifest.archive is not None and set(manifest.audit_ids) - baseline_ids:
                final_save_started.set()
                await never_finish.wait()
            return await original_save(manifest)

        async def _record_created(manifest) -> str:
            assert manifest.archive is not None
            record = await asyncio.to_thread(
                audit.record,
                action="run.archive.created",
                resource_type="run_archive",
                resource_id=manifest.archive.archive_id,
                tenant_id="tenant-a",
                actor_id="user-a",
                trace_id=manifest.trace_id,
                run_id=manifest.run_id,
                details={"status": "created"},
            )
            return str(record.id)

        async def _record_rollback(manifest, created_audit_id: str) -> str:
            assert manifest.archive is not None
            record = await asyncio.to_thread(
                audit.record,
                action="run.archive.rollback",
                resource_type="run_archive",
                resource_id=manifest.archive.archive_id,
                tenant_id="tenant-a",
                actor_id="user-a",
                outcome="failure",
                trace_id=manifest.trace_id,
                run_id=manifest.run_id,
                details={
                    "status": "rolled_back",
                    "created_audit_id": created_audit_id,
                },
            )
            return str(record.id)

        monkeypatch.setattr(manager, "_save_manifest_unlocked", _controlled_save)
        task = asyncio.create_task(
            manager.create_archive(
                "run-lifecycle",
                "tenant-a",
                "user-a",
                audit_callback=_record_created,
                rollback_audit_callback=_record_rollback,
            )
        )
        await asyncio.wait_for(final_save_started.wait(), timeout=2)
        published = await manager.get_manifest(
            "run-lifecycle",
            "tenant-a",
            "user-a",
        )
        assert published is not None
        assert published.archive is None
        assert len(list(manager.archive_path.rglob("*.zip"))) == 1

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)

    asyncio.run(_cancel_during_audit_id_commit())

    authoritative = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert authoritative is not None
    assert authoritative.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []
    records = audit.list(limit=100, tenant_id="tenant-a", actor_id="user-a")
    created = [record for record in records if record.action == "run.archive.created"]
    rolled_back = [record for record in records if record.action == "run.archive.rollback"]
    assert len(created) == 1
    assert len(rolled_back) == 1
    assert rolled_back[0].details["created_audit_id"] == created[0].id
    assert {created[0].id, rolled_back[0].id}.issubset(authoritative.audit_ids)


def test_archive_cancellation_during_inflight_zip_write_leaves_no_orphan(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    write_started = threading.Event()
    allow_write = threading.Event()
    write_finished = threading.Event()
    original_atomic_write = manager._atomic_write

    def _controlled_atomic_write(path: Path, content: bytes) -> None:
        if path.suffix == ".zip":
            write_started.set()
            if not allow_write.wait(timeout=2):
                raise TimeoutError("archive write test gate timed out")
        original_atomic_write(path, content)
        if path.suffix == ".zip":
            write_finished.set()

    async def _unexpected_created_audit(_manifest) -> str:
        raise AssertionError("archive cancellation must precede audit")

    async def _unexpected_rollback_audit(_manifest, _created_id) -> str:
        raise AssertionError("created audit id does not exist")

    monkeypatch.setattr(manager, "_atomic_write", _controlled_atomic_write)

    async def _cancel_inflight_write() -> bool:
        task = asyncio.create_task(
            manager.create_archive(
                "run-lifecycle",
                "tenant-a",
                "user-a",
                audit_callback=_unexpected_created_audit,
                rollback_audit_callback=_unexpected_rollback_audit,
            )
        )
        started = await asyncio.to_thread(write_started.wait, 2)
        assert started

        async def _allow_later() -> None:
            await asyncio.sleep(0.05)
            allow_write.set()

        allow_task = asyncio.create_task(_allow_later())
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        finished_before_exit = False
        try:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
            finished_before_exit = write_finished.is_set()
        finally:
            allow_write.set()
            await asyncio.wait_for(allow_task, timeout=2)
            finished = await asyncio.to_thread(write_finished.wait, 2)
            assert finished
        return finished_before_exit

    assert asyncio.run(_cancel_inflight_write()) is True
    authoritative = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert authoritative is not None
    assert authoritative.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []
    assert audit.list(
        limit=100,
        tenant_id="tenant-a",
        actor_id="user-a",
        action="run.archive.created",
    ) == []


def test_archive_cancellation_waits_for_inflight_manifest_write_before_rollback(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    write_started = threading.Event()
    allow_write = threading.Event()
    write_finished = threading.Event()
    original_atomic_write = manager._atomic_write

    def _controlled_atomic_write(path: Path, content: bytes) -> None:
        is_archive_manifest = (
            manager.manifest_path in path.parents
            and b'"archive": {' in content
        )
        if is_archive_manifest:
            write_started.set()
            if not allow_write.wait(timeout=2):
                raise TimeoutError("manifest write test gate timed out")
        original_atomic_write(path, content)
        if is_archive_manifest:
            write_finished.set()

    async def _record_created(manifest) -> str:
        assert manifest.archive is not None
        record = await asyncio.to_thread(
            audit.record,
            action="run.archive.created",
            resource_type="run_archive",
            resource_id=manifest.archive.archive_id,
            tenant_id="tenant-a",
            actor_id="user-a",
            trace_id=manifest.trace_id,
            run_id=manifest.run_id,
            details={"status": "created"},
        )
        return str(record.id)

    async def _record_rollback(manifest, created_audit_id: str) -> str:
        assert manifest.archive is not None
        record = await asyncio.to_thread(
            audit.record,
            action="run.archive.rollback",
            resource_type="run_archive",
            resource_id=manifest.archive.archive_id,
            tenant_id="tenant-a",
            actor_id="user-a",
            outcome="failure",
            trace_id=manifest.trace_id,
            run_id=manifest.run_id,
            details={"created_audit_id": created_audit_id},
        )
        return str(record.id)

    monkeypatch.setattr(manager, "_atomic_write", _controlled_atomic_write)

    async def _cancel_inflight_write() -> bool:
        task = asyncio.create_task(
            manager.create_archive(
                "run-lifecycle",
                "tenant-a",
                "user-a",
                audit_callback=_record_created,
                rollback_audit_callback=_record_rollback,
            )
        )
        started = await asyncio.to_thread(write_started.wait, 2)
        assert started

        async def _allow_later() -> None:
            await asyncio.sleep(0.05)
            allow_write.set()

        allow_task = asyncio.create_task(_allow_later())
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        finished_before_exit = False
        try:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
            finished_before_exit = write_finished.is_set()
        finally:
            allow_write.set()
            await asyncio.wait_for(allow_task, timeout=2)
            finished = await asyncio.to_thread(write_finished.wait, 2)
            assert finished
        return finished_before_exit

    assert asyncio.run(_cancel_inflight_write()) is True

    authoritative = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert authoritative is not None
    assert authoritative.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []


def test_archive_cancellation_surfaces_unlink_rollback_failure(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )

    async def _cancel_with_broken_unlink() -> None:
        audit_started = asyncio.Event()
        never_finish = asyncio.Event()

        async def _blocked_created_audit(_manifest) -> str:
            audit_started.set()
            await never_finish.wait()
            raise AssertionError("unreachable")

        async def _unexpected_rollback_audit(_manifest, _created_id) -> str:
            raise AssertionError("created audit id does not exist")

        def _fail_unlink(_path) -> None:
            raise OSError("PRIVATE_UNLINK_FAILURE")

        monkeypatch.setattr(manager, "_remove_file", _fail_unlink)
        task = asyncio.create_task(
            manager.create_archive(
                "run-lifecycle",
                "tenant-a",
                "user-a",
                audit_callback=_blocked_created_audit,
                rollback_audit_callback=_unexpected_rollback_audit,
            )
        )
        await asyncio.wait_for(audit_started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(RuntimeError) as failure:
            await asyncio.wait_for(task, timeout=2)
        assert type(failure.value).__name__ == "RunArtifactRollbackError"
        assert isinstance(failure.value.__cause__, OSError)
        assert "PRIVATE_UNLINK_FAILURE" not in str(failure.value)

    asyncio.run(_cancel_with_broken_unlink())

    authoritative = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert authoritative is not None
    assert authoritative.archive is None
    assert len(list(manager.archive_path.rglob("*.zip"))) == 1
    assert list(manager.lock_path.rglob("*.lock")) == []


def test_archive_manifest_cleanup_failure_is_a_distinct_stable_api_error(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    original_save = manager._save_manifest_unlocked
    save_calls = 0

    async def _fail_manifest_cleanup(manifest):
        nonlocal save_calls
        save_calls += 1
        if save_calls == 1:
            await original_save(manifest)
            raise OSError("PRIVATE_ARCHIVE_PUBLISH_ACK_FAILURE")
        if save_calls == 2:
            raise OSError("PRIVATE_MANIFEST_CLEANUP_FAILURE")
        return await original_save(manifest)

    monkeypatch.setattr(manager, "_save_manifest_unlocked", _fail_manifest_cleanup)

    async def _request_archive():
        return await asyncio.wait_for(
            asyncio.to_thread(
                client.post,
                "/api/v1/artifacts/runs/run-lifecycle/archive",
            ),
            timeout=2,
        )

    response = asyncio.run(_request_archive())

    assert response.status_code == 503
    assert response.json()["message"] == "Run archive rollback could not be completed."
    assert "PRIVATE_MANIFEST_CLEANUP_FAILURE" not in response.text
    authoritative = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert authoritative is not None
    assert authoritative.archive is not None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []


def test_archive_download_handles_file_disappearing_before_read(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    archive = client.post(
        "/api/v1/artifacts/runs/run-lifecycle/archive"
    ).json()["archive"]
    archive_file = manager._archive_file(
        archive["archive_id"],
        "tenant-a",
        "user-a",
    )
    original_read_bytes = Path.read_bytes

    def _vanish_before_read(path: Path) -> bytes:
        if path == archive_file:
            path.unlink()
            raise FileNotFoundError("PRIVATE_ARCHIVE_RACE")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", _vanish_before_read)

    response = client.get(
        f"/api/v1/artifacts/archives/{archive['archive_id']}/download"
    )

    assert response.status_code == 404
    assert "PRIVATE_ARCHIVE_RACE" not in response.text
    assert list(manager.lock_path.rglob("*.lock")) == []


def test_archive_lock_release_failure_returns_stable_503(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    lock_file = manager._lock_file("run-lifecycle", "tenant-a", "user-a")
    original_unlink = Path.unlink

    def _fail_owned_lock_unlink(path: Path, *args, **kwargs) -> None:
        if path == lock_file:
            raise OSError("PRIVATE_LOCK_RELEASE_FAILURE")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _fail_owned_lock_unlink)
    try:
        response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

        assert response.status_code == 503
        assert response.json()["message"] == "Run artifact lock could not be released."
        assert "PRIVATE_LOCK_RELEASE_FAILURE" not in response.text
        assert lock_file.is_file()
    finally:
        if lock_file.exists():
            original_unlink(lock_file)


@pytest.mark.parametrize(
    ("payload", "token"),
    [
        ("not-json", "owned-token"),
        (json.dumps({"token": "different-token"}), "owned-token"),
    ],
)
def test_lock_release_rejects_corrupt_or_unowned_lock(
    tmp_path,
    payload,
    token,
) -> None:
    manager = RunArtifactManager(tmp_path / "invalid-release-lock")
    lock_file = manager._lock_file("release-check", "tenant-a", "user-a")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(payload, encoding="utf-8")

    with pytest.raises(RuntimeError) as failure:
        manager._release_lock(lock_file, token)

    assert type(failure.value).__name__ == "RunArtifactLockError"
    assert lock_file.is_file()


def test_archive_download_lock_timeout_returns_stable_503(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    archive = client.post(
        "/api/v1/artifacts/runs/run-lifecycle/archive"
    ).json()["archive"]
    lock_file = manager._lock_file("run-lifecycle", "tenant-a", "user-a")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(
        json.dumps({"token": "other-worker", "pid": os.getpid()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_artifacts_core, "_LOCK_TIMEOUT_SECONDS", 0.02)
    try:
        response = client.get(
            f"/api/v1/artifacts/archives/{archive['archive_id']}/download"
        )

        assert response.status_code == 503
        assert response.json()["message"] == "Run artifact lock is temporarily unavailable."
    finally:
        lock_file.unlink(missing_ok=True)


def test_double_cancellation_waits_for_lock_release(tmp_path, monkeypatch) -> None:
    manager = RunArtifactManager(tmp_path / "double-cancel-run")
    manifest = manager.failed_manifest(
        run_id="double-cancel",
        tenant_id="tenant-a",
        user_id="user-a",
        error_code="cancelled",
        audit_ids=[],
    )
    lock_file = manager._lock_file("double-cancel", "tenant-a", "user-a")
    release_started = threading.Event()
    allow_release = threading.Event()
    release_finished = threading.Event()
    original_release = manager._release_lock

    def _controlled_release(path: Path, token: str) -> None:
        release_started.set()
        if not allow_release.wait(timeout=2):
            raise TimeoutError("release test gate timed out")
        original_release(path, token)
        release_finished.set()

    monkeypatch.setattr(manager, "_release_lock", _controlled_release)

    async def _cancel_twice() -> bool:
        task = asyncio.create_task(manager.save_manifest(manifest))
        started = await asyncio.to_thread(release_started.wait, 2)
        assert started

        async def _allow_later() -> None:
            await asyncio.sleep(0.05)
            allow_release.set()

        allow_task = asyncio.create_task(_allow_later())
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        completed_release_before_exit = False
        try:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
            completed_release_before_exit = release_finished.is_set()
        finally:
            allow_release.set()
            await asyncio.wait_for(allow_task, timeout=2)
            finished = await asyncio.to_thread(release_finished.wait, 2)
            assert finished
        return completed_release_before_exit

    assert asyncio.run(_cancel_twice()) is True
    assert not lock_file.exists()


@pytest.mark.parametrize("rollback_mode", ["raise", "none"])
def test_archive_rollback_audit_failure_is_not_hidden(
    lifecycle,
    monkeypatch,
    rollback_mode,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    baseline_ids = set(final["manifest"]["audit_ids"])
    original_save = manager._save_manifest_unlocked

    async def _fail_publish_after_created_audit(manifest):
        if manifest.archive is not None and set(manifest.audit_ids) - baseline_ids:
            raise OSError("PRIVATE_ARCHIVE_PUBLISH_FAILURE")
        return await original_save(manifest)

    monkeypatch.setattr(
        manager,
        "_save_manifest_unlocked",
        _fail_publish_after_created_audit,
    )
    monkeypatch.setattr(
        artifacts_api,
        "get_audit_store",
        lambda: _RollbackFailingAudit(audit, rollback_mode),
    )

    response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert response.status_code == 503
    assert response.json()["message"] == "Run archive rollback could not be completed."
    assert "PRIVATE_" not in response.text
    persisted = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert persisted is not None
    assert persisted.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []


def test_archive_rollback_audit_id_merge_failure_is_not_hidden(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    baseline_ids = set(final["manifest"]["audit_ids"])
    original_save = manager._save_manifest_unlocked
    publish_failed = False

    async def _fail_publish_and_rollback_merge(manifest):
        nonlocal publish_failed
        new_ids = set(manifest.audit_ids) - baseline_ids
        if manifest.archive is not None and new_ids and not publish_failed:
            publish_failed = True
            raise OSError("PRIVATE_ARCHIVE_PUBLISH_FAILURE")
        if publish_failed and manifest.archive is None and len(new_ids) >= 2:
            raise OSError("PRIVATE_ROLLBACK_AUDIT_MERGE_FAILURE")
        return await original_save(manifest)

    monkeypatch.setattr(
        manager,
        "_save_manifest_unlocked",
        _fail_publish_and_rollback_merge,
    )

    response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert response.status_code == 503
    assert response.json()["message"] == "Run archive rollback could not be completed."
    assert "PRIVATE_" not in response.text
    persisted = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert persisted is not None
    assert persisted.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []
    actions = [
        record.action
        for record in audit.list(limit=100, tenant_id="tenant-a", actor_id="user-a")
    ]
    assert "run.archive.created" in actions
    assert "run.archive.rollback" in actions


def test_artifact_create_and_update_reject_content_over_limits(
    lifecycle,
    monkeypatch,
) -> None:
    client, _manager, _audit = lifecycle
    monkeypatch.setattr(
        artifact_storage_core,
        "MAX_ARTIFACT_CONTENT_CHARS",
        4,
        raising=False,
    )
    monkeypatch.setattr(
        artifact_storage_core,
        "MAX_ARTIFACT_CONTENT_BYTES",
        5,
        raising=False,
    )

    accepted = client.post(
        "/api/v1/artifacts",
        json={"name": "small.txt", "type": "text", "content": "1234"},
    )
    too_many_chars = client.post(
        "/api/v1/artifacts",
        json={"name": "chars.txt", "type": "text", "content": "12345"},
    )
    too_many_bytes = client.put(
        f"/api/v1/artifacts/{accepted.json()['id']}",
        json={"content": "你你"},
    )

    assert accepted.status_code == 201
    assert too_many_chars.status_code == 422
    assert too_many_bytes.status_code == 422
    persisted = client.get(f"/api/v1/artifacts/{accepted.json()['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["content"] == "1234"


@pytest.mark.parametrize(
    "limit_name",
    [
        "MAX_ARCHIVE_ARTIFACTS",
        "MAX_ARCHIVE_CONTENT_BYTES",
        "MAX_ARCHIVE_BYTES",
    ],
)
def test_archive_resource_limits_fail_closed(
    lifecycle,
    monkeypatch,
    limit_name,
) -> None:
    client, manager, _audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    artifact_size = final["manifest"]["artifacts"][0]["size_bytes"]
    limit = 0 if limit_name == "MAX_ARCHIVE_ARTIFACTS" else artifact_size - 1
    if limit_name == "MAX_ARCHIVE_BYTES":
        limit = 1
    monkeypatch.setattr(run_artifacts_core, limit_name, limit, raising=False)

    response = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")

    assert response.status_code == 409
    assert response.json()["message"] == "Run archive integrity check failed."
    persisted = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert persisted is not None
    assert persisted.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []


def test_artifact_download_audit_failure_never_claims_downloaded_or_returns_bytes(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    final = _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    artifact_id = final["manifest"]["artifacts"][0]["artifact_id"]

    async def _fail_manifest_update(_manifest, _audit_id):
        raise OSError("PRIVATE_MANIFEST_FAILURE")

    monkeypatch.setattr(manager, "add_audit_id", _fail_manifest_update)
    response = client.get(f"/api/v1/artifacts/{artifact_id}/download")

    assert response.status_code == 503
    assert b"<!doctype html>" not in response.content
    assert "PRIVATE_MANIFEST_FAILURE" not in response.text
    actions = [
        record.action
        for record in audit.list(limit=100, tenant_id="tenant-a", actor_id="user-a")
    ]
    assert "artifact.downloaded" not in actions
    assert "artifact.download.requested" in actions
    assert "artifact.download.manifest_failed" in actions


def test_archive_download_audit_failure_never_claims_downloaded_or_returns_bytes(
    lifecycle,
    monkeypatch,
) -> None:
    client, manager, audit = lifecycle
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    _final(
        client.post(
            "/api/v1/agents/run/stream",
            json={"task": "create a result"},
        ).text
    )
    archive = client.post(
        "/api/v1/artifacts/runs/run-lifecycle/archive"
    ).json()["archive"]

    async def _fail_manifest_update(_manifest, _audit_id):
        raise OSError("PRIVATE_ARCHIVE_MANIFEST_FAILURE")

    monkeypatch.setattr(manager, "add_audit_id", _fail_manifest_update)
    response = client.get(
        f"/api/v1/artifacts/archives/{archive['archive_id']}/download"
    )

    assert response.status_code == 503
    assert response.content != asyncio.run(
        manager.archive_bytes(
            archive["archive_id"],
            "tenant-a",
            "user-a",
        )
    )[1]
    assert "PRIVATE_ARCHIVE_MANIFEST_FAILURE" not in response.text
    actions = [
        record.action
        for record in audit.list(limit=100, tenant_id="tenant-a", actor_id="user-a")
    ]
    assert "run.archive.downloaded" not in actions
    assert "run.archive.download.requested" in actions
    assert "run.archive.download.manifest_failed" in actions


def test_missing_audit_ids_fail_closed_for_create_archive_and_download(
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
    monkeypatch.setattr(artifacts_api, "get_audit_store", lambda: _NoIdAudit())

    archive = client.post("/api/v1/artifacts/runs/run-lifecycle/archive")
    artifact_download = client.get(f"/api/v1/artifacts/{artifact_id}/download")
    created = client.post(
        "/api/v1/artifacts",
        json={"name": "no-audit.html", "type": "html", "content": "private"},
    )

    assert archive.status_code == 503
    assert artifact_download.status_code == 503
    assert b"<!doctype html>" not in artifact_download.content
    assert created.status_code == 503
    persisted = asyncio.run(
        manager.get_manifest("run-lifecycle", "tenant-a", "user-a")
    )
    assert persisted is not None
    assert persisted.archive is None
    assert list(manager.archive_path.rglob("*.zip")) == []
    assert list(manager.lock_path.rglob("*.lock")) == []
    assert client.get("/api/v1/artifacts").json()["count"] == 1


def test_stale_dead_process_lock_is_recovered_under_valid_tmp_root(tmp_path) -> None:
    manager = RunArtifactManager(tmp_path / "valid-run-root")
    manifest = manager.failed_manifest(
        run_id="stale-lock-run",
        tenant_id="tenant-a",
        user_id="user-a",
        error_code="agent_execution_failed",
        audit_ids=[],
    )
    asyncio.run(manager.save_manifest(manifest))
    lock_file = manager._lock_file("stale-lock-run", "tenant-a", "user-a")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(
        json.dumps({"token": "orphan", "pid": 2_147_483_647}),
        encoding="utf-8",
    )
    os.utime(lock_file, (0, 0))

    updated = asyncio.run(manager.add_audit_id(manifest, "recovered-audit"))

    assert updated.audit_ids == ["recovered-audit"]
    assert list(manager.lock_path.rglob("*.lock")) == []


def test_artifact_routes_are_mounted_and_reachable_in_production_app(
    tmp_path,
) -> None:
    from backend.app import main as main_module

    app = main_module.app
    original_routes = list(app.router.routes)
    original_startup_handlers = list(app.router.on_startup)
    original_routers_registered = main_module._routers_registered
    original_openapi_schema = app.openapi_schema

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

    async def _forbid_lifespan_startup() -> None:
        raise AssertionError("main route acceptance must not run application startup")

    app.router.on_startup.insert(0, _forbid_lifespan_startup)
    try:
        main_module._register_all_routers()
        app.openapi_schema = None
        client = TestClient(app)
        try:
            paths = app.openapi()["paths"]
            assert "/api/v1/artifacts/runs/{run_id}/manifest" in paths
            assert "/api/v1/artifacts/runs/{run_id}/archive" in paths
            assert "/api/v1/artifacts/{artifact_id}/download" in paths
            assert "/api/v1/artifacts/archives/{archive_id}/download" in paths
            response = client.get(
                "/api/v1/artifacts/runs/mounted-run/manifest",
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["run_id"] == "mounted-run"
            assert payload["tenant_id"] == "tenant-a"
            assert payload["user_id"] == "user-a"
            stats = client.get(
                "/api/v1/artifacts/stats",
                headers={"Authorization": "Bearer test-token"},
            )
            assert stats.status_code == 200
            assert stats.json()["total_artifacts"] == 0
            assert "storage_path" not in stats.json()
        finally:
            client.close()
    finally:
        app.router.on_startup.remove(_forbid_lifespan_startup)
        app.dependency_overrides.pop(get_current_principal, None)
        app.dependency_overrides.pop(get_run_artifact_manager, None)
        app.router.routes[:] = original_routes
        main_module._routers_registered = original_routers_registered
        app.openapi_schema = original_openapi_schema

    assert app.router.routes == original_routes
    assert app.router.on_startup == original_startup_handlers
    assert main_module._routers_registered is original_routers_registered
    assert app.openapi_schema is original_openapi_schema
