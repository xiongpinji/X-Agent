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

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "provider-health-failover-gate.json"

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


def _provider_matrix() -> list[dict[str, Any]]:
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
        },
        {
            "capability": "llm+rag",
            "provider": "mock",
            "configured": True,
            "api_only": True,
            "local": False,
            "failover_order": [],
            "secret_value": "<redacted>",
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
