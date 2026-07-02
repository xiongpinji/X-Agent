# X-Agent Commercial Audit Upgrade Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current RC candidate into a commercially credible first-version delivery by removing unshipped user-facing surfaces, adding API/auth contract gates, and preserving strict evidence for final Stage3 release.

**Architecture:** Treat mounted FastAPI routes from `backend.app.main:app.routes` as the backend source of truth. Treat first-version frontend routes and desktop packaging as the commercial user surface. Browser extension work is explicitly out of first-version scope; domain/ICP/HTTPS evidence is isolated into the final external Stage3 task.

**Tech Stack:** FastAPI, pytest, React/Vite/TypeScript, Docker Compose Stage3, GitHub Actions, Windows desktop packaging, NGINX staging proxy.

---

## Progress

- [x] Three-report comparison generated: `COMMERCIAL_AUDIT_COMPARISON_AND_UPGRADE_PLAN_20260618.md`
- [x] Machine evidence generated: `.xagent_runtime/reports/audit-compare-evidence-20260618.json`
- [x] Current route auth gate rechecked: `python scripts/route_auth_audit.py --json`
- [x] Deployment hardening gate rechecked: `python scripts/security_deployment_gate.py`
- [x] Non-strict RC final gate rechecked: `python scripts/rc_final_gate.py --require-ready-to-tag`
- [x] Task 1: Freeze first-version scope and hide deferred frontend entries
- [x] Task 2: Add frontend-to-mounted-route API contract gate
- [x] Task 3: Unify frontend authenticated HTTP/SSE client usage
- [x] Task 4: Classify unmounted backend route modules
- [x] Task 5: Harden hosted CI/deploy workflow trust boundary
- [x] Task 6: Validate desktop first-version packaging and smoke flow
- [x] Task 6.1: Close post-review local auth/contract findings
- [x] Task 7A: Complete first-version single-machine smoke delivery
- [ ] Task 7: Complete Stage3 external evidence after domain/ICP readiness

## Scope Rules

- First-version commercial scope includes: auth/RBAC, workbench/agent run, workspace/file preview, memory, desktop, DeepSeek LLM backend, GitHub integration, Feishu integration, Stage3 deploy evidence.
- First-version commercial scope excludes: browser extension, WebAuthn/passkey, full OAuth marketplace, forum, analytics dashboards, plugin marketplace, skill marketplace, templates marketplace, public notification subscription, and any unmounted route module not explicitly promoted by this plan.
- Do not mount deferred backend modules just because frontend references exist. Every promoted module must import cleanly, be mounted intentionally, pass route auth audit, and have focused tests.
- Keep domain/ICP/HTTPS as Stage3 external evidence. It must not block local code cleanup tasks.

### Task 1: Freeze first-version scope and hide deferred frontend entries

**Files:**
- Create: `docs/RC_FIRST_VERSION_SCOPE.md`
- Modify: `frontend/src/console/*` and route/navigation files discovered by `rg "Forum|Analytics|PluginMarket|SkillMarket|Template|Notification|WebAuthn|OAuth" frontend/src`
- Test: existing frontend tests plus a new focused test near the affected router/navigation tests

- [ ] **Step 1: Create the scope document**

Write `docs/RC_FIRST_VERSION_SCOPE.md` with these exact sections:

```markdown
# X-Agent RC First-Version Scope

## Ship In First Version

- Auth and RBAC
- Workbench and agent run
- Workspace and file preview
- Memory
- Desktop client/runtime
- DeepSeek LLM backend
- GitHub integration
- Feishu integration
- Stage3 deploy evidence chain

## Deferred From First Version

- Browser extension
- WebAuthn/passkey
- Full OAuth marketplace flows
- Forum
- Analytics dashboards
- Plugin marketplace
- Skill marketplace
- Templates marketplace
- Public notification subscription

## Rule

The frontend must not route users into deferred surfaces. The backend must not mount deferred route modules unless the module is explicitly promoted with tests, route-auth audit coverage, and API contract coverage.
```

- [ ] **Step 2: Locate all deferred frontend entries**

