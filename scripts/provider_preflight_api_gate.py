#!/usr/bin/env python3
"""Validate the provider preflight runtime API contract."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.api.provider_preflight import router
from backend.app.core.provider_preflight import PROVIDER_STATUSES
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "provider-preflight-api-gate.json"

SENSITIVE_ENV_KEYS = {
    "XAGENT_PROTOCOL_LLM_API_KEY",
    "XAGENT_DEEPSEEK_API_KEY",
    "XAGENT_PROTOCOL_SEARCH_API_KEY",
    "XAGENT_CREATIVE_VIDEO_API_KEY",
}


@dataclass(frozen=True)
class GateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class GateReport:
    status: str
    generated_at: str
    evidence_type: str
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    full_release_claimed: bool
    git_sha: str
    endpoint: str
    providers: list[dict[str, Any]]
    checks: list[GateCheck]
    known_limits: list[str]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _current_git_sha(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None, error: str) -> GateCheck:
    return GateCheck(name=name, status="passed" if ok else "failed", details=details or {}, error=None if ok else error)


def _principal(scopes: list[str]) -> Principal:
    return Principal(
        tenant_id="tenant-1",
        user_id="provider-preflight-gate",
        role="developer",
        authenticated=True,
        api_key_id="provider-preflight-gate",
        permission_scope=scopes,
        scopes=scopes,
    )


def _client(scopes: list[str]) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    app.dependency_overrides[get_current_principal] = lambda: _principal(scopes)
    return TestClient(app)


@contextmanager
def _temporary_env(values: dict[str, str]) -> Iterator[None]:
    old_values: dict[str, str | None] = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _preflight_payload(env: dict[str, str], *, scopes: list[str] | None = None) -> dict[str, Any]:
    with _temporary_env(env):
        response = _client(scopes or ["audit:read"]).get("/api/v1/providers/preflight")
    if response.status_code != 200:
        return {"status_code": response.status_code, "text": response.text}
    return dict(response.json())


def build_provider_preflight_api_gate_report(root: Path = ROOT) -> GateReport:
    main_source = (root / "backend/app/main.py").read_text(encoding="utf-8")
    api_source = (root / "backend/app/api/provider_preflight.py").read_text(encoding="utf-8")
    ready_env = {
        "XAGENT_PROTOCOL_LLM_API_KEY": "gate-secret-protocol-llm",
        "XAGENT_PROTOCOL_LLM_BASE_URL": "https://llm-gateway.x-agent.dev/v1",
        "XAGENT_DEEPSEEK_API_KEY": "gate-secret-deepseek",
        "XAGENT_DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        "XAGENT_PROTOCOL_SEARCH_API_KEY": "gate-secret-protocol-search",
        "XAGENT_PROTOCOL_SEARCH_BASE_URL": "https://search-gateway.x-agent.dev/v1/search",
        "XAGENT_CREATIVE_VIDEO_API_KEY": "gate-secret-video",
        "XAGENT_CREATIVE_VIDEO_API_URL": "https://video-gateway.x-agent.dev/v1/generate",
        "XAGENT_CREATIVE_VIDEO_PROVIDER": "external-video-api",
    }
    rejected_env = {
        **ready_env,
        "XAGENT_PROTOCOL_LLM_BASE_URL": "https://api.openai.com/v1",
        "XAGENT_DEEPSEEK_BASE_URL": "https://openrouter.ai/api/v1",
        "XAGENT_PROTOCOL_SEARCH_BASE_URL": "https://api.tavily.com/search",
        "XAGENT_CREATIVE_VIDEO_PROVIDER": "comfyui",
    }

    unauthorized_response = _client(["agent:run"]).get("/api/v1/providers/preflight")
    ready_payload = _preflight_payload(ready_env)
    rejected_payload = _preflight_payload(rejected_env)
    serialized_ready = json.dumps(ready_payload, ensure_ascii=False)
    ready_providers = ready_payload.get("providers", []) if isinstance(ready_payload.get("providers"), list) else []
    rejected_providers = {
        item.get("provider"): item
        for item in rejected_payload.get("providers", [])
        if isinstance(item, dict)
    } if isinstance(rejected_payload.get("providers"), list) else {}

    checks = [
        _check(
            "route_is_mounted",
            "from backend.app.api.provider_preflight import router as provider_preflight_router" in main_source
            and "app.include_router(provider_preflight_router)" in main_source,
            error="provider preflight router is not mounted in backend/app/main.py",
        ),
        _check(
            "endpoint_requires_audit_read",
            unauthorized_response.status_code == 403 and "audit:read" in unauthorized_response.text,
            details={"status_code": unauthorized_response.status_code},
            error="provider preflight endpoint does not enforce audit:read",
        ),
        _check(
            "runtime_api_uses_core_not_scripts",
            "scripts." not in api_source and "backend.app.core.provider_preflight" in api_source,
            error="runtime API imports scripts or does not import provider preflight from core",
        ),
        _check(
            "preflight_response_is_dry_run",
            ready_payload.get("status") == "passed"
            and ready_payload.get("dry_run") is True
            and ready_payload.get("network_mutation_performed") is False,
            details={"status": ready_payload.get("status")},
            error="provider preflight response is not a passed dry-run response",
        ),
        _check(
            "provider_statuses_are_valid",
            bool(ready_providers)
            and all(isinstance(item, dict) and item.get("status") in PROVIDER_STATUSES for item in ready_providers),
            error="one or more provider status values are invalid",
        ),
        _check(
            "provider_secrets_are_redacted",
            not any(ready_env[key] in serialized_ready for key in SENSITIVE_ENV_KEYS),
            error="provider preflight response leaks secret values",
        ),
        _check(
            "preflight_does_not_call_network",
            bool(ready_providers)
            and all(item.get("network_call_attempted") is False for item in ready_providers if isinstance(item, dict)),
            error="provider preflight attempted or reported a network call",
        ),
        _check(
            "rejected_provider_urls_are_blocked",
            rejected_providers.get("protocol-llm", {}).get("status") == "rejected_config"
            and rejected_providers.get("deepseek", {}).get("status") == "rejected_config"
            and rejected_providers.get("protocol-search", {}).get("status") == "rejected_config"
            and rejected_providers.get("comfyui", {}).get("status") == "rejected_config",
            error="provider preflight did not reject blocked official/local provider configuration",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="provider_preflight_api_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        git_sha=_current_git_sha(root),
        endpoint="/api/v1/providers/preflight",
        providers=[
            {
                "capability": item.get("capability"),
                "provider": item.get("provider"),
                "status": item.get("status"),
                "api_key_configured": item.get("api_key_configured"),
                "base_url_configured": item.get("base_url_configured"),
                "network_call_attempted": item.get("network_call_attempted"),
            }
            for item in ready_providers
            if isinstance(item, dict)
        ],
        checks=checks,
        known_limits=[
            "This gate validates the local runtime API contract only; it does not call external providers.",
            "ready_to_call means local configuration shape is acceptable, not that remote credentials are live.",
        ],
        next_commands=[
            "python scripts/provider_preflight_api_gate.py",
            "python -m pytest tests/test_provider_preflight_api.py tests/test_provider_preflight_api_gate.py -q --no-cov",
            "git diff --check",
        ],
    )


def write_report(report: GateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_provider_preflight_api_gate_report()
    write_report(report, args.output)
    print(f"Provider preflight API gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
