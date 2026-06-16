#!/usr/bin/env python3
"""Validate Stage 5 staging and production rehearsal evidence.

This gate is intentionally read-only. It does not deploy, dispatch workflows,
mutate clusters, tag releases, or send outbound messages. It only verifies that
separate environment evidence reports exist, are ready, and are bound to the
selected release SHA.
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
DEFAULT_STAGING_OUTPUT_JSON = REPORT_DIR / "stage3-staging-rehearsal-result-20260615.json"
DEFAULT_STAGING_OUTPUT_MD = REPORT_DIR / "stage3-staging-rehearsal-result-20260615.md"
DEFAULT_PRODUCTION_OUTPUT_JSON = REPORT_DIR / "stage5-production-rehearsal-result-20260615.json"
DEFAULT_PRODUCTION_OUTPUT_MD = REPORT_DIR / "stage5-production-rehearsal-result-20260615.md"


@dataclass(frozen=True)
class RehearsalEvidenceSpec:
    name: str
    path: Path
    expected_statuses: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class RehearsalEvidence:
    name: str
    path: str
    status: str | None
    expected_statuses: list[str]
    bound_sha: str | None
    sha_matches_release: bool
    ready: bool
    reason: str
    error: str | None = None


@dataclass(frozen=True)
class RehearsalCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class EnvironmentRehearsalReport:
    status: str
    environment: str
    generated_at: str
    current_head_sha: str | None
    release_sha: str | None
    rehearsal_ready: bool
    mutation_performed: bool
    outbound_message_sent: bool
    deploy_tag_release_performed: bool
    workflow_dispatch_performed: bool
    cluster_mutation_performed_by_gate: bool
    evidence: list[RehearsalEvidence]
    checks: list[RehearsalCheck]
    missing_or_mismatched: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [asdict(item) for item in self.evidence]
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
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def default_evidence_specs(environment: str, report_dir: Path = REPORT_DIR) -> list[RehearsalEvidenceSpec]:
    if environment == "staging":
        return [
            RehearsalEvidenceSpec(
                "staging_deploy_run",
                report_dir / "stage5-staging-deploy-run-20260615.json",
                ("staging_deploy_ready", "passed"),
                "Real staging deploy or staging-equivalent rollout evidence.",
            ),
            RehearsalEvidenceSpec(
                "staging_smoke_tests",
                report_dir / "stage5-staging-smoke-tests-20260615.json",
                ("staging_smoke_ready", "passed"),
                "Health, readiness, auth, API, frontend, and Panda BFF smoke evidence.",
            ),
            RehearsalEvidenceSpec(
                "staging_rollback_rehearsal",
                report_dir / "stage5-staging-rollback-rehearsal-20260615.json",
                ("staging_rollback_ready", "passed"),
                "Rollback target and rehearsal evidence.",
            ),
            RehearsalEvidenceSpec(
                "staging_observability",
                report_dir / "stage5-staging-observability-20260615.json",
                ("staging_observability_ready", "passed"),
                "Logs, metrics, tracing, and alert visibility evidence.",
            ),
            RehearsalEvidenceSpec(
                "staging_environment_protection",
                report_dir / "stage5-staging-environment-protection-20260615.json",
                ("staging_environment_protection_ready", "passed"),
                "Environment protection, secret binding, DNS/TLS, and owner approval evidence.",
            ),
        ]
    if environment == "production":
        return [
            RehearsalEvidenceSpec(
                "production_deploy_rehearsal",
                report_dir / "stage5-production-deploy-rehearsal-20260615.json",
                ("production_deploy_rehearsal_ready", "passed"),
                "Production or production-equivalent deployment rehearsal evidence.",
            ),
            RehearsalEvidenceSpec(
                "production_smoke_tests",
                report_dir / "stage5-production-smoke-tests-20260615.json",
                ("production_smoke_ready", "passed"),
                "Production health, readiness, auth, API, frontend, and Panda BFF smoke evidence.",
            ),
            RehearsalEvidenceSpec(
                "production_rollback_rehearsal",
                report_dir / "stage5-production-rollback-rehearsal-20260615.json",
                ("production_rollback_ready", "passed"),
                "Production rollback target and rehearsal evidence.",
            ),
            RehearsalEvidenceSpec(
                "production_observability",
                report_dir / "stage5-production-observability-20260615.json",
                ("production_observability_ready", "passed"),
                "Production logs, metrics, tracing, and alert visibility evidence.",
            ),
            RehearsalEvidenceSpec(
                "production_release_approval",
                report_dir / "stage5-production-release-approval-20260615.json",
                ("production_release_approval_ready", "passed"),
                "Owner-approved production release rehearsal decision evidence.",
            ),
        ]
    raise ValueError(f"unknown environment: {environment}")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _status(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("status", "report", "package_status"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _is_sha_key(key: str) -> bool:
    lowered = key.lower()
    return lowered == "sha" or lowered.endswith("_sha") or "commit_sha" in lowered


def _collect_sha_fields(value: Any, *, prefix: str = "") -> dict[str, str]:
    found: dict[str, str] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if _is_sha_key(str(key)) and isinstance(child, str) and child:
                found[child_prefix] = child
            found.update(_collect_sha_fields(child, prefix=child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(_collect_sha_fields(child, prefix=f"{prefix}[{index}]"))
    return found


def _bound_sha(sha_fields: dict[str, str]) -> str | None:
    preferred_fragments = ("release_sha", "current_head_sha", "head_sha", "remote_branch_sha")
    preferred = {
        value
        for key, value in sha_fields.items()
        if any(fragment in key.lower() for fragment in preferred_fragments)
    }
    if len(preferred) == 1:
        return next(iter(preferred))
    if len(preferred) > 1:
        return None
    unique = {value for value in sha_fields.values() if value}
    if len(unique) == 1:
        return next(iter(unique))
    return None


def _evidence_item(spec: RehearsalEvidenceSpec, *, release_sha: str | None) -> RehearsalEvidence:
    payload, read_error = _read_json(spec.path)
    status = _status(payload)
    if payload is None:
        return RehearsalEvidence(
            name=spec.name,
            path=_display_path(spec.path),
            status=status,
            expected_statuses=list(spec.expected_statuses),
            bound_sha=None,
            sha_matches_release=False,
            ready=False,
            reason=spec.reason,
            error=read_error,
        )

    sha_fields = _collect_sha_fields(payload)
    bound_sha = _bound_sha(sha_fields)
    status_ready = status in spec.expected_statuses
    sha_matches_release = bool(release_sha and bound_sha == release_sha)
    problems: list[str] = []
    if read_error:
        problems.append(read_error)
    if not status_ready:
        problems.append(f"status {status or '<missing>'} not in expected statuses")
    if not sha_fields:
        problems.append("no SHA fields found in evidence report")
    elif bound_sha is None:
        problems.append("evidence report contains multiple distinct SHA values")
    elif not sha_matches_release:
        problems.append("evidence SHA does not match release_sha")

    return RehearsalEvidence(
        name=spec.name,
        path=_display_path(spec.path),
        status=status,
        expected_statuses=list(spec.expected_statuses),
        bound_sha=bound_sha,
        sha_matches_release=sha_matches_release,
        ready=not problems,
        reason=spec.reason,
        error="; ".join(problems) if problems else None,
    )


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> RehearsalCheck:
    return RehearsalCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def build_environment_rehearsal_report(
    environment: str,
    *,
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    specs: Sequence[RehearsalEvidenceSpec] | None = None,
) -> EnvironmentRehearsalReport:
    resolved_head = current_head_sha or resolve_current_head_sha()
    resolved_release_sha = release_sha or resolved_head
    evidence_specs = list(specs or default_evidence_specs(environment, report_dir))
    evidence = [_evidence_item(spec, release_sha=resolved_release_sha) for spec in evidence_specs]
    missing_or_mismatched = [item.name for item in evidence if not item.ready]
    all_evidence_ready = not missing_or_mismatched
    release_sha_ready = resolved_release_sha is not None
    ready = all_evidence_ready and release_sha_ready
    status = f"{environment}_rehearsal_ready" if ready else f"{environment}_rehearsal_blocked"
    checks = [
        _check(
            "required_environment_evidence_ready",
            all_evidence_ready,
            {"missing_or_mismatched": missing_or_mismatched},
            "required environment rehearsal evidence is missing, blocked, or mismatched",
        ),
        _check(
            "release_sha_resolved",
            release_sha_ready,
            {"current_head_sha": resolved_head, "release_sha": resolved_release_sha},
            "release SHA could not be resolved",
        ),
        _check(
            "gate_has_no_environment_side_effects",
            True,
            {
                "mutation_performed": False,
                "workflow_dispatch_performed": False,
                "cluster_mutation_performed_by_gate": False,
                "outbound_message_sent": False,
                "deploy_tag_release_performed": False,
            },
            "gate attempted environment side effects",
        ),
    ]
    return EnvironmentRehearsalReport(
        status=status,
        environment=environment,
        generated_at=_utc_now(),
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        rehearsal_ready=ready,
        mutation_performed=False,
        outbound_message_sent=False,
        deploy_tag_release_performed=False,
        workflow_dispatch_performed=False,
        cluster_mutation_performed_by_gate=False,
        evidence=evidence,
        checks=checks,
        missing_or_mismatched=missing_or_mismatched,
        next_actions=[
            f"Produce or refresh {environment} evidence for {name}."
            for name in missing_or_mismatched
        ]
        or [f"Archive this {environment} rehearsal report with the GA release packet."],
        known_limits=[
            "This gate validates environment evidence only; it does not run deployments or smoke tests.",
            "Controlled pilot or static remediation evidence is not substituted for real environment rehearsal proof.",
        ],
    )


def render_markdown_report(report: EnvironmentRehearsalReport) -> str:
    evidence = "\n".join(
        f"- {item.name}: `{item.status or '<missing>'}` / ready `{item.ready}`"
        + (f" / error: {item.error}" if item.error else "")
        for item in report.evidence
    )
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    missing = "\n".join(f"- {name}" for name in report.missing_or_mismatched) or "- none"
    return (
        f"# Stage 5 {report.environment.title()} Rehearsal Gate\n\n"
        f"- Status: `{report.status}`\n"
        f"- Ready: `{report.rehearsal_ready}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Cluster mutation performed by gate: `{report.cluster_mutation_performed_by_gate}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Deploy/tag/release performed: `{report.deploy_tag_release_performed}`\n\n"
        "## Evidence\n\n"
        f"{evidence}\n\n"
        "## Missing Or Mismatched\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n"
    )


def write_report(report: EnvironmentRehearsalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: EnvironmentRehearsalReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def _default_output_paths(environment: str) -> tuple[Path, Path]:
    if environment == "staging":
        return DEFAULT_STAGING_OUTPUT_JSON, DEFAULT_STAGING_OUTPUT_MD
    if environment == "production":
        return DEFAULT_PRODUCTION_OUTPUT_JSON, DEFAULT_PRODUCTION_OUTPUT_MD
    raise ValueError(f"unknown environment: {environment}")


def write_default_reports(
    *,
    environment: str = "both",
    report_dir: Path = REPORT_DIR,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> list[EnvironmentRehearsalReport]:
    environments = ("staging", "production") if environment == "both" else (environment,)
    reports: list[EnvironmentRehearsalReport] = []
    for item in environments:
        report = build_environment_rehearsal_report(
            item,
            report_dir=report_dir,
            current_head_sha=current_head_sha,
            release_sha=release_sha,
        )
        default_json, default_md = _default_output_paths(item)
        write_report(report, output_json or default_json)
        write_markdown_report(report, output_md or default_md)
        reports.append(report)
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Stage 5 environment rehearsal evidence.")
    parser.add_argument("--environment", choices=("staging", "production", "both"), default="both")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.environment == "both" and (args.output_json or args.output_md):
        raise SystemExit("--output-json/--output-md can only be used with one environment")
    reports = write_default_reports(
        environment=args.environment,
        report_dir=args.report_dir,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    for report in reports:
        print(f"{report.environment.title()} rehearsal gate status: {report.status}")
        print(f"Release SHA: {report.release_sha or '<missing>'}")
        print(f"Missing or mismatched: {', '.join(report.missing_or_mismatched) or '<none>'}")
    return 0 if all(report.rehearsal_ready for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
