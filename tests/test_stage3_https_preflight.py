from __future__ import annotations

import json
import socket
from pathlib import Path

from scripts.stage3_https_preflight import build_stage3_https_preflight_report, main


def _resolver(addresses: list[str]):
    def resolve(_domain: str, port: int):
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port),
            )
            for address in addresses
        ]

    return resolve


def _tls_ok(_domain: str, _timeout: float):
    return {"issuer": "test-ca", "not_after": "Jun 18 00:00:00 2027 GMT"}, None


def _http_ok(url: str, _timeout: float):
    if url.endswith("/health"):
        return {"status_code": 200, "content_type": "application/json", "json_status": "ok"}, None
    if url.endswith("/ready"):
        return {
            "status_code": 200,
            "content_type": "application/json",
            "json_status": "ready",
            "component_names": ["audit", "qdrant"],
        }, None
    return {}, "unexpected url"


def test_stage3_https_preflight_ready_for_real_domain() -> None:
    report = build_stage3_https_preflight_report(
        domain="stage3.example.com",
        expected_ip="111.228.49.160",
        resolver=_resolver(["111.228.49.160"]),
        tls_probe=_tls_ok,
        http_probe=_http_ok,
    )

    assert report.status == "stage3_https_preflight_ready"
    assert report.endpoint == "https://stage3.example.com"
    assert report.mutation_performed is False
    assert report.deploy_performed is False
    assert report.workflow_dispatch_performed is False
    assert report.raw_secret_values_recorded is False
    assert all(check.status == "passed" for check in report.checks)


def test_stage3_https_preflight_rejects_non_owner_domain_shapes() -> None:
    for domain in (
        "https://111.228.49.160",
        "xagent.111.228.49.160.sslip.io",
        "localhost",
        "stage3",
        "http://stage3.example.com",
        "https://user:pass@stage3.example.com",
        "https://stage3.example.com/health",
    ):
        report = build_stage3_https_preflight_report(domain=domain)

        assert report.status == "stage3_https_preflight_blocked"
        assert report.endpoint is None
        domain_check = next(check for check in report.checks if check.name == "domain_shape")
        assert domain_check.status == "failed"


def test_stage3_https_preflight_blocks_when_dns_does_not_point_to_expected_ip() -> None:
    report = build_stage3_https_preflight_report(
        domain="stage3.example.com",
        expected_ip="111.228.49.160",
        resolver=_resolver(["203.0.113.10"]),
        tls_probe=_tls_ok,
        http_probe=_http_ok,
    )

    assert report.status == "stage3_https_preflight_blocked"
    dns_check = next(check for check in report.checks if check.name == "dns_points_to_expected_ip")
    assert dns_check.status == "failed"
    assert "111.228.49.160" in str(dns_check.error)
    assert any("DNS A record" in action for action in report.next_actions)


def test_stage3_https_preflight_blocks_on_tls_or_probe_failure() -> None:
    def tls_fail(_domain: str, _timeout: float):
        return {}, "certificate verify failed"

    def ready_fail(url: str, _timeout: float):
        if url.endswith("/health"):
            return {"status_code": 200, "json_status": "ok"}, None
        return {"status_code": 503, "json_status": "not_ready"}, None

    report = build_stage3_https_preflight_report(
        domain="stage3.example.com",
        resolver=_resolver(["111.228.49.160"]),
        tls_probe=tls_fail,
        http_probe=ready_fail,
    )

    assert report.status == "stage3_https_preflight_blocked"
    tls_check = next(check for check in report.checks if check.name == "trusted_https_tls")
    ready_check = next(check for check in report.checks if check.name == "https_ready_probe")
    assert tls_check.status == "failed"
    assert ready_check.status == "failed"
    assert not any("DNS A record" in action for action in report.next_actions)
    assert any("port 443" in action for action in report.next_actions)
    assert any("/health" in action and "/ready" in action for action in report.next_actions)


def test_stage3_https_preflight_cli_writes_blocked_report(tmp_path: Path) -> None:
    output_json = tmp_path / "preflight.json"
    output_md = tmp_path / "preflight.md"

    rc = main(
        [
            "--domain",
            "https://111.228.49.160",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert rc == 1
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "stage3_https_preflight_blocked"
    assert payload["mutation_performed"] is False
    assert payload["raw_secret_values_recorded"] is False
    assert "Stage3 HTTPS Preflight" in markdown
