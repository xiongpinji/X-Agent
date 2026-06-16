from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.rc_install_release_gate as gate
from scripts.rc_install_release_gate import (
    InstallReleaseCheck,
    check_release_artifact_consistency,
    check_report_status,
    run_install_release_gate,
)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_report_status_accepts_expected_status(tmp_path: Path) -> None:
    report = _write_json(tmp_path / "report.json", {"status": "planned", "file_count": 3, "errors": []})

    check = check_report_status(report, name="source_bundle_report", expected={"planned", "created"})

    assert check.status == "passed"
    assert check.details["file_count"] == 3


def test_report_status_fails_on_missing_report(tmp_path: Path) -> None:
    check = check_report_status(tmp_path / "missing.json", name="source_bundle_report", expected={"planned"})

    assert check.status == "failed"
    assert check.error == "report missing"


def test_install_release_gate_aggregates_checks(tmp_path: Path, monkeypatch) -> None:
    artifact_path = tmp_path / "release" / "bundle.zip"
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 10,
            "output_path": str(artifact_path),
            "files": [
                {"path": "scripts/install-xagent.ps1"},
                {"path": "scripts/install-xagent.sh"},
                {"path": "scripts/xagent_doctor.py"},
            ],
            "errors": [],
        },
    )
    artifact = _write_json(tmp_path / "artifact.json", {"status": "passed", "file_count": 10, "artifact_path": str(artifact_path), "checks": []})
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 10, "errors": []})

    monkeypatch.setattr(
        gate,
        "check_windows_installer_dry_run",
        lambda timeout_seconds=90.0: InstallReleaseCheck("windows_installer_dry_run", "passed"),
    )
    monkeypatch.setattr(
        gate,
        "check_posix_installer_dry_run",
        lambda timeout_seconds=90.0: InstallReleaseCheck("posix_installer_dry_run", "passed"),
    )
    monkeypatch.setattr(
        gate,
        "check_doctor",
        lambda timeout_seconds=90.0: InstallReleaseCheck("doctor", "passed"),
    )

    report = run_install_release_gate(
        source_bundle_report=source,
        staging_plan_report=staging,
        artifact_integrity_report=artifact,
    )

    assert report.status == "passed"
    assert [check.name for check in report.checks] == [
        "windows_installer_dry_run",
        "posix_installer_dry_run",
        "doctor",
        "source_bundle_report",
        "artifact_integrity_report",
        "staging_plan_report",
        "release_artifact_consistency",
    ]


def test_install_release_gate_fails_when_any_check_fails(tmp_path: Path, monkeypatch) -> None:
    source = _write_json(tmp_path / "source.json", {"status": "failed", "errors": ["bad"]})
    artifact = _write_json(tmp_path / "artifact.json", {"status": "passed", "checks": []})
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 10, "errors": []})

    monkeypatch.setattr(
        gate,
        "check_windows_installer_dry_run",
        lambda timeout_seconds=90.0: InstallReleaseCheck("windows_installer_dry_run", "passed"),
    )
    monkeypatch.setattr(
        gate,
        "check_posix_installer_dry_run",
        lambda timeout_seconds=90.0: InstallReleaseCheck("posix_installer_dry_run", "passed"),
    )
    monkeypatch.setattr(gate, "check_doctor", lambda timeout_seconds=90.0: InstallReleaseCheck("doctor", "passed"))

    report = run_install_release_gate(
        source_bundle_report=source,
        staging_plan_report=staging,
        artifact_integrity_report=artifact,
    )

    assert report.status == "failed"
    assert any(check.name == "source_bundle_report" and check.status == "failed" for check in report.checks)


def test_release_artifact_consistency_passes_when_reports_match(tmp_path: Path) -> None:
    artifact_path = tmp_path / "release" / "bundle.zip"
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 3,
            "output_path": str(artifact_path),
            "files": [
                {"path": "scripts/install-xagent.ps1"},
                {"path": "scripts/install-xagent.sh"},
                {"path": "scripts/xagent_doctor.py"},
            ],
        },
    )
    artifact = _write_json(tmp_path / "artifact.json", {"status": "passed", "file_count": 3, "artifact_path": str(artifact_path)})
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 3})

    check = check_release_artifact_consistency(source, staging, artifact)

    assert check.status == "passed"


