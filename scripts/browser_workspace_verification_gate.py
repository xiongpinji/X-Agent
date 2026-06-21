#!/usr/bin/env python3
"""Build a replayable browser/workspace verification harness report."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "browser-workspace-verification-gate.json"


@dataclass(frozen=True)
class VerificationStep:
    step_id: str
    command: str
    evidence_path: str
    requires_browser: bool = False
    network_mutation_allowed: bool = False


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
    replay_steps: list[dict[str, Any]]
    checks: list[GateCheck]
    known_limits: list[str]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None, error: str) -> GateCheck:
    return GateCheck(name=name, status="passed" if ok else "failed", details=details or {}, error=None if ok else error)


def _default_steps() -> list[VerificationStep]:
    return [
        VerificationStep(
            step_id="api_gate_pack",
            command="python scripts/second_batch_quality_gate.py",
            evidence_path=".xagent_runtime/reports/second-batch-quality-gate.json",
        ),
        VerificationStep(
            step_id="frontend_contracts",
            command="cd frontend && npm run verify:creative-studio:contracts && npm run type-check",
            evidence_path="frontend/dist",
        ),
        VerificationStep(
            step_id="optional_browser_smoke",
            command="cd frontend && npm run build",
            evidence_path="frontend/dist/index.html",
            requires_browser=False,
        ),
    ]


def build_browser_workspace_verification_gate_report() -> GateReport:
    steps = _default_steps()
    step_payload = [asdict(step) for step in steps]
    checks = [
        _check(
            "replay_steps_are_defined",
            bool(steps) and all(step.step_id and step.command and step.evidence_path for step in steps),
            details={"step_count": len(steps)},
            error="verification harness has no replayable steps",
        ),
        _check(
            "network_mutation_is_disabled",
            all(step.network_mutation_allowed is False for step in steps),
            error="one or more verification steps allow network mutation",
        ),
        _check(
            "ai_exploration_is_not_final_proof",
            all("ai" not in step.step_id.lower() for step in steps),
            error="verification harness relies on AI exploration as final proof",
        ),
        _check(
            "evidence_paths_are_local",
            all(not step.evidence_path.startswith(("http://", "https://")) for step in steps),
            error="verification evidence must be local/replayable",
        ),
        _check(
            "workspace_commands_are_replayable",
            all("python " in step.command or "npm " in step.command or "cd frontend" in step.command for step in steps),
            error="one or more commands are not replayable workspace commands",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="browser_workspace_verification_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        replay_steps=step_payload,
        checks=checks,
        known_limits=[
            "This harness defines replayable local verification steps; it does not launch a browser by itself.",
            "Visual/browser execution should attach screenshots or traces in a later run when a UI server is active.",
        ],
        next_commands=[
            "python scripts/browser_workspace_verification_gate.py",
            "python -m pytest tests/test_browser_workspace_verification_gate.py -q --no-cov",
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
    report = build_browser_workspace_verification_gate_report()
    write_report(report, args.output)
    print(f"Browser/workspace verification gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
