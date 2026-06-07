#!/usr/bin/env python3
"""Validate production secret generation readiness for the commercial RC.

The gate intentionally never writes generated secret values to its report. It
records only field names, lengths, format classes, and the source-control
secret-scan status from the release audit report.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.generate_secrets import generate_all_secrets

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_RELEASE_AUDIT = REPORT_DIR / "rc-release-audit.json"
DEFAULT_ARTIFACT_INTEGRITY = REPORT_DIR / "rc-artifact-integrity-gate.json"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_OUTPUT = REPORT_DIR / "rc-secrets-gate.json"

REQUIRED_FIELDS = {
    "JWT_SECRET",
    "ENCRYPTION_KEY",
    "AUDIT_HMAC_SECRET",
    "BOOTSTRAP_API_KEY",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "NEO4J_PASSWORD",
}
PROHIBITED_SECRET_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.staging",
    ".env.test",
}
PROHIBITED_SECRET_SUFFIXES = (".key", ".p12", ".pem", ".pfx")
PROHIBITED_SECRET_PATH_COMPONENTS = {".secrets", "secret", "secrets"}
ALLOWED_SECRET_TEMPLATE_SUFFIXES = (
    ".env.example",
    ".env.template",
    ".sample.env",
    ".template.env",
)


@dataclass(frozen=True)
class SecretShape:
    name: str
    present: bool
    length: int
    format_class: str


@dataclass(frozen=True)
class SecretsCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SecretsGateReport:
    status: str
    generated_at: str
    checks: list[SecretsCheck]
    secret_shapes: list[SecretShape]
    required_fields: list[str]
    unique_value_count: int
    generated_value_count: int
    release_audit_path: str
    artifact_integrity_path: str
    source_bundle_path: str
    non_leakage_note: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["secret_shapes"] = [asdict(shape) for shape in self.secret_shapes]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json_report(path: Path, label: str) -> tuple[dict[str, Any] | None, SecretsCheck | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, SecretsCheck(
            name=label,
            status="failed",
            error=f"{label} report missing",
            details={"path": str(path)},
        )
    except json.JSONDecodeError as exc:
        return None, SecretsCheck(
            name=label,
            status="failed",
            error=f"invalid {label} JSON: {exc}",
            details={"path": str(path)},
        )
    if not isinstance(payload, dict):
        return None, SecretsCheck(
            name=label,
            status="failed",
            error=f"{label} report is not a JSON object",
            details={"path": str(path)},
        )
    return payload, None


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


def _normalized_path(raw_value: Any) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    return str(Path(raw_value).resolve(strict=False))


def _bundle_file_paths(payload: dict[str, Any]) -> list[str]:
    files = payload.get("files", [])
    if not isinstance(files, list):
        return []
    paths: list[str] = []
    for item in files:
        if isinstance(item, str):
            raw_path = item
        elif isinstance(item, dict):
            raw_path = str(item.get("path") or "")
        else:
            continue
        path = raw_path.replace("\\", "/").strip()
        if path:
            paths.append(path)
    return sorted(dict.fromkeys(paths))


def _is_prohibited_secret_artifact_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip().lower()
    if not normalized:
        return False
    if normalized.endswith(ALLOWED_SECRET_TEMPLATE_SUFFIXES):
        return False
    parts = [part for part in normalized.split("/") if part]
    file_name = parts[-1] if parts else normalized
    if file_name in PROHIBITED_SECRET_FILE_NAMES:
        return True
    if any(part in PROHIBITED_SECRET_PATH_COMPONENTS for part in parts[:-1]):
        return True
    if normalized.endswith(".env"):
        return True
    return normalized.endswith(PROHIBITED_SECRET_SUFFIXES)


def _format_class(value: str) -> str:
    if value.startswith("xagent-"):
        return "prefixed-token"
    if re.fullmatch(r"[0-9a-f]+", value):
        return "hex"
    if re.fullmatch(r"[A-Za-z0-9]+", value):
        return "alnum"
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return "mixed"
    return "base64"


def _secret_shapes(secrets: dict[str, str]) -> list[SecretShape]:
    return [
        SecretShape(
            name=name,
            present=name in secrets,
            length=len(str(secrets.get(name, ""))),
            format_class=_format_class(str(secrets.get(name, ""))) if name in secrets else "missing",
        )
        for name in sorted(REQUIRED_FIELDS)
    ]


def check_required_fields(secrets: dict[str, str]) -> SecretsCheck:
    missing = sorted(REQUIRED_FIELDS.difference(secrets))
    unexpected = sorted(set(secrets).difference(REQUIRED_FIELDS))
    status = "passed" if not missing and not unexpected else "failed"
    return SecretsCheck(
        name="required_fields",
        status=status,
        details={
            "missing": missing,
            "unexpected": unexpected,
            "required_count": len(REQUIRED_FIELDS),
            "generated_count": len(secrets),
        },
    )


def check_secret_strength(secrets: dict[str, str]) -> SecretsCheck:
    failures: list[str] = []

    if len(secrets.get("JWT_SECRET", "")) < 64:
        failures.append("JWT_SECRET must be at least 64 characters.")

    encryption_key = secrets.get("ENCRYPTION_KEY", "")
    try:
        encryption_bytes = base64.b64decode(encryption_key, validate=True)
    except (binascii.Error, ValueError):
        encryption_bytes = b""
    if len(encryption_bytes) != 32:
        failures.append("ENCRYPTION_KEY must be base64 for exactly 32 bytes.")

    audit_hmac = secrets.get("AUDIT_HMAC_SECRET", "")
    if not re.fullmatch(r"[0-9a-f]{64}", audit_hmac):
        failures.append("AUDIT_HMAC_SECRET must be 64 lowercase hex characters.")

    bootstrap_key = secrets.get("BOOTSTRAP_API_KEY", "")
    if not bootstrap_key.startswith("xagent-") or len(bootstrap_key) < 48:
        failures.append("BOOTSTRAP_API_KEY must use the xagent- prefix and be at least 48 characters.")

    if len(secrets.get("S3_ACCESS_KEY", "")) < 24:
        failures.append("S3_ACCESS_KEY must be at least 24 characters.")

    if len(secrets.get("S3_SECRET_KEY", "")) < 48:
        failures.append("S3_SECRET_KEY must be at least 48 characters.")

    if len(secrets.get("NEO4J_PASSWORD", "")) < 32:
        failures.append("NEO4J_PASSWORD must be at least 32 characters.")

    return SecretsCheck(
        name="secret_strength",
        status="passed" if not failures else "failed",
        details={"failures": failures},
    )


def check_uniqueness(secrets: dict[str, str]) -> SecretsCheck:
    values = [str(value) for value in secrets.values()]
    unique_count = len(set(values))
    duplicates = len(values) - unique_count
    return SecretsCheck(
        name="unique_generated_values",
        status="passed" if duplicates == 0 else "failed",
        details={"generated_value_count": len(values), "unique_value_count": unique_count, "duplicate_count": duplicates},
    )


def check_release_audit_secret_scan(release_audit_path: Path) -> SecretsCheck:
    payload, error_check = _read_json_report(release_audit_path, "release_audit_secret_scan")
    if error_check:
        return error_check
    assert payload is not None

    secret_findings = payload.get("secret_findings", [])
    if not isinstance(secret_findings, list):
        secret_findings = ["invalid secret_findings field"]
    return SecretsCheck(
        name="release_audit_secret_scan",
        status="passed" if payload.get("status") == "passed" and not secret_findings else "failed",
        details={
            "release_audit_status": payload.get("status"),
            "secret_finding_count": len(secret_findings),
            "release_audit_path": str(release_audit_path),
        },
    )


def _check_named_report_check(payload: dict[str, Any], name: str) -> dict[str, Any] | None:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return None
    for item in checks:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None


def check_artifact_secret_scan(artifact_integrity_path: Path, source_bundle_path: Path) -> SecretsCheck:
    artifact_payload, artifact_error = _read_json_report(artifact_integrity_path, "artifact_secret_scan")
    source_payload, source_error = _read_json_report(source_bundle_path, "artifact_secret_scan")
    if artifact_error or source_error:
        failures = []
        if artifact_error:
            failures.append(artifact_error.error)
        if source_error:
            failures.append(source_error.error)
        return SecretsCheck(
            name="artifact_secret_scan",
            status="failed",
            error="; ".join(failure for failure in failures if failure),
            details={
                "artifact_integrity_path": str(artifact_integrity_path),
                "source_bundle_path": str(source_bundle_path),
            },
        )
    assert artifact_payload is not None
    assert source_payload is not None

    failures: list[str] = []
    artifact_status = artifact_payload.get("status")
    source_status = source_payload.get("status")
    if artifact_status != "passed":
        failures.append(f"expected artifact integrity status passed, got {artifact_status}")
    if source_status != "created":
        failures.append(f"expected source bundle status created, got {source_status}")
    if source_payload.get("dry_run") is not False:
        failures.append("source bundle report must come from --create, not dry-run")

    artifact_file_count = artifact_payload.get("file_count")
    source_file_count = source_payload.get("file_count")
    if not isinstance(artifact_file_count, int) or not isinstance(source_file_count, int):
        failures.append("artifact and source bundle file_count values must be integers")
    elif artifact_file_count != source_file_count:
        failures.append(f"file_count mismatch: artifact={artifact_file_count}, source_bundle={source_file_count}")

    artifact_path = _normalized_path(artifact_payload.get("artifact_path"))
    source_output_path = _normalized_path(source_payload.get("output_path"))
    if not artifact_path or not source_output_path:
        failures.append("artifact_path and source bundle output_path are required")
    elif artifact_path != source_output_path:
        failures.append("artifact_path does not match source bundle output_path")

    reported_source_bundle = _normalized_path(artifact_payload.get("source_bundle_report"))
    expected_source_bundle = _normalized_path(str(source_bundle_path))
    if not reported_source_bundle:
        failures.append("artifact integrity report does not name its source_bundle_report")
    elif reported_source_bundle != expected_source_bundle:
        failures.append("artifact integrity source_bundle_report does not match the provided source bundle report")

    source_generated_at = source_payload.get("generated_at")
    artifact_generated_at = artifact_payload.get("generated_at")
    source_time = _parse_report_time(source_generated_at)
    artifact_time = _parse_report_time(artifact_generated_at)
    if source_time is None or artifact_time is None:
        failures.append("artifact and source bundle reports must include valid generated_at timestamps")
    elif artifact_time < source_time:
        failures.append("artifact integrity report is older than the source bundle report")

    zip_scan = _check_named_report_check(artifact_payload, "zip_security_scan")
    zip_scan_status = zip_scan.get("status") if isinstance(zip_scan, dict) else None
    zip_scan_details = zip_scan.get("details", {}) if isinstance(zip_scan, dict) else {}
    if zip_scan is None:
        failures.append("artifact integrity report is missing zip_security_scan")
        zip_scan_details = {}
    elif zip_scan_status != "passed":
        failures.append(f"expected zip_security_scan status passed, got {zip_scan_status}")
    if not isinstance(zip_scan_details, dict):
        failures.append("zip_security_scan details must be a JSON object")
        zip_scan_details = {}

    secret_findings = zip_scan_details.get("secret_findings", [])
    excluded_reference_findings = zip_scan_details.get("excluded_reference_findings", [])
    local_path_findings = zip_scan_details.get("local_path_findings", [])
    scanned_text_files = zip_scan_details.get("scanned_text_files")
    if not isinstance(secret_findings, list):
        failures.append("zip_security_scan.details.secret_findings must be a list")
        secret_finding_count: int | None = None
    else:
        secret_finding_count = len(secret_findings)
        if secret_findings:
            failures.append("zip_security_scan reported secret findings")
    if not isinstance(excluded_reference_findings, list):
        failures.append("zip_security_scan.details.excluded_reference_findings must be a list")
        excluded_reference_finding_count: int | None = None
    else:
        excluded_reference_finding_count = len(excluded_reference_findings)
        if excluded_reference_findings:
            failures.append("zip_security_scan reported excluded-area references")
    if not isinstance(local_path_findings, list):
        failures.append("zip_security_scan.details.local_path_findings must be a list")
        local_path_finding_count: int | None = None
    else:
        local_path_finding_count = len(local_path_findings)
        if local_path_findings:
            failures.append("zip_security_scan reported local path references")
    if not isinstance(scanned_text_files, int) or scanned_text_files <= 0:
        failures.append("zip_security_scan must scan at least one text file")

    return SecretsCheck(
        name="artifact_secret_scan",
        status="passed" if not failures else "failed",
        details={
            "artifact_integrity_status": artifact_status,
            "source_bundle_status": source_status,
            "artifact_file_count": artifact_file_count,
            "source_bundle_file_count": source_file_count,
            "zip_security_scan_status": zip_scan_status,
            "secret_finding_count": secret_finding_count,
            "excluded_reference_finding_count": excluded_reference_finding_count,
            "local_path_finding_count": local_path_finding_count,
            "scanned_text_files": scanned_text_files,
            "source_bundle_generated_at": source_generated_at,
            "artifact_integrity_generated_at": artifact_generated_at,
            "artifact_integrity_path": str(artifact_integrity_path),
            "source_bundle_path": str(source_bundle_path),
            "failures": failures,
        },
    )


def check_prohibited_secret_artifacts(source_bundle_path: Path) -> SecretsCheck:
    payload, error_check = _read_json_report(source_bundle_path, "prohibited_secret_artifacts")
    if error_check:
        return error_check
    assert payload is not None

    paths = _bundle_file_paths(payload)
    failures: list[str] = []
    if payload.get("status") != "created":
        failures.append(f"expected source bundle status created, got {payload.get('status')}")
    if not paths:
        failures.append("source bundle file list is missing or empty")
    prohibited_paths = [path for path in paths if _is_prohibited_secret_artifact_path(path)]
    if prohibited_paths:
        failures.append("source bundle contains prohibited secret artifact paths")
    return SecretsCheck(
        name="prohibited_secret_artifacts",
        status="passed" if not failures else "failed",
        details={
            "source_bundle_status": payload.get("status"),
            "checked_file_count": len(paths),
            "prohibited_paths": prohibited_paths,
            "failures": failures,
        },
    )


def run_secrets_gate(
    release_audit_path: Path = DEFAULT_RELEASE_AUDIT,
    artifact_integrity_path: Path = DEFAULT_ARTIFACT_INTEGRITY,
    source_bundle_path: Path = DEFAULT_SOURCE_BUNDLE,
) -> SecretsGateReport:
    secrets = {str(key): str(value) for key, value in generate_all_secrets().items()}
    checks = [
        check_required_fields(secrets),
        check_secret_strength(secrets),
        check_uniqueness(secrets),
        check_release_audit_secret_scan(release_audit_path),
        check_artifact_secret_scan(artifact_integrity_path, source_bundle_path),
        check_prohibited_secret_artifacts(source_bundle_path),
    ]
    values = list(secrets.values())
    return SecretsGateReport(
        status="passed" if all(check.status == "passed" for check in checks) else "failed",
        generated_at=_utc_now(),
        checks=checks,
        secret_shapes=_secret_shapes(secrets),
        required_fields=sorted(REQUIRED_FIELDS),
        unique_value_count=len(set(values)),
        generated_value_count=len(values),
        release_audit_path=str(release_audit_path),
        artifact_integrity_path=str(artifact_integrity_path),
        source_bundle_path=str(source_bundle_path),
        non_leakage_note="Generated secret values are validated in memory and are not included in this report.",
    )


def write_report(report: SecretsGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate commercial RC secret generation readiness")
    parser.add_argument("--release-audit", type=Path, default=DEFAULT_RELEASE_AUDIT)
    parser.add_argument("--artifact-integrity", type=Path, default=DEFAULT_ARTIFACT_INTEGRITY)
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_secrets_gate(args.release_audit, args.artifact_integrity, args.source_bundle)
    write_report(report, args.output)
    print(f"RC secrets gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
