#!/usr/bin/env python3
"""Validate the created commercial RC source-bundle artifact.

This gate is intentionally read-only. It verifies that the source-bundle report
points to a real zip archive, the archive contents match the reported manifest
payload exactly, and every archived file has the expected size and SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.rc_release_audit import (
    EXCLUDED_REFERENCE_PATTERNS,
    EXCLUDED_REFERENCE_SCAN_EXEMPT,
    SECRET_PATTERNS,
    TEXT_SUFFIXES,
    _is_allowed_secret_match_sample,
    _redact,
    is_excluded,
)
from scripts.rc_source_bundle import ROOT

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_OUTPUT = REPORT_DIR / "rc-artifact-integrity-gate.json"

LOCAL_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("windows_user_profile", re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/:\s]+")),
    ("posix_user_home", re.compile(r"(?i)/(?:home|Users)/[A-Za-z0-9._-]+/")),
)


@dataclass(frozen=True)
class ArtifactIntegrityCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ArtifactIntegrityReport:
    status: str
    generated_at: str
    source_bundle_report: str
    artifact_path: str | None
    artifact_sha256: str | None
    artifact_size_bytes: int | None
    file_count: int
    checks: list[ArtifactIntegrityCheck]
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
        return None, "source bundle report missing"
    except json.JSONDecodeError as exc:
        return None, f"invalid source bundle report JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "source bundle report is not a JSON object"
    return payload, None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def _reported_files(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for item in payload.get("files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").replace("\\", "/")
        if path:
            files[path] = item
    return files


def _unsafe_archive_name(name: str) -> bool:
    parts = [part for part in name.replace("\\", "/").split("/") if part]
    return name.startswith("/") or ":" in parts[0] or ".." in parts


def check_source_bundle_report(payload: dict[str, Any] | None, error: str | None) -> ArtifactIntegrityCheck:
    if error:
        return ArtifactIntegrityCheck("source_bundle_report", "failed", error=error)
    assert payload is not None
    status = payload.get("status")
    dry_run = payload.get("dry_run")
    output_path = payload.get("output_path")
    failures: list[str] = []
    if status != "created":
        failures.append(f"expected source bundle status created, got {status}")
    if dry_run is not False:
        failures.append("source bundle report must come from --create, not dry-run")
    if not output_path:
        failures.append("source bundle report has no output_path")
    return ArtifactIntegrityCheck(
        "source_bundle_report",
        "passed" if not failures else "failed",
        details={
            "report_status": status,
            "dry_run": dry_run,
            "output_path": output_path,
            "file_count": payload.get("file_count"),
            "errors": payload.get("errors", []),
            "failures": failures,
        },
    )


def check_artifact_file(path: Path | None) -> ArtifactIntegrityCheck:
    if path is None:
        return ArtifactIntegrityCheck("artifact_file", "failed", error="artifact output_path missing")
    if not path.exists() or not path.is_file():
        return ArtifactIntegrityCheck("artifact_file", "failed", details={"path": str(path)}, error="artifact zip missing")
    if path.suffix.lower() != ".zip":
        return ArtifactIntegrityCheck("artifact_file", "failed", details={"path": str(path)}, error="artifact is not a zip file")
    return ArtifactIntegrityCheck(
        "artifact_file",
        "passed",
        details={"path": str(path), "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)},
    )


def check_zip_contents(path: Path | None, payload: dict[str, Any] | None) -> ArtifactIntegrityCheck:
    if path is None or payload is None:
        return ArtifactIntegrityCheck("zip_contents", "failed", error="artifact path or source bundle report missing")
    expected = _reported_files(payload)
    try:
        with zipfile.ZipFile(path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename.replace("\\", "/") for info in infos]
            actual = {info.filename.replace("\\", "/"): info for info in infos}
            mismatches: list[str] = []
            if sorted(actual) != sorted(expected):
                missing = sorted(set(expected).difference(actual))
                extra = sorted(set(actual).difference(expected))
                mismatches.append(f"zip file list mismatch: missing={missing}, extra={extra}")
            unsafe = sorted(name for name in actual if _unsafe_archive_name(name))
            if unsafe:
                mismatches.append(f"zip contains unsafe archive names: {unsafe}")
            excluded = sorted(name for name in actual if is_excluded(name) or name.startswith(".xagent_runtime/"))
            if excluded:
                mismatches.append(f"zip contains excluded paths: {excluded}")
            for name, reported in expected.items():
                info = actual.get(name)
                if info is None:
                    continue
                data = archive.read(info)
                if len(data) != int(reported.get("size_bytes", -1)):
                    mismatches.append(f"{name}: size mismatch")
                if _sha256_bytes(data) != str(reported.get("sha256") or ""):
                    mismatches.append(f"{name}: sha256 mismatch")
    except zipfile.BadZipFile as exc:
        return ArtifactIntegrityCheck("zip_contents", "failed", details={"path": str(path)}, error=f"bad zip file: {exc}")
    return ArtifactIntegrityCheck(
        "zip_contents",
        "passed" if not mismatches else "failed",
        details={"entry_count": len(names), "reported_count": len(expected), "mismatches": mismatches},
    )


def check_workspace_contents(payload: dict[str, Any] | None, root: Path = ROOT) -> ArtifactIntegrityCheck:
    if payload is None:
        return ArtifactIntegrityCheck("workspace_contents", "failed", error="source bundle report missing")
    expected = _reported_files(payload)
    mismatches: list[str] = []
    for name, reported in expected.items():
        if _unsafe_archive_name(name) or is_excluded(name) or name.startswith(".xagent_runtime/"):
            mismatches.append(f"{name}: unsafe or excluded path")
            continue
        path = root / name
        if not path.exists() or not path.is_file():
            mismatches.append(f"{name}: workspace file missing")
            continue
        if path.stat().st_size != int(reported.get("size_bytes", -1)):
            mismatches.append(f"{name}: workspace size mismatch")
        if _sha256_file(path) != str(reported.get("sha256") or ""):
            mismatches.append(f"{name}: workspace sha256 mismatch")
    return ArtifactIntegrityCheck(
        "workspace_contents",
        "passed" if not mismatches else "failed",
        details={"reported_count": len(expected), "mismatches": mismatches},
        error=None if not mismatches else "source bundle report does not match current workspace files",
    )


def check_zip_security_scan(path: Path | None) -> ArtifactIntegrityCheck:
    if path is None:
        return ArtifactIntegrityCheck("zip_security_scan", "failed", error="artifact path missing")
    secret_findings: list[dict[str, Any]] = []
    excluded_reference_findings: list[dict[str, Any]] = []
    local_path_findings: list[dict[str, Any]] = []
    scanned_files = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                suffix = Path(name).suffix.lower()
                if suffix not in TEXT_SUFFIXES:
                    continue
                try:
                    text = archive.read(info).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                scanned_files += 1
                for line_number, line in enumerate(text.splitlines(), start=1):
                    for pattern in SECRET_PATTERNS:
                        for match in pattern.finditer(line):
                            sample = match.group(1) if match.groups() else match.group(0)
                            if _is_allowed_secret_match_sample(sample):
                                continue
                            secret_findings.append(
                                {
                                    "path": name,
                                    "line": line_number,
                                    "pattern": pattern.pattern,
                                    "sample": _redact(sample),
                                }
                            )
                    for area, patterns in EXCLUDED_REFERENCE_PATTERNS.items():
                        if name in EXCLUDED_REFERENCE_SCAN_EXEMPT:
                            continue
                        if any(pattern in line for pattern in patterns):
                            excluded_reference_findings.append(
                                {
                                    "path": name,
                                    "line": line_number,
                                    "excluded_area": area,
                                    "sample": line.strip()[:160],
                                }
                            )
                    for pattern_name, pattern in LOCAL_PATH_PATTERNS:
                        for match in pattern.finditer(line):
                            local_path_findings.append(
                                {
                                    "path": name,
                                    "line": line_number,
                                    "pattern": pattern_name,
                                    "sample": _redact(match.group(0)),
                                }
                            )
    except zipfile.BadZipFile as exc:
        return ArtifactIntegrityCheck("zip_security_scan", "failed", details={"path": str(path)}, error=f"bad zip file: {exc}")
    status = "passed" if not secret_findings and not excluded_reference_findings and not local_path_findings else "failed"
    return ArtifactIntegrityCheck(
        "zip_security_scan",
        status,
        details={
            "scanned_text_files": scanned_files,
            "secret_findings": secret_findings,
            "excluded_reference_findings": excluded_reference_findings,
            "local_path_findings": local_path_findings,
        },
        error=None
        if status == "passed"
        else "zip contains secret-like findings, excluded-area references, or local path references",
    )


def run_artifact_integrity_gate(source_bundle_report: Path = DEFAULT_SOURCE_BUNDLE, *, root: Path = ROOT) -> ArtifactIntegrityReport:
    payload, error = _read_json(source_bundle_report)
    artifact = _artifact_path((payload or {}).get("output_path"))
    checks = [
        check_source_bundle_report(payload, error),
        check_artifact_file(artifact),
        check_zip_contents(artifact, payload),
        check_workspace_contents(payload, root=root),
        check_zip_security_scan(artifact),
    ]
    artifact_sha256 = _sha256_file(artifact) if artifact and artifact.exists() and artifact.is_file() else None
    artifact_size = artifact.stat().st_size if artifact and artifact.exists() and artifact.is_file() else None
    return ArtifactIntegrityReport(
        status="passed" if all(check.status == "passed" for check in checks) else "failed",
        generated_at=_utc_now(),
        source_bundle_report=str(source_bundle_report),
        artifact_path=str(artifact) if artifact else None,
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=artifact_size,
        file_count=len(_reported_files(payload or {})),
        checks=checks,
        next_commands=[
            "Run python scripts/rc_source_bundle.py --create after owner review to generate the zip artifact.",
            "Archive .xagent_runtime/release/*.zip and its SHA-256 outside source control.",
            "Run python scripts/rc_final_gate.py after artifact integrity passes.",
        ],
    )


def write_report(report: ArtifactIntegrityReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the commercial RC source-bundle artifact integrity")
    parser.add_argument("--source-bundle-report", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_artifact_integrity_gate(args.source_bundle_report)
    write_report(report, args.output)
    print(f"RC artifact integrity gate status: {report.status}")
    print(f"Report written to {args.output}")
    if report.artifact_path:
        print(f"Artifact: {report.artifact_path}")
    if report.artifact_sha256:
        print(f"Artifact sha256: {report.artifact_sha256}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
