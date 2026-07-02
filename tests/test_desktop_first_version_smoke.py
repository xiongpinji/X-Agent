from __future__ import annotations

from pathlib import Path

import scripts.desktop_first_version_smoke as desktop_smoke


def test_desktop_first_version_smoke_accepts_current_contract() -> None:
    report = desktop_smoke.build_report(run_compile=False)

    assert report.status == "passed"
    assert report.native_installer_claimed is False
    assert {check.name for check in report.checks} == {
        "desktop_entrypoints",
        "packaging_spec",
        "tauri_security_contract",
    }


def test_packaging_spec_rejects_non_repo_local_assets(tmp_path: Path, monkeypatch) -> None:
    spec = tmp_path / "xagent-desktop.spec"
    spec.write_text(
        "\n".join(
            [
                "[app]",
                'name = "X-Agent"',
                'entry = "backend.app.main:app"',
                'startup_page = "frontend/startup.html"',
                'index_page = "frontend/index.html"',
                'icon = "D:/private/icon.ico"',
                'logo = "frontend/public/assets/panda-agent-logo.png"',
                'mode = "desktop_single_user"',
                'launch_url = "http://127.0.0.1:8000/"',
            ],
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(desktop_smoke, "SPEC", spec)

    check = desktop_smoke.check_packaging_spec()

    assert check.status == "failed"
    assert "icon" in check.details["invalid_paths"]


def test_tauri_contract_rejects_missing_typecheck_config(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "package.json"
    package.write_text(
        '{"scripts":{"type-check":"vue-tsc --noEmit -p tsconfig.app.json --composite false"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(desktop_smoke, "DESKTOP_FRONTEND_PACKAGE", package)

    check = desktop_smoke.check_tauri_contract()

    assert check.status == "failed"
    assert "desktop_frontend_typecheck_points_to_missing_config" in check.details["problems"]
