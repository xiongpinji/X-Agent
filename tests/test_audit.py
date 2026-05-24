import json

from fastapi.testclient import TestClient

from backend.app.core.audit import AuditLogRecord, AuditStore
from backend.app.main import app


def test_audit_store_persists_records(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    store = AuditStore(storage_path=path)

    store.record(
        action="agent.run",
        resource_type="agent",
        resource_id="agent-1",
        actor_id="user-1",
        tenant_id="tenant-1",
        outcome="completed",
    )

    reloaded = AuditStore(storage_path=path)
    records = reloaded.list(actor_id="user-1")

    assert reloaded.count() == 1
    assert records[0].action == "agent.run"
    assert records[0].resource_id == "agent-1"
    assert records[0].hash is not None
    assert reloaded.verify_chain().valid is True


def test_audit_hmac_signature_detects_rehashed_tampering(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    store = AuditStore(storage_path=path, hmac_secret="audit-secret")
    record = store.record(
        action="agent.run",
        resource_type="agent",
        actor_id="user-1",
        outcome="completed",
    )

    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    payload["outcome"] = "tampered"
    payload["hash"] = AuditStore._hash_record(AuditLogRecord.model_validate(payload))
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    reloaded = AuditStore(storage_path=path, hmac_secret="audit-secret")
    verification = reloaded.verify_chain()

    assert record.signature is not None
    assert verification.valid is False
    assert verification.signature_valid is False
    assert verification.reason == "Record signature mismatch."


def test_agent_run_writes_audit_log() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    run = client.post("/api/v1/agents/run", json={"task": "audit check"}).json()

    response = client.get(
        "/api/v1/audit-logs",
        params={"action": "agent.run", "limit": 10, "has_snapshot": True},
    )

    assert response.status_code == 200
    assert any(item["trace_id"] == run["trace_id"] for item in response.json())
    assert all(item["snapshot"] for item in response.json())


def test_audit_chain_verify_endpoint() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    client.post("/api/v1/agents/run", json={"task": "verify audit"})

    response = client.get("/api/v1/audit-logs/verify")

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["checked"] >= 1


def test_workflow_run_writes_audit_log() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    workflow = client.post(
        "/api/v1/workflows",
        json={
            "name": "Audit workflow",
            "nodes": [
                {"id": "input_1", "type": "input", "config": {"key": "name"}},
                {"id": "output_1", "type": "output", "config": {"from": "input_1"}},
            ],
            "edges": [{"source": "input_1", "target": "output_1"}],
        },
    ).json()
    run = client.post(
        f"/api/v1/workflows/{workflow['id']}/run",
        json={"inputs": {"name": "audit"}},
    ).json()

    response = client.get("/api/v1/audit-logs", params={"action": "workflow.run", "limit": 10})

    assert response.status_code == 200
    assert any(item["run_id"] == run["run_id"] for item in response.json())
