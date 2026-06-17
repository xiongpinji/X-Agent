# X-Agent Commercial Delivery Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development. Update this document after every completed item with status, command, result, and evidence. Do not record secret values.

**Goal:** Bring X-Agent to first-version commercial delivery readiness with backend security, desktop client, CI/deployment gates, Stage3/production evidence, release artifacts, and operator handoff all verified.

**Architecture:** This is the single delivery ledger for the long-running commercial gate. Each task is promoted only after code change, focused verification, and evidence update. Browser extension work is excluded from first-version delivery and tracked as a future hardening item.

**Tech Stack:** Python 3.11, pytest, FastAPI, Docker Compose, GitHub Actions, Tauri 1.x, Rust, Vue/Vite, Stage3 Ubuntu server.

---

## Status Legend

- `NOT_STARTED`: accepted task, no implementation started.
- `IN_PROGRESS`: actively being changed or verified.
- `FIXED_WAITING_VERIFY`: implementation done, verification not complete.
- `VERIFIED`: acceptance gate passed and evidence recorded.
- `BLOCKED`: cannot proceed without a concrete dependency or owner/operator input.
- `DEFERRED`: intentionally outside first-version commercial delivery.

## Scope Boundary

| Area | First-Version Status | Notes |
|---|---:|---|
| Backend/API auth, RBAC, SAML, workspace, file preview | In scope | Existing focused security evidence is passing; remaining backend debts stay P0/P1. |
| Desktop client `desktop/` | In scope | P0. Must be hardened before commercial delivery. |
| CI and deployment gates | In scope | Release-blocking gates must fail closed. |
| Stage3/production evidence | In scope | Temporary HTTP smoke is not final HTTPS/443 production evidence. |
| Browser extension `extension/` | Deferred | Not shipped, documented, or demoed in first-version delivery. Must be hardened before later release. |

## Delivery Ledger

