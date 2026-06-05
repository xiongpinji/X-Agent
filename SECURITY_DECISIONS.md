# X-Agent Production Security Decision List

Date: 2026-06-05  
Status: Pending owner approval on HIGH-RISK items

---

## Already hardened (no decision needed)

The following security controls are already enforced in production by `backend/app/settings.py` validators:

- `XAGENT_AUDIT_HMAC_SECRET` — required in production (validator raises on empty)
- `XAGENT_JWT_SECRET` — must be ≥32 chars with uppercase + digits; default rejected in production
- `XAGENT_ENCRYPTION_KEY` — same enforcement as JWT_SECRET
- `XAGENT_CORS_ORIGINS` — wildcard rejected in production mode
- `XAGENT_ENABLE_HIGH_RISK_TOOLS` — defaults to `false`; write/patch tools require explicit opt-in

---

## Decisions required before GA

### D-1 API key enforcement in production (MEDIUM risk)

Current: `XAGENT_REQUIRE_API_KEY=false` in both dev and the docker-compose default.  
Risk: If deployed without a reverse proxy or token gateway, the API is open.  
Options:
- **A (recommended)**: Set `XAGENT_REQUIRE_API_KEY=true` in `docker-compose.yml` production service default and document this in DEPLOYMENT.md.
- **B**: Leave off by default but add a startup WARNING log when `APP_MODE=production` and `REQUIRE_API_KEY=false`.

Owner decision: ______

### D-2 HMAC-signed GitHub webhook secret (LOW risk in current state)

Current: `XAGENT_AUDIT_HMAC_SECRET` guards audit logs. GitHub webhook signature validation (`X-Hub-Signature-256`) in `backend/app/core/sandbox/github_webhook.py` already uses HMAC-SHA256 with constant-time comparison.  
Risk: If `XAGENT_GITHUB_WEBHOOK_SECRET` is empty in production, webhooks are unauthenticated.  
Options:
- **A (recommended)**: Add `XAGENT_GITHUB_WEBHOOK_SECRET` to `.env.production` with a `REPLACE_WITH_GENERATED` placeholder and document it in DEPLOYMENT.md.
- **B**: Add a validator in settings.py that raises in production if webhook secret is empty.

Owner decision: ______

### D-3 Secret files still tracked in git (HIGH risk)

Current: `data/api_keys.json` (and potentially other files in `data/`) were tracked in a previous commit. These files may contain real API key hashes.  
Risk: Any clone of the repo can read historical file contents.  
Options:
- **A**: Run `git filter-repo` (or `git-bfg`) to scrub `data/api_keys.json` from git history and rotate any exposed keys. Requires all collaborators to re-clone.
- **B (if no real keys were committed)**: Verify contents are dummy/test-only, then `git rm --cached data/api_keys.json`, update `.gitignore`, commit and document.
- **C**: If A/B are too disruptive now, document as a known risk and schedule for GA.

Owner decision: ______  
**Note**: Do NOT modify these files without your explicit approval.

### D-4 `enable_high_risk_tools` production approval flow (LOW risk)

Current: Setting defaults to `false`. Turning it on allows write_file, apply_text_patch, apply_batch_patch without human approval.  
Recommendation: Keep `false` as the default. For production AgentFixRunner/IssueToPR deployments that need file mutation, set it explicitly via env and consider enabling the `XAGENT_APPROVAL_STORE` approval flow so each high-risk tool call gets logged and can be gated.

Owner decision: ______

---

## Already implemented (no action)

- PBKDF2HMAC password hashing (implemented in auth module)
- AST execution sandbox with restricted builtins (implemented in plugin_sandbox)
- Audit HMAC enforcement in production mode (validator in settings.py)
- Path traversal protection in all file tools (_resolve_tool_path)
- CSRF exemptions documented for Feishu/Bearer tokens
