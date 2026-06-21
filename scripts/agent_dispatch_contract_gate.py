#!/usr/bin/env python3
"""Validate second-batch multi-agent dispatch contract controls."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.agent_dispatch_contracts import build_default_second_batch_dispatch_contract

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "agent-dispatch-contract-gate.json"


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
    contract_summary: dict[str, Any]
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


def build_agent_dispatch_contract_gate_report() -> GateReport:
    contract = build_default_second_batch_dispatch_contract()
    validation = contract.validate()
    handoff_summaries = [
        {
            "task_id": handoff.task_id,
            "target_agent": handoff.target_agent,
            "timeout_seconds": handoff.timeout_seconds,
            "max_cost_usd": handoff.max_cost_usd,
            "max_retries": handoff.max_retries,
            "required_artifact_count": len(handoff.required_artifacts),
        }
        for handoff in contract.handoffs
    ]
    checks = [
        _check("contract_validates", validation["valid"], details=validation, error="dispatch contract validation failed"),
        _check(
            "handoffs_are_bounded",
            all(item["timeout_seconds"] > 0 and item["max_cost_usd"] >= 0 for item in handoff_summaries),
            details={"handoffs": handoff_summaries},
            error="one or more handoffs lack timeout or cost bounds",
        ),
        _check(
            "retry_policy_is_bounded",
            all(item["max_retries"] <= 2 for item in handoff_summaries),
            error="one or more handoffs have unbounded retry policy",
        ),
        _check(
            "fan_in_trace_and_audit_required",
            validation["fan_in_required"] is True
            and validation["trace_required"] is True
            and validation["audit_required"] is True,
            error="dispatch contract does not require fan-in, trace, and audit",
        ),
        _check(
            "handoff_outputs_are_explicit",
            all(item["required_artifact_count"] > 0 for item in handoff_summaries),
            error="one or more handoffs have no required output artifacts",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return GateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="agent_dispatch_contract_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        contract_summary={
            "workflow_id": contract.workflow_id,
            "pattern": contract.pattern,
            "handoff_count": len(contract.handoffs),
            "max_parallel_agents": contract.max_parallel_agents,
            "total_cost_budget_usd": contract.total_cost_budget_usd,
            "validation": validation,
        },
        checks=checks,
        known_limits=[
            "This gate validates dispatch contracts only; it does not spawn agents.",
            "Runtime dispatcher integration can build on this contract in a later slice.",
        ],
        next_commands=[
            "python scripts/agent_dispatch_contract_gate.py",
            "python -m pytest tests/test_agent_dispatch_contract_gate.py -q --no-cov",
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
    report = build_agent_dispatch_contract_gate_report()
    write_report(report, args.output)
    print(f"Agent dispatch contract gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