Run:

```powershell
rg -n "Forum|Analytics|PluginMarket|SkillMarket|Template|Notification|WebAuthn|passkey|OAuth|browser extension" frontend/src
```

Expected: a concrete list of navigation, router, and page references to either remove from first-version navigation or mark disabled.

- [ ] **Step 3: Disable or hide deferred navigation**

Use the existing navigation pattern in the repo. For every deferred item, make one of these two changes:

```ts
// Preferred when the product should not show the feature yet:
// remove the item from the exported first-version navigation array
```

or:

```ts
{
  id: "templates",
  label: "Templates",
  disabled: true,
  badge: "Coming soon"
}
```

Do not leave clickable links that call `/api/v1/forum`, `/api/v1/analytics`, `/api/v1/plugin-market`, `/api/v1/skill-market`, `/api/v1/templates`, or `/api/v1/notifications/subscribe`.

- [ ] **Step 4: Add a frontend regression test**

Add or update a test that renders the first-version navigation and asserts deferred entries are absent or disabled:

```ts
expect(screen.queryByRole("link", { name: /forum/i })).not.toBeInTheDocument();
expect(screen.queryByRole("link", { name: /analytics/i })).not.toBeInTheDocument();
expect(screen.queryByRole("link", { name: /plugin market/i })).not.toBeInTheDocument();
expect(screen.queryByRole("link", { name: /skill market/i })).not.toBeInTheDocument();
expect(screen.queryByRole("link", { name: /templates/i })).not.toBeInTheDocument();
```

- [ ] **Step 5: Verify**

Run:

```powershell
npm --prefix frontend test -- --run
```

Expected: frontend tests pass, or any unrelated pre-existing failure is captured with exact test names before proceeding.

- [ ] **Step 6: Commit**

Run:

```powershell
git add docs/RC_FIRST_VERSION_SCOPE.md frontend/src
git commit -m "fix(frontend): hide deferred first-version surfaces"
```

### Task 2: Add frontend-to-mounted-route API contract gate

**Files:**
- Create: `scripts/frontend_api_contract_audit.py`
- Create: `tests/test_frontend_api_contract_audit.py`
- Create: `docs/API_CONTRACT_ALLOWLIST.md`
- Modify: `.github/workflows/commercial-rc.yml` or the active commercial RC workflow

- [ ] **Step 1: Write the failing test for missing routes**

Create `tests/test_frontend_api_contract_audit.py`:

```python
from pathlib import Path

from scripts.frontend_api_contract_audit import audit_frontend_api_contract


def test_frontend_api_contract_has_no_unapproved_missing_routes():
    result = audit_frontend_api_contract(
        frontend_root=Path("frontend/src"),
        allowlist_path=Path("docs/API_CONTRACT_ALLOWLIST.md"),
    )

    assert result["ok"], result["missing"]
```

- [ ] **Step 2: Run the test and confirm it fails before implementation**

Run:

```powershell
python -m pytest tests/test_frontend_api_contract_audit.py --no-cov -q
```

Expected: import failure because `scripts/frontend_api_contract_audit.py` does not exist yet.

- [ ] **Step 3: Implement the audit script**

Create `scripts/frontend_api_contract_audit.py` with these responsibilities:

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from fastapi.routing import APIRoute

from backend.app.main import app

API_REF_RE = re.compile(r"['\"](/api/[^'\"`\\s)]+)")
PARAM_RE = re.compile(r"\$\{[^}]+\}|[0-9a-fA-F-]{8,}|\\b\\d+\\b")


def _normalize_frontend_path(path: str) -> str:
    path = path.split("?")[0]
    path = PARAM_RE.sub("{param}", path)
    return path.rstrip("/") or path


def _normalize_fastapi_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{param}", path).rstrip("/") or path


def _mounted_routes() -> set[str]:
    routes: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.add(_normalize_fastapi_path(route.path))
    return routes


def _frontend_refs(frontend_root: Path) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for path in frontend_root.rglob("*"):
        if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in API_REF_RE.finditer(text):
            refs.append((str(path), _normalize_frontend_path(match.group(1))))
    return refs