| ID | Priority | Scope | Status | Owner | Acceptance Gate | Evidence | Last Updated | Next Action |
|---|---|---|---|---|---|---|---|---|
| P0-A | P0 | Desktop Tauri hardening | VERIFIED | Codex | Tauri config forbids null CSP, wildcard shell, broad fs/http allowlists; Rust tests pass. | `python -m pytest tests/test_desktop_tauri_security.py --no-cov -q` -> 8 passed; `cargo check --offline` -> passed with warnings only; `cargo test --offline` -> 8 passed with warnings only. | 2026-06-18 | Keep as regression-protected baseline; restore tray later only with real signed icon assets. |
| P0-B | P0 | Backend remaining security debt | IN_PROGRESS | Codex | Tenant isolation, admin object boundaries, audit HMAC, SSO/OIDC/WebAuthn, path and DNS guards verified. | P0-B1 memory tenant isolation verified; P0-B2 Postgres audit HMAC default-secret removed; P0-B3 MCP file path boundary verified; P0-B4 browser DNS SSRF guard verified; P0-B5 SSO/OIDC/WebAuthn fail-closed verified; P0-B6 API key/user admin object boundaries verified; remaining backend debt pending. | 2026-06-18 | Continue backend security debt burn-down, then run route/security gate set before P0-C. |
| P0-B1 | P0 | Memory API tenant isolation | VERIFIED | Codex | Memory collection/detail/search routes never return other tenant content or counts. | `python -m pytest tests/test_memory_api.py --no-cov -q` -> 3 passed; `python -m pytest tests/test_memory_api.py tests/test_api_browser_desktop_memory.py tests/test_main_api_key_auth.py --no-cov -q` -> 10 passed. | 2026-06-18 | Keep regression test as guard; continue remaining P0-B items. |
| P0-B2 | P0 | Postgres audit HMAC secret handling | VERIFIED | Codex | Postgres audit signatures never use a hardcoded default secret. | `python -m pytest tests/test_audit.py --no-cov -q` -> 7 passed. | 2026-06-18 | Wire any future Postgres audit dependency through configured `audit_hmac_secret`. |
| P0-B3 | P0 | MCP file path boundary | VERIFIED | Codex | MCP file tool rejects `..` sibling-prefix and symlink escapes using resolved path containment. | `python -m pytest tests/test_mcp_components.py --no-cov -q` -> 20 passed, 1 skipped. | 2026-06-18 | Keep sibling-prefix regression mandatory; symlink guard remains covered where OS permits symlink creation. |
| P0-B4 | P0 | Browser DNS SSRF guard | VERIFIED | Codex | Browser navigation blocks literal local/private IPs and DNS names resolving to local/private addresses at API and service layers. | Deterministic guard set: `python -m pytest tests/test_url_safety.py tests/test_browser_service.py::test_browser_client_goto_blocks_private_ip_without_api_layer tests/test_browser_service.py::test_browser_session_close_prevents_further_actions tests/test_security.py::test_browser_goto_blocks_private_ip --no-cov -q` -> 25 passed. | 2026-06-18 | Full `tests/test_browser_service.py` still has a pre-existing real-browser fixture instability on `#name` at example.com; not counted as SSRF failure. |
| P0-B5 | P0 | SSO/OIDC/WebAuthn fail-closed | VERIFIED | Codex | SAML rejects unsigned/forged responses, OIDC requires signature key and nonce validation, WebAuthn placeholders cannot return success. | `python -m pytest tests/test_saml_signature.py tests/enterprise/test_sso.py::TestWebAuthnProvider tests/test_sso_webauthn_fail_closed.py --no-cov -q` -> 25 passed. | 2026-06-18 | Later WebAuthn release requires standards-compliant attestation/assertion verification before enabling endpoints. |
| P0-B6 | P0 | API key/user admin object boundaries | VERIFIED | Codex | `security:manage` is tenant-admin by default; only bootstrap/platform admin can list or mutate cross-tenant API keys/users. | `python -m pytest tests/test_admin_tenant_boundaries.py --no-cov -q` -> 9 passed; `python -m pytest tests/test_admin_tenant_boundaries.py tests/test_security_api_comprehensive.py tests/test_security_authz.py tests/test_api_endpoint_fixes.py --no-cov -q` -> 70 passed; wider P0-B regression set -> 150 passed, 1 skipped. | 2026-06-18 | Keep bootstrap-only platform admin semantics; continue backend security route/gate sweep. |
| P0-C | P0 | CI/deployment trust chain | IN_PROGRESS | Codex | Official commercial gate fails closed and hosted GitHub Actions pass for target SHA. | Local fail-closed CI/deployment/security gate contract verified in P0-C1; hosted GitHub Actions run still pending. | 2026-06-18 | Push/trigger hosted Commercial RC Gate for the selected release SHA after commit boundary is owner-approved. |
| P0-C1 | P0 | Local CI/deployment/security gate contract | VERIFIED | Codex | Commercial RC workflow runs route auth audit, deployment hardening gate, and production hardening gate fail-closed; tests catch missing or fail-open gate commands. | `python -m pytest tests/test_rc_ci_contract.py tests/test_ci_workflow_hardening.py tests/test_stage3_staging_rehearsal_workflow_contract.py tests/test_deployment_hardening.py tests/test_production_hardening_gate.py tests/test_route_auth_audit.py --no-cov -q` -> 58 passed; `python scripts/rc_ci_contract.py` -> passed; `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`; `python scripts/security_deployment_gate.py` -> OK; `python scripts/production_hardening_gate.py` -> ready, 0 findings. | 2026-06-18 | Keep as hosted CI contract; next P0-C step is external Actions evidence. |
| P0-D | P0 | Stage3/production evidence | BLOCKED | Codex + Owner | HTTPS/443, domain/TLS, full stack smoke, observability decision, owner intake, final gate pass. | `.xagent_runtime/reports/stage3-http-smoke-608e529-20260618.json` is temporary HTTP evidence only. | 2026-06-18 | Resume after CI/deploy and domain/TLS path are ready. |
| P1-A | P1 | Dirty worktree classification | NOT_STARTED | Codex | 526 changed/untracked items classified without destructive cleanup. | `git status --porcelain=v1 -uall` count observed: 526. | 2026-06-18 | Classify after P0 blockers. |
| P1-B | P1 | Release docs and customer handoff | NOT_STARTED | Codex | Release notes, runbook, quickstart, rollback and support boundaries match verified product. | Pending | 2026-06-18 | Update after final gate evidence. |
| P2-A | P2 | Browser extension future hardening | DEFERRED | Future iteration | Extension is not shipped in first version; later release requires separate security work. | `extension/` excluded by scope decision. | 2026-06-18 | Keep out of release package/docs. |

