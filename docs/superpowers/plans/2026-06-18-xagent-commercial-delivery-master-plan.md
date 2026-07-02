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
| P0-A | P0 | Desktop Tauri hardening | VERIFIED | Codex | Tauri config forbids null CSP, wildcard shell, broad fs/http allowlists; Rust tests pass. | Latest refresh: `python -m pytest tests/test_desktop_tauri_security.py --no-cov -q` -> 8 passed; `cargo check --offline` -> passed with warnings only; `cargo test --offline` -> 8 passed with warnings only. | 2026-06-18 | Keep as regression-protected baseline; restore tray later only with real signed icon assets. |
| P0-B | P0 | Backend remaining security debt | VERIFIED | Codex + ZCode pending board sync | Tenant isolation, admin object boundaries, audit HMAC, SSO/OIDC/WebAuthn, path and DNS guards verified; legacy ZCode P0 task verifiers pass. | P0-B1..P0-B6 verified; `$env:PYTHONIOENCODING='utf-8'; python audit_reports/verify_fixes.py P0-01/P0-03/P0-04/P0-06` -> P0-01 5/0, P0-03 4/0, P0-04 2/0, P0-06 1/0; `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`. | 2026-06-18 | Ask ZCode to sync stale `AGENTS.md` task-board status; keep backend route/security gates in final RC regression. |
| P0-B1 | P0 | Memory API tenant isolation | VERIFIED | Codex | Memory collection/detail/search routes never return other tenant content or counts. | `python -m pytest tests/test_memory_api.py --no-cov -q` -> 3 passed; `python -m pytest tests/test_memory_api.py tests/test_api_browser_desktop_memory.py tests/test_main_api_key_auth.py --no-cov -q` -> 10 passed. | 2026-06-18 | Keep regression test as guard; continue remaining P0-B items. |
| P0-B2 | P0 | Postgres audit HMAC secret handling | VERIFIED | Codex | Postgres audit signatures never use a hardcoded default secret. | `python -m pytest tests/test_audit.py --no-cov -q` -> 7 passed. | 2026-06-18 | Wire any future Postgres audit dependency through configured `audit_hmac_secret`. |
| P0-B3 | P0 | MCP file path boundary | VERIFIED | Codex | MCP file tool rejects `..` sibling-prefix and symlink escapes using resolved path containment. | `python -m pytest tests/test_mcp_components.py --no-cov -q` -> 20 passed, 1 skipped. | 2026-06-18 | Keep sibling-prefix regression mandatory; symlink guard remains covered where OS permits symlink creation. |
| P0-B4 | P0 | Browser DNS SSRF guard | VERIFIED | Codex | Browser navigation blocks literal local/private IPs and DNS names resolving to local/private addresses at API and service layers. | Deterministic guard set: `python -m pytest tests/test_url_safety.py tests/test_browser_service.py::test_browser_client_goto_blocks_private_ip_without_api_layer tests/test_browser_service.py::test_browser_session_close_prevents_further_actions tests/test_security.py::test_browser_goto_blocks_private_ip --no-cov -q` -> 25 passed. | 2026-06-18 | Full `tests/test_browser_service.py` still has a pre-existing real-browser fixture instability on `#name` at example.com; not counted as SSRF failure. |
| P0-B5 | P0 | SSO/OIDC/WebAuthn fail-closed | VERIFIED | Codex | SAML rejects unsigned/forged responses, OIDC requires signature key and nonce validation, WebAuthn placeholders cannot return success. | `python -m pytest tests/test_saml_signature.py tests/enterprise/test_sso.py::TestWebAuthnProvider tests/test_sso_webauthn_fail_closed.py --no-cov -q` -> 25 passed. | 2026-06-18 | Later WebAuthn release requires standards-compliant attestation/assertion verification before enabling endpoints. |
| P0-B6 | P0 | API key/user admin object boundaries | VERIFIED | Codex | `security:manage` is tenant-admin by default; only bootstrap/platform admin can list or mutate cross-tenant API keys/users. | `python -m pytest tests/test_admin_tenant_boundaries.py --no-cov -q` -> 9 passed; `python -m pytest tests/test_admin_tenant_boundaries.py tests/test_security_api_comprehensive.py tests/test_security_authz.py tests/test_api_endpoint_fixes.py --no-cov -q` -> 70 passed; wider P0-B regression set -> 150 passed, 1 skipped. | 2026-06-18 | Keep bootstrap-only platform admin semantics; continue backend security route/gate sweep. |
| P0-C | P0 | CI/deployment trust chain | VERIFIED | Codex | Official commercial gate fails closed and hosted GitHub Actions pass for target SHA. | Local fail-closed CI/deployment/security gate contract verified in P0-C1; latest hosted Commercial RC Gate run `27717463270` passed for SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf` on branch `codex/p0-c-ci-deployment-gates`. | 2026-06-18 | Continue to P0-D Stage3/production evidence and owner-final gate; do not treat CI pass alone as commercial release complete. |
| P0-C1 | P0 | Local CI/deployment/security gate contract | VERIFIED | Codex | Commercial RC workflow runs route auth audit, deployment hardening gate, and production hardening gate fail-closed; tests catch missing or fail-open gate commands. | `python -m pytest tests/test_rc_ci_contract.py tests/test_ci_workflow_hardening.py tests/test_stage3_staging_rehearsal_workflow_contract.py tests/test_deployment_hardening.py tests/test_production_hardening_gate.py tests/test_route_auth_audit.py --no-cov -q` -> 58 passed; `python scripts/rc_ci_contract.py` -> passed; `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`; `python scripts/security_deployment_gate.py` -> OK; `python scripts/production_hardening_gate.py` -> ready, 0 findings. | 2026-06-18 | Keep as hosted CI contract; next P0-C step is external Actions evidence. |
| P0-C2 | P0 | Hosted Commercial RC Gate evidence | VERIFIED | Codex | GitHub Actions Commercial RC Gate passes on the RC repository branch containing the CI/deployment hardening commits. | [Commercial RC Gate run 27717463270](https://github.com/xiongpinji/Panda-Agent-RC/actions/runs/27717463270) -> success; head SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`; jobs `commercial-rc-linux` and `commercial-rc-windows-installer` both success. | 2026-06-18 | Use this as CI evidence for P0-D/owner gate; final release still requires Stage3 HTTPS/full-stack evidence and final gate. |
| P0-D | P0 | Stage3/production evidence | IN_PROGRESS | Codex + Owner | HTTPS/443, domain/TLS, full stack smoke, observability decision, owner intake, final gate pass. | Owner-controlled external gates now pass and `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`; strict commercial Stage3 gate now fail-closes with `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json` -> expected failure only on `staging_rehearsal_blocked`; rehearsal report is bound to release SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`, but its evidence slots remain blocked for `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`; Stage3 HTTP smoke still passes on `http://111.228.49.160:8899`, but HTTPS/443 probes fail TLS handshake and the five-report Stage3 intake keeps all five Stage3 evidence outputs blocked until real external references are supplied; `python scripts/stage3_owner_evidence_todo.py` now extracts the blocked owner draft into a no-secret 32-item Markdown todo list. | 2026-06-18 | Provision real HTTPS/443 and either configure observability or record an explicit first-RC observability acceptance, then rerun Stage3/full-stack smoke, regenerate the owner todo, fill the owner draft with references only, run intake, run Stage3 rehearsal for SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`, and rerun strict final gate. |
| P0-D1 | P0 | Owner external smoke and RC final gate | VERIFIED | Codex + Owner | DeepSeek provider, Feishu webhook contract, GitHub issue dry-run/execute preflight, hosted Actions evidence, owner checklist, release chain, and final gate all pass without recording secret values. | `python scripts/rc_external_smoke.py --provider deepseek --check provider --check feishu_webhook_contract --check github_issue_to_pr_dry_run --check github_issue_to_pr_execute_preflight --check hosted_github_actions_run --require-configured --github-execute-preflight --github-actions-preflight --timeout 40` -> passed; `python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60` -> passed; `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`. | 2026-06-18 | Keep this as verified owner-gate evidence; do not rerun unless inputs or release SHA change. |
| P0-D2 | P0 | Stage3 HTTPS/observability/environment evidence | IN_PROGRESS | Codex + Owner | Public Stage3 endpoint proves HTTPS/443 domain/TLS, ready health, release-bound deploy/smoke/rollback, observability, and environment protection evidence. | HTTP `http://111.228.49.160:8899/health` and `/ready` -> 200 OK; `https://111.228.49.160/health` and `https://xagent.111.228.49.160.sslip.io/{health,ready}` -> TLS handshake failure; owner screenshot shows a DNS console row for `www -> 111.228.49.160`, but public DNS still does not see the zone or record: `Resolve-DnsName www.xiong-agent.com`, default `nslookup`, `nslookup www.xiong-agent.com 8.8.8.8`, AliDNS `223.5.5.5`, 114DNS, and gTLD authoritative server `a.gtld-servers.net` all returned NXDOMAIN/no resolved address on 2026-06-18; `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com` -> `stage3_https_preflight_blocked` with DNS/TLS/health/ready checks failing on `getaddrinfo failed`; intake now generates and validates all five Stage3 evidence outputs: `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`; intake rejects HTTP, localhost, bare IPs, temporary wildcard DNS such as `sslip.io`, missing `/health` and `/ready` refs, local-only deploy/smoke/rollback refs, and template evidence; owner draft helper now writes beginner fill order, owner-vs-Codex responsibility split, exact JSON fields, and optional `--https-preflight-report` prefill for endpoint/DNS/TLS/health/ready refs while keeping drafts blocked; `scripts/stage3_owner_evidence_todo.py` writes `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.json/.md` and currently reports `stage3_owner_evidence_todo_ready` with 32 remaining no-secret items: 3 final toggles, 21 operator refs, 4 Codex-prefill refs, 3 owner decisions, and 1 owner secret-reference confirmation; `scripts/stage3_https_preflight.py` now provides read-only DNS/TLS/health/ready preflight reports and correctly blocks `sslip.io`; `scripts/stage3_owner_domain_guide.py` now generates a no-secret DNS/Nginx/Certbot/preflight/draft/final-gate guide, auto-detects the owner-verified hosted Actions `head_sha` from `.xagent_runtime/reports/rc-external-smoke.json`, and blocks bare IP/localhost/sslip inputs without performing mutations; `rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal` now requires the rehearsal `release_sha` to match owner-verified hosted Actions `head_sha`; `commercial_environment_rehearsal_gate.py` now requires intake-backed metadata for `staging_observability`/`staging_environment_protection` and real external-environment metadata for `staging_deploy_run`/`staging_smoke_tests`/`staging_rollback_rehearsal`, so handwritten ready JSON or local staging-equivalent evidence cannot satisfy Stage3. Current rehearsal remains blocked for all five Stage3 evidence slots. | 2026-06-18 | Fix domain registration/NS delegation/DNS provider binding for `xiong-agent.com` until public resolvers return `www.xiong-agent.com -> 111.228.49.160`; only then configure Nginx HTTPS/443 from `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.md`, rerun `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com`, update owner draft with `--https-preflight-report`, rerun intake, run `scripts/commercial_environment_rehearsal_gate.py --environment staging --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf`, and rerun strict final gate. |
| P1-A | P1 | Dirty worktree classification | VERIFIED | Codex | Changed/untracked items classified without destructive cleanup, with release-risk exclusions called out. | `git status --porcelain=v1 -uall` -> 528 items: 144 modified, 384 untracked; RC include/defer/exclude coverage command -> `total=528 unclassified=0`; explicit excludes are `deployment/kubernetes/secret.yaml` and `{r['assigned_to']}`; `.mcp.json` and AGENTS/blackboard/session coordination artifacts are internal-only; root tooling/deps, generated packets, broad nonsecurity backend changes, unrelated scripts/tests, and owner-review docs/assets are not first-RC runtime payload by default. | 2026-06-18 | Enforce this manifest during final RC bundle assembly after P0-D2 domain/TLS evidence is available; any backend P0 file with unfinished ZCode task-board status remains blocked from RC promotion until verified. |
| P1-B | P1 | Release docs and customer handoff | IN_PROGRESS | Codex | Release notes, runbook, quickstart, rollback and support boundaries match verified product. | Deployment docs, release notes, README deliverables, runbook, checklist, and diff review now avoid secret-looking examples, align with desktop-in/browser-extension-deferred scope, and no longer present historical Ollama attempts as current commercial evidence; `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` now includes Stage3 owner domain guide, Stage3 HTTPS evidence, `python scripts/stage3_owner_evidence_todo.py`, `python scripts/stage3_owner_quickstart.py`, strict Stage3 rehearsal final-gate instructions, owner-verified hosted Actions `head_sha` binding, and `--https-preflight-report` owner-draft prefill for non-expert owner/operator use; `scripts/rc_deployment_docs_gate.py` now requires the Stage3 owner-domain guide command, Stage3 HTTPS preflight command, owner-evidence todo command/output reports, owner quickstart command/output reports, preflight-to-draft token, strict `--require-stage3-rehearsal` final-gate command, release-SHA binding language, and current DeepSeek owner-verified refresh path; `python -m pytest tests/test_stage3_owner_domain_guide.py tests/test_stage3_https_preflight.py tests/test_stage3_owner_quickstart.py tests/test_stage3_owner_evidence_todo.py tests/test_rc_deployment_docs_gate.py tests/test_rc_evidence_pack.py tests/test_rc_final_gate.py --no-cov -q` -> 163 passed; `www.xiong-agent.com` domain guide and quickstart generated; `stage3_https_preflight.py --domain www.xiong-agent.com` correctly reports `stage3_https_preflight_blocked` because DNS currently returns NXDOMAIN/no resolved addresses; latest evidence pack `x-agent-commercial-rc-evidence-20260618T023728Z.zip` sha256 `6e8cea4dcc7ba4f231d95f8478fc2942fceeb12113eaa3f1a1261fd55cd309de`, 31 files; `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`; strict Stage3 final gate remains blocked as expected on missing Stage3 external evidence only. | 2026-06-18 | Create DNS A record `www.xiong-agent.com -> 111.228.49.160`, wait for DNS propagation, rerun `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com`, then configure HTTPS/443 and continue Stage3 intake/rehearsal. |
| P2-A | P2 | Browser extension future hardening | DEFERRED | Future iteration | Extension is not shipped in first version; later release requires separate security work. | `extension/` excluded by scope decision. | 2026-06-18 | Keep out of release package/docs. |

## Current Evidence Baseline

