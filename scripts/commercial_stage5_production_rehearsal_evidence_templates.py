#!/usr/bin/env python3
"""Generate blocked Stage 5 production rehearsal evidence templates.

These templates are operator work items, not evidence. They intentionally keep
the production rehearsal gate blocked until real production or
production-equivalent deploy, smoke, rollback, observability, and approval
evidence is collected by an owner or environment operator.
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

from scripts.commercial_environment_rehearsal_gate import (
    REPORT_DIR,
    RehearsalEvidenceSpec,
    default_evidence_specs,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = REPORT_DIR / "controller-stage5-production-rehearsal-templates-worker-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "controller-stage5-production-rehearsal-templates-worker-20260615.md"
ENVIRONMENT = "production"


@dataclass(frozen=True)
class TemplateWriteResult:
    name: str
    path: str
    status: str
    written: bool
    skipped_existing: bool
    force: bool
    error: str | None = None


@dataclass(frozen=True)
class TemplateWorkerReport:
    status: str
    generated_at: str
    report_dir: str
    current_head_sha: str | None
    release_sha: str | None
    template_not_evidence: bool
    real_evidence_collected: bool
    mutation_performed: bool
    deploy_performed: bool
    owner_approval_created: bool
    workflow_dispatch_performed: bool
    templates: list[TemplateWriteResult] = field(default_factory=list)
    production_rehearsal_gate_expected_status: str = "production_rehearsal_blocked"
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["templates"] = [asdict(item) for item in self.templates]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_head(root: Path = ROOT) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
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


def _display_path(path: Path, *, root: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
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


def _actions_for_spec(spec: RehearsalEvidenceSpec) -> list[str]:
    actions_by_name = {
        "production_deploy_rehearsal": [
            "Run or obtain the authorized production or production-equivalent deploy rehearsal for the selected release SHA.",
            "Record the deployment target, operator, timestamps, outcome, and immutable run URL or transcript.",
            "Replace this template with real deploy rehearsal evidence before rerunning the production rehearsal gate.",
        ],
        "production_smoke_tests": [
            "Run production health, readiness, auth, API, frontend, and Panda BFF smoke checks for the selected release SHA.",
            "Record command output, target endpoints, operator, timestamps, and pass/fail evidence.",
            "Replace this template with real smoke test evidence before rerunning the production rehearsal gate.",
        ],
        "production_rollback_rehearsal": [
            "Run or obtain the authorized production rollback rehearsal or production-equivalent rollback proof.",
            "Record rollback target, rollback procedure, operator, timestamps, and recovery result.",
            "Replace this template with real rollback rehearsal evidence before rerunning the production rehearsal gate.",
        ],
        "production_observability": [
            "Collect production logs, metrics, traces, dashboards, and alert visibility proof for the selected release SHA.",
            "Record durable links or exported artifacts showing release visibility and alert coverage.",
            "Replace this template with real observability evidence before rerunning the production rehearsal gate.",
        ],
        "production_release_approval": [
            "Obtain owner-approved production release rehearsal decision evidence for the selected release SHA.",
            "Record accountable owner, approval timestamp, scope, rationale, and any explicit constraints.",
            "Replace this template with real owner approval evidence before rerunning the production rehearsal gate.",
        ],
    }
    return actions_by_name.get(
        spec.name,
        [
            f"Collect real production rehearsal evidence for {spec.name}.",
            "Replace this blocked template with a real evidence report before rerunning the gate.",
        ],
    )


def _base_template(
    *,
    spec: RehearsalEvidenceSpec,
    current_head_sha: str | None,
    release_sha: str | None,
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "environment": ENVIRONMENT,
        "evidence_name": spec.name,
        "evidence_path": str(spec.path),
        "template_filename": spec.path.name,
        "template_not_evidence": True,
        "real_evidence_collected": False,
        "mutation_performed": False,
        "deploy_performed": False,
        "owner_approval_created": False,
        "workflow_dispatch_performed": False,
        "current_head_sha": current_head_sha,
        "release_sha": release_sha,
        "expected_ready_statuses": list(spec.expected_statuses),
        "required_owner_or_operator_actions": _actions_for_spec(spec),
        "reason": spec.reason,
        "blocking_reason": (
            "Blocked skeleton only. Replace this file with real production rehearsal evidence "
            "before using it for Stage 5 production rehearsal gates."
        ),
    }


def build_template_payloads(
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build blocked production rehearsal template payloads keyed by filename."""

    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    specs = default_evidence_specs(ENVIRONMENT, Path(report_dir))
    return {
        spec.path.name: _base_template(
            spec=spec,
            current_head_sha=resolved_head,
            release_sha=resolved_release_sha,
        )
        for spec in specs
    }