def _allowlist_entries(path: Path) -> set[str]:
    if not path.exists():
        return set()
    entries: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- `/api/"):
            entries.add(line.split("`", 2)[1].rstrip("/"))
    return entries


def audit_frontend_api_contract(frontend_root: Path, allowlist_path: Path) -> dict:
    mounted = _mounted_routes()
    refs = sorted(set(_frontend_refs(frontend_root)))
    allowlist = _allowlist_entries(allowlist_path)
    missing = [
        {"file": file, "path": ref}
        for file, ref in refs
        if ref not in mounted and ref not in allowlist
    ]
    return {
        "ok": not missing,
        "mounted_count": len(mounted),
        "frontend_ref_count": len(refs),
        "missing": missing,
    }


def main() -> int:
    result = audit_frontend_api_contract(
        frontend_root=Path("frontend/src"),
        allowlist_path=Path("docs/API_CONTRACT_ALLOWLIST.md"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create a strict allowlist document**

Create `docs/API_CONTRACT_ALLOWLIST.md` with only routes that are intentionally public, health-only, test-only, or deferred by Task 1. Every entry must include a reason:

```markdown
# API Contract Allowlist

- `/api/health` - public health alias used by frontend bootstrap.
- `/api/v1` - base URL string, not a callable route.
```

Do not allowlist first-version user actions. Fix or hide those instead.

- [ ] **Step 5: Run and iterate**

Run:

```powershell
python scripts/frontend_api_contract_audit.py
python -m pytest tests/test_frontend_api_contract_audit.py --no-cov -q
```

Expected: both pass after Task 1 hides deferred calls or the allowlist documents non-callable references.

- [ ] **Step 6: Add the gate to commercial RC workflow**

Add this step to the active commercial RC workflow:

```yaml
- name: Frontend API contract audit
  run: python scripts/frontend_api_contract_audit.py
```

- [ ] **Step 7: Commit**

Run:

```powershell
git add scripts/frontend_api_contract_audit.py tests/test_frontend_api_contract_audit.py docs/API_CONTRACT_ALLOWLIST.md .github/workflows
git commit -m "test: add frontend API contract gate"
```

### Task 3: Unify frontend authenticated HTTP/SSE client usage

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/services/apiClient.ts`
- Modify: files found by `rg -n "fetch\\('/api|fetch\\(\"/api|new EventSource\\('/api|new EventSource\\(\"/api" frontend/src`
- Create: `frontend/src/__tests__/authClientContract.test.ts`

- [x] **Step 1: Locate all direct API calls**

Run:

```powershell
rg -n "fetch\\('/api|fetch\\(\"/api|new EventSource\\('/api|new EventSource\\(\"/api" frontend/src
```

Expected: list of files using direct API calls.

- [x] **Step 2: Add an auth-client contract test**

Create `frontend/src/__tests__/authClientContract.test.ts`:

```ts
import { describe, expect, it } from "vitest";

describe("authenticated API client contract", () => {
  it("requires protected API calls to use the shared client", () => {
    expect(true).toBe(true);
  });
});
```

Then evolve this into a static check or lint-backed test after the call sites are migrated.

- [x] **Step 3: Make `apiClient.ts` delegate to the authenticated client**

Change `frontend/src/services/apiClient.ts` so protected calls use the same token injection path as `frontend/src/services/api.ts`. The effective request must include:

```ts
Authorization: `Bearer ${localStorage.getItem("auth_token")}`
```

when an auth token exists.

- [x] **Step 4: Replace direct protected fetch calls**

For each protected call found in Step 1, replace:

```ts
await fetch("/api/v1/protected/path")
```

with the existing shared client pattern used in the repo, for example:

```ts
await api.get("/protected/path")
```

or:

```ts
await apiClient.get("/api/v1/protected/path")
```

Use exactly one convention consistently after inspecting current service code.

- [x] **Step 5: Handle SSE separately**

For `EventSource`, do not assume `Authorization` headers work. Implement one of these two patterns:

```ts
const token = await api.post("/streaming/token", { streamId });
const source = new EventSource(`/api/v1/streaming/stream/${streamId}?token=${encodeURIComponent(token.data.token)}`);
```

or use cookie/session auth if the backend already supports it for that stream.

- [x] **Step 6: Verify**

Run:

```powershell
npm --prefix frontend test -- --run
python scripts/frontend_api_contract_audit.py
```

Expected: frontend tests pass and API contract remains clean.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src
git commit -m "fix(frontend): route protected API calls through authenticated client"
```

Task 3 verification completed with `npm --prefix frontend run type-check`, `python -m pytest tests/test_frontend_auth_client_contract.py tests/test_frontend_api_contract_audit.py tests/test_rc_first_version_scope.py --no-cov -q`, and `python scripts/frontend_api_contract_audit.py --json`. Follow-up review found protected `EventSource` calls still needed true signed URLs, not long-lived bearer tokens in query strings. The follow-up fix added short-lived backend stream tokens for agent and messages SSE, routed frontend SSE helpers through token mint endpoints, expanded the auth-client contract test, and fixed the `/api/v1/agent/stream/health` static route so it is not shadowed by `/stream/{run_id}`. Follow-up verification completed with `python -m pytest tests/test_frontend_auth_client_contract.py tests/test_streaming_comprehensive.py::TestStreamingEndpoints tests/test_messages_stream.py tests/test_messages_end_to_end.py tests/test_route_auth_audit.py --no-cov -q` (27 passed), `npm --prefix frontend run type-check`, `python scripts/frontend_api_contract_audit.py --json`, `python scripts/route_auth_audit.py --json`, and `python scripts/rc_ci_contract.py`. Commit intentionally deferred until this multi-task slice is ready for owner review.

### Task 4: Classify unmounted backend route modules

**Files:**
- Create: `docs/API_ROUTE_SCOPE_DECISION_20260618.md`
- Modify only selected `backend/app/main.py` and module tests if a module is promoted

- [x] **Step 1: Generate the route inventory**

Run:

```powershell
python - <<'PY'
from pathlib import Path
from fastapi.routing import APIRoute
from backend.app.main import app

mounted = sorted({r.endpoint.__module__.split(".")[-1] for r in app.routes if isinstance(r, APIRoute)})
print("mounted_modules")
print("\n".join(mounted))
PY
```

Expected: current mounted module list.

- [x] **Step 2: Create the decision document**

Create `docs/API_ROUTE_SCOPE_DECISION_20260618.md` with four tables:

```markdown
# API Route Scope Decision 2026-06-18

## Ship Now

| Module | Reason | Required Tests |
| --- | --- | --- |

## Defer Hidden

| Module | Reason | Frontend Entry Removed |
| --- | --- | --- |

## Internal Only

| Module | Reason | Access Control |
| --- | --- | --- |

## Delete Or Archive Later

| Module | Reason | Replacement |
| --- | --- | --- |
```

- [x] **Step 3: Classify the known missing modules**

Start with these as `defer_hidden` unless the first-version scope explicitly needs them:

```text
analytics
forum
plugin_market
plugin_marketplace
plugin_marketplace_api
skill_market
skill_market_advanced
skill_market_complete
templates
streaming_enhanced
```

Record import failures exactly as found in `.xagent_runtime/reports/audit-compare-evidence-20260618.json`.

- [x] **Step 4: Promote only one module at a time**

For any `ship_now` module:

```powershell
python - <<'PY'
import importlib
module = importlib.import_module("backend.app.api.<module_name>")
print(module)
PY
python scripts/route_auth_audit.py --json
python -m pytest tests/test_security_auth.py tests/test_security_authz.py --no-cov -q
```

Expected: import OK, route audit OK, focused tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/API_ROUTE_SCOPE_DECISION_20260618.md backend/app/main.py tests
git commit -m "docs: classify commercial API route scope"
```

Task 4 completed with `docs/API_ROUTE_SCOPE_DECISION_20260618.md` and `tests/test_api_route_scope_decision.py`. No unmounted backend API module was promoted. Verification completed with `python -m pytest tests/test_api_route_scope_decision.py tests/test_frontend_auth_client_contract.py tests/test_frontend_api_contract_audit.py tests/test_rc_first_version_scope.py tests/test_route_auth_audit.py --no-cov -q`, `python scripts/route_auth_audit.py --json`, `python scripts/frontend_api_contract_audit.py --json`, `python scripts/security_deployment_gate.py`, and `python scripts/rc_final_gate.py --require-ready-to-tag`. Commit intentionally deferred until this multi-task slice is ready for owner review.

### Task 5: Harden hosted CI/deploy workflow trust boundary

**Files:**
- Modify: `.github/workflows/security.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy.yml`
- Modify: active commercial RC workflow if the frontend API contract gate is added there

- [x] **Step 1: Locate fail-open patterns**

Run:

```powershell
rg -n "continue-on-error:\\s*true|\\|\\| true|echo .*placeholder|kubectl .*#|health.*comment" .github/workflows
```

Expected: exact workflow lines that can hide failing security/deploy checks.

- [x] **Step 2: Keep commercial release path strict**

For high/critical security gates and commercial release gates, remove:

```yaml
continue-on-error: true
```

and remove shell fallbacks:

```bash
|| true
```

from commands that should block release.

- [x] **Step 3: Disable or rename placeholder production deploy**

If `.github/workflows/deploy.yml` still contains placeholder production deployment, either make it real with health check and rollback, or rename job text so it cannot be mistaken for production automation:

```yaml
name: Deployment Template - Not Production Release
```

- [x] **Step 4: Verify workflow YAML parses**

Run:

```powershell
python - <<'PY'
from pathlib import Path
import yaml
for path in Path(".github/workflows").glob("*.yml"):
    yaml.safe_load(path.read_text(encoding="utf-8"))
    print("ok", path)
PY
```

Expected: every workflow parses.

- [ ] **Step 5: Commit**

Run:

```powershell
git add .github/workflows
git commit -m "ci: make commercial release gates fail closed"
```

Task 5 completed by making hosted security gates fail closed in `.github/workflows/security.yml` and `.github/workflows/ci.yml`, making Trivy image scanning fail closed in `.github/workflows/deploy.yml`, replacing the placeholder production job with an explicit blocking template job, and extending `scripts/rc_ci_contract.py`/`tests/test_rc_ci_contract.py` to require the frontend API/auth contract gates. Remaining grep hits are non-blocking notification/snapshot fallbacks: the security PR comment and commercial RC delivery-status snapshot. Verification completed with workflow YAML parsing, `python -m pytest tests/test_rc_ci_contract.py tests/test_frontend_auth_client_contract.py tests/test_api_route_scope_decision.py tests/test_frontend_api_contract_audit.py tests/test_rc_first_version_scope.py tests/test_route_auth_audit.py --no-cov -q`, `python scripts/rc_ci_contract.py`, and `python scripts/rc_final_gate.py --require-ready-to-tag`. Commit intentionally deferred until this multi-task slice is ready for owner review.

### Task 6: Validate desktop first-version packaging and smoke flow

**Files:**
- Inspect: desktop-related package/build scripts found by `rg -n "desktop|tauri|electron|pyinstaller|one_click_desktop" .`
- Modify only desktop packaging/test files needed for a reproducible first-version package
- Create or update: `docs/DESKTOP_FIRST_VERSION_SMOKE.md`

- [x] **Step 1: Locate desktop build entrypoints**

Run:

```powershell
rg -n "desktop|tauri|electron|pyinstaller|one_click_desktop" .
```

Expected: exact packaging commands and runtime entrypoints.

- [x] **Step 2: Document the supported desktop flow**

Create `docs/DESKTOP_FIRST_VERSION_SMOKE.md`:

```markdown
# Desktop First-Version Smoke

## Supported Scope

- Launch desktop runtime
- Authenticate against local/stage backend
- Trigger one agent/workbench action
- Access workspace/file preview
- Exit cleanly

## Out Of Scope

- Browser extension
- Full marketplace flows
```

- [x] **Step 3: Run the desktop smoke command**

Run the repo's actual desktop command found in Step 1. Capture command, pass/fail, and logs in `docs/DESKTOP_FIRST_VERSION_SMOKE.md`.

- [x] **Step 4: Add a repeatable smoke test if missing**

If there is no automated smoke, add the smallest test that verifies the desktop launcher imports and the configured backend URL is read from environment without opening a privileged browser extension path.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/DESKTOP_FIRST_VERSION_SMOKE.md
git commit -m "test(desktop): document first-version smoke flow"
```

Task 6 completed with `scripts/desktop_first_version_smoke.py`, `tests/test_desktop_first_version_smoke.py`, `docs/DESKTOP_FIRST_VERSION_SMOKE.md`, reproducible desktop packaging spec asset paths, commercial RC CI contract coverage, and desktop frontend dependency/build repairs. Verification completed with `python scripts/desktop_first_version_smoke.py --json`, `python -m pytest tests/test_desktop_first_version_smoke.py tests/test_desktop_tauri_security.py tests/test_rc_ci_contract.py --no-cov -q` (31 passed), `npm --prefix desktop/frontend run type-check`, `npm --prefix desktop/frontend run build`, `npm --prefix desktop/frontend audit --audit-level=high` (0 vulnerabilities), `cargo check --manifest-path desktop/Cargo.toml` (passed with non-blocking dead-code warnings), `python scripts/rc_ci_contract.py`, `python scripts/frontend_api_contract_audit.py --json`, `python scripts/route_auth_audit.py --json`, and `python scripts/security_deployment_gate.py`. Follow-up focused regression completed with `python -m pytest tests/test_desktop_first_version_smoke.py tests/test_desktop_tauri_security.py tests/test_rc_ci_contract.py tests/test_frontend_auth_client_contract.py tests/test_frontend_api_contract_audit.py tests/test_api_route_scope_decision.py tests/test_rc_first_version_scope.py tests/test_route_auth_audit.py --no-cov -q` (51 passed). This closes local desktop first-version gates but does not claim a signed native installer or real Windows-native strict E2E artifact yet.

### Task 6.1: Close post-review local auth/contract findings

**Files:**
- Modify: `backend/app/api/messages.py`
- Modify: `backend/app/api/streaming.py`
- Modify: `scripts/route_auth_audit.py`
- Modify: `frontend/src/console/**`
- Modify: `tests/test_messages_stream.py`
- Modify: `tests/test_streaming_comprehensive.py`
- Modify: `tests/test_route_auth_audit.py`
- Modify: `tests/test_frontend_auth_client_contract.py`

- [x] **Step 1: Close message-stream cross-tenant token signing**

`/api/v1/messages/stream/token` now rejects caller-supplied `tenant_id`, `agent_id`, `user_id`, or `trace_id` that do not match the authenticated principal. Direct `/api/v1/messages/stream` fallback auth uses the same self-service filter. Tests now mint a short-lived stream token before opening replay-only SSE history.

- [x] **Step 2: Close remaining protected console raw fetches**

First-version console pages under execution, tools, memory, organization, and realtime bootstrap now include shared `getAuthHeaders()` on protected `/api/v1/*-control` and workbench fetches. `tests/test_frontend_auth_client_contract.py` now scans protected raw fetches and rejects ones that do not use the shared auth header path.

- [x] **Step 3: Strengthen mounted-route auth audit dependency matching**

`scripts/route_auth_audit.py` now recognizes equivalent auth/signature dependencies by fully qualified module path instead of function `__name__` alone. `tests/test_route_auth_audit.py` proves a same-named dependency from the wrong module is rejected.

- [x] **Step 4: Encode signed agent stream URLs**

`/api/v1/agent/stream/{run_id}/token` now percent-encodes `run_id` in the returned EventSource URL so reserved characters cannot corrupt query parsing. `tests/test_streaming_comprehensive.py` covers reserved-character run IDs.

- [x] **Step 5: Verify local review closure**

Verification completed:

```powershell
python -m pytest tests/test_messages_stream.py tests/test_streaming_comprehensive.py::TestStreamingEndpoints tests/test_route_auth_audit.py tests/test_frontend_auth_client_contract.py --no-cov -q
# 31 passed

npm --prefix frontend run type-check
# passed

python scripts/route_auth_audit.py --json
# ok true

python scripts/frontend_api_contract_audit.py --json
# ok true

python scripts/rc_ci_contract.py
# RC CI contract status: passed

python scripts/security_deployment_gate.py
# OK No deployment-hardening issues found.

python -m pytest tests/test_frontend_api_contract_audit.py tests/test_rc_ci_contract.py tests/test_api_route_scope_decision.py tests/test_rc_first_version_scope.py tests/test_desktop_first_version_smoke.py tests/test_desktop_tauri_security.py --no-cov -q
# 39 passed

python -m pytest tests/test_rc_evidence_pack.py tests/test_rc_final_gate.py --no-cov -q
# 117 passed
```

Local evidence refresh completed:

```powershell
python scripts/desktop_first_version_smoke.py --json
# status passed

python scripts/rc_release_receipt.py
# status created

python scripts/rc_evidence_pack.py
# status created, pack sha256 4d2bf5a22ba2fdc960896efa46b4a173fb890d1f4e2bc40dfcbcab857db2a585
```

Default `python scripts/rc_final_gate.py --require-ready-to-tag` currently reports `ready_with_receipt_refresh_required` with all local gates ok and `evidence_pack` passed; this is the script's receipt/final-gate freshness loop, so it is not claimed as `ready_for_rc_tag`. Strict Stage3 was run separately with `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json` and now fails only on `staging_rehearsal_blocked` because real Stage3 evidence is still missing.

### Task 7A: Complete first-version single-machine smoke delivery

**Goal:** Ship and validate a first-version single-machine run path before public domain/ICP/HTTPS evidence is available. This is a local/single-server delivery target, not a public production launch or RC tag claim.

**Files:**
- Create: `scripts/single_machine_smoke.py`
- Create: `tests/test_single_machine_smoke.py`
- Create: `docs/SINGLE_MACHINE_FIRST_VERSION_SMOKE.md`
- Modify: this plan document

- [x] **Step 1: Define single-machine acceptance separately from public Stage3**

Single-machine acceptance now means one local machine or one private server can run the backend stack, return `/health` as `ok`, return `/ready` as `ready`, expose required API security headers, and reject unauthenticated access to `/api/v1/auth/me`. It explicitly does not claim public domain, ICP, TLS, RC tag, or full public production readiness.

- [x] **Step 2: Add a repeatable live single-machine smoke script**

Added `scripts/single_machine_smoke.py`, a stdlib-only script that checks:

```text
base_url_scope
health
ready
security_headers
unauthenticated_guard
authenticated_me (optional, skipped unless a bearer token env var is provided)
```

It writes `.xagent_runtime/reports/single-machine-smoke.json` and redacts the optional bearer token by recording only token length.

- [x] **Step 3: Add regression tests for the smoke contract**

Added `tests/test_single_machine_smoke.py` to prove loopback HTTP is accepted, public HTTP is rejected unless explicitly opted in, protected `/api/v1/auth/me` must not be public, and optional bearer token values are not written to evidence.

- [x] **Step 4: Document the operator command**

Added `docs/SINGLE_MACHINE_FIRST_VERSION_SMOKE.md` with copy/paste commands for the single-machine server:

```bash
cd /opt/xagent-stage3/Panda-Agent-RC
python3 scripts/single_machine_smoke.py --base-url http://127.0.0.1:8899 --json
```

Alternative direct API check:

```bash
python3 scripts/single_machine_smoke.py --base-url http://127.0.0.1:8000 --json
```

- [x] **Step 5: Verify local non-domain gates**

Run:

```powershell
python -m pytest tests/test_single_machine_smoke.py tests/test_rc_single_user_local_gate.py tests/test_desktop_first_version_smoke.py tests/test_route_auth_audit.py tests/test_frontend_api_contract_audit.py --no-cov -q
# 24 passed

python scripts/desktop_first_version_smoke.py --json
# status passed

python scripts/route_auth_audit.py --json
# ok true

python scripts/frontend_api_contract_audit.py --json
# ok true

python scripts/security_deployment_gate.py
# OK No deployment-hardening issues found.

python scripts/rc_single_user_local_gate.py --timeout 180
# status passed
```

`python scripts/single_machine_smoke.py --base-url http://127.0.0.1:8000 --json` was also run on the Windows checkout and failed only because no local API process was listening on `127.0.0.1:8000` (`WinError 10061`). This is an environment/live-service absence, not a script or contract failure. Run the live smoke on the single-machine server instead and attach `.xagent_runtime/reports/single-machine-smoke.json` as the evidence.

- [x] **Step 6: Record final single-machine result**

Live single-machine smoke passed on the Ubuntu server `111.228.49.160` using the local NGINX/API endpoint:

```text
single_machine_smoke: passed
generated_at: 2026-06-18T09:31:50Z
server_path: /opt/xagent-stage3/Panda-Agent-RC
base_url: http://127.0.0.1:8899
report: .xagent_runtime/reports/single-machine-smoke.json
health: passed, HTTP 200, {"status":"ok","service":"x-agent"}
ready: passed, HTTP 200, status ready
ready_components: memory ok, trace ok, runs ok, workflows ok, audit ok, qdrant ok, browser ok, observability degraded
security_headers: passed
unauthenticated_guard: passed, /api/v1/auth/me returned 401
authenticated_me: skipped because no bearer token env var was provided
```

The smoke script initially failed under Ubuntu 22.04's Python 3.10 because it used `datetime.UTC`; `scripts/single_machine_smoke.py` was changed to use `datetime.timezone.utc`, and the focused test remains green with `python -m pytest tests/test_single_machine_smoke.py --no-cov -q` (`5 passed`).

Post-review evidence freshness note:

Claude Code correctly identified that a transient `evidence_pack` final-gate failure was caused by report timestamp ordering after `rc_ci_contract.py` rewrote `rc-ci-contract.json`. The local evidence chain was refreshed without claiming owner-verified external evidence:

```powershell
python scripts/rc_refresh_release_chain.py --provider mock --timeout 180
# passed

python scripts/rc_final_gate.py --require-ready-to-tag
# status ready_with_owner_gates

python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json
# failed only on staging_rehearsal_blocked

python -m pytest tests/test_rc_refresh_release_chain.py tests/test_rc_deployment_docs_gate.py tests/test_rc_evidence_pack.py tests/test_rc_release_receipt.py tests/test_rc_final_gate.py --no-cov -q
# 196 passed
```

`docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` and `docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md` now explicitly mention the current final gate status `ready_with_owner_gates`, preserving the boundary that local/single-machine evidence is not full public Stage3 or RC-tag readiness.

### Task 7: Complete Stage3 external evidence after domain/ICP readiness

**Files:**
- Modify only evidence input files already used by `scripts/rc_final_gate.py`
- Do not fake refs

- [ ] **Step 1: Wait for domain/ICP readiness**

Use `www.xiong-agent.com` only after DNS and ICP constraints allow the public HTTPS deployment path.

- [ ] **Step 2: Run HTTPS preflight**

Run:

```powershell
python scripts/stage3_https_preflight.py --domain www.xiong-agent.com
```

Expected: DNS, TLS, `/health`, and `/ready` all pass.

- [ ] **Step 3: Fill real Stage3 evidence refs**

Provide real refs for:

```text
staging_deploy_run
staging_smoke_tests
staging_rollback_rehearsal
staging_observability
staging_environment_protection
```

- [ ] **Step 4: Run strict final gate**

Run:

```powershell
python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal
```

Expected: `ready_for_rc_tag` with Stage3 rehearsal accepted.

- [ ] **Step 5: Commit and tag only after strict gate passes**

Run:

```powershell
git status --porcelain=v1 -uall
git tag -a rc-<date> -m "X-Agent RC after Stage3 evidence"
```

Only tag if the strict gate passes and worktree is clean.
