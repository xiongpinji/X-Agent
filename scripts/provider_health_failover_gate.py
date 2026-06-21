#!/usr/bin/env python3
"""Validate API-only provider health and failover evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.app.api.llm_governance import DEEPSEEK_BASE_URL_HOSTS
from backend.app.api.llm_governance import DEFAULT_DEEPSEEK_BASE_URL
from backend.app.api.llm_governance import PROTOCOL_LLM_DENIED_HOSTS
from backend.app.api.rag_governance import PROTOCOL_SEARCH_DENIED_HOSTS
from backend.app.core.creative_studio.adapters import LOCAL_VIDEO_PROVIDER_NAMES
from backend.app.core.url_safety import external_https_url_error_reason

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "provider-health-failover-gate.json"

SENSITIVE_ENV_KEYS = {
    "XAGENT_PROTOCOL_LLM_API_KEY",
    "XAGENT_DEEPSEEK_API_KEY",
    "XAGENT_PROTOCOL_SEARCH_API_KEY",
    "XAGENT_CREATIVE_VIDEO_API_KEY",
}
PROVIDER_STATUSES = {"ready_to_call", "missing_config", "rejected_config", "verification_only"}


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
    provider_matrix: list[dict[str, Any]]
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


def _configured(env_key: str) -> bool:
    return bool(os.environ.get(env_key))


def _fingerprint_env(env_key: str) -> str:
    value = os.environ.get(env_key, "")
    if not value:
        return ""
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").rstrip(".").lower()


def _url_preflight(url: str, *, denied_hosts: set[str] | None = None, allowed_hosts: set[str] | None = None) -> str:
    error = external_https_url_error_reason(url)
    if error is not None:
        return error
    host = _host(url)
    if denied_hosts and host in denied_hosts:
        return "host is blocked for this protocol gateway"
    if allowed_hosts and host not in allowed_hosts:
        return "host is not allowed for this provider"
    return ""


def _provider_status(*, missing: list[str], rejection_reason: str = "", verification_only: bool = False) -> str:
    if verification_only:
        return "verification_only"
    if rejection_reason:
        return "rejected_config"
    if missing:
        return "missing_config"
    return "ready_to_call"


def _provider_preflight() -> list[dict[str, Any]]:
    protocol_llm_url = os.environ.get("XAGENT_PROTOCOL_LLM_BASE_URL", "")
    protocol_llm_missing = [
        key
        for key in ("XAGENT_PROTOCOL_LLM_API_KEY", "XAGENT_PROTOCOL_LLM_BASE_URL")
        if not os.environ.get(key)
    ]
    protocol_llm_rejection = "" if protocol_llm_missing else _url_preflight(
        protocol_llm_url,
        denied_hosts=PROTOCOL_LLM_DENIED_HOSTS,
    )

    deepseek_url = os.environ.get("XAGENT_DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL
    deepseek_missing = [key for key in ("XAGENT_DEEPSEEK_API_KEY",) if not os.environ.get(key)]
    deepseek_rejection = "" if deepseek_missing else _url_preflight(
        deepseek_url,
        allowed_hosts=DEEPSEEK_BASE_URL_HOSTS,
    )

    protocol_search_url = os.environ.get("XAGENT_PROTOCOL_SEARCH_BASE_URL", "")
    protocol_search_missing = [
        key
        for key in ("XAGENT_PROTOCOL_SEARCH_API_KEY", "XAGENT_PROTOCOL_SEARCH_BASE_URL")
        if not os.environ.get(key)
    ]
    protocol_search_rejection = "" if protocol_search_missing else _url_preflight(
        protocol_search_url,
        denied_hosts=PROTOCOL_SEARCH_DENIED_HOSTS,
    )

    creative_provider = os.environ.get("XAGENT_CREATIVE_VIDEO_PROVIDER", "external-video-api")
    creative_url = os.environ.get("XAGENT_CREATIVE_VIDEO_API_URL", "")
    creative_missing = [
        key
        for key in ("XAGENT_CREATIVE_VIDEO_API_KEY", "XAGENT_CREATIVE_VIDEO_API_URL")
        if not os.environ.get(key)
    ]
    creative_rejection = ""
    if creative_provider.strip().lower() in LOCAL_VIDEO_PROVIDER_NAMES:
        creative_rejection = "provider must not be local"
    elif not creative_missing:
        creative_rejection = _url_preflight(creative_url)

    return [
        {
            "capability": "llm",
            "provider": "protocol-llm",
            "status": _provider_status(missing=protocol_llm_missing, rejection_reason=protocol_llm_rejection),
            "missing_config": protocol_llm_missing,
            "configuration_error": protocol_llm_rejection,
            "base_url_configured": bool(protocol_llm_url),
            "api_key_configured": _configured("XAGENT_PROTOCOL_LLM_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_PROTOCOL_LLM_API_KEY"),
            "external_https_required": True,
            "official_hosts_blocked": sorted(PROTOCOL_LLM_DENIED_HOSTS),
            "network_call_attempted": False,
        },
        {
            "capability": "llm",
            "provider": "deepseek",
            "status": _provider_status(missing=deepseek_missing, rejection_reason=deepseek_rejection),
            "missing_config": deepseek_missing,
            "configuration_error": deepseek_rejection,
            "base_url_configured": bool(os.environ.get("XAGENT_DEEPSEEK_BASE_URL")),
            "api_key_configured": _configured("XAGENT_DEEPSEEK_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_DEEPSEEK_API_KEY"),
            "official_host_only": True,
            "allowed_hosts": sorted(DEEPSEEK_BASE_URL_HOSTS),
            "network_call_attempted": False,
        },
        {
            "capability": "rag",
            "provider": "protocol-search",
            "status": _provider_status(missing=protocol_search_missing, rejection_reason=protocol_search_rejection),
            "missing_config": protocol_search_missing,
            "configuration_error": protocol_search_rejection,
            "base_url_configured": bool(protocol_search_url),
            "api_key_configured": _configured("XAGENT_PROTOCOL_SEARCH_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_PROTOCOL_SEARCH_API_KEY"),
            "external_https_required": True,
            "official_hosts_blocked": sorted(PROTOCOL_SEARCH_DENIED_HOSTS),
            "network_call_attempted": False,
        },
        {
            "capability": "creative-video",
            "provider": creative_provider,
            "status": _provider_status(missing=creative_missing, rejection_reason=creative_rejection),
            "missing_config": creative_missing,
            "configuration_error": creative_rejection,
            "base_url_configured": bool(creative_url),
            "api_key_configured": _configured("XAGENT_CREATIVE_VIDEO_API_KEY"),
            "api_key_fingerprint": _fingerprint_env("XAGENT_CREATIVE_VIDEO_API_KEY"),
            "external_https_required": True,
            "requires_human_review": True,
            "network_call_attempted": False,
        },
        {
            "capability": "llm+rag",
            "provider": "mock",
            "status": "verification_only",
            "missing_config": [],
            "configuration_error": "",
            "api_key_configured": False,
            "api_key_fingerprint": "",
            "network_call_attempted": False,
        },
    ]


def _provider_matrix() -> list[dict[str, Any]]:
    preflight_by_provider = {item["provider"]: item for item in _provider_preflight()}
    return [
        {
            "capability": "llm",
            "provider": "protocol-llm",
            "configured": _configured("XAGENT_PROTOCOL_LLM_API_KEY") and _configured("XAGENT_PROTOCOL_LLM_BASE_URL"),
            "api_only": True,
            "local": False,
            "external_https_required": True,
            "failover_order": ["deepseek", "mock"],
            "secret_value": "<redacted>",
            "preflight": preflight_by_provider["protocol-llm"],
        },
        {
            "capability": "llm",
            "provider": "deepseek",
            "configured": _configured("XAGENT_DEEPSEEK_API_KEY"),
            "api_only": True,
            "local": False,
            "official_host_only": True,
            "failover_order": ["mock"],
            "secret_value": "<redacted>",
            "preflight": preflight_by_provider["deepseek"],
        },
        {
            "capability": "rag",
            "provider": "protocol-search",
            "configured": _configured("XAGENT_PROTOCOL_SEARCH_API_KEY") and _configured("XAGENT_PROTOCOL_SEARCH_BASE_URL"),
            "api_only": True,
            "local": False,
            "external_https_required": True,
            "failover_order": ["mock"],
            "secret_value": "<redacted>",
            "preflight": preflight_by_provider["protocol-search"],
        },
        {
            "capability": "creative-video",
            "provider": os.environ.get("XAGENT_CREATIVE_VIDEO_PROVIDER", "external-video-api"),
            "configured": _configured("XAGENT_CREATIVE_VIDEO_API_KEY") and _configured("XAGENT_CREATIVE_VIDEO_API_URL"),
            "api_only": True,
            "local": False,
            "external_https_required": True,
            "failover_order": ["dry-run"],
            "secret_value": "<redacted>",
            "preflight": preflight_by_provider[os.environ.get("XAGENT_CREATIVE_VIDEO_PROVIDER", "external-video-api")],
        },
        {
            "capability": "llm+rag",
            "provider": "mock",
            "configured": True,
            "api_only": True,
            "local": False,
            "failover_order": [],
            "secret_value": "<redacted>",
            "preflight": preflight_by_provider["mock"],
        },
    ]


def build_provider_health_failover_gate_report() -> GateReport:
    matrix = _provider_matrix()
    serialized = json.dumps(matrix, ensure_ascii=False)
    checks = [
        _check(
            "provider_matrix_is_api_only",
            all(item["api_only"] is True and item["local"] is False for item in matrix),
            error="provider matrix includes local or non API-only providers",
        ),
        _check(
            "provider_secrets_are_redacted",
            all(item.get("secret_value") == "<redacted>" for item in matrix)
            and not any(os.environ.get(key, "") and os.environ[key] in serialized for key in SENSITIVE_ENV_KEYS),
            error="provider matrix leaks secret values",
        ),
        _check(
            "failover_paths_are_declared",
            all("failover_order" in item and isinstance(item["failover_order"], list) for item in matrix),
            error="one or more provider entries lack failover order",
        ),
        _check(
            "mock_fallback_is_available",
            any(item["provider"] == "mock" and item["configured"] is True for item in matrix),
            error="mock fallback provider is not available for local verification",
        ),
        _check(
            "deepseek_official_host_guard_is_declared",
            any(item["provider"] == "deepseek" and item.get("official_host_only") is True for item in matrix),
            error="deepseek provider does not declare official-host-only guard",
        ),
        _check(
            "creative_video_provider_is_covered",
            any(item["capability"] == "creative-video" and item.get("external_https_required") is True for item in matrix),
            error="provider matrix does not cover the creative video external provider",
        ),
        _check(
            "provider_preflight_statuses_are_valid",
            all(item.get("preflight", {}).get("status") in PROVIDER_STATUSES for item in matrix),
            error="one or more provider preflight statuses are invalid",
        ),
        _check(
            "provider_preflight_does_not_call_network",
            all(item.get("preflight", {}).get("network_call_attempted") is False for item in matrix),
            error="provider preflight attempted a network call",
        ),
        _check(
            "provider_preflight_blocks_rejected_urls",
            all(
                item.get("preflight", {}).get("status") != "ready_to_call"
                for item in matrix
                if item["provider"] in {"protocol-llm", "protocol-search"}
                and item.get("preflight", {}).get("configuration_error")
            ),
            error="provider preflight marks rejected protocol URLs as ready",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="provider_health_failover_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        git_sha=_current_git_sha(),
        provider_matrix=matrix,
        checks=checks,
        known_limits=[
            "This gate inspects configuration shape only; it does not call external providers.",
            "Live provider health requires owner credentials and explicit network approval.",
            "Preflight validates configuration only; ready_to_call is not proof that the remote provider accepts requests.",
        ],
        next_commands=[
            "python scripts/provider_health_failover_gate.py",
            "python -m pytest tests/test_provider_health_failover_gate.py -q --no-cov",
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
    report = build_provider_health_failover_gate_report()
    write_report(report, args.output)
    print(f"Provider health/failover gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
