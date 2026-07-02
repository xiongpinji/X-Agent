# API Route Scope Decision 2026-06-18

This document is the commercial-RC decision record for API modules that exist under `backend/app/api` but are not mounted by `backend.app.main:app.routes`.

## Decision Rule

- The mounted FastAPI app is the source of truth for the first-version backend surface.
- No unmounted module is promoted in this slice.
- A module can be promoted later only after it imports cleanly, is intentionally mounted in `backend/app/main.py`, passes `scripts/route_auth_audit.py --json`, has focused authorization tests, and is covered by `scripts/frontend_api_contract_audit.py`.
- Deferred frontend surfaces must stay hidden from first-version navigation.

## Inventory

- Route modules with an `APIRouter` or router decorators: 112.
- Mounted route modules in `backend.app.main:app.routes`: 56.
- Unmounted route modules requiring a decision here: 56.

## Ship Now

| Module | Reason | Required Tests |
| --- | --- | --- |
| None | All first-version route needs are already covered by mounted modules for auth/RBAC, workbench, agent run, workspace/file preview, memory, desktop, GitHub/Feishu integration, and Stage3 evidence. | No `backend/app/main.py` promotion in this task. Keep `route_auth_audit`, `frontend_api_contract_audit`, and focused security tests green. |

## Defer Hidden

| Module | Reason | Frontend Entry Removed |
| --- | --- | --- |
| `analytics` | Analytics dashboards are outside first-version scope; current evidence also shows an import failure from the wrong aggregator path. | Analytics console entry hidden; frontend API contract excludes deferred analytics files. |
| `creative_studio` | Creative studio is not in the first-version commercial scope and has no approved first-version workflow. | No first-version navigation entry. |
| `forum` | Forum/community is explicitly deferred from first version, even though the module can import. | Forum entry hidden; `Forum.tsx` is excluded as deferred surface. |
| `forum_search` | Companion forum search surface follows the deferred forum decision. | No first-version navigation entry. |
| `i18n` | Translation/localization management is not part of the first-version user workflow. | No first-version navigation entry. |
| `media` | Media APIs are not part of the first-version workbench/workspace path. | No first-version navigation entry. |
| `personalization` | Personalization is a later product surface, not required for RC delivery. | No first-version navigation entry. |
| `plugin_dev_api` | Plugin development APIs are part of the deferred plugin ecosystem. | Plugin marketplace/developer entries hidden. |
| `plugin_market` | Plugin marketplace is explicitly deferred; it can import but is not route-auth audited in the mounted app. | Plugin marketplace entries hidden. |
| `plugin_marketplace` | Duplicate marketplace implementation; current evidence shows dependency assertion failure. | Plugin marketplace entries hidden. |
| `plugin_marketplace_api` | Duplicate marketplace API; current evidence shows invalid FastAPI query parameter typing. | Plugin marketplace entries hidden. |
| `plugins` | Generic plugin management belongs to the deferred plugin ecosystem for first version. | Plugin entries hidden from first-version navigation. |
| `recommendations_advanced` | Advanced recommendations are not required for first-version workbench delivery. | No first-version navigation entry. |
| `skill_market` | Skill marketplace is explicitly deferred; promotion would require choosing the authority implementation and re-running auth audit. | Skill marketplace entries hidden. |
| `skill_market_advanced` | Advanced skill marketplace functions are part of the deferred skill ecosystem. | Skill marketplace entries hidden. |
| `skill_market_complete` | Duplicate skill marketplace implementation; current evidence shows FastAPI response-model construction failure. | Skill marketplace entries hidden. |
| `skill_marketplace` | Duplicate skill marketplace implementation and not first-version scope. | Skill marketplace entries hidden. |
| `skills` | Standalone skills routes are treated as part of the deferred skill marketplace surface; mounted `skill_curator` remains the first-version controlled path. | Skill marketplace entries hidden. |
| `skills_api` | Legacy `/api/skills` marketplace-style API is not mounted for first version; previous auth fixes do not make it a ship surface. | Skill marketplace entries hidden. |
| `streaming_enhanced` | First version uses mounted agent SSE stream paths; enhanced realtime visualization is not a ship surface. | Realtime visualization surface deferred from first-version API contract. |
| `subscriptions` | Public subscription/notification flows are deferred from first version. | Public notification subscription entry hidden. |
| `templates` | Templates marketplace is explicitly deferred; current evidence shows missing `backend.app.core.workflows.template_system`. | Template marketplace/editor entries hidden. |
| `translation_management` | Translation management is not part of first-version commercial workflow. | No first-version navigation entry. |
| `vision` | Vision APIs are not part of first-version desktop/workbench delivery. | No first-version navigation entry. |

