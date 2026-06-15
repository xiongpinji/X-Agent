from __future__ import annotations

import json
import base64
from pathlib import Path

import scripts.rc_secrets_gate as gate
from scripts.generate_secrets import generate_all_secrets
from scripts.rc_secrets_gate import (
    check_required_fields,
    check_artifact_secret_scan,
    check_prohibited_secret_artifacts,
    check_release_audit_secret_scan,
    check_secret_strength,
    check_uniqueness,
    run_secrets_gate,
)


def _write_release_audit(path: Path, *, status: str = "passed", secret_findings: list[dict[str, object]] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": status,
                "candidate_count": 90,
                "secret_findings": [] if secret_findings is None else secret_findings,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_source_bundle(
    path: Path,
    *,
    status: str = "created",
    file_count: int = 90,
    output_path: str | None = None,
    generated_at: str = "2026-06-05T10:00:00Z",
    files: list[dict[str, object]] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path = output_path or str(path.parent.parent / "release" / "bundle.zip")
    path.write_text(
        json.dumps(
            {
                "status": status,
                "generated_at": generated_at,
                "dry_run": False,
                "output_path": bundle_path,
                "file_count": file_count,
                "files": files if files is not None else [{"path": "README.md", "size_bytes": 6, "sha256": "a" * 64}],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_artifact_integrity(
    path: Path,
    *,
    source_bundle_path: Path,
    status: str = "passed",
    file_count: int = 90,
    output_path: str | None = None,
    generated_at: str = "2026-06-05T10:01:00Z",
    zip_scan: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path = output_path or str(path.parent.parent / "release" / "bundle.zip")
    if zip_scan is None:
        zip_scan = {
            "name": "zip_security_scan",
            "status": "passed",
            "details": {
                "scanned_text_files": 12,
                "secret_findings": [],
                "excluded_reference_findings": [],
                "local_path_findings": [],
            },
        }
    path.write_text(
        json.dumps(
            {
                "status": status,
                "generated_at": generated_at,
                "source_bundle_report": str(source_bundle_path),
                "artifact_path": bundle_path,
                "artifact_sha256": "b" * 64,
                "artifact_size_bytes": 1234,
                "file_count": file_count,
                "checks": [
                    {"name": "source_bundle_report", "status": "passed"},
                    {"name": "artifact_file", "status": "passed"},
                    {"name": "zip_contents", "status": "passed"},
                    zip_scan,
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_clean_artifact_reports(tmp_path: Path) -> tuple[Path, Path]:
    source = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json")
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
    )
    return artifact, source


def test_release_audit_secret_scan_accepts_clean_report(tmp_path: Path) -> None:
    audit = _write_release_audit(tmp_path / "reports" / "rc-release-audit.json")

    check = check_release_audit_secret_scan(audit)

    assert check.status == "passed"
    assert check.details["secret_finding_count"] == 0


def test_release_audit_secret_scan_fails_secret_findings(tmp_path: Path) -> None:
    audit = _write_release_audit(
        tmp_path / "reports" / "rc-release-audit.json",
        secret_findings=[{"path": "config/example.env", "pattern": "secret"}],
    )

    check = check_release_audit_secret_scan(audit)

    assert check.status == "failed"
    assert check.details["secret_finding_count"] == 1


def test_artifact_secret_scan_accepts_clean_report(tmp_path: Path) -> None:
    artifact, source = _write_clean_artifact_reports(tmp_path)

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "passed"
    assert check.details["secret_finding_count"] == 0
    assert check.details["excluded_reference_finding_count"] == 0
    assert check.details["scanned_text_files"] == 12


def test_artifact_secret_scan_fails_zip_secret_findings(tmp_path: Path) -> None:
    source = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json")
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
        zip_scan={
            "name": "zip_security_scan",
            "status": "failed",
            "details": {
                "scanned_text_files": 12,
                "secret_findings": [{"path": "config/production.env", "sample": "xage..."}],
                "excluded_reference_findings": [],
                "local_path_findings": [],
            },
        },
    )

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "failed"
    assert check.details["secret_finding_count"] == 1
    assert any("secret findings" in failure for failure in check.details["failures"])


def test_artifact_secret_scan_fails_file_count_mismatch(tmp_path: Path) -> None:
    source = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json", file_count=90)
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
        file_count=91,
    )

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "failed"
    assert "file_count mismatch" in str(check.details["failures"])


def test_artifact_secret_scan_fails_missing_zip_security_scan(tmp_path: Path) -> None:
    source = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json")
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
        zip_scan={"name": "zip_contents", "status": "passed", "details": {}},
    )

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "failed"
    assert "missing zip_security_scan" in str(check.details["failures"])


def test_artifact_secret_scan_fails_non_list_secret_findings(tmp_path: Path) -> None:
    source = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json")
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
        zip_scan={
            "name": "zip_security_scan",
            "status": "passed",
            "details": {
                "scanned_text_files": 12,
                "secret_findings": "none",
                "excluded_reference_findings": [],
                "local_path_findings": [],
            },
        },
    )

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "failed"
    assert "secret_findings must be a list" in str(check.details["failures"])


def test_artifact_secret_scan_fails_local_path_findings(tmp_path: Path) -> None:
    source = _write_source_bundle(tmp_path / "reports" / "rc-source-bundle.json")
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
        zip_scan={
            "name": "zip_security_scan",
            "status": "failed",
            "details": {
                "scanned_text_files": 12,
                "secret_findings": [],
                "excluded_reference_findings": [],
                "local_path_findings": [{"path": "docs/handoff.txt", "pattern": "windows_user_profile"}],
            },
        },
    )

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "failed"
    assert check.details["local_path_finding_count"] == 1
    assert "local path references" in str(check.details["failures"])


def test_artifact_secret_scan_fails_stale_artifact_report(tmp_path: Path) -> None:
    source = _write_source_bundle(
        tmp_path / "reports" / "rc-source-bundle.json",
        generated_at="2026-06-05T10:05:00Z",
    )
    artifact = _write_artifact_integrity(
        tmp_path / "reports" / "rc-artifact-integrity-gate.json",
        source_bundle_path=source,
        generated_at="2026-06-05T10:04:59Z",
    )

    check = check_artifact_secret_scan(artifact, source)

    assert check.status == "failed"
    assert "older than the source bundle" in str(check.details["failures"])


def test_prohibited_secret_artifacts_accepts_clean_source_bundle(tmp_path: Path) -> None:
    source = _write_source_bundle(
        tmp_path / "reports" / "rc-source-bundle.json",
        files=[
            {"path": "README.md", "size_bytes": 6, "sha256": "a" * 64},
            {"path": "config/.env.example", "size_bytes": 6, "sha256": "b" * 64},
            {"path": "config/runtime.env.template", "size_bytes": 6, "sha256": "c" * 64},
        ],
    )

    check = check_prohibited_secret_artifacts(source)

    assert check.status == "passed"
    assert check.details["prohibited_paths"] == []


def test_prohibited_secret_artifacts_rejects_secret_bearing_paths(tmp_path: Path) -> None:
    source = _write_source_bundle(
        tmp_path / "reports" / "rc-source-bundle.json",
        files=[
            {"path": ".env.production", "size_bytes": 6, "sha256": "a" * 64},
            {"path": "certs/server.pem", "size_bytes": 6, "sha256": "b" * 64},
            {"path": "secrets/customer-notes.txt", "size_bytes": 6, "sha256": "c" * 64},
        ],
    )

    check = check_prohibited_secret_artifacts(source)

    assert check.status == "failed"
    assert check.details["prohibited_paths"] == [
        ".env.production",
        "certs/server.pem",
        "secrets/customer-notes.txt",
    ]


def test_secret_strength_rejects_weak_shapes() -> None:
    check = check_secret_strength(
        {
            "JWT_SECRET": "short",
            "ENCRYPTION_KEY": "not-base64",
            "AUDIT_HMAC_SECRET": "abc",
            "BOOTSTRAP_API_KEY": "wrong-prefix",
            "S3_ACCESS_KEY": "short",
            "S3_SECRET_KEY": "short",
            "NEO4J_PASSWORD": "short",
        }
    )

    assert check.status == "failed"
    assert len(check.details["failures"]) == 7


def test_default_generated_secrets_match_commercial_rc_contract() -> None:
    generated = generate_all_secrets()

    required = set(gate.REQUIRED_FIELDS)
    assert set(generated) == required
    assert check_required_fields(generated).status == "passed"
    assert check_secret_strength(generated).status == "passed"


def test_optional_generated_secrets_are_explicitly_opted_in() -> None:
    generated = generate_all_secrets(include_optional=True)

    assert gate.REQUIRED_FIELDS <= set(generated)
    assert {"DB_PASSWORD", "REDIS_PASSWORD", "QDRANT_API_KEY"} <= set(generated)
    assert check_secret_strength(generated).status == "passed"


def test_uniqueness_rejects_duplicate_generated_values() -> None:
    check = check_uniqueness({"JWT_SECRET": "same", "ENCRYPTION_KEY": "same"})

    assert check.status == "failed"
    assert check.details["duplicate_count"] == 1


def test_secrets_gate_passes_without_leaking_values(monkeypatch, tmp_path: Path) -> None:
    audit = _write_release_audit(tmp_path / "reports" / "rc-release-audit.json")
    artifact, source = _write_clean_artifact_reports(tmp_path)
    generated = {
        "JWT_SECRET": "J" * 64,
        "ENCRYPTION_KEY": base64.b64encode(b"1" * 32).decode(),
        "AUDIT_HMAC_SECRET": "a" * 64,
        "BOOTSTRAP_API_KEY": "xagent-" + ("A" * 64),
        "S3_ACCESS_KEY": "B" * 24,
        "S3_SECRET_KEY": "C" * 48,
        "NEO4J_PASSWORD": "D" * 32,
    }
    monkeypatch.setattr(gate, "generate_all_secrets", lambda: generated)

    report = run_secrets_gate(audit, artifact, source)
    payload_text = json.dumps(report.to_dict())

    assert report.status == "passed"
    assert report.generated_value_count == 7
    assert report.unique_value_count == 7
    assert {shape.name for shape in report.secret_shapes} == gate.REQUIRED_FIELDS
    assert "Generated secret values are validated in memory" in report.non_leakage_note

    for value in generated.values():
        assert value not in payload_text


def test_secrets_gate_fails_when_required_field_missing(monkeypatch, tmp_path: Path) -> None:
    audit = _write_release_audit(tmp_path / "reports" / "rc-release-audit.json")
    artifact, source = _write_clean_artifact_reports(tmp_path)
    generated = gate.generate_all_secrets()
    generated.pop("NEO4J_PASSWORD")
    monkeypatch.setattr(gate, "generate_all_secrets", lambda: generated)

    report = run_secrets_gate(audit, artifact, source)

    assert report.status == "failed"
    assert any(check.name == "required_fields" and check.status == "failed" for check in report.checks)
