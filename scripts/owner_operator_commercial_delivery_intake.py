#!/usr/bin/env python3
"""Fail-closed intake for owner/operator commercial-delivery refs.

This script validates the shape of owner/operator returned references before
they are routed to Review and F verification. It is read-only with respect to
external systems: it does not run owner gates, deploy, dispatch workflows,
refresh release artifacts, or inspect secret values.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_INPUT = REPORT_DIR / "owner-operator-commercial-delivery-input.json"
DEFAULT_REPORT = REPORT_DIR / "owner-operator-commercial-delivery-intake.json"
DEFAULT_TEMPLATE = ROOT / "docs" / "owner-operator-commercial-delivery-input-template.json"

SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{20,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\b(?:postgres(?:ql)?|mysql|redis|mongodb|amqp|neo4j)(?:\+srv)?://[^\s\"']+", re.IGNORECASE),
    re.compile(r"DefaultEndpointsProtocol=[^;\s]+;AccountName=[^;\s]+;AccountKey=[^;\s]+", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
SECRET_FIELD_NAMES = {
    "access_token",
    "api_key",
    "auth_header",
    "bearer_token",
    "client_secret",
    "connection_string",
    "cookie",
    "data",
    "database_url",
    "decoded_secret",
    "dsn",
    "password",
    "private_key",
    "refresh_token",
    "redis_url",
    "secret",
    "secret_value",
    "token",
    "webhook_secret",
}
DECISIONS = {"include", "exclude", "defer"}
SHA_BOUNDARY_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])")
SHA_BOUNDARY_FIELD_NAMES = {
    "accepted_sha_environment_boundary",
    "git_sha",
    "head_sha",
    "release_sha",
    "target_sha",
}
STATUS_ALLOWED_VALUES: dict[tuple[str, str, str], set[str]] = {
    ("owner_gate_refs", "provider", "status"): {"passed"},
    ("owner_gate_refs", "feishu_webhook_contract", "status"): {"passed"},
    ("owner_gate_refs", "github_issue_to_pr_dry_run", "no_execute_mutation_status"): {
        "passed",
        "no_mutation",
        "no_mutation_performed",
    },
    ("owner_gate_refs", "github_issue_to_pr_execute_preflight", "no_mutation_status"): {
        "passed",
        "no_mutation",
        "no_mutation_performed",
    },
    ("owner_gate_refs", "hosted_github_actions_commercial_rc", "linux_job_status"): {"success", "passed"},
    ("owner_gate_refs", "hosted_github_actions_commercial_rc", "windows_installer_job_status"): {
        "success",
        "passed",
    },
    ("owner_gate_refs", "refresh_release_chain_owner_verified", "status"): {
        "owner_verified",
        "passed",
        "verified",
    },
    ("stage3_production_refs", "external_endpoint", "smoke_status"): {"passed", "success"},
}


@dataclass(frozen=True)
class IntakeCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerOperatorIntakeReport:
    status: str
    generated_at: str
    input_path: str
    input_loaded: bool
    target_sha: str | None
    ready_for_review: bool
    intake_only_not_evidence: bool
    mutation_performed: bool
    owner_gate_execution_performed: bool
    stage3_execution_performed: bool
    release_refresh_performed: bool
    final_gate_performed: bool
    raw_secret_values_recorded: bool
    checks: list[IntakeCheck]
    missing_fields: list[str]
    redaction_violations: list[str]
    rejected_inputs: list[str]
    tag_blockers: list[str]
    next_chain: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


OWNER_GATE_REQUIRED: dict[str, tuple[str, ...]] = {
    "owner_approval": (
        "target_sha",
        "approval_ref",
        "approval_timestamp",
        "approver_identity_ref",
        "approved_scope",
    ),
    "provider": (
        "provider_backend",
        "model_ref",
        "credential_variable_name",
        "provider_smoke_ref",
        "status",
    ),
    "feishu_webhook_contract": (
        "app_id_variable_name",
        "app_secret_variable_name",
        "encrypt_key_variable_name",
        "verification_ref",
        "status",
    ),
    "github_issue_to_pr_dry_run": (
        "disposable_issue_ref",
        "repository_ref",
        "dry_run_ref",
        "no_execute_mutation_status",
    ),
    "github_issue_to_pr_execute_preflight": (
        "github_token_variable_name",
        "disposable_issue_ref",
        "issue_probe_ref",
        "repo_permission_probe_ref",
        "no_mutation_status",
    ),
    "hosted_github_actions_commercial_rc": (
        "run_ref",
        "head_sha",
        "linux_job_status",
        "windows_installer_job_status",
        "evidence_artifact_ref",
        "artifact_digest_ref",
    ),
    "refresh_release_chain_owner_verified": (
        "owner_verified_ref",
        "status",
        "timestamp",
    ),
}

STAGE3_REQUIRED: dict[str, tuple[str, ...]] = {
    "external_endpoint": (
        "public_https_endpoint",
        "health_url",
        "ready_url",
        "smoke_run_ref",
        "smoke_status",
        "timestamp",
    ),
    "dns_tls_lb_ingress": (
        "hostname",
        "dns_record_ref",
        "tls_certificate_ref",
        "ingress_ref",
        "load_balancer_ref",
        "environment_name",
    ),
    "deployed_image": (
        "image_ref",
        "digest",
        "workload_imageid_ref",
        "provenance_ref",
        "rollout_ref",
    ),
    "observability": (
        "metrics_ref",
        "alert_ref",
        "log_search_ref",
        "rabbitmq_health_ref",
        "langfuse_trace_ref",
        "sentry_event_ref",
    ),
    "runtime_bindings": (
        "db_binding_ref",
        "redis_binding_ref",
        "rabbitmq_binding_ref",
        "qdrant_binding_ref",
        "neo4j_binding_ref",
        "langfuse_binding_ref",
        "sentry_event_ref",
    ),
    "external_secret_eso": (
        "eso_ready_ref",
        "cluster_secret_store_name",
        "cluster_secret_store_ready_ref",
        "external_secret_object_refs",
        "target_secret_object_names",
        "expected_key_names",
        "workload_secretkeyref_refs",
    ),
    "rollback": (
        "rollback_run_ref",
        "rollback_target_ref",
        "pre_rollback_digest",
        "post_rollback_digest",
        "post_rollback_health_ref",
        "started_at",
        "completed_at",
    ),
    "owner_approval": (
        "approval_ref",
        "approval_timestamp",
        "approver_identity_ref",
        "environment_name",
        "release_sha",
    ),
    "stage3_run_artifacts": (
        "stage3_run_ref",
        "stage3_artifact_ref",
        "stage3_artifact_digest_ref",
    ),
    "production_readiness_acceptance": (
        "acceptance_ref",
        "acceptance_timestamp",
        "accepted_sha_environment_boundary",
    ),
}

PANDA_REQUIRED: dict[str, tuple[str, ...]] = {
    "panda_qa_smoke_script": ("disposition", "path", "owner_ref", "tag_impact"),
    "canonical_role_png_set": ("disposition", "paths", "owner_ref", "tag_impact"),
    "modified_role_pngs": ("disposition", "paths_or_pattern", "owner_ref", "tag_impact"),
    "untracked_xagent_reference_pngs": ("disposition", "paths_or_pattern", "owner_ref", "tag_impact"),
    "smoke_artifact_treatment": ("disposition", "artifact_refs", "owner_ref", "tag_impact"),
    "release_notes_wording": ("disposition", "wording", "owner_ref", "tag_impact"),
    "screenshot_review_refs": ("disposition", "refs", "owner_ref", "tag_impact"),
    "bff_contract_refs": ("disposition", "refs", "owner_ref", "tag_impact"),
    "auth_tenant_refs": ("disposition", "refs", "owner_ref", "tag_impact"),
    "accessibility_security_refs": ("disposition", "refs", "owner_ref", "tag_impact"),
    "asset_manifest_refs": ("disposition", "refs", "owner_ref", "tag_impact"),
    "release_manifest_refs": ("disposition", "refs", "owner_ref", "tag_impact"),
    "frontend_browser_claim_boundary": ("disposition", "permitted_wording", "owner_ref", "tag_impact"),
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return str(path.resolve(strict=False))


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"input file not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"could not read input file {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"input file is not a JSON object: {_display_path(path)}"
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


def _missing_fields(section: Any, required_fields: Sequence[str], *, prefix: str) -> list[str]:
    if not isinstance(section, Mapping):
        return [f"{prefix}.{field_name}" for field_name in required_fields]
    return [f"{prefix}.{field_name}" for field_name in required_fields if not _nonempty(section.get(field_name))]


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        values: list[str] = []
        for child in value.values():
            values.extend(_string_values(child))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for child in value:
            values.extend(_string_values(child))
        return values
    return []


def _secret_redaction_violations(value: Any, *, prefix: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            key_name = key_text.lower()
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_name in SECRET_FIELD_NAMES and _nonempty(child):
                violations.append(path)
                continue
            violations.extend(_secret_redaction_violations(child, prefix=path))
        return sorted(set(violations))

    for candidate in _string_values(value):
        if any(pattern.search(candidate) for pattern in SECRET_VALUE_PATTERNS):
            violations.append(prefix or "<root>")
    return sorted(set(violations))


def _invalid_status_fields(payload: Mapping[str, Any]) -> list[str]:
    invalid: list[str] = []
    for (group_name, section_name, field_name), allowed in STATUS_ALLOWED_VALUES.items():
        group = _section_payload(payload, group_name)
        section = group.get(section_name) if isinstance(group, Mapping) else None
        value = section.get(field_name) if isinstance(section, Mapping) else None
        if not _nonempty(value):
            continue
        normalized = str(value).strip().lower()
        if normalized not in allowed:
            invalid.append(f"{group_name}.{section_name}.{field_name}")
    return sorted(set(invalid))


def _section_payload(payload: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = payload.get(name)
    return value if isinstance(value, Mapping) else {}


def _required_section_checks(
    payload: Mapping[str, Any],
    *,
    group_name: str,
    requirements: Mapping[str, Sequence[str]],
) -> tuple[list[IntakeCheck], list[str]]:
    checks: list[IntakeCheck] = []
    missing: list[str] = []
    group = _section_payload(payload, group_name)
    for section_name, fields in requirements.items():
        section = group.get(section_name) if isinstance(group, Mapping) else None
        section_missing = _missing_fields(section, fields, prefix=f"{group_name}.{section_name}")
        missing.extend(section_missing)
        checks.append(
            _check(
                f"{group_name}_{section_name}_required_fields_present",
                not section_missing,
                details={"missing_fields": section_missing},
                error=f"{group_name}.{section_name} is missing required returned refs",
            )
        )
    return checks, missing


def _panda_decision_checks(payload: Mapping[str, Any]) -> tuple[list[IntakeCheck], list[str], list[str]]:
    checks, missing = _required_section_checks(
        payload,
        group_name="panda_frontend_decisions",
        requirements=PANDA_REQUIRED,
    )
    rejected: list[str] = []
    group = _section_payload(payload, "panda_frontend_decisions")
    for section_name in PANDA_REQUIRED:
        section = group.get(section_name) if isinstance(group, Mapping) else None
        disposition = section.get("disposition") if isinstance(section, Mapping) else None
        if _nonempty(disposition) and str(disposition) not in DECISIONS:
            rejected.append(f"panda_frontend_decisions.{section_name}.disposition")
    checks.append(
        _check(
            "panda_frontend_decisions_dispositions_valid",
            not rejected,
            details={"invalid_dispositions": rejected},
            error="Panda/frontend decisions must use include, exclude, or defer",
        )
    )
    return checks, missing, rejected


def _sha_mismatches(payload: Mapping[str, Any], target_sha: str | None) -> list[str]:
    if not target_sha or not SHA_RE.match(target_sha):
        return []
    mismatches: list[str] = []

    def visit(value: Any, *, prefix: str = "") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key)
                key_name = key_text.lower()
                path = f"{prefix}.{key_text}" if prefix else key_text
                if isinstance(child, str) and key_name in SHA_BOUNDARY_FIELD_NAMES:
                    matches = SHA_BOUNDARY_RE.findall(child)
                    for match in matches:
                        if match.lower() != target_sha.lower():
                            mismatches.append(path)
                            break
                visit(child, prefix=path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, prefix=f"{prefix}[{index}]")

    visit(payload)
    return sorted(set(mismatches))


def build_template_payload(target_sha: str = "adbce7a93854870ef665fe03c39051491a90b9d6") -> dict[str, Any]:
    return {
        "target_sha": target_sha,
        "owner_gate_refs": {
            "owner_approval": {
                "target_sha": target_sha,
                "approval_ref": "",
                "approval_timestamp": "",
                "approver_identity_ref": "",
                "approved_scope": "SHA + environment + release boundary",
            },
            "provider": {
                "provider_backend": "",
                "model_ref": "",
                "credential_variable_name": "",
                "provider_smoke_ref": "",
                "status": "",
            },
            "feishu_webhook_contract": {
                "app_id_variable_name": "",
                "app_secret_variable_name": "",
                "encrypt_key_variable_name": "",
                "verification_ref": "",
                "status": "",
            },
            "github_issue_to_pr_dry_run": {
                "disposable_issue_ref": "",
                "repository_ref": "",
                "dry_run_ref": "",
                "no_execute_mutation_status": "",
            },
            "github_issue_to_pr_execute_preflight": {
                "github_token_variable_name": "",
                "disposable_issue_ref": "",
                "issue_probe_ref": "",
                "repo_permission_probe_ref": "",
                "no_mutation_status": "",
            },
            "hosted_github_actions_commercial_rc": {
                "run_ref": "",
                "head_sha": target_sha,
                "linux_job_status": "",
                "windows_installer_job_status": "",
                "evidence_artifact_ref": "",
                "artifact_digest_ref": "",
            },
            "refresh_release_chain_owner_verified": {
                "owner_verified_ref": "",
                "status": "",
                "timestamp": "",
            },
        },
        "stage3_production_refs": {
            "external_endpoint": {
                "public_https_endpoint": "",
                "health_url": "",
                "ready_url": "",
                "smoke_run_ref": "",
                "smoke_status": "",
                "timestamp": "",
            },
            "dns_tls_lb_ingress": {
                "hostname": "",
                "dns_record_ref": "",
                "tls_certificate_ref": "",
                "ingress_ref": "",
                "load_balancer_ref": "",
                "environment_name": "",
            },
            "deployed_image": {
                "image_ref": "",
                "digest": "",
                "workload_imageid_ref": "",
                "provenance_ref": "",
                "rollout_ref": "",
            },
            "observability": {
                "metrics_ref": "",
                "alert_ref": "",
                "log_search_ref": "",
                "rabbitmq_health_ref": "",
                "langfuse_trace_ref": "",
                "sentry_event_ref": "",
            },
            "runtime_bindings": {
                "db_binding_ref": "",
                "redis_binding_ref": "",
                "rabbitmq_binding_ref": "",
                "qdrant_binding_ref": "",
                "neo4j_binding_ref": "",
                "langfuse_binding_ref": "",
                "sentry_event_ref": "",
            },
            "external_secret_eso": {
                "eso_ready_ref": "",
                "cluster_secret_store_name": "",
                "cluster_secret_store_ready_ref": "",
                "external_secret_object_refs": [],
                "target_secret_object_names": [],
                "expected_key_names": [],
                "workload_secretkeyref_refs": [],
            },
            "rollback": {
                "rollback_run_ref": "",
                "rollback_target_ref": "",
                "pre_rollback_digest": "",
                "post_rollback_digest": "",
                "post_rollback_health_ref": "",
                "started_at": "",
                "completed_at": "",
            },
            "owner_approval": {
                "approval_ref": "",
                "approval_timestamp": "",
                "approver_identity_ref": "",
                "environment_name": "",
                "release_sha": target_sha,
            },
            "stage3_run_artifacts": {
                "stage3_run_ref": "",
                "stage3_artifact_ref": "",
                "stage3_artifact_digest_ref": "",
            },
            "production_readiness_acceptance": {
                "acceptance_ref": "",
                "acceptance_timestamp": "",
                "accepted_sha_environment_boundary": "",
            },
        },
        "panda_frontend_decisions": {
            "panda_qa_smoke_script": {
                "disposition": "",
                "path": "frontend/scripts/panda-qa-smoke.mjs",
                "owner_ref": "",
                "tag_impact": "",
            },
            "canonical_role_png_set": {"disposition": "", "paths": [], "owner_ref": "", "tag_impact": ""},
            "modified_role_pngs": {"disposition": "", "paths_or_pattern": "", "owner_ref": "", "tag_impact": ""},
            "untracked_xagent_reference_pngs": {
                "disposition": "",
                "paths_or_pattern": "frontend/src/panda/assets/roles/xagent-reference-*.png",
                "owner_ref": "",
                "tag_impact": "",
            },
            "smoke_artifact_treatment": {"disposition": "", "artifact_refs": [], "owner_ref": "", "tag_impact": ""},
            "release_notes_wording": {"disposition": "", "wording": "", "owner_ref": "", "tag_impact": ""},
            "screenshot_review_refs": {"disposition": "", "refs": [], "owner_ref": "", "tag_impact": ""},
            "bff_contract_refs": {"disposition": "", "refs": [], "owner_ref": "", "tag_impact": ""},
            "auth_tenant_refs": {"disposition": "", "refs": [], "owner_ref": "", "tag_impact": ""},
            "accessibility_security_refs": {"disposition": "", "refs": [], "owner_ref": "", "tag_impact": ""},
            "asset_manifest_refs": {"disposition": "", "refs": [], "owner_ref": "", "tag_impact": ""},
            "release_manifest_refs": {"disposition": "", "refs": [], "owner_ref": "", "tag_impact": ""},
            "frontend_browser_claim_boundary": {
                "disposition": "",
                "permitted_wording": "",
                "owner_ref": "",
                "tag_impact": "",
            },
        },
    }


def build_intake_report(input_path: Path = DEFAULT_INPUT) -> OwnerOperatorIntakeReport:
    payload, input_error = _read_json_object(input_path)
    input_loaded = input_error is None
    checks: list[IntakeCheck] = []
    missing_fields: list[str] = []
    rejected_inputs: list[str] = []
    tag_blockers: list[str] = []

    target_sha = str(payload.get("target_sha") or "") if input_loaded else ""
    target_sha_valid = bool(target_sha and SHA_RE.match(target_sha))
    checks.append(
        _check(
            "input_loaded",
            input_loaded,
            details={"input_path": _display_path(input_path)},
            error=input_error or "input file could not be loaded",
        )
    )
    checks.append(
        _check(
            "target_sha_valid",
            target_sha_valid,
            details={"target_sha": target_sha or None},
            error="target_sha must be a 40-character commit SHA",
        )
    )
    if not target_sha_valid:
        missing_fields.append("target_sha")

    owner_checks, owner_missing = _required_section_checks(
        payload,
        group_name="owner_gate_refs",
        requirements=OWNER_GATE_REQUIRED,
    )
    stage3_checks, stage3_missing = _required_section_checks(
        payload,
        group_name="stage3_production_refs",
        requirements=STAGE3_REQUIRED,
    )
    panda_checks, panda_missing, panda_rejected = _panda_decision_checks(payload)
    checks.extend(owner_checks)
    checks.extend(stage3_checks)
    checks.extend(panda_checks)
    missing_fields.extend(owner_missing)
    missing_fields.extend(stage3_missing)
    missing_fields.extend(panda_missing)
    rejected_inputs.extend(panda_rejected)

    redaction_violations = _secret_redaction_violations(payload)
    invalid_status_fields = _invalid_status_fields(payload)
    sha_mismatches = _sha_mismatches(payload, target_sha if target_sha_valid else None)
    rejected_inputs.extend(invalid_status_fields)
    rejected_inputs.extend(sha_mismatches)
    checks.append(
        _check(
            "redaction_boundary_clean",
            not redaction_violations,
            details={"redaction_violations": redaction_violations},
            error="input contains forbidden secret-looking fields or values",
        )
    )
    checks.append(
        _check(
            "critical_status_values_valid",
            not invalid_status_fields,
            details={"invalid_status_fields": invalid_status_fields},
            error="critical status fields must be passed/success/no-mutation/verified values",
        )
    )
    checks.append(
        _check(
            "sha_boundary_consistent",
            not sha_mismatches,
            details={"sha_mismatches": sha_mismatches},
            error="one or more returned refs are bound to a different SHA",
        )
    )

    if missing_fields:
        tag_blockers.append("owner/operator returned input has missing required fields")
    if redaction_violations:
        tag_blockers.append("owner/operator returned input violates redaction boundary")
    if invalid_status_fields:
        tag_blockers.append("owner/operator returned input has non-passing critical status fields")
    if sha_mismatches:
        tag_blockers.append("owner/operator returned input has SHA boundary mismatches")
    if panda_rejected:
        tag_blockers.append("Panda/frontend returned decisions contain invalid dispositions")

    ready = input_loaded and all(check.status == "passed" for check in checks)
    status = (
        "owner_operator_commercial_delivery_intake_ready_for_review"
        if ready
        else "owner_operator_commercial_delivery_intake_blocked"
    )
    return OwnerOperatorIntakeReport(
        status=status,
        generated_at=_utc_now(),
        input_path=_display_path(input_path),
        input_loaded=input_loaded,
        target_sha=target_sha if target_sha else None,
        ready_for_review=ready,
        intake_only_not_evidence=True,
        mutation_performed=False,
        owner_gate_execution_performed=False,
        stage3_execution_performed=False,
        release_refresh_performed=False,
        final_gate_performed=False,
        raw_secret_values_recorded=False,
        checks=checks,
        missing_fields=sorted(set(missing_fields)),
        redaction_violations=redaction_violations,
        rejected_inputs=sorted(set(rejected_inputs)),
        tag_blockers=tag_blockers,
        next_chain=[
            "D owner-gate intake completeness and redaction check",
            "E Stage3/prod admissibility triage",
            "M Panda/frontend decision intake",
            "Review admissibility and overclaim audit",
            "F independent verification after Review accepts concrete refs",
            "B release consistency only after F verification and stable release boundary",
            "Final gate only after owner gates, Stage3/prod evidence, release consistency, and closure snapshot are ready",
        ],
        known_limits=[
            "This intake validates returned refs and decisions only.",
            "It does not run owner gates, Stage3/prod, release gates, final gate, deployments, or external mutations.",
            "A ready intake is not evidence completion, owner approval, deployment proof, or tag readiness.",
        ],
    )


def write_json(payload: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--template-output", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--write-template", action="store_true")
    parser.add_argument("--fail-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write_template:
        write_json(build_template_payload(), args.template_output)
        print(f"Template written to {args.template_output}")

    report = build_intake_report(args.input)
    write_json(report.to_dict(), args.output)
    print(f"Owner/operator commercial delivery intake status: {report.status}")
    print(f"Report written to {args.output}")
    if args.fail_blocked and not report.ready_for_review:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
