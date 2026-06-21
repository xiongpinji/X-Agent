#!/usr/bin/env python3
"""Validate second-batch capability gate reports as one audit pack."""

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
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "second-batch-quality-gate.json"


@dataclass(frozen=True)
class QualityGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class QualityGateReport:
    status: str
    generated_at: str
    evidence_type: str
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    full_release_claimed: bool
    git_sha: str
    capability_reports: list[dict[str, Any]]
    checks: list[QualityGateCheck]
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


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None, error: str) -> QualityGateCheck:
    return QualityGateCheck(
        name=name,
        status="passed" if ok else "failed",
        details=details or {},
        error=None if ok else error,
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _report_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    return {
        "path": str(path.relative_to(ROOT)),
        "status": payload.get("status"),
        "evidence_type": payload.get("evidence_type"),
        "dry_run": payload.get("dry_run"),
        "mutation_performed": payload.get("mutation_performed"),
        "network_mutation_performed": payload.get("network_mutation_performed"),
        "full_release_claimed": payload.get("full_release_claimed"),
        "git_sha": payload.get("git_sha"),
        "check_count": len(checks),
        "failed_checks": [
            item.get("name")
            for item in checks
            if isinstance(item, dict) and item.get("status") != "passed"
        ],
        "next_commands": payload.get("next_commands") if isinstance(payload.get("next_commands"), list) else [],
    }


def build_second_batch_quality_gate_report(root: Path = ROOT) -> QualityGateReport:
    current_git_sha = _current_git_sha(root)
    report_paths = [
        root / ".xagent_runtime/reports/creative-studio-external-video-gate.json",
        root / ".xagent_runtime/reports/llm-governance-api-gate.json",
        root / ".xagent_runtime/reports/rag-governance-api-gate.json",
        root / ".xagent_runtime/reports/agent-dispatch-contract-gate.json",
        root / ".xagent_runtime/reports/browser-workspace-verification-gate.json",
        root / ".xagent_runtime/reports/provider-health-failover-gate.json",
    ]
    loaded: list[tuple[Path, dict[str, Any]]] = []
    missing: list[str] = []
    for path in report_paths:
        if path.exists():
            loaded.append((path, _load_json(path)))
        else:
            missing.append(str(path.relative_to(root)))

    summaries = [_report_summary(path, payload) for path, payload in loaded]
    all_next_commands = [
        command
        for _path, payload in loaded
        for command in payload.get("next_commands", [])
        if isinstance(command, str) and command.strip()
    ]
    evidence_types = {summary["evidence_type"] for summary in summaries}
    checks = [
        _check(
            "capability_reports_present",
            not missing and len(loaded) == len(report_paths),
            details={"missing": missing, "count": len(loaded)},
            error="one or more second-batch capability reports are missing",
        ),
        _check(
            "capability_reports_passed",
            bool(loaded) and all(summary["status"] == "passed" for summary in summaries),
            details={"statuses": {summary["path"]: summary["status"] for summary in summaries}},
            error="one or more second-batch capability reports did not pass",
        ),
        _check(
            "capability_reports_are_dry_run",
            bool(loaded) and all(summary["dry_run"] is True for summary in summaries),
            error="one or more reports are not marked dry_run=true",
        ),
        _check(
            "capability_reports_do_not_mutate",
            bool(loaded)
            and all(summary["mutation_performed"] is False for summary in summaries)
            and all(summary["network_mutation_performed"] is False for summary in summaries),
            error="one or more reports performed local or network mutation",
        ),
        _check(
            "capability_reports_do_not_claim_release",
            bool(loaded) and all(summary["full_release_claimed"] is False for summary in summaries),
            error="one or more reports claim full release readiness",
        ),
        _check(
            "capability_reports_have_checks",
            bool(loaded) and all(summary["check_count"] > 0 and not summary["failed_checks"] for summary in summaries),
            details={"check_counts": {summary["path"]: summary["check_count"] for summary in summaries}},
            error="one or more reports have no checks or failed checks",
        ),
        _check(
            "capability_reports_have_next_commands",
            bool(loaded) and all(summary["next_commands"] for summary in summaries),
            error="one or more reports are missing replay commands",
        ),
        _check(
            "capability_reports_match_current_git_sha",
            bool(loaded) and all(summary["git_sha"] == current_git_sha for summary in summaries),
            details={
                "current_git_sha": current_git_sha,
                "report_shas": {summary["path"]: summary["git_sha"] for summary in summaries},
            },
            error="one or more reports were generated from a different git revision",
        ),
        _check(
            "required_capability_surfaces_covered",
            {
                "creative_studio_external_video_api_only_gate",
                "llm_governance_api_gate",
                "rag_governance_api_gate",
                "agent_dispatch_contract_gate",
                "browser_workspace_verification_gate",
                "provider_health_failover_gate",
            }.issubset(evidence_types),
            details={"evidence_types": sorted(str(item) for item in evidence_types)},
            error="second-batch audit pack does not cover the required capability surfaces",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return QualityGateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="second_batch_quality_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        git_sha=current_git_sha,
        capability_reports=summaries,
        checks=checks,
        known_limits=[
            "This gate validates local report contracts only; it does not execute external provider calls.",
            "This gate is an audit-pack aggregator and does not replace each capability's focused gate.",
            "Passing this gate is not a public release claim.",
        ],
        next_commands=[
            "python scripts/creative_studio_external_video_gate.py",
            "python scripts/llm_governance_api_gate.py",
            "python scripts/rag_governance_api_gate.py",
            "python scripts/agent_dispatch_contract_gate.py",
            "python scripts/browser_workspace_verification_gate.py",
            "python scripts/provider_health_failover_gate.py",
            "python scripts/second_batch_quality_gate.py",
            *sorted(set(all_next_commands)),
        ],
    )


def write_report(report: QualityGateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_second_batch_quality_gate_report()
    write_report(report, args.output)
    print(f"Second batch quality gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
