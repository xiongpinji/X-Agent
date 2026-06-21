#!/usr/bin/env python3
"""Validate the second-batch runtime capability manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.second_batch_capabilities import build_second_batch_capability_manifest

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "second-batch-capability-manifest-gate.json"

REQUIRED_EVIDENCE_TYPES = {
    "llm_governance_api_gate",
    "rag_governance_api_gate",
    "provider_health_failover_gate",
    "provider_preflight_api_gate",
    "agent_dispatch_contract_gate",
    "browser_workspace_verification_gate",
    "creative_studio_external_video_api_only_gate",
    "second_batch_quality_gate",
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
    manifest_summary: dict[str, Any]
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


def build_second_batch_capability_manifest_gate_report(root: Path = ROOT) -> GateReport:
    manifest = build_second_batch_capability_manifest()
    main_source = (root / "backend/app/main.py").read_text(encoding="utf-8")
    api_source = (root / "backend/app/api/capabilities.py").read_text(encoding="utf-8")
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), list) else []
    evidence_types = {
        evidence_type
        for item in capabilities
        if isinstance(item, dict)
        for evidence_type in item.get("evidence_types", [])
        if isinstance(evidence_type, str)
    }
    mounted_surfaces = {
        surface.get("path")
        for item in capabilities
        if isinstance(item, dict)
        for surface in item.get("surfaces", [])
        if isinstance(surface, dict)
    }
    checks = [
        _check(
            "route_is_mounted",
            "from backend.app.api.capabilities import router as capabilities_router" in main_source
            and "app.include_router(capabilities_router)" in main_source,
            error="capabilities router is not mounted in backend/app/main.py",
        ),
        _check(
            "endpoint_requires_audit_read",
            'enforce_scope(principal, "audit:read")' in api_source,
            error="capabilities endpoint does not enforce audit:read",
        ),
        _check(
            "manifest_is_api_first_without_local_models",
            manifest.get("external_api_first") is True
            and manifest.get("local_model_runtime_supported") is False
            and all(item.get("local_runtime_required") is False for item in capabilities if isinstance(item, dict)),
            error="manifest does not preserve external API-first and no-local-runtime boundaries",
        ),
        _check(
            "manifest_does_not_claim_release",
            manifest.get("full_release_claimed") is False
            and manifest.get("network_mutation_allowed") is False,
            error="manifest claims release readiness or network mutation",
        ),
        _check(
            "required_capabilities_are_listed",
            {"external_llm_governance", "api_only_rag", "provider_preflight", "creative_video_protocol"}.issubset(
                {item.get("capability_id") for item in capabilities if isinstance(item, dict)}
            ),
            error="manifest is missing required second-batch capabilities",
        ),
        _check(
            "runtime_surfaces_are_declared",
            {
                "/api/v1/llm/providers",
                "/api/v1/rag/query",
                "/api/v1/providers/preflight",
                "/api/v1/capabilities/second-batch",
            }.issubset(mounted_surfaces),
            details={"surface_count": len(mounted_surfaces)},
            error="manifest is missing required runtime API surfaces",
        ),
        _check(
            "required_evidence_types_are_declared",
            REQUIRED_EVIDENCE_TYPES.issubset(evidence_types),
            details={"evidence_types": sorted(evidence_types)},
            error="manifest does not declare all required second-batch evidence types",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="second_batch_capability_manifest_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        git_sha=_current_git_sha(root),
        manifest_summary=dict(manifest.get("summary", {})),
        checks=checks,
        known_limits=[
            "This gate validates manifest shape only; it does not execute capabilities.",
            "Evidence freshness remains enforced by scripts/second_batch_quality_gate.py.",
        ],
        next_commands=[
            "python scripts/second_batch_capability_manifest_gate.py",
            "python -m pytest tests/test_second_batch_capabilities_api.py tests/test_second_batch_capability_manifest_gate.py -q --no-cov",
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
    report = build_second_batch_capability_manifest_gate_report()
    write_report(report, args.output)
    print(f"Second-batch capability manifest gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
