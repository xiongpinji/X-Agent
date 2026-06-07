from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from scripts.rc_artifact_integrity_gate import run_artifact_integrity_gate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_report(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _windows_user_path(*parts: str) -> str:
    return "C:" + "\\Users\\" + "canqu" + "\\" + "\\".join(parts)


def test_artifact_integrity_gate_rejects_dry_run_source_bundle(tmp_path: Path) -> None:
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {"status": "planned", "dry_run": True, "output_path": None, "file_count": 0, "files": []},
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    assert any(check.name == "source_bundle_report" and check.status == "failed" for check in report.checks)


def test_artifact_integrity_gate_accepts_matching_zip(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    files = {
        "README.md": b"readme",
        "scripts/rc_final_gate.py": b"print('gate')",
    }
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    with zipfile.ZipFile(artifact, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": len(files),
            "files": [
                {"path": name, "size_bytes": len(data), "sha256": _sha256(data)}
                for name, data in files.items()
            ],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "passed"
    assert report.artifact_sha256 == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert report.file_count == 2
    workspace_check = next(check for check in report.checks if check.name == "workspace_contents")
    assert workspace_check.status == "passed"


def test_artifact_integrity_gate_rejects_tampered_zip_entry(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    original = b"readme"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("README.md", b"tampered")
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": 1,
            "files": [{"path": "README.md", "size_bytes": len(original), "sha256": _sha256(original)}],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    zip_check = next(check for check in report.checks if check.name == "zip_contents")
    assert any("README.md" in mismatch for mismatch in zip_check.details["mismatches"])


def test_artifact_integrity_gate_rejects_workspace_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    original = b"readme"
    current = b"readme changed after bundle"
    (tmp_path / "README.md").write_bytes(current)
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("README.md", original)
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": 1,
            "files": [{"path": "README.md", "size_bytes": len(original), "sha256": _sha256(original)}],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    workspace_check = next(check for check in report.checks if check.name == "workspace_contents")
    assert workspace_check.status == "failed"
    assert any("README.md" in mismatch for mismatch in workspace_check.details["mismatches"])


def test_artifact_integrity_gate_rejects_excluded_zip_entry(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    data = b"local"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr(".agents/config.toml", data)
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": 1,
            "files": [{"path": ".agents/config.toml", "size_bytes": len(data), "sha256": _sha256(data)}],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    zip_check = next(check for check in report.checks if check.name == "zip_contents")
    assert zip_check.details["mismatches"]


def test_artifact_integrity_gate_rejects_secret_like_zip_content(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    secret_sample = "xagent-" + "secretvalue12345678901234567890"
    data = f'XAGENT_BOOTSTRAP_API_KEY="{secret_sample}"\n'.encode("utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "production.env").write_bytes(data)
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("config/production.env", data)
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": 1,
            "files": [{"path": "config/production.env", "size_bytes": len(data), "sha256": _sha256(data)}],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    scan_check = next(check for check in report.checks if check.name == "zip_security_scan")
    assert scan_check.details["secret_findings"][0]["sample"].startswith("xage")


def test_artifact_integrity_gate_rejects_excluded_reference_zip_content(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    module_name = "creative" + "_studio"
    data = f"from backend.app.api.{module_name} import router\n".encode("utf-8")
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_bytes(data)
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("backend/app/main.py", data)
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": 1,
            "files": [{"path": "backend/app/main.py", "size_bytes": len(data), "sha256": _sha256(data)}],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    scan_check = next(check for check in report.checks if check.name == "zip_security_scan")
    assert scan_check.details["excluded_reference_findings"][0]["excluded_area"] == "creative_studio"


def test_artifact_integrity_gate_rejects_local_path_zip_content(tmp_path: Path) -> None:
    artifact = tmp_path / "release" / "bundle.zip"
    artifact.parent.mkdir()
    data = f"venv={_windows_user_path('AppData', 'Local', 'hermes', 'hermes-agent', 'venv')}\n".encode("utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "handoff.txt").write_bytes(data)
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("docs/handoff.txt", data)
    report_path = _write_report(
        tmp_path / "reports" / "rc-source-bundle.json",
        {
            "status": "created",
            "dry_run": False,
            "output_path": str(artifact),
            "file_count": 1,
            "files": [{"path": "docs/handoff.txt", "size_bytes": len(data), "sha256": _sha256(data)}],
        },
    )

    report = run_artifact_integrity_gate(report_path, root=tmp_path)

    assert report.status == "failed"
    scan_check = next(check for check in report.checks if check.name == "zip_security_scan")
    assert scan_check.details["local_path_findings"][0]["pattern"] == "windows_user_profile"
