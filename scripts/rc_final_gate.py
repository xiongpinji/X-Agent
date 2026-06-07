#!/usr/bin/env python3
"""Consolidate commercial RC evidence into one final gate report.

This script does not run the expensive checks itself. It reads the machine
reports produced by the dedicated gates and answers one release question:

Can this branch be treated as a commercial RC candidate from local evidence,
and which owner-controlled external gates still need real resources?
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
SMOKE_DIR = ROOT / ".xagent_runtime" / "smoke"
DEFAULT_OUTPUT = REPORT_DIR / "rc-final-gate.json"
MAX_GENERATED_AT_FUTURE_SKEW = timedelta(minutes=5)

DEFAULT_INPUTS = {
    "gap_matrix": REPORT_DIR / "codex-hermes-gap-closure.json",
    "release_audit": REPORT_DIR / "rc-release-audit.json",
    "runtime_smoke": SMOKE_DIR / "rc-runtime-smoke.json",
    "external_smoke": REPORT_DIR / "rc-external-smoke.json",
    "ci_contract": REPORT_DIR / "rc-ci-contract.json",
    "refresh_release_chain": REPORT_DIR / "rc-refresh-release-chain.json",
    "release_diff_review_gate": REPORT_DIR / "rc-release-diff-review-gate.json",
    "deployment_docs_gate": REPORT_DIR / "rc-deployment-docs-gate.json",
    "owner_gate_plan": REPORT_DIR / "rc-owner-gate-plan.json",
    "owner_gate_runner": REPORT_DIR / "rc-owner-gate-runner.json",
    "owner_env_template": REPORT_DIR / "rc-owner-env-template.json",
    "owner_gate_checklist": REPORT_DIR / "rc-owner-gate-checklist.json",
    "owner_handoff_gate": REPORT_DIR / "rc-owner-handoff-gate.json",
    "install_release_gate": REPORT_DIR / "rc-install-release-gate.json",
    "supply_chain_gate": REPORT_DIR / "rc-supply-chain-gate.json",
    "secrets_gate": REPORT_DIR / "rc-secrets-gate.json",
    "source_bundle": REPORT_DIR / "rc-source-bundle.json",
    "artifact_integrity_gate": REPORT_DIR / "rc-artifact-integrity-gate.json",
    "release_receipt": ROOT / ".xagent_runtime" / "release" / "x-agent-commercial-rc-receipt.json",
    "evidence_pack": REPORT_DIR / "rc-evidence-pack.json",
    "staging_plan": REPORT_DIR / "rc-staging-plan.json",
}

REQUIRED_SECRETS_CHECKS = {
    "required_fields",
    "secret_strength",
    "unique_generated_values",
    "release_audit_secret_scan",
    "artifact_secret_scan",
    "prohibited_secret_artifacts",
}

REQUIRED_INSTALL_RELEASE_CHECKS = {
    "windows_installer_dry_run",
    "posix_installer_dry_run",
    "doctor",
    "source_bundle_report",
    "artifact_integrity_report",
    "staging_plan_report",
    "release_artifact_consistency",
}

REQUIRED_SUPPLY_CHAIN_CHECKS = {
    "python_manifest",
    "python_lockfile",
    "frontend_lockfile",
    "npm_audit",
    "ci_dependency_contract",
    "release_dependency_evidence",
}

REQUIRED_ARTIFACT_INTEGRITY_CHECKS = {
    "source_bundle_report",
    "artifact_file",
    "zip_contents",
    "workspace_contents",
    "zip_security_scan",
}

REQUIRED_EVIDENCE_PACK_CHECKS = {
    "release_receipt",
    "required_files",
    "artifact_consistency",
    "owner_gate_runner_evidence",
    "evidence_pack_freshness",
    "evidence_secret_scan",
    "evidence_local_path_privacy_scan",
}

REQUIRED_RECEIPT_CHECKS = {
    "artifact_security_scan",
    "artifact_integrity_gate",
    "final_gate",
    "release_diff_review_gate",
    "deployment_docs_gate",
    "source_bundle",
    "staging_plan",
    "owner_gate_plan",
    "owner_gate_plan_consistency",
    "owner_gate_runner",
    "owner_handoff_gate",
    "owner_env_template",
    "owner_gate_checklist",
    "install_release_gate",
    "supply_chain_gate",
    "secrets_gate",
    "release_artifact_consistency",
}

REQUIRED_RECEIPT_GATE_SECTIONS = {
    "install_release_gate",
    "release_diff_review_gate",
    "deployment_docs_gate",
    "owner_handoff_gate",
    "supply_chain_gate",
    "secrets_gate",
}

REQUIRED_RECEIPT_OWNER_SECTIONS = {
    "owner_env_template",
    "owner_gate_checklist",
}

REQUIRED_OWNER_GATE_NEXT_ACTION_FIELDS = {
    "command",
    "evidence",
    "completion_criteria",
    "required_env_groups",
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

REQUIRED_OWNER_GATE_RUNNER_REFRESH_STEPS = {
    "refresh:rc_owner_gate_plan",
    "refresh:rc_owner_env_template",
    "refresh:rc_owner_gate_checklist",
    "refresh:rc_owner_handoff_gate",
    "refresh:rc_final_gate",
}
OWNER_GATE_RUNNER_REQUIRED_ENV_FILE = ".xagent_runtime/reports/rc-owner-env-template.env"

EVIDENCE_PACK_FRESHNESS_INPUTS = {
    "release_receipt": "release_receipt",
    "gap_matrix": "gap_matrix",
    "release_audit": "release_audit",
    "runtime_smoke": "runtime_smoke",
    "external_smoke": "external_smoke",
    "ci_contract": "ci_contract",
    "refresh_release_chain": "refresh_release_chain",
    "source_bundle": "source_bundle",
    "artifact_integrity_gate": "artifact_integrity_gate",
    "release_diff_review_gate": "release_diff_review_gate",
    "deployment_docs_gate": "deployment_docs_gate",
    "owner_gate_plan": "owner_gate_plan",
    "owner_gate_runner": "owner_gate_runner",
    "owner_handoff_gate": "owner_handoff_gate",
    "owner_env_template": "owner_env_template",
    "owner_gate_checklist": "owner_gate_checklist",
    "install_release_gate": "install_release_gate",
    "supply_chain_gate": "supply_chain_gate",
    "secrets_gate": "secrets_gate",
    "staging_plan": "staging_plan",
}


@dataclass(frozen=True)
class GateInput:
    name: str
    path: str
    status: str
    ok: bool
    required: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerGate:
    name: str
    status: str
    missing: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinalGateReport:
    status: str
    generated_at: str
    rc_candidate: bool
    full_parity_claimed: bool
    local_gates: list[GateInput]
    owner_gates: list[OwnerGate]
    release_decision: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_report_time(raw_value: Any) -> datetime | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_future_report_time(value: datetime, *, now: datetime | None = None) -> bool:
    reference = now or datetime.now(UTC)
    return value > reference + MAX_GENERATED_AT_FUTURE_SKEW


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "report missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _evidence_pack_zip_integrity(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    output_path = str(payload.get("output_path") or "")
    expected_sha = str(payload.get("pack_sha256") or "")
    problems: list[str] = []
    details: dict[str, Any] = {
        "evidence_pack_output_path": output_path,
        "evidence_pack_expected_sha256": expected_sha,
    }

    if not output_path:
        problems.append("evidence pack output_path is missing")
        return problems, details
    path = Path(output_path)
    if path.suffix.lower() != ".zip":
        problems.append("evidence pack output_path is not a .zip file")
    if not _is_sha256_hex(expected_sha):
        problems.append("evidence pack pack_sha256 is not a 64-character hex digest")
    if not path.is_file():
        problems.append("evidence pack output_path does not exist")
        return problems, details

    actual_sha = _sha256_file(path)
    details["evidence_pack_actual_sha256"] = actual_sha
    if _is_sha256_hex(expected_sha) and actual_sha != expected_sha:
        problems.append("evidence pack SHA-256 does not match current file")
    return problems, details


def _artifact_zip_integrity(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    artifact_path = str(payload.get("artifact_path") or "")
    expected_sha = str(payload.get("artifact_sha256") or "")
    problems: list[str] = []
    details: dict[str, Any] = {
        "artifact_filename": Path(artifact_path).name if artifact_path else "",
        "artifact_expected_sha256": expected_sha,
    }

    if not artifact_path:
        problems.append("artifact integrity artifact_path is missing")
        return problems, details
    path = Path(artifact_path)
    if path.suffix.lower() != ".zip":
        problems.append("artifact integrity artifact_path is not a .zip file")
    if not _is_sha256_hex(expected_sha):
        problems.append("artifact integrity artifact_sha256 is not a 64-character hex digest")
    if not path.is_file():
        problems.append("artifact integrity artifact_path does not exist")
        return problems, details

    actual_sha = _sha256_file(path)
    details["artifact_actual_sha256"] = actual_sha
    if _is_sha256_hex(expected_sha) and actual_sha != expected_sha:
        problems.append("artifact integrity SHA-256 does not match current file")
    return problems, details


def _status(payload: dict[str, Any] | None, *keys: str) -> str:
    if payload is None:
        return "missing"
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "")


def _gate_from_report(name: str, path: Path, expected_status: set[str], *, status_keys: tuple[str, ...] = ("status",)) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, *status_keys)
    problems: list[str] = []
    if error:
        problems.append(error)
    if payload is not None:
        generated_at = payload.get("generated_at")
        report_time = _parse_report_time(generated_at)
        if report_time is not None and _is_future_report_time(report_time):
            problems.append(f"{name} generated_at is in the future")
    return GateInput(
        name=name,
        path=str(path),
        status=status,
        ok=not problems and status in expected_status,
        error="; ".join(problems) if problems else None,
        details=_summary_details(name, payload),
    )


def _check_map(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name") or ""): check
        for check in checks
        if isinstance(check, dict) and check.get("name")
    }


def _checked_report_gate(
    name: str,
    path: Path,
    *,
    expected_status: set[str],
    required_checks: set[str],
) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, "status")
    details = _summary_details(name, payload)
    problems: list[str] = []

    if error:
        problems.append(error)
    if status not in expected_status:
        problems.append(f"expected {sorted(expected_status)}, got {status}")
    if payload is not None:
        checks = payload.get("checks")
        checks_by_name = _check_map(payload)
        if not isinstance(checks, list):
            problems.append(f"{name}.checks is missing or not a list")
        missing = sorted(required_checks.difference(checks_by_name))
        if missing:
            problems.append(f"missing required {name} checks: {', '.join(missing)}")
        failed = sorted(
            check_name
            for check_name, check in checks_by_name.items()
            if check_name in required_checks and check.get("status") != "passed"
        )
        if failed:
            problems.append(f"required {name} checks failed: {', '.join(failed)}")
        unexpected_failed = sorted(
            check_name
            for check_name, check in checks_by_name.items()
            if check_name not in required_checks and check.get("status") != "passed"
        )
        if unexpected_failed:
            problems.append(f"non-required {name} checks failed: {', '.join(unexpected_failed)}")

    return GateInput(
        name=name,
        path=str(path),
        status="passed" if not problems else "failed",
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _artifact_integrity_gate(path: Path) -> GateInput:
    gate = _checked_report_gate(
        "artifact_integrity_gate",
        path,
        expected_status={"passed"},
        required_checks=REQUIRED_ARTIFACT_INTEGRITY_CHECKS,
    )
    if not gate.ok:
        return gate

    payload, _ = _read_json(path)
    if payload is None:
        return gate
    artifact_problems, artifact_details = _artifact_zip_integrity(payload)
    if artifact_problems:
        details = dict(gate.details)
        details.update(artifact_details)
        return GateInput(
            name="artifact_integrity_gate",
            path=str(path),
            status="failed",
            ok=False,
            details=details,
            error="; ".join(artifact_problems),
        )
    details = dict(gate.details)
    details.update(artifact_details)
    return GateInput(
        name=gate.name,
        path=gate.path,
        status=gate.status,
        ok=gate.ok,
        required=gate.required,
        details=details,
        error=gate.error,
    )


def _deployment_docs_gate(path: Path, *, allow_missing: bool) -> GateInput:
    gate = _gate_from_report("deployment_docs_gate", path, {"passed"})
    if gate.ok or not allow_missing:
        return gate

    payload, _ = _read_json(path)
    if payload is None or not _deployment_docs_bootstrap_refresh_only(payload):
        return gate

    details = dict(gate.details)
    details["bootstrap_allowed"] = True
    details["bootstrap_reason"] = "deployment docs are refreshed from a bootstrap final gate snapshot"
    return GateInput(
        name="deployment_docs_gate",
        path=str(path),
        status="bootstrap_allowed",
        ok=True,
        details=details,
        error="deployment docs state-only refresh required during bootstrap",
    )


def _deployment_docs_bootstrap_refresh_only(payload: dict[str, Any]) -> bool:
    if payload.get("status") != "failed":
        return False
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        return False
    failed = {
        str(check.get("name") or "")
        for check in checks
        if isinstance(check, dict) and check.get("status") != "passed"
    }
    return bool(failed) and failed.issubset({"release_state_docs", "overclaim_boundary_docs"})


def _refresh_release_chain_gate(path: Path, *, allow_missing: bool) -> GateInput:
    expected_status = {"passed", "running"} if allow_missing else {"passed"}
    gate = _gate_from_report("refresh_release_chain", path, expected_status)
    payload, _ = _read_json(path)
    details = dict(gate.details)
    problems: list[str] = []
    if gate.error:
        problems.append(gate.error)
    if payload is None:
        problems.append("refresh_release_chain report is missing or invalid")
    else:
        status = str(payload.get("status") or "")
        if status not in expected_status:
            problems.append(f"expected {sorted(expected_status)}, got {status}")
        if payload.get("dry_run") is True:
            problems.append("refresh_release_chain dry_run must be false for final gate")
        steps = payload.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append("refresh_release_chain.steps is missing or empty")
        elif not allow_missing:
            step_by_name = {
                str(step.get("name") or ""): step
                for step in steps
                if isinstance(step, dict)
            }
            final_step = step_by_name.get("final_gate_final")
            if not isinstance(final_step, dict) or final_step.get("status") != "passed":
                problems.append("refresh_release_chain final_gate_final step must be passed")
            external_step = step_by_name.get("external_smoke")
            command = external_step.get("command") if isinstance(external_step, dict) else []
            if payload.get("owner_verified") is True and not isinstance(command, list):
                problems.append("refresh_release_chain external_smoke command is missing")
            elif payload.get("owner_verified") is True:
                for token in (
                    "--check",
                    "provider",
                    "feishu_webhook_contract",
                    "github_issue_to_pr_dry_run",
                    "github_issue_to_pr_execute_preflight",
                    "hosted_github_actions_run",
                    "--require-configured",
                    "--github-execute-preflight",
                    "--github-actions-preflight",
                ):
                    if token not in command:
                        problems.append(f"refresh_release_chain external_smoke command missing token: {token}")

    return GateInput(
        name="refresh_release_chain",
        path=str(path),
        status=gate.status,
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _evidence_pack_gate(paths: dict[str, Path], *, allow_missing: bool) -> GateInput:
    path = paths["evidence_pack"]
    gate = _checked_report_gate(
        "evidence_pack",
        path,
        expected_status={"created"},
        required_checks=REQUIRED_EVIDENCE_PACK_CHECKS,
    )
    if allow_missing and "report missing" in str(gate.error or ""):
        details = dict(gate.details)
        details["bootstrap_allowed"] = True
        details["bootstrap_reason"] = "evidence pack is generated after the first refreshed final gate snapshot"
        return GateInput(
            name="evidence_pack",
            path=str(path),
            status="bootstrap_allowed",
            ok=True,
            details=details,
            error="evidence pack missing during bootstrap; rerun final gate after evidence pack refresh",
        )

    payload, _ = _read_json(path)
    if payload is None:
        return gate
    if allow_missing and not gate.ok and _evidence_pack_bootstrap_refresh_only(payload):
        details = dict(gate.details)
        details["bootstrap_allowed"] = True
        details["bootstrap_reason"] = "previous evidence pack must be refreshed during this release chain"
        return GateInput(
            name="evidence_pack",
            path=str(path),
            status="bootstrap_allowed",
            ok=True,
            details=details,
            error="evidence pack refresh required during bootstrap; rerun final gate after evidence pack refresh",
        )
    if not gate.ok:
        return gate
    zip_problems, zip_details = _evidence_pack_zip_integrity(payload)
    if zip_problems:
        details = dict(gate.details)
        details.update(zip_details)
        return GateInput(
            name="evidence_pack",
            path=str(path),
            status="failed",
            ok=False,
            details=details,
            error="; ".join(zip_problems),
        )

    pack_time = _parse_report_time(payload.get("generated_at"))
    now = datetime.now(UTC)
    problems: list[str] = []
    stale_reports: list[dict[str, Any]] = []
    invalid_reports: list[dict[str, Any]] = []
    if pack_time is None:
        problems.append("evidence pack generated_at is missing or invalid")
    elif _is_future_report_time(pack_time, now=now):
        problems.append("evidence pack generated_at is in the future")
    for label, key in sorted(EVIDENCE_PACK_FRESHNESS_INPUTS.items()):
        report_payload, report_error = _read_json(paths[key])
        if report_error:
            if key == "release_receipt":
                continue
            invalid_reports.append({"name": label, "error": report_error})
            continue
        assert report_payload is not None
        report_time = _parse_report_time(report_payload.get("generated_at"))
        if report_time is None:
            if key == "release_receipt":
                continue
            invalid_reports.append({"name": label, "error": "generated_at is missing or invalid"})
            continue
        if _is_future_report_time(report_time, now=now):
            invalid_reports.append({"name": label, "error": "generated_at is in the future"})
            continue
        if (
            pack_time is not None
            and pack_time < report_time
            and not _is_refresh_chain_fixed_point_evidence(label, report_payload)
        ):
            stale_reports.append(
                {
                    "name": label,
                    "report_generated_at": report_payload.get("generated_at"),
                    "evidence_pack_generated_at": payload.get("generated_at"),
                }
            )
    if invalid_reports:
        problems.append("evidence pack freshness inputs are missing or invalid")
    if stale_reports:
        problems.append("evidence pack is older than required release reports")
    if problems:
        details = dict(gate.details)
        details.update(
            {
                "evidence_pack_generated_at": payload.get("generated_at"),
                "stale_reports": stale_reports,
                "invalid_freshness_inputs": invalid_reports,
            }
        )
        if allow_missing and not invalid_reports and stale_reports:
            details["bootstrap_allowed"] = True
            details["bootstrap_reason"] = "evidence pack is refreshed after the bootstrap final gate snapshot"
            return GateInput(
                name="evidence_pack",
                path=str(path),
                status="bootstrap_allowed",
                ok=True,
                details=details,
                error="evidence pack stale during bootstrap; rerun final gate after evidence pack refresh",
            )
        return GateInput(
            name="evidence_pack",
            path=str(path),
            status="failed",
            ok=False,
            details=details,
            error="; ".join(problems),
        )
    return gate


def _is_refresh_chain_fixed_point_evidence(label: str, payload: dict[str, Any]) -> bool:
    if label != "refresh_release_chain":
        return False
    if payload.get("status") != "passed":
        return False
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return False
    step_by_name = {
        str(step.get("name") or ""): step
        for step in steps
        if isinstance(step, dict)
    }
    required_passed = ("evidence_pack_after_receipt", "final_gate_final")
    return all(
        isinstance(step_by_name.get(name), dict) and step_by_name[name].get("status") == "passed"
        for name in required_passed
    )


def _evidence_pack_bootstrap_refresh_only(payload: dict[str, Any]) -> bool:
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        return False
    failed = [
        str(check.get("name") or "")
        for check in checks
        if isinstance(check, dict) and check.get("status") != "passed"
    ]
    return failed in (["evidence_pack_freshness"], ["release_receipt"])


def _owner_handoff_gate(path: Path) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, "status")
    details = _summary_details("owner_handoff_gate", payload)
    problems: list[str] = []

    if error:
        problems.append(error)
    if status != "passed":
        problems.append(f"expected ['passed'], got {status}")
    if payload is not None:
        checks_by_name = _check_map(payload)
        checks = payload.get("checks")
        if not isinstance(checks, list):
            problems.append("owner_handoff_gate.checks is missing or not a list")
        missing = sorted(REQUIRED_OWNER_HANDOFF_CHECKS.difference(checks_by_name))
        if missing:
            problems.append(f"missing required owner_handoff_gate checks: {', '.join(missing)}")
        failed = sorted(
            name
            for name, check in checks_by_name.items()
            if name in REQUIRED_OWNER_HANDOFF_CHECKS and check.get("status") != "passed"
        )
        if failed:
            problems.append(f"required owner_handoff_gate checks failed: {', '.join(failed)}")
        for check_name in sorted(OWNER_HANDOFF_PRIVACY_CHECKS):
            check = checks_by_name.get(check_name)
            if check is None:
                continue
            check_details = check.get("details")
            if not isinstance(check_details, dict):
                problems.append(f"{check_name}.details must be a JSON object")
                continue
            for key, label in (
                ("secret_findings", "secret-like findings"),
                ("local_path_findings", "local user/runtime path findings"),
            ):
                findings = check_details.get(key)
                if not isinstance(findings, list):
                    problems.append(f"{check_name}.details.{key} must be a list")
                elif findings:
                    problems.append(f"{check_name} reported {label}")

    return GateInput(
        name="owner_handoff_gate",
        path=str(path),
        status="passed" if not problems else "failed",
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _owner_gate_runner_gate(path: Path) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, "status")
    details = _summary_details("owner_gate_runner", payload)
    problems: list[str] = []

    if error:
        problems.append(error)
    if status not in {"planned", "passed"}:
        problems.append(f"expected ['passed', 'planned'], got {status}")
    if payload is not None:
        if payload.get("selected_gate") != "all":
            problems.append("owner gate runner must be generated for --gate all")
        if payload.get("dry_run") is not True:
            problems.append("owner gate runner local final gate input must be a dry-run report")
        if payload.get("env_file") != OWNER_GATE_RUNNER_REQUIRED_ENV_FILE:
            problems.append(f"owner gate runner env_file must be {OWNER_GATE_RUNNER_REQUIRED_ENV_FILE}")
        for key in ("loaded_env_names", "owner_gate_env_names"):
            value = payload.get(key)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                problems.append(f"owner gate runner {key} must be a list of env variable names")
        if not _is_env_group_list(payload.get("missing_env_groups")):
            problems.append("owner gate runner missing_env_groups must be a list of env variable name groups")
        steps = payload.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append("owner gate runner steps are missing")
        else:
            step_names = {
                str(step.get("name") or "")
                for step in steps
                if isinstance(step, dict)
            }
            missing_refresh = sorted(REQUIRED_OWNER_GATE_RUNNER_REFRESH_STEPS.difference(step_names))
            if missing_refresh:
                problems.append(f"owner gate runner missing refresh steps: {', '.join(missing_refresh)}")
            first_step = steps[0] if isinstance(steps[0], dict) else {}
            command = first_step.get("command") if isinstance(first_step, dict) else []
            if not isinstance(command, list):
                problems.append("owner gate runner first command is missing")
            else:
                for token in (
                    "scripts/rc_external_smoke.py",
                    "--github-execute-preflight",
                    "--github-actions-preflight",
                    "--require-configured",
                ):
                    if token not in command:
                        problems.append(f"owner gate runner all-gate command missing token: {token}")
            failed_steps = [
                str(step.get("name") or "owner_gate_runner_step")
                for step in steps
                if isinstance(step, dict) and step.get("status") not in {"planned", "passed"}
            ]
            if failed_steps:
                problems.append(f"owner gate runner contains failed steps: {', '.join(failed_steps)}")

    return GateInput(
        name="owner_gate_runner",
        path=str(path),
        status="passed" if not problems else "failed",
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _secrets_gate(path: Path) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, "status")
    details = _summary_details("secrets_gate", payload)
    problems: list[str] = []

    if error:
        problems.append(error)
    if status != "passed":
        problems.append(f"expected ['passed'], got {status}")
    if payload is not None:
        checks_by_name = _check_map(payload)
        if not isinstance(payload.get("checks"), list):
            problems.append("secrets_gate.checks is missing or not a list")
        else:
            missing = sorted(REQUIRED_SECRETS_CHECKS.difference(checks_by_name))
            if missing:
                problems.append(f"missing required secrets checks: {', '.join(missing)}")
            failed = sorted(
                name
                for name, check in checks_by_name.items()
                if name in REQUIRED_SECRETS_CHECKS and check.get("status") != "passed"
            )
            if failed:
                problems.append(f"required secrets checks failed: {', '.join(failed)}")
            unexpected_failed = sorted(
                name
                for name, check in checks_by_name.items()
                if name not in REQUIRED_SECRETS_CHECKS and check.get("status") != "passed"
            )
            if unexpected_failed:
                problems.append(f"non-required secrets checks failed: {', '.join(unexpected_failed)}")

        generated_count = payload.get("generated_value_count")
        unique_count = payload.get("unique_value_count")
        required_fields = payload.get("required_fields")
        if not isinstance(required_fields, list) or not required_fields:
            problems.append("secrets_gate.required_fields is missing or empty")
        if not isinstance(generated_count, int) or generated_count <= 0:
            problems.append("secrets_gate.generated_value_count must be a positive integer")
        if not isinstance(unique_count, int) or unique_count <= 0:
            problems.append("secrets_gate.unique_value_count must be a positive integer")
        if isinstance(generated_count, int) and isinstance(unique_count, int) and generated_count != unique_count:
            problems.append("secrets_gate generated values are not unique")
        if isinstance(required_fields, list) and isinstance(generated_count, int) and generated_count != len(required_fields):
            problems.append("secrets_gate.generated_value_count does not match required_fields length")

    return GateInput(
        name="secrets_gate",
        path=str(path),
        status="passed" if not problems else "failed",
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _receipt_owner_handoff_summary_problems(section: dict[str, Any]) -> list[str]:
    checks = section.get("checks")
    if not isinstance(checks, list):
        return []
    checks_by_name = {
        str(check.get("name") or ""): check
        for check in checks
        if isinstance(check, dict) and check.get("name")
    }
    problems: list[str] = []
    missing = sorted(REQUIRED_OWNER_HANDOFF_CHECKS.difference(checks_by_name))
    if missing:
        problems.append(f"receipt owner_handoff_gate missing required checks: {', '.join(missing)}")
    failed = sorted(
        name
        for name, check in checks_by_name.items()
        if name in REQUIRED_OWNER_HANDOFF_CHECKS and check.get("status") != "passed"
    )
    if failed:
        problems.append(f"receipt owner_handoff_gate has failed checks: {', '.join(failed)}")
    for check_name in sorted(OWNER_HANDOFF_PRIVACY_CHECKS):
        check = checks_by_name.get(check_name)
        if check is None:
            continue
        for key in ("secret_finding_count", "local_path_finding_count"):
            if check.get(key) != 0:
                problems.append(f"receipt owner_handoff_gate.{check_name}.{key} must be 0")
    return problems


def _is_env_group_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return all(
        isinstance(group, list)
        and all(isinstance(item, str) and item.strip() for item in group)
        for group in value
    )


def _receipt_owner_gate_runner_summary_problems(section: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if section.get("status") not in {"planned", "passed"}:
        problems.append("receipt owner_gate_runner.status is not planned or passed")
    if section.get("selected_gate") != "all":
        problems.append("receipt owner_gate_runner.selected_gate must be all")
    if section.get("dry_run") is not True:
        problems.append("receipt owner_gate_runner.dry_run must be true")
    if section.get("env_file") != OWNER_GATE_RUNNER_REQUIRED_ENV_FILE:
        problems.append(f"receipt owner_gate_runner.env_file must be {OWNER_GATE_RUNNER_REQUIRED_ENV_FILE}")
    for key in ("loaded_env_names", "owner_gate_env_names"):
        value = section.get(key)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            problems.append(f"receipt owner_gate_runner.{key} must be a list of env variable names")
    if not _is_env_group_list(section.get("missing_env_groups")):
        problems.append("receipt owner_gate_runner.missing_env_groups must be a list of env variable name groups")
    steps = section.get("steps")
    if not isinstance(steps, list) or not steps:
        problems.append("receipt owner_gate_runner.steps is missing or empty")
        return problems

    step_names = {
        str(step.get("name") or "")
        for step in steps
        if isinstance(step, dict)
    }
    missing_refresh = sorted(REQUIRED_OWNER_GATE_RUNNER_REFRESH_STEPS.difference(step_names))
    if missing_refresh:
        problems.append(f"receipt owner_gate_runner missing refresh steps: {', '.join(missing_refresh)}")
    first_step = steps[0] if isinstance(steps[0], dict) else {}
    command = first_step.get("command") if isinstance(first_step, dict) else []
    if not isinstance(command, list):
        problems.append("receipt owner_gate_runner first command is missing")
    else:
        for token in (
            "scripts/rc_external_smoke.py",
            "--github-execute-preflight",
            "--github-actions-preflight",
            "--require-configured",
        ):
            if token not in command:
                problems.append(f"receipt owner_gate_runner all-gate command missing token: {token}")
    failed_steps = [
        str(step.get("name") or "owner_gate_runner_step")
        for step in steps
        if isinstance(step, dict) and step.get("status") not in {"planned", "passed"}
    ]
    if failed_steps:
        problems.append(f"receipt owner_gate_runner contains failed steps: {', '.join(failed_steps)}")
    step_count = section.get("step_count")
    if not isinstance(step_count, int) or step_count != len(steps):
        problems.append("receipt owner_gate_runner.step_count must match steps length")
    return problems


def _receipt_approval_request_problems(section: dict[str, Any], payload: dict[str, Any], path: Path) -> list[str]:
    problems: list[str] = []
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    final_gate = payload.get("final_gate") if isinstance(payload.get("final_gate"), dict) else {}
    if section.get("approval_required_before_staging") is not True:
        problems.append("receipt approval_request.approval_required_before_staging must be true")
    if section.get("final_gate_status") != final_gate.get("status"):
        problems.append("receipt approval_request.final_gate_status must match final_gate.status")
    if section.get("artifact_path") != artifact.get("path"):
        problems.append("receipt approval_request.artifact_path must match artifact.path")
    if section.get("artifact_sha256") != artifact.get("sha256"):
        problems.append("receipt approval_request.artifact_sha256 must match artifact.sha256")
    if section.get("artifact_file_count") != artifact.get("file_count"):
        problems.append("receipt approval_request.artifact_file_count must match artifact.file_count")
    if section.get("receipt_path") != str(path):
        problems.append("receipt approval_request.receipt_path must match the current receipt path")
    if section.get("full_parity_claimed") is not False:
        problems.append("receipt approval_request.full_parity_claimed must be false")
    if not isinstance(section.get("can_stage_candidate_files"), bool):
        problems.append("receipt approval_request.can_stage_candidate_files must be a boolean")
    if not isinstance(section.get("can_tag_rc_now"), bool):
        problems.append("receipt approval_request.can_tag_rc_now must be a boolean")
    if not isinstance(section.get("remaining_risks"), list):
        problems.append("receipt approval_request.remaining_risks must be a list")
    commands = section.get("exact_staging_commands")
    if not isinstance(commands, list) or not commands or any(not isinstance(command, str) for command in commands):
        problems.append("receipt approval_request.exact_staging_commands must be a non-empty list of strings")
    if section.get("no_broad_staging_command") is not True:
        problems.append("receipt approval_request.no_broad_staging_command must be true")
    return problems


def _receipt_is_refreshed_from_receipt_only_final_gate_cycle(
    payload: dict[str, Any] | None,
    owner_gate_plan_payload: dict[str, Any] | None,
) -> bool:
    """Detect the expected receipt/final-gate fixed point after owner gates are verified."""

    if payload is None or owner_gate_plan_payload is None:
        return False
    if _status(owner_gate_plan_payload, "status") != "verified":
        return False
    final_gate = payload.get("final_gate") if isinstance(payload.get("final_gate"), dict) else {}
    if final_gate.get("status") != "ready_with_receipt_refresh_required":
        return False
    approval_request = payload.get("approval_request")
    if not isinstance(approval_request, dict):
        return False
    return (
        approval_request.get("final_gate_status") == "ready_with_receipt_refresh_required"
        and approval_request.get("can_tag_rc_now") is False
    )


def _release_receipt_gate(
    path: Path,
    artifact_integrity_path: Path,
    source_bundle_path: Path,
    owner_gate_plan_path: Path,
    owner_env_template_path: Path,
    owner_gate_checklist_path: Path,
    owner_handoff_path: Path,
    additional_freshness_paths: dict[str, Path] | None = None,
) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, "status")
    artifact_payload, artifact_error = _read_json(artifact_integrity_path)
    source_payload, source_error = _read_json(source_bundle_path)
    owner_gate_plan_payload, owner_gate_plan_error = _read_json(owner_gate_plan_path)
    owner_env_template_payload, owner_env_template_error = _read_json(owner_env_template_path)
    owner_gate_checklist_payload, owner_gate_checklist_error = _read_json(owner_gate_checklist_path)
    owner_handoff_payload, owner_handoff_error = _read_json(owner_handoff_path)
    additional_reports = {
        name: _read_json(report_path)
        for name, report_path in (additional_freshness_paths or {}).items()
    }
    details = _summary_details("release_receipt", payload)
    problems: list[str] = []

    if error:
        problems.append(error)
    if artifact_error:
        problems.append(f"artifact integrity report unavailable: {artifact_error}")
    if source_error:
        problems.append(f"source bundle report unavailable: {source_error}")
    if owner_gate_plan_error:
        problems.append(f"owner gate plan report unavailable: {owner_gate_plan_error}")
    if owner_env_template_error:
        problems.append(f"owner env template report unavailable: {owner_env_template_error}")
    if owner_gate_checklist_error:
        problems.append(f"owner gate checklist report unavailable: {owner_gate_checklist_error}")
    if owner_handoff_error:
        problems.append(f"owner handoff gate report unavailable: {owner_handoff_error}")
    for name, (_, report_error) in additional_reports.items():
        if report_error:
            problems.append(f"{name} report unavailable: {report_error}")
    if status != "created":
        problems.append(f"expected ['created'], got {status}")
    if payload is not None and artifact_payload is not None and source_payload is not None:
        receipt_artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
        receipt_path = str(receipt_artifact.get("path") or "")
        receipt_sha = str(receipt_artifact.get("sha256") or "")
        artifact_path = str(artifact_payload.get("artifact_path") or "")
        artifact_sha = str(artifact_payload.get("artifact_sha256") or "")
        if not receipt_path or Path(receipt_path) != Path(artifact_path):
            problems.append("receipt artifact.path does not match artifact integrity artifact_path")
        if not receipt_sha or receipt_sha != artifact_sha:
            problems.append("receipt artifact.sha256 does not match artifact integrity artifact_sha256")
        security_scan = receipt_artifact.get("security_scan") if isinstance(receipt_artifact.get("security_scan"), dict) else {}
        if not security_scan:
            problems.append("receipt artifact.security_scan is missing")
        else:
            if security_scan.get("zip_security_scan_status") != "passed":
                problems.append("receipt artifact.security_scan.zip_security_scan_status is not passed")
            scanned_text_files = security_scan.get("scanned_text_files")
            if not isinstance(scanned_text_files, int) or scanned_text_files <= 0:
                problems.append("receipt artifact.security_scan.scanned_text_files must be positive")
            for key in (
                "secret_finding_count",
                "excluded_reference_finding_count",
                "local_path_finding_count",
            ):
                if security_scan.get(key) != 0:
                    problems.append(f"receipt artifact.security_scan.{key} must be 0")
        receipt_time = _parse_report_time(payload.get("generated_at"))
        artifact_time = _parse_report_time(artifact_payload.get("generated_at"))
        source_time = _parse_report_time(source_payload.get("generated_at"))
        owner_gate_plan_time = (
            _parse_report_time(owner_gate_plan_payload.get("generated_at")) if owner_gate_plan_payload else None
        )
        owner_env_template_time = (
            _parse_report_time(owner_env_template_payload.get("generated_at")) if owner_env_template_payload else None
        )
        owner_gate_checklist_time = (
            _parse_report_time(owner_gate_checklist_payload.get("generated_at"))
            if owner_gate_checklist_payload
            else None
        )
        owner_handoff_time = _parse_report_time(owner_handoff_payload.get("generated_at")) if owner_handoff_payload else None
        now = datetime.now(UTC)
        if receipt_time is None:
            problems.append("receipt generated_at is missing or invalid")
        elif _is_future_report_time(receipt_time, now=now):
            problems.append("receipt generated_at is in the future")
        if artifact_time is None:
            problems.append("artifact integrity generated_at is missing or invalid")
        elif _is_future_report_time(artifact_time, now=now):
            problems.append("artifact integrity generated_at is in the future")
        if source_time is None:
            problems.append("source bundle generated_at is missing or invalid")
        elif _is_future_report_time(source_time, now=now):
            problems.append("source bundle generated_at is in the future")
        if owner_gate_plan_time is None:
            problems.append("owner gate plan generated_at is missing or invalid")
        elif _is_future_report_time(owner_gate_plan_time, now=now):
            problems.append("owner gate plan generated_at is in the future")
        if owner_env_template_time is None:
            problems.append("owner env template generated_at is missing or invalid")
        elif _is_future_report_time(owner_env_template_time, now=now):
            problems.append("owner env template generated_at is in the future")
        if owner_gate_checklist_time is None:
            problems.append("owner gate checklist generated_at is missing or invalid")
        elif _is_future_report_time(owner_gate_checklist_time, now=now):
            problems.append("owner gate checklist generated_at is in the future")
        if owner_handoff_time is None:
            problems.append("owner handoff gate generated_at is missing or invalid")
        elif _is_future_report_time(owner_handoff_time, now=now):
            problems.append("owner handoff gate generated_at is in the future")
        if receipt_time is not None and artifact_time is not None and receipt_time < artifact_time:
            problems.append("release receipt is older than artifact integrity report")
        if receipt_time is not None and source_time is not None and receipt_time < source_time:
            problems.append("release receipt is older than source bundle report")
        if receipt_time is not None and owner_gate_plan_time is not None and receipt_time < owner_gate_plan_time:
            problems.append("release receipt is older than owner gate plan report")
        if receipt_time is not None and owner_env_template_time is not None and receipt_time < owner_env_template_time:
            problems.append("release receipt is older than owner env template report")
        if receipt_time is not None and owner_gate_checklist_time is not None and receipt_time < owner_gate_checklist_time:
            problems.append("release receipt is older than owner gate checklist report")
        if receipt_time is not None and owner_handoff_time is not None and receipt_time < owner_handoff_time:
            problems.append("release receipt is older than owner handoff gate report")
        for name, (report_payload, _) in additional_reports.items():
            report_time = _parse_report_time(report_payload.get("generated_at")) if report_payload else None
            if report_time is None:
                problems.append(f"{name} generated_at is missing or invalid")
            elif _is_future_report_time(report_time, now=now):
                problems.append(f"{name} generated_at is in the future")
            elif receipt_time is not None and receipt_time < report_time:
                problems.append(f"release receipt is older than {name} report")
        final_gate = payload.get("final_gate") if isinstance(payload.get("final_gate"), dict) else {}
        final_gate_status = str(final_gate.get("status") or "")
        if final_gate.get("bootstrap_allowed") is True or final_gate_status == "failed":
            problems.append("release receipt was generated from bootstrap final gate; rerun rc_release_receipt.py after final gate refresh")
        elif final_gate_status not in {
            "ready_with_receipt_refresh_required",
            "ready_with_owner_gates",
            "ready_for_rc_tag",
        }:
            problems.append("receipt final_gate.status is not a recognized refreshed final gate state")
        owner_gate_plan_status = _status(owner_gate_plan_payload, "status")
        if (
            owner_gate_plan_status == "verified"
            and final_gate_status != "ready_for_rc_tag"
            and not _receipt_is_refreshed_from_receipt_only_final_gate_cycle(payload, owner_gate_plan_payload)
        ):
            problems.append("receipt final_gate.status must be ready_for_rc_tag when owner gate plan is verified")
        checks = payload.get("checks")
        if isinstance(checks, list):
            checks_by_name = _check_map(payload)
            missing_checks = sorted(REQUIRED_RECEIPT_CHECKS.difference(checks_by_name))
            if missing_checks:
                problems.append(f"receipt missing required checks: {', '.join(missing_checks)}")
            failed_checks = [
                str(check.get("name") or "receipt_check")
                for check in checks
                if isinstance(check, dict) and check.get("status") != "passed"
            ]
            if failed_checks:
                problems.append(f"receipt contains failed checks: {', '.join(failed_checks)}")
        else:
            problems.append("receipt checks are missing")
        for section_name in sorted(REQUIRED_RECEIPT_GATE_SECTIONS):
            section = payload.get(section_name)
            if not isinstance(section, dict):
                problems.append(f"receipt missing {section_name} summary")
                continue
            section_status = section.get("status")
            if section_status != "passed":
                problems.append(f"receipt {section_name}.status is not passed")
            section_checks = section.get("checks")
            if not isinstance(section_checks, list) or not section_checks:
                problems.append(f"receipt {section_name}.checks is missing or empty")
            if section_name == "owner_handoff_gate":
                problems.extend(_receipt_owner_handoff_summary_problems(section))
        owner_env = payload.get("owner_env_template")
        if not isinstance(owner_env, dict):
            problems.append("receipt missing owner_env_template summary")
        else:
            if owner_env.get("status") != "created":
                problems.append("receipt owner_env_template.status is not created")
            if not isinstance(owner_env.get("entry_count"), int) or owner_env.get("entry_count") <= 0:
                problems.append("receipt owner_env_template.entry_count must be positive")
            if not _is_env_group_list(owner_env.get("env_groups")):
                problems.append("receipt owner_env_template.env_groups must be a list of env variable name groups")
        owner_checklist = payload.get("owner_gate_checklist")
        if not isinstance(owner_checklist, dict):
            problems.append("receipt missing owner_gate_checklist summary")
        else:
            if owner_checklist.get("status") not in {"verified", "ready_to_run", "action_required"}:
                problems.append("receipt owner_gate_checklist.status is not recognized")
            if not isinstance(owner_checklist.get("gate_count"), int) or owner_checklist.get("gate_count") <= 0:
                problems.append("receipt owner_gate_checklist.gate_count must be positive")
        owner_runner = payload.get("owner_gate_runner")
        if not isinstance(owner_runner, dict):
            problems.append("receipt missing owner_gate_runner summary")
        else:
            problems.extend(_receipt_owner_gate_runner_summary_problems(owner_runner))
        owner_actions = payload.get("owner_gate_next_actions")
        if not isinstance(owner_actions, list) or not owner_actions:
            problems.append("receipt owner_gate_next_actions is missing or empty")
        else:
            for index, action in enumerate(owner_actions, start=1):
                if not isinstance(action, dict):
                    problems.append(f"receipt owner_gate_next_actions[{index}] is not an object")
                    continue
                action_name = str(action.get("name") or f"gate_{index}")
                action_status = str(action.get("status") or "")
                if not action_name:
                    problems.append(f"receipt owner_gate_next_actions[{index}].name is missing")
                if action_status not in {"verified", "ready_to_run", "action_required"}:
                    problems.append(f"receipt owner_gate_next_actions.{action_name}.status is not recognized")
                for field_name in sorted(REQUIRED_OWNER_GATE_NEXT_ACTION_FIELDS):
                    value = action.get(field_name)
                    if field_name == "command":
                        if not isinstance(value, str) or not value.strip():
                            problems.append(f"receipt owner_gate_next_actions.{action_name}.command is missing")
                    elif not isinstance(value, list) or not value:
                        problems.append(f"receipt owner_gate_next_actions.{action_name}.{field_name} is missing")
        approval_request = payload.get("approval_request")
        if not isinstance(approval_request, dict):
            problems.append("receipt missing approval_request summary")
        else:
            problems.extend(_receipt_approval_request_problems(approval_request, payload, path))

    if problems:
        details["refresh_required"] = True
        details["refresh_reason"] = "; ".join(problems)
        return GateInput(
            name="release_receipt",
            path=str(path),
            status="refresh_required",
            ok=True,
            error="; ".join(problems),
            details=details,
        )

    return GateInput(
        name="release_receipt",
        path=str(path),
        status=status,
        ok=True,
        error=None,
        details=details,
    )


def _owner_gate_plan_freshness_gate(path: Path) -> GateInput:
    payload, error = _read_json(path)
    status = _status(payload, "status")
    details = _summary_details("owner_gate_plan", payload)
    problems: list[str] = []

    if error:
        problems.append(error)
    if payload is not None and status == "verified":
        freshness = payload.get("evidence_freshness")
        if not isinstance(freshness, dict):
            problems.append("owner_gate_plan.evidence_freshness is missing")
        else:
            details["evidence_freshness"] = freshness
            if freshness.get("required") is not True:
                problems.append("owner_gate_plan.evidence_freshness.required must be true for verified owner gates")
            if freshness.get("fresh") is not True:
                problems.append("owner_gate_plan evidence is not fresh for the current source bundle")
        gates = payload.get("gates")
        if not isinstance(gates, list) or not gates:
            problems.append("owner_gate_plan.gates is missing")
        elif any(not isinstance(gate, dict) or gate.get("status") != "verified" for gate in gates):
            problems.append("owner_gate_plan status is verified but not every gate is verified")

    return GateInput(
        name="owner_gate_plan_freshness",
        path=str(path),
        status="passed" if not problems else "failed",
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _normalized_path_list(items: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(items, list):
        return paths
    for item in items:
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = str(item.get("path") or "")
        else:
            continue
        normalized = path.replace("\\", "/").strip()
        if normalized:
            paths.append(normalized)
    return sorted(dict.fromkeys(paths))


def _staging_command_paths(payload: dict[str, Any] | None) -> list[str]:
    if not payload:
        return []
    paths: list[str] = []
    commands = payload.get("commands")
    if not isinstance(commands, list):
        return paths
    for command in commands:
        if isinstance(command, dict):
            paths.extend(_normalized_path_list(command.get("paths")))
    return sorted(dict.fromkeys(paths))


def _cross_report_consistency_gate(paths: dict[str, Path]) -> GateInput:
    """Ensure release staging and bundle evidence describe the same payload."""

    payloads: dict[str, dict[str, Any] | None] = {}
    problems: list[str] = []
    refresh_problems: list[str] = []
    for name in ("release_audit", "source_bundle", "staging_plan", "artifact_integrity_gate", "release_receipt"):
        payload, error = _read_json(paths[name])
        payloads[name] = payload
        if error:
            if name == "release_receipt":
                refresh_problems.append(f"{name}: {error}")
            else:
                problems.append(f"{name}: {error}")

    source_payload = payloads["source_bundle"]
    staging_payload = payloads["staging_plan"]
    artifact_payload = payloads["artifact_integrity_gate"]
    receipt_payload = payloads["release_receipt"]
    release_payload = payloads["release_audit"]

    release_candidate_count = (release_payload or {}).get("candidate_count")
    release_manifest_count = (release_payload or {}).get("manifest_count")
    source_count = (source_payload or {}).get("file_count")
    staging_count = (staging_payload or {}).get("file_count")
    artifact_count = (artifact_payload or {}).get("file_count")
    receipt_artifact = (receipt_payload or {}).get("artifact")
    receipt_count = receipt_artifact.get("file_count") if isinstance(receipt_artifact, dict) else None
    counts = {
        "release_audit_candidate": release_candidate_count,
        "release_audit_manifest": release_manifest_count,
        "source_bundle": source_count,
        "staging_plan": staging_count,
        "artifact_integrity_gate": artifact_count,
        "release_receipt": receipt_count,
    }
    local_counts = {
        "release_audit_candidate": release_candidate_count,
        "release_audit_manifest": release_manifest_count,
        "source_bundle": source_count,
        "staging_plan": staging_count,
        "artifact_integrity_gate": artifact_count,
    }
    if any(value is None for value in local_counts.values()):
        missing = [name for name, value in local_counts.items() if value is None]
        problems.append(f"missing file_count fields: {', '.join(missing)}")
    elif len(set(local_counts.values())) != 1:
        problems.append(f"file_count mismatch: {counts}")
    elif receipt_payload is not None:
        if receipt_count is None:
            refresh_problems.append("release_receipt.artifact.file_count is missing")
        elif receipt_count != source_count:
            refresh_problems.append("release_receipt artifact.file_count does not match current reports")

    source_paths = _normalized_path_list((source_payload or {}).get("files"))
    staging_paths = _staging_command_paths(staging_payload)
    if not source_paths:
        problems.append("source_bundle.files is missing or empty")
    if not staging_paths:
        problems.append("staging_plan.commands[].paths is missing or empty")
    if isinstance(source_count, int) and source_paths and source_count != len(source_paths):
        problems.append("source_bundle.file_count does not match files length")
    if isinstance(staging_count, int) and staging_paths and staging_count != len(staging_paths):
        problems.append("staging_plan.file_count does not match command path count")
    if source_paths and staging_paths and source_paths != staging_paths:
        missing_from_staging = sorted(set(source_paths).difference(staging_paths))
        extra_in_staging = sorted(set(staging_paths).difference(source_paths))
        problems.append(
            "staging/source path mismatch: "
            f"missing_from_staging={missing_from_staging}, extra_in_staging={extra_in_staging}"
        )

    if staging_payload is not None:
        for field_name in ("missing_files", "excluded_files", "errors"):
            values = staging_payload.get(field_name)
            if isinstance(values, list) and values:
                problems.append(f"staging_plan.{field_name} is not empty")
            elif values not in (None, []) and not isinstance(values, list):
                problems.append(f"staging_plan.{field_name} is not a list")

    if release_payload is not None:
        for field_name in (
            "missing_from_manifest",
            "manifest_extra",
            "secret_findings",
            "excluded_reference_findings",
        ):
            values = release_payload.get(field_name)
            if isinstance(values, list) and values:
                problems.append(f"release_audit.{field_name} is not empty")
            elif values not in (None, []) and not isinstance(values, list):
                problems.append(f"release_audit.{field_name} is not a list")

    details = {
        "file_counts": counts,
        "release_audit_clean": not any(
            isinstance((release_payload or {}).get(field_name), list)
            and (release_payload or {}).get(field_name)
            for field_name in (
                "missing_from_manifest",
                "manifest_extra",
                "secret_findings",
                "excluded_reference_findings",
            )
        ),
        "source_path_count": len(source_paths),
        "staging_path_count": len(staging_paths),
        "staging_plan_clean": not any(
            isinstance((staging_payload or {}).get(field_name), list)
            and (staging_payload or {}).get(field_name)
            for field_name in ("missing_files", "excluded_files", "errors")
        ),
        "refresh_required": bool(refresh_problems),
    }
    if refresh_problems and not problems:
        details["refresh_reason"] = "; ".join(refresh_problems)
        return GateInput(
            name="release_report_consistency",
            path=", ".join(
                str(paths[name])
                for name in ("release_audit", "source_bundle", "staging_plan", "artifact_integrity_gate", "release_receipt")
            ),
            status="refresh_required",
            ok=True,
            details=details,
            error="; ".join(refresh_problems),
        )
    return GateInput(
        name="release_report_consistency",
        path=", ".join(
            str(paths[name])
            for name in ("release_audit", "source_bundle", "staging_plan", "artifact_integrity_gate", "release_receipt")
        ),
        status="passed" if not problems else "failed",
        ok=not problems,
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _summary_details(name: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if name == "gap_matrix":
        summary = payload.get("summary") or {}
        return {
            "counts": summary.get("counts"),
            "competitive_parity": summary.get("competitive_parity"),
        }
    if name == "release_audit":
        return {
            "candidate_count": payload.get("candidate_count"),
            "missing_from_manifest": payload.get("missing_from_manifest", []),
            "secret_findings": payload.get("secret_findings", []),
            "excluded_reference_findings": payload.get("excluded_reference_findings", []),
            "local_path_findings": payload.get("local_path_findings", []),
        }
    if name == "runtime_smoke":
        return {
            "backend_base_url": payload.get("backend_base_url"),
            "frontend_base_url": payload.get("frontend_base_url"),
            "ports": payload.get("ports"),
        }
    if name == "external_smoke":
        checks = payload.get("checks", [])
        return {
            "require_configured": payload.get("require_configured"),
            "checks": [
                {"name": check.get("name"), "status": check.get("status"), "missing": check.get("missing", [])}
                for check in checks
                if isinstance(check, dict)
            ],
        }
    if name == "ci_contract":
        return {
            "workflow_path": payload.get("workflow_path"),
            "requirements_checked": payload.get("requirements_checked"),
            "forbidden_patterns_checked": payload.get("forbidden_patterns_checked"),
            "findings": payload.get("findings", []),
        }
    if name == "release_diff_review_gate":
        return {
            "review_path": payload.get("review_path"),
            "candidate_file_count": payload.get("candidate_file_count"),
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
        }
    if name == "deployment_docs_gate":
        return {
            "docs": payload.get("docs", {}),
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
            "next_commands": payload.get("next_commands", []),
        }
    if name == "owner_gate_plan":
        return {
            "status": payload.get("status"),
            "external_smoke_report": payload.get("external_smoke_report"),
            "source_bundle_report": payload.get("source_bundle_report"),
            "evidence_freshness": payload.get("evidence_freshness", {}),
            "gates": [
                {
                    "name": gate.get("name"),
                    "status": gate.get("status"),
                    "missing": gate.get("missing", []),
                }
                for gate in payload.get("gates", [])
                if isinstance(gate, dict)
            ],
            "next_commands": payload.get("next_commands", []),
        }
    if name == "owner_handoff_gate":
        checks: list[dict[str, Any]] = []
        for check in payload.get("checks", []):
            if not isinstance(check, dict):
                continue
            check_details = check.get("details") if isinstance(check.get("details"), dict) else {}
            secret_findings = check_details.get("secret_findings")
            local_path_findings = check_details.get("local_path_findings")
            summary = {
                "name": check.get("name"),
                "status": check.get("status"),
                "error": check.get("error"),
            }
            if isinstance(secret_findings, list):
                summary["secret_finding_count"] = len(secret_findings)
            if isinstance(local_path_findings, list):
                summary["local_path_finding_count"] = len(local_path_findings)
            checks.append(summary)
        return {
            "inputs": payload.get("inputs", {}),
            "checks": checks,
            "next_commands": payload.get("next_commands", []),
        }
    if name == "install_release_gate":
        return {
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
            "next_commands": payload.get("next_commands", []),
        }
    if name == "supply_chain_gate":
        return {
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
            "next_commands": payload.get("next_commands", []),
        }
    if name == "secrets_gate":
        return {
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
            "generated_value_count": payload.get("generated_value_count"),
            "unique_value_count": payload.get("unique_value_count"),
            "required_fields": payload.get("required_fields", []),
            "non_leakage_note": payload.get("non_leakage_note"),
        }
    if name == "source_bundle":
        return {
            "file_count": payload.get("file_count"),
            "dry_run": payload.get("dry_run"),
            "output_path": payload.get("output_path"),
            "clean_tracked_files": payload.get("clean_tracked_files", []),
            "errors": payload.get("errors", []),
        }
    if name == "artifact_integrity_gate":
        return {
            "artifact_path": payload.get("artifact_path"),
            "artifact_sha256": payload.get("artifact_sha256"),
            "artifact_size_bytes": payload.get("artifact_size_bytes"),
            "file_count": payload.get("file_count"),
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
        }
    if name == "release_receipt":
        artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
        final_gate = payload.get("final_gate") if isinstance(payload.get("final_gate"), dict) else {}
        return {
            "artifact": {
                "path": artifact.get("path"),
                "sha256": artifact.get("sha256"),
                "size_bytes": artifact.get("size_bytes"),
                "file_count": artifact.get("file_count"),
                "security_scan": artifact.get("security_scan", {}),
            },
            "final_gate": final_gate,
            "checks": [
                {
                    "name": check.get("name"),
                    "status": check.get("status"),
                    "error": check.get("error"),
                }
                for check in payload.get("checks", [])
                if isinstance(check, dict)
            ],
            "sidecars": payload.get("sidecars", {}),
        }
    if name == "staging_plan":
        return {
            "file_count": payload.get("file_count"),
            "command_count": payload.get("command_count"),
            "missing_files": payload.get("missing_files", []),
            "excluded_files": payload.get("excluded_files", []),
            "errors": payload.get("errors", []),
        }
    return {}


def _owner_gates(external_payload: dict[str, Any] | None) -> list[OwnerGate]:
    if not external_payload:
        return [
            OwnerGate(
                name="external_smoke",
                status="missing",
                missing=["Run scripts/rc_external_smoke.py with the intended provider/channel/GitHub test resources."],
            )
        ]
    gates: list[OwnerGate] = []
    for check in external_payload.get("checks", []):
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "")
        if status == "skipped":
            name = str(check.get("name") or "external_check")
            if name == "hosted_github_actions_run":
                name = "hosted_github_actions_commercial_rc"
            gates.append(
                OwnerGate(
                    name=name,
                    status=status,
                    missing=[str(item) for item in check.get("missing", [])],
                    details=dict(check.get("details") or {}),
                )
            )
    return gates


def _owner_plan_gates(owner_plan_payload: dict[str, Any] | None) -> list[OwnerGate]:
    if not owner_plan_payload:
        return [
            OwnerGate(
                name="owner_gate_plan",
                status="missing",
                missing=["Run scripts/rc_owner_gate_plan.py to produce the owner-controlled gate handoff."],
            )
        ]
    gates: list[OwnerGate] = []
    for gate in owner_plan_payload.get("gates", []):
        if not isinstance(gate, dict):
            continue
        status = str(gate.get("status") or "")
        if status != "verified":
            gates.append(
                OwnerGate(
                    name=str(gate.get("name") or "owner_gate"),
                    status=status,
                    missing=[str(item) for item in gate.get("missing", [])],
                    details={
                        "command": gate.get("command"),
                        "evidence": gate.get("evidence", []),
                        "completion_criteria": gate.get("completion_criteria", []),
                    },
                )
            )
    return gates


def _merge_owner_gates(*groups: list[OwnerGate]) -> list[OwnerGate]:
    merged: dict[str, OwnerGate] = {}
    for group in groups:
        for gate in group:
            existing = merged.get(gate.name)
            if existing is None:
                merged[gate.name] = gate
                continue
            missing = list(dict.fromkeys([*existing.missing, *gate.missing]))
            details = {**existing.details, **gate.details}
            status = gate.status if gate.status != "skipped" else existing.status
            merged[gate.name] = OwnerGate(name=gate.name, status=status, missing=missing, details=details)
    return list(merged.values())


def _refresh_release_chain_owner_gate(refresh_payload: dict[str, Any] | None) -> list[OwnerGate]:
    if not refresh_payload or refresh_payload.get("owner_verified") is True:
        return []
    return [
        OwnerGate(
            name="refresh_release_chain_owner_verified",
            status="action_required",
            missing=[
                "Run scripts/rc_refresh_release_chain.py with --owner-verified before RC tagging.",
            ],
            details={
                "owner_verified": refresh_payload.get("owner_verified"),
                "provider": refresh_payload.get("provider"),
                "status": refresh_payload.get("status"),
            },
        )
    ]


def run_final_gate(inputs: dict[str, Path] | None = None, *, allow_missing_evidence_pack: bool = False) -> FinalGateReport:
    paths = inputs or DEFAULT_INPUTS
    local_gates = [
        _gate_from_report("gap_matrix", paths["gap_matrix"], {"passed"}, status_keys=("summary", "overall_status")),
        _gate_from_report("release_audit", paths["release_audit"], {"passed"}),
        _gate_from_report("runtime_smoke", paths["runtime_smoke"], {"passed"}),
        _gate_from_report("external_smoke", paths["external_smoke"], {"passed"}),
        _gate_from_report("ci_contract", paths["ci_contract"], {"passed"}),
        _refresh_release_chain_gate(paths["refresh_release_chain"], allow_missing=allow_missing_evidence_pack),
        _gate_from_report("release_diff_review_gate", paths["release_diff_review_gate"], {"passed"}),
        _deployment_docs_gate(paths["deployment_docs_gate"], allow_missing=allow_missing_evidence_pack),
        _gate_from_report("owner_gate_plan", paths["owner_gate_plan"], {"verified", "ready_to_run", "action_required"}),
        _owner_gate_plan_freshness_gate(paths["owner_gate_plan"]),
        _owner_gate_runner_gate(paths["owner_gate_runner"]),
        _gate_from_report("owner_env_template", paths["owner_env_template"], {"created"}),
        _gate_from_report("owner_gate_checklist", paths["owner_gate_checklist"], {"verified", "ready_to_run", "action_required"}),
        _owner_handoff_gate(paths["owner_handoff_gate"]),
        _checked_report_gate(
            "install_release_gate",
            paths["install_release_gate"],
            expected_status={"passed"},
            required_checks=REQUIRED_INSTALL_RELEASE_CHECKS,
        ),
        _checked_report_gate(
            "supply_chain_gate",
            paths["supply_chain_gate"],
            expected_status={"passed"},
            required_checks=REQUIRED_SUPPLY_CHAIN_CHECKS,
        ),
        _secrets_gate(paths["secrets_gate"]),
        _gate_from_report("source_bundle", paths["source_bundle"], {"created"}),
        _artifact_integrity_gate(paths["artifact_integrity_gate"]),
        _release_receipt_gate(
            paths["release_receipt"],
            paths["artifact_integrity_gate"],
            paths["source_bundle"],
            paths["owner_gate_plan"],
            paths["owner_env_template"],
            paths["owner_gate_checklist"],
            paths["owner_handoff_gate"],
            {
                "owner gate runner": paths["owner_gate_runner"],
                "release diff review gate": paths["release_diff_review_gate"],
                "deployment docs gate": paths["deployment_docs_gate"],
                "staging plan": paths["staging_plan"],
                "install release gate": paths["install_release_gate"],
                "supply chain gate": paths["supply_chain_gate"],
                "secrets gate": paths["secrets_gate"],
            },
        ),
        _evidence_pack_gate(paths, allow_missing=allow_missing_evidence_pack),
        _gate_from_report("staging_plan", paths["staging_plan"], {"planned"}),
        _cross_report_consistency_gate(paths),
    ]
    external_payload, _ = _read_json(paths["external_smoke"])
    owner_plan_payload, _ = _read_json(paths["owner_gate_plan"])
    refresh_payload, _ = _read_json(paths["refresh_release_chain"])
    owner_gates = _merge_owner_gates(
        _owner_gates(external_payload),
        _owner_plan_gates(owner_plan_payload),
        _refresh_release_chain_owner_gate(refresh_payload),
    )
    local_ok = all(gate.ok for gate in local_gates)
    receipt_refresh_required = any(gate.details.get("refresh_required") is True for gate in local_gates)
    full_parity_claimed = False
    gap_payload, _ = _read_json(paths["gap_matrix"])
    if gap_payload:
        full_parity_claimed = bool(
            ((gap_payload.get("summary") or {}).get("competitive_parity") or {}).get("full_parity_claimed")
        )

    if not local_ok or full_parity_claimed:
        status = "failed"
    elif receipt_refresh_required:
        status = "ready_with_receipt_refresh_required"
    elif owner_gates:
        status = "ready_with_owner_gates"
    else:
        status = "ready_for_rc_tag"

    rc_candidate = local_ok and not full_parity_claimed and not receipt_refresh_required
    return FinalGateReport(
        status=status,
        generated_at=_utc_now(),
        rc_candidate=rc_candidate,
        full_parity_claimed=full_parity_claimed,
        local_gates=local_gates,
        owner_gates=owner_gates,
        release_decision={
            "can_tag_rc_now": status == "ready_for_rc_tag",
            "can_stage_candidate_files": local_ok and not receipt_refresh_required,
            "bootstrap_allowed": any(gate.details.get("bootstrap_allowed") is True for gate in local_gates),
            "reason": (
                "gap matrix overclaims full Codex/Hermes parity"
                if full_parity_claimed
                else "release receipt refresh required"
                if status == "ready_with_receipt_refresh_required"
                else
                "owner-controlled external gates remain"
                if status == "ready_with_owner_gates"
                else "local gate failed"
                if status == "failed"
                else "all local and owner gates passed"
            ),
            "non_claim": "This report does not claim full Codex/Hermes parity.",
        },
    )


def write_report(report: FinalGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidate X-Agent commercial RC final gate reports")
    parser.add_argument("--gap-matrix", type=Path, default=DEFAULT_INPUTS["gap_matrix"])
    parser.add_argument("--release-audit", type=Path, default=DEFAULT_INPUTS["release_audit"])
    parser.add_argument("--runtime-smoke", type=Path, default=DEFAULT_INPUTS["runtime_smoke"])
    parser.add_argument("--external-smoke", type=Path, default=DEFAULT_INPUTS["external_smoke"])
    parser.add_argument("--ci-contract", type=Path, default=DEFAULT_INPUTS["ci_contract"])
    parser.add_argument("--refresh-release-chain", type=Path, default=DEFAULT_INPUTS["refresh_release_chain"])
    parser.add_argument("--release-diff-review-gate", type=Path, default=DEFAULT_INPUTS["release_diff_review_gate"])
    parser.add_argument("--deployment-docs-gate", type=Path, default=DEFAULT_INPUTS["deployment_docs_gate"])
    parser.add_argument("--owner-gate-plan", type=Path, default=DEFAULT_INPUTS["owner_gate_plan"])
    parser.add_argument("--owner-gate-runner", type=Path, default=DEFAULT_INPUTS["owner_gate_runner"])
    parser.add_argument("--owner-env-template", type=Path, default=DEFAULT_INPUTS["owner_env_template"])
    parser.add_argument("--owner-gate-checklist", type=Path, default=DEFAULT_INPUTS["owner_gate_checklist"])
    parser.add_argument("--owner-handoff-gate", type=Path, default=DEFAULT_INPUTS["owner_handoff_gate"])
    parser.add_argument("--install-release-gate", type=Path, default=DEFAULT_INPUTS["install_release_gate"])
    parser.add_argument("--supply-chain-gate", type=Path, default=DEFAULT_INPUTS["supply_chain_gate"])
    parser.add_argument("--secrets-gate", type=Path, default=DEFAULT_INPUTS["secrets_gate"])
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_INPUTS["source_bundle"])
    parser.add_argument("--artifact-integrity-gate", type=Path, default=DEFAULT_INPUTS["artifact_integrity_gate"])
    parser.add_argument("--release-receipt", type=Path, default=DEFAULT_INPUTS["release_receipt"])
    parser.add_argument("--evidence-pack", type=Path, default=DEFAULT_INPUTS["evidence_pack"])
    parser.add_argument("--staging-plan", type=Path, default=DEFAULT_INPUTS["staging_plan"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--allow-missing-evidence-pack",
        action="store_true",
        help="allow the first bootstrap final gate before rc_evidence_pack.py has produced its report",
    )
    parser.add_argument("--require-ready-to-tag", action="store_true", help="fail when owner gates remain")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_final_gate(
        {
            "gap_matrix": args.gap_matrix,
            "release_audit": args.release_audit,
            "runtime_smoke": args.runtime_smoke,
            "external_smoke": args.external_smoke,
            "ci_contract": args.ci_contract,
            "refresh_release_chain": args.refresh_release_chain,
            "release_diff_review_gate": args.release_diff_review_gate,
            "deployment_docs_gate": args.deployment_docs_gate,
            "owner_gate_plan": args.owner_gate_plan,
            "owner_gate_runner": args.owner_gate_runner,
            "owner_env_template": args.owner_env_template,
            "owner_gate_checklist": args.owner_gate_checklist,
            "owner_handoff_gate": args.owner_handoff_gate,
            "install_release_gate": args.install_release_gate,
            "supply_chain_gate": args.supply_chain_gate,
            "secrets_gate": args.secrets_gate,
            "source_bundle": args.source_bundle,
            "artifact_integrity_gate": args.artifact_integrity_gate,
            "release_receipt": args.release_receipt,
            "evidence_pack": args.evidence_pack,
            "staging_plan": args.staging_plan,
        },
        allow_missing_evidence_pack=args.allow_missing_evidence_pack,
    )
    write_report(report, args.output)
    print(f"RC final gate status: {report.status}")
    print(f"Report written to {args.output}")
    for gate in report.local_gates:
        print(f"- {gate.name}: {gate.status} ({'ok' if gate.ok else 'failed'})")
    for gate in report.owner_gates:
        print(f"- owner gate {gate.name}: {gate.status}")
    if report.status == "failed":
        return 1
    if args.require_ready_to_tag and report.status != "ready_for_rc_tag":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
