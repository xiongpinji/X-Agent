# X-Agent Production Security Decision List

Date: 2026-06-05 (original)  
Closed: 2026-07-19 by Security Decision Closure (P0-08), Phase 1 stabilization  
Status: **ALL DECISIONS CLOSED** — evidence cited as `path:line` against the 2026-07-19 working tree (baseline commit f3aab93). Full closure report (Chinese): `commercial_audit/security_decisions_closure_2026-07-19.md`.

---

## Already hardened (re-verified 2026-07-19, no decision needed)

The following security controls are already enforced in production by `backend/app/settings.py` validators:

- `XAGENT_AUDIT_HMAC_SECRET` — required in production (validator raises on empty)
- `XAGENT_JWT_SECRET` — must be ≥32 chars with uppercase + digits; default rejected in production (`backend/app/settings.py:100-125`)
- `XAGENT_ENCRYPTION_KEY` — same enforcement as JWT_SECRET
- `XAGENT_CORS_ORIGINS` — wildcard rejected in production mode (`backend/app/settings.py:139-150`)
- `XAGENT_ENABLE_HIGH_RISK_TOOLS` — defaults to `false` (`backend/app/settings.py:67`); write/patch tools require explicit opt-in

---

## Decisions — closed 2026-07-19

### D-1 API key enforcement in production (MEDIUM risk) — ✅ CLOSED, Option A adopted

Original concern: `XAGENT_REQUIRE_API_KEY=false` in both dev and the docker-compose default; API open if deployed without a reverse proxy or token gateway.

**Decision: Option A adopted** — the production profile requires API-key auth; dev stays open by default.

Evidence (verified 2026-07-19):
- `.env.production:82` — `XAGENT_REQUIRE_API_KEY=true`
- `DEPLOYMENT.md:78,102` — production deployment profiles set `XAGENT_REQUIRE_API_KEY=true`; `DEPLOYMENT.md:114` keeps `false` explicitly for local development only
- `backend/app/settings.py:20` — code default remains `false` (developer convenience); the production value is injected via environment

Residual notes (non-blocking; tracked in closure report §5):
- `docker-compose.yml:136,211` still use the `${XAGENT_REQUIRE_API_KEY:-false}` fallback and no `env_file:` entry wires `.env.production` into compose — operators must export the variable (or follow DEPLOYMENT.md). Recommend flipping the compose fallback to `:-true` in the deployment-hardening batch (outside P0-08 scope).
- Option B (startup WARNING when `APP_MODE=production` and `REQUIRE_API_KEY=false`) was **not** implemented; judged unnecessary now that Option A is in force.

### D-2 HMAC-signed GitHub webhook secret (LOW risk) — ✅ CLOSED, Option A adopted (+ production WARNING active)

Original concern: if `XAGENT_GITHUB_WEBHOOK_SECRET` is empty in production, webhooks are unauthenticated.

**Decision: Option A adopted** — placeholder in the production env file plus deployment documentation. A startup WARNING (a weaker form of Option B) is also already in place.

Evidence (verified 2026-07-19):
- `.env.production:44` — `XAGENT_GITHUB_WEBHOOK_SECRET=REPLACE_WITH_GENERATED_SECRET`
- `DEPLOYMENT.md:104` — documents `XAGENT_GITHUB_WEBHOOK_SECRET=your-webhook-secret`
- `backend/app/settings.py:129-137` — in production mode an empty webhook secret logs a startup WARNING ("GitHub webhooks will be unauthenticated")
- Signature verification itself (`X-Hub-Signature-256`, HMAC-SHA256, constant-time comparison) confirmed in `backend/app/core/sandbox/github_webhook.py` (see `commercial_audit/12_security_compliance_audit.md`)

Residual note: the validator warns instead of raising; upgrading it to fail-fast in production is logged as a P1 hardening suggestion (closure report §5.4).

### D-3 Secret files still tracked in git (HIGH risk) — ✅ CLOSED, risk eliminated by repo rebuild (2 follow-ups tracked)

Original concern: `data/api_keys.json` (and potentially other `data/` files, possibly containing real API-key hashes) was tracked in a previous commit; any clone of the repo could read historical contents.

