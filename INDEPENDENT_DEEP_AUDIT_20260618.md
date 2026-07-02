# X-Agent Independent Deep Audit

Date: 2026-06-18
Scope: current working tree at `D:\AI编程库\项目库\进行中的项目\X-Agent`
Mode: independent review from current code, config, routes, and locally runnable gates. Existing `audit_reports/` conclusions were not used as authority.

## Executive Summary

X-Agent is materially improved on local security gates, but it is not yet commercially deliverable.

Estimated current state:

- Code/security readiness: 88% to 92%
- Commercial delivery readiness: 75% to 82%
- Final delivery status: blocked

The main remaining commercial blockers are owner/operator returned references, Stage3/production evidence, and final gate readiness. In addition, several real code-level risks remain and should be fixed before any commercial-ready claim.

## Evidence Reviewed

This audit used current repository state and local commands only.

Validated positive evidence:

- `python scripts/route_auth_audit.py --json`
  - Result: `{"issues": [], "ok": true}`
- Security/auth focused regression:
  - `116 passed, 1 skipped`
- Deployment hardening regression:
  - `44 passed`
- Commercial gate focused regression:
  - `131 passed`
- `python scripts/security_deployment_gate.py --json`
  - Result: no deployment-hardening issues found

Delivery evidence state:

- `.xagent_runtime/reports/commercial-delivery-closure-snapshot.json`
  - `status`: `commercial_delivery_closure_blocked`
  - `delivery_complete`: `false`
  - blocker: `owner_staging_preflight_not_ready`
- `.xagent_runtime/reports/owner-operator-commercial-delivery-intake.json`
  - `status`: `owner_operator_commercial_delivery_intake_blocked`
  - `ready_for_review`: `false`
  - blockers: missing required fields and non-passing critical status fields
- `.xagent_runtime/reports/rc-final-gate.json`
  - Text indicates `ready_with_owner_gates`
  - Text indicates owner gates remain `action_required`
  - The file could not be parsed by a standard JSON parser due invalid escaping, so it is not currently a clean machine-readable final-gate artifact.

## High Priority Findings

### 1. Cross-Tenant Memory Disclosure

Affected files:

- `backend/app/api/memory.py`
- `backend/app/core/memory/store.py`

Risk:

Several memory endpoints enforce `memory:read` but do not consistently filter returned records by `principal.tenant_id`.

Observed paths:

- `POST /api/v1/memory/search`
  - fallback path uses `memory.layer_items(layer)` and filters by content terms only.
- `GET /api/v1/memory/layers/{layer}`
  - returns `memory.layer_items(layer)` across all tenants in the in-memory backend.
- `GET /api/v1/memory/sessions/{session_id}`
  - returns session items by `session_id` without checking tenant ownership.

Impact:

An authenticated caller with `memory:read` may read another tenant's memory/RAG contents, metadata, session IDs, and agent context when using the affected backend path.

Recommended fix:

- Require every memory listing/detail/search fallback to filter by `principal.tenant_id`.
- Add tests that create tenant A and tenant B memory items, then assert tenant A cannot read tenant B via layer detail, session detail, or fallback search.

### 2. API Key and User Administration Lack Object-Level Tenant Boundaries

Affected files:

- `backend/app/api/security.py`
- `backend/app/api/users.py`
- `backend/app/core/security.py`
- `backend/app/core/admin.py`

Risk:

The routes enforce `security:manage`, but object-level tenant checks are not visible.

Observed behavior:

- API key creation accepts request-controlled `tenant_id`, `user_id`, `role`, and `scopes`.
- API key list/get/revoke operates over global records.
- User list/create/update/delete uses global `user_store`.
- User update can affect role and tenant data.

Impact:

If `security:manage` is tenant-scoped rather than a platform-superadmin-only permission, this enables cross-tenant API key disclosure, key revocation, user enumeration, role changes, and tenant movement.

Recommended fix:

- Decide and encode permission semantics:
  - `security:manage` for tenant admin only: restrict to `principal.tenant_id`.
  - platform superadmin: require an explicit global/admin scope separate from tenant admin.
- For tenant admins, ignore caller-supplied tenant IDs and bind created keys/users to `principal.tenant_id`.
- Add cross-tenant tests for list/get/revoke/create/update/delete.

### 3. Postgres Audit Signatures Use a Fixed HMAC Secret

Affected file:

- `backend/app/core/audit_postgres.py`

Risk:

`PostgresAuditStore._signature_record()` signs audit records with hardcoded `default-secret`.

Impact:

Audit signatures are predictable and cannot provide meaningful tamper evidence. Anyone with code access can forge valid signatures.

Recommended fix:

- Require audit HMAC secret from configuration or secret store.
- In production mode, fail closed if the secret is absent or weak.
- Add regression tests proving `default-secret` is rejected.

### 4. SSO/OIDC/WebAuthn Security Debt

Affected files:

- `backend/app/core/saml_sso.py`
- `backend/app/core/sso/saml_provider.py`
- `backend/app/core/enterprise_sso.py`
- `backend/app/core/sso/webauthn_provider.py`
- `backend/app/api/sso.py`

Risks:

- `SAMLManager.parse_response()` parses and returns an assertion even when `_verify_signature()` returns false, relying only on a `signature_valid` flag.
- `OIDCManager.decode_id_token()` uses `jwt.decode(..., options={"verify_signature": False})`.
- WebAuthn provider contains a TODO for public-key signature verification and currently accepts authentication after challenge/credential checks.
- WebAuthn API includes TODO/commented verification paths and returns successful placeholder responses if that router is included.

