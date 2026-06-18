#!/usr/bin/env python3
"""Preflight a Stage3 HTTPS endpoint before owner evidence intake.

This script is read-only and redaction-safe. It does not deploy, mutate the
server, dispatch workflows, or record secret values. It only verifies that an
owner-controlled DNS name resolves to the expected Stage3 host and serves
trusted HTTPS `/health` and `/ready` probes.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage3-https-preflight-20260618.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage3-https-preflight-20260618.md"
DEFAULT_EXPECTED_IP = "111.228.49.160"
TEMPORARY_DOMAIN_SUFFIXES = (".sslip.io", ".nip.io", ".xip.io")


@dataclass(frozen=True)
class Stage3PreflightCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Stage3HttpsPreflightReport:
    status: str
    generated_at: str
    domain: str
    expected_ip: str
    endpoint: str | None
    mutation_performed: bool
    deploy_performed: bool
    workflow_dispatch_performed: bool
    cluster_mutation_performed: bool
    raw_secret_values_recorded: bool
    checks: list[Stage3PreflightCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> Stage3PreflightCheck:
    return Stage3PreflightCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _normalize_domain(value: str) -> tuple[str, list[str]]:
    candidate = value.strip()
    errors: list[str] = []
    if not candidate:
        return "", ["domain is required"]
    if "://" in candidate:
        parsed = urlparse(candidate)
        if parsed.scheme != "https":
            errors.append("domain URL must use https")
        if parsed.username or parsed.password:
            errors.append("domain URL must not contain credentials")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            errors.append("domain must be a hostname, not a path/query URL")
        candidate = parsed.hostname or ""
    domain = candidate.strip().lower().rstrip(".")
    return domain, errors


def _domain_validation_errors(domain: str) -> list[str]:
    errors: list[str] = []
    if not domain:
        return ["domain is required"]
    if domain == "localhost" or domain.endswith(".localhost"):
        errors.append("domain must not use localhost")
    if "." not in domain:
        errors.append("domain must be a real DNS name, not a single-label host")
    if any(domain == suffix[1:] or domain.endswith(suffix) for suffix in TEMPORARY_DOMAIN_SUFFIXES):
        errors.append("domain must not use temporary wildcard DNS such as sslip.io")
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        pass
    else:
        errors.append("domain must be an owner-controlled DNS name, not a bare IP")
    return sorted(set(errors))


def _resolve_addresses(
    domain: str,
    *,
    resolver: Callable[[str, int], Sequence[Any]] | None = None,
) -> tuple[list[str], str | None]:
    resolve = resolver or (lambda host, port: socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
    try:
        records = resolve(domain, 443)
    except OSError as exc:
        return [], str(exc)
    addresses: set[str] = set()
    for record in records:
        try:
            sockaddr = record[4]
            addresses.add(str(sockaddr[0]))
        except (IndexError, TypeError):
            continue
    return sorted(addresses), None


def _trusted_tls_summary(domain: str, *, timeout: float) -> tuple[dict[str, Any], str | None]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=timeout) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=domain) as tls_sock:
                cert = tls_sock.getpeercert()
    except (OSError, ssl.SSLError) as exc:
        return {}, str(exc)
    if not isinstance(cert, Mapping) or not cert:
        return {}, "TLS certificate was not available"
    return {
        "subject": cert.get("subject"),
        "issuer": cert.get("issuer"),
        "not_after": cert.get("notAfter"),
        "subject_alt_name_count": len(cert.get("subjectAltName") or []),
    }, None


def _fetch_probe_json(url: str, *, timeout: float) -> tuple[dict[str, Any], str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "xagent-stage3-preflight"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = int(getattr(response, "status", response.getcode()))
            content_type = response.headers.get("content-type", "")
            raw = response.read(4096)
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code}, f"HTTP probe returned {exc.code}"
    except (OSError, urllib.error.URLError) as exc:
        return {}, str(exc)
    details: dict[str, Any] = {"status_code": status_code, "content_type": content_type}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        details["json_status"] = None
        return details, f"probe did not return JSON: {exc}"
    details["json_status"] = payload.get("status") if isinstance(payload, Mapping) else None
    if isinstance(payload, Mapping) and isinstance(payload.get("components"), Mapping):
        details["component_names"] = sorted(str(name) for name in payload["components"].keys())
    return details, None


def _next_actions_for_checks(
    *,
    ready: bool,
    checks: list[Stage3PreflightCheck],
    expected_ip: str,
) -> list[str]:
    if ready:
        return [
            "Use this report as a redaction-safe reference for Stage3 environment-protection evidence.",
            "Fill the Stage3 owner evidence draft with DNS/TLS/health/ready refs and rerun the intake.",
        ]

    failed_checks = {check.name for check in checks if check.status != "passed"}
    actions: list[str] = []
    if "domain_shape" in failed_checks:
        actions.append(
            "Provide an owner-controlled HTTPS hostname only; do not use bare IPs, localhost, "
            "temporary wildcard DNS, credentials, paths, query strings, or fragments."
        )
    if "dns_points_to_expected_ip" in failed_checks:
        actions.append(f"Create or fix the owner-controlled DNS A record so the domain resolves to {expected_ip}.")
    if "trusted_https_tls" in failed_checks:
        actions.append(
            "Configure trusted HTTPS on port 443 for the domain and clear any cloud-provider domain access block."
        )
    if {"https_health_probe", "https_ready_probe"} & failed_checks:
        actions.append(
            "Confirm /health returns JSON status 'ok' and /ready returns JSON status 'ready' over trusted HTTPS."
        )
    if not actions:
        actions.append("Inspect the failed Stage3 HTTPS preflight checks and rerun the report after remediation.")
    return actions


def build_stage3_https_preflight_report(
    *,
    domain: str,
    expected_ip: str = DEFAULT_EXPECTED_IP,
    timeout: float = 15.0,
    resolver: Callable[[str, int], Sequence[Any]] | None = None,
    tls_probe: Callable[[str, float], tuple[dict[str, Any], str | None]] | None = None,
    http_probe: Callable[[str, float], tuple[dict[str, Any], str | None]] | None = None,
) -> Stage3HttpsPreflightReport:
    normalized_domain, normalization_errors = _normalize_domain(domain)
    domain_errors = [*normalization_errors, *_domain_validation_errors(normalized_domain)]
    endpoint = f"https://{normalized_domain}" if normalized_domain and not domain_errors else None

    checks: list[Stage3PreflightCheck] = [
        _check(
            "domain_shape",
            not domain_errors,
            details={"domain": normalized_domain, "expected_ip": expected_ip},
            error="; ".join(domain_errors),
        )
    ]

    if not domain_errors:
        addresses, dns_error = _resolve_addresses(normalized_domain, resolver=resolver)
        dns_ok = dns_error is None and expected_ip in addresses
        checks.append(
            _check(
                "dns_points_to_expected_ip",
                dns_ok,
                details={"resolved_addresses": addresses, "expected_ip": expected_ip},
                error=dns_error or f"domain does not resolve to expected IP {expected_ip}",
            )
        )

        probe_tls = tls_probe or (lambda host, seconds: _trusted_tls_summary(host, timeout=seconds))
        tls_details, tls_error = probe_tls(normalized_domain, timeout)
        checks.append(
            _check(
                "trusted_https_tls",
                tls_error is None,
                details=tls_details,
                error=tls_error or "trusted TLS check failed",
            )
        )

        probe_http = http_probe or (lambda url, seconds: _fetch_probe_json(url, timeout=seconds))
        for path, expected_status in (("/health", "ok"), ("/ready", "ready")):
            url = f"https://{normalized_domain}{path}"
            details, error = probe_http(url, timeout)
            passed = error is None and details.get("status_code") == 200 and details.get("json_status") == expected_status
            check_name = f"https_{path.strip('/')}_probe"
            checks.append(
                _check(
                    check_name,
                    passed,
                    details={"url": url, **details},
                    error=error
                    or (
                        f"{path} must return HTTP 200 and JSON status {expected_status!r}; "
                        f"got HTTP {details.get('status_code')} and status {details.get('json_status')!r}"
                    ),
                )
            )

    ready = all(check.status == "passed" for check in checks)
    next_actions = _next_actions_for_checks(ready=ready, checks=checks, expected_ip=expected_ip)
    return Stage3HttpsPreflightReport(
        status="stage3_https_preflight_ready" if ready else "stage3_https_preflight_blocked",
        generated_at=_utc_now(),
        domain=normalized_domain,
        expected_ip=expected_ip,
        endpoint=endpoint,
        mutation_performed=False,
        deploy_performed=False,
        workflow_dispatch_performed=False,
        cluster_mutation_performed=False,
        raw_secret_values_recorded=False,
        checks=checks,
        next_actions=next_actions,
        known_limits=[
            "This preflight is read-only and does not deploy or mutate Stage3.",
            "This report proves endpoint reachability only; observability and owner approval refs are still required.",
            "No request or response secrets are recorded.",
        ],
    )


def render_markdown_report(report: Stage3HttpsPreflightReport) -> str:
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    actions = "\n".join(f"- {item}" for item in report.next_actions)
    return (
        "# Stage3 HTTPS Preflight\n\n"
        f"- Status: `{report.status}`\n"
        f"- Domain: `{report.domain or '<missing>'}`\n"
        f"- Expected IP: `{report.expected_ip}`\n"
        f"- Endpoint: `{report.endpoint or '<blocked>'}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Raw secret values recorded: `{report.raw_secret_values_recorded}`\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Next Actions\n\n"
        f"{actions}\n"
    )


def write_reports(
    report: Stage3HttpsPreflightReport,
    *,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight Stage3 owner-domain HTTPS readiness.")
    parser.add_argument("--domain", required=True, help="Owner-controlled domain, for example xagent.example.com.")
    parser.add_argument("--expected-ip", default=DEFAULT_EXPECTED_IP)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_stage3_https_preflight_report(
        domain=args.domain,
        expected_ip=args.expected_ip,
        timeout=args.timeout,
    )
    write_reports(report, output_json=args.output_json, output_md=args.output_md)
    print(f"Stage3 HTTPS preflight status: {report.status}")
    print(f"Domain: {report.domain or '<missing>'}")
    print(f"JSON report written to {_display_path(args.output_json)}")
    print(f"Markdown report written to {_display_path(args.output_md)}")
    return 0 if report.status == "stage3_https_preflight_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
