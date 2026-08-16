from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


def test_desktop_tauri_surface_is_minimal_and_bounded() -> None:
    config = json.loads((DESKTOP / "tauri.conf.json").read_text(encoding="utf-8"))

    assert config["build"] == {
        "beforeDevCommand": "npm run dev",
        "beforeBuildCommand": "npm run build",
        "devUrl": "http://localhost:5173",
        "frontendDist": "frontend/dist",
    }
    security = config["app"]["security"]
    assert security["csp"]
    assert security["capabilities"] == [
        {
            "identifier": "main-agent-runner",
            "description": "The main window may invoke only the custom commands registered by the application.",
            "windows": ["main"],
            "permissions": [],
        }
    ]
    assert "plugins" not in config

    main_source = (DESKTOP / "src/main.rs").read_text(encoding="utf-8")
    forbidden = (
        "commands::file",
        "commands::agent",
        "call_backend_api",
        "toggle_devtools",
        "global_shortcut",
        "system_tray",
    )
    assert all(item not in main_source for item in forbidden)
    for command in (
        "configure_backend",
        "login",
        "logout",
        "trigger_agent",
        "get_run_status",
        "cancel_run",
    ):
        assert f"commands::commercial::{command}" in main_source


def test_desktop_release_uses_real_mobile_contract_without_demo_surfaces() -> None:
    commercial = "\n".join(
        (DESKTOP / path).read_text(encoding="utf-8")
        for path in ("src/commands/commercial.rs", "src/state.rs")
    )
    app = (DESKTOP / "frontend/src/App.vue").read_text(encoding="utf-8")
    router = DESKTOP / "frontend/src/router/index.ts"

    for endpoint in (
        "/api/v1/auth/login",
        "/api/v1/mobile/trigger",
        "/api/v1/mobile/runs/",
    ):
        assert endpoint in commercial
    assert "AUTHORIZATION" in commercial
    assert "Bearer" in commercial
    assert "http://localhost" in commercial
    assert "https" in commercial
    assert "error_body" not in commercial

    assert not router.exists()
    for marker in ("Mock data", "功能开发中", "文件浏览", "Agent管理", "总运行次数"):
        assert marker not in app


def test_desktop_cargo_lock_is_versioned() -> None:
    ignore = (DESKTOP / ".gitignore").read_text(encoding="utf-8")
    assert "Cargo.lock" not in ignore
    assert (DESKTOP / "Cargo.lock").is_file()
