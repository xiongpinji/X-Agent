#!/usr/bin/env python3
"""Run first-version single-machine smoke checks against a live X-Agent API.

This script is intentionally small and stdlib-only so it can run on a fresh
Ubuntu host after a Docker Compose deployment. It validates the live HTTP
surface that does not depend on public DNS, ICP filing, or TLS automation.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "single-machine-smoke.json"
LOCAL_HTTP_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    text: str
    json: Any | None = None


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"passed", "skipped"}


@dataclass(frozen=True)
class SingleMachineSmokeReport:
    status: str
    generated_at: str
    base_url: str
    duration_seconds: float
    checks: list[SmokeCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Requester = Callable[[str, str, dict[str, str] | None, float], HttpResponse]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _parse_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def request_http(method: str, url: str, headers: dict[str, str] | None, timeout_seconds: float) -> HttpResponse:
    request = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return HttpResponse(
                status=int(response.status),
                headers=response_headers,
                text=raw,
                json=_parse_json(raw),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        response_headers = {key.lower(): value for key, value in exc.headers.items()}
        return HttpResponse(
            status=int(exc.code),
            headers=response_headers,
            text=raw,
            json=_parse_json(raw),
        )


def _is_private_or_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    normalized = hostname.strip("[]").lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized.endswith(".localhost")
    return any(address in network for network in LOCAL_HTTP_NETWORKS)


def check_base_url_scope(base_url: str, *, allow_public_http: bool = False) -> SmokeCheck:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return SmokeCheck(
            name="base_url_scope",
            status="failed",
            details={"base_url": base_url},
            error="base_url must be an absolute http(s) URL.",
        )

    if parsed.scheme == "http" and not _is_private_or_loopback_host(parsed.hostname) and not allow_public_http:
        return SmokeCheck(
            name="base_url_scope",
            status="failed",
            details={"base_url": base_url, "hostname": parsed.hostname},
            error="public HTTP is not accepted for this single-machine smoke; use localhost/private IP or pass --allow-public-http.",
        )

    return SmokeCheck(
        name="base_url_scope",
        status="passed",
        details={"scheme": parsed.scheme, "hostname": parsed.hostname, "public_http_allowed": allow_public_http},
    )


def check_health(base_url: str, requester: Requester, timeout_seconds: float) -> tuple[SmokeCheck, HttpResponse | None]:
    url = _join_url(base_url, "/health")
    try:
        response = requester("GET", url, None, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - smoke should report connection failures
        return SmokeCheck("health", "failed", {"url": url}, str(exc)), None

    payload = response.json if isinstance(response.json, dict) else {}
    ok = response.status == 200 and payload.get("status") == "ok" and payload.get("service") == "x-agent"
    return (
        SmokeCheck(
            name="health",
            status="passed" if ok else "failed",
            details={"url": url, "status": response.status, "payload": payload},
            error=None if ok else "expected HTTP 200 with {'status': 'ok', 'service': 'x-agent'}.",
        ),
        response,
    )


def check_ready(base_url: str, requester: Requester, timeout_seconds: float) -> SmokeCheck:
    url = _join_url(base_url, "/ready")
    try:
        response = requester("GET", url, None, timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        return SmokeCheck("ready", "failed", {"url": url}, str(exc))

    payload = response.json if isinstance(response.json, dict) else {}
    ok = response.status == 200 and payload.get("status") == "ready"
    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    return SmokeCheck(
        name="ready",
        status="passed" if ok else "failed",
        details={
            "url": url,
            "status": response.status,
            "ready_status": payload.get("status"),
            "components": components,
            "integrations": payload.get("integrations") if isinstance(payload.get("integrations"), dict) else {},
        },
        error=None if ok else "expected HTTP 200 with {'status': 'ready'}.",
    )


def check_security_headers(response: HttpResponse | None) -> SmokeCheck:
    if response is None:
        return SmokeCheck("security_headers", "failed", error="health response missing; cannot inspect headers.")

    headers = response.headers
    required = {
        "x-request-id": lambda value: bool(value),
        "x-content-type-options": lambda value: value.lower() == "nosniff",
        "x-frame-options": lambda value: value.upper() == "DENY",
        "content-security-policy": lambda value: "frame-ancestors 'none'" in value,
    }
    missing_or_invalid = [
        name for name, validator in required.items() if not headers.get(name) or not validator(headers.get(name, ""))
    ]
    ok = not missing_or_invalid
    return SmokeCheck(
        name="security_headers",
        status="passed" if ok else "failed",
        details={
            "checked_headers": sorted(required),
            "missing_or_invalid": missing_or_invalid,
            "strict_transport_security_present": bool(headers.get("strict-transport-security")),
        },
        error=None if ok else "required API security headers are missing or invalid.",
    )


def check_unauthenticated_guard(base_url: str, requester: Requester, timeout_seconds: float) -> SmokeCheck:
    url = _join_url(base_url, "/api/v1/auth/me")
    try:
        response = requester("GET", url, None, timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        return SmokeCheck("unauthenticated_guard", "failed", {"url": url}, str(exc))

    ok = response.status in {401, 403}
    return SmokeCheck(
        name="unauthenticated_guard",
        status="passed" if ok else "failed",
        details={"url": url, "status": response.status},
        error=None if ok else "protected /api/v1/auth/me must reject unauthenticated requests.",
    )


def check_authenticated_me(
    base_url: str,
    requester: Requester,
    timeout_seconds: float,
    *,
    bearer_token: str | None,
) -> SmokeCheck:
    if not bearer_token:
        return SmokeCheck(
            name="authenticated_me",
            status="skipped",
            details={"reason": "no bearer token env var was provided"},
        )

    url = _join_url(base_url, "/api/v1/auth/me")
    headers = {"Authorization": f"Bearer {bearer_token}"}
    try:
        response = requester("GET", url, headers, timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        return SmokeCheck("authenticated_me", "failed", {"url": url, "token_length": len(bearer_token)}, str(exc))

    ok = response.status == 200 and isinstance(response.json, dict)
    return SmokeCheck(
        name="authenticated_me",
        status="passed" if ok else "failed",
        details={"url": url, "status": response.status, "token_length": len(bearer_token)},
        error=None if ok else "bearer token did not authenticate against /api/v1/auth/me.",
    )


def run_single_machine_smoke(
    *,
    base_url: str,
    output_path: Path = DEFAULT_OUTPUT,
    timeout_seconds: float = 10.0,
    allow_public_http: bool = False,
    bearer_token: str | None = None,
    requester: Requester = request_http,
) -> SingleMachineSmokeReport:
    start = time.perf_counter()
    checks: list[SmokeCheck] = [check_base_url_scope(base_url, allow_public_http=allow_public_http)]
    health_response: HttpResponse | None = None

    if checks[-1].status == "passed":
        health_check, health_response = check_health(base_url, requester, timeout_seconds)
        checks.append(health_check)
        checks.append(check_ready(base_url, requester, timeout_seconds))
        checks.append(check_security_headers(health_response))
        checks.append(check_unauthenticated_guard(base_url, requester, timeout_seconds))
        checks.append(check_authenticated_me(base_url, requester, timeout_seconds, bearer_token=bearer_token))

    failed = [check for check in checks if check.status == "failed"]
    report = SingleMachineSmokeReport(
        status="failed" if failed else "passed",
        generated_at=_utc_now(),
        base_url=base_url,
        duration_seconds=round(time.perf_counter() - start, 3),
        checks=checks,
        next_commands=_next_commands(output_path, failed),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _next_commands(output_path: Path, failed: list[SmokeCheck]) -> list[str]:
    if failed:
        return [
            f"Inspect {output_path}.",
            f"Fix the first failing check: {failed[0].name}.",
            "Then rerun scripts/single_machine_smoke.py against the same base URL.",
        ]
    return [
        f"Use {output_path} as first-version single-machine smoke evidence.",
        "Keep public DNS/ICP/HTTPS Stage3 evidence separate from this local single-machine result.",
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run X-Agent first-version single-machine smoke checks")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Live API base URL, usually http://127.0.0.1:8899 or http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--allow-public-http", action="store_true", help="Allow testing a public http:// URL. Prefer localhost/private IP for single-machine smoke.")
    parser.add_argument("--bearer-token-env", default="", help="Optional env var containing a bearer token for /api/v1/auth/me.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv(args.bearer_token_env) if args.bearer_token_env else None
    report = run_single_machine_smoke(
        base_url=args.base_url,
        output_path=args.output,
        timeout_seconds=args.timeout,
        allow_public_http=args.allow_public_http,
        bearer_token=token,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Single-machine smoke status: {report.status}")
        print(f"Report written to {args.output}")
        for check in report.checks:
            print(f"- {check.name}: {check.status}")
            if check.error:
                print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