## Current Evidence Baseline

- Focused auth/RBAC/SAML/path-boundary security matrix previously reverified as passing in `audit_reports/FINAL_MULTI_AGENT_REVERIFY_20260617.md`.
- Route audit previously reverified as `{"issues":[],"ok":true}`.
- Deployment hardening gate previously reverified as passing.
- Commercial RC workflow now has a local contract requiring route auth audit, deployment hardening, and production hardening gates to run fail-closed.
- Stage3 SHA `608e52924f965f7a3289c24349110089a81cc99d` has temporary HTTP health/ready smoke passing, but final GA still needs HTTPS/443 and full stack evidence.
- Current workspace is dirty; do not reset, clean, or revert unrelated changes.

## Execution Log

### 2026-06-18 P0-A Desktop Tauri Hardening

- Changed desktop Tauri allowlist to enable CSP, disable arbitrary shell execution and sidecars, scope filesystem access to `$APPDATA/com.xagent.desktop/**`, and restrict Tauri HTTP requests to `http://127.0.0.1:8000/**` and `http://localhost:8000/**`.
- Replaced broad Tauri Cargo features `fs-all` and `http-all` with explicit fs/http features and added missing declared dependencies already referenced by desktop Rust code: `dirs`, `futures`, and `sha2`.
- Added backend URL/path validation helpers in `desktop/src/security.rs`; desktop API, agent, and IPC network calls now build URLs through the shared local-backend-only helper.
- Added `tests/test_desktop_tauri_security.py` to prevent regression to `csp:null`, wildcard shell scope, HOME-wide fs scope, broad HTTP scope, or broad Tauri Cargo features.
- Verification completed:
  - `python -m pytest tests/test_desktop_tauri_security.py --no-cov -q` -> 8 passed.
  - Static config summary confirms `csp_is_null=false`, `shell.execute=false`, `shell.sidecar=false`, `fs.all=false`, app-data-only fs scope, and local-backend-only HTTP scope.
- Rust verification completed:
  - `cargo check --offline` -> passed with warnings only.
  - `cargo test --offline` -> 8 passed with warnings only.
- Removed the Tauri system tray wiring from the first-version desktop build because the repo did not contain the required tray icon resources and it blocked build verification. It can be restored later with real signed icon assets and matching tests.

### 2026-06-18 P0-B1 Memory API Tenant Isolation

- Fixed memory collection paths that could expose cross-tenant data in the in-memory backend:
  - `POST /api/v1/memory/search` fallback path now filters `layer_items()` by `principal.tenant_id`.
  - `GET /api/v1/memory/layers/{layer}` now returns only current-tenant items and count.
  - `GET /api/v1/memory/sessions/{session_id}` now returns 404 for another tenant's session and rebuilds summary/layers from current-tenant items.
  - `GET /api/v1/memory/layers` and `GET /api/v1/memory/count` now use tenant-scoped layer/session counts when the backend supports them.
- Added tenant-aware optional parameters to `MemorySystem.layer_counts()`, `layer_summary()`, `session_count()`, and `snapshot()` while preserving the previous global behavior when no tenant is passed.
- Added regression coverage in `tests/test_memory_api.py` that seeds tenant A and tenant B memory items, then proves tenant A cannot read tenant B content through layer detail, fallback search, count, or session detail.
- Verification completed:
  - `python -m pytest tests/test_memory_api.py --no-cov -q` -> 3 passed.
  - `python -m pytest tests/test_memory_api.py tests/test_api_browser_desktop_memory.py tests/test_main_api_key_auth.py --no-cov -q` -> 10 passed.

### 2026-06-18 P0-B2 Postgres Audit HMAC Secret Handling

- Removed the hardcoded `default-secret` signing key from `backend/app/core/audit_postgres.py`.
- `PostgresAuditStore` now accepts `hmac_secret` at construction time and signs only when a real configured secret is supplied, matching the file-backed audit store semantics.
- Added regression coverage in `tests/test_audit.py` proving the Postgres audit signature is not the `default-secret` HMAC and that a missing secret does not silently sign records.
- Verification completed:
  - `python -m pytest tests/test_audit.py --no-cov -q` -> 7 passed.

