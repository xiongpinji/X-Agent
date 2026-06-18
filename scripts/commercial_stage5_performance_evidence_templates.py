#!/usr/bin/env python3
"""Generate blocked Stage 5 performance evidence templates.

These templates are operator scaffolds only. They intentionally keep the
performance/capacity gate blocked until replaced with real, ready evidence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.commercial_performance_capacity_gate import (
    REPORT_DIR,
    ROOT,
    RequiredPerformanceEvidenceSpec,
    default_required_evidence,
)

DEFAULT_OUTPUT_JSON = REPORT_DIR / "controller-stage5-performance-templates-worker-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "controller-stage5-performance-templates-worker-20260615.md"


@dataclass(frozen=True)
class TemplateWriteResult:
    name: str
    path: str
    status: str
    written: bool
    force: bool
    template_not_evidence: bool = True
    real_evidence_collected: bool = False
    mutation_performed: bool = False
    deploy_performed: bool = False
    owner_approval_created: bool = False
    error: str | None = None


@dataclass(frozen=True)
class PerformanceTemplateReport:
    status: str
    generated_at: str
    evidence_type: str
    template_not_evidence: bool
    real_evidence_collected: bool
    mutation_performed: bool
    deploy_performed: bool
    owner_approval_created: bool
    current_head_sha: str | None
    release_sha: str | None
    report_dir: str
    force: bool
    dry_run: bool
    templates: list[dict[str, Any]]
    write_results: list[TemplateWriteResult]
    required_owner_or_operator_actions: list[str]
    known_limits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["write_results"] = [asdict(result) for result in self.write_results]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_head() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _existing_file_is_template(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("template_not_evidence") is True and payload.get("real_evidence_collected") is False


def _domain_placeholders(name: str) -> dict[str, Any]:
    if name == "load_performance_test":
        return {
            "load_test": {
                "test_run_url": None,
                "run_id": None,
                "tool": None,
                "scenario": None,
                "duration_minutes": None,
                "total_requests": None,
                "artifact_paths": [],
            },
            "results": {},
        }
    if name == "capacity_target":
        return {
            "capacity_target": {
                "target_rps": None,
                "concurrent_users": None,
                "workload_mix": None,
                "duration_minutes": None,
                "rationale": None,
            }
        }
    if name == "latency_error_rate_thresholds":
        return {
            "metrics": {
                "latency_p95_ms": None,
                "latency_p99_ms": None,
                "error_rate": None,
            },
            "thresholds": {
                "max_latency_p95_ms": None,
                "max_latency_p99_ms": None,
                "max_error_rate": None,
            },
        }
    if name == "cost_guardrail":
        return {
            "cost_guardrail": {
                "estimated_monthly_cost": None,
                "max_monthly_cost": None,
                "currency": None,
                "assumptions": [],
            }
        }
    if name == "performance_tests_skipped_disposition":
        return {
            "performance_tests_skipped_disposition": False,
            "skipped_check": "performance-tests",
            "disposition": None,
            "accepted_by": None,
            "acceptance_reference": None,
        }
    if name == "resource_sizing":
        return {
            "resource_sizing": {
                "replicas": None,
                "cpu": None,
                "memory": None,
                "workers": None,
                "queues": None,
                "autoscaling": None,
            }
        }
    return {"evidence": {}}


def _required_actions(name: str) -> list[str]:
    actions = {
        "load_performance_test": [
            "Run the agreed load/performance test suite for the release candidate.",
            "Replace this template with the real test run URL, run ID, workload, and result artifact paths.",
        ],
        "capacity_target": [
            "Document the release target throughput, concurrency, workload mix, and capacity rationale.",
            "Replace this template with owner/operator-reviewed capacity target evidence.",
        ],
        "latency_error_rate_thresholds": [
            "Collect measured p95/p99 latency and error-rate results for the release candidate.",
            "Replace this template with threshold values and measurements that prove the release is within limits.",
        ],
        "cost_guardrail": [
            "Calculate the projected runtime cost for the selected sizing and traffic target.",
            "Replace this template with the approved cost ceiling, projection, currency, and assumptions.",
        ],
        "performance_tests_skipped_disposition": [
            "If the remote performance-tests check was skipped, record the explicit owner/operator disposition.",
            "Replace this template with the accepted skipped-check disposition and approval reference.",
        ],
        "resource_sizing": [
            "Record CPU, memory, replica, worker, queue, and autoscaling sizing for the release candidate.",
            "Replace this template with measured or operator-approved resource sizing evidence.",
        ],
    }
    return actions.get(name, ["Replace this blocked template with real ready evidence."])


def _template_payload(
    spec: RequiredPerformanceEvidenceSpec,
    *,
    current_head_sha: str | None,
    release_sha: str | None,
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "evidence_type": "stage5_performance_capacity_evidence_template",
        "name": spec.name,
        "path": _display_path(spec.path),
        "template_not_evidence": True,
        "real_evidence_collected": False,
        "mutation_performed": False,
        "deploy_performed": False,
        "owner_approval_created": False,
        "current_head_sha": current_head_sha,
        "release_sha": release_sha,
        "expected_ready_statuses": list(spec.expected_statuses),
        "evidence_level": spec.evidence_level,
        "reason": spec.reason,
        "required_owner_or_operator_actions": _required_actions(spec.name),
        "placeholders": _domain_placeholders(spec.name),
    }


def build_template_payloads(
    report_dir: Path = REPORT_DIR,
    *,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> list[dict[str, Any]]:
    current_head_sha = current_head_sha or _git_head()
    release_sha = release_sha or current_head_sha
    return [
        _template_payload(spec, current_head_sha=current_head_sha, release_sha=release_sha)
        for spec in default_required_evidence(report_dir)
    ]


def _result_from_payload(
    payload: dict[str, Any],
    *,
    status: str,
    written: bool,
    force: bool,
    error: str | None = None,
) -> TemplateWriteResult:
    return TemplateWriteResult(
        name=str(payload["name"]),
        path=str(payload["path"]),
        status=status,
        written=written,
        force=force,
        error=error,
    )


def write_templates(
    report_dir: Path = REPORT_DIR,
    *,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    force: bool = False,
) -> list[TemplateWriteResult]:
    payloads = build_template_payloads(
        report_dir,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    specs_by_name = {spec.name: spec for spec in default_required_evidence(report_dir)}
    results: list[TemplateWriteResult] = []
    for payload in payloads:
        spec = specs_by_name[str(payload["name"])]
        existed = spec.path.exists()
        if existed and not force:
            results.append(_result_from_payload(payload, status="skipped_existing", written=False, force=force))
            continue
        if existed and force and not _existing_file_is_template(spec.path):
            results.append(
                _result_from_payload(
                    payload,
                    status="skipped_existing_real_evidence",
                    written=False,
                    force=force,
                    error="existing file is not a blocked template; refusing to overwrite with --force",
                )
            )
            continue
        spec.path.parent.mkdir(parents=True, exist_ok=True)
        spec.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            _result_from_payload(
                payload,
                status="overwritten" if force and existed else "created",
                written=True,
                force=force,
            )
        )
    return results


def _dry_run_results(payloads: Sequence[dict[str, Any]], *, force: bool) -> list[TemplateWriteResult]:
    return [
        _result_from_payload(payload, status="dry_run", written=False, force=force)
        for payload in payloads
    ]


def build_report(
    *,
    report_dir: Path = REPORT_DIR,
    payloads: Sequence[dict[str, Any]] | None = None,
    write_results: Sequence[TemplateWriteResult] | None = None,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> PerformanceTemplateReport:
    payload_list = list(
        payloads
        or build_template_payloads(
            report_dir,
            current_head_sha=current_head_sha,
            release_sha=release_sha,
        )
    )
    if current_head_sha is None and payload_list:
        current_head_sha = payload_list[0].get("current_head_sha")
    if release_sha is None and payload_list:
        release_sha = payload_list[0].get("release_sha")
    result_list = list(write_results or _dry_run_results(payload_list, force=force))
    result_statuses = {result.status for result in result_list}
    if dry_run:
        status = "performance_evidence_templates_dry_run"
    elif any(result.error for result in result_list):
        status = "performance_evidence_templates_blocked"
    elif result_statuses == {"skipped_existing"}:
        status = "performance_evidence_templates_skipped_existing"
    else:
        status = "performance_evidence_templates_written"
    return PerformanceTemplateReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="stage5_performance_capacity_evidence_templates",
        template_not_evidence=True,
        real_evidence_collected=False,
        mutation_performed=False,
        deploy_performed=False,
        owner_approval_created=False,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
        report_dir=_display_path(report_dir),
        force=force,
        dry_run=dry_run,
        templates=payload_list,
        write_results=result_list,
        required_owner_or_operator_actions=[
            "Replace each blocked template with real performance/capacity evidence before rerunning the gate.",
            "Keep the performance/capacity gate and evidence pack blocked while template_not_evidence is true.",
            "Do not use this generator to create owner approval, deploy, tag, release, or workflow side effects.",
        ],
        known_limits=[
            "Generated skeletons are templates, not evidence.",
            "All skeleton statuses are blocked and are intentionally outside each domain's expected ready statuses.",
            "The generator does not run load tests, calculate cost, size infrastructure, or approve skipped checks.",
        ],
    )


def render_markdown_report(report: PerformanceTemplateReport) -> str:
    templates = "\n".join(
        f"- {item['name']}: `{item['status']}` / path `{item['path']}` / "
        f"expected ready `{', '.join(item['expected_ready_statuses'])}`"
        for item in report.templates
    )
    results = "\n".join(
        f"- {item.name}: `{item.status}` / written `{item.written}` / path `{item.path}`"
        + (f" - {item.error}" if item.error else "")
        for item in report.write_results
    )
    actions = "\n".join(f"- {item}" for item in report.required_owner_or_operator_actions)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# Stage 5 Performance Evidence Templates\n\n"
        f"- Status: `{report.status}`\n"
        f"- Template not evidence: `{report.template_not_evidence}`\n"
        f"- Real evidence collected: `{report.real_evidence_collected}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Force: `{report.force}`\n"
        f"- Dry run: `{report.dry_run}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Owner approval created: `{report.owner_approval_created}`\n\n"
        "## Templates\n\n"
        f"{templates}\n\n"
        "## Write Results\n\n"
        f"{results}\n\n"
        "## Required Actions\n\n"
        f"{actions}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: PerformanceTemplateReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: PerformanceTemplateReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--write-templates",
        action="store_true",
        help="Materialize blocked skeleton files. Default is a dry-run summary only.",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payloads = build_template_payloads(
        args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    dry_run = args.dry_run or not args.write_templates
    if dry_run:
        results = _dry_run_results(payloads, force=args.force)
    else:
        results = write_templates(
            args.report_dir,
            current_head_sha=args.current_head_sha,
            release_sha=args.release_sha,
            force=args.force,
        )
    report = build_report(
        report_dir=args.report_dir,
        payloads=payloads,
        write_results=results,
        current_head_sha=payloads[0].get("current_head_sha") if payloads else args.current_head_sha,
        release_sha=payloads[0].get("release_sha") if payloads else args.release_sha,
        force=args.force,
        dry_run=dry_run,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 performance evidence template status: {report.status}")
    print(f"Template not evidence: {report.template_not_evidence}")
    print(f"Real evidence collected: {report.real_evidence_collected}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Deploy performed: {report.deploy_performed}")
    print(f"Owner approval created: {report.owner_approval_created}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    for result in report.write_results:
        print(f"- {result.name}: {result.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