- Focused auth/RBAC/SAML/path-boundary security matrix previously reverified as passing in `audit_reports/FINAL_MULTI_AGENT_REVERIFY_20260617.md`.
- Route audit previously reverified as `{"issues":[],"ok":true}`.
- Deployment hardening gate previously reverified as passing.
- Commercial RC workflow now has a local contract requiring route auth audit, deployment hardening, and production hardening gates to run fail-closed.
- Hosted Commercial RC Gate evidence is now available for RC branch `codex/p0-c-ci-deployment-gates`: latest verified run `27717463270`, SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`, conclusion `success`.
- Owner external gates are now verified for the current RC evidence chain: DeepSeek provider smoke, Feishu webhook contract smoke, GitHub issue dry-run/execute preflight, and hosted Actions run verification all passed with redacted reports.
- Stage3 SHA `608e52924f965f7a3289c24349110089a81cc99d` has temporary HTTP health/ready smoke passing on port `8899`, but final GA still needs HTTPS/443 and release-bound Stage3 evidence.
- Local RC final gate is currently green for the owner-verified refreshed evidence chain: `python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60` -> passed, then `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`. This does not substitute for the P0-D2 HTTPS/full-stack Stage3 evidence requirement.
- Latest Stage3 external evidence intake generates all five Stage3 evidence reports and remains blocked until real release-bound external references are supplied for `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`; owner external gates are no longer the blocker.
- A redaction-safe owner evidence draft now exists at `.xagent_runtime/reports/stage3-staging-external-evidence-owner-draft-20260616.json` and `.xagent_runtime/reports/stage3-staging-external-evidence-owner-draft-20260616.md`; it includes beginner fill order, owner-vs-Codex responsibility split, and exact JSON fields to replace; it is explicitly marked `template_not_external_evidence=true` and is not accepted as real Stage3 proof.
- A no-secret owner todo extractor now exists at `scripts/stage3_owner_evidence_todo.py`; the latest `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.json/.md` reports `stage3_owner_evidence_todo_ready` with 32 remaining items and no mutation/deploy/workflow/secret recording.
- A no-secret owner quickstart now exists at `scripts/stage3_owner_quickstart.py`; the latest `.xagent_runtime/reports/stage3-owner-quickstart-20260618.json/.md` reports `stage3_owner_quickstart_ready`, reduces Stage3 owner work into six steps, and records no mutation/deploy/workflow dispatch/raw secret values.
- A read-only Stage3 HTTPS preflight tool now exists at `scripts/stage3_https_preflight.py`; it writes `.xagent_runtime/reports/stage3-https-preflight-20260618.json/.md`, rejects temporary wildcard DNS/bare IP/localhost/non-HTTPS shapes, verifies DNS points to `111.228.49.160`, requires trusted TLS on port 443, and requires `/health` status `ok` plus `/ready` status `ready`.
- Stage3 rehearsal gate now requires `staging_observability` and `staging_environment_protection` reports to carry intake-backed external-evidence metadata: `real_external_evidence_collected=true`, non-template status, an external input path, no intake side effects, no raw secret values, and passed intake checks. Handwritten ready JSON is no longer enough for those two slots.
- Stage3 rehearsal gate now also requires `staging_deploy_run`, `staging_smoke_tests`, and `staging_rollback_rehearsal` to carry real external-environment metadata: `real_external_evidence_collected=true`, `environment=staging`, external evidence refs/URLs, passed checks, no template/raw-secret/workflow/tag/release side effects, and no `local_staging_equivalent`/`controlled_pilot`/template evidence class or claim boundary forbidding external Stage3 use.
- Current workspace is dirty; do not reset, clean, or revert unrelated changes.
- Dirty-worktree RC routing now has full coverage for the current 528 entries: `total=528 unclassified=0`. This is a release packaging control, not a cleanup or staging action.
- Legacy ZCode task-board P0 checks now pass locally with UTF-8 output enabled: P0-01, P0-03, P0-04, and P0-06 all report zero failed verifier checks. `AGENTS.md` still has stale statuses until ZCode updates the board.
- Real domain candidate `www.xiong-agent.com` is now recorded in `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.json/.md` and `.xagent_runtime/reports/stage3-owner-quickstart-20260618.json/.md`; DNS now resolves to `111.228.49.160`, but HTTP/80 is intercepted by JD Cloud `JDTP` and HTTPS/443 connection is refused until the new-domain ICP/provider access window clears and trusted HTTPS is configured.
- Latest Stage3 HTTPS preflight report `.xagent_runtime/reports/stage3-https-preflight-20260618.json/.md` reports `stage3_https_preflight_blocked` with `domain_shape=passed`, `dns_points_to_expected_ip=passed`, and failures only on `trusted_https_tls`, `https_health_probe`, and `https_ready_probe`; its `next_actions` now correctly point to HTTPS/443/cloud-provider access and `/health` `/ready`, not DNS repair.
- Latest evidence pack after the non-domain local closeout refresh is machine-recorded in `.xagent_runtime/reports/rc-evidence-pack.json`; use that report's `output_path`, `pack_sha256`, and `file_count` as the current source of truth, including the refreshed Stage3 preflight and owner quickstart/todo reports.
- Current non-domain closeout boundary for multi-model audit: local auth/RBAC/route guard, deployment hardening, production hardening, deployment docs, release receipt, evidence pack, and non-strict RC final gate are green; strict commercial final gate must remain blocked only on real Stage3 rehearsal evidence until domain HTTPS/443 and owner/operator external references exist.

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

### 2026-06-18 P0-C2 Hosted Commercial RC Gate Evidence

- Pushed the P0-C CI/deployment trust-chain commits to the RC repository branch `codex/p0-c-ci-deployment-gates`.
- Initial hosted runs failed usefully:
  - Run `27711438390` failed at static checks because the newly required gate scripts were not yet committed to the RC branch.
  - Run `27711660654` failed at RC smoke collection because `route_auth_audit.py` imported `get_refresh_principal` as a hard requirement while the remote auth baseline did not yet expose that symbol.
  - Run `27711885828` failed because deployment hardening tests found real HIGH findings in remote deployment/monitoring/template files.
  - Run `27712160209` passed RC smoke and security/deployment gates, then failed in `codex_hermes_gap_matrix.py` because issue-to-PR API tests still assumed unauthenticated access after P0-04 route hardening.
- Fixed the above without relaxing security:
  - Added the missing local gate scripts and tests to the RC branch.
  - Made `route_auth_audit.py` tolerate older auth baselines by detecting refresh principal by dependency name when the object import is unavailable.
  - Committed deployment/monitoring/template hardening changes so hosted `security_deployment_gate.py` and `production_hardening_gate.py` pass.
  - Updated `tests/test_issue_to_pr_api.py` to use API-key auth for the RBAC-protected dry-run/execute paths while preserving the CSRF negative test for browser-style unauthenticated requests.
- Verification completed:
  - `python -m pytest tests/test_issue_to_pr_pipeline.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts= -o timeout=0 -o faulthandler_timeout=0 -p no:cov -q` -> 10 passed.
  - `python -m pytest tests/test_sessions_skills_issuepr_auth.py --no-cov -q` -> 17 passed.
  - Hosted [Commercial RC Gate run 27712888135](https://github.com/xiongpinji/Panda-Agent-RC/actions/runs/27712888135) -> success for SHA `c99598749b45cffe9cce54d4a0f44172a741782d`.
  - Follow-up docs-only commit `dbd01763e88b2cfd9947b202f92e70473e667816` triggered hosted [Commercial RC Gate run 27713214579](https://github.com/xiongpinji/Panda-Agent-RC/actions/runs/27713214579) -> success.
  - Latest hosted job results for run `27713214579`: `commercial-rc-linux` success and `commercial-rc-windows-installer` success.
- Claim boundary:
  - P0-C CI/deployment trust chain is verified for the RC branch/SHA above.
  - This is not final commercial release approval. P0-D still needs Stage3/production evidence, HTTPS/443/domain/TLS/full-stack smoke evidence, and final owner gate/final gate handling.

### 2026-06-18 P0-D Stage3 And Final Gate Stabilization

- Rechecked live temporary Stage3 endpoint:
  - `curl.exe -i --max-time 15 http://111.228.49.160:8899/health` -> 200 OK.
  - `curl.exe -i --max-time 15 http://111.228.49.160:8899/ready` -> 200 OK with `status=ready`, `audit=ok`, `qdrant=ok`, `browser=ok`, and `observability=degraded`.
  - `curl.exe -k -i --max-time 15 https://111.228.49.160/health` -> TLS handshake failure.
