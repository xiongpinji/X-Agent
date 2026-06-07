#!/usr/bin/env python3
"""Generate a commercial RC release receipt and SHA-256 sidecar.

The receipt is a runtime artifact for handoff and archival. It contains only
release evidence metadata: artifact checksum, gate statuses, owner gates, and
staging/source-bundle summaries. It does not include generated secret values.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
RELEASE_DIR = ROOT / ".xagent_runtime" / "release"
DEFAULT_ARTIFACT_INTEGRITY = REPORT_DIR / "rc-artifact-integrity-gate.json"
DEFAULT_FINAL_GATE = REPORT_DIR / "rc-final-gate.json"
DEFAULT_RELEASE_DIFF_REVIEW_GATE = REPORT_DIR / "rc-release-diff-review-gate.json"
DEFAULT_DEPLOYMENT_DOCS_GATE = REPORT_DIR / "rc-deployment-docs-gate.json"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_STAGING_PLAN = REPORT_DIR / "rc-staging-plan.json"
DEFAULT_OWNER_GATE_PLAN = REPORT_DIR / "rc-owner-gate-plan.json"
DEFAULT_OWNER_GATE_RUNNER = REPORT_DIR / "rc-owner-gate-runner.json"
DEFAULT_OWNER_HANDOFF_GATE = REPORT_DIR / "rc-owner-handoff-gate.json"
DEFAULT_OWNER_ENV_TEMPLATE = REPORT_DIR / "rc-owner-env-template.json"
DEFAULT_OWNER_GATE_CHECKLIST = REPORT_DIR / "rc-owner-gate-checklist.json"
DEFAULT_INSTALL_RELEASE_GATE = REPORT_DIR / "rc-install-release-gate.json"
DEFAULT_SINGLE_USER_LOCAL_GATE = REPORT_DIR / "rc-single-user-local-gate.json"
DEFAULT_SUPPLY_CHAIN_GATE = REPORT_DIR / "rc-supply-chain-gate.json"
DEFAULT_SECRETS_GATE = REPORT_DIR / "rc-secrets-gate.json"
DEFAULT_OUTPUT = RELEASE_DIR / "x-agent-commercial-rc-receipt.json"

SECRET_VALUE_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b"),
    re.compile(r"\b[A-Za-z0-9_./+=-]{32,}\b"),
)
ALLOWED_TEMPLATE_VALUE_MARKERS = ("<", ">", "set-in-owner-secret-store", "openai|deepseek", "github.com/<owner>")
OWNER_CHECKLIST_REQUIRED_NEXT_COMMAND_TOKENS = (
    "rc_owner_gate_runner.py --gate all",
    "--env-file",
    "rc_external_smoke.py",
    "--require-configured",
    "--github-execute-preflight",
    "--github-actions-preflight",
)
OWNER_GATE_RUNNER_REQUIRED_ALL_COMMAND_TOKENS = (
    "scripts/rc_external_smoke.py",
    "--github-execute-preflight",
    "--github-actions-preflight",
    "--require-configured",
)
OWNER_GATE_RUNNER_REQUIRED_ENV_FILE = ".xagent_runtime/reports/rc-owner-env-template.env"
REQUIRED_OWNER_GATE_RUNNER_REFRESH_STEPS = {
    "refresh:rc_owner_gate_plan",
    "refresh:rc_owner_env_template",
    "refresh:rc_owner_gate_checklist",
    "refresh:rc_owner_handoff_gate",
    "refresh:rc_final_gate",
}
OPTIONAL_SKIPPED_CHECKS_BY_GATE = {
    "single_user_local_gate": {"rc2_release_handoff_snapshot"},
}

REQUIRED_OWNER_HANDOFF_CHECKS = {
    "owner_gate_plan",
    "owner_env_template",
    "owner_gate_checklist",
    "evidence_paths",
}

OWNER_HANDOFF_PRIVACY_CHECKS = {
    "owner_env_template",
    "owner_gate_checklist",
}


@dataclass(frozen=True)
class ReceiptCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ReleaseReceipt:
    status: str
    generated_at: str
    artifact: dict[str, Any]
    final_gate: dict[str, Any]
    source_bundle: dict[str, Any]
    staging_plan: dict[str, Any]
    owner_gates: list[dict[str, Any]]
    owner_gate_next_actions: list[dict[str, Any]]
    owner_gate_evidence: dict[str, Any]
    owner_gate_runner: dict[str, Any]
    owner_handoff_gate: dict[str, Any]
    owner_env_template: dict[str, Any]
    owner_gate_checklist: dict[str, Any]
    release_diff_review_gate: dict[str, Any]
    deployment_docs_gate: dict[str, Any]
    install_release_gate: dict[str, Any]
    single_user_local_gate: dict[str, Any]
    supply_chain_gate: dict[str, Any]
    secrets_gate: dict[str, Any]
    checks: list[ReceiptCheck]
    sidecars: dict[str, str | None]
    approval_request: dict[str, Any]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing report: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {path}"
    return payload, None


def _check_report(name: str, payload: dict[str, Any] | None, error: str | None, expected: set[str]) -> ReceiptCheck:
    if error:
        return ReceiptCheck(name, "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    return ReceiptCheck(
        name,
        "passed" if status in expected else "failed",
        details={"status": status, "expected": sorted(expected)},
        error=None if status in expected else f"expected {sorted(expected)}, got {status}",
    )


def _final_gate_bootstrap_ready(payload: dict[str, Any] | None) -> bool:
    """Allow receipt regeneration when final gate is blocked only by refresh artifacts."""

    if not payload:
        return False
    if payload.get("status") == "ready_with_receipt_refresh_required":
        return True
    if payload.get("status") != "failed":
        return False
    local_gates = payload.get("local_gates")
    if not isinstance(local_gates, list):
        return False
    blockers = [gate for gate in local_gates if isinstance(gate, dict) and gate.get("ok") is not True]
    allowed_blockers = {"release_receipt", "evidence_pack"}
    if not blockers or any(gate.get("name") not in allowed_blockers for gate in blockers):
        return False
    for gate in blockers:
        if gate.get("name") == "release_receipt":
            continue
        details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        error = str(gate.get("error") or "").lower()
        refresh_only_error = (
            "older than required release reports" in error
            or "required evidence_pack checks failed: release_receipt" in error
            or "receipt contains failed checks: final_gate" in error
        )
        if not details.get("stale_reports") and not refresh_only_error:
            return False
    return True


def _check_final_gate_report(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("final_gate", "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    expected = {"ready_with_owner_gates", "ready_for_rc_tag"}
    if status in expected:
        return ReceiptCheck("final_gate", "passed", details={"status": status, "expected": sorted(expected)})
    if _final_gate_bootstrap_ready(payload):
        return ReceiptCheck(
            "final_gate",
            "passed",
            details={
                "status": status,
                "expected": sorted(expected | {"ready_with_receipt_refresh_required"}),
                "bootstrap_allowed": True,
                "reason": "final gate requires release receipt refresh",
            },
        )
    return ReceiptCheck(
        "final_gate",
        "failed",
        details={"status": status, "expected": sorted(expected)},
        error=f"expected {sorted(expected)}, got {status}",
    )


def _check_release_artifact_consistency(
    artifact_payload: dict[str, Any] | None,
    source_payload: dict[str, Any] | None,
) -> ReceiptCheck:
    artifact_path = str((artifact_payload or {}).get("artifact_path") or "")
    source_output = str((source_payload or {}).get("output_path") or "")
    artifact_sha = str((artifact_payload or {}).get("artifact_sha256") or "")
    artifact_file_count = (artifact_payload or {}).get("file_count")
    source_file_count = (source_payload or {}).get("file_count")
    problems: list[str] = []

    if not artifact_path:
        problems.append("artifact_integrity_gate.artifact_path is missing")
    if not source_output:
        problems.append("source_bundle.output_path is missing")
    if artifact_path and source_output and Path(artifact_path) != Path(source_output):
        problems.append("artifact_integrity_gate.artifact_path does not match source_bundle.output_path")
    if artifact_path and not Path(artifact_path).is_file():
        problems.append("artifact file does not exist")
    if len(artifact_sha) != 64 or any(char not in "0123456789abcdef" for char in artifact_sha.lower()):
        problems.append("artifact_integrity_gate.artifact_sha256 is not a 64-character hex digest")
    if artifact_file_count != source_file_count:
        problems.append("artifact_integrity_gate.file_count does not match source_bundle.file_count")

    return ReceiptCheck(
        "release_artifact_consistency",
        "passed" if not problems else "failed",
        details={
            "artifact_path": artifact_path,
            "source_output_path": source_output,
            "artifact_sha256": artifact_sha,
            "artifact_file_count": artifact_file_count,
            "source_file_count": source_file_count,
        },
        error="; ".join(problems) if problems else None,
    )


def _named_check(payload: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    checks = (payload or {}).get("checks")
    if not isinstance(checks, list):
        return None
    for check in checks:
        if isinstance(check, dict) and check.get("name") == name:
            return check
    return None


def _artifact_security_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    check = _named_check(payload, "zip_security_scan")
    details = check.get("details", {}) if isinstance(check, dict) else {}
    if not isinstance(details, dict):
        details = {}
    secret_findings = details.get("secret_findings")
    excluded_reference_findings = details.get("excluded_reference_findings")
    local_path_findings = details.get("local_path_findings")
    return {
        "zip_security_scan_status": check.get("status") if isinstance(check, dict) else None,
        "scanned_text_files": details.get("scanned_text_files"),
        "secret_finding_count": len(secret_findings) if isinstance(secret_findings, list) else None,
        "excluded_reference_finding_count": (
            len(excluded_reference_findings) if isinstance(excluded_reference_findings, list) else None
        ),
        "local_path_finding_count": len(local_path_findings) if isinstance(local_path_findings, list) else None,
    }


def _check_artifact_security_scan(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("artifact_security_scan", "failed", error=error)
    assert payload is not None
    check = _named_check(payload, "zip_security_scan")
    problems: list[str] = []
    details = check.get("details", {}) if isinstance(check, dict) else {}
    if check is None:
        problems.append("artifact integrity report is missing zip_security_scan")
        details = {}
    elif check.get("status") != "passed":
        problems.append(f"expected zip_security_scan passed, got {check.get('status')}")
    if not isinstance(details, dict):
        problems.append("zip_security_scan.details must be a JSON object")
        details = {}

    for key, label in (
        ("secret_findings", "secret-like findings"),
        ("excluded_reference_findings", "excluded-area references"),
        ("local_path_findings", "local user/runtime path findings"),
    ):
        findings = details.get(key)
        if not isinstance(findings, list):
            problems.append(f"zip_security_scan.details.{key} must be a list")
        elif findings:
            problems.append(f"zip_security_scan reported {label}")
    scanned_text_files = details.get("scanned_text_files")
    if not isinstance(scanned_text_files, int) or scanned_text_files <= 0:
        problems.append("zip_security_scan must scan at least one text file")

    return ReceiptCheck(
        "artifact_security_scan",
        "passed" if not problems else "failed",
        details=_artifact_security_summary(payload),
        error="; ".join(problems) if problems else None,
    )


def _check_owner_gate_plan_consistency(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("owner_gate_plan_consistency", "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    gates = payload.get("gates")
    freshness = payload.get("evidence_freshness")
    problems: list[str] = []

    if not isinstance(gates, list) or not gates:
        problems.append("owner_gate_plan.gates is missing")
    if status == "verified":
        if not isinstance(freshness, dict):
            problems.append("owner_gate_plan.evidence_freshness is missing")
        else:
            if freshness.get("required") is not True:
                problems.append("owner_gate_plan.evidence_freshness.required must be true")
            if freshness.get("fresh") is not True:
                problems.append("owner_gate_plan evidence is not fresh for the current source bundle")
        if isinstance(gates, list) and any(not isinstance(gate, dict) or gate.get("status") != "verified" for gate in gates):
            problems.append("owner_gate_plan status is verified but not every gate is verified")

    return ReceiptCheck(
        "owner_gate_plan_consistency",
        "passed" if not problems else "failed",
        details={
            "status": status,
            "gate_count": len(gates) if isinstance(gates, list) else 0,
            "evidence_freshness": freshness if isinstance(freshness, dict) else {},
        },
        error="; ".join(problems) if problems else None,
    )


def _is_placeholder_value(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ALLOWED_TEMPLATE_VALUE_MARKERS)


def _contains_secret_like_value(value: str) -> bool:
    if not value or _is_placeholder_value(value):
        return False
    return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def _check_owner_env_template(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("owner_env_template", "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    entries = payload.get("entries")
    problems: list[str] = []
    if status != "created":
        problems.append(f"expected created, got {status}")
    if not isinstance(entries, list) or not entries:
        problems.append("owner_env_template.entries is missing or empty")
    else:
        for entry in entries:
            if not isinstance(entry, dict):
                problems.append("owner_env_template.entries contains a non-object entry")
                continue
            name = str(entry.get("name") or "")
            value = str(entry.get("value") or "")
            required_by = entry.get("required_by")
            if not name:
                problems.append("owner_env_template entry name is missing")
            if not isinstance(required_by, list) or not required_by:
                problems.append(f"owner_env_template.{name or 'entry'}.required_by is missing or empty")
            if _contains_secret_like_value(value):
                problems.append(f"owner_env_template.{name or 'entry'} contains a secret-like value")
    return ReceiptCheck(
        "owner_env_template",
        "passed" if not problems else "failed",
        details=_owner_env_template_summary(payload),
        error="; ".join(problems) if problems else None,
    )


def _check_owner_gate_checklist(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("owner_gate_checklist", "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    gates = payload.get("gates")
    next_commands = payload.get("next_commands")
    problems: list[str] = []
    if status not in {"verified", "ready_to_run", "action_required"}:
        problems.append(f"expected verified, ready_to_run, or action_required; got {status}")
    if not isinstance(gates, list) or not gates:
        problems.append("owner_gate_checklist.gates is missing or empty")
    if not isinstance(next_commands, list) or not next_commands:
        problems.append("owner_gate_checklist.next_commands is missing or empty")
    else:
        commands = _string_list(next_commands)
        for token in OWNER_CHECKLIST_REQUIRED_NEXT_COMMAND_TOKENS:
            if not any(token in command for command in commands):
                problems.append(f"owner_gate_checklist.next_commands missing token: {token}")
    return ReceiptCheck(
        "owner_gate_checklist",
        "passed" if not problems else "failed",
        details=_owner_gate_checklist_summary(payload),
        error="; ".join(problems) if problems else None,
    )


def _check_owner_gate_runner(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("owner_gate_runner", "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    problems: list[str] = []
    if status not in {"planned", "passed"}:
        problems.append(f"expected planned or passed, got {status}")
    if payload.get("selected_gate") != "all":
        problems.append("owner_gate_runner must be generated for --gate all")
    if payload.get("dry_run") is not True:
        problems.append("owner_gate_runner receipt input must be a dry-run report")
    if payload.get("env_file") != OWNER_GATE_RUNNER_REQUIRED_ENV_FILE:
        problems.append(f"owner_gate_runner env_file must be {OWNER_GATE_RUNNER_REQUIRED_ENV_FILE}")
    for key in ("loaded_env_names", "owner_gate_env_names"):
        value = payload.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            problems.append(f"owner_gate_runner {key} must be a list of env variable names")
    if not _is_env_group_list(payload.get("missing_env_groups")):
        problems.append("owner_gate_runner missing_env_groups must be a list of env variable name groups")

    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        problems.append("owner_gate_runner.steps is missing or empty")
    else:
        step_names = {
            str(step.get("name") or "")
            for step in steps
            if isinstance(step, dict)
        }
        missing_refresh = sorted(REQUIRED_OWNER_GATE_RUNNER_REFRESH_STEPS.difference(step_names))
        if missing_refresh:
            problems.append(f"owner_gate_runner missing refresh steps: {', '.join(missing_refresh)}")

        first_step = steps[0] if isinstance(steps[0], dict) else {}
        command = first_step.get("command") if isinstance(first_step, dict) else []
        if not isinstance(command, list):
            problems.append("owner_gate_runner first command is missing")
        else:
            for token in OWNER_GATE_RUNNER_REQUIRED_ALL_COMMAND_TOKENS:
                if token not in command:
                    problems.append(f"owner_gate_runner all-gate command missing token: {token}")

        failed_steps = [
            str(step.get("name") or "owner_gate_runner_step")
            for step in steps
            if isinstance(step, dict) and step.get("status") not in {"planned", "passed"}
        ]
        if failed_steps:
            problems.append(f"owner_gate_runner contains failed steps: {', '.join(failed_steps)}")

    return ReceiptCheck(
        "owner_gate_runner",
        "passed" if not problems else "failed",
        details=_owner_gate_runner_summary(payload),
        error="; ".join(problems) if problems else None,
    )


def _check_gate_report(name: str, payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck(name, "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    checks = payload.get("checks")
    problems: list[str] = []
    if status != "passed":
        problems.append(f"expected passed, got {status}")
    optional_skipped = OPTIONAL_SKIPPED_CHECKS_BY_GATE.get(name, set())
    if not isinstance(checks, list) or not checks:
        problems.append(f"{name}.checks is missing or empty")
    elif any(
        not isinstance(check, dict)
        or (
            check.get("status") != "passed"
            and not (
                str(check.get("name") or "") in optional_skipped
                and check.get("status") == "skipped"
            )
        )
        for check in checks
    ):
        failed = [
            str(check.get("name") or name)
            for check in checks
            if not isinstance(check, dict)
            or (
                check.get("status") != "passed"
                and not (
                    str(check.get("name") or "") in optional_skipped
                    and check.get("status") == "skipped"
                )
            )
        ]
        problems.append(f"{name} has failed checks: {', '.join(failed)}")
    return ReceiptCheck(
        name,
        "passed" if not problems else "failed",
        details={
            "status": status,
            "check_count": len(checks) if isinstance(checks, list) else 0,
            "checks": _gate_checks_summary(payload),
        },
        error="; ".join(problems) if problems else None,
    )


def _check_owner_handoff_gate(payload: dict[str, Any] | None, error: str | None) -> ReceiptCheck:
    if error:
        return ReceiptCheck("owner_handoff_gate", "failed", error=error)
    assert payload is not None
    status = str(payload.get("status") or "")
    checks = payload.get("checks")
    checks_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(checks, list):
        checks_by_name = {
            str(check.get("name") or ""): check
            for check in checks
            if isinstance(check, dict) and check.get("name")
        }
    problems: list[str] = []
    if status != "passed":
        problems.append(f"expected passed, got {status}")
    if not isinstance(checks, list) or not checks:
        problems.append("owner_handoff_gate.checks is missing or empty")
    missing = sorted(REQUIRED_OWNER_HANDOFF_CHECKS.difference(checks_by_name))
    if missing:
        problems.append(f"missing required owner_handoff_gate checks: {', '.join(missing)}")
    failed = sorted(
        name
        for name, check in checks_by_name.items()
        if name in REQUIRED_OWNER_HANDOFF_CHECKS and check.get("status") != "passed"
    )
    if failed:
        problems.append(f"owner_handoff_gate has failed checks: {', '.join(failed)}")
    for check_name in sorted(OWNER_HANDOFF_PRIVACY_CHECKS):
        check = checks_by_name.get(check_name)
        if check is None:
            continue
        details = check.get("details")
        if not isinstance(details, dict):
            problems.append(f"{check_name}.details must be a JSON object")
            continue
        for key, label in (
            ("secret_findings", "secret-like findings"),
            ("local_path_findings", "local user/runtime path findings"),
        ):
            findings = details.get(key)
            if not isinstance(findings, list):
                problems.append(f"{check_name}.details.{key} must be a list")
            elif findings:
                problems.append(f"{check_name} reported {label}")
    return ReceiptCheck(
        "owner_handoff_gate",
        "passed" if not problems else "failed",
        details={
            "status": status,
            "check_count": len(checks) if isinstance(checks, list) else 0,
            "checks": _gate_checks_summary(payload),
        },
        error="; ".join(problems) if problems else None,
    )


def _gate_checks_summary(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return []
    summaries: list[dict[str, Any]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        details = check.get("details") if isinstance(check.get("details"), dict) else {}
        secret_findings = details.get("secret_findings")
        local_path_findings = details.get("local_path_findings")
        summary = {
            "name": check.get("name"),
            "status": check.get("status"),
            "error": check.get("error"),
        }
        if isinstance(secret_findings, list):
            summary["secret_finding_count"] = len(secret_findings)
        if isinstance(local_path_findings, list):
            summary["local_path_finding_count"] = len(local_path_findings)
        summaries.append(summary)
    return summaries


def _artifact_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {
        "path": payload.get("artifact_path"),
        "sha256": payload.get("artifact_sha256"),
        "size_bytes": payload.get("artifact_size_bytes"),
        "file_count": payload.get("file_count"),
        "security_scan": _artifact_security_summary(payload),
    }


def _final_gate_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    decision = payload.get("release_decision") if isinstance(payload.get("release_decision"), dict) else {}
    return {
        "status": payload.get("status"),
        "rc_candidate": payload.get("rc_candidate"),
        "full_parity_claimed": payload.get("full_parity_claimed"),
        "can_stage_candidate_files": decision.get("can_stage_candidate_files"),
        "can_tag_rc_now": decision.get("can_tag_rc_now"),
        "reason": decision.get("reason"),
        "bootstrap_allowed": any(
            isinstance(check, dict)
            and check.get("name") == "final_gate"
            and isinstance(check.get("details"), dict)
            and check["details"].get("bootstrap_allowed") is True
            for check in payload.get("checks", [])
        ),
    }


def _source_bundle_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {
        "status": payload.get("status"),
        "manifest_path": payload.get("manifest_path"),
        "output_path": payload.get("output_path"),
        "file_count": payload.get("file_count"),
        "total_bytes": payload.get("total_bytes"),
        "errors": payload.get("errors", []),
    }


def _staging_plan_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {
        "status": payload.get("status"),
        "manifest_path": payload.get("manifest_path"),
        "manifest_sha256": payload.get("manifest_sha256"),
        "file_count": payload.get("file_count"),
        "command_count": payload.get("command_count"),
        "missing_files": payload.get("missing_files", []),
        "excluded_files": payload.get("excluded_files", []),
    }


def _staging_commands(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    commands = payload.get("commands")
    if not isinstance(commands, list):
        return []
    command_strings: list[str] = []
    for command in commands:
        if isinstance(command, dict) and isinstance(command.get("command"), str):
            command_strings.append(str(command["command"]))
    return command_strings


def _is_broad_staging_command(command: str) -> bool:
    normalized = " ".join(command.strip().split())
    return (
        normalized == "git add ."
        or normalized.startswith("git add . ")
        or normalized == "git add -A"
        or normalized.startswith("git add -A ")
        or normalized == "git add --all"
        or normalized.startswith("git add --all ")
    )


def _approval_request_summary(
    *,
    artifact: dict[str, Any],
    final_gate: dict[str, Any],
    staging_payload: dict[str, Any] | None,
    owner_gates: list[dict[str, Any]],
    receipt_path: Path,
    sha256_sidecar: str | None,
) -> dict[str, Any]:
    staging_commands = _staging_commands(staging_payload)
    remaining_risks = [
        {
            "name": gate.get("name"),
            "status": gate.get("status"),
            "missing": gate.get("missing", []),
        }
        for gate in owner_gates
        if gate.get("status") not in {"passed", "verified"}
    ]
    return {
        "approval_required_before_staging": True,
        "final_gate_status": final_gate.get("status"),
        "can_stage_candidate_files": final_gate.get("can_stage_candidate_files"),
        "can_tag_rc_now": final_gate.get("can_tag_rc_now"),
        "full_parity_claimed": final_gate.get("full_parity_claimed"),
        "artifact_path": artifact.get("path"),
        "artifact_sha256": artifact.get("sha256"),
        "artifact_file_count": artifact.get("file_count"),
        "receipt_path": str(receipt_path),
        "sha256_sidecar": sha256_sidecar,
        "remaining_risks": remaining_risks,
        "exact_staging_commands": staging_commands,
        "no_broad_staging_command": not any(_is_broad_staging_command(command) for command in staging_commands),
    }


def _owner_gates(final_payload: dict[str, Any] | None, owner_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    source = final_payload.get("owner_gates", []) if final_payload else []
    if not source and owner_payload:
        source = owner_payload.get("gates", [])
    gates: list[dict[str, Any]] = []
    for gate in source:
        if not isinstance(gate, dict):
            continue
        gates.append(
            {
                "name": gate.get("name"),
                "status": gate.get("status"),
                "missing": gate.get("missing", []),
            }
        )
    return gates


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _env_groups(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    groups: list[list[str]] = []
    for group in value:
        if not isinstance(group, list):
            continue
        names = [str(item) for item in group if str(item).strip()]
        if names:
            groups.append(names)
    return groups


def _is_env_group_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return all(
        isinstance(group, list)
        and all(isinstance(item, str) and item.strip() for item in group)
        for group in value
    )


def _owner_gate_next_actions(
    owner_payload: dict[str, Any] | None,
    owner_checklist_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    source = owner_checklist_payload.get("gates", []) if owner_checklist_payload else []
    if not source and owner_payload:
        source = owner_payload.get("gates", [])

    actions: list[dict[str, Any]] = []
    for gate in source:
        if not isinstance(gate, dict):
            continue
        actions.append(
            {
                "name": str(gate.get("name") or "owner_gate"),
                "status": str(gate.get("status") or "unknown"),
                "complete": gate.get("complete") is True or gate.get("status") == "verified",
                "required_env_groups": _env_groups(gate.get("required_env_groups")),
                "configured_env": _string_list(gate.get("configured_env")),
                "missing": _string_list(gate.get("missing")),
                "command": str(gate.get("command") or ""),
                "evidence": _string_list(gate.get("evidence")),
                "completion_criteria": _string_list(gate.get("completion_criteria")),
            }
        )
    return actions


def _owner_gate_evidence_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    gates = payload.get("gates")
    return {
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "external_smoke_report": payload.get("external_smoke_report"),
        "source_bundle_report": payload.get("source_bundle_report"),
        "evidence_freshness": payload.get("evidence_freshness", {}),
        "gate_count": len(gates) if isinstance(gates, list) else 0,
    }


def _owner_env_template_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    entries = payload.get("entries")
    names = [
        str(entry.get("name"))
        for entry in entries
        if isinstance(entries, list) and isinstance(entry, dict) and entry.get("name")
    ]
    return {
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "entry_count": len(entries) if isinstance(entries, list) else 0,
        "variable_names": names,
        "env_groups": _env_groups(payload.get("env_groups")),
        "errors": payload.get("errors", []),
    }


def _owner_gate_checklist_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    gates = payload.get("gates")
    complete = [
        gate
        for gate in gates
        if isinstance(gates, list) and isinstance(gate, dict) and gate.get("complete") is True
    ]
    return {
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "gate_count": len(gates) if isinstance(gates, list) else 0,
        "complete_count": len(complete),
        "next_commands": payload.get("next_commands", []),
        "errors": payload.get("errors", []),
    }


def _owner_gate_runner_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    steps = payload.get("steps")
    step_summaries: list[dict[str, Any]] = []
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            command = step.get("command")
            step_summaries.append(
                {
                    "name": step.get("name"),
                    "status": step.get("status"),
                    "returncode": step.get("returncode"),
                    "command": command if isinstance(command, list) else [],
                    "error": step.get("error"),
                }
            )
    return {
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "selected_gate": payload.get("selected_gate"),
        "dry_run": payload.get("dry_run"),
        "env_file": payload.get("env_file"),
        "loaded_env_names": payload.get("loaded_env_names", []),
        "owner_gate_env_names": payload.get("owner_gate_env_names", []),
        "missing_env_groups": _env_groups(payload.get("missing_env_groups")),
        "step_count": len(steps) if isinstance(steps, list) else 0,
        "steps": step_summaries,
        "next_commands": payload.get("next_commands", []),
    }


def _gate_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "checks": _gate_checks_summary(payload),
        "next_commands": payload.get("next_commands", []),
    }


def _write_sha256_sidecar(artifact: dict[str, Any]) -> str | None:
    path = artifact.get("path")
    sha256 = artifact.get("sha256")
    if not path or not sha256:
        return None
    sidecar = Path(str(path) + ".sha256")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(f"{sha256}  {Path(str(path)).name}\n", encoding="utf-8")
    return str(sidecar)


def run_release_receipt(
    *,
    artifact_integrity_report: Path = DEFAULT_ARTIFACT_INTEGRITY,
    final_gate_report: Path = DEFAULT_FINAL_GATE,
    release_diff_review_gate_report: Path = DEFAULT_RELEASE_DIFF_REVIEW_GATE,
    deployment_docs_gate_report: Path = DEFAULT_DEPLOYMENT_DOCS_GATE,
    source_bundle_report: Path = DEFAULT_SOURCE_BUNDLE,
    staging_plan_report: Path = DEFAULT_STAGING_PLAN,
    owner_gate_plan_report: Path = DEFAULT_OWNER_GATE_PLAN,
    owner_gate_runner_report: Path = DEFAULT_OWNER_GATE_RUNNER,
    owner_handoff_gate_report: Path = DEFAULT_OWNER_HANDOFF_GATE,
    owner_env_template_report: Path = DEFAULT_OWNER_ENV_TEMPLATE,
    owner_gate_checklist_report: Path = DEFAULT_OWNER_GATE_CHECKLIST,
    install_release_gate_report: Path = DEFAULT_INSTALL_RELEASE_GATE,
    single_user_local_gate_report: Path = DEFAULT_SINGLE_USER_LOCAL_GATE,
    supply_chain_gate_report: Path = DEFAULT_SUPPLY_CHAIN_GATE,
    secrets_gate_report: Path = DEFAULT_SECRETS_GATE,
    write_sha256: bool = True,
    receipt_path: Path = DEFAULT_OUTPUT,
) -> ReleaseReceipt:
    artifact_payload, artifact_error = _read_json(artifact_integrity_report)
    final_payload, final_error = _read_json(final_gate_report)
    diff_review_payload, diff_review_error = _read_json(release_diff_review_gate_report)
    deployment_docs_payload, deployment_docs_error = _read_json(deployment_docs_gate_report)
    source_payload, source_error = _read_json(source_bundle_report)
    staging_payload, staging_error = _read_json(staging_plan_report)
    owner_payload, owner_error = _read_json(owner_gate_plan_report)
    owner_runner_payload, owner_runner_error = _read_json(owner_gate_runner_report)
    owner_handoff_payload, owner_handoff_error = _read_json(owner_handoff_gate_report)
    owner_env_payload, owner_env_error = _read_json(owner_env_template_report)
    owner_checklist_payload, owner_checklist_error = _read_json(owner_gate_checklist_report)
    install_payload, install_error = _read_json(install_release_gate_report)
    single_user_payload, single_user_error = _read_json(single_user_local_gate_report)
    supply_payload, supply_error = _read_json(supply_chain_gate_report)
    secrets_payload, secrets_error = _read_json(secrets_gate_report)

    checks = [
        _check_report("artifact_integrity_gate", artifact_payload, artifact_error, {"passed"}),
        _check_artifact_security_scan(artifact_payload, artifact_error),
        _check_final_gate_report(final_payload, final_error),
        _check_gate_report("release_diff_review_gate", diff_review_payload, diff_review_error),
        _check_gate_report("deployment_docs_gate", deployment_docs_payload, deployment_docs_error),
        _check_report("source_bundle", source_payload, source_error, {"created"}),
        _check_report("staging_plan", staging_payload, staging_error, {"planned"}),
        _check_report("owner_gate_plan", owner_payload, owner_error, {"verified", "ready_to_run", "action_required"}),
        _check_owner_gate_plan_consistency(owner_payload, owner_error),
        _check_owner_gate_runner(owner_runner_payload, owner_runner_error),
        _check_owner_handoff_gate(owner_handoff_payload, owner_handoff_error),
        _check_owner_env_template(owner_env_payload, owner_env_error),
        _check_owner_gate_checklist(owner_checklist_payload, owner_checklist_error),
        _check_gate_report("install_release_gate", install_payload, install_error),
        _check_gate_report("single_user_local_gate", single_user_payload, single_user_error),
        _check_gate_report("supply_chain_gate", supply_payload, supply_error),
        _check_gate_report("secrets_gate", secrets_payload, secrets_error),
        _check_release_artifact_consistency(artifact_payload, source_payload),
    ]
    artifact = _artifact_summary(artifact_payload)
    sha_sidecar = _write_sha256_sidecar(artifact) if write_sha256 else None
    final_gate = _final_gate_summary(final_payload)
    owner_gates = _owner_gates(final_payload, owner_payload)
    status = "created" if all(check.status == "passed" for check in checks) else "failed"
    return ReleaseReceipt(
        status=status,
        generated_at=_utc_now(),
        artifact=artifact,
        final_gate=final_gate,
        source_bundle=_source_bundle_summary(source_payload),
        staging_plan=_staging_plan_summary(staging_payload),
        owner_gates=owner_gates,
        owner_gate_next_actions=_owner_gate_next_actions(owner_payload, owner_checklist_payload),
        owner_gate_evidence=_owner_gate_evidence_summary(owner_payload),
        owner_gate_runner=_owner_gate_runner_summary(owner_runner_payload),
        owner_handoff_gate=_gate_summary(owner_handoff_payload),
        owner_env_template=_owner_env_template_summary(owner_env_payload),
        owner_gate_checklist=_owner_gate_checklist_summary(owner_checklist_payload),
        release_diff_review_gate=_gate_summary(diff_review_payload),
        deployment_docs_gate=_gate_summary(deployment_docs_payload),
        install_release_gate=_gate_summary(install_payload),
        single_user_local_gate=_gate_summary(single_user_payload),
        supply_chain_gate=_gate_summary(supply_payload),
        secrets_gate=_gate_summary(secrets_payload),
        checks=checks,
        sidecars={"sha256": sha_sidecar},
        approval_request=_approval_request_summary(
            artifact=artifact,
            final_gate=final_gate,
            staging_payload=staging_payload,
            owner_gates=owner_gates,
            receipt_path=receipt_path,
            sha256_sidecar=sha_sidecar,
        ),
        next_commands=[
            "Archive the zip, .sha256 sidecar, receipt JSON, and .xagent_runtime/reports/*.json outside source control.",
            "Use rc-owner-env-template.* and rc-owner-gate-checklist.md for release-owner external gate execution.",
            "Complete owner gates before RC tagging: provider, Feishu, GitHub dry-run/execute preflight, and hosted GitHub Actions.",
            "Stage only paths from docs/RC_STAGING_MANIFEST.md after owner review; never use git add .",
        ],
    )


def write_report(report: ReleaseReceipt, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the X-Agent commercial RC release receipt")
    parser.add_argument("--artifact-integrity-report", type=Path, default=DEFAULT_ARTIFACT_INTEGRITY)
    parser.add_argument("--final-gate-report", type=Path, default=DEFAULT_FINAL_GATE)
    parser.add_argument("--release-diff-review-gate-report", type=Path, default=DEFAULT_RELEASE_DIFF_REVIEW_GATE)
    parser.add_argument("--deployment-docs-gate-report", type=Path, default=DEFAULT_DEPLOYMENT_DOCS_GATE)
    parser.add_argument("--source-bundle-report", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--staging-plan-report", type=Path, default=DEFAULT_STAGING_PLAN)
    parser.add_argument("--owner-gate-plan-report", type=Path, default=DEFAULT_OWNER_GATE_PLAN)
    parser.add_argument("--owner-gate-runner-report", type=Path, default=DEFAULT_OWNER_GATE_RUNNER)
    parser.add_argument("--owner-handoff-gate-report", type=Path, default=DEFAULT_OWNER_HANDOFF_GATE)
    parser.add_argument("--owner-env-template-report", type=Path, default=DEFAULT_OWNER_ENV_TEMPLATE)
    parser.add_argument("--owner-gate-checklist-report", type=Path, default=DEFAULT_OWNER_GATE_CHECKLIST)
    parser.add_argument("--install-release-gate-report", type=Path, default=DEFAULT_INSTALL_RELEASE_GATE)
    parser.add_argument("--single-user-local-gate-report", type=Path, default=DEFAULT_SINGLE_USER_LOCAL_GATE)
    parser.add_argument("--supply-chain-gate-report", type=Path, default=DEFAULT_SUPPLY_CHAIN_GATE)
    parser.add_argument("--secrets-gate-report", type=Path, default=DEFAULT_SECRETS_GATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-sha256-sidecar", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = run_release_receipt(
        artifact_integrity_report=args.artifact_integrity_report,
        final_gate_report=args.final_gate_report,
        release_diff_review_gate_report=args.release_diff_review_gate_report,
        deployment_docs_gate_report=args.deployment_docs_gate_report,
        source_bundle_report=args.source_bundle_report,
        staging_plan_report=args.staging_plan_report,
        owner_gate_plan_report=args.owner_gate_plan_report,
        owner_gate_runner_report=args.owner_gate_runner_report,
        owner_handoff_gate_report=args.owner_handoff_gate_report,
        owner_env_template_report=args.owner_env_template_report,
        owner_gate_checklist_report=args.owner_gate_checklist_report,
        install_release_gate_report=args.install_release_gate_report,
        single_user_local_gate_report=args.single_user_local_gate_report,
        supply_chain_gate_report=args.supply_chain_gate_report,
        secrets_gate_report=args.secrets_gate_report,
        write_sha256=not args.no_sha256_sidecar,
        receipt_path=args.output,
    )
    write_report(receipt, args.output)
    print(f"RC release receipt status: {receipt.status}")
    print(f"Receipt written to {args.output}")
    if receipt.sidecars.get("sha256"):
        print(f"SHA-256 sidecar written to {receipt.sidecars['sha256']}")
    if receipt.artifact.get("sha256"):
        print(f"Artifact sha256: {receipt.artifact['sha256']}")
    for check in receipt.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if receipt.status == "created" else 1


if __name__ == "__main__":
    raise SystemExit(main())
