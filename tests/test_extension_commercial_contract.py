from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"


def test_extension_manifest_has_no_automatic_page_or_native_access() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert manifest["permissions"] == ["storage"]
    assert manifest["optional_host_permissions"] == [
        "https://*/*",
        "http://localhost/*",
        "http://127.0.0.1/*",
    ]
    for key in ("host_permissions", "background", "content_scripts", "web_accessible_resources", "commands"):
        assert key not in manifest
    assert manifest["content_security_policy"]["extension_pages"] == (
        "script-src 'self'; object-src 'none'; base-uri 'none'"
    )


def test_extension_package_and_popup_use_only_commercial_agent_surface() -> None:
    package_script = (EXTENSION / "scripts/package-extension.js").read_text(encoding="utf-8")
    api = (EXTENSION / "extension-api.js").read_text(encoding="utf-8")
    popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")

    for name in ("background.js", "content.js", "injected.js", "native-messaging-host.json.example"):
        assert name not in package_script
    for endpoint in (
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/mobile/trigger",
        "/api/v1/mobile/runs/",
    ):
        assert endpoint in api
    assert "chrome.storage.session" in api
    assert "chrome.storage.local" in api
    assert "Authorization" in api
    assert "Bearer" in api
    assert "innerHTML" not in (EXTENSION / "popup.js").read_text(encoding="utf-8")
    assert '<script src="extension-api.js"></script>' in popup
    assert '<script src="popup.js"></script>' in popup
