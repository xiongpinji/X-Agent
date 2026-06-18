#!/usr/bin/env python3
"""Validate the first-version desktop packaging and smoke contract.

This gate is intentionally non-GUI by default. It proves that the desktop
delivery has reproducible entrypoints, local-only backend scope, in-repo bundle
assets, and runnable dry-run commands. It does not claim a signed native
installer or a real Windows-native strict E2E session.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "desktop-first-version-smoke.json"
SPEC = ROOT / "packaging" / "xagent-desktop.spec"
DESKTOP_FRONTEND_PACKAGE = ROOT / "desktop" / "frontend" / "package.json"
TAURI_CONFIG = ROOT / "desktop" / "tauri.conf.json"
TAURI_CARGO = ROOT / "desktop" / "Cargo.toml"


@dataclass(frozen=True)
class DesktopSmokeCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "passed"


@dataclass(frozen=True)
class DesktopSmokeReport:
    status: str
    generated_at: str
    native_installer_claimed: bool
    checks: list[DesktopSmokeCheck]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.status == "passed"
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_spec(path: Path | None = None) -> dict[str, str]:
    path = path or SPEC
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _is_repo_relative(value: str) -> bool:
    path = Path(value)
    return (
        bool(value)
        and not path.is_absolute()
        and not re.match(r"^[A-Za-z]:[\\/]", value)
        and "://" not in value
        and not value.startswith(("\\", "/"))
    )


def _path_from_spec(value: str) -> Path:
    return ROOT / value


def check_desktop_entrypoints() -> DesktopSmokeCheck:
    required = {
        "one_click_script": ROOT / "scripts" / "one_click_desktop.py",
        "package_script": ROOT / "scripts" / "package_desktop.py",
        "start_batch": ROOT / "start_xagent_desktop.bat",
        "package_batch": ROOT / "package_xagent_desktop.bat",
        "pyproject": ROOT / "pyproject.toml",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    console_scripts = {
        "xagent-desktop": 'xagent-desktop = "scripts.one_click_desktop:main"',
        "xagent-package-desktop": 'xagent-package-desktop = "scripts.package_desktop:main"',
    }
    missing_scripts = [name for name, token in console_scripts.items() if token not in pyproject_text]
    if missing or missing_scripts:
        return DesktopSmokeCheck(
            name="desktop_entrypoints",
            status="failed",
            details={"missing_files": missing, "missing_console_scripts": missing_scripts},
            error="Desktop entrypoints are incomplete.",
        )
    return DesktopSmokeCheck(
        name="desktop_entrypoints",
        status="passed",
        details={"console_scripts": sorted(console_scripts), "batch_files": ["start_xagent_desktop.bat", "package_xagent_desktop.bat"]},
    )


def check_packaging_spec() -> DesktopSmokeCheck:
    values = _read_spec()
    required_keys = {"name", "entry", "startup_page", "index_page", "icon", "logo", "mode", "launch_url"}
    missing_keys = sorted(required_keys - set(values))
    local_asset_keys = ("startup_page", "index_page", "icon", "logo")
    invalid_paths = [key for key in local_asset_keys if key in values and not _is_repo_relative(values[key])]
    missing_assets = [key for key in local_asset_keys if key in values and not _path_from_spec(values[key]).is_file()]
    launch_url = values.get("launch_url", "")
    local_launch = launch_url.startswith("http://127.0.0.1:") or launch_url.startswith("http://localhost:")
    mode_ok = values.get("mode") == "desktop_single_user"
    entry_ok = values.get("entry") == "backend.app.main:app"
    if missing_keys or invalid_paths or missing_assets or not local_launch or not mode_ok or not entry_ok:
        return DesktopSmokeCheck(
            name="packaging_spec",
            status="failed",
            details={
                "missing_keys": missing_keys,
                "invalid_paths": invalid_paths,
                "missing_assets": missing_assets,
                "launch_url": launch_url,
                "mode": values.get("mode"),
                "entry": values.get("entry"),
            },
            error="Desktop packaging spec is not reproducible from repo contents.",
        )
    return DesktopSmokeCheck(
        name="packaging_spec",
        status="passed",
        details={key: values[key] for key in sorted(required_keys)},
    )


def check_tauri_contract() -> DesktopSmokeCheck:
    config = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))
    package = json.loads(DESKTOP_FRONTEND_PACKAGE.read_text(encoding="utf-8"))
    cargo_text = TAURI_CARGO.read_text(encoding="utf-8")

    allowlist = config.get("tauri", {}).get("allowlist", {})
    security = config.get("tauri", {}).get("security", {})
    fs_scope = allowlist.get("fs", {}).get("scope")
    http_scope = allowlist.get("http", {}).get("scope")
    type_check_script = package.get("scripts", {}).get("type-check", "")
    problems: list[str] = []
    if security.get("csp", "").find("script-src 'self'") == -1:
        problems.append("csp_script_src_not_self")
    if allowlist.get("shell", {}).get("execute") is not False:
        problems.append("shell_execute_not_disabled")
    if fs_scope != ["$APPDATA/com.xagent.desktop/**"]:
        problems.append("fs_scope_not_appdata_scoped")
    if http_scope != ["http://127.0.0.1:8000/**", "http://localhost:8000/**"]:
        problems.append("http_scope_not_local_backend_only")
    if "tsconfig.app.json" in type_check_script or "tsconfig.json" not in type_check_script:
        problems.append("desktop_frontend_typecheck_points_to_missing_config")
    for forbidden in ("fs-all", "http-all", "shell-execute", "shell-sidecar"):
        if forbidden in cargo_text:
            problems.append(f"cargo_feature_{forbidden}_enabled")

    if problems:
        return DesktopSmokeCheck(
            name="tauri_security_contract",
            status="failed",
            details={"problems": problems},
            error="Desktop Tauri security or type-check contract is not satisfied.",
        )
    return DesktopSmokeCheck(
        name="tauri_security_contract",
        status="passed",
        details={"fs_scope": fs_scope, "http_scope": http_scope, "type_check_script": type_check_script},
    )


def _run_command(command: list[str], *, cwd: Path = ROOT, timeout_seconds: int = 120) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )
    return completed.returncode, completed.stdout[-4000:]


def check_python_compile() -> DesktopSmokeCheck:
    code, output = _run_command(
        [sys.executable, "-m", "py_compile", "scripts/one_click_desktop.py", "scripts/package_desktop.py"],
    )
    if code != 0:
        return DesktopSmokeCheck(
            name="desktop_python_entrypoint_compile",
            status="failed",
            details={"exit_code": code, "output_tail": output},
            error="Desktop Python entrypoints do not compile.",
        )
    return DesktopSmokeCheck(name="desktop_python_entrypoint_compile", status="passed", details={"exit_code": code})


def build_report(*, run_compile: bool = True) -> DesktopSmokeReport:
    checks = [
        check_desktop_entrypoints(),
        check_packaging_spec(),
        check_tauri_contract(),
    ]
    if run_compile:
        checks.append(check_python_compile())
    status = "passed" if all(check.ok for check in checks) else "failed"
    return DesktopSmokeReport(
        status=status,
        generated_at=_utc_now(),
        native_installer_claimed=False,
        checks=checks,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-compile", action="store_true", help="Skip Python entrypoint py_compile.")
    args = parser.parse_args(argv)

    report = build_report(run_compile=not args.no_compile)
    payload = report.to_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Desktop first-version smoke status: {report.status}")
        print(f"Report written to {args.output}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