def write_templates(
    report_dir: Path = REPORT_DIR,
    *,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    force: bool = False,
) -> list[TemplateWriteResult]:
    payloads = build_template_payloads(
        report_dir=report_dir,
        current_head_sha=current_head_sha,
        release_sha=release_sha,
    )
    specs = default_evidence_specs(ENVIRONMENT, Path(report_dir))
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    results: list[TemplateWriteResult] = []

    for spec in specs:
        payload = payloads[spec.path.name]
        if spec.path.exists() and not force:
            results.append(
                TemplateWriteResult(
                    name=spec.name,
                    path=_display_path(spec.path),
                    status="skipped_existing",
                    written=False,
                    skipped_existing=True,
                    force=force,
                )
            )
            continue
        if spec.path.exists() and force and not _existing_file_is_template(spec.path):
            results.append(
                TemplateWriteResult(
                    name=spec.name,
                    path=_display_path(spec.path),
                    status="skipped_existing_real_evidence",
                    written=False,
                    skipped_existing=True,
                    force=force,
                    error="existing file is not a blocked template; refusing to overwrite with --force",
                )
            )
            continue

        spec.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            TemplateWriteResult(
                name=spec.name,
                path=_display_path(spec.path),
                status="written",
                written=True,
                skipped_existing=False,
                force=force,
            )
        )

    return results


def _report_status(results: Sequence[TemplateWriteResult]) -> str:
    if all(result.status == "dry_run" for result in results):
        return "production_rehearsal_evidence_templates_dry_run"
    if any(result.error for result in results):
        return "production_rehearsal_evidence_templates_blocked"
    if all(result.written for result in results):
        return "production_rehearsal_evidence_templates_written"
    if any(result.written for result in results):
        return "production_rehearsal_evidence_templates_partial"
    return "production_rehearsal_evidence_templates_unchanged"


def build_worker_report(
    results: Sequence[TemplateWriteResult],
    *,
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> TemplateWorkerReport:
    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    return TemplateWorkerReport(
        status=_report_status(results),
        generated_at=_utc_now(),
        report_dir=_display_path(Path(report_dir)),
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        template_not_evidence=True,
        real_evidence_collected=False,
        mutation_performed=False,
        deploy_performed=False,
        owner_approval_created=False,
        workflow_dispatch_performed=False,
        templates=list(results),
        next_actions=[
            "Owner/operator must replace blocked templates with real production rehearsal evidence.",
            "The production rehearsal gate must remain blocked while these templates are present.",
        ],
    )


def render_markdown_report(report: TemplateWorkerReport) -> str:
    template_lines = "\n".join(
        f"- {item.name}: `{item.status}` at `{item.path}`"
        for item in report.templates
    ) or "- none"
    return (
        "# Stage 5 Production Rehearsal Evidence Templates Worker\n\n"
        f"- Status: `{report.status}`\n"
        f"- Template not evidence: `{report.template_not_evidence}`\n"
        f"- Real evidence collected: `{report.real_evidence_collected}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Owner approval created: `{report.owner_approval_created}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Production rehearsal gate expected status: `{report.production_rehearsal_gate_expected_status}`\n\n"
        "## Templates\n\n"
        f"{template_lines}\n"
    )


def write_report(report: TemplateWorkerReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: TemplateWorkerReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate blocked Stage 5 production rehearsal evidence templates.")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--write-templates",
        action="store_true",
        help="Materialize blocked skeleton files. Default is a dry-run summary only.",
    )
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write_templates:
        results = write_templates(
            args.report_dir,
            current_head_sha=args.current_head_sha,
            release_sha=args.release_sha,
            force=args.force,
        )
    else:
        payloads = build_template_payloads(
            args.report_dir,
            current_head_sha=args.current_head_sha,
            release_sha=args.release_sha,
        )
        results = [
            TemplateWriteResult(
                name=payload["evidence_name"],
                path=_display_path(args.report_dir / filename),
                status="dry_run",
                written=False,
                skipped_existing=False,
                force=args.force,
            )
            for filename, payload in payloads.items()
        ]
    report = build_worker_report(
        results,
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 production rehearsal evidence templates status: {report.status}")
    print(f"Template not evidence: {report.template_not_evidence}")
    print(f"Real evidence collected: {report.real_evidence_collected}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
