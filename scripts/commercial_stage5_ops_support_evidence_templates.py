#!/usr/bin/env python3
"""Generate blocked Stage 5 Ops / Support evidence templates.

These templates are operator work items, not evidence. They intentionally keep
Ops / Support gates blocked until real operational, support, and ownership
evidence is collected by an owner or environment operator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.commercial_ops_support_gate import default_required_evidence
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT

DEFAULT_OUTPUT_JSON = REPORT_DIR / "controller-stage5-ops-support-templates-worker-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "controller-stage5-ops-support-templates-worker-20260615.md"


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
    templates: list[TemplateWriteResult] = field(default_factory=list)
    ops_support_gate_expected_status: str = "ops_support_blocked"
    ops_support_evidence_pack_expected_status: str = "ops_support_evidence_blocked"
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


def _base_template(
    *,
    evidence_name: str,
    filename: str,
    evidence_reason: str,
    expected_ready_statuses: list[str],
    current_head_sha: str | None,
    release_sha: str | None,
    required_owner_or_operator_actions: list[str],
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "evidence_name": evidence_name,
        "template_filename": filename,
        "evidence_reason": evidence_reason,
        "template_not_evidence": True,
        "real_evidence_collected": False,
        "mutation_performed": False,
        "deploy_performed": False,
        "owner_approval_created": False,
        "current_head_sha": current_head_sha,
        "release_sha": release_sha,
        "expected_ready_statuses": expected_ready_statuses,
        "required_owner_or_operator_actions": required_owner_or_operator_actions,
        "blocking_reason": (
            "Blocked skeleton only. Replace this file with real Ops / Support evidence "
            "before using it for Stage 5 Ops / Support gates."
        ),
    }


def _domain_placeholders() -> dict[str, dict[str, Any]]:
    return {
        "slo_sla": {
            "required_owner_or_operator_actions": [
                "Define service level objectives and support response targets for the selected release SHA.",
                "Attach measurement windows, error budget policy, and customer-impact thresholds.",
                "Replace this template with a real SLO/SLA evidence report.",
            ],
            "placeholders": {
                "slo_targets": [],
                "sla_targets": [],
                "measurement_window": "",
                "error_budget_policy": "",
                "customer_support_response_targets": [],
            },
        },
        "alert_routing": {
            "required_owner_or_operator_actions": [
                "Map alert severities to routed notification channels and named receivers.",
                "Run or cite a receiver-routing test for the selected release SHA.",
                "Replace this template with a real alert routing evidence report.",
            ],
            "placeholders": {
                "severity_mapping": [],
                "notification_channels": [],
                "receiver_owners": [],
                "routing_test_result": "",
            },
        },
        "backup_restore_rehearsal": {
            "required_owner_or_operator_actions": [
                "Run a backup and restore rehearsal against the owner-approved environment.",
                "Record RPO, RTO, restored dataset identity, and verification outcome.",
                "Replace this template with a real backup/restore rehearsal evidence report.",
            ],
            "placeholders": {
                "backup_artifact": "",
                "restore_environment": "",
                "rpo_target": "",
                "rto_target": "",
                "verification_outcome": "",
            },
        },
        "incident_process": {
            "required_owner_or_operator_actions": [
                "Document incident declaration, triage, communications, and postmortem flow.",
                "Identify severity levels, decision owners, and customer communication triggers.",
                "Replace this template with a real incident process evidence report.",
            ],
            "placeholders": {
                "severity_levels": [],
                "triage_process": "",
                "communications_process": "",
                "postmortem_process": "",
                "decision_owners": [],
            },
        },
        "support_escalation": {
            "required_owner_or_operator_actions": [
                "Document customer support escalation path and owner handoff rules.",
                "Identify escalation contacts, response windows, and customer-impact routing.",
                "Replace this template with a real support escalation evidence report.",
            ],
            "placeholders": {
                "support_tiers": [],
                "escalation_contacts": [],
                "owner_handoff_rules": "",
                "customer_impact_routing": "",
            },
        },
        "cost_capacity_guardrails": {
            "required_owner_or_operator_actions": [
                "Define cost budgets, capacity thresholds, throttling policy, and scale limits.",
                "Attach monitor or dashboard references that prove guardrails exist.",
                "Replace this template with a real cost/capacity guardrails evidence report.",
            ],
            "placeholders": {
                "cost_budgets": [],
                "capacity_thresholds": [],
                "throttling_policy": "",
                "scale_guardrails": [],
                "monitor_refs": [],
            },
        },
        "on_call_ownership": {
            "required_owner_or_operator_actions": [
                "Document on-call schedule, service owner, backup owner, and escalation coverage.",
                "Attach owner-approved rotation evidence for the selected release SHA.",
                "Replace this template with a real on-call ownership evidence report.",
            ],
            "placeholders": {
                "service_owner": "",
                "primary_on_call": "",
                "backup_owner": "",
                "rotation_schedule_ref": "",
                "escalation_coverage": "",
            },
        },
    }


def build_template_payloads(
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build blocked Ops / Support template payloads keyed by target filename."""

    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    placeholders_by_name = _domain_placeholders()

    payloads: dict[str, dict[str, Any]] = {}
    for spec in default_required_evidence(Path(report_dir)):
        filename = spec.path.name
        domain = placeholders_by_name[spec.name]
        payloads[filename] = {
            **_base_template(
                evidence_name=spec.name,
                filename=filename,
                evidence_reason=spec.reason,
                expected_ready_statuses=sorted(spec.expected_statuses),
                current_head_sha=resolved_head,
                release_sha=resolved_release_sha,
                required_owner_or_operator_actions=list(domain["required_owner_or_operator_actions"]),
            ),
            **domain["placeholders"],
            "evidence_refs": [],
            "summary": (
                "Blocked Ops / Support evidence template. This is not proof of operational readiness."
            ),
            "notes": "Do not change status to a ready value until real owner/operator evidence is collected.",
        }

    return payloads


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
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    results: list[TemplateWriteResult] = []

    for spec in default_required_evidence(report_dir):
        filename = spec.path.name
        path = spec.path
        if path.exists() and not force:
            results.append(
                TemplateWriteResult(
                    name=spec.name,
                    path=_display_path(path),
                    status="skipped_existing",
                    written=False,
                    skipped_existing=True,
                    force=force,
                )
            )
            continue
        if path.exists() and force and not _existing_file_is_template(path):
            results.append(
                TemplateWriteResult(
                    name=spec.name,
                    path=_display_path(path),
                    status="skipped_existing_real_evidence",
                    written=False,
                    skipped_existing=True,
                    force=force,
                    error="existing file is not a blocked template; refusing to overwrite with --force",
                )
            )
            continue

        path.write_text(json.dumps(payloads[filename], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            TemplateWriteResult(
                name=spec.name,
                path=_display_path(path),
                status="written",
                written=True,
                skipped_existing=False,
                force=force,
            )
        )

    return results


def _report_status(results: list[TemplateWriteResult]) -> str:
    if all(result.status == "dry_run" for result in results):
        return "ops_support_evidence_templates_dry_run"
    if any(result.error for result in results):
        return "ops_support_evidence_templates_blocked"
    if all(result.written for result in results):
        return "ops_support_evidence_templates_written"
    if any(result.written for result in results):
        return "ops_support_evidence_templates_partial"
    return "ops_support_evidence_templates_unchanged"


def build_worker_report(
    results: list[TemplateWriteResult],
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
        templates=results,
        next_actions=[
            "Owner/operator must replace blocked templates with real Ops / Support evidence.",
            "Ops / Support gate and evidence pack must remain blocked while these templates are present.",
        ],
    )


def render_markdown_report(report: TemplateWorkerReport) -> str:
    template_lines = "\n".join(
        f"- {item.name}: `{item.status}` at `{item.path}`"
        for item in report.templates
    ) or "- none"
    return (
        "# Stage 5 Ops / Support Evidence Templates Worker\n\n"
        f"- Status: `{report.status}`\n"
        f"- Template not evidence: `{report.template_not_evidence}`\n"
        f"- Real evidence collected: `{report.real_evidence_collected}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Owner approval created: `{report.owner_approval_created}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Ops / Support gate expected status: `{report.ops_support_gate_expected_status}`\n"
        f"- Ops / Support evidence pack expected status: `{report.ops_support_evidence_pack_expected_status}`\n\n"
        "## Templates\n\n"
        f"{template_lines}\n"
    )


def write_report(report: TemplateWorkerReport, output_path: Path = DEFAULT_OUTPUT_JSON) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: TemplateWorkerReport, output_path: Path = DEFAULT_OUTPUT_MD) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate blocked Stage 5 Ops / Support evidence templates.")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
    print(f"Stage 5 Ops / Support evidence templates status: {report.status}")
    print(f"Template not evidence: {report.template_not_evidence}")
    print(f"Real evidence collected: {report.real_evidence_collected}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