- Re-ran Stage3 external evidence intake for hosted RC SHA `dbd01763e88b2cfd9947b202f92e70473e667816`:
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --current-head-sha dbd01763e88b2cfd9947b202f92e70473e667816 --release-sha dbd01763e88b2cfd9947b202f92e70473e667816 --force` -> blocked for `staging_observability` and `staging_environment_protection`.
- Stabilized the local final gate chain:
  - Updated `docs/RC_RELEASE_DIFF_REVIEW.md` from the stale `131 candidate files` evidence line to `145 candidate files`.
  - Refreshed Codex/Hermes gap evidence with `python scripts/codex_hermes_gap_matrix.py --write-report` -> passed for all 9 categories.
  - Tightened `scripts/rc_evidence_pack.py` so public `xagent-...` artifact/path names are not treated as token leaks while `xagent_...` token-like values still fail the evidence secret scan.
  - Added regression coverage in `tests/test_rc_evidence_pack.py`.
- Verification completed:
  - `python -m pytest tests/test_issue_to_pr_pipeline.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts= -o timeout=0 -o faulthandler_timeout=0 -p no:cov -q` -> 10 passed.
  - `python -m pytest tests/test_rc_evidence_pack.py --no-cov -q` -> 20 passed.
  - `python -m py_compile scripts/rc_evidence_pack.py` -> passed.
  - `python scripts/rc_evidence_pack.py; python scripts/rc_final_gate.py --allow-missing-evidence-pack; python scripts/rc_release_receipt.py; python scripts/rc_final_gate.py --allow-missing-evidence-pack; python scripts/rc_evidence_pack.py; python scripts/rc_final_gate.py; python scripts/rc_final_gate.py --require-ready-to-tag` -> final status `ready_for_rc_tag`.
- Claim boundary:
  - Local RC gate evidence is green again.
  - Commercial delivery is still not complete because final P0-D requires real HTTPS/443/domain/TLS/full-stack Stage3 evidence and a decision on degraded observability.

### 2026-06-18 P0-C Hosted Gate False-Positive Stabilization

- Hosted run `27714792464` failed in `Release candidate audit` because public `xagent-...` artifact/path names in tests were treated as secret-like token leaks.
- Fixed the release audit/evidence pack secret-sample logic so public `xagent-...` path names are allowed while `xagent_...` token-like values still fail.
- Hosted run `27716098610` proved `Release candidate audit` passed, then failed in `Sequential release evidence refresh` at `artifact_integrity_gate` for the same public `xagent-...` path-name false positive inside the source zip scan.
- Fixed `rc_artifact_integrity_gate.py` to reuse the shared secret-sample allow rule and added artifact-integrity regression coverage.
- Hosted run `27716803939` proved `artifact_integrity_gate` passed, then failed at `release_diff_review_gate` because source-controlled release docs had been updated from a dirty local workspace count (`145/8`) while clean RC CI still audits the manifest as `131/7`.
- Restored `docs/RC_RELEASE_DIFF_REVIEW.md` and `docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md` to the clean RC manifest counts: `131 candidate files` and `planned 131 files across 7 commands`.
- Verification completed:
  - `python -m pytest tests/test_rc_release_audit.py tests/test_rc_evidence_pack.py --no-cov -q` -> 45 passed.
  - `python scripts/rc_release_audit.py --manifest-candidates` -> passed, 145 candidate files in the dirty local workspace.
  - `python -m pytest tests/test_rc_evidence_pack.py tests/test_rc_release_audit.py tests/test_rc_release_diff_review_gate.py tests/test_rc_final_gate.py tests/test_rc_release_receipt.py tests/test_codex_hermes_gap_matrix.py tests/test_rc_ci_contract.py tests/test_ci_workflow_hardening.py tests/test_deployment_hardening.py tests/test_production_hardening_gate.py tests/test_route_auth_audit.py --no-cov -q` -> 229 passed.
  - `python -m pytest tests/test_rc_artifact_integrity_gate.py tests/test_rc_release_audit.py tests/test_rc_evidence_pack.py --no-cov -q` -> 54 passed.
  - `python scripts/rc_refresh_release_chain.py --provider mock` -> passed locally after the artifact integrity/docs fixes, but this local count is dirty-workspace dependent and not promoted as release evidence.
  - `python -m pytest tests/test_rc_release_diff_review_gate.py tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 28 passed.
  - Hosted [Commercial RC Gate run 27717463270](https://github.com/xiongpinji/Panda-Agent-RC/actions/runs/27717463270) -> success for SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`; jobs `commercial-rc-linux` and `commercial-rc-windows-installer` both success.
- Claim boundary:
  - P0-C is restored to verified against the latest clean hosted RC run.
  - Dirty local workspace counts can differ from clean hosted RC manifest counts and must not be used as release evidence.
  - P0-D remains open: temporary HTTP Stage3 readiness and hosted CI success do not replace real HTTPS/443/domain/TLS/full-stack Stage3 evidence or the observability decision.

### 2026-06-18 P0-D Stage3 Probe Refresh After CI Recovery

- Rechecked current temporary Stage3 endpoint after P0-C hosted CI recovery:
  - `curl.exe -i --max-time 15 http://111.228.49.160:8899/health` -> 200 OK.
  - `curl.exe -i --max-time 15 http://111.228.49.160:8899/ready` -> 200 OK with `status=ready`, `audit=ok`, `qdrant=ok`, `browser=ok`, and `observability=degraded`.
  - `curl.exe -k -i --max-time 15 https://111.228.49.160/health` -> TLS handshake failure.
- Current P0-D blocker remains unchanged:
  - The service is externally reachable only through temporary HTTP port `8899`.
  - There is no verified HTTPS/443 domain/TLS path yet.
  - Observability is still degraded because Langfuse is not configured.
- Next action:
  - Provision real HTTPS/443 with a domain and certificate, or record an explicit owner-approved equivalent before running final Stage3 external evidence intake.

### 2026-06-18 P0-D1 Owner External Gates And Final Gate Closure

- Used owner-provided local environment references without printing secret values.
- Ran the strict external owner smoke against current RC evidence:
  - `python scripts/rc_external_smoke.py --provider deepseek --check provider --check feishu_webhook_contract --check github_issue_to_pr_dry_run --check github_issue_to_pr_execute_preflight --check hosted_github_actions_run --require-configured --github-execute-preflight --github-actions-preflight --timeout 40` -> `RC external smoke status: passed`.
  - Passed checks: `provider`, `feishu_webhook_contract`, `github_issue_to_pr_dry_run`, `github_issue_to_pr_execute_preflight`, `hosted_github_actions_run`.
  - GitHub issue dry-run target: `https://github.com/xiongpinji/Panda-Agent-RC/issues/1`.
  - Hosted Actions evidence: [Commercial RC Gate run 27717463270](https://github.com/xiongpinji/Panda-Agent-RC/actions/runs/27717463270), SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`.
- Refreshed owner gate reports:
  - `python scripts/rc_owner_gate_plan.py` -> `RC owner gate plan status: verified`.
  - `python scripts/rc_owner_gate_checklist.py` -> `RC owner gate checklist status: verified`.
  - `python scripts/rc_owner_env_template.py; python scripts/rc_owner_handoff_gate.py` -> owner handoff gate passed after the DeepSeek env groups were regenerated into the template.
- Refreshed the full owner-verified release evidence chain:
  - `python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60` -> passed.
  - All refresh steps passed, including `release_audit`, `staging_plan`, `source_bundle`, `artifact_integrity_gate`, `external_smoke`, `owner_gate_plan`, `owner_gate_checklist`, `owner_handoff_gate`, `release_diff_review_gate`, `deployment_docs_gate`, `release_receipt`, `evidence_pack`, and `final_gate_final`.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
- Claim boundary:
  - P0-D1 is verified: owner external gates and local final gate are closed for the current RC evidence chain.
  - P0-D remains open because Stage3 HTTPS/443 and release-bound staging observability/environment protection evidence are still missing.

### 2026-06-18 P0-D2 Stage3 HTTPS And External Evidence Recheck

- Rechecked Stage3 externally after P0-D1 owner gate closure:
  - `curl.exe -i --max-time 20 http://111.228.49.160:8899/health` -> 200 OK.
  - `curl.exe -i --max-time 20 http://111.228.49.160:8899/ready` -> 200 OK with `status=ready`, `audit=ok`, `qdrant=ok`, `browser=ok`, and `observability=degraded`.
  - `curl.exe -k -i --max-time 20 https://111.228.49.160/health` -> TLS handshake failure.
  - `curl.exe -i --max-time 20 https://xagent.111.228.49.160.sslip.io/health` -> TLS handshake failure.
  - `curl.exe -i --max-time 20 https://xagent.111.228.49.160.sslip.io/ready` -> TLS handshake failure.
  - `curl.exe -i --max-time 15 http://xagent.111.228.49.160.sslip.io/health` -> JDCloud `JDTP` 403 page, while direct IP HTTP reaches Nginx/app. The temporary `sslip.io` host is therefore not acceptable as production domain evidence on this server.
- Re-ran Stage3 external evidence intake against hosted RC SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`:
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --force` -> `stage3_staging_external_evidence_blocked`.
  - Missing or blocked evidence: `staging_observability`, `staging_environment_protection`.
- Claim boundary:
  - Owner gates are no longer the P0-D blocker.
  - The remaining first-release blocker is Stage3 production-grade evidence: HTTPS/443 domain/TLS plus release-bound observability and environment-protection proof, or an explicit owner acceptance that degraded observability is acceptable for this RC.
- Next execution path:
  - Preferred commercial path: bind a real domain to `111.228.49.160`, ensure the cloud provider allows that Host header, then configure Nginx + trusted TLS on 443 and rerun `/health` and `/ready`.
  - Temporary RC rehearsal path: configure self-signed TLS on direct IP only if the owner explicitly accepts it as a non-production equivalent; do not mark P0-D2 verified from self-signed TLS alone.

### 2026-06-18 P0-D2 Human-Readable Owner Action Checklist

The Stage3 intake source is `.xagent_runtime/reports/stage3-staging-external-evidence-input-20260616.json`, but the owner should not edit it blindly. The intake script accepts only sanitized evidence references and fails closed when the file is still a template.

What can be prefilled by Codex without secret values:

- `release_sha`: `dca6a063e9c21ee5e420d3346c28735b17a92fdf`.
- `secret_binding.secret_refs`: names or locations only, never secret values.
- `github_environment.required_reviewer`: `xiongpinji`.
- `owner_approval.owner`: `xiongpinji`.

What must be real external evidence before P0-D2 can be verified:

- Real domain: a domain controlled by the owner with DNS `A` record pointing to `111.228.49.160`. The temporary `sslip.io` domain is blocked by JDCloud and cannot be used as commercial evidence.
- Trusted TLS: a successful HTTPS/443 probe for `https://<real-domain>/health` and `https://<real-domain>/ready`, plus a TLS certificate reference such as a `certbot certificates` output, certificate transparency URL, or screenshot/reference from the certificate issuer. Do not record private key material.
- Ingress reference: Nginx site config path and reload/test evidence, for example `/etc/nginx/sites-available/xagent-stage3` plus `nginx -t` and `systemctl reload nginx` result.
- Observability references:
  - workflow broker kind and health reference;
  - Langfuse trace reference, or a first-RC owner-approved observability exception reference if Langfuse is intentionally not enabled;
  - Sentry event reference, or a first-RC owner-approved exception reference if Sentry is intentionally not enabled;
  - metrics reference;
  - alert reference.
- Deployed image proof: the image ref/digest actually running on the Stage3 server or staging platform. The current advisory build digest is not enough because the intake rejects `not_external_deploy_proof=true`.
- Owner approval reference and timestamp: an issue/comment/checklist item or signed handoff note saying the owner accepts this Stage3 evidence for the selected RC SHA.

Preferred server command sequence once a real domain is available. Replace only `<REAL_DOMAIN>`; do not paste secret values:

```bash
set -e

DOMAIN="<REAL_DOMAIN>"

cat >/etc/nginx/sites-available/xagent-stage3 <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/xagent-stage3 /etc/nginx/sites-enabled/xagent-stage3
nginx -t
systemctl reload nginx

curl -i --max-time 20 "http://${DOMAIN}/health"
curl -i --max-time 20 "http://${DOMAIN}/ready"

apt-get update
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d "${DOMAIN}" --redirect --agree-tos --register-unsafely-without-email

nginx -t
systemctl reload nginx
curl -i --max-time 20 "https://${DOMAIN}/health"
curl -i --max-time 20 "https://${DOMAIN}/ready"
certbot certificates
```

After that command succeeds, update the Stage3 input with references only and rerun:

```powershell
python scripts/commercial_stage3_staging_external_evidence_intake.py `
  --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf `
  --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf `
  --force
```

P0-D2 acceptance criteria:

- `stage3-staging-external-evidence-intake-20260616.json` status is `stage3_staging_external_evidence_ready`.
- `stage5-staging-observability-20260615.json` status is `staging_observability_ready`.
- `stage5-staging-environment-protection-20260615.json` status is `staging_environment_protection_ready`.
- Public HTTPS `/health` and `/ready` both return 200 on the real domain.
- No raw secret values are recorded in any evidence file.

### 2026-06-18 P0-D2 Owner Evidence Draft Helper

- Added a fail-closed owner draft mode to `scripts/commercial_stage3_staging_external_evidence_intake.py`:
  - `--write-owner-draft` writes a separate JSON draft and Markdown checklist.
  - Default draft outputs are `.xagent_runtime/reports/stage3-staging-external-evidence-owner-draft-20260616.json` and `.xagent_runtime/reports/stage3-staging-external-evidence-owner-draft-20260616.md`.
  - The draft keeps `template_not_external_evidence=true`, keeps `deployed_image.not_external_deploy_proof=true`, and records reference placeholders only.
  - The helper refuses to overwrite the official Stage3 input file without `--force`.
- Added regression coverage in `tests/test_commercial_stage3_staging_external_evidence_intake.py`:
  - draft includes all required observability/environment-protection fields;
  - draft contains no raw secret-like values;
  - draft CLI writes separate files without touching the official input;
  - intake rejects the draft until placeholders are replaced with real external evidence and template markers are removed.
- Verification completed:
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py --no-cov -q` -> 10 passed.
  - `python -m py_compile scripts/commercial_stage3_staging_external_evidence_intake.py` -> passed.
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --write-owner-draft --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --domain "<REAL_DOMAIN>"` -> draft written.
  - Draft fail-closed check using the generated draft as `--input-json` -> `stage3_staging_external_evidence_blocked`, `real_external_evidence_collected=false`, missing `staging_observability` and `staging_environment_protection`.
- Claim boundary:
  - This reduces owner/operator filling mistakes and prevents secret-value capture.
  - It does not close P0-D2 and does not substitute for real domain/TLS/observability/environment-protection evidence.
- Next action:
  - Owner must provide a real domain pointed to `111.228.49.160`; after DNS resolves, configure HTTPS/443 and replace draft placeholders with evidence references only.

### 2026-06-18 P1-A Dirty Worktree Classification Pass 1

- Ran read-only worktree classification:
  - `git status --porcelain=v1 -uall` -> 528 changed/untracked entries.
  - Status split: 144 modified, 384 untracked.
  - Top-level split: backend 220, tests 197, frontend 41, docs 21, scripts 15, desktop 12, plus smaller root/config/doc entries.
- Bucketed release decision groups:

| Bucket | Count | Status Split | Release Decision |
|---|---:|---|---|
| `generated-readiness-packets-review` | 314 | 314 untracked | Not first-RC payload by default. Treat as generated review/readiness packet material; include only if a named release gate requires it and tests prove it. |
| `other-review-required` | 78 | 46 modified, 32 untracked | Needs follow-up classification before release. Includes broad cache/performance/LLM/search changes, root config/docs, `uv.lock`, and misc tests. |
| `product-docs-assets-review` | 68 | 43 modified, 25 untracked | Product docs/Panda assets may be release-facing, but require visual/content owner review before inclusion. |
| `P0-backend-security-candidate` | 48 | 38 modified, 10 untracked | Candidate first-RC security payload. Keep tied to focused auth/RBAC/SAML/path/memory/browser/admin evidence before staging. |
| `P0-desktop-candidate` | 12 | 11 modified, 1 untracked | Candidate first-RC desktop hardening payload. Keep tied to desktop pytest and cargo evidence. |
| `P0-C-D-gate-and-stage3-candidate` | 6 | 5 modified, 1 untracked | Candidate CI/Stage3 gate payload, including the new Stage3 owner draft helper. |
| `release-risk-config-review` | 2 | 1 modified, 1 untracked | Release-risk config. `.env.example` can be reviewed; `deployment/kubernetes/secret.yaml` must not be included in an RC bundle without explicit owner/security approval. |

- Explicit release-risk finding:
  - `deployment/kubernetes/secret.yaml` is untracked and path/name indicate a secret manifest. It was not opened or modified. Treat as excluded from first-RC packaging unless owner explicitly confirms it is sanitized and intended.
- Claim boundary:
  - This is classification only. No files were reverted, deleted, staged, or committed.
  - P1-A remains `IN_PROGRESS` until each bucket has a final include/exclude/defer decision and the release bundle is checked against that decision.
- Next action:
  - Continue with bucket-level convergence after P0-D2 domain/TLS evidence is unblocked, or start with the highest-risk bucket now: `release-risk-config-review` and `other-review-required`.

### 2026-06-18 P1-A Release-Risk Config Review

- Reviewed the `release-risk-config-review` bucket without opening the untracked secret manifest:
  - `git status --porcelain=v1 -uall -- .env.example deployment/kubernetes/secret.yaml .github deployment monitoring docker-compose.yml docker-compose.stage3.yml` -> `.env.example` modified and `deployment/kubernetes/secret.yaml` untracked.
  - `git diff -- .env.example --` shows added monitoring/local-dev credential keys with empty values, plus `UVICORN_RELOAD=` as opt-in; no concrete secret values are added.
  - `rg -n "(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|PRIVATE) KEY|password\s*=\s*[^<\s#][^\s#]*|token\s*=\s*[^<\s#][^\s#]*|secret\s*=\s*[^<\s#][^\s#]*)" .env.example` -> no matches.
- Gate verification:
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> `Production hardening gate status: ready`, `Findings: 0`, `Blocking reasons: <none>`.
- Release decision:
  - `.env.example` is acceptable as a release-template candidate from this pass, subject to normal review with the final bundle.
  - `deployment/kubernetes/secret.yaml` remains excluded from first-RC packaging unless owner/security explicitly confirms it is sanitized and intended. It was not opened, modified, staged, or validated as safe.
- Claim boundary:
  - This only clears the currently visible release-risk config bucket. It does not classify the broad `other-review-required` bucket or generated readiness packet material.

### 2026-06-18 P1-A Other-Review-Required Split

- Split the 78-entry `other-review-required` bucket:

| Sub-Bucket | Count | Initial Release Decision |
|---|---:|---|
| `backend-nonsecurity-performance-cache-llm` | 25 modified | Default defer from first-RC unless a named commercial gate requires it. This broad cache/performance/LLM/search set needs targeted tests and product rationale before inclusion. |
| `tests-nonsecurity-e2e-context-governance` | 11 modified | Pair with the corresponding product/runtime changes only; do not include as standalone RC payload. |
| `root-tooling-and-deps` | 5 total | Needs human review before RC. `.pre-commit-config.yaml` adds gitleaks and deployment hardening hook; `pyproject.toml` adds dev dependencies; `.gitignore` and `.mcp.json` diffs show mojibake/encoded path drift and must be cleaned or excluded before release. |
| `root-audit-deliverable-docs` | 7 untracked | Evidence/audit deliverables, not product runtime. Include only in a docs/evidence bundle if owner asks; otherwise defer from app release payload. |
| `misc` | 28 total | Mixed scripts/tests and miscellaneous backend files; requires file-by-file routing before inclusion. |
| `original-kernel-manifest` | 1 modified | Keep separate from first-RC runtime unless the original-kernel release manifest is explicitly in scope. |
| `stray-template-artifact` | 1 untracked | Exclude. `{r['assigned_to']}` is a 0-byte template-rendering artifact. |

- Light verification:
  - `python -m py_compile scripts/original_kernel_delivery_manifest.py scripts/ga_quality_gate.py scripts/owner_operator_commercial_delivery_intake.py scripts/read_codex_messages.py scripts/send_to_zcode.py` -> passed.
  - `Test-Path -LiteralPath "{r['assigned_to']}"` -> true; `Length` -> 0 bytes.
- Root tooling observations:
  - `.pre-commit-config.yaml` gitleaks/deployment-hardening additions are conceptually useful but require final hook install/run proof before release.
  - `pyproject.toml` dev dependency additions require dependency-lock review because `uv.lock` is untracked.
  - `.gitignore` and `.mcp.json` currently show encoding/path drift in diff output; do not include them in an RC bundle until reviewed and normalized.
- Claim boundary:
  - No cleanup was performed and no files were staged.
  - `other-review-required` is now routed, not cleared. It remains a release-blocking bucket for any bundle that tries to include it wholesale.

### 2026-06-18 P1-A Generated Readiness Packets Review

- Reviewed the generated readiness/secondary candidate packet bucket as release scope, not as product runtime:
  - Broad scan matched 317 Python files: 160 under `backend/app/core/` and 157 under `tests/`.
  - Pattern split: 101 `codex_*_readiness_packet` files, 164 `integration_*` files, and 56 other readiness/acceptance/runtime/evidence matrix files.
  - Sample headers show pure-payload/packet style modules such as `_codex_readiness_packet_core.py`, `_codex_readiness_packet_specs.py`, `acceptance_matrix.py`, `agent_eval_matrix.py`, `agent_orchestration_runtime.py`, and `agent_registry.py`.
- Reference/routing evidence:
  - Existing docs and tests route many of these as `secondary_integration_candidate` or `secondary_pending_candidate`, not as first-RC runtime.
  - No current P0-D2 Stage3/HTTPS gate depends on this bucket.
  - These files are too broad to include wholesale in the first-RC bundle without owner review.
- Light verification:
  - AST parse sanity check across the 317 matched Python files -> `syntax_errors=0`.
  - This check only proves syntax readability. It does not prove product readiness, API integration, or release suitability.
- Release decision:
  - Default defer from first-RC runtime and customer-facing release package.
  - Include only as a separate secondary/evidence bundle if owner explicitly asks, or if a named gate requires a specific file/test pair.
  - Do not mix this bucket into the verified P0 backend/security, desktop, CI, or Stage3 release candidates.
- Claim boundary:
  - No files were deleted, modified, staged, or promoted.
  - This bucket is classified, not accepted.

### 2026-06-18 P1-A Product Docs And Assets Review

- Split the 69-entry product docs/assets bucket:

| Sub-Bucket | Count | Initial Release Decision |
|---|---:|---|
| `panda-image-assets` | 40 PNG files | Potentially release-facing, but requires owner visual review before inclusion. |
| `docs` | 7 markdown files | Candidate documentation updates; require content review against final verified product scope. |
| `owner-evidence-docs` | 7 files | Evidence/owner intake support docs; include only in evidence/handoff bundle, not product runtime. |
| `planning-docs` | 7 plan files | Planning history. Keep internal unless owner wants a planning archive. |
| `release-user-docs` | 7 files | Candidate release/customer docs, except `deployment/kubernetes/secret.yaml` remains classified as release-risk secret manifest and excluded. |
| `frontend-smoke-script` | 1 script | Candidate QA script change; requires JS/runtime test before release. |

- Light verification:
  - `node --check frontend/scripts/panda-qa-smoke.mjs` -> passed.
  - PNG signature check for `frontend/src/panda/assets/roles/*.png` -> `png_checked=40`, `png_bad=0`.
  - `rg` over release docs for obvious secret-token patterns found placeholder examples only: `DEPLOYMENT.md` contains `LANGFUSE_SECRET="sk-xxx"` and plugin docs contain `gh_example_token_redacted`.
- Release decision:
  - Panda image assets are structurally valid PNGs but not visually accepted. They require owner/UI review before first-RC inclusion.
  - Release/user docs are candidates, but `DEPLOYMENT.md` should replace `sk-xxx` with a clearer non-secret placeholder before final publication, or document why the release audit allows it.
  - Planning/owner-evidence docs should stay in internal evidence/handoff bundles unless explicitly included.
- Claim boundary:
  - No docs or assets were modified by this review.
  - This pass does not prove visual quality, copy accuracy, or customer-readiness of the docs.

### 2026-06-18 P1-A RC Include/Defer/Exclude Manifest

- Converted the current dirty-worktree classification into an RC routing manifest with full path coverage:
  - `git status --porcelain=v1 -uall` -> 528 entries.
  - Status split remains 144 modified and 384 untracked.
  - Bucket coverage command over the current status set -> `total=528 unclassified=0`.

| RC Bucket | Count | Decision | Release Rule |
|---|---:|---|---|
| `INCLUDE-P0-backend-security-and-tests` | 50 | Include candidate | Only with the existing focused auth/RBAC/SAML/path-boundary/memory/browser/admin regression evidence. |
| `INCLUDE-P0-C-D-gates-stage3-and-tests` | 13 | Include candidate | CI/route/deployment/production gate and Stage3 helper payload; must stay tied to hosted CI and Stage3 intake evidence. Only `scripts/commercial_stage3_staging_external_evidence_intake.py` is the P0-D2 helper; Stage5 template helpers are deferred. |
| `INCLUDE-P0-desktop-hardening` | 12 | Include candidate | Desktop is first-version scope; keep tied to Tauri security pytest plus `cargo check/test` evidence. `desktop/icons/icon.ico` is not automatic include unless tray/icon wiring is restored and reverified. |
| `INCLUDE-release-template-no-secrets` | 1 | Include candidate | `.env.example` only, because the current pass found no concrete secret value in the template. |
| `EXCLUDE-explicit-risk-artifacts` | 2 | Exclude | `deployment/kubernetes/secret.yaml` was not opened and must not enter RC; `{r['assigned_to']}` is a 0-byte stray template artifact. |
| `DEFER-generated-readiness-secondary-packets` | 297 | Defer | Generated readiness/secondary packet material is not first-RC runtime payload unless a named gate requires a specific file/test pair. |
| `DEFER-backend-nonsecurity-broad-changes` | 42 | Defer | Broad cache/performance/LLM/search/runtime changes need product rationale and targeted tests before inclusion. |
| `DEFER-tests-without-accepted-payload` | 24 | Defer | Tests are included only when their corresponding runtime/docs payload is accepted. |
| `DEFER-scripts-outside-P0-gates` | 6 | Defer | Scripts outside the verified P0 gate/Stage3 lanes need separate owner/gate justification. |
| `DEFER-root-tooling-deps-review` | 5 | Defer | `.gitignore`, `.mcp.json`, `.pre-commit-config.yaml`, `pyproject.toml`, and `uv.lock` need dependency/encoding/hook review before RC. |
| `OWNER-REVIEW-frontend-assets-and-smoke` | 41 | Owner review | Panda assets and frontend smoke script are structurally checked, but owner/UI visual acceptance is still required. |
| `OWNER-REVIEW-release-docs-evidence` | 35 | Owner review | Docs/evidence/handoff materials require content review against final verified product scope. |

- Release packaging rule:
  - A first-RC bundle may use only the four `INCLUDE-*` buckets unless an owner explicitly accepts a named owner-review item.
  - The two `EXCLUDE-*` items must stay out of the RC bundle.
  - `DEFER-*` buckets are not runtime release payload by default and must not be swept into the bundle as a group.
  - Internal coordination files (`AGENTS.md`, blackboard/session tooling, and Codex/ZCode communication scripts) are allowed as repo evidence only; they are not customer runtime payload.
  - Any bundle containing `backend/app/api/enterprise.py`, `backend/app/api/skills_api.py`, `backend/app/api/issue_to_pr.py`, or the `backend/app/main.py` P0 warning path remains blocked until the ZCode task board marks P0-01/P0-03/P0-04/P0-06 verified.
  - Any bundle containing `pyproject.toml` changes must include a reviewed and synchronized dependency lock decision; do not include `pyproject.toml` while treating untracked `uv.lock` as unrelated.
  - `.mcp.json` is internal local-tooling configuration and must not enter the customer/runtime RC bundle.
- Claim boundary:
  - No files were reverted, deleted, staged, committed, or promoted by this classification.
  - P1-A verifies routing coverage only. Commercial readiness still depends on P0-D2 real HTTPS/443/domain/TLS, observability/environment evidence, and final gate proof.

### 2026-06-18 P1-B Deployment Docs Secret Placeholder Hardening

- Hardened `DEPLOYMENT.md` examples so deployment docs no longer show fake secret-looking literals:
  - replaced `postgresql://user:password@...`, `your-secure-api-key-here`, `pk-xxx`, and `sk-xxx` examples with `<secret-manager-ref:...>` references;
  - added explicit wording that secret values must be loaded from a secret manager into the current shell and must not be committed or pasted into docs.
- Verification completed:
  - `Select-String DEPLOYMENT.md -Pattern 'sk-xxx|pk-xxx|your-secure-api-key-here|postgresql://user:password'` -> no matches.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 21 passed.
  - `python scripts/rc_evidence_pack.py` -> evidence pack created; `evidence_secret_scan` and `evidence_local_path_privacy_scan` passed.
- Claim boundary:
  - This improves release-document hygiene but does not close P0-D2.
  - Final customer handoff docs still need the real HTTPS domain, final Stage3 evidence references, and the owner decision on observability/environment evidence.

### 2026-06-18 P1-B Release Scope Documentation Alignment

- Updated `RELEASE_NOTES_v1.0.0.md` to match the owner scope decision:
  - desktop/Tauri client is first-version delivery scope and remains tied to the desktop security/build evidence;
  - browser extension is not included in the first-version commercial delivery package, demo scope, or customer documentation commitment;
  - browser extension hardening and packaging is moved to the v1.1/future roadmap.
- Verification completed:
  - `rg -n "Chrome Extension|browser extension|Browser extension|extension/|WebStore|Web Store|Desktop App|Tauri|desktop client|桌面|浏览器扩展" ...` -> remaining matches now state desktop in scope and browser extension deferred.
  - `python scripts/rc_release_audit.py --manifest-candidates` -> passed, 131 candidate files.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py --no-cov -q` -> 46 passed.
- Claim boundary:
  - This closes the local documentation-scope mismatch.
  - Final customer handoff remains `IN_PROGRESS` until P0-D2 supplies the real domain/TLS/observability/environment evidence references.

### 2026-06-18 P1-B README And Runbook Current-State Alignment

- Hardened `README_DELIVERABLES.md` quickstart examples:
  - SDK example now reads `apiKey` from `process.env.XAGENT_API_KEY` instead of a literal example key.
  - Helm example now passes `$XAGENT_DATABASE_URL` and `$XAGENT_API_KEY` instead of inline placeholder secrets.
  - Added explicit instruction to load those values from the owner secret manager or CI secret store and never paste them into docs or commit them.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` top-of-file status:
  - date refreshed to 2026-06-18;
  - points to this master plan as the current ledger;
  - records desktop/Tauri as first-version scope and browser extension as deferred;
  - replaces stale 2026-06-08 Ollama/old-SHA current-state language with the current DeepSeek/Feishu/GitHub/hosted Actions owner-gate evidence chain: hosted run `27717463270`, SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`;
  - keeps P0-D2 explicitly open until real domain/TLS, HTTPS `/health` and `/ready`, observability, and environment-protection evidence are available.
- Verification completed:
  - `rg -n "GA-Ready|production-ready release|commercial delivery-complete|release-ready proof|full Codex parity proof|apiKey: 'key'|apiKey: 'your|secrets\\.apiKey=\"\\.\\.\\.\"|secrets\\.databaseUrl=\"postgresql://|sk-xxx|pk-xxx|your-secure-api-key-here|postgresql://user:password|WebStore|Web Store|Chrome Extension|browser extension|Browser extension" README_DELIVERABLES.md DEPLOYMENT.md RELEASE_NOTES_v1.0.0.md docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md docs/RC_RELEASE_DIFF_REVIEW.md docs/owner-operator-commercial-delivery-input-request.md` -> no matches.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py --no-cov -q` -> 46 passed.
  - `python scripts/rc_release_audit.py --manifest-candidates` -> passed, 131 candidate files.
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> ready, 0 findings.
- Evidence-pack freshness recovery:
  - First `python scripts/rc_evidence_pack.py` run failed correctly because the release receipt was older than newly generated JSON evidence reports.
  - `python scripts/rc_release_receipt.py` -> created fresh release receipt.
  - Re-run `python scripts/rc_evidence_pack.py` -> created pack `x-agent-commercial-rc-evidence-20260617T214310Z.zip`, sha256 `4a4d46ce40eaa9db6da64762396905469021f894f74c34489a04bade0fc20afd`.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
- Claim boundary:
  - This aligns local release/customer documentation with the current verified evidence chain.
  - It still does not close P0-D2. Final handoff remains blocked on real HTTPS/443 domain/TLS and release-bound observability/environment-protection evidence.

### 2026-06-18 P0-A Desktop Evidence Refresh

- Re-ran the desktop first-version security/build baseline after release-scope docs were aligned:
  - `python -m pytest tests/test_desktop_tauri_security.py --no-cov -q` -> 8 passed.
  - `Push-Location desktop; cargo check --offline; cargo test --offline; Pop-Location` -> `cargo check` passed with warnings only; `cargo test` passed, 8 tests.
  - `node --check frontend/scripts/panda-qa-smoke.mjs` -> passed.
- Claim boundary:
  - This refreshes desktop hardening evidence only.
  - `desktop/icons/icon.ico` remains excluded from automatic RC promotion unless tray/icon wiring is restored and reverified.

### 2026-06-18 P0-B Legacy ZCode P0 Verifier Refresh

- Re-ran the legacy ZCode verifier tasks that were still stale in `AGENTS.md`:
  - `$env:PYTHONIOENCODING='utf-8'; python audit_reports/verify_fixes.py P0-01` -> 5 passed / 0 failed.
  - `$env:PYTHONIOENCODING='utf-8'; python audit_reports/verify_fixes.py P0-03` -> 4 passed / 0 failed.
  - `$env:PYTHONIOENCODING='utf-8'; python audit_reports/verify_fixes.py P0-04` -> 2 passed / 0 failed.
  - `$env:PYTHONIOENCODING='utf-8'; python audit_reports/verify_fixes.py P0-06` -> 1 passed / 0 failed.
- Verification caveat:
  - Running those same commands without `PYTHONIOENCODING=utf-8` on this Windows console hits a `UnicodeEncodeError` when the script prints the final checkmark after all checks have already passed.
  - With UTF-8 output enabled, all four commands exit 0.
- Communication:
  - Sent ZCode a file-backed message via `python scripts/send_to_zcode.py` with message id `4a2fbcd7-04d9-4166-9e32-0a0a99498222`.
  - SQLite task update returned `task P0-01 not found on board`, but the inbox fallback file was written at `audit_reports/_comm/inbox_zcode/2026-06-17T21-33-16_P0-task-board-reverify-evidence.md`.
- Claim boundary:
  - Codex did not edit `audit_reports/`.
  - `AGENTS.md` may remain stale until ZCode performs its verification-record update.

### 2026-06-18 P1-B Checklist Evidence Wording And Final Gate Refresh

- Cleaned the remaining release-checklist evidence wording drift:
  - `docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md` no longer describes the older local Ollama `qwen2.5:1.5b` attempt as the current provider evidence.
  - The checklist now states that the current owner-verified RC evidence chain uses DeepSeek for provider smoke and keeps older Ollama/local attempts as troubleshooting history only.
  - Re-scan command:
    `rg -n "codex/codex-hermes-gap-closure|x-agent-commercial-rc-20260608-5|5877b0b273a8d4abd1fad1ce501d673c6cd06f32|owner_finalize_pending|ready_with_owner_gates|rc_refresh_release_chain.py --provider ollama|--provider ollama --ollama-model|qwen2\\.5:1\\.5b|127\\.0\\.0\\.1:11435|localhost:11434|Current local RC evidence uses Ollama|Provider owner gate: not verified|current local Ollama|Ollama attempt" docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md docs/RC_RELEASE_DIFF_REVIEW.md`
    -> only remaining match is optional local provider configuration `XAGENT_OLLAMA_BASE_URL=http://localhost:11434` in the runbook.
- Fresh verification completed:
  - `python -m pytest tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py --no-cov -q` -> 46 passed.
  - `python scripts/rc_release_audit.py --manifest-candidates` -> passed, 131 candidate files.
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> `Production hardening gate status: ready`, `Findings: 0`, `Blocking reasons: <none>`.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T215421Z.zip`, sha256 `55ae36b87882bff5de82c7203dbb34547a7d87ed02bf3277a38b527ae526ea3d`, 27 evidence files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
- Claim boundary:
  - P1-B documentation/current-evidence alignment is locally refreshed.
  - This does not close P0-D2. Commercial delivery still needs real owner-controlled domain, trusted HTTPS/443 `/health` and `/ready`, and release-bound observability/environment-protection evidence.

### 2026-06-18 P1-B SDK Example Secret Hygiene Follow-Up

- Hardened the remaining `DEPLOYMENT.md` SDK examples:
  - replaced `apiKey: 'your-api-key'` in the quick example and client initialization example with `process.env.XAGENT_API_KEY`;
  - examples now throw a configuration error when `XAGENT_API_KEY` is absent, instructing the operator to load it from a secret manager or CI secret store.
- Fresh verification completed:
  - `rg -n "apiKey: 'your-api-key'|apiKey: 'your|apiKey: \"your|sk-xxx|pk-xxx|your-secure-api-key-here|postgresql://user:password|GA-Ready|production-ready release|commercial delivery-complete|release-ready proof|full Codex parity proof|Chrome Extension|WebStore|Web Store" README_DELIVERABLES.md DEPLOYMENT.md RELEASE_NOTES_v1.0.0.md docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md docs/RC_RELEASE_DIFF_REVIEW.md` -> no matches.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py --no-cov -q` -> 46 passed.
  - `python scripts/rc_release_audit.py --manifest-candidates` -> passed, 131 candidate files.
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> `Production hardening gate status: ready`, `Findings: 0`, `Blocking reasons: <none>`.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T220008Z.zip`, sha256 `c5f2d68bcabc71f87a02d0f9f2a07b5d58300ec0dec21cef2be9122a4a9b3994`, 27 evidence files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
- Claim boundary:
  - This removes a misleading copy-paste secret placeholder from public deployment docs.
  - It does not close P0-D2 or replace real owner-controlled secret management.

### 2026-06-18 P0-D2 Stage3 Evidence Intake Endpoint Hardening

- Hardened `scripts/commercial_stage3_staging_external_evidence_intake.py` so Stage3 environment-protection evidence cannot accept weak endpoint proof:
  - `staging_environment_protection.external_endpoint.url` must be HTTPS on a real DNS domain using default 443 or explicit 443.
  - HTTP, credentials in URL, localhost, single-label hosts, bare IP addresses, and temporary wildcard DNS domains such as `sslip.io`/`nip.io`/`xip.io` are rejected.
  - `external_endpoint.health_ref` and `external_endpoint.ready_ref` are now required evidence references, so a real `/health` and `/ready` HTTPS probe must be recorded before P0-D2 can pass.
  - Owner draft generation now includes `health_ref` and `ready_ref` placeholders while still marking the draft as `template_not_external_evidence=true`.
- Regression coverage added in `tests/test_commercial_stage3_staging_external_evidence_intake.py`:
  - complete external evidence still produces ready reports;
  - unsafe endpoints `http://stage3.example.com`, `https://111.228.49.160`, `https://xagent.111.228.49.160.sslip.io`, and `https://localhost` are blocked;
  - missing `/health` and `/ready` probe references keep environment protection blocked;
  - refreshed owner draft contains the new required fields and remains fail-closed until placeholders are replaced.
- Fresh verification completed:
  - `python -m py_compile scripts/commercial_stage3_staging_external_evidence_intake.py` -> passed.
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py --no-cov -q` -> 12 passed.
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_stage5_production_rehearsal_evidence_templates.py tests/test_stage3_staging_rehearsal_workflow_contract.py --no-cov -q` -> 25 passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py --no-cov -q` -> 46 passed.
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> `Production hardening gate status: ready`, `Findings: 0`, `Blocking reasons: <none>`.
  - `python scripts/rc_release_audit.py --manifest-candidates` -> passed, 131 candidate files.
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --force` -> exited 1 with expected fail-closed status `stage3_staging_external_evidence_blocked`; missing/blocked evidence is `staging_observability, staging_environment_protection`; no mutation or raw secret values recorded.
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --write-owner-draft --domain '<REAL_DOMAIN>' --force` -> regenerated owner draft JSON/Markdown and kept `template_not_external_evidence=true`.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T220656Z.zip`, sha256 `e973790c8d3bc2d5fd592daf1291f0c5163d7999f0132eaa7b5982b198264900`, 27 evidence files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
- Claim boundary:
  - This improves P0-D2 evidence quality and prevents accepting temporary HTTP/IP/sslip placeholders as commercial proof.
  - It still does not close P0-D2. Real owner-controlled DNS, trusted HTTPS/443 `/health` and `/ready`, observability references, environment-protection references, deployed image digest, and owner approval reference are still required.

### 2026-06-18 P0-D2 Owner Evidence Draft Usability Pass

- Improved the Stage3 owner evidence draft for non-expert owner/operator use:
  - `scripts/commercial_stage3_staging_external_evidence_intake.py` now renders a beginner fill order in the generated Markdown checklist.
  - The checklist separates what the owner must decide from what Codex/operator tooling can fill after a real domain exists.
  - The checklist lists exact JSON field paths that must be replaced with references only.
  - It keeps the same fail-closed semantics: the draft is still `template_not_external_evidence=true`, does not record raw secret values, and cannot pass intake until placeholders are replaced with real release-bound references.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` with a Stage3 HTTPS evidence checklist:
  - real owner-controlled domain A record to `111.228.49.160`;
  - HTTPS/443 `/health` and `/ready` refs;
  - Nginx config/test/reload refs, certificate refs, running image ref/digest, secret variable-name refs;
  - observability refs or explicit first-RC observability exception ref.
- Regenerated the owner draft:
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --write-owner-draft --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --domain '<REAL_DOMAIN>' --owner xiongpinji --force` -> draft JSON/Markdown written, `template_not_external_evidence=true`.
- Verification completed:
  - `python -m py_compile scripts/commercial_stage3_staging_external_evidence_intake.py` -> passed.
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py --no-cov -q` -> 12 passed.
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --force` -> exited 1 with expected fail-closed status `stage3_staging_external_evidence_blocked`; missing/blocked evidence remains `staging_observability, staging_environment_protection`.
- Claim boundary:
  - This makes the owner/operator evidence path actionable without asking for secret values.
  - It still does not close P0-D2. The next real blocker is an owner-controlled domain with trusted HTTPS/443 and release-bound observability/environment-protection refs.

### 2026-06-18 P0-D2 Stage3 HTTPS Preflight Tool

- Added `scripts/stage3_https_preflight.py` as a redaction-safe, read-only probe for the real Stage3 domain:
  - rejects bare IPs, localhost, single-label hosts, HTTP URLs, URL credentials, paths/query URLs, and temporary wildcard DNS such as `sslip.io`/`nip.io`/`xip.io`;
  - checks DNS resolution includes `111.228.49.160`;
  - validates trusted TLS on port 443;
  - probes `https://<domain>/health` for HTTP 200 and JSON `status=ok`;
  - probes `https://<domain>/ready` for HTTP 200 and JSON `status=ready`;
  - writes `.xagent_runtime/reports/stage3-https-preflight-20260618.json` and `.xagent_runtime/reports/stage3-https-preflight-20260618.md`.
- Added `tests/test_stage3_https_preflight.py` with success and fail-closed coverage for domain shape, DNS mismatch, TLS failure, readiness failure, and CLI report writing.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` so the Stage3 HTTPS checklist tells the operator to run:
  - `python scripts/stage3_https_preflight.py --domain "<REAL_DOMAIN>"`
- Verification completed:
  - `python -m py_compile scripts/stage3_https_preflight.py` -> passed.
  - `python -m pytest tests/test_stage3_https_preflight.py --no-cov -q` -> 5 passed.
  - `python scripts/stage3_https_preflight.py --domain xagent.111.228.49.160.sslip.io` -> exited 1 with expected `stage3_https_preflight_blocked`; JSON/Markdown reports written.
  - `python -m pytest tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_stage5_production_rehearsal_evidence_templates.py tests/test_stage3_staging_rehearsal_workflow_contract.py --no-cov -q` -> 30 passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py --no-cov -q` -> 46 passed.
  - `rg -n "GA-Ready|production-ready release|commercial delivery-complete|release-ready proof|full Codex parity proof|apiKey: 'key'|apiKey: 'your|secrets\\.apiKey=\"\\.\\.\\.\"|secrets\\.databaseUrl=\"postgresql://|sk-xxx|pk-xxx|your-secure-api-key-here|postgresql://user:password|WebStore|Web Store|Chrome Extension|browser extension|Browser extension" README_DELIVERABLES.md DEPLOYMENT.md RELEASE_NOTES_v1.0.0.md docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md docs/RC_RELEASE_DIFF_REVIEW.md docs/owner-operator-commercial-delivery-input-request.md` -> no matches.
- Claim boundary:
  - This tool prepares the exact local verification path for a future real domain.
  - It still does not close P0-D2 because the current external hostname remains temporary/blocked and no owner-controlled HTTPS/443 domain evidence exists yet.

### 2026-06-18 P1-B Deployment Docs Gate Current-Path Refresh

- Updated `scripts/rc_deployment_docs_gate.py` so the deployment docs gate matches the current commercial RC path:
  - requires `python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60` instead of the older Ollama-specific current-path token;
  - requires `python scripts/rc_release_receipt.py` instead of treating `rc_delivery_status.py` as the current handoff command;
  - requires the Stage3 HTTPS preflight command tokens, generated JSON/Markdown report names, and the explicit `sslip.io` temporary-DNS rejection note;
  - keeps no-full-parity enforcement, now case-insensitive and compatible with `not a full Codex/Hermes parity claim` wording.
- Updated `tests/test_rc_deployment_docs_gate.py` so fixture docs represent the current DeepSeek owner-verified release path and assert that omitting `stage3_https_preflight.py` fails the runbook check.
- Verification completed:
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 22 passed.
  - `python -m py_compile scripts/rc_deployment_docs_gate.py scripts/stage3_https_preflight.py` -> passed.
  - `python scripts/rc_deployment_docs_gate.py` -> passed; all checks passed and report written to `.xagent_runtime/reports/rc-deployment-docs-gate.json`.
- Claim boundary:
  - This tightens release-document guardrails and keeps the Stage3 HTTPS preflight from becoming optional.
  - It does not close P0-D2; the real owner-controlled domain and trusted HTTPS evidence are still required.

### 2026-06-18 P0-D2 Strict Stage3 Final Gate Guard

- Tightened `scripts/rc_final_gate.py` with an explicit Stage3 rehearsal requirement:
  - added `--require-stage3-rehearsal` and `--staging-rehearsal`;
  - default local final-gate behavior remains unchanged for owner-gate debugging;
  - strict commercial mode appends a `staging_rehearsal` local gate and requires `.xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.json` to report `staging_rehearsal_ready`, `rehearsal_ready=true`, `environment=staging`, a release SHA, no `missing_or_mismatched` evidence, no gate side effects, and passed rehearsal checks.
- Updated `tests/test_rc_final_gate.py`:
  - default final gate does not require Stage3 rehearsal;
  - explicit `require_stage3_rehearsal=True` fails on missing reports;
  - blocked rehearsal reports fail closed;
  - ready staging rehearsal reports pass when owner gates are verified;
  - CLI parsing accepts `--require-stage3-rehearsal` and `--staging-rehearsal`.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md`, `scripts/rc_deployment_docs_gate.py`, and `tests/test_rc_deployment_docs_gate.py` so commercial handoff docs require:
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal`
- Verification completed:
  - `python -m py_compile scripts/rc_final_gate.py scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_rc_final_gate.py --no-cov -q` -> 91 passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 23 passed.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T224826Z.zip`, sha256 `9efa1247c6553bc6d63efc59359ae11914febef938edbf8da5ff64ab2e26edd2`, 27 evidence files.
  - `python -m pytest tests/test_rc_final_gate.py tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 114 passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> exited 1 internally as expected and wrapper returned 0; only strict Stage3 gate failed with `staging_rehearsal_blocked`.
- Claim boundary:
  - This prevents final commercial gate drift by making Stage3 rehearsal enforceable.
  - It does not close P0-D2. The strict commercial final gate is expected to fail until a real owner-controlled domain, trusted HTTPS/443 `/health` and `/ready`, release-bound observability/environment-protection refs, and a ready Stage3 rehearsal report exist.

### 2026-06-18 P0-D2 Stage3 Rehearsal Release-SHA Binding

- Tightened `scripts/rc_final_gate.py` again so strict Stage3 rehearsal evidence cannot be reused across RC candidates:
  - `_stage3_rehearsal_gate()` now receives the owner-verified release SHA extracted from `rc-external-smoke.json` `hosted_github_actions_run.details.expected_head_sha/head_sha`;
  - strict Stage3 mode fails if the rehearsal `release_sha` differs from the owner-verified hosted Actions `head_sha`;
  - strict Stage3 mode also fails if `current_head_sha` is present but differs from the rehearsal `release_sha`.
- Updated `tests/test_rc_final_gate.py`:
  - hosted Actions fixture now carries `expected_head_sha`, `head_sha`, and `head_sha_verified=true`;
  - added a regression test proving a ready Stage3 rehearsal for a different release SHA fails.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md`, `scripts/rc_deployment_docs_gate.py`, and `tests/test_rc_deployment_docs_gate.py` so owner-facing docs explicitly require Stage3 rehearsal `release_sha` to match the owner-verified hosted GitHub Actions `head_sha`.
- Verification completed:
  - `python -m pytest tests/test_rc_final_gate.py --no-cov -q` -> 92 passed.
  - `python -m pytest tests/test_rc_final_gate.py tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 115 passed.
  - `python -m py_compile scripts/rc_final_gate.py scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_rc_final_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_release_audit.py tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_stage5_production_rehearsal_evidence_templates.py tests/test_stage3_staging_rehearsal_workflow_contract.py --no-cov -q` -> 170 passed.
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> `OK No deployment-hardening issues found.`
  - `python scripts/production_hardening_gate.py` -> `Production hardening gate status: ready`, `Findings: 0`, `Blocking reasons: <none>`.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T225708Z.zip`, sha256 `456fe05690b86d32643997a6691002658571f9e727667211915d6df115b5cabc`, 27 evidence files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> exited 1 internally as expected and wrapper returned 0.
- Current strict-gate blocker details:
  - `staging_rehearsal.status=staging_rehearsal_blocked`;
  - rehearsal `release_sha=9a1bd6732df06cd8d58fcdd2ab646f31ff20f243`;
  - owner-verified release SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`;
  - missing/mismatched evidence: `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, `staging_environment_protection`.
- Claim boundary:
  - This removes a future false-positive path where old Stage3 readiness could satisfy the current RC.
  - It still does not close P0-D2; the owner/operator must produce real Stage3 evidence for the current owner-verified release SHA.

### 2026-06-18 P0-D2 Stage3 Rehearsal Intake-Metadata Guard

- Tightened `scripts/commercial_environment_rehearsal_gate.py` so the Stage3 rehearsal gate cannot accept hand-written ready JSON for the two evidence reports generated by the Stage3 external evidence intake:
  - `staging_observability` and `staging_environment_protection` now require `real_external_evidence_collected=true`;
  - `template_not_evidence` must not be true;
  - `external_evidence_input_path` must be present;
  - `external_evidence_input_embedded`, `raw_secret_values_recorded`, `deploy_performed_by_intake`, `workflow_dispatch_performed`, `cluster_mutation_performed_by_intake`, and `outbound_message_sent` must all be false;
  - generated intake `checks` must exist and all be `passed`.
- Added regression coverage in `tests/test_commercial_environment_rehearsal_gate.py`:
  - default Stage3 rehearsal accepts observability/protection evidence only when intake metadata is present and valid;
  - hand-written ready observability/protection JSON is rejected;
  - failed intake checks or raw-secret flags keep the rehearsal blocked.
- Fresh verification completed:
  - `python -m py_compile scripts/commercial_environment_rehearsal_gate.py` -> passed.
  - `python -m pytest tests/test_commercial_environment_rehearsal_gate.py --no-cov -q` -> 8 passed.
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_stage5_production_rehearsal_evidence_templates.py tests/test_commercial_environment_rehearsal_gate.py --no-cov -q` -> 28 passed.
  - `python scripts/commercial_environment_rehearsal_gate.py --environment staging --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --output-json .xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.json --output-md .xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.md` -> exited 1 internally as expected; wrapper accepted the fail-closed result. Status remains `staging_rehearsal_blocked`.
- Current strict blocker details:
  - deploy, smoke, and rollback staging evidence are still bound to old SHA `743e5c4c42ff7236e1d9840f9593235a15c5404e`;
  - observability and environment-protection are blocked, template/intake checks are not passing, and `real_external_evidence_collected=false`;
  - the refreshed `.xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.json` records `external_evidence_metadata_required=true` and `external_evidence_metadata_valid=false` for both external-evidence slots.
- Claim boundary:
  - This closes another false-positive path in P0-D2.
  - It still does not close P0-D2; real owner-controlled HTTPS/443 domain evidence, release-bound deploy/smoke/rollback evidence, observability refs or explicit owner exception, environment-protection refs, and a ready strict final gate are still required.

### 2026-06-18 P0-D2 Stage3 Deploy/Smoke/Rollback External-Environment Guard

- Tightened `scripts/commercial_environment_rehearsal_gate.py` so default Stage3 rehearsal cannot accept local Docker Desktop or controlled-pilot evidence for the three environment-action reports:
  - `staging_deploy_run`, `staging_smoke_tests`, and `staging_rollback_rehearsal` now require `real_external_evidence_collected=true`;
  - `environment` must be `staging`;
  - at least one external evidence reference must be present through `external_evidence_ref`, `external_evidence_refs`, `evidence_url`, `evidence_urls`, `run_url`, or `artifact_url`;
  - `template_not_evidence`, `raw_secret_values_recorded`, `workflow_dispatch_performed`, `outbound_message_sent`, `tag_performed`, and `release_performed` must not indicate side effects or unsafe evidence;
  - `checks` must exist and all be `passed`;
  - evidence classes such as `local_staging_equivalent`, `controlled_pilot`, `controlled_pilot_only`, and `template` are rejected;
  - `claim_boundary.forbidden` must not forbid external Stage3 use.
- Added regression coverage in `tests/test_commercial_environment_rehearsal_gate.py`:
  - default Stage3 rehearsal records valid external-environment metadata for deploy/smoke/rollback when present;
  - local staging-equivalent deploy/smoke/rollback reports are rejected;
  - failed checks or missing external evidence references keep the rehearsal blocked.
- Fresh verification completed:
  - `python -m py_compile scripts/commercial_environment_rehearsal_gate.py scripts/commercial_stage3_staging_external_evidence_intake.py` -> passed.
  - `python -m pytest tests/test_commercial_environment_rehearsal_gate.py --no-cov -q` -> 10 passed.
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_stage5_production_rehearsal_evidence_templates.py tests/test_commercial_environment_rehearsal_gate.py --no-cov -q` -> 30 passed.
  - `python -m pytest tests/test_commercial_environment_rehearsal_gate.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_rc_final_gate.py tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 137 passed.
  - `python scripts/commercial_environment_rehearsal_gate.py --environment staging --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --output-json .xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.json --output-md .xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.md` -> exited 1 internally as expected; wrapper accepted the fail-closed result. Status remains `staging_rehearsal_blocked`.
- Current strict blocker details:
  - deploy, smoke, and rollback evidence are still old-SHA/local-equivalent, not release-bound external Stage3 evidence;
  - observability and environment-protection still require intake-backed external evidence metadata;
  - the target owner-verified release SHA remains `dca6a063e9c21ee5e420d3346c28735b17a92fdf`.
- Claim boundary:
  - This closes the false-positive path where local staging-equivalent deploy/smoke/rollback reports could be promoted into commercial Stage3 proof.
  - It still does not close P0-D2; real owner-controlled HTTPS/443 domain evidence, release-bound deploy/smoke/rollback refs, observability refs or an explicit owner exception, environment-protection refs, and a passing strict final gate are still required.

### 2026-06-18 P0-D2 Receipt/Evidence Pack Freshness Refresh

- Refreshed the local release receipt and evidence pack after the Stage3 rehearsal evidence reports changed, so strict final gate no longer sees stale packed evidence:
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T232222Z.zip`, sha256 `19d88e6b871167133779983cf37c1b1038af91da77a23e239f85fb2e8baa611b`, 27 evidence files; `evidence_pack_freshness` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the gate failed closed as expected.
- Current strict final-gate state:
  - all non-Stage3 gates pass, including `release_receipt` and `evidence_pack`;
  - only `staging_rehearsal` fails with `staging_rehearsal_blocked`;
  - rehearsal `release_sha`, `expected_release_sha`, and `current_head_sha` all equal `dca6a063e9c21ee5e420d3346c28735b17a92fdf`;
  - `missing_or_mismatched` remains `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Current rehearsal evidence errors:
  - deploy/smoke/rollback are still old-SHA `743e5c4c42ff7236e1d9840f9593235a15c5404e`, local staging-equivalent, missing external evidence references, and not marked as real external evidence;
  - observability and environment-protection are still blocked/template-like, not real external evidence, and their intake checks are failing;
  - environment-protection still lacks accepted public HTTPS domain endpoint and external deployed-image proof.
- Claim boundary:
  - This verifies the gate freshness problem is resolved.
  - This still does not close P0-D2 or commercial delivery; the remaining work is real owner-controlled Stage3 HTTPS/443 plus release-bound external evidence refs.

### 2026-06-18 P0-D2 HTTPS Preflight-To-Owner-Draft Prefill

- Improved the Stage3 owner evidence draft helper so a successful read-only HTTPS preflight can prefill endpoint references without turning the draft into accepted evidence:
  - added `--https-preflight-report` to `scripts/commercial_stage3_staging_external_evidence_intake.py --write-owner-draft`;
  - a ready `stage3_https_preflight_ready` report can prefill `external_endpoint.url`, `external_endpoint.health_ref`, `external_endpoint.ready_ref`, `dns_tls.dns_ref`, and `dns_tls.tls_ref`;
  - blocked or incomplete preflight reports are rejected with exit code 2 and a readable error;
  - generated drafts still keep `template_not_external_evidence=true`, `secret_binding.redaction_confirmed=false`, and `deployed_image.not_external_deploy_proof=true`, so intake remains fail-closed until the owner replaces all remaining placeholders and explicitly approves the evidence.
- Added regression coverage in `tests/test_commercial_stage3_staging_external_evidence_intake.py`:
  - ready preflight reports prefill only references and still do not pass intake as a draft;
  - blocked preflight reports cannot prefill drafts;
  - CLI reports blocked preflight errors without a traceback.
- Verification completed:
  - `python -m py_compile scripts/commercial_stage3_staging_external_evidence_intake.py scripts/stage3_https_preflight.py` -> passed.
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py --no-cov -q` -> 15 passed.
  - `python -m pytest tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_environment_rehearsal_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 145 passed.
  - `python scripts/commercial_stage3_staging_external_evidence_intake.py --write-owner-draft --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --domain '<REAL_DOMAIN>' --https-preflight-report .xagent_runtime/reports/stage3-https-preflight-20260618.json --owner xiongpinji --force` -> exited 2 internally as expected because the current preflight report is `stage3_https_preflight_blocked`; wrapper accepted the fail-closed result and no traceback was emitted.
- Claim boundary:
  - This reduces the future owner/operator JSON editing burden after a real domain exists.
  - It still does not close P0-D2; current preflight remains blocked, and the project still needs real owner-controlled DNS, trusted HTTPS/443, release-bound deploy/smoke/rollback refs, observability refs or owner exception, environment-protection refs, and strict final gate pass.

### 2026-06-18 P1-B Runbook And Docs Gate Preflight-Draft Flow

- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` so the Stage3 HTTPS checklist now tells the operator to:
  - run `python scripts/stage3_https_preflight.py --domain "<REAL_DOMAIN>"`;
  - pass the ready preflight JSON into the owner draft helper with `--https-preflight-report .xagent_runtime\reports\stage3-https-preflight-20260618.json`;
  - keep the draft blocked while `template_not_external_evidence=true`, even if `prefill_refs.https_preflight_applied=true`;
  - continue replacing remaining observability, deploy image, owner approval, and redaction placeholders with references only.
- Updated `scripts/rc_deployment_docs_gate.py` and `tests/test_rc_deployment_docs_gate.py` so the runbook must mention the preflight-to-draft flow:
  - required tokens now include `--https-preflight-report` and `prefill_refs.https_preflight_applied=true`;
  - missing the preflight-to-draft token fails `runbook_document`.
- Verification completed:
  - `python -m py_compile scripts/rc_deployment_docs_gate.py scripts/commercial_stage3_staging_external_evidence_intake.py` -> passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 24 passed.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_environment_rehearsal_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 146 passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260617T234206Z.zip`, sha256 `41a1d7d878a2c03a8a1da355d2ca6744ee7dafcb3166a1545f345449126b8d91`, 27 evidence files; `evidence_pack_freshness` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the strict final gate failed closed as expected; all non-Stage3 gates passed and only `staging_rehearsal` failed.
- Claim boundary:
  - Documentation now matches the helper flow and is guarded by tests.
  - This still does not close P0-D2; no real owner-controlled HTTPS/443 domain evidence exists yet.

### 2026-06-18 P0-D2 Five-Report Stage3 External Evidence Intake

- Extended `scripts/commercial_stage3_staging_external_evidence_intake.py` so the owner/operator intake produces all five Stage3 rehearsal evidence reports, not only observability/protection:
  - `staging_deploy_run`;
  - `staging_smoke_tests`;
  - `staging_rollback_rehearsal`;
  - `staging_observability`;
  - `staging_environment_protection`.
- The intake remains evidence-only:
  - it converts owner/operator references into gate-readable JSON/Markdown reports;
  - it does not deploy, mutate infrastructure, dispatch workflows, tag releases, publish releases, send outbound messages, or record raw secret values.
- Added regression coverage in `tests/test_commercial_stage3_staging_external_evidence_intake.py` for:
  - successful generation of all five report payloads;
  - blocked deploy/smoke/rollback refs when external references are missing or failed;
  - blocked drafts/templates;
  - preflight-assisted owner draft generation that still remains non-evidence until placeholders are replaced.
- Verification completed:
  - `python -m pytest tests/test_commercial_stage3_staging_external_evidence_intake.py --no-cov -q` -> 17 passed.
  - `python -m pytest tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_environment_rehearsal_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 148 passed.
- Claim boundary:
  - This closes a tooling gap: all five Stage3 evidence slots now have a single intake path and tests.
  - This does not close P0-D2. The five outputs are still blocked until the owner/operator supplies real release-bound external references for domain/TLS, deploy, smoke, rollback, observability or approved exception, environment protection, image proof, and owner approval.

### 2026-06-18 P0-D2 Strict Gate Evidence Refresh After Five-Report Intake

- Refreshed the docs gate, release receipt, evidence pack, and strict final gate after the five-report intake changes:
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - First parallel refresh attempt ran `python scripts/rc_release_receipt.py` and `python scripts/rc_evidence_pack.py` at the same time; receipt passed, but evidence pack failed freshness because the receipt was older than newly packed JSON reports. This was a sequencing issue, not a gate regression.
  - Corrected by running receipt and pack serially: `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T000017Z.zip`, sha256 `c6680306e948132c678d9af3c7b38ca463b3b25ff33cd25d1941eea96432ce0d`, 27 evidence files; `evidence_pack_freshness` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the strict gate failed closed as expected.
- Current strict final-gate state:
  - all non-Stage3 gates pass, including `release_receipt` and `evidence_pack`;
  - only `staging_rehearsal` fails with `staging_rehearsal_blocked`;
  - `current_head_sha`, `release_sha`, and `expected_release_sha` all equal `dca6a063e9c21ee5e420d3346c28735b17a92fdf`;
  - `missing_or_mismatched` is exactly `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Claim boundary:
  - This confirms local release/evidence freshness is green.
  - This still does not close commercial delivery. The remaining blocker is real owner-controlled Stage3 HTTPS/443 plus release-bound external evidence refs for all five Stage3 slots.

### 2026-06-18 P0-D2 Owner Domain Guide For Non-Expert Stage3 Setup

- Added `scripts/stage3_owner_domain_guide.py` as a redaction-safe, read-only owner/operator guide generator:
  - accepts a real owner-controlled domain and release SHA;
  - writes `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.json` and `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.md`;
  - emits DNS, Nginx, Certbot, HTTPS probe, preflight, owner-draft, intake, rehearsal, and strict final-gate commands;
  - records `mutation_performed=false`, `deploy_performed=false`, `workflow_dispatch_performed=false`, and `raw_secret_values_recorded=false`;
  - blocks bare IPs, localhost, single-label hosts, URL credentials, paths, HTTP URLs, and temporary wildcard DNS such as `sslip.io` without printing server commands.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md`, `scripts/rc_deployment_docs_gate.py`, and `tests/test_rc_deployment_docs_gate.py` so the owner-facing runbook must expose the guide before the HTTPS preflight flow.
- Added `tests/test_stage3_owner_domain_guide.py` for:
  - ready guide generation for a real-domain-shaped input;
  - fail-closed handling for `sslip.io`, bare IP, localhost, single-label, HTTP, URL credentials, and path-bearing inputs;
  - CLI JSON/Markdown output with no secret values and no mutation flags.
- Verification completed:
  - `python -m py_compile scripts/stage3_owner_domain_guide.py scripts/stage3_https_preflight.py scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_stage3_owner_domain_guide.py --no-cov -q` -> 4 passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 25 passed, 1 warning for an existing invalid escape sequence in the test fixture string.
  - `python scripts/stage3_owner_domain_guide.py --domain xagent.example.com --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf --output-json .xagent_runtime/reports/stage3-owner-domain-guide-20260618.json --output-md .xagent_runtime/reports/stage3-owner-domain-guide-20260618.md` -> `stage3_owner_domain_guide_ready`; example-domain guide written for operator usability only, not accepted as real Stage3 evidence.
  - `python scripts/stage3_owner_domain_guide.py --domain xagent.111.228.49.160.sslip.io --output-json .xagent_runtime/reports/stage3-owner-domain-guide-blocked-20260618.json --output-md .xagent_runtime/reports/stage3-owner-domain-guide-blocked-20260618.md; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> blocked as expected and wrapper returned 0.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T001052Z.zip`, sha256 `926f6cfe0636dc536e9014b74829719818b9be9f490cc180d4d4a38c9db7cce6`, 27 evidence files; `evidence_pack_freshness` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the strict gate failed closed as expected.
  - `python -m pytest tests/test_stage3_owner_domain_guide.py tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_environment_rehearsal_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 153 passed.
- Current strict final-gate state:
  - all non-Stage3 gates pass;
  - only `staging_rehearsal` fails with `staging_rehearsal_blocked`;
  - `missing_or_mismatched` remains exactly `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Claim boundary:
  - This reduces owner/operator execution ambiguity without asking for secret values.
  - This still does not close P0-D2. The example-domain guide is not evidence. A real owner-controlled domain, trusted HTTPS/443, release-bound deploy/smoke/rollback refs, observability refs or owner exception, environment-protection refs, image proof, owner approval, intake, rehearsal, and strict final gate pass are still required.

### 2026-06-18 P0-D2 Owner Domain Guide Auto-Detects Release SHA

- Improved `scripts/stage3_owner_domain_guide.py` so the basic owner command no longer requires manually copying the 40-character release SHA:
  - when `--release-sha` is omitted, the guide reads `.xagent_runtime/reports/rc-external-smoke.json`;
  - it uses `hosted_github_actions_run.details.head_sha` only when that check passed, `head_sha_verified=true`, the SHA is 40 hex characters, and `expected_head_sha` matches when present;
  - if the verified SHA is unavailable, the guide keeps `<OWNER_VERIFIED_HEAD_SHA>` and marks the `release_sha_source` check failed instead of guessing.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md`, `scripts/rc_deployment_docs_gate.py`, and `tests/test_rc_deployment_docs_gate.py` so the owner-facing command is now:
  - `python scripts/stage3_owner_domain_guide.py --domain "<REAL_DOMAIN>"`
  - `--release-sha <40-character-sha>` remains documented only for intentional alternate RC commits.
- Added regression coverage in `tests/test_stage3_owner_domain_guide.py` for:
  - auto-detecting a verified hosted Actions `head_sha`;
  - retaining the placeholder when `head_sha_verified` is false;
  - CLI generation with `--external-smoke-report` and no explicit `--release-sha`.
- Verification completed:
  - `python -m py_compile scripts/stage3_owner_domain_guide.py scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_stage3_owner_domain_guide.py --no-cov -q` -> 6 passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 25 passed, 1 warning for an existing invalid escape sequence in the test fixture string.
  - `python scripts/stage3_owner_domain_guide.py --domain xagent.example.com --output-json .xagent_runtime/reports/stage3-owner-domain-guide-20260618.json --output-md .xagent_runtime/reports/stage3-owner-domain-guide-20260618.md` -> `stage3_owner_domain_guide_ready`; generated JSON used release SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf` from `.xagent_runtime/reports/rc-external-smoke.json hosted_github_actions_run.head_sha`; no mutation/deploy/workflow/secret recording flags were set.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_stage3_owner_domain_guide.py tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_environment_rehearsal_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 155 passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T002326Z.zip`, sha256 `5186a167bc9c1ea4743de035369f88b5a893e682fb856f817bed45318df8d4cc`, 27 evidence files; `evidence_pack_freshness` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the strict gate failed closed as expected.
- Current strict final-gate state:
  - all non-Stage3 gates pass;
  - only `staging_rehearsal` fails with `staging_rehearsal_blocked`;
  - `missing_or_mismatched` remains exactly `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Claim boundary:
  - This removes one manual owner/operator copy-paste step.
  - This still does not close P0-D2. The example-domain guide is not real Stage3 evidence, and the final strict gate still requires real owner-controlled DNS, trusted HTTPS/443, and all five release-bound Stage3 evidence refs.

### 2026-06-18 P0-D2 Owner Evidence Todo Extractor And Docs Gate Refresh

- Added `scripts/stage3_owner_evidence_todo.py` to turn the blocked Stage3 owner draft into beginner-facing no-secret todo reports:
  - reads `.xagent_runtime/reports/stage3-staging-external-evidence-owner-draft-20260616.json` by default;
  - writes `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.json` and `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.md`;
  - categorizes remaining fields as `owner_decision`, `operator_ref`, `codex_prefill`, `owner_secret_ref`, or `final_toggle`;
  - records `mutation_performed=false`, `deploy_performed=false`, `workflow_dispatch_performed=false`, and `raw_secret_values_recorded=false`;
  - treats secret refs as owner confirmation work until `secret_binding.redaction_confirmed=true`, without asking for or recording secret values.
- Updated `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` so the Stage3 flow now says to run `python scripts/stage3_owner_evidence_todo.py` immediately after generating the owner draft, then use the Markdown todo file instead of manually reading the large JSON draft.
- Updated `scripts/rc_deployment_docs_gate.py` and `tests/test_rc_deployment_docs_gate.py` so the runbook must include the owner-evidence todo command and its two generated report paths.
- Verification completed:
  - `python -m py_compile scripts/stage3_owner_evidence_todo.py scripts/commercial_stage3_staging_external_evidence_intake.py` -> passed.
  - `python -m pytest tests/test_stage3_owner_evidence_todo.py --no-cov -q` -> 4 passed.
  - `python -m pytest tests/test_rc_deployment_docs_gate.py --no-cov -q` -> 26 passed, 1 existing fixture warning for an invalid escape sequence.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python -m pytest tests/test_stage3_owner_evidence_todo.py tests/test_stage3_owner_domain_guide.py tests/test_stage3_https_preflight.py tests/test_commercial_stage3_staging_external_evidence_intake.py tests/test_commercial_environment_rehearsal_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 160 passed.
  - `python scripts/stage3_owner_evidence_todo.py` -> `stage3_owner_evidence_todo_ready`, 32 todo items; wrote `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.json/.md`.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T004524Z.zip`, sha256 `7e0719ee1612ef565bd582a292214ecbfd3991ec4b2e5342cd578b9f320f4559`, 27 evidence files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the strict gate failed closed as expected.
- Current strict final-gate state:
  - all non-Stage3 gates pass;
  - only `staging_rehearsal` fails with `staging_rehearsal_blocked`;
  - the remaining blocker is still real owner-controlled Stage3 external evidence for `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Claim boundary:
  - This makes the owner/operator evidence work understandable without requiring secret values or manual JSON spelunking.
  - This still does not close P0-D2 or commercial delivery. A real owner-controlled domain, trusted HTTPS/443, release-bound deploy/smoke/rollback refs, observability refs or owner exception, environment-protection refs, intake readiness, rehearsal readiness, and strict final gate pass are still required.

### 2026-06-18 P1-B Evidence Pack Includes Owner Todo Reports

- Updated `scripts/rc_evidence_pack.py` so the commercial RC evidence pack now requires the beginner-facing owner todo outputs:
  - `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.json`;
  - `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.md`.
- Updated `tests/test_rc_evidence_pack.py` so `test_evidence_pack_creates_zip_with_manifest` verifies both files appear in `report.files` and inside the generated zip archive.
- Verification completed:
  - `python -m py_compile scripts/rc_evidence_pack.py` -> passed.
  - `python -m pytest tests/test_rc_evidence_pack.py --no-cov -q` -> 20 passed.
  - `python -m pytest tests/test_stage3_owner_evidence_todo.py tests/test_rc_evidence_pack.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 142 passed.
  - `python scripts/stage3_owner_evidence_todo.py` -> `stage3_owner_evidence_todo_ready`, 32 todo items.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
- Code review found one real gap after the initial patch: `scripts/rc_final_gate.py` also needed to treat `stage3-owner-evidence-todo-20260618.json` as an evidence-pack freshness input, otherwise a regenerated owner todo could leave the old evidence pack falsely fresh.
- Fixed the gap by adding `stage3_owner_evidence_todo` to `DEFAULT_INPUTS` and `EVIDENCE_PACK_FRESHNESS_INPUTS`, adding the `--stage3-owner-evidence-todo` CLI parameter, and passing it through `main()` inputs.
- Additional regression coverage:
  - `tests/test_rc_final_gate.py::test_final_gate_freshness_inputs_are_available_to_defaults_and_cli`;
  - `tests/test_rc_final_gate.py::test_final_gate_requires_evidence_pack_refresh_after_stage3_owner_todo_changes`;
  - `tests/test_rc_evidence_pack.py::test_evidence_pack_fails_when_stage3_owner_todo_report_missing`.
- Verification after the review fix:
  - `python -m py_compile scripts/rc_final_gate.py scripts/rc_evidence_pack.py` -> passed.
  - `python -m pytest tests/test_rc_final_gate.py::test_final_gate_freshness_inputs_are_available_to_defaults_and_cli tests/test_rc_final_gate.py::test_final_gate_requires_evidence_pack_refresh_after_stage3_owner_todo_changes tests/test_rc_evidence_pack.py::test_evidence_pack_fails_when_stage3_owner_todo_report_missing --no-cov -q` -> 3 passed.
  - `python -m pytest tests/test_stage3_owner_evidence_todo.py tests/test_rc_evidence_pack.py tests/test_rc_deployment_docs_gate.py tests/test_rc_final_gate.py --no-cov -q` -> 145 passed.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T012123Z.zip`, sha256 `e5cc301527dbe92c75bd020f28fa96819aa5e81d458174282bac22dc2d9e0e1f`, 29 evidence files; `required_files`, `evidence_pack_freshness`, `evidence_secret_scan`, and `evidence_local_path_privacy_scan` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json; if ($LASTEXITCODE -eq 1) { exit 0 } else { exit $LASTEXITCODE }` -> wrapper returned 0 after the strict gate failed closed as expected.
- Current strict final-gate state:
  - all non-Stage3 gates still pass;
  - only `staging_rehearsal` remains blocked;
  - this does not close P0-D2 or commercial delivery because real owner-controlled Stage3 HTTPS/443 and release-bound external evidence are still missing.

### 2026-06-18 P1-B Stage3 Owner Quickstart And Evidence Pack Integration

- Added `scripts/stage3_owner_quickstart.py` as a no-secret, read-only owner/operator quickstart generator:
  - writes `.xagent_runtime/reports/stage3-owner-quickstart-20260618.json`;
  - writes `.xagent_runtime/reports/stage3-owner-quickstart-20260618.md`;
  - summarizes Stage3 into six steps: real domain, trusted HTTPS, read-only preflight, references-only owner evidence, Stage3 intake/rehearsal, and strict final gate;
  - keeps example-domain guide output as `<REAL_DOMAIN>` so owner/operator instructions do not accidentally treat `xagent.example.com` as a configured domain;
  - records `mutation_performed=false`, `deploy_performed=false`, `workflow_dispatch_performed=false`, and `raw_secret_values_recorded=false`.
- Integrated the quickstart into the delivery control path:
  - `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` now mentions `python scripts/stage3_owner_quickstart.py`;
  - `scripts/rc_deployment_docs_gate.py` now requires the quickstart command plus both quickstart report paths;
  - `scripts/rc_evidence_pack.py` now requires the quickstart JSON/Markdown reports in the commercial RC evidence pack;
  - `scripts/rc_final_gate.py` now treats `stage3-owner-quickstart-20260618.json` as an evidence-pack freshness input and exposes `--stage3-owner-quickstart`.
- Added/updated regression coverage:
  - `tests/test_stage3_owner_quickstart.py`;
  - `tests/test_rc_deployment_docs_gate.py`;
  - `tests/test_rc_evidence_pack.py`;
  - `tests/test_rc_final_gate.py`.
- Verification completed:
  - `python -m py_compile scripts/stage3_owner_quickstart.py scripts/rc_deployment_docs_gate.py scripts/rc_evidence_pack.py scripts/rc_final_gate.py` -> passed.
  - `python -m pytest tests/test_stage3_owner_quickstart.py --no-cov -q` -> 4 passed.
  - `python -m pytest tests/test_stage3_owner_quickstart.py tests/test_stage3_owner_evidence_todo.py tests/test_rc_deployment_docs_gate.py tests/test_rc_evidence_pack.py tests/test_rc_final_gate.py --no-cov -q` -> 152 passed.
  - `python scripts/stage3_owner_evidence_todo.py` -> `stage3_owner_evidence_todo_ready`, 32 todo items.
  - `python scripts/stage3_owner_quickstart.py` -> `stage3_owner_quickstart_ready`, 32 remaining todo items, release SHA `dca6a063e9c21ee5e420d3346c28735b17a92fdf`; generated Markdown now uses `<REAL_DOMAIN>` in the six-step commands while the default domain guide still contains only example-domain guidance.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T022206Z.zip`, sha256 `f10347fe01bbd035fbc534879085faa7f3b59730489d1ceb4ac7d5887ee0262d`, 31 evidence files; `required_files`, `evidence_pack_freshness`, `evidence_secret_scan`, and `evidence_local_path_privacy_scan` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json` -> failed closed as expected because `staging_rehearsal` remains blocked.
- Current strict final-gate state:
  - all non-Stage3 gates still pass;
  - only `staging_rehearsal` remains blocked;
  - `missing_or_mismatched` remains exactly `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Claim boundary:
  - This closes a handoff/usability gap for a non-expert owner/operator and ensures the quickstart is included in freshness and evidence-pack controls.
  - This still does not close P0-D2 or commercial delivery. A real owner-controlled domain, trusted HTTPS/443 `/health` and `/ready`, release-bound deploy/smoke/rollback refs, observability refs or owner exception, environment-protection refs, intake readiness, rehearsal readiness, and strict final gate pass are still required.

### 2026-06-18 P0-D2 Real Domain Candidate Preflight

- Owner provided real domain candidate `www.xiong-agent.com`.
- Read-only DNS and endpoint checks:
  - `Resolve-DnsName www.xiong-agent.com` -> no record returned.
  - `nslookup www.xiong-agent.com` -> NXDOMAIN.
  - `nslookup www.xiong-agent.com 8.8.8.8` -> NXDOMAIN.
  - `curl.exe -i --max-time 20 http://www.xiong-agent.com/health` -> failed with `Could not resolve host`.
  - `curl.exe -i --max-time 20 http://www.xiong-agent.com/ready` -> failed with `Could not resolve host`.
  - `curl.exe -i --max-time 20 https://www.xiong-agent.com/health` -> failed with `Could not resolve host`.
- Generated real-domain owner reports:
  - `python scripts/stage3_owner_domain_guide.py --domain www.xiong-agent.com` -> `stage3_owner_domain_guide_ready`; wrote `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.json/.md`.
  - `python scripts/stage3_owner_evidence_todo.py` -> `stage3_owner_evidence_todo_ready`, 32 todo items.
  - `python scripts/stage3_owner_quickstart.py` -> `stage3_owner_quickstart_ready`; generated six-step quickstart now uses `www.xiong-agent.com`.
  - `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com` -> exited 1 internally as expected; wrapper accepted the fail-closed result. Report status is `stage3_https_preflight_blocked`; failed checks are `dns_points_to_expected_ip`, `trusted_https_tls`, `https_health_probe`, and `https_ready_probe`, all caused by DNS resolution failure.
- Verification and evidence refresh:
  - `python -m pytest tests/test_stage3_owner_domain_guide.py tests/test_stage3_https_preflight.py tests/test_stage3_owner_quickstart.py tests/test_stage3_owner_evidence_todo.py tests/test_rc_deployment_docs_gate.py tests/test_rc_evidence_pack.py tests/test_rc_final_gate.py --no-cov -q` -> 163 passed.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `x-agent-commercial-rc-evidence-20260618T023728Z.zip`, sha256 `6e8cea4dcc7ba4f231d95f8478fc2942fceeb12113eaa3f1a1261fd55cd309de`, 31 evidence files; `required_files`, `evidence_pack_freshness`, `evidence_secret_scan`, and `evidence_local_path_privacy_scan` passed.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json` -> failed closed as expected because `staging_rehearsal` remains blocked.
- Current strict final-gate state:
  - all non-Stage3 gates still pass;
  - only `staging_rehearsal` remains blocked;
  - `missing_or_mismatched` remains exactly `staging_deploy_run`, `staging_smoke_tests`, `staging_rollback_rehearsal`, `staging_observability`, and `staging_environment_protection`.
- Next action:
  - Create DNS A record `www.xiong-agent.com -> 111.228.49.160` in the domain provider console.
  - After DNS resolves, rerun `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com`.
  - Only after DNS passes should the operator configure Nginx/Certbot HTTPS/443 using `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.md`.

### 2026-06-18 P0-D2 DNS A Record Save Recheck

- Owner confirmed saving the DNS A record in the console:
  - Host record: `www`.
  - Type: `A`.
  - Value: `111.228.49.160`.
  - Line: default.
  - TTL: 10 minutes.
- Immediate and delayed read-only DNS checks still do not resolve the record:
  - `Resolve-DnsName www.xiong-agent.com` -> no record returned.
  - `nslookup www.xiong-agent.com` -> NXDOMAIN.
  - `nslookup www.xiong-agent.com 8.8.8.8` -> NXDOMAIN.
  - `nslookup www.xiong-agent.com 223.5.5.5` -> NXDOMAIN.
  - `nslookup www.xiong-agent.com 114.114.114.114` -> NXDOMAIN.
  - `curl.exe -i --max-time 15 http://www.xiong-agent.com/health` -> failed with `Could not resolve host`.
  - `curl.exe -i --max-time 15 http://www.xiong-agent.com/ready` -> failed with `Could not resolve host`.
  - `curl.exe -i --max-time 15 https://www.xiong-agent.com/health` -> failed with `Could not resolve host`.
- Registry and authoritative DNS diagnosis:
  - RDAP for `xiong-agent.com` now returns a registered, `active` domain.
  - Registrar: `Xin Net Technology Corporation`.
  - Domain nameservers: `FREENS1.JDGSLB.COM` and `FREENS2.JDGSLB.COM`.
  - Direct queries to the JD Cloud nameservers still return NXDOMAIN/no zone data for `www.xiong-agent.com` and `xiong-agent.com`.
- Refreshed preflight and release evidence:
  - `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com` -> `stage3_https_preflight_blocked`; DNS/TLS/health/ready checks fail on `getaddrinfo failed`.
  - `python scripts/stage3_owner_quickstart.py` -> `stage3_owner_quickstart_ready`.
  - First `python scripts/rc_evidence_pack.py` after quickstart refresh failed freshness because the release receipt was older than the newly generated report; this was expected freshness protection.
  - `python scripts/rc_release_receipt.py; python scripts/rc_evidence_pack.py` -> evidence pack created, freshness passed, `x-agent-commercial-rc-evidence-20260618T024606Z.zip`, sha256 `a09d7af8761a4f46fd23370e15b0b0f7b500168ca5bc17aefebb299086620ae4`, 31 files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime\reports\rc-final-gate-stage3-rehearsal-check.json` -> failed closed only on `staging_rehearsal`.
- Current diagnosis:
  - The domain is registered and delegated to JD Cloud nameservers, but the saved `www` A record has not appeared on the authoritative JD Cloud DNS servers yet.
  - Do not start HTTPS/Certbot configuration until `nslookup www.xiong-agent.com FREENS1.JDGSLB.COM` or `FREENS2.JDGSLB.COM` returns `111.228.49.160`.
- Next owner action:
  - In JD Cloud DNS, confirm the DNS zone being edited is exactly `xiong-agent.com`, not a different domain or inactive zone.
  - If the record is visible there, wait for JD Cloud authoritative DNS propagation and recheck direct authoritative queries.
  - If the record is not visible in the zone served by `FREENS1.JDGSLB.COM`/`FREENS2.JDGSLB.COM`, recreate the `www` A record in that exact zone.

### 2026-06-18 P0-D2 DNS Resolved, HTTP/HTTPS Blocked At Domain Edge

- Owner clarified/check target domain as `xiong-agent.com`.
- DNS is now resolved for both root and `www`:
  - `Resolve-DnsName xiong-agent.com` -> `111.228.49.160`, TTL 600.
  - `Resolve-DnsName www.xiong-agent.com` -> `111.228.49.160`, TTL 600.
  - `nslookup xiong-agent.com 8.8.8.8` -> `111.228.49.160`.
  - `nslookup xiong-agent.com 223.5.5.5` -> `111.228.49.160`.
  - `nslookup xiong-agent.com 114.114.114.114` -> `111.228.49.160`.
  - `nslookup xiong-agent.com FREENS1.JDGSLB.COM` -> `111.228.49.160`.
  - `nslookup xiong-agent.com FREENS2.JDGSLB.COM` -> `111.228.49.160`.
  - `nslookup www.xiong-agent.com FREENS1.JDGSLB.COM` -> `111.228.49.160`.
  - `nslookup www.xiong-agent.com FREENS2.JDGSLB.COM` -> `111.228.49.160`.
- Domain HTTP/HTTPS probes:
  - `curl.exe -i --max-time 15 http://www.xiong-agent.com/health` -> `HTTP/1.1 403 Forbidden`, `Server: JDTP`, HTML title `网页禁止访问`, iframe target `https://illegalitydomain.jcloud.com`.
  - `curl.exe -i --max-time 15 http://www.xiong-agent.com/ready` -> same JDTP 403 block page.
  - `curl.exe -i --max-time 15 https://www.xiong-agent.com/health` -> failed to connect to port 443.
- Existing direct Stage3 service remains healthy on temporary nonstandard HTTP port:
  - `curl.exe -i --max-time 15 http://111.228.49.160:8899/health` -> 200 OK, `{"status":"ok","service":"x-agent"}`.
  - `curl.exe -i --max-time 15 http://111.228.49.160:8899/ready` -> 200 OK, `status=ready`, `observability=degraded`.
- Refreshed preflight:
  - `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com` -> `stage3_https_preflight_blocked`.
- Current diagnosis:
  - DNS is no longer the blocker.
  - The domain is being intercepted on HTTP/80 by JD Cloud edge/access control before requests reach the app, likely because the domain is not yet permitted for web access/ICP filing/website access on this mainland server.
  - HTTPS/443 is not listening or not allowed yet.
- Next owner/operator action:
  - Check JD Cloud ICP/website access/domain access state for `xiong-agent.com` and `www.xiong-agent.com`; clear the JDTP `网页禁止访问` block before treating the domain as usable Stage3 evidence.
  - After domain access is allowed, configure Nginx on ports 80/443 and obtain a trusted certificate for `www.xiong-agent.com`.
  - Then rerun `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com`.

### 2026-06-18 P0-D2 ICP Waiting Window

- Owner confirmed `xiong-agent.com` was newly purchased and cannot enter ICP filing for about three business days.
- Current interpretation:
  - DNS is correct and no longer blocks Stage3.
  - The JDTP `网页禁止访问` response is consistent with mainland cloud web-access/ICP gating on a newly purchased, not-yet-filed domain.
  - The current mainland JD Cloud server cannot provide final commercial HTTPS/443 Stage3 evidence for this domain until the domain is eligible for filing and the provider access block is cleared.
- Delivery impact:
  - `python scripts/rc_final_gate.py --require-ready-to-tag` can remain green for local/owner gates.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal` must remain blocked until real external Stage3 evidence exists.
  - Temporary HTTP on `111.228.49.160:8899`, bare IP, `sslip.io`, self-signed TLS, or the current JDTP block page must not be promoted to final commercial evidence.
- Viable paths:
  - Recommended conservative path: wait until ICP filing is available, complete filing/access approval, then configure Nginx 80/443 and trusted HTTPS on `www.xiong-agent.com`.
  - Faster evidence path: use a non-mainland Stage3 host with the same real domain and trusted HTTPS, then rerun preflight and Stage3 intake there.
  - Alternative owner path: use an already-filed/approved domain or subdomain controlled by the owner, if available.
- Next action:
  - During the ICP waiting window, keep final commercial gate blocked and use the time for remaining non-domain release packaging/customer-handoff cleanup.

### 2026-06-18 Non-Domain Local Closeout For Multi-Model Audit

- Scope:
  - Completed the current local closeout slice excluding server domain/ICP/HTTPS provider access.
  - Kept final commercial Stage3 blocked until real HTTPS/443 and Stage3 rehearsal evidence exists.
- Code/test change:
  - `scripts/stage3_https_preflight.py` now derives `next_actions` from failed checks instead of always suggesting DNS repair.
  - `tests/test_stage3_https_preflight.py` now verifies DNS failures still ask for DNS repair, while DNS-passed TLS/HTTPS failures ask for port 443 and `/health` `/ready` remediation without DNS noise.
- Refreshed real-domain preflight:
  - `python scripts/stage3_https_preflight.py --domain www.xiong-agent.com` -> `stage3_https_preflight_blocked`.
  - `.xagent_runtime/reports/stage3-https-preflight-20260618.json/.md` now shows `domain_shape=passed`, `dns_points_to_expected_ip=passed`, `trusted_https_tls=failed`, `https_health_probe=failed`, and `https_ready_probe=failed`.
  - The refreshed `next_actions` are HTTPS/443/cloud-provider access and `/health` `/ready` only.
- Focused test evidence:
  - `python -m pytest tests/test_stage3_https_preflight.py --no-cov -q` -> 5 passed.
  - `python -m pytest tests/test_stage3_https_preflight.py tests/test_rc_deployment_docs_gate.py tests/test_rc_evidence_pack.py tests/test_rc_final_gate.py --no-cov -q` -> 149 passed.
  - `python -m pytest tests/test_security_auth.py tests/test_security_authz.py tests/test_main_api_key_auth.py tests/test_route_auth_audit.py --no-cov -q` -> 38 passed.
- Gate evidence:
  - `python scripts/route_auth_audit.py --json` -> `{"issues":[],"ok":true}`.
  - `python scripts/security_deployment_gate.py` -> OK, no deployment-hardening issues.
  - `python scripts/production_hardening_gate.py` -> ready, 0 findings.
  - `python scripts/rc_deployment_docs_gate.py` -> passed.
  - `python scripts/rc_release_receipt.py` -> created release receipt; artifact sha256 `924eec09cde5f2919cf26172e784baef13f54c5b99b60d1b5a140288d1a871b8`.
  - `python scripts/rc_evidence_pack.py` -> created `.xagent_runtime/release/x-agent-commercial-rc-evidence-20260618T040544Z.zip`, sha256 `e39fcbe052bd9edcb3c5a47e019f099af55a770b053cd39d26b83f296094f2f9`, 31 files.
  - `python scripts/rc_final_gate.py --require-ready-to-tag` -> `ready_for_rc_tag`.
  - `python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal --output .xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json` -> failed closed only on `staging_rehearsal`.
- Multi-model audit handoff:
  - Use this plan, `.xagent_runtime/reports/rc-final-gate.json`, `.xagent_runtime/reports/rc-final-gate-stage3-rehearsal-check.json`, `.xagent_runtime/reports/rc-evidence-pack.json`, `.xagent_runtime/reports/stage3-https-preflight-20260618.json/.md`, and the three deep-audit reports as the current input pack.
  - Treat domain/ICP/HTTPS provider access as the only intentionally excluded external blocker in this closeout slice.

## Update Rules

- Update this document after each task transition.
- Evidence must include command, result, and file/link reference.
- Never write secret values. Use configured/not configured, length, or external reference only.
- Do not mark commercial delivery complete until `rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal` passes against final evidence.