### 2026-06-18 P0-B3 MCP File Path Boundary

- Replaced MCP file tool string-prefix containment with resolved `Path.relative_to()` in `backend/app/core/mcp/tools/file_tool.py`.
- Added regression tests in `tests/test_mcp_components.py`:
  - sibling-prefix escape such as `../workspace-evil/secret.txt` is rejected;
  - symlink escape is rejected when the OS/test runner permits symlink creation.
- Verification completed:
  - `python -m pytest tests/test_mcp_components.py --no-cov -q` -> 20 passed, 1 skipped.

### 2026-06-18 P0-B4 Browser DNS SSRF Guard

- Added resolver-backed browser navigation URL validation in `backend/app/core/url_safety.py`.
  - Allows only HTTP/HTTPS URLs without credentials.
  - Blocks literal localhost/private/link-local/reserved/multicast/unspecified addresses.
  - Resolves hostname targets and fails closed when DNS cannot be resolved.
  - Blocks DNS names that resolve to private or local address ranges.
- Reused the shared guard in `backend/app/api/browser.py`.
- Added a second service-layer guard in `backend/app/services/browser/playwright_client.py` so direct browser client calls cannot bypass the API route.
- Added regression coverage:
  - `tests/test_url_safety.py` covers DNS rebinding to `127.0.0.1`, public resolved IPs, and DNS fail-closed behavior using injected resolvers.
  - `tests/test_browser_service.py` covers direct low-level private-IP navigation blocking.
  - Existing `tests/test_security.py::test_browser_goto_blocks_private_ip` continues to cover API-level private IP blocking.
- Verification completed:
  - `python -m pytest tests/test_url_safety.py tests/test_browser_service.py::test_browser_client_goto_blocks_private_ip_without_api_layer tests/test_browser_service.py::test_browser_session_close_prevents_further_actions tests/test_security.py::test_browser_goto_blocks_private_ip --no-cov -q` -> 25 passed.
- Note:
  - Full `tests/test_browser_service.py` currently fails one pre-existing real-browser test because it navigates to `https://example.com` and then expects `#name` to exist. This is unrelated to the SSRF guard and should be stabilized separately.

### 2026-06-18 P0-B5 SSO/OIDC/WebAuthn Fail-Closed

- `backend/app/core/saml_sso.py`
  - `SAMLManager.parse_response()` now raises when XMLDSig verification returns false instead of returning an assertion with `signature_valid=false`.
  - `OIDCManager.decode_id_token()` no longer decodes with `verify_signature=False`; callers must provide a verification key and optional nonce, and issuer/audience are validated from config/discovery where enabled.
- `backend/app/core/sso/webauthn_provider.py`
  - WebAuthn registration fails closed by default until real attestation verification is implemented.
  - WebAuthn authentication always rejects placeholder signatures until standards-compliant assertion verification is implemented.
  - A clearly named test-only config flag allows exercising stored credential flows without pretending it is production verification.
- `backend/app/api/sso.py`
  - Placeholder WebAuthn handlers now raise 501 instead of returning fake challenge IDs, `registered=true`, or fake access tokens. This router is not currently mounted, but future mounting will fail closed.
- Verification completed:
  - `python -m pytest tests/test_saml_signature.py tests/enterprise/test_sso.py::TestWebAuthnProvider tests/test_sso_webauthn_fail_closed.py --no-cov -q` -> 25 passed.

### 2026-06-18 P0-B6 API Key/User Admin Object Boundaries

- Added explicit bootstrap/platform-admin detection in `backend/app/core/security.py`. A principal is platform admin only when authenticated with `api_key_id="bootstrap"`; ordinary `security:manage` principals remain tenant administrators.
- Hardened `backend/app/api/security.py`:
  - `GET /api/v1/security/api-keys` and `/api-keys/expiring-soon` return only current-tenant keys for non-platform admins.
  - `GET`, `DELETE`, and `POST /revoke` for API keys return 404 and do not mutate records when the key belongs to another tenant.
  - Non-platform API key creation ignores caller-supplied `tenant_id` and `user_id`, binds to the principal tenant/user, and intersects requested/default role scopes with the caller's actual scopes while using a custom role to avoid role-default scope expansion.