**Decision: risk eliminated — the intended outcome of Option A (history scrub) was achieved more thoroughly by a full repository rebuild.** No `git filter-repo`/BFG run is needed or possible.

Facts (verified 2026-07-19):
- The git repository was **re-initialized fresh on 2026-07-19**. `git rev-list --all --count` = 1; the only commit is `f3aab93 chore: 商用修复基线快照 (审计前状态, 2026-07-19)`. No remotes are configured (`git remote -v` empty) and `git fsck` shows no dangling objects — the old history is **unreachable in any form** on this machine.
- `data/api_keys.json` is **absent** from the working tree (`data/` holds only gitignored runtime files), **not tracked** (`git ls-files data/` is empty), and **gitignored** (`.gitignore:38` and `.gitignore:196`).
- A full working-tree secret scan on 2026-07-19 (patterns: `sk-*`, `AKIA*`, `-----BEGIN * PRIVATE KEY-----`, `password=`, `ghp_*`, `xox*`, `AIza*`, JWT `eyJ*`, bcrypt `$2*$`, `xag_*`, high-entropy secret assignments) found **zero real credentials**; every hit is a placeholder, documentation example, test dummy, or weak dev/test/CI default. Full inventory: `commercial_audit/security_decisions_closure_2026-07-19.md` §4.
- The legacy `cleanup_sensitive_info.py` (filter-repo helper written for the old repository) is now moot; disposal is suggested in the closure report (outside P0-08 scope).

Follow-ups (tracked in closure report §5):
1. **Key-rotation caveat — owner confirmation required**: scrubbing local history does not revoke copies. If the pre-rebuild repository was ever pushed to a remote or shared with third parties, all API keys in use at that time MUST still be rotated. If the old repo never left this machine, no rotation is needed.
2. **`.env.*` files are tracked in the NEW repository**: the `.gitignore:33` pattern `*.env` does not match `.env.<name>` file names, so `.env.development`, `.env.performance`, `.env.production`, `.env.test` are committed. Contents were verified placeholder/dev-only on 2026-07-19, but they must be untracked (`git rm --cached`) and the gitignore pattern fixed before any real secret is ever written into them.

**Note**: the original instruction "Do NOT modify these files without your explicit approval" was honored — no data files were modified; the scan was strictly read-only.

### D-4 `enable_high_risk_tools` production approval flow (LOW risk) — ✅ CLOSED, recommendation adopted

Original concern: turning on `enable_high_risk_tools` allows write_file / apply_text_patch / apply_batch_patch without human approval.

**Decision: recommendation adopted** — `false` stays the default everywhere; production deployments that need file mutation must opt in explicitly via env and should pair it with the approval store so each high-risk call is logged and gateable.

Evidence (verified 2026-07-19):
- `backend/app/settings.py:67` — `enable_high_risk_tools: bool = False` default
- `.env.production:70` — `XAGENT_ENABLE_HIGH_RISK_TOOLS=false`
- `DEPLOYMENT.md:57-61` — documents explicit env opt-in and warns "Do not leave `XAGENT_ENABLE_HIGH_RISK_TOOLS=true` as a broad production default"; `DEPLOYMENT.md:85` production checklist keeps it `false`
- Approval store available: `backend/app/settings.py:53` `approval_store_path` (default `data/approvals.json`); `.env.production:35` leaves the path empty so the default store is used

---

## Already implemented (re-verified 2026-07-19, no action)

- bcrypt (rounds=12) password hashing (`backend/app/core/admin.py:235`) — *corrected 2026-07-19: this document previously stated "PBKDF2HMAC password hashing"; the actual password hash is bcrypt. PBKDF2 is used only for data-encryption key derivation.*
- AST execution sandbox with restricted builtins (implemented in plugin_sandbox) — *caveat added 2026-07-19: the `core/execution/python_sandbox.py` AST blacklist is separately flagged as unsafe for untrusted code (audit item P0-18); only Docker isolation may be used for untrusted workloads.*
- Audit HMAC enforcement in production mode (validator in settings.py)
- Path traversal protection in all file tools (_resolve_tool_path)
- CSRF exemptions documented for Feishu/Bearer tokens
