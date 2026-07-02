import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


def _tauri_config() -> dict:
    return json.loads((DESKTOP / "tauri.conf.json").read_text(encoding="utf-8"))


def test_tauri_csp_is_enabled_and_blocks_remote_script_execution():
    security = _tauri_config()["tauri"]["security"]

    csp = security.get("csp")
    assert isinstance(csp, str)
    assert csp
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "https:" not in csp.split("script-src", 1)[1].split(";", 1)[0]


def test_tauri_shell_allowlist_cannot_execute_arbitrary_commands():
    shell = _tauri_config()["tauri"]["allowlist"]["shell"]

    assert shell["all"] is False
    assert shell["open"] is True
    assert shell["execute"] is False
    assert shell["sidecar"] is False
    assert shell["scope"] == []


def test_tauri_filesystem_allowlist_is_app_scoped():
    fs = _tauri_config()["tauri"]["allowlist"]["fs"]

    assert fs["all"] is False
    assert fs["scope"] == ["$APPDATA/com.xagent.desktop/**"]
    assert "$HOME/**" not in fs["scope"]
    assert "$APPDATA/**" not in fs["scope"]


def test_tauri_http_allowlist_is_local_backend_only():
    http = _tauri_config()["tauri"]["allowlist"]["http"]

    assert http["all"] is False
    assert http["request"] is True
    assert http["scope"] == [
        "http://127.0.0.1:8000/**",
        "http://localhost:8000/**",
    ]
    assert "http://**" not in http["scope"]
    assert "https://**" not in http["scope"]


def test_tauri_windows_icon_resource_exists():
    bundle = _tauri_config()["tauri"]["bundle"]

    assert bundle["icon"] == ["icons/icon.ico"]
    assert (DESKTOP / "icons" / "icon.ico").is_file()


def test_tauri_unused_high_risk_allowlists_are_disabled():
    allowlist = _tauri_config()["tauri"]["allowlist"]

    assert allowlist["path"]["all"] is False
    assert allowlist["notification"]["all"] is False
    assert allowlist["dialog"]["all"] is False
    assert allowlist["clipboard"]["all"] is False
    assert allowlist["clipboard"]["readText"] is False
    assert allowlist["clipboard"]["writeText"] is False

    window = allowlist["window"]
    assert window["all"] is False
    assert window["setAlwaysOnTop"] is False
    assert window["setCursorGrab"] is False
    assert window["print"] is False
    assert window["minimize"] is True
    assert window["maximize"] is True
    assert window["show"] is True
    assert window["hide"] is True
    assert window["close"] is True
    assert window["setFocus"] is True


def test_tauri_cargo_features_do_not_reenable_broad_permissions():
    cargo_toml = (DESKTOP / "Cargo.toml").read_text(encoding="utf-8")

    assert "fs-all" not in cargo_toml
    assert "http-all" not in cargo_toml
    assert "shell-execute" not in cargo_toml
    assert "shell-sidecar" not in cargo_toml
    assert "dialog-all" not in cargo_toml
    assert "clipboard-all" not in cargo_toml
    assert "notification-all" not in cargo_toml
    assert "path-all" not in cargo_toml
    assert "window-all" not in cargo_toml
    assert "fs-read-file" in cargo_toml
    assert "http-request" in cargo_toml


def test_desktop_backend_url_builder_is_used_by_network_commands():
    for rel_path in [
        "src/commands/api.rs",
        "src/commands/agent.rs",
        "src/ipc.rs",
    ]:
        source = (DESKTOP / rel_path).read_text(encoding="utf-8")
        assert "crate::security::build_backend_url" in source

    security_source = (DESKTOP / "src/security.rs").read_text(encoding="utf-8")
    assert 'match backend_url' in security_source
    assert '"http://127.0.0.1" | "http://localhost"' in security_source
    assert "path.starts_with('/')" in security_source
    assert 'path.contains("://")' in security_source
