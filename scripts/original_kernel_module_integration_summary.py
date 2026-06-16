#!/usr/bin/env python3
"""Aggregate original-kernel module integration evidence.

This summary is a final module-level gate before any mainline wiring. It reads
the isolated integration reports and verifies that they are ready, guarded, and
non-mutating. It does not import or execute the integrated capability modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.storage import atomic_write_json

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "original-kernel-module-integration-summary.json"


@dataclass(frozen=True)
class ExpectedReport:
    filename: str
    evidence_type: str
    ready_status: str


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


EXPECTED_REPORTS: tuple[ExpectedReport, ...] = (
    ExpectedReport(
        filename="original-kernel-minimal-integration.json",
        evidence_type="original_kernel_minimal_integration",
        ready_status="original_kernel_minimal_integration_ready",
    ),
    ExpectedReport(
        filename="original-kernel-context-integration.json",
        evidence_type="original_kernel_context_integration",
        ready_status="original_kernel_context_integration_ready",
    ),
    ExpectedReport(
        filename="original-kernel-agent-run-closure-integration.json",
        evidence_type="original_kernel_agent_run_closure_integration",
        ready_status="original_kernel_agent_run_closure_integration_ready",
    ),
    ExpectedReport(
        filename="original-kernel-long-task-integration.json",
        evidence_type="original_kernel_long_task_integration",
        ready_status="original_kernel_long_task_integration_ready",
    ),
    ExpectedReport(
        filename="original-kernel-shell-job-runner-integration.json",
        evidence_type="original_kernel_shell_job_runner_integration",
        ready_status="original_kernel_shell_job_runner_integration_ready",
    ),
    ExpectedReport(
        filename="original-kernel-pull-request-delivery-integration.json",
        evidence_type="original_kernel_pull_request_delivery_integration",
        ready_status="original_kernel_pull_request_delivery_integration_ready",
    ),
    ExpectedReport(
        filename="original-kernel-report-evidence-integration.json",
        evidence_type="original_kernel_report_evidence_integration",
        ready_status="original_kernel_report_evidence_integration_ready",
    ),
)

WIRING_FLAGS = frozenset(
    {
        "entrypoints_modified",
        "api_router_modified",
        "control_plane_modified",
        "frontend_modified",
        "agent_loop_modified",
        "backend_core_init_modified",
    }
)

EXECUTION_FLAGS = frozenset(
    {
        "agent_execution_enabled",
        "command_execution_enabled",
        "command_execution_performed",
        "shell_command_execution_performed",
        "subprocess_execution_performed",
        "valid_command_payload_executed",
        "real_tool_execution_performed",
        "real_engineering_task_execution_performed",
        "long_task_worker_enabled",
        "subagent_execution_enabled",
        "workflow_execution_enabled",
        "merge_execution_enabled",
        "real_validation_execution_performed",
        "real_pytest_execution_performed",
        "broad_pytest_execution_performed",
    }
)

MUTATION_FLAGS = frozenset(
    {
        "mutation_performed",
        "network_mutation_performed",
        "external_provider_http_performed",
        "git_push_performed",
        "real_pull_request_created",
        "existing_reports_modified",
    }
)

UNSAFE_TRUE_FLAGS = WIRING_FLAGS | EXECUTION_FLAGS | MUTATION_FLAGS
PARITY_CLAIM_FIELDS = frozenset({"full_codex_parity_claimed", "codex_parity_claimed"})


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc.msg}"
    if not isinstance(payload, dict):
        return None, "json_root_is_not_object"
    return payload, None


def _report_has_no_full_codex_parity_claim(payload: dict[str, Any]) -> bool:
    for field_name in PARITY_CLAIM_FIELDS:
        if payload.get(field_name) is True:
            return False

    known_limits = payload.get("known_limits")
    if not isinstance(known_limits, list):
        return False

    normalized_limits = [str(item).lower() for item in known_limits]
    return any(
        "no full codex parity claim" in item or "full codex parity claimed: false" in item
        for item in normalized_limits
    )


def _summarize_report(spec: ExpectedReport, reports_dir: Path) -> dict[str, Any]:
    path = reports_dir / spec.filename
    payload, error = _load_json(path)
    if payload is None:
        return {
            "filename": spec.filename,
            "path": str(path),
            "present": False,
            "ready": False,
            "evidence_type": None,
            "status": None,
            "modules": [],
            "checks_count": 0,
            "unsafe_true_flags": [],
            "missing_wiring_flags": [],
            "full_codex_parity_claimed": None,
            "error": error,
        }

    checks = payload.get("checks")
    modules = payload.get("modules")
    unsafe_true_flags = sorted(
        field_name for field_name in UNSAFE_TRUE_FLAGS if payload.get(field_name) is True
    )
    missing_wiring_flags = sorted(field_name for field_name in WIRING_FLAGS if field_name not in payload)
    has_no_parity_claim = _report_has_no_full_codex_parity_claim(payload)

    ready = all(
        [
            payload.get("status") == spec.ready_status,
            payload.get("evidence_type") == spec.evidence_type,
            isinstance(checks, list),
            all(isinstance(check, dict) and check.get("status") == "passed" for check in checks),
            not unsafe_true_flags,
            has_no_parity_claim,
        ]
    )

    return {
        "filename": spec.filename,
        "path": str(path),
        "present": True,
        "ready": ready,
        "expected_status": spec.ready_status,
        "status": payload.get("status"),
        "expected_evidence_type": spec.evidence_type,
        "evidence_type": payload.get("evidence_type"),
        "modules": modules if isinstance(modules, list) else [],
        "checks_count": len(checks) if isinstance(checks, list) else 0,
        "unsafe_true_flags": unsafe_true_flags,
        "missing_wiring_flags": missing_wiring_flags,
        "full_codex_parity_claimed": not has_no_parity_claim,
        "error": None if ready else "report is missing readiness, passed checks, safety flags, or no-parity evidence",
    }


def _expected_reports_check(report_summaries: list[dict[str, Any]]) -> IntegrationCheck:
    missing_reports = [item["filename"] for item in report_summaries if not item["present"]]
    passed = not missing_reports
    return IntegrationCheck(
        name="expected_reports_present",
        status="passed" if passed else "failed",
        details={
            "expected_report_count": len(EXPECTED_REPORTS),
            "present_report_count": len(report_summaries) - len(missing_reports),
            "missing_reports": missing_reports,
        },
        error=None if passed else "one or more expected original-kernel integration reports are missing",
    )


def _ready_reports_check(report_summaries: list[dict[str, Any]]) -> IntegrationCheck:
    not_ready = [item["filename"] for item in report_summaries if item["present"] and not item["ready"]]
    passed = not not_ready
    return IntegrationCheck(
        name="expected_reports_ready",
        status="passed" if passed else "failed",
        details={
            "ready_report_count": sum(1 for item in report_summaries if item["ready"]),
            "not_ready_reports": not_ready,
        },
        error=None if passed else "one or more original-kernel integration reports are not ready",
    )


def _unsafe_flags_check(report_summaries: list[dict[str, Any]]) -> IntegrationCheck:
    unsafe_reports = {
        item["filename"]: item["unsafe_true_flags"]
        for item in report_summaries
        if item["unsafe_true_flags"]
    }
    passed = not unsafe_reports
    return IntegrationCheck(
        name="no_real_execution_or_mutation_enabled",
        status="passed" if passed else "failed",
        details={
            "unsafe_report_count": len(unsafe_reports),
            "unsafe_reports": unsafe_reports,
        },
        error=None if passed else "one or more reports enabled a wiring, execution, or mutation flag",
    )


def _parity_claim_check(report_summaries: list[dict[str, Any]]) -> IntegrationCheck:
    parity_claims = [
        item["filename"] for item in report_summaries if item["full_codex_parity_claimed"] is True
    ]
    passed = not parity_claims
    return IntegrationCheck(
        name="no_full_codex_parity_claimed",
        status="passed" if passed else "failed",
        details={
            "parity_claim_report_count": len(parity_claims),
            "parity_claim_reports": parity_claims,
        },
        error=None if passed else "one or more reports claim full Codex parity",
    )


def build_report(*, reports_dir: str | Path = REPORT_DIR) -> dict[str, Any]:
    report_dir_path = Path(reports_dir)
    report_summaries = [_summarize_report(spec, report_dir_path) for spec in EXPECTED_REPORTS]
    module_names = sorted(
        {
            str(module)
            for summary in report_summaries
            for module in summary.get("modules", [])
            if isinstance(module, str)
        }
    )
    checks = [
        _expected_reports_check(report_summaries),
        _ready_reports_check(report_summaries),
        _unsafe_flags_check(report_summaries),
        _parity_claim_check(report_summaries),
    ]
    all_passed = all(check.status == "passed" for check in checks)

    return {
        "status": "original_kernel_module_integration_summary_ready" if all_passed else "failed",
        "generated_at": _utc_now(),
        "evidence_type": "original_kernel_module_integration_summary",
        "reports_dir": str(report_dir_path),
        "expected_report_count": len(EXPECTED_REPORTS),
        "ready_report_count": sum(1 for item in report_summaries if item["ready"]),
        "modules": module_names,
        "entrypoints_modified": False,
        "api_router_modified": False,
        "control_plane_modified": False,
        "frontend_modified": False,
        "agent_loop_modified": False,
        "backend_core_init_modified": False,
        "mutation_performed": False,
        "report_file_written": False,
        "network_mutation_performed": False,
        "agent_execution_enabled": False,
        "command_execution_enabled": False,
        "real_execution_or_mutation_enabled": False,
        "full_codex_parity_claimed": False,
        "mainline_wiring_enabled": False,
        "summary_reads_reports_only": True,
        "report_summaries": report_summaries,
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report aggregates original-kernel module-level integration evidence only.",
            "No API router, agent loop, control plane, frontend, or backend core package entrypoint is wired by this report.",
            "No real agent execution, shell execution, provider HTTP call, git push, pull request creation, or broad pytest execution is enabled.",
            "No full Codex parity claim is made by this report.",
            "The next phase should be explicit review, selective staging, or a separately designed mainline wiring plan.",
        ],
        "next_actions": [
            "Review and stage only the original-kernel module integration files explicitly.",
            "Design any future mainline wiring as a separate owner-gated task.",
        ],
    }


def write_report(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    reports_dir: str | Path = REPORT_DIR,
) -> dict[str, Any]:
    report = build_report(reports_dir=reports_dir)
    report["report_file_written"] = True
    report["report_path"] = str(output_path)
    atomic_write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORT_DIR,
        help="Directory containing original-kernel integration reports.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write the JSON summary report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_report(args.output, reports_dir=args.reports_dir)

    print(f"Original kernel module integration summary status: {report['status']}")
    print(f"Report written to {args.output}")
    print(f"Ready reports: {report['ready_report_count']}/{report['expected_report_count']}")
    for check in report["checks"]:
        print(f"- {check['name']}: {check['status']}")
        if check.get("error"):
            print(f"  error: {check['error']}")

    return 0 if report["status"] == "original_kernel_module_integration_summary_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
