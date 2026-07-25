#!/usr/bin/env python3
"""Validate extension/manifest.json the way Chrome would on "Load unpacked".

Checks:
  1. manifest.json is valid JSON.
  2. MV3 required fields present (manifest_version=3, name, version).
  3. Expected version pinning (version 0.2.0, version_name 0.2.0-alpha).
  4. Every file path referenced by the manifest exists on disk
     (icons, action popup/icons, background service worker,
     content scripts, web_accessible_resources).
  5. Permission names are recognizable MV3 permissions (typo guard).
  6. background.type is "module" when the service worker uses ES imports.

Exit code 0 on success, 1 on any failure.

Usage (from repository root):
    ./venv/Scripts/python.exe extension/scripts/validate_manifest.py
"""

import json
import re
import sys
from pathlib import Path

EXTENSION_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = EXTENSION_ROOT / "manifest.json"

EXPECTED_VERSION = "0.2.0"
EXPECTED_VERSION_NAME = "0.2.0-alpha"

# MV3 API permissions (non-host) recognized by Chrome 90+.
KNOWN_PERMISSIONS = {
    "activeTab", "alarms", "background", "bookmarks", "browsingData",
    "clipboardRead", "clipboardWrite", "contentSettings", "contextMenus",
    "cookies", "debugger", "declarativeContent", "declarativeNetRequest",
    "declarativeNetRequestWithHostAccess", "desktopCapture", "downloads",
    "fontSettings", "gcm", "geolocation", "history", "identity",
    "idle", "management", "nativeMessaging", "notifications",
    "offscreen", "pageCapture", "platformKeys", "power", "printerProvider",
    "printing", "privacy", "processes", "proxy", "scripting", "search",
    "sessions", "sidePanel", "storage", "system.cpu", "system.memory",
    "system.storage", "tabCapture", "tabGroups", "tabs", "topSites",
    "tts", "ttsEngine", "unlimitedStorage", "vpnProvider", "wallpaper",
    "webAuthenticationProxy", "webNavigation", "webRequest",
    "webRequestBlocking",
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {message}")
    if not condition:
        failures.append(message)


def main() -> int:
    # 1. Valid JSON
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        check(True, "manifest.json 是合法 JSON")
    except json.JSONDecodeError as exc:
        check(False, f"manifest.json JSON 解析失败: {exc}")
        return 1

    # 2. MV3 required fields
    check(manifest.get("manifest_version") == 3, "manifest_version == 3")
    check(bool(manifest.get("name")), "name 存在且非空")
    check(bool(manifest.get("version")), "version 存在且非空")

    # 3. Version pinning
    check(manifest.get("version") == EXPECTED_VERSION,
          f"version == {EXPECTED_VERSION} (实际: {manifest.get('version')})")
    check(manifest.get("version_name") == EXPECTED_VERSION_NAME,
          f"version_name == {EXPECTED_VERSION_NAME} (实际: {manifest.get('version_name')})")
    check(re.fullmatch(r"\d+(\.\d+){0,3}", manifest.get("version", "")) is not None,
          "version 符合 Chrome 版本号格式 (1-4 段数字)")

    # 4. Referenced files exist
    referenced: list[str] = []

    def add(path, origin):
        if isinstance(path, str):
            referenced.append((path, origin))

    for size, p in (manifest.get("icons") or {}).items():
        add(p, f"icons[{size}]")
    action = manifest.get("action") or {}
    add(action.get("default_popup"), "action.default_popup")
    for size, p in (action.get("default_icon") or {}).items():
        add(p, f"action.default_icon[{size}]")
    add((manifest.get("background") or {}).get("service_worker"),
        "background.service_worker")
    for i, cs in enumerate(manifest.get("content_scripts") or []):
        for p in cs.get("js", []):
            add(p, f"content_scripts[{i}].js")
        for p in cs.get("css", []):
            add(p, f"content_scripts[{i}].css")
    for i, war in enumerate(manifest.get("web_accessible_resources") or []):
        for p in war.get("resources", []):
            add(p, f"web_accessible_resources[{i}]")

    check(len(referenced) > 0, f"共收集 {len(referenced)} 个 manifest 引用路径")
    for rel, origin in referenced:
        exists = (EXTENSION_ROOT / rel).is_file()
        check(exists, f"{origin} -> {rel} {'存在' if exists else '缺失'}")

    # 5. Permission typo guard
    for perm in manifest.get("permissions", []):
        check(perm in KNOWN_PERMISSIONS, f"权限 '{perm}' 是已知 MV3 权限")

    # 6. Module service worker consistency
    bg = manifest.get("background") or {}
    sw_rel = bg.get("service_worker")
    if sw_rel and (EXTENSION_ROOT / sw_rel).is_file():
        sw_src = (EXTENSION_ROOT / sw_rel).read_text(encoding="utf-8")
        uses_esm = re.search(r"^\s*(import|export)\s", sw_src, re.MULTILINE) is not None
        if uses_esm:
            check(bg.get("type") == "module",
                  "service worker 使用 ES import => background.type == 'module'")

    # 7. MV3 must NOT contain legacy MV2 keys
    for legacy in ("browser_action", "page_action", "persistent"):
        check(legacy not in json.dumps(manifest.get("background", {}))
              and legacy not in manifest,
              f"不含 MV2 遗留字段 '{legacy}'")

    print()
    if failures:
        print(f"验证失败: {len(failures)} 项")
        return 1
    print("全部检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
