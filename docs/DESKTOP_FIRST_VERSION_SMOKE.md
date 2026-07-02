# Desktop First-Version Smoke

## Supported Scope

- Launch the local desktop entrypoint with `python -m scripts.one_click_desktop` or `start_xagent_desktop.bat`.
- Run the desktop packaging dry-run contract with `python scripts/desktop_first_version_smoke.py --json`.
- Verify the Tauri shell can build-check against the local backend-only allowlist with `cargo check --manifest-path desktop/Cargo.toml`.
- Authenticate against a local or Stage3 backend through the backend's normal auth/RBAC layer.
- Trigger one agent/workbench action, access workspace/file preview, and exit cleanly during the later real Windows-native strict E2E run.

## Out Of Scope

- Browser extension.
- Full marketplace flows.
- Forum, analytics dashboards, plugin/skill/template marketplaces.
- Claiming a signed native MSI/NSIS installer before signing material and hosted Windows artifact evidence exist.

## Entry Points

- Runtime: `python -m scripts.one_click_desktop`
- Runtime batch wrapper: `start_xagent_desktop.bat`
- Packaging dry-run: `python -m scripts.package_desktop`
- Packaging batch wrapper: `package_xagent_desktop.bat`
- Console scripts from `pyproject.toml`: `xagent-desktop`, `xagent-package-desktop`
- Tauri app: `desktop/Cargo.toml`, `desktop/tauri.conf.json`, `desktop/frontend/package.json`

## Packaging Contract

`packaging/xagent-desktop.spec` must stay reproducible from repository files:

- `entry = "backend.app.main:app"`
- `startup_page = "frontend/startup.html"`
- `index_page = "frontend/index.html"`
- `icon = "desktop/icons/icon.ico"`
- `logo = "frontend/public/assets/panda-agent-logo.png"`
- `mode = "desktop_single_user"`
- `launch_url = "http://127.0.0.1:8000/"`

No local absolute asset paths such as `D:/...` are allowed in the packaging spec.

## Commands Run On 2026-06-18

```powershell
python scripts/desktop_first_version_smoke.py --json
python -m pytest tests/test_desktop_first_version_smoke.py tests/test_desktop_tauri_security.py tests/test_rc_ci_contract.py --no-cov -q
npm --prefix desktop/frontend run type-check
npm --prefix desktop/frontend run build
npm --prefix desktop/frontend audit --audit-level=high
cargo check --manifest-path desktop/Cargo.toml
```

Results:

- `desktop_first_version_smoke.py`: passed; report written to `.xagent_runtime/reports/desktop-first-version-smoke.json`.
- Pytest desktop/CI contract slice: 31 passed.
- Desktop frontend type-check: passed.
- Desktop frontend build: passed with Vite 8.0.16; remaining Rollup/Rolldown messages are non-blocking upstream annotation and plugin timing warnings.
- Desktop frontend high-severity dependency audit: passed; 0 vulnerabilities reported at the configured `--audit-level=high` threshold.
- `cargo check`: passed with non-blocking dead-code warnings.

## Current Local Limitation

This is still not a signed native Windows installer claim. The local gate covers reproducible desktop entrypoints, Tauri security scope, Rust build-check, frontend type-check/build, and high-severity dependency audit. A signed installer artifact and real Windows-native strict E2E run remain release-evidence tasks after signing material and hosted artifact storage are available.

## CI Guard

The commercial RC workflow now runs `python scripts/desktop_first_version_smoke.py --json`, uploads `.xagent_runtime/reports/desktop-first-version-smoke.json`, and the CI contract requires the command and desktop smoke tests.