## Internal Only

| Module | Reason | Access Control |
| --- | --- | --- |
| `api_keys` | Useful for operator/admin lifecycle later, but not a first-version mounted product page. | Must require principal/admin scope before promotion; add API-key lifecycle tests. |
| `audit_enhanced` | Mounted `audit` is the first-version audit surface; enhanced audit remains internal until reviewed. | Must pass route auth audit and audit-store integrity tests before promotion. |
| `audit_export_api` | Audit export can expose sensitive records and is not first-version UI scope. | Must require tenant/admin authorization and export redaction tests before promotion. |
| `backup` | Backup operations are operator-only and should not become public product routes by default. | Must require operator/admin principal and destructive-action safeguards. |
| `backup_monitoring` | Backup monitoring is ops-only. | Must require operator/admin principal. |
| `billing` | Billing is commercially important but not wired to a real payment/provider contract in first-version scope. | Must require tenant/admin scope, provider sandbox evidence, and webhook signature tests before promotion. |
| `code_execution` | Code execution is high risk and must stay internal until sandbox policy is reviewed. | Must require explicit execution scope and sandbox escape regression tests. |
| `enterprise` | Enterprise admin APIs are outside current first-version scope. | Must require tenant/admin/enterprise scopes and focused authz tests before promotion. |
| `enterprise_audit` | Enterprise audit is sensitive and not first-version mounted. | Must require enterprise admin scope. |
| `enterprise_cluster` | Cluster management is operator/enterprise-only. | Must require operator/admin scope. |
| `enterprise_im` | Enterprise IM integration is not part of first-version Feishu/GitHub path. | Must require enterprise integration scope. |
| `enterprise_migration` | Migration APIs are operator-only. | Must require operator/admin scope and migration dry-run tests. |
| `enterprise_sso` | Enterprise SSO route layer remains unmounted while SAML/OIDC core stays tested; public auth callbacks need separate provider evidence. | Must require enterprise admin for config and fail-closed callback tests before promotion. |
| `health_checks` | Mounted `health` already covers first-version health/ready checks. | Keep internal diagnostics off public surface unless explicitly scoped. |
| `jwt_key_rotation` | Key rotation is security-ops only. | Must require security-admin principal and rotation rollback tests. |
| `llm_providers` | LLM provider management is operator configuration, not a first-version route surface. | Must require operator/admin scope and secret-redaction tests. |
| `mcp` | MCP management is internal connector control. | Must require integration/admin scope and connector isolation tests. |
| `oauth_routes` | Full OAuth marketplace flows are deferred from first version. | Must use real token/session semantics before any mount. |
| `partners` | Partner API is not part of first-version self-serve surface. | Must require partner-scoped auth and tenant boundary tests. |
| `scheduler` | Scheduler control is operational automation. | Must require operator/admin scope. |
| `sessions` | Session API has focused auth tests but is not mounted or required by first-version frontend routing. | Keep unmounted until a current workbench/desktop caller is identified; rerun session authz tests before promotion. |
| `sso` | WebAuthn/passkey and full OAuth/conditional-access flows are deferred. | Keep fail-closed semantics; mount only after provider evidence and auth tests. |
| `tenant_isolation` | Tenant isolation diagnostics are security-internal. | Must require security-admin scope. |
| `webhooks` | Generic webhook ingress must not be exposed without per-provider signature contracts. | Must require signature verification tests before promotion. |

## Delete Or Archive Later

| Module | Reason | Replacement |
| --- | --- | --- |
| `agent` | Legacy/alternate agent API overlaps mounted `agents`, `execution`, and `runs`. | Mounted `agents`, `execution`, `runs`, and `workbench`. |
| `agents_v2` | Duplicate agent implementation not selected for first-version authority. | Mounted `agents`. |
| `artifacts` | Artifact route surface is not selected and overlaps workspace/file-preview flows. | Mounted `workspace` and `file_preview` for first version. |
| `artifacts_api` | Duplicate artifacts implementation. | Mounted `workspace` and `file_preview`. |
| `collaboration_enhanced` | Enhanced collaboration overlaps mounted base collaboration surface and is not first-version scope. | Mounted `collaboration`, `messages`, and `workbench` paths. |
| `files_v2` | Alternate files API overlaps mounted workspace/file preview. | Mounted `workspace` and `file_preview`. |
| `search` | Duplicate search route family, not selected for first version. | Workbench/resource-specific search paths, if needed, must be added through mounted BFFs. |
| `search_api` | Duplicate search route family. | Same as `search`; do not mount both. |