def test_release_artifact_consistency_fails_on_count_and_path_mismatch(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 3,
            "output_path": str(tmp_path / "release" / "bundle.zip"),
            "files": [
                {"path": "scripts/install-xagent.ps1"},
                {"path": "scripts/install-xagent.sh"},
                {"path": "scripts/xagent_doctor.py"},
            ],
        },
    )
    artifact = _write_json(tmp_path / "artifact.json", {"status": "passed", "file_count": 2, "artifact_path": str(tmp_path / "release" / "old.zip")})
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 3})

    check = check_release_artifact_consistency(source, staging, artifact)

    assert check.status == "failed"
    assert "file_count mismatch" in str(check.error)
    assert "output_path does not match" in str(check.error)


def test_release_artifact_consistency_requires_installer_files_in_bundle(tmp_path: Path) -> None:
    artifact_path = tmp_path / "release" / "bundle.zip"
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 1,
            "output_path": str(artifact_path),
            "files": [{"path": "scripts/xagent_doctor.py"}],
        },
    )
    artifact = _write_json(tmp_path / "artifact.json", {"status": "passed", "file_count": 1, "artifact_path": str(artifact_path)})
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 1})

    check = check_release_artifact_consistency(source, staging, artifact)

    assert check.status == "failed"
    assert "install-xagent.ps1" in str(check.error)
    assert "install-xagent.sh" in str(check.error)


def test_windows_installer_dry_run_parses_expected_output(monkeypatch) -> None:
    monkeypatch.setattr(gate, "_powershell_executable", lambda: "powershell")
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, timeout_seconds: subprocess.CompletedProcess(
            command,
            0,
            stdout="X-Agent installer (dry-run)\n> Push-Location frontend; npm ci; npm run type-check; Pop-Location\n> .\\venv\\Scripts\\python scripts/xagent_doctor.py --json\nDry-run only.\n",
            stderr="",
        ),
    )

    check = gate.check_windows_installer_dry_run()

    assert check.status == "passed"


def test_posix_shell_ignores_windows_wsl_relay(monkeypatch) -> None:
    monkeypatch.setattr(gate.shutil, "which", lambda name: r"C:\Windows\system32\bash.exe" if name == "bash" else None)

    shell = gate._posix_shell_executable()

    assert shell != r"C:\Windows\system32\bash.exe"
    assert "Git" in shell or shell == "sh"


def test_posix_installer_dry_run_rejects_npm_install(monkeypatch) -> None:
    monkeypatch.setattr(gate, "_posix_shell_executable", lambda: "sh")
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, timeout_seconds: subprocess.CompletedProcess(
            command,
            0,
            stdout="X-Agent installer (dry-run)\n> cd frontend && npm install && npm run type-check\n> ./venv/bin/python scripts/xagent_doctor.py --json\nDry-run only.\n",
            stderr="",
        ),
    )

    check = gate.check_posix_installer_dry_run()

    assert check.status == "failed"
    assert "lockfile install plan" in str(check.error)


def test_doctor_accepts_warn_status(monkeypatch) -> None:
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, timeout_seconds: subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"status": "warn", "checks": [{"name": "optional_env", "status": "warn"}]}),
            stderr="",
        ),
    )

    check = gate.check_doctor()

    assert check.status == "passed"
    assert check.command == ["python", "scripts/xagent_doctor.py", "--json"]
    assert check.details["doctor_status"] == "warn"


def test_install_release_tail_redacts_secret_like_output() -> None:
    text = "BOOTSTRAP_API_KEY=sk-" + ("a" * 32) + "\nstdout ghp_" + ("b" * 40)

    tail = gate._tail(text)

    assert "BOOTSTRAP_API_KEY=<redacted-output>" in tail
    assert "stdout <redacted-secret>" in tail
    assert "sk-" not in tail
    assert "ghp_" not in tail
