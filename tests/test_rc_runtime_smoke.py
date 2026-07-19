from __future__ import annotations

import socket

from scripts.rc_runtime_smoke import _clean_env, _resolve_port, validate_backend_contract, validate_frontend_contract


def test_clean_env_removes_proxy_and_forces_mock_backend(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://example.invalid")
    monkeypatch.setenv("grpc_proxy", "socks5h://localhost:1080")
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "openai")

    env = _clean_env()

    assert "HTTP_PROXY" not in env
    assert "grpc_proxy" not in env
    assert env["XAGENT_LLM_BACKEND"] == "mock"
    assert env["XAGENT_REQUIRE_API_KEY"] == "false"


def test_resolve_port_falls_back_when_requested_port_is_busy() -> None:
    host = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.listen(1)
        busy_port = int(sock.getsockname()[1])

        resolved = _resolve_port(host, busy_port, strict_ports=False)

    assert resolved != busy_port
    assert resolved > 0


def test_validate_backend_contract_accepts_first_run_smoke_shape() -> None:
    checks = {
        "health": {"status": 200, "content_type": "application/json", "text": "", "json": {"status": "ok"}},
        "ready": {"status": 200, "content_type": "application/json", "text": "", "json": {"status": "ready"}},
        "chat": {"status": 200, "content_type": "text/html", "text": "<title>X-Agent</title>", "json": None},
        "workflow_chat": {
            "status": 200,
            "content_type": "application/json",
            "text": "",
            "json": {
                "run_id": "chat-1",
                "status": "accepted",
                "approval_required": False,
                "resource_type": "workflow_chat",
            },
        },
    }

    assert validate_backend_contract(checks) == {
        "health_ok": True,
        "ready_ok": True,
        "chat_html": True,
        "workflow_chat_ok": True,
    }


def test_validate_frontend_contract_accepts_vite_and_proxy_shape() -> None:
    checks = {
        "root": {"status": 200, "content_type": "text/html", "text": "X-Agent /@vite/client", "json": None},
        "chat": {"status": 200, "content_type": "text/html", "text": "X-Agent /@vite/client", "json": None},
        "proxied_workbench": {
            "status": 200,
            "content_type": "application/json",
            "text": "",
            "json": {"console": {"tenant_id": "default"}, "entries": [{"path": "/chat"}]},
        },
    }

    assert validate_frontend_contract(checks) == {
        "frontend_root_html": True,
        "frontend_chat_html": True,
        "vite_dev_client_injected": True,
        "api_proxy_workbench": True,
    }
