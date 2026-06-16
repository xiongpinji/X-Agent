#!/usr/bin/env python3
"""Validate external staging evidence for the Stage 3 rehearsal gate.

The intake is fail-closed and read-only. It never deploys, dispatches a
workflow, mutates a cluster, sends outbound messages, or records secret values.
It converts an owner/operator supplied evidence file into the two staging
evidence reports consumed by ``commercial_environment_rehearsal_gate.py``:

* ``stage5-staging-observability-20260615.json``
* ``stage5-staging-environment-protection-20260615.json``

If required external evidence is missing, stale, digest-mismatched, or appears
to contain secret material, the generated reports remain blocked.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.commercial_environment_rehearsal_gate import REPORT_DIR, ROOT

DEFAULT_INPUT_JSON = REPORT_DIR / "stage3-staging-external-evidence-input-20260616.json"
DEFAULT_OBSERVABILITY_OUTPUT = REPORT_DIR / "stage5-staging-observability-20260615.json"
DEFAULT_PROTECTION_OUTPUT = REPORT_DIR / "stage5-staging-environment-protection-20260615.json"
DEFAULT_SUMMARY_OUTPUT_JSON = REPORT_DIR / "stage3-staging-external-evidence-intake-20260616.json"
DEFAULT_SUMMARY_OUTPUT_MD = REPORT_DIR / "stage3-staging-external-evidence-intake-20260616.md"

OBSERVABILITY_REQUIRED_FIELDS = (
    "workflow_event_broker.broker_kind",
    "workflow_event_broker.health_ref",
    "langfuse.trace_ref",
    "sentry.event_ref",
    "metrics.metrics_ref",
    "alerting.alert_ref",
)
PROTECTION_REQUIRED_FIELDS = (
    "external_endpoint.url",
    "external_endpoint.ingress_ref",
    "dns_tls.dns_ref",
    "dns_tls.tls_ref",
    "secret_binding.secret_refs",
    "secret_binding.redaction_confirmed",
    "deployed_image.image_ref",
    "deployed_image.digest",
    "github_environment.required_reviewer",
    "owner_approval.owner",
    "owner_approval.approval_ref",
    "owner_approval.approved_at",
)
ALLOWED_SECRET_FIELD_PATHS = {
    "staging_environment_protection.secret_binding.secret_refs",
    "staging_environment_protection.secret_binding.redaction_confirmed",
}
SECRET_FIELD_NAMES = {
    "api_key",
    "dsn",
    "password",
    "private_key",
    "secret",
    "secret_key",
    "token",
}
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)


@dataclass(frozen=True)
class IntakeCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class EvidenceWriteResult:
    name: str
    path: str
    status: str
    ready: bool
    written: bool
    skipped_existing_ready: bool = False
    error: str | None = None


@dataclass(frozen=True)
class ExternalEvidenceIntakeReport:
    status: str
    generated_at: str
    current_head_sha: str | None
    release_sha: str | None
    expected_image_digest: str | None
    input_path: str
    input_loaded: bool
    real_external_evidence_collected: bool
    mutation_performed: bool
    deploy_performed: bool
    workflow_dispatch_performed: bool
    cluster_mutation_performed: bool
    outbound_message_sent: bool
    raw_secret_values_recorded: bool
    evidence_reports: list[EvidenceWriteResult]
    checks: list[IntakeCheck]
    missing_or_blocked_evidence: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_reports"] = [asdict(item) for item in self.evidence_reports]
        payload["checks"] = [asdict(check) for check in self.checks]
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


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"input evidence file not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"could not read input evidence file {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"input evidence file is not a JSON object: {_display_path(path)}"
    return payload, None


def _check(name: str, passed: bool, *, details: dict[str, Any] | None = None, error: str | None = None) -> IntakeCheck:
    return IntakeCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value is True
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None


def _nested_value(payload: Mapping[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _missing_fields(section: Mapping[str, Any], required_fields: Sequence[str]) -> list[str]:
    return [field_name for field_name in required_fields if not _nonempty(_nested_value(section, field_name))]


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list | tuple | set):
        for child in value:
            yield from _string_values(child)


def _secret_redaction_violations(value: Any, *, prefix: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            key_name = str(key).lower()
            if path not in ALLOWED_SECRET_FIELD_PATHS and key_name in SECRET_FIELD_NAMES and _nonempty(child):
                violations.append(path)
                continue
            violations.extend(_secret_redaction_violations(child, prefix=path))
        return sorted(set(violations))
    for candidate in _string_values(value):
        if any(pattern.search(candidate) for pattern in SECRET_VALUE_PATTERNS):
            violations.append(prefix or "<root>")
    return sorted(set(violations))


def _safe_requirement_summary(section: Mapping[str, Any], required_fields: Sequence[str]) -> dict[str, str]:
    summary: dict[str, str] = {}
    for field_name in required_fields:
        value = _nested_value(section, field_name)
        summary[field_name] = "present" if _nonempty(value) else "missing"
    return summary


def _ready_report_status(name: str, ready: bool) -> str:
    if name == "staging_observability":
        return "staging_observability_ready" if ready else "staging_observability_blocked"
    if name == "staging_environment_protection":
        return "staging_environment_protection_ready" if ready else "staging_environment_protection_blocked"
    raise ValueError(f"unknown evidence report name: {name}")


def _existing_ready_external_evidence(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    status = payload.get("status")
    return (
        payload.get("real_external_evidence_collected") is True
        and isinstance(status, str)
        and status.endswith("_ready")
    )


def _build_evidence_payload(
    *,
    name: str,
    section: Mapping[str, Any],
    required_fields: Sequence[str],
    input_path: Path,
    current_head_sha: str | None,
    release_sha: str | None,
    input_release_sha: str | None,
    input_error: str | None,
    expected_image_digest: str | None,
) -> tuple[dict[str, Any], list[IntakeCheck]]:
    missing = _missing_fields(section, required_fields)
    secret_violations = _secret_redaction_violations({name: section})
    release_bound = bool(release_sha and input_release_sha == release_sha)
    digest = _nested_value(section, "deployed_image.digest")
    digest_matches = (
        name != "staging_environment_protection"
        or not expected_image_digest
        or digest == expected_image_digest
    )
    ready = (
        input_error is None
        and not missing
        and not secret_violations
        and release_bound
        and digest_matches
    )
    checks = [
        _check(
            f"{name}_input_loaded",
            input_error is None,
            details={"input_path": _display_path(input_path)},
            error=input_error,
        ),
        _check(
            f"{name}_release_sha_bound",
            release_bound,
            details={"input_release_sha": input_release_sha, "release_sha": release_sha},
            error="external staging evidence input is not bound to the selected release SHA",
        ),
        _check(
            f"{name}_required_fields_present",
            not missing,
            details={"missing_fields": missing},
            error="required external staging evidence fields are missing",
        ),
        _check(
            f"{name}_secret_values_redacted",
            not secret_violations,
            details={"secret_field_paths": secret_violations},
            error="input evidence contains secret-like fields or values; provide references only",
        ),
    ]
    if name == "staging_environment_protection":
        checks.append(
            _check(
                f"{name}_image_digest_matches_expected",
                digest_matches,
                details={"expected_image_digest": expected_image_digest, "input_digest_present": bool(digest)},
                error="deployed image digest does not match the selected advisory image digest",
            )
        )

    payload = {
        "status": _ready_report_status(name, ready),
        "environment": "staging",
        "evidence_name": name,
        "generated_at": _utc_now(),
        "current_head_sha": current_head_sha,
        "release_sha": release_sha,
        "real_external_evidence_collected": ready,
        "external_evidence_input_path": _display_path(input_path),
        "external_evidence_input_embedded": False,
        "raw_secret_values_recorded": False,
        "template_not_evidence": False,
        "mutation_performed": False,
        "deploy_performed_by_intake": False,
        "workflow_dispatch_performed": False,
        "cluster_mutation_performed_by_intake": False,
        "outbound_message_sent": False,
        "expected_image_digest": expected_image_digest,
        "required_fields": list(required_fields),
        "missing_required_fields": missing,
        "secret_redaction_violations": secret_violations,
        "validated_requirement_summary": _safe_requirement_summary(section, required_fields),
        "checks": [asdict(check) for check in checks],
        "known_limits": [
            "This report validates owner/operator supplied evidence references only.",
            "The intake did not deploy, mutate staging, dispatch workflows, send messages, or verify secret values.",
            "Raw input evidence is not embedded to avoid recording secrets in generated reports.",
        ],
    }
    return payload, checks


def build_external_evidence_payloads(
    *,
    input_path: Path = DEFAULT_INPUT_JSON,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    expected_image_digest: str | None = None,
) -> tuple[dict[str, dict[str, Any]], list[IntakeCheck], str | None]:
    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    input_payload, input_error = _read_json(input_path)
    input_release_sha = input_payload.get("release_sha") if isinstance(input_payload.get("release_sha"), str) else None

    observability_section = input_payload.get("staging_observability")
    if not isinstance(observability_section, Mapping):
        observability_section = {}
    protection_section = input_payload.get("staging_environment_protection")
    if not isinstance(protection_section, Mapping):
        protection_section = {}

    observability_payload, observability_checks = _build_evidence_payload(
        name="staging_observability",
        section=observability_section,
        required_fields=OBSERVABILITY_REQUIRED_FIELDS,
        input_path=input_path,
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        input_release_sha=input_release_sha,
        input_error=input_error,
        expected_image_digest=expected_image_digest,
    )
    protection_payload, protection_checks = _build_evidence_payload(
        name="staging_environment_protection",
        section=protection_section,
        required_fields=PROTECTION_REQUIRED_FIELDS,
        input_path=input_path,
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        input_release_sha=input_release_sha,
        input_error=input_error,
        expected_image_digest=expected_image_digest,
    )
    return (
        {
            "staging_observability": observability_payload,
            "staging_environment_protection": protection_payload,
        },
        [*observability_checks, *protection_checks],
        input_error,
    )


def write_evidence_reports(
    payloads: Mapping[str, dict[str, Any]],
    *,
    observability_output: Path = DEFAULT_OBSERVABILITY_OUTPUT,
    protection_output: Path = DEFAULT_PROTECTION_OUTPUT,
    force: bool = False,
) -> list[EvidenceWriteResult]:
    targets = {
        "staging_observability": observability_output,
        "staging_environment_protection": protection_output,
    }
    results: list[EvidenceWriteResult] = []
    for name, output_path in targets.items():
        payload = payloads[name]
        ready = payload["status"].endswith("_ready")
        if output_path.exists() and _existing_ready_external_evidence(output_path) and not force:
            results.append(
                EvidenceWriteResult(
                    name=name,
                    path=_display_path(output_path),
                    status="skipped_existing_ready",
                    ready=ready,
                    written=False,
                    skipped_existing_ready=True,
                    error="existing ready external evidence report was not overwritten",
                )
            )
            continue
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            EvidenceWriteResult(
                name=name,
                path=_display_path(output_path),
                status=str(payload["status"]),
                ready=ready,
                written=True,
            )
        )
    return results


def build_intake_report(
    *,
    input_path: Path = DEFAULT_INPUT_JSON,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    expected_image_digest: str | None = None,
    write_results: Sequence[EvidenceWriteResult],
    checks: Sequence[IntakeCheck],
    input_error: str | None,
) -> ExternalEvidenceIntakeReport:
    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha if release_sha is not None else resolved_head
    missing_or_blocked = [result.name for result in write_results if not result.ready or not result.written]
    all_ready = not missing_or_blocked and input_error is None and all(check.status == "passed" for check in checks)
    return ExternalEvidenceIntakeReport(
        status="stage3_staging_external_evidence_ready" if all_ready else "stage3_staging_external_evidence_blocked",
        generated_at=_utc_now(),
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        expected_image_digest=expected_image_digest,
        input_path=_display_path(input_path),
        input_loaded=input_error is None,
        real_external_evidence_collected=all_ready,
        mutation_performed=False,
        deploy_performed=False,
        workflow_dispatch_performed=False,
        cluster_mutation_performed=False,
        outbound_message_sent=False,
        raw_secret_values_recorded=False,
        evidence_reports=list(write_results),
        checks=list(checks),
        missing_or_blocked_evidence=missing_or_blocked,
        next_actions=[
            "Collect real external staging observability references and rerun this intake.",
            "Collect real external staging environment-protection references and rerun this intake.",
            "Rerun commercial_environment_rehearsal_gate.py after both generated evidence reports are ready.",
        ]
        if not all_ready
        else ["Rerun commercial_environment_rehearsal_gate.py for the selected release SHA."],
        known_limits=[
            "This intake validates evidence references only and does not call external staging services.",
            "A ready intake is not a deployment action; it only makes the supplied external evidence consumable by the Stage 3 gate.",
            "Do not include raw secret values in the input evidence file.",
        ],
    )


def render_markdown_report(report: ExternalEvidenceIntakeReport) -> str:
    reports = "\n".join(
        f"- {item.name}: `{item.status}` / written `{item.written}` / path `{item.path}`"
        + (f" / error: {item.error}" if item.error else "")
        for item in report.evidence_reports
    )
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    missing = "\n".join(f"- {name}" for name in report.missing_or_blocked_evidence) or "- none"
    return (
        "# Stage 3 Staging External Evidence Intake\n\n"
        f"- Status: `{report.status}`\n"
        f"- Input loaded: `{report.input_loaded}`\n"
        f"- Real external evidence collected: `{report.real_external_evidence_collected}`\n"
        f"- Current head SHA: `{report.current_head_sha or '<missing>'}`\n"
        f"- Release SHA: `{report.release_sha or '<missing>'}`\n"
        f"- Expected image digest: `{report.expected_image_digest or '<not provided>'}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Deploy performed: `{report.deploy_performed}`\n"
        f"- Workflow dispatch performed: `{report.workflow_dispatch_performed}`\n"
        f"- Cluster mutation performed: `{report.cluster_mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n"
        f"- Raw secret values recorded: `{report.raw_secret_values_recorded}`\n\n"
        "## Evidence Reports\n\n"
        f"{reports}\n\n"
        "## Missing Or Blocked Evidence\n\n"
        f"{missing}\n\n"
        "## Checks\n\n"
        f"{checks}\n"
    )


def write_summary_reports(
    report: ExternalEvidenceIntakeReport,
    *,
    output_json: Path = DEFAULT_SUMMARY_OUTPUT_JSON,
    output_md: Path = DEFAULT_SUMMARY_OUTPUT_MD,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate external staging evidence for Stage 3.")
    parser.add_argument("--input-json", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--expected-image-digest", default=None)
    parser.add_argument("--observability-output", type=Path, default=DEFAULT_OBSERVABILITY_OUTPUT)
    parser.add_argument("--environment-protection-output", type=Path, default=DEFAULT_PROTECTION_OUTPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_SUMMARY_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_SUMMARY_OUTPUT_MD)
    parser.add_argument("--force", action="store_true", help="Overwrite existing ready external evidence reports.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=args.input_json,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
        expected_image_digest=args.expected_image_digest,
    )
    write_results = write_evidence_reports(
        payloads,
        observability_output=args.observability_output,
        protection_output=args.environment_protection_output,
        force=args.force,
    )
    report = build_intake_report(
        input_path=args.input_json,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
        expected_image_digest=args.expected_image_digest,
        write_results=write_results,
        checks=checks,
        input_error=input_error,
    )
    write_summary_reports(report, output_json=args.output_json, output_md=args.output_md)
    print(f"Stage 3 staging external evidence intake status: {report.status}")
    print(f"Input loaded: {report.input_loaded}")
    print(f"Missing or blocked evidence: {', '.join(report.missing_or_blocked_evidence) or '<none>'}")
    print(f"JSON report written to {args.output_json}")
    print(f"Markdown report written to {args.output_md}")
    return 0 if report.status == "stage3_staging_external_evidence_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