- Hardened `backend/app/api/users.py`:
  - list/get/update/role/activity/delete are scoped to `principal.tenant_id` for tenant admins.
  - create/update ignore caller-supplied `tenant_id` for tenant admins.
  - user activity now receives `AuditStore` via FastAPI dependency injection and filters activity by tenant for tenant admins.
- Added `tests/test_admin_tenant_boundaries.py` with route-level regression coverage for cross-tenant list/get/revoke/delete/update/activity denial and bootstrap cross-tenant visibility.
- Updated existing security API mock tests so test records carry the tenant expected by the injected principal and destructive mock paths provide `list()` data for the new object-visibility guard.
- Verification completed:
  - `python -m pytest tests/test_admin_tenant_boundaries.py --no-cov -q` -> 9 passed.
  - `python -m pytest tests/test_admin_tenant_boundaries.py tests/test_security_api_comprehensive.py tests/test_security_authz.py tests/test_api_endpoint_fixes.py --no-cov -q` -> 70 passed.
  - `python -m pytest tests/test_admin_tenant_boundaries.py tests/test_memory_api.py tests/test_audit.py tests/test_mcp_components.py tests/test_url_safety.py tests/test_browser_service.py::test_browser_client_goto_blocks_private_ip_without_api_layer tests/test_browser_service.py::test_browser_session_close_prevents_further_actions tests/test_security.py::test_browser_goto_blocks_private_ip tests/test_saml_signature.py tests/enterprise/test_sso.py::TestWebAuthnProvider tests/test_sso_webauthn_fail_closed.py tests/test_security_api_comprehensive.py tests/test_security_authz.py tests/test_api_endpoint_fixes.py --no-cov -q` -> 150 passed, 1 skipped.

### 2026-06-18 P0-C1 Local CI/Deployment/Security Gate Contract

- Hardened `.github/workflows/commercial-rc.yml` so the commercial RC job directly runs:
  - `python scripts/route_auth_audit.py --json > .xagent_runtime/reports/route-auth-audit.json`
  - `python scripts/security_deployment_gate.py`
  - `python scripts/production_hardening_gate.py`
- Extended `scripts/rc_ci_contract.py` so the workflow contract requires those gate scripts in `py_compile`, the targeted pytest group, the direct gate-command step, and uploaded evidence paths. The contract also rejects fail-open variants such as `|| true` or `--allow-blocked` for the production hardening gate.
- Added `tests/test_ci_workflow_hardening.py` and expanded `tests/test_rc_ci_contract.py` to prove CI fails when the route auth, deployment hardening, or production hardening gates are removed or made fail-open.
- Hardened `.github/workflows/test.yml` by pinning all Qdrant service images to `qdrant/qdrant:v1.7.0`, removing PR fail-open behavior from integration tests, and making the test summary report actual `needs.*.result` values instead of hardcoded success marks.
- Verification completed:
  - `python -m pytest tests/test_rc_ci_contract.py tests/test_ci_workflow_hardening.py --no-cov -q` -> 18 passed.
  - `python scripts/rc_ci_contract.py` -> passed.
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> `Production hardening gate status: ready`, `Findings: 0`.
  - `python -m pytest tests/test_rc_ci_contract.py tests/test_ci_workflow_hardening.py tests/test_stage3_staging_rehearsal_workflow_contract.py tests/test_deployment_hardening.py tests/test_production_hardening_gate.py tests/test_route_auth_audit.py --no-cov -q` -> 58 passed.
  - `python -m py_compile scripts/rc_ci_contract.py scripts/route_auth_audit.py scripts/security_deployment_gate.py scripts/production_hardening_gate.py` -> passed.
- Claim boundary:
  - This verifies local CI contract and gate behavior only.
  - P0-C remains `IN_PROGRESS` until a hosted GitHub Actions Commercial RC Gate run passes for the selected release SHA.

## Update Rules

- Update this document after each task transition.
- Evidence must include command, result, and file/link reference.
- Never write secret values. Use configured/not configured, length, or external reference only.
- Do not mark commercial delivery complete until `rc_final_gate.py --require-ready-to-tag` passes against final evidence.
