#!/usr/bin/env python3
"""Build a fail-closed Stage 5 environment rehearsal evidence pack.

This script is read-only with respect to real environments. It summarizes
staging and production rehearsal result reports, binds them to one release SHA,
and writes JSON/Markdown evidence-pack reports. It never deploys, tags,
releases, dispatches workflows, or mutates staging/production resources.
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

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_STAGING_REPORT = REPORT_DIR / "stage3-staging-rehearsal-result-20260615.json"
DEFAULT_PRODUCTION_REPORT = REPORT_DIR / "stage5-production-rehearsal-result-20260615.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "stage5-environment-rehearsal-evidence-pack-20260615.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "stage5-environment-rehearsal-evidence-pack-20260615.md"

STAGING_REQUIRED_EVIDENCE = (
    "staging_deploy_run",
    "staging_smoke_tests",
    "staging_rollback_rehearsal",
    "staging_observability",
    "staging_environment_protection",
)
PRODUCTION_REQUIRED_EVIDENCE = (
    "production_deploy_rehearsal",
    "production_smoke_tests",
    "production_rollback_rehearsal",
    "production_observability",
    "production_release_approval",
)
EXPECTED_REHEARSAL_STATUSES = {
    "staging": "staging_rehearsal_ready",
    "production": "production_rehearsal_ready",
}
FORBIDDEN_CLAIMS = (
    "staging proven",
    "production ready",
    "GA ready",
)


@dataclass(frozen=True)
class EnvironmentEvidenceItem:
    environment: str
    name: str
    path: str | None
    status: str | None
    bound_sha: str | None
    sha_matches_release: bool
    ready: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EnvironmentReportSummary:
    environment: str
    path: str
    status: str | None
    rehearsal_ready: bool
    release_sha: str | None
    current_head_sha: str | None
    mutation_performed: bool
    deploy_tag_release_performed: bool
    workflow_dispatch_performed: bool
    cluster_mutation_performed_by_gate: bool
    outbound_message_sent: bool
    evidence: list[EnvironmentEvidenceItem]
    ready: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidencePackCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class EnvironmentEvidencePack:
    status: str
    generated_at: str
    release_sha: str | None
    current_head_sha: str | None
    controlled_commercial_pilot_readiness: bool
    claim_boundary: dict[str, Any]
    mutation_performed: bool
    deploy_performed: bool
    tag_performed: bool
    release_performed: bool
    workflow_dispatch_performed: bool
    cluster_mutation_performed: bool
    outbound_message_sent: bool
    reports: list[EnvironmentReportSummary]
    checks: list[EvidencePackCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    main_control_integration_suggestion: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reports"] = [asdict(report) for report in self.reports]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(args: Sequence[str]) -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout).strip() or f"git exited {completed.returncode}"
    return completed.stdout.strip(), None


def resolve_current_head_sha() -> str | None:
    value, error = _run_git(["rev-parse", "HEAD"])
    return None if error else value


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing rehearsal report: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read rehearsal report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"rehearsal report is not a JSON object: {_display_path(path)}"
    return payload, None


def _bool(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True


def _str_value(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _evidence_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        return {}
    by_name: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            by_name[item["name"]] = item
    return by_name


def _item_summary(
    environment: str,
    name: str,
    item: dict[str, Any] | None,
    *,
    release_sha: str | None,
) -> EnvironmentEvidenceItem:
    if item is None:
        return EnvironmentEvidenceItem(
            environment=environment,
            name=name,
            path=None,
            status=None,
            bound_sha=None,
            sha_matches_release=False,
            ready=False,
            errors=["required rehearsal evidence item missing"],
        )

    path = item.get("path") if isinstance(item.get("path"), str) else None
    status = item.get("status") if isinstance(item.get("status"), str) else None
    bound_sha = item.get("bound_sha") if isinstance(item.get("bound_sha"), str) else None
    ready = item.get("ready") is True
    sha_matches_release = bool(release_sha and bound_sha == release_sha and item.get("sha_matches_release") is True)
    errors: list[str] = []
    if not ready:
        errors.append("evidence item is not ready")
    if not bound_sha:
        errors.append("evidence item has no bound_sha")
    elif not sha_matches_release:
        errors.append("evidence item SHA does not match release_sha")
    source_error = item.get("error")
    if isinstance(source_error, str) and source_error:
        errors.append(source_error)

    return EnvironmentEvidenceItem(
        environment=environment,
        name=name,
        path=path,
        status=status,
        bound_sha=bound_sha,
        sha_matches_release=sha_matches_release,
        ready=not errors,
        errors=errors,
    )


def summarize_environment_report(
    environment: str,
    report_path: Path,
    *,
    release_sha: str | None,
) -> EnvironmentReportSummary:
    payload, read_error = _read_json(report_path)
    required_names = STAGING_REQUIRED_EVIDENCE if environment == "staging" else PRODUCTION_REQUIRED_EVIDENCE
    if payload is None:
        return EnvironmentReportSummary(
            environment=environment,
            path=_display_path(report_path),
            status=None,
            rehearsal_ready=False,
            release_sha=None,
            current_head_sha=None,
            mutation_performed=False,
            deploy_tag_release_performed=False,
            workflow_dispatch_performed=False,
            cluster_mutation_performed_by_gate=False,
            outbound_message_sent=False,
            evidence=[
                EnvironmentEvidenceItem(
                    environment=environment,
                    name=name,
                    path=None,
                    status=None,
                    bound_sha=None,
                    sha_matches_release=False,
                    ready=False,
                    errors=["parent rehearsal report missing"],
                )
                for name in required_names
            ],
            ready=False,
            errors=[read_error or "parent rehearsal report missing"],
        )

    report_release_sha = _str_value(payload, "release_sha")
    report_head_sha = _str_value(payload, "current_head_sha")
    by_name = _evidence_by_name(payload)
    evidence = [
        _item_summary(environment, name, by_name.get(name), release_sha=release_sha)
        for name in required_names
    ]
    status = _str_value(payload, "status")
    errors: list[str] = []
    if status != EXPECTED_REHEARSAL_STATUSES[environment]:
        errors.append(f"expected status {EXPECTED_REHEARSAL_STATUSES[environment]}, got {status or '<missing>'}")
    if payload.get("rehearsal_ready") is not True:
        errors.append("rehearsal_ready is not true")
    if not report_release_sha:
        errors.append("report release_sha missing")
    elif report_release_sha != release_sha:
        errors.append("report release_sha does not match selected release_sha")
    for side_effect_key in (
        "mutation_performed",
        "deploy_tag_release_performed",
        "workflow_dispatch_performed",
        "cluster_mutation_performed_by_gate",
        "outbound_message_sent",
    ):
        if payload.get(side_effect_key) is True:
            errors.append(f"{side_effect_key} must remain false")
    blocked_items = [item.name for item in evidence if not item.ready]
    if blocked_items:
        errors.append(f"blocked evidence items: {', '.join(blocked_items)}")

    return EnvironmentReportSummary(
        environment=environment,
        path=_display_path(report_path),
        status=status,
        rehearsal_ready=_bool(payload, "rehearsal_ready"),
        release_sha=report_release_sha,
        current_head_sha=report_head_sha,
        mutation_performed=_bool(payload, "mutation_performed"),
        deploy_tag_release_performed=_bool(payload, "deploy_tag_release_performed"),
        workflow_dispatch_performed=_bool(payload, "workflow_dispatch_performed"),
        cluster_mutation_performed_by_gate=_bool(payload, "cluster_mutation_performed_by_gate"),
        outbound_message_sent=_bool(payload, "outbound_message_sent"),
        evidence=evidence,
        ready=not errors,
        errors=errors,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> EvidencePackCheck:
    return EvidencePackCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def build_environment_evidence_pack(
    *,
    staging_report: Path = DEFAULT_STAGING_REPORT,
    production_report: Path = DEFAULT_PRODUCTION_REPORT,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
) -> EnvironmentEvidencePack:
    resolved_head = current_head_sha or resolve_current_head_sha()
    resolved_release_sha = release_sha or resolved_head
    reports = [
        summarize_environment_report("staging", staging_report, release_sha=resolved_release_sha),
        summarize_environment_report("production", production_report, release_sha=resolved_release_sha),
    ]
    missing_or_blocked = [
        item.name
        for report in reports
        for item in report.evidence
        if not item.ready
    ]
    report_blockers = [report.environment for report in reports if not report.ready]
    sha_ready = bool(resolved_release_sha)
    side_effect_free = all(
        not (
            report.mutation_performed
            or report.deploy_tag_release_performed
            or report.workflow_dispatch_performed
            or report.cluster_mutation_performed_by_gate
            or report.outbound_message_sent
        )
        for report in reports
    )
    all_ready = sha_ready and side_effect_free and not report_blockers and not missing_or_blocked
    checks = [
        _check(
            "release_sha_bound",
            sha_ready,
            {"release_sha": resolved_release_sha, "current_head_sha": resolved_head},
            "release SHA could not be resolved",
        ),
        _check(
            "staging_rehearsal_evidence_ready",
            reports[0].ready,
            {"errors": reports[0].errors},
            "staging rehearsal evidence is blocked or incomplete",
        ),
        _check(
            "production_rehearsal_evidence_ready",
            reports[1].ready,
            {"errors": reports[1].errors},
            "production rehearsal evidence is blocked or incomplete",
        ),
        _check(
            "no_environment_side_effects",
            side_effect_free,
            {
                "mutation_performed": False,
                "deploy_performed": False,
                "tag_performed": False,
                "release_performed": False,
                "workflow_dispatch_performed": False,
                "cluster_mutation_performed": False,
                "outbound_message_sent": False,
            },
            "rehearsal pack input reports indicate environment side effects",
        ),
        _check(
            "claim_boundary_controlled_pilot_only",
            True,
            {
                "allowed": "controlled commercial pilot readiness",
                "forbidden": list(FORBIDDEN_CLAIMS),
            },
            "forbidden Stage 5 environment readiness claim present",
        ),
    ]
    return EnvironmentEvidencePack(
        status="environment_rehearsal_evidence_pack_ready" if all_ready else "environment_rehearsal_evidence_pack_blocked",
        generated_at=_utc_now(),
        release_sha=resolved_release_sha,
        current_head_sha=resolved_head,
        controlled_commercial_pilot_readiness=all_ready,
        claim_boundary={
            "allowed": "controlled commercial pilot readiness",
            "forbidden": list(FORBIDDEN_CLAIMS),
        },
        mutation_performed=False,
        deploy_performed=False,
        tag_performed=False,
        release_performed=False,
        workflow_dispatch_performed=False,
        cluster_mutation_performed=False,
        outbound_message_sent=False,
        reports=reports,
        checks=checks,
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=[
            "collect_missing_staging_rehearsal_evidence",
            "collect_missing_production_rehearsal_evidence",
            "rerun_commercial_stage5_environment_evidence_pack",
        ]
        if not all_ready
        else ["attach_environment_rehearsal_evidence_pack_to_controlled_pilot_gate"],
        main_control_integration_suggestion=[
            "Wire this pack as a read-only prerequisite before any Stage 5 owner approval surface.",
            "Keep deploy/tag/release/workflow-dispatch execution outside this pack and owner-gated.",
            "Expose blocked evidence names directly in the control-plane readiness UI.",
        ],
        known_limits=[
            "This pack summarizes existing rehearsal reports only; it does not perform staging or production deployment.",
            "Ready status supports controlled commercial pilot readiness only, not staging proven, production ready, or GA ready claims.",
        ],
    )


def render_markdown_report(report: EnvironmentEvidencePack) -> str:
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    report_lines = []
    for environment_report in report.reports:
        report_lines.append(
            f"- {environment_report.environment}: `{environment_report.status or '<missing>'}` "
            f"/ ready `{environment_report.ready}` / path `{environment_report.path}`"
        )
        for item in environment_report.evidence:
            suffix = f" / errors: {'; '.join(item.errors)}" if item.errors else ""
            report_lines.append(f"  - {item.name}: ready `{item.ready}` / status `{item.status or '<missing>'}`{suffix}")
    missing = "\n".join(f"- {name}" for name in report.missing_or_blocked_evidence) or "- none"
    suggestions = "\n".join(f"- {item}" for item in report.main_control_integration_suggestion)
    forbidden_claims = ", ".join(report.claim_boundary["forbidden"])
    return (
        "# Stage 5 Environment Rehearsal Evidence Pack\n\n"
        f"- Status: `{report.status}`\n"
        f"- Controlled commercial pilot readiness: `{report.controlled_commercial_pilot_readiness}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Tag performed: `{report.tag_performed}`\n"
        f"- Release performed: `{report.release_performed}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Cluster mutation performed: `{report.cluster_mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Claim boundary: `{report.claim_boundary['allowed']}`\n\n"
        f"- Forbidden claims: `{forbidden_claims}`\n\n"
        "## Environment Reports\n\n"
        f"{chr(10).join(report_lines)}\n\n"
        "## Missing Or Blocked Evidence\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Main Control Integration Suggestion\n\n"
        f"{suggestions}\n"
    )


def write_json_report(report: EnvironmentEvidencePack, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: EnvironmentEvidencePack, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage 5 environment rehearsal evidence pack.")
    parser.add_argument("--staging-report", type=Path, default=DEFAULT_STAGING_REPORT)
    parser.add_argument("--production-report", type=Path, default=DEFAULT_PRODUCTION_REPORT)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_environment_evidence_pack(
        staging_report=args.staging_report,
        production_report=args.production_report,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
    )
    write_json_report(report, args.output_json)
    write_markdown_report(report, args.output_md)
    print(f"Stage 5 environment rehearsal evidence pack status: {report.status}")
    print(f"Release SHA: {report.release_sha or '<missing>'}")
    print(f"Missing or blocked evidence: {', '.join(report.missing_or_blocked_evidence) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0 if report.controlled_commercial_pilot_readiness else 1


if __name__ == "__main__":
    raise SystemExit(main())
