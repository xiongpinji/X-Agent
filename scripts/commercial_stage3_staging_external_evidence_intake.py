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
import ipaddress
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.commercial_environment_rehearsal_gate import REPORT_DIR, ROOT

DEFAULT_INPUT_JSON = REPORT_DIR / "stage3-staging-external-evidence-input-20260616.json"
DEFAULT_DEPLOY_OUTPUT = REPORT_DIR / "stage5-staging-deploy-run-20260615.json"
DEFAULT_SMOKE_OUTPUT = REPORT_DIR / "stage5-staging-smoke-tests-20260615.json"
DEFAULT_ROLLBACK_OUTPUT = REPORT_DIR / "stage5-staging-rollback-rehearsal-20260615.json"
DEFAULT_OBSERVABILITY_OUTPUT = REPORT_DIR / "stage5-staging-observability-20260615.json"
DEFAULT_PROTECTION_OUTPUT = REPORT_DIR / "stage5-staging-environment-protection-20260615.json"
DEFAULT_SUMMARY_OUTPUT_JSON = REPORT_DIR / "stage3-staging-external-evidence-intake-20260616.json"
DEFAULT_SUMMARY_OUTPUT_MD = REPORT_DIR / "stage3-staging-external-evidence-intake-20260616.md"
DEFAULT_OWNER_DRAFT_JSON = REPORT_DIR / "stage3-staging-external-evidence-owner-draft-20260616.json"
DEFAULT_OWNER_DRAFT_MD = REPORT_DIR / "stage3-staging-external-evidence-owner-draft-20260616.md"

