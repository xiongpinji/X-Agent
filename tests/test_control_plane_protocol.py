from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def _client() -> TestClient:
    return TestClient(app, headers={"x-api-key": "bootstrap"})


def test_control_plane_method_catalog_covers_p0_groups() -> None:
    response = _client().get("/api/v1/control-plane/methods")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "control_plane_contract_ready"
    assert payload["implementation_stage"] == "contract_first"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["safety"]["raw_secret_payloads_rejected"] is True
    assert payload["safety"]["mutation_performed"] is False

    groups = set(payload["method_groups"])
    assert {
        "thread",
        "turn",
        "tool",
        "approval",
        "plugin",
        "skill",
        "mcp",
        "channel",
        "runtime/evidence",
    }.issubset(groups)

    methods = {method["method"]: method for method in payload["methods"]}
    assert methods["thread/read"]["implementation_state"] == "read_only_contract"
    assert methods["tool/call"]["requires_approval"] is True
    assert methods["channel/send"]["requires_approval"] is True
    assert methods["runtime/evidence/read"]["operation_kind"] == "read"


def test_control_plane_read_method_returns_envelope_and_audit_evidence() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-thread-read",
            "method": "thread/read",
            "params": {"trace_id": "trace-demo"},
            "context": {
                "tenant_id": "default",
                "actor_id": "owner",
                "workspace_id": "workspace-demo",
                "trace_id": "trace-demo",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "req-thread-read"
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["evidence"]["trace_id"] == "trace-demo"
    assert payload["evidence"]["audit_id"]
    assert payload["result"]["method"] == "thread/read"
    assert payload["result"]["contract"]["mutation_performed"] is False
    assert payload["result"]["compatibility"]["thread_id"] == "trace-demo"


def test_control_plane_mutating_method_is_adapter_gated_without_mutation() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-tool-call",
            "method": "tool/call",
            "params": {"tool_name": "file_write", "arguments": {"path": "demo.txt"}},
            "context": {"trace_id": "trace-tool-call"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "approval_required"
    assert payload["error"]["retryable"] is True
    assert payload["error"]["details"]["requires_approval"] is True
    assert payload["error"]["details"]["mutation_performed"] is False
    assert payload["evidence"]["audit_id"]


def test_control_plane_rejects_raw_secret_payloads() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-secret",
            "method": "thread/read",
            "params": {"openai_api_key": "sk-test1234567890abcdef"},
            "context": {"trace_id": "trace-secret"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "raw_secret_payload_rejected"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["details"]["secret_paths"] == ["$.params.openai_api_key"]
    assert "sk-test" not in response.text


def test_control_plane_accepts_secret_references() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-secret-ref",
            "method": "runtime/evidence/read",
            "params": {
                "report_name": "latest-codex-alignment.json",
                "openai_api_key": "secret://openai/default",
            },
            "context": {"trace_id": "trace-secret-ref"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["method"] == "runtime/evidence/read"
    assert payload["result"]["contract"]["mutation_performed"] is False
    assert payload["result"]["evidence"]["report_name"] == "latest-codex-alignment.json"


def test_control_plane_unknown_method_uses_protocol_error_envelope() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-unknown",
            "method": "missing/method",
            "params": {},
            "context": {"trace_id": "trace-unknown"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "method_not_found"
    assert payload["evidence"]["trace_id"] == "trace-unknown"
    assert payload["evidence"]["audit_id"]
