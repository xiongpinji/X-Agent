#!/usr/bin/env python3
"""Create a commercial RC evidence pack for release-owner handoff.

The source bundle is the deployable code artifact. This evidence pack is the
handoff archive: receipt, reports, owner env templates, owner checklist, and
artifact checksums in one zip. It intentionally stays under `.xagent_runtime`
and is not meant for source-control staging.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from scripts.rc_release_audit import SECRET_PATTERNS, TEXT_SUFFIXES, _is_allowed_secret_match_sample, _redact
from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
RELEASE_DIR = ROOT / ".xagent_runtime" / "release"
SMOKE_DIR = ROOT / ".xagent_runtime" / "smoke"

DEFAULT_RECEIPT = RELEASE_DIR / "x-agent-commercial-rc-receipt.json"
DEFAULT_OUTPUT_REPORT = REPORT_DIR / "rc-evidence-pack.json"
MAX_GENERATED_AT_FUTURE_SKEW = timedelta(minutes=5)

REQUIRED_REPORTS = (
    REPORT_DIR / "codex-hermes-gap-closure.json",
    REPORT_DIR / "rc-release-audit.json",
    REPORT_DIR / "rc-ci-contract.json",
    REPORT_DIR / "rc-release-diff-review-gate.json",
    REPORT_DIR / "rc-deployment-docs-gate.json",
    REPORT_DIR / "rc-external-smoke.json",
    REPORT_DIR / "rc-refresh-release-chain.json",
    REPORT_DIR / "rc-owner-gate-plan.json",
    REPORT_DIR / "rc-owner-gate-runner.json",
    REPORT_DIR / "rc-owner-handoff-gate.json",
    REPORT_DIR / "rc-owner-env-template.json",
    REPORT_DIR / "rc-owner-env-template.env",
    REPORT_DIR / "rc-owner-env-template.ps1",
    REPORT_DIR / "rc-owner-gate-checklist.json",
    REPORT_DIR / "rc-owner-gate-checklist.md",
    REPORT_DIR / "rc-source-bundle.json",
    REPORT_DIR / "rc-artifact-integrity-gate.json",
    REPORT_DIR / "rc-staging-plan.json",
    REPORT_DIR / "rc-install-release-gate.json",
    REPORT_DIR / "rc-single-user-local-gate.json",
    REPORT_DIR / "rc-supply-chain-gate.json",
    REPORT_DIR / "rc-secrets-gate.json",
    REPORT_DIR / "rc-final-gate.json",
    SMOKE_DIR / "rc-runtime-smoke.json",
)

LOCAL_PATH_PATTERNS = (
    re.compile(
        r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"']+[\\/]+AppData[\\/]+(?:Local|LocalLow|Roaming)"
        r"(?:[\\/]+[^\\/\s\"']+)*"
    ),
    re.compile(
        r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"']+[\\/]+(?:\.agents|\.cache|\.codex|\.config)"
        r"(?:[\\/]+[^\\/\s\"']+)*"
    ),
    re.compile(r"(?i)(?<!\w)/(?:Users|home)/[^/\s\"']+/(?:\.agents|\.cache|\.codex|\.config)(?:/[^/\s\"']+)*"),
    re.compile(r"(?i)(?<!\w)/Users/[^/\s\"']+/Library/(?:Application Support|Caches)(?:/[^\"']+)?"),
    re.compile(r"(?i)\bhermes-agent\b"),
)
ARCHIVE_SECRET_KEY_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
ARCHIVE_SECRET_VALUE_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")
ARCHIVE_WINDOWS_LOCAL_PATH_RE = re.compile(
    r"(?i)\b[A-Z]:(?:\\\\|[\\/])+(?:(?!\\\\[nr])[^\"'\r\n])+"
)
ARCHIVE_POSIX_LOCAL_PATH_RE = re.compile(
    r"(?<!\w)/(?:Users|home|tmp|var)/(?:[^/\s\"']+/)*[^/\s\"']*"
)
ARCHIVE_OLLAMA_BLOB_RE = re.compile(r"(?i)\bblobs(?:\\\\|[\\/])+sha256-[a-f0-9]{24,}\b")

ALLOWED_LOCAL_PATH_MARKERS = (
    "/appdata/local/temp/pytest-of-",
    "/appdata/local/temp/pytest-",
    "/tmp/pytest-of-",
    "/tmp/pytest-",
)
RECEIPT_VALIDATOR_REPORTS = {
    ".xagent_runtime/reports/rc-final-gate.json",
    ".xagent_runtime/reports/rc-refresh-release-chain.json",
}
SELF_EVIDENCE_PACK_REPORT_ARCHIVE_PATH = ".xagent_runtime/reports/rc-evidence-pack.json"
OWNER_GATE_RUNNER_ARCHIVE_PATH = ".xagent_runtime/reports/rc-owner-gate-runner.json"
OWNER_ENV_TEMPLATE_ARCHIVE_PATH = ".xagent_runtime/reports/rc-owner-env-template.env"
OWNER_GATE_RUNNER_REQUIRED_ALL_COMMAND_TOKENS = (
    "scripts/rc_external_smoke.py",
    "--github-execute-preflight",
    "--github-actions-preflight",
    "--require-configured",
)


@dataclass(frozen=True)
class EvidencePackFile:
    path: str
    archive_path: str
    size_bytes: int
    sha256: str
    required: bool = True


@dataclass(frozen=True)
class EvidencePackCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class EvidencePackReport:
    status: str
    generated_at: str
    receipt_path: str
    output_path: str | None
    pack_sha256: str | None
    file_count: int
    files: list[EvidencePackFile]
    checks: list[EvidencePackCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["files"] = [asdict(item) for item in self.files]
        payload["checks"] = [asdict(item) for item in self.checks]
        return payload


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"missing JSON file: {path}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON file is not an object: {path}"
    return payload, None


def _default_pack_path(output_dir: Path = RELEASE_DIR) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"x-agent-commercial-rc-evidence-{stamp}.zip"


def _resolve_path(raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def _artifact_paths_from_receipt(receipt: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    artifact = receipt.get("artifact")
    if isinstance(artifact, dict):
        path = _resolve_path(artifact.get("path"))
        if path is not None:
            paths.append(path)
    sidecars = receipt.get("sidecars")
    if isinstance(sidecars, dict):
        sidecar = _resolve_path(sidecars.get("sha256"))
        if sidecar is not None:
            paths.append(sidecar)
    return paths


def _relative_archive_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
        return relative.as_posix()
    except ValueError:
        return f"external/{path.name}"


def _is_self_evidence_pack_report(path: Path) -> bool:
    archive_path = _relative_archive_path(path)
    return archive_path == SELF_EVIDENCE_PACK_REPORT_ARCHIVE_PATH or (
        path.name == "rc-evidence-pack.json" and path.parent.name == "reports"
    )


def _pack_inputs(receipt_path: Path, receipt: dict[str, Any], extra_reports: Iterable[Path]) -> list[Path]:
    ordered: list[Path] = [receipt_path, *_artifact_paths_from_receipt(receipt), *REQUIRED_REPORTS, *extra_reports]
    seen: set[str] = set()
    unique: list[Path] = []
    for path in ordered:
        if _is_self_evidence_pack_report(path):
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _inspect_files(paths: Iterable[Path]) -> tuple[list[EvidencePackFile], list[str]]:
    files: list[EvidencePackFile] = []
    missing: list[str] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            missing.append(str(path))
            continue
        files.append(
            EvidencePackFile(
                path=str(path),
                archive_path=_relative_archive_path(path),
                size_bytes=path.stat().st_size,
                sha256=_sha256_file(path),
                required=True,
            )
        )
    return files, missing


def _scan_text_file(path: Path, archive_path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return findings
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings
    for line_number, line in enumerate(lines, start=1):
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(line):
                sample = match.group(1) if match.groups() else match.group(0)
                if _is_allowed_secret_match_sample(sample):
                    continue
                findings.append(
                    {
                        "path": archive_path,
                        "line": line_number,
                        "pattern": pattern.pattern,
                        "sample": _redact(sample),
                    }
                )
    return findings



def _security_scan(files: list[EvidencePackFile]) -> EvidencePackCheck:
    findings: list[dict[str, Any]] = []
    scanned = 0
    for item in files:
        path = Path(item.path)
        if path.suffix.lower() in TEXT_SUFFIXES:
            scanned += 1
        findings.extend(_scan_text_file(path, item.archive_path))
    return EvidencePackCheck(
        name="evidence_secret_scan",
        status="passed" if not findings else "failed",
        details={"scanned_text_files": scanned, "secret_findings": findings},
        error=None if not findings else "evidence pack contains secret-like text findings",
    )


def _scan_privacy_file(path: Path, archive_path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    archive_text = _archive_text(path)
    if archive_text is None:
        return findings
    lines = archive_text.splitlines()
    for line_number, line in enumerate(lines, start=1):
        for pattern in LOCAL_PATH_PATTERNS:
            for match in pattern.finditer(line):
                sample = match.group(0)
                normalized_sample = re.sub(r"/+", "/", sample.replace("\\", "/").lower())
                if any(marker in normalized_sample for marker in ALLOWED_LOCAL_PATH_MARKERS):
                    continue
                findings.append(
                    {
                        "path": archive_path,
                        "line": line_number,
                        "pattern": pattern.pattern,
                        "sample": _redact(sample),
                    }
                )
    return findings


def _privacy_scan(files: list[EvidencePackFile]) -> EvidencePackCheck:
    findings: list[dict[str, Any]] = []
    scanned = 0
    for item in files:
        path = Path(item.path)
        if path.suffix.lower() in TEXT_SUFFIXES:
            scanned += 1
        findings.extend(_scan_privacy_file(path, item.archive_path))
    return EvidencePackCheck(
        name="evidence_local_path_privacy_scan",
        status="passed" if not findings else "failed",
        details={"scanned_text_files": scanned, "privacy_findings": findings},
        error=None if not findings else "evidence pack contains local user/runtime path findings",
    )


def _sanitize_archive_text(text: str) -> str:
    text = ARCHIVE_SECRET_KEY_RE.sub(r"\1<redacted-output>", text)
    text = ARCHIVE_SECRET_VALUE_RE.sub("<redacted-secret>", text)
    text = ARCHIVE_OLLAMA_BLOB_RE.sub("<redacted-ollama-blob>", text)
    text = ARCHIVE_WINDOWS_LOCAL_PATH_RE.sub("<redacted-local-path>", text)
    text = ARCHIVE_POSIX_LOCAL_PATH_RE.sub("<redacted-local-path>", text)
    return text.replace("\ufffd", "<replacement-char>")


def _archive_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    return _sanitize_archive_text(text)


def _archive_text_bytes(path: Path) -> bytes | None:
    archive_text = _archive_text(path)
    if archive_text is None:
        return None
    return archive_text.encode("utf-8")


def _receipt_approval_request_problems(
    section: dict[str, Any],
    receipt: dict[str, Any],
    receipt_path: Path,
) -> list[str]:
    problems: list[str] = []
    artifact = receipt.get("artifact") if isinstance(receipt.get("artifact"), dict) else {}
    final_gate = receipt.get("final_gate") if isinstance(receipt.get("final_gate"), dict) else {}
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
    if section.get("receipt_path") != str(receipt_path):
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


def _receipt_check(
    receipt: dict[str, Any] | None,
    error: str | None,
    receipt_path: Path,
) -> EvidencePackCheck:
    if error:
        return EvidencePackCheck("release_receipt", "failed", error=error)
    assert receipt is not None
    status = str(receipt.get("status") or "")
    checks = receipt.get("checks")
    problems: list[str] = []
    if status != "created":
        problems.append(f"expected receipt status created, got {status}")
    if not isinstance(checks, list) or not checks:
        problems.append("receipt checks are missing")
    elif any(not isinstance(check, dict) or check.get("status") != "passed" for check in checks):
        failed = [
            str(check.get("name") or "receipt_check")
            for check in checks
            if not isinstance(check, dict) or check.get("status") != "passed"
        ]
        problems.append(f"receipt contains failed checks: {', '.join(failed)}")
    approval_request = receipt.get("approval_request")
    if not isinstance(approval_request, dict):
        problems.append("receipt missing approval_request summary")
        approval_request = {}
    else:
        problems.extend(_receipt_approval_request_problems(approval_request, receipt, receipt_path))
    commands = approval_request.get("exact_staging_commands") if isinstance(approval_request, dict) else None
    return EvidencePackCheck(
        "release_receipt",
        "passed" if not problems else "failed",
        details={
            "status": status,
            "check_count": len(checks) if isinstance(checks, list) else 0,
            "approval_required_before_staging": approval_request.get("approval_required_before_staging"),
            "full_parity_claimed": approval_request.get("full_parity_claimed"),
            "staging_command_count": len(commands) if isinstance(commands, list) else 0,
        },
        error="; ".join(problems) if problems else None,
    )


def _required_files_check(files: list[EvidencePackFile], missing: list[str]) -> EvidencePackCheck:
    return EvidencePackCheck(
        "required_files",
        "passed" if not missing else "failed",
        details={"file_count": len(files), "missing": missing},
        error=None if not missing else "required evidence files are missing",
    )


def _artifact_consistency_check(receipt: dict[str, Any] | None, files: list[EvidencePackFile]) -> EvidencePackCheck:
    if receipt is None:
        return EvidencePackCheck("artifact_consistency", "failed", error="receipt missing")
    artifact = receipt.get("artifact") if isinstance(receipt.get("artifact"), dict) else {}
    path = _resolve_path(artifact.get("path"))
    expected_sha = str(artifact.get("sha256") or "")
    if path is None:
        return EvidencePackCheck("artifact_consistency", "failed", error="receipt artifact path missing")
    matching = next((item for item in files if Path(item.path) == path), None)
    problems: list[str] = []
    if matching is None:
        problems.append("source bundle artifact is not included in evidence pack")
    elif matching.sha256 != expected_sha:
        problems.append("source bundle artifact sha256 does not match receipt")
    return EvidencePackCheck(
        "artifact_consistency",
        "passed" if not problems else "failed",
        details={"artifact_path": str(path), "expected_sha256": expected_sha},
        error="; ".join(problems) if problems else None,
    )


def _file_by_archive_path(files: list[EvidencePackFile], archive_path: str) -> EvidencePackFile | None:
    return next((item for item in files if item.archive_path == archive_path), None)


def _owner_gate_runner_evidence_check(files: list[EvidencePackFile]) -> EvidencePackCheck:
    runner_file = _file_by_archive_path(files, OWNER_GATE_RUNNER_ARCHIVE_PATH)
    env_file = _file_by_archive_path(files, OWNER_ENV_TEMPLATE_ARCHIVE_PATH)
    problems: list[str] = []
    details: dict[str, Any] = {
        "runner_report": OWNER_GATE_RUNNER_ARCHIVE_PATH,
        "env_file": OWNER_ENV_TEMPLATE_ARCHIVE_PATH,
    }

    if runner_file is None:
        problems.append("owner gate runner report is missing from evidence pack")
    if env_file is None:
        problems.append("owner env template file is missing from evidence pack")
    if runner_file is None:
        return EvidencePackCheck(
            "owner_gate_runner_evidence",
            "failed",
            details=details,
            error="; ".join(problems),
        )

    payload, error = _read_json(Path(runner_file.path))
    if error or payload is None:
        problems.append("owner gate runner report is not valid JSON")
        return EvidencePackCheck(
            "owner_gate_runner_evidence",
            "failed",
            details=details,
            error="; ".join(problems),
        )

    loaded_env_names = payload.get("loaded_env_names")
    owner_gate_env_names = payload.get("owner_gate_env_names")
    missing_env_groups = payload.get("missing_env_groups")
    details.update(
        {
            "status": payload.get("status"),
            "selected_gate": payload.get("selected_gate"),
            "dry_run": payload.get("dry_run"),
            "reported_env_file": payload.get("env_file"),
            "loaded_env_name_count": len(loaded_env_names) if isinstance(loaded_env_names, list) else None,
            "owner_gate_env_name_count": len(owner_gate_env_names) if isinstance(owner_gate_env_names, list) else None,
            "missing_env_group_count": len(missing_env_groups) if isinstance(missing_env_groups, list) else None,
        }
    )
    if payload.get("status") not in {"planned", "passed"}:
        problems.append("owner gate runner status is not planned or passed")
    if payload.get("selected_gate") != "all":
        problems.append("owner gate runner selected_gate must be all")
    if payload.get("dry_run") is not True:
        problems.append("owner gate runner must be a dry-run report")
    if payload.get("env_file") != OWNER_ENV_TEMPLATE_ARCHIVE_PATH:
        problems.append(f"owner gate runner env_file must be {OWNER_ENV_TEMPLATE_ARCHIVE_PATH}")
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
        first_step = steps[0] if isinstance(steps[0], dict) else {}
        command = first_step.get("command") if isinstance(first_step, dict) else []
        if not isinstance(command, list):
            problems.append("owner gate runner first command is missing")
        else:
            for token in OWNER_GATE_RUNNER_REQUIRED_ALL_COMMAND_TOKENS:
                if token not in command:
                    problems.append(f"owner gate runner all-gate command missing token: {token}")

    return EvidencePackCheck(
        "owner_gate_runner_evidence",
        "passed" if not problems else "failed",
        details=details,
        error="; ".join(problems) if problems else None,
    )


def _is_env_group_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return all(
        isinstance(group, list)
        and all(isinstance(item, str) and item.strip() for item in group)
        for group in value
    )


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _freshness_check(
    receipt_path: Path,
    receipt: dict[str, Any] | None,
    files: list[EvidencePackFile],
) -> EvidencePackCheck:
    if receipt is None:
        return EvidencePackCheck("evidence_pack_freshness", "failed", error="receipt missing")

    receipt_generated_at = receipt.get("generated_at")
    receipt_time = _parse_report_time(receipt_generated_at)
    missing_or_invalid: list[dict[str, Any]] = []
    invalid_json: list[dict[str, str]] = []
    stale_reports: list[dict[str, Any]] = []
    stale_validators: list[dict[str, Any]] = []
    receipt_validator_reports: list[dict[str, Any]] = []
    checked = 0
    now = datetime.now(UTC)

    for item in files:
        path = Path(item.path)
        if path.suffix.lower() != ".json" or _same_path(path, receipt_path):
            continue
        payload, error = _read_json(path)
        if error or payload is None:
            invalid_json.append({"path": item.archive_path, "error": "invalid JSON evidence report"})
            continue
        report_generated_at = payload.get("generated_at")
        report_time = _parse_report_time(report_generated_at)
        if report_time is None:
            missing_or_invalid.append({"path": item.archive_path, "generated_at": report_generated_at})
            continue
        if _is_future_report_time(report_time, now=now):
            missing_or_invalid.append(
                {
                    "path": item.archive_path,
                    "generated_at": report_generated_at,
                    "error": "generated_at is in the future",
                }
            )
            continue
        checked += 1
        if item.archive_path in RECEIPT_VALIDATOR_REPORTS:
            if receipt_time is not None:
                receipt_validator_reports.append(
                    {
                        "path": item.archive_path,
                        "report_generated_at": report_generated_at,
                        "receipt_generated_at": receipt_generated_at,
                        "accepted": True,
                        "reason": "report validates receipt/evidence freshness and can be regenerated before or after receipt",
                    }
                )
        elif receipt_time is not None and receipt_time < report_time:
            stale_reports.append(
                {
                    "path": item.archive_path,
                    "report_generated_at": report_generated_at,
                    "receipt_generated_at": receipt_generated_at,
                }
            )

    problems: list[str] = []
    if receipt_time is None:
        problems.append("receipt generated_at is missing or invalid")
    elif _is_future_report_time(receipt_time, now=now):
        problems.append("receipt generated_at is in the future")
    if invalid_json:
        problems.append("packed JSON evidence reports are invalid")
    if missing_or_invalid:
        problems.append("packed JSON evidence reports are missing valid generated_at timestamps")
    if stale_reports:
        problems.append("release receipt is older than packed JSON evidence reports")

    return EvidencePackCheck(
        "evidence_pack_freshness",
        "passed" if not problems else "failed",
        details={
            "receipt_generated_at": receipt_generated_at,
            "checked_json_reports": checked,
            "invalid_json_reports": invalid_json,
            "missing_or_invalid_generated_at_reports": missing_or_invalid,
            "stale_reports": stale_reports,
            "stale_validator_reports": stale_validators,
            "receipt_validator_reports": receipt_validator_reports,
        },
        error="; ".join(problems) if problems else None,
    )


def _create_zip(files: list[EvidencePackFile], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            path = Path(item.path)
            archive_bytes = _archive_text_bytes(path)
            if archive_bytes is None:
                archive.write(path, arcname=item.archive_path)
            else:
                archive.writestr(item.archive_path, archive_bytes)


def build_evidence_pack(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    output_path: Path | None = None,
    extra_reports: Iterable[Path] = (),
    dry_run: bool = False,
) -> EvidencePackReport:
    receipt, receipt_error = _read_json(receipt_path)
    inputs = _pack_inputs(receipt_path, receipt or {}, extra_reports)
    files, missing = _inspect_files(inputs)
    checks = [
        _receipt_check(receipt, receipt_error, receipt_path),
        _required_files_check(files, missing),
        _artifact_consistency_check(receipt, files),
        _owner_gate_runner_evidence_check(files),
        _freshness_check(receipt_path, receipt, files),
        _security_scan(files),
        _privacy_scan(files),
    ]
    destination = output_path if output_path is not None else _default_pack_path()
    if not dry_run and all(check.status == "passed" for check in checks):
        _create_zip(files, destination)
        pack_sha = _sha256_file(destination)
    else:
        pack_sha = _sha256_file(destination) if destination.exists() else None
    status = "planned" if dry_run and all(check.status == "passed" for check in checks) else "created" if all(check.status == "passed" for check in checks) else "failed"
    return EvidencePackReport(
        status=status,
        generated_at=_utc_now(),
        receipt_path=str(receipt_path),
        output_path=str(destination) if not dry_run else None,
        pack_sha256=pack_sha,
        file_count=len(files),
        files=files,
        checks=checks,
        next_commands=[
            "Archive the evidence pack zip outside source control.",
            "Give the evidence pack and source bundle SHA-256 sidecar to the release owner.",
            "Complete real owner gates before running rc_final_gate.py --require-ready-to-tag.",
        ],
    )


def write_report(report: EvidencePackReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the X-Agent commercial RC evidence pack")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--extra-report", type=Path, action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_evidence_pack(
        receipt_path=args.receipt,
        output_path=args.output,
        extra_reports=args.extra_report,
        dry_run=args.dry_run,
    )
    write_report(report, args.report)
    print(f"RC evidence pack status: {report.status}")
    if report.output_path:
        print(f"Evidence pack written to {report.output_path}")
    if report.pack_sha256:
        print(f"Evidence pack sha256: {report.pack_sha256}")
    print(f"Evidence files: {report.file_count}")
    print(f"Report written to {args.report}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status in {"planned", "created"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
