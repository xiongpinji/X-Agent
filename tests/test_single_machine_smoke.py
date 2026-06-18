from __future__ import annotations

from pathlib import Path

from scripts.single_machine_smoke import HttpResponse, check_base_url_scope, run_single_machine_smoke


def test_base_url_scope_accepts_loopback_http() -> None:
    check = check_base_url_scope("http://127.0.0.1:8899")

    assert check.status == "passed"


def test_base_url_scope_rejects_public_http_without_opt_in() -> None:
    check = check_base_url_scope("http://203.0.113.10:8899")

    assert check.status == "failed"
    assert "public HTTP" in str(check.error)


def test_single_machine_smoke_passes_minimal_live_contract(tmp_path: Path) -> None:
    def requester(method: str, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse:
        if url.endswith("/health"):
            return HttpResponse(
                status=200,
                headers={
                    "x-request-id": "req-1",
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
                },
                text='{"status":"ok","service":"x-agent"}',
                json={"status": "ok", "service": "x-agent"},
            )
        if url.endswith("/ready"):
            return HttpResponse(
                status=200,
                headers={},
                text='{"status":"ready","components":{"audit":"ok"},"integrations":{}}',
                json={"status": "ready", "components": {"audit": "ok"}, "integrations": {}},
            )
        if url.endswith("/api/v1/auth/me") and not headers:
            return HttpResponse(status=401, headers={}, text='{"detail":"Not authenticated"}', json={"detail": "Not authenticated"})
        raise AssertionError(f"unexpected request: {method} {url} {headers} {timeout}")

    report = run_single_machine_smoke(
        base_url="http://127.0.0.1:8899",
        output_path=tmp_path / "single-machine-smoke.json",
        requester=requester,
    )

    assert report.status == "passed"
    assert [check.name for check in report.checks] == [
        "base_url_scope",
        "health",
        "ready",
        "security_headers",
        "unauthenticated_guard",
        "authenticated_me",
    ]
    assert report.checks[-1].status == "skipped"


def test_single_machine_smoke_fails_when_protected_me_is_public(tmp_path: Path) -> None:
    def requester(method: str, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse:
        if url.endswith("/health"):
            return HttpResponse(
                status=200,
                headers={
                    "x-request-id": "req-1",
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "content-security-policy": "frame-ancestors 'none'",
                },
                text='{"status":"ok","service":"x-agent"}',
                json={"status": "ok", "service": "x-agent"},
            )
        if url.endswith("/ready"):
            return HttpResponse(status=200, headers={}, text='{"status":"ready"}', json={"status": "ready"})
        if url.endswith("/api/v1/auth/me"):
            return HttpResponse(status=200, headers={}, text='{"id":"user-1"}', json={"id": "user-1"})
        raise AssertionError(f"unexpected request: {method} {url} {headers} {timeout}")

    report = run_single_machine_smoke(
        base_url="http://127.0.0.1:8899",
        output_path=tmp_path / "single-machine-smoke.json",
        requester=requester,
    )

    assert report.status == "failed"
    failed = [check for check in report.checks if check.status == "failed"]
    assert [check.name for check in failed] == ["unauthenticated_guard"]


def test_single_machine_smoke_never_writes_bearer_token_value(tmp_path: Path) -> None:
    token = "secret-token-value"

    def requester(method: str, url: str, headers: dict[str, str] | None, timeout: float) -> HttpResponse:
        if url.endswith("/health"):
            return HttpResponse(
                status=200,
                headers={
                    "x-request-id": "req-1",
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "content-security-policy": "frame-ancestors 'none'",
                },
                text='{"status":"ok","service":"x-agent"}',
                json={"status": "ok", "service": "x-agent"},
            )
        if url.endswith("/ready"):
            return HttpResponse(status=200, headers={}, text='{"status":"ready"}', json={"status": "ready"})
        if url.endswith("/api/v1/auth/me") and headers:
            assert headers["Authorization"] == f"Bearer {token}"
            return HttpResponse(status=200, headers={}, text='{"id":"user-1"}', json={"id": "user-1"})
        return HttpResponse(status=401, headers={}, text='{}', json={})

    output = tmp_path / "single-machine-smoke.json"
    report = run_single_machine_smoke(
        base_url="http://127.0.0.1:8899",
        output_path=output,
        requester=requester,
        bearer_token=token,
    )

    assert report.status == "passed"
    assert token not in output.read_text(encoding="utf-8")
    assert '"token_length": 18' in output.read_text(encoding="utf-8")