OBSERVABILITY_REQUIRED_FIELDS = (
    "workflow_event_broker.broker_kind",
    "workflow_event_broker.health_ref",
    "langfuse.trace_ref",
    "sentry.event_ref",
    "metrics.metrics_ref",
    "alerting.alert_ref",
)
EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS = {
    "staging_deploy_run": (
        "deploy_ref",
        "image_ref",
        "operator",
        "completed_at",
    ),
    "staging_smoke_tests": (
        "health_ref",
        "ready_ref",
        "smoke_ref",
        "operator",
        "completed_at",
    ),
    "staging_rollback_rehearsal": (
        "rollback_ref",
        "post_rollback_health_ref",
        "post_rollback_ready_ref",
        "operator",
        "completed_at",
    ),
}
PROTECTION_REQUIRED_FIELDS = (
    "external_endpoint.url",
    "external_endpoint.health_ref",
    "external_endpoint.ready_ref",
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
TEMPORARY_DOMAIN_SUFFIXES = (
    ".sslip.io",
    ".nip.io",
    ".xip.io",
)
EXTERNAL_ENVIRONMENT_READY_STATUSES = {
    "staging_deploy_run": "staging_deploy_ready",
    "staging_smoke_tests": "staging_smoke_ready",
    "staging_rollback_rehearsal": "staging_rollback_ready",
}
EXTERNAL_ENVIRONMENT_REF_FIELDS = (
    "external_evidence_ref",
    "external_evidence_refs",
    "evidence_url",
    "evidence_urls",
    "run_url",
    "artifact_url",
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


def _https_preflight_prefill_refs(path: Path) -> dict[str, str]:
    payload, error = _read_json(path)
    if error:
        raise ValueError(error)

    status = payload.get("status")
    if status != "stage3_https_preflight_ready":
        raise ValueError(f"HTTPS preflight report is not ready: {status or '<missing>'}")

    endpoint = payload.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise ValueError("HTTPS preflight report is missing a valid endpoint")

    check_names = {
        check.get("name"): check
        for check in payload.get("checks", [])
        if isinstance(check, dict) and isinstance(check.get("name"), str)
    }
    required_checks = (
        "domain_shape",
        "dns_points_to_expected_ip",
        "trusted_https_tls",
        "https_health_probe",
        "https_ready_probe",
    )
    missing_or_failed = [
        name
        for name in required_checks
        if not isinstance(check_names.get(name), dict) or check_names[name].get("status") != "passed"
    ]
    if missing_or_failed:
        raise ValueError(f"HTTPS preflight report has missing or failed checks: {', '.join(missing_or_failed)}")

    display_path = _display_path(path)
    return {
        "endpoint_url": endpoint,
        "health_ref": f"{display_path}#checks.https_health_probe",
        "ready_ref": f"{display_path}#checks.https_ready_probe",
        "dns_ref": f"{display_path}#checks.dns_points_to_expected_ip",
        "tls_ref": f"{display_path}#checks.trusted_https_tls",
    }


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


def _section_references(section: Mapping[str, Any]) -> dict[str, Any]:
    return {field_name: section[field_name] for field_name in EXTERNAL_ENVIRONMENT_REF_FIELDS if _nonempty(section.get(field_name))}


def _reference_value_present(section: Mapping[str, Any]) -> bool:
    return bool(_section_references(section))


def _external_endpoint_url_errors(section: Mapping[str, Any]) -> list[str]:
    value = _nested_value(section, "external_endpoint.url")
    if not isinstance(value, str) or not value.strip():
        return ["external_endpoint.url is missing"]

    url = value.strip()
    if "<" in url or ">" in url:
        return ["external_endpoint.url still contains a placeholder"]

    parsed = urlparse(url)
    errors: list[str] = []
    if parsed.scheme != "https":
        errors.append("external_endpoint.url must use https")
    if parsed.username or parsed.password:
        errors.append("external_endpoint.url must not contain credentials")
    if parsed.port not in (None, 443):
        errors.append("external_endpoint.url must use default HTTPS port or explicit 443")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        errors.append("external_endpoint.url must include a hostname")
        return errors
    if hostname == "localhost" or hostname.endswith(".localhost"):
        errors.append("external_endpoint.url must not use localhost")
    if "." not in hostname:
        errors.append("external_endpoint.url must use a real DNS domain, not a single-label host")
    if any(hostname == suffix[1:] or hostname.endswith(suffix) for suffix in TEMPORARY_DOMAIN_SUFFIXES):
        errors.append("external_endpoint.url must not use temporary wildcard DNS domains such as sslip.io")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        errors.append("external_endpoint.url must use an owner-controlled DNS domain, not a bare IP address")
    return sorted(set(errors))


def _ready_report_status(name: str, ready: bool) -> str:
    if name in EXTERNAL_ENVIRONMENT_READY_STATUSES:
        if ready:
            return EXTERNAL_ENVIRONMENT_READY_STATUSES[name]
        return f"{name}_blocked"
    if name == "staging_observability":
        return "staging_observability_ready" if ready else "staging_observability_blocked"
    if name == "staging_environment_protection":
        return "staging_environment_protection_ready" if ready else "staging_environment_protection_blocked"
    raise ValueError(f"unknown evidence report name: {name}")


def _build_external_environment_payload(
    *,
    name: str,
    section: Mapping[str, Any],
    required_fields: Sequence[str],
    input_path: Path,
    current_head_sha: str | None,
    release_sha: str | None,
    input_release_sha: str | None,
    input_error: str | None,
    template_not_evidence: bool = False,
) -> tuple[dict[str, Any], list[IntakeCheck]]:
    missing = _missing_fields(section, required_fields)
    secret_violations = _secret_redaction_violations({name: section})
    release_bound = bool(release_sha and input_release_sha == release_sha)
    has_reference = _reference_value_present(section)
    checks_source = section.get("checks")
    supplied_checks = checks_source if isinstance(checks_source, list) else []
    failed_supplied_checks: list[str] = []
    for index, check in enumerate(supplied_checks):
        if not isinstance(check, dict):
            failed_supplied_checks.append(f"check[{index}]")
            continue
        if check.get("status") != "passed":
            check_name = check.get("name")
            failed_supplied_checks.append(
                str(check_name) if isinstance(check_name, str) and check_name else f"check[{index}]"
            )

    ready = (
        input_error is None
        and not missing
        and not secret_violations
        and release_bound
        and not template_not_evidence
        and has_reference
        and isinstance(checks_source, list)
        and bool(checks_source)
        and not failed_supplied_checks
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
            f"{name}_not_template",
            not template_not_evidence,
            details={"template_not_external_evidence": template_not_evidence},
            error="input is explicitly marked as a template, not real external staging evidence",
        ),
        _check(
            f"{name}_required_fields_present",
            not missing,
            details={"missing_fields": missing},
            error="required external staging evidence fields are missing",
        ),
        _check(
            f"{name}_external_reference_present",
            has_reference,
            details={"reference_fields": sorted(_section_references(section).keys())},
            error="external deploy/smoke/rollback evidence reference is missing",
        ),
        _check(
            f"{name}_external_checks_passed",
            isinstance(checks_source, list) and bool(checks_source) and not failed_supplied_checks,
            details={"failed_checks": failed_supplied_checks, "check_count": len(supplied_checks)},
            error="external environment checks must be present and all passed",
        ),
        _check(
            f"{name}_secret_values_redacted",
            not secret_violations,
            details={"secret_field_paths": secret_violations},
            error="input evidence contains secret-like fields or values; provide references only",
        ),
    ]

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
        "template_not_evidence": template_not_evidence,
        "evidence_class": "external_stage3",
        "external_evidence_refs": _section_references(section),
        "external_evidence_ref": next(iter(_section_references(section).values()), None),
        "mutation_performed": False,
        "deploy_performed_by_intake": False,
        "workflow_dispatch_performed": False,
        "cluster_mutation_performed_by_intake": False,
        "outbound_message_sent": False,
        "tag_performed": False,
        "release_performed": False,
        "required_fields": list(required_fields),
        "missing_required_fields": missing,
        "secret_redaction_violations": secret_violations,
        "validated_requirement_summary": _safe_requirement_summary(section, required_fields),
        "checks": [asdict(check) for check in checks] + [check for check in supplied_checks if isinstance(check, dict)],
        "known_limits": [
            "This report validates owner/operator supplied external staging references only.",
            "The intake did not deploy, rollback, mutate staging, dispatch workflows, tag, release, or send messages.",
            "Raw input evidence is not embedded to avoid recording secrets in generated reports.",
        ],
    }
    return payload, checks


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
    template_not_evidence: bool = False,
) -> tuple[dict[str, Any], list[IntakeCheck]]:
    missing = _missing_fields(section, required_fields)
    secret_violations = _secret_redaction_violations({name: section})
    release_bound = bool(release_sha and input_release_sha == release_sha)
    digest = _nested_value(section, "deployed_image.digest")
    not_external_deploy_proof = _nested_value(section, "deployed_image.not_external_deploy_proof") is True
    endpoint_url_errors = (
        _external_endpoint_url_errors(section)
        if name == "staging_environment_protection"
        else []
    )
    digest_matches = (
        name != "staging_environment_protection"
        or not expected_image_digest
        or digest == expected_image_digest
    )
    deployed_image_is_external_proof = name != "staging_environment_protection" or not not_external_deploy_proof
    ready = (
        input_error is None
        and not missing
        and not secret_violations
        and release_bound
        and digest_matches
        and not template_not_evidence
        and not endpoint_url_errors
        and deployed_image_is_external_proof
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
            f"{name}_not_template",
            not template_not_evidence,
            details={"template_not_external_evidence": template_not_evidence},
            error="input is explicitly marked as a template, not real external staging evidence",
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
        checks.extend(
            [
                _check(
                    f"{name}_external_endpoint_uses_public_https_domain",
                    not endpoint_url_errors,
                    details={"endpoint_url_errors": endpoint_url_errors},
                    error=(
                        "external endpoint must be HTTPS on a real owner-controlled DNS domain "
                        "using port 443/default; HTTP, localhost, bare IPs, and temporary "
                        "wildcard DNS domains are not accepted"
                    ),
                ),
                _check(
                    f"{name}_image_digest_matches_expected",
                    digest_matches,
                    details={"expected_image_digest": expected_image_digest, "input_digest_present": bool(digest)},
                    error="deployed image digest does not match the selected advisory image digest",
                ),
                _check(
                    f"{name}_deployed_image_is_external_proof",
                    deployed_image_is_external_proof,
                    details={"not_external_deploy_proof": not_external_deploy_proof},
                    error="deployed image evidence is marked as advisory-only, not external deploy proof",
                ),
            ]
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
        "template_not_evidence": template_not_evidence,
        "not_external_deploy_proof": not_external_deploy_proof,
        "mutation_performed": False,
        "deploy_performed_by_intake": False,
        "workflow_dispatch_performed": False,
        "cluster_mutation_performed_by_intake": False,
        "outbound_message_sent": False,
        "expected_image_digest": expected_image_digest,
        "required_fields": list(required_fields),
        "missing_required_fields": missing,
        "secret_redaction_violations": secret_violations,
        "external_endpoint_validation_errors": endpoint_url_errors,
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
    template_not_evidence = input_payload.get("template_not_external_evidence") is True

    observability_section = input_payload.get("staging_observability")
    if not isinstance(observability_section, Mapping):
        observability_section = {}
    protection_section = input_payload.get("staging_environment_protection")
    if not isinstance(protection_section, Mapping):
        protection_section = {}
    deploy_section = input_payload.get("staging_deploy_run")
    if not isinstance(deploy_section, Mapping):
        deploy_section = {}
    smoke_section = input_payload.get("staging_smoke_tests")
    if not isinstance(smoke_section, Mapping):
        smoke_section = {}
    rollback_section = input_payload.get("staging_rollback_rehearsal")
    if not isinstance(rollback_section, Mapping):
        rollback_section = {}

    deploy_payload, deploy_checks = _build_external_environment_payload(
        name="staging_deploy_run",
        section=deploy_section,
        required_fields=EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS["staging_deploy_run"],
        input_path=input_path,
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        input_release_sha=input_release_sha,
        input_error=input_error,
        template_not_evidence=template_not_evidence,
    )
    smoke_payload, smoke_checks = _build_external_environment_payload(
        name="staging_smoke_tests",
        section=smoke_section,
        required_fields=EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS["staging_smoke_tests"],
        input_path=input_path,
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        input_release_sha=input_release_sha,
        input_error=input_error,
        template_not_evidence=template_not_evidence,
    )
    rollback_payload, rollback_checks = _build_external_environment_payload(
        name="staging_rollback_rehearsal",
        section=rollback_section,
        required_fields=EXTERNAL_ENVIRONMENT_REQUIRED_FIELDS["staging_rollback_rehearsal"],
        input_path=input_path,
        current_head_sha=resolved_head,
        release_sha=resolved_release_sha,
        input_release_sha=input_release_sha,
        input_error=input_error,
        template_not_evidence=template_not_evidence,
    )

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
        template_not_evidence=template_not_evidence,
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
        template_not_evidence=template_not_evidence,
    )
    return (
        {
            "staging_deploy_run": deploy_payload,
            "staging_smoke_tests": smoke_payload,
            "staging_rollback_rehearsal": rollback_payload,
            "staging_observability": observability_payload,
            "staging_environment_protection": protection_payload,
        },
        [
            *deploy_checks,
            *smoke_checks,
            *rollback_checks,
            *observability_checks,
            *protection_checks,
        ],
        input_error,
    )


def write_evidence_reports(
    payloads: Mapping[str, dict[str, Any]],
    *,
    deploy_output: Path | None = None,
    smoke_output: Path | None = None,
    rollback_output: Path | None = None,
    observability_output: Path = DEFAULT_OBSERVABILITY_OUTPUT,
    protection_output: Path = DEFAULT_PROTECTION_OUTPUT,
    force: bool = False,
) -> list[EvidenceWriteResult]:
    output_dir = observability_output.parent
    targets = {
        "staging_deploy_run": deploy_output or output_dir / DEFAULT_DEPLOY_OUTPUT.name,
        "staging_smoke_tests": smoke_output or output_dir / DEFAULT_SMOKE_OUTPUT.name,
        "staging_rollback_rehearsal": rollback_output or output_dir / DEFAULT_ROLLBACK_OUTPUT.name,
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


def build_owner_draft_payload(
    *,
    current_head_sha: str | None = None,
    release_sha: str | None = None,
    expected_image_digest: str | None = None,
    domain: str | None = None,
    owner: str = "xiongpinji",
    https_preflight_report: Path | None = None,
) -> dict[str, Any]:
    """Build a redaction-safe owner draft that is explicitly not evidence."""
    resolved_head = current_head_sha if current_head_sha is not None else _git_head()
    resolved_release_sha = release_sha or resolved_head or "<REPLACE_WITH_RELEASE_SHA>"
    preflight_refs = _https_preflight_prefill_refs(https_preflight_report) if https_preflight_report else {}
    domain_value = (domain or "<REAL_DOMAIN>").strip() or "<REAL_DOMAIN>"
    if domain_value.startswith("http://") or domain_value.startswith("https://"):
        endpoint_url = domain_value
    else:
        endpoint_url = f"https://{domain_value}"
    if preflight_refs:
        endpoint_url = preflight_refs["endpoint_url"]

    return {
        "template_not_external_evidence": True,
        "draft_generated_at": _utc_now(),
        "draft_purpose": "owner_fillable_stage3_external_evidence_references_only",
        "prefill_refs": {
            "https_preflight_report": _display_path(https_preflight_report) if https_preflight_report else None,
            "https_preflight_applied": bool(preflight_refs),
        },
        "draft_rules": [
            "This file is a draft helper, not real external evidence.",
            "Replace placeholders with links, command-output references, issue URLs, run IDs, or certificate references only.",
            "Do not paste API keys, passwords, tokens, private keys, DSNs, cookies, or raw secret values.",
            "Keep template_not_external_evidence=true until every placeholder is replaced by real owner-approved evidence.",
        ],
        "current_head_sha": resolved_head,
        "release_sha": resolved_release_sha,
        "staging_deploy_run": {
            "deploy_ref": "<EXTERNAL_STAGE3_DEPLOY_RUN_REF>",
            "image_ref": expected_image_digest or "<RUNNING_STAGE3_IMAGE_REF_WITH_DIGEST>",
            "operator": owner,
            "completed_at": "<UTC_TIMESTAMP_AFTER_EXTERNAL_STAGE3_DEPLOY>",
            "external_evidence_ref": "<EXTERNAL_STAGE3_DEPLOY_RUN_REF>",
            "checks": [
                {"name": "stage3_deploy_run_completed", "status": "blocked"},
                {"name": "stage3_deploy_release_sha_verified", "status": "blocked"},
            ],
        },
        "staging_smoke_tests": {
            "health_ref": preflight_refs.get("health_ref", "<HTTPS_443_HEALTH_PROBE_REF>"),
            "ready_ref": preflight_refs.get("ready_ref", "<HTTPS_443_READY_PROBE_REF>"),
            "smoke_ref": "<EXTERNAL_STAGE3_SMOKE_TEST_RUN_REF>",
            "operator": owner,
            "completed_at": "<UTC_TIMESTAMP_AFTER_EXTERNAL_STAGE3_SMOKE>",
            "external_evidence_ref": "<EXTERNAL_STAGE3_SMOKE_TEST_RUN_REF>",
            "checks": [
                {"name": "stage3_health_probe_passed", "status": "blocked"},
                {"name": "stage3_ready_probe_passed", "status": "blocked"},
                {"name": "stage3_smoke_suite_passed", "status": "blocked"},
            ],
        },
        "staging_rollback_rehearsal": {
            "rollback_ref": "<EXTERNAL_STAGE3_ROLLBACK_REHEARSAL_REF>",
            "post_rollback_health_ref": "<POST_ROLLBACK_HEALTH_PROBE_REF>",
            "post_rollback_ready_ref": "<POST_ROLLBACK_READY_PROBE_REF>",
            "operator": owner,
            "completed_at": "<UTC_TIMESTAMP_AFTER_EXTERNAL_STAGE3_ROLLBACK>",
            "external_evidence_ref": "<EXTERNAL_STAGE3_ROLLBACK_REHEARSAL_REF>",
            "checks": [
                {"name": "stage3_rollback_rehearsal_completed", "status": "blocked"},
                {"name": "stage3_post_rollback_health_passed", "status": "blocked"},
                {"name": "stage3_post_rollback_ready_passed", "status": "blocked"},
            ],
        },
        "staging_observability": {
            "workflow_event_broker": {
                "broker_kind": "<rabbitmq|redis-stream|github-actions|other>",
                "health_ref": "<URL_OR_LOG_REF_FOR_BROKER_HEALTH>",
            },
            "langfuse": {
                "trace_ref": "<LANGFUSE_TRACE_URL_OR_OWNER_APPROVED_FIRST_RC_EXCEPTION_REF>",
            },
            "sentry": {
                "event_ref": "<SENTRY_EVENT_URL_OR_OWNER_APPROVED_FIRST_RC_EXCEPTION_REF>",
            },
            "metrics": {
                "metrics_ref": "<METRICS_DASHBOARD_OR_COMMAND_OUTPUT_REF>",
            },
            "alerting": {
                "alert_ref": "<ALERT_RULE_OR_OWNER_ACCEPTANCE_REF>",
            },
        },
        "staging_environment_protection": {
            "external_endpoint": {
                "url": endpoint_url,
                "health_ref": preflight_refs.get("health_ref", "<HTTPS_443_HEALTH_PROBE_REF>"),
                "ready_ref": preflight_refs.get("ready_ref", "<HTTPS_443_READY_PROBE_REF>"),
                "ingress_ref": "<NGINX_SITE_PATH_AND_NGINX_T_RELOAD_REF>",
            },
            "dns_tls": {
                "dns_ref": preflight_refs.get("dns_ref", "<DNS_A_RECORD_REF_TO_111.228.49.160>"),
                "tls_ref": preflight_refs.get("tls_ref", "<CERTBOT_CERTIFICATES_OR_CERTIFICATE_ISSUER_REF>"),
            },
            "secret_binding": {
                "secret_refs": [
                    "github-actions:XAGENT_DEEPSEEK_API_KEY",
                    "server-env:XAGENT_FEISHU_APP_ID",
                    "server-env:XAGENT_FEISHU_APP_SECRET",
                    "server-env:XAGENT_FEISHU_ENCRYPT_KEY",
                ],
                "redaction_confirmed": False,
            },
            "deployed_image": {
                "image_ref": "<RUNNING_STAGE3_IMAGE_REF_WITH_DIGEST>",
                "digest": expected_image_digest or "<RUNNING_STAGE3_IMAGE_DIGEST>",
                "not_external_deploy_proof": True,
                "source": "draft_placeholder_until_replaced_with_real_stage3_runtime_proof",
            },
            "github_environment": {
                "required_reviewer": owner,
            },
            "owner_approval": {
                "owner": owner,
                "approval_ref": "<GITHUB_ISSUE_COMMENT_OR_SIGNED_HANDOFF_REF>",
                "approved_at": "<UTC_TIMESTAMP_AFTER_OWNER_REVIEW>",
            },
        },
    }


def render_owner_draft_markdown(payload: Mapping[str, Any], *, json_path: Path) -> str:
    domain = _nested_value(payload, "staging_environment_protection.external_endpoint.url")
    release_sha = payload.get("release_sha") or "<missing>"
    return (
        "# Stage 3 Owner Evidence Draft\n\n"
        "This is a fillable draft only. It is not accepted by the Stage 3 intake until "
        "`template_not_external_evidence` is changed to `false` after every placeholder is "
        "replaced with real external references.\n\n"
        "## Beginner Fill Order\n\n"
        "1. Choose a real domain you control, such as `xagent.example.com`, and point its "
        "DNS A record to `111.228.49.160`.\n"
        "2. Configure HTTPS on port 443 for that domain, then capture command-output refs "
        "for `/health` and `/ready` returning HTTP 200.\n"
        "3. Capture environment refs: external deploy run, external smoke run, rollback "
        "rehearsal, Nginx site path plus `nginx -t` and reload output, certificate output, "
        "running image ref/digest, and secret variable-name refs.\n"
        "4. Decide observability: provide real broker/trace/error/metrics/alert refs, or "
        "create an explicit owner-approved first-RC observability exception ref.\n"
        "5. After every placeholder below is replaced, set `template_not_external_evidence` "
        "to `false`, set `secret_binding.redaction_confirmed` to `true`, and set "
        "`deployed_image.not_external_deploy_proof` to `false` only when the image ref/digest "
        "comes from the running Stage3 environment.\n\n"
        "## What Codex Can Fill After You Provide The Domain\n\n"
        "- Probe refs for `https://<domain>/health` and `https://<domain>/ready`.\n"
        "- Nginx config/test/reload refs, TLS certificate refs, and running container image refs.\n"
        "- External Stage3 deploy, smoke, and rollback evidence refs after the operator records them.\n"
        "- The final validation command output and the updated generated reports.\n\n"
        "If `prefill_refs.https_preflight_applied` is `true`, the HTTPS endpoint, DNS, TLS, "
        "`/health`, and `/ready` references were copied from the read-only preflight report. "
        "They are still references only; the owner must review them before turning this draft "
        "into accepted evidence.\n\n"
        "## What The Owner Must Decide\n\n"
        "- The real owner-controlled domain name. Temporary wildcard DNS such as `sslip.io` is "
        "not accepted.\n"
        "- Whether first-RC observability uses real Langfuse/Sentry/metrics/alerting refs or "
        "an explicit owner-approved exception ref.\n"
        "- The approval ref and UTC approval timestamp for the exact release SHA.\n\n"
        "## File To Fill\n\n"
        f"- JSON draft: `{_display_path(json_path)}`\n"
        f"- Release SHA: `{release_sha}`\n"
        f"- Endpoint placeholder: `{domain or '<missing>'}`\n\n"
        "## Exact JSON Fields To Replace\n\n"
        "- `staging_environment_protection.external_endpoint.url`\n"
        "- `staging_environment_protection.external_endpoint.health_ref`\n"
        "- `staging_environment_protection.external_endpoint.ready_ref`\n"
        "- `staging_environment_protection.external_endpoint.ingress_ref`\n"
        "- `staging_environment_protection.dns_tls.dns_ref`\n"
        "- `staging_environment_protection.dns_tls.tls_ref`\n"
        "- `staging_environment_protection.deployed_image.image_ref`\n"
        "- `staging_environment_protection.deployed_image.digest`\n"
        "- `staging_environment_protection.owner_approval.approval_ref`\n"
        "- `staging_environment_protection.owner_approval.approved_at`\n"
        "- `staging_deploy_run.deploy_ref`\n"
        "- `staging_deploy_run.image_ref`\n"
        "- `staging_deploy_run.completed_at`\n"
        "- `staging_deploy_run.external_evidence_ref`\n"
        "- `staging_deploy_run.checks[*].status`\n"
        "- `staging_smoke_tests.health_ref`\n"
        "- `staging_smoke_tests.ready_ref`\n"
        "- `staging_smoke_tests.smoke_ref`\n"
        "- `staging_smoke_tests.completed_at`\n"
        "- `staging_smoke_tests.external_evidence_ref`\n"
        "- `staging_smoke_tests.checks[*].status`\n"
        "- `staging_rollback_rehearsal.rollback_ref`\n"
        "- `staging_rollback_rehearsal.post_rollback_health_ref`\n"
        "- `staging_rollback_rehearsal.post_rollback_ready_ref`\n"
        "- `staging_rollback_rehearsal.completed_at`\n"
        "- `staging_rollback_rehearsal.external_evidence_ref`\n"
        "- `staging_rollback_rehearsal.checks[*].status`\n"
        "- `staging_observability.workflow_event_broker.health_ref`\n"
        "- `staging_observability.langfuse.trace_ref`\n"
        "- `staging_observability.sentry.event_ref`\n"
        "- `staging_observability.metrics.metrics_ref`\n"
        "- `staging_observability.alerting.alert_ref`\n\n"
        "## Fill These With References Only\n\n"
        "- Real domain DNS A-record proof pointing to `111.228.49.160`.\n"
        "- HTTPS/443 proof for `/health` and `/ready` on the real domain.\n"
        "- Nginx ingress config path plus `nginx -t` and reload result reference.\n"
        "- Certificate reference from `certbot certificates` or the certificate issuer.\n"
        "- Observability references for broker health, trace, error/event, metrics, and alerting; "
        "or an explicit owner-approved first-RC exception reference.\n"
        "- External Stage3 deploy, smoke, and rollback references with checks changed from "
        "`blocked` to `passed` only after the operator reviews those references.\n"
        "- Running Stage3 image reference and digest from the deployed environment.\n"
        "- Owner approval reference and UTC approval timestamp.\n\n"
        "## Never Put In This File\n\n"
        "- API key values, passwords, bearer tokens, private keys, DSNs, cookies, or webhook secrets.\n"
        "- Screenshots or logs that expose secret values.\n\n"
        "## Validation Command After Filling\n\n"
        "```powershell\n"
        "python scripts/commercial_stage3_staging_external_evidence_intake.py `\n"
        f"  --input-json {_display_path(json_path)} `\n"
        f"  --current-head-sha {release_sha} `\n"
        f"  --release-sha {release_sha} `\n"
        "  --force\n"
        "```\n"
    )


def write_owner_draft(
    payload: Mapping[str, Any],
    *,
    output_json: Path = DEFAULT_OWNER_DRAFT_JSON,
    output_md: Path = DEFAULT_OWNER_DRAFT_MD,
    force: bool = False,
) -> None:
    if output_json.resolve() == DEFAULT_INPUT_JSON.resolve() and not force:
        raise ValueError(
            "refusing to write owner draft over the official Stage 3 intake input without --force"
        )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_owner_draft_markdown(payload, json_path=output_json), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate external staging evidence for Stage 3.")
    parser.add_argument("--input-json", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--current-head-sha", default=None)
    parser.add_argument("--release-sha", default=None)
    parser.add_argument("--expected-image-digest", default=None)
    parser.add_argument("--deploy-output", type=Path, default=DEFAULT_DEPLOY_OUTPUT)
    parser.add_argument("--smoke-output", type=Path, default=DEFAULT_SMOKE_OUTPUT)
    parser.add_argument("--rollback-output", type=Path, default=DEFAULT_ROLLBACK_OUTPUT)
    parser.add_argument("--observability-output", type=Path, default=DEFAULT_OBSERVABILITY_OUTPUT)
    parser.add_argument("--environment-protection-output", type=Path, default=DEFAULT_PROTECTION_OUTPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_SUMMARY_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_SUMMARY_OUTPUT_MD)
    parser.add_argument("--force", action="store_true", help="Overwrite existing ready external evidence reports.")
    parser.add_argument(
        "--write-owner-draft",
        action="store_true",
        help="Write a redaction-safe owner fillable draft instead of running the intake.",
    )
    parser.add_argument("--owner-draft-json", type=Path, default=DEFAULT_OWNER_DRAFT_JSON)
    parser.add_argument("--owner-draft-md", type=Path, default=DEFAULT_OWNER_DRAFT_MD)
    parser.add_argument("--domain", default=None, help="Optional real domain to prefill in the owner draft.")
    parser.add_argument(
        "--https-preflight-report",
        type=Path,
        default=None,
        help="Optional ready stage3_https_preflight JSON report to prefill endpoint/DNS/TLS probe refs.",
    )
    parser.add_argument("--owner", default="xiongpinji", help="Owner/reviewer name to prefill in the owner draft.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write_owner_draft:
        try:
            payload = build_owner_draft_payload(
                current_head_sha=args.current_head_sha,
                release_sha=args.release_sha,
                expected_image_digest=args.expected_image_digest,
                domain=args.domain,
                owner=args.owner,
                https_preflight_report=args.https_preflight_report,
            )
            write_owner_draft(
                payload,
                output_json=args.owner_draft_json,
                output_md=args.owner_draft_md,
                force=args.force,
            )
        except (OSError, ValueError) as exc:
            print(f"Could not write Stage 3 owner evidence draft: {exc}")
            return 2
        print("Stage 3 owner evidence draft written.")
        print(f"JSON draft written to {args.owner_draft_json}")
        print(f"Markdown checklist written to {args.owner_draft_md}")
        print("Draft status: template_not_external_evidence=true")
        return 0

    payloads, checks, input_error = build_external_evidence_payloads(
        input_path=args.input_json,
        current_head_sha=args.current_head_sha,
        release_sha=args.release_sha,
        expected_image_digest=args.expected_image_digest,
    )
    write_results = write_evidence_reports(
        payloads,
        deploy_output=args.deploy_output,
        smoke_output=args.smoke_output,
        rollback_output=args.rollback_output,
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