Impact:

Default-mounted reachability varies by route, but these helpers and routers are unsafe to rely on for production SSO/OIDC/WebAuthn authentication.

Recommended fix:

- Make SAML parsing fail closed when signature verification fails.
- Verify OIDC ID token signature, issuer, audience, nonce, and expiry.
- Disable WebAuthn endpoints until real verification is implemented, or wire a standards-compliant verifier.
- Add tests that reject unsigned SAML, forged OIDC ID tokens, and bogus WebAuthn assertions.

### 5. Sensitive Data Can Leak to Logs

Affected files:

- `backend/app/api/auth.py`
- `backend/app/core/sso/mfa_manager.py`
- `backend/app/core/middleware/logging_middleware.py`

Risks:

- Token storage/revocation debug logs include full bearer token values.
- MFA email sender logs the email verification code and email address at info level.
- Request logging records raw query strings and can record raw request/response bodies without a sanitizer.

Impact:

Log readers can recover active tokens, MFA codes, reset/query tokens, API keys, or PII.

Recommended fix:

- Redact bearer tokens and token-like values before logging.
- Never log MFA verification codes.
- Route request/response logging through a shared redaction utility.
- Add tests for token, password, code, query string, and body redaction.

## Medium Priority Findings

### 6. MCP File Tool Path Boundary Uses String Prefix Check

Affected file:

- `backend/app/core/mcp/tools/file_tool.py`

Risk:

`_resolve_path()` checks containment with `str(resolved).startswith(str(base_path))`.

Impact:

Sibling paths such as `/repo/work-evil` can pass a prefix check for `/repo/work` on some layouts.

Recommended fix:

- Use `Path.relative_to()` on resolved paths.
- Add tests for sibling-prefix escape and symlink escape.

### 7. Browser URL Guard Does Not Resolve DNS

Affected files:

- `backend/app/api/browser.py`
- `backend/app/services/browser/automation.py`
- `backend/app/services/browser/playwright_client.py`

Risk:

The API blocks literal private IPs and localhost, but does not resolve hostnames before browser navigation.

Impact:

An attacker-controlled hostname can resolve to private/link-local addresses and cause SSRF through the browser.

Recommended fix:

- Centralize URL safety in a resolver-backed guard.
- Block private, loopback, link-local, multicast, and reserved resolved addresses.
- Apply the guard in both route-level and lower-level browser service APIs.

### 8. CI and Production Workflow Enforcement Needs Hardening

Affected files:

- `.github/workflows/security.yml`
- `.github/workflows/deploy.yml`

Risks observed in static discovery:

- Security scanners are configured fail-open in places.
- Some scanner actions use moving refs such as `main` or `master`.
- Production deploy and health/rollback steps include commented commands or `continue-on-error`.

Impact:

CI may report green without enforcing security scan, image scan, deploy, health, or rollback proof.

Recommended fix:

- Pin security actions to immutable versions.
- Remove `continue-on-error` from blocking security/deploy gates.
- Ensure production deploy, health check, and rollback commands are real and fail closed.

### 9. Legacy/Secondary Deployment Manifests Still Contain Unsafe Examples

Affected examples observed:

- `k8s/deployment.yml`
- selected monitoring files and docs
- `backend/app/core/enterprise_deployment.py`

Risk:

Some non-primary manifests/templates still contain `:latest`, placeholder secrets, disabled auth, or weak defaults.

Impact:

If operators apply these files instead of hardened primary manifests, they can deploy mutable images or weak credentials.

Recommended fix:

- Decide which manifests are supported.
- Move unsupported examples out of deployable paths or add explicit non-production guards.
- Make all deployable manifests pass the same hardening gate.

## Current Delivery Blockers

The project should not be marked commercial-ready until all of the following are true:

- `commercial-delivery-closure-snapshot.json` reports complete.
- `owner-operator-commercial-delivery-intake.json` is ready for review and contains required owner/operator refs.
- `rc_final_gate.py --require-ready-to-tag` exits 0.
- Real owner gate evidence exists for provider, Feishu webhook, GitHub issue-to-PR dry run, GitHub execute preflight, hosted GitHub Actions Commercial RC, and owner-verified refresh chain.
- Real Stage3/production evidence exists for external HTTPS endpoint, DNS/TLS/LB/Ingress, deployed image digest/provenance, observability, rollback rehearsal, and production readiness acceptance.
- Remaining high-priority code issues above are fixed and independently reverified.

## Recommended Work Plan

### Codex

Fix application security issues:

- Cross-tenant memory disclosure.
- API key/user object-level tenant boundaries.
- Audit HMAC secret enforcement.
- Token/MFA/request logging redaction.
- SAML fail-closed parsing and OIDC signature validation.

### Claude Code

Fix delivery/CI/deployment hardening:

- Fail-closed CI scanners.
- Production deploy/health/rollback proof.
- Unsupported or unsafe deployable manifests.
- Ensure deployment hardening gate runs in server-side CI, not only pre-commit.

### ZCode

Read-only verification:

- Reverify tenant isolation with cross-tenant tests.
- Reverify log redaction.
- Reverify SSO/OIDC/WebAuthn fail-closed behavior.
- Reverify CI/deploy workflow enforcement.
- Produce final PASS / FAIL / BLOCKED_BY_OWNER_INPUT status.

## Final Assessment

Current status: not commercially deliverable.

Reason:

Local tests and security gates are much stronger now, but final delivery is blocked by owner/Stage3 evidence and several remaining high-priority application security issues. The project is close to a hardened release candidate, but not yet at commercial delivery standard.
