# X-Agent Commercial Pilot Readiness

## Purpose

This document defines the post-RC commercial pilot path for X-Agent. It is
intended for a controlled pilot, not general availability and not a full Codex
parity claim.

> Boundary note (2026-06-14): The RC and pilot proof below is historical
> handoff evidence for the listed branch, tag, and commits. It must not be used
> as current `feat/commercial-delivery-v1` delivery-complete or release-ready
> proof without rerunning the current gates. The current closure snapshot is
> `.xagent_runtime/reports/commercial-delivery-closure-snapshot.json` and is
> owner-gated/blocked.

Current RC proof:

- Status: `commercial_rc_ready`.
- Tag: `x-agent-commercial-rc-20260608-6`.
- Commit: `592141f35520df62578a00cbb805eeaa7371a940`.
- Report: `.xagent_runtime/reports/rc-delivery-status.json`.

Current Feishu Pilot V1 handoff:

- Delivery pack: `docs/FEISHU_PILOT_V1_DELIVERY_PACK.md`.
- Status report: `.xagent_runtime/reports/commercial-pilot-handoff-status.json`.
- Status: `pilot_handoff_ready`.
- Pilot tag: `x-agent-commercial-pilot-feishu-20260608`.
- Pilot commit: `765d44b69da061caba6585a4cee0105bbf3310a7`.
- Full Codex parity claimed: `false`.

## Pilot Scope

Included:

- Backend API and Web Workbench pilot path.
- CLI operational path.
- MCP, tools, approvals, memory, workflow, audit, and sandbox evidence.
- One selected non-REST channel for end-to-end pilot use.
- Plugin/skill lifecycle in governed review mode.
- Commercial setup, smoke, rollback, and evidence collection.

Excluded:

- GA claims.
- Full Codex, Hermes, Claude Code, or OpenClaw parity.
- Production sandbox SLA claims without workload evidence.
- Broad channel count claims.
- Automatic high-risk skill promotion.
- Unreviewed third-party plugin execution.

## 30-Minute Setup Path

### 1. Checkout And Environment

```powershell
cd "D:\AI编程库\项目库\进行中的项目\X-Agent"
git status --short --branch
```

Expected:

- Branch is `codex/codex-hermes-gap-closure`.
- Existing unrelated untracked files are not staged automatically.

### 2. Confirm RC Handoff Proof

```powershell
python scripts\rc_delivery_status.py --expected-commit-sha 592141f35520df62578a00cbb805eeaa7371a940 --tag-name x-agent-commercial-rc-20260608-6 --github-actions-run-url https://github.com/xiongpinji/X-Agent/actions/runs/27112069486 --github-actions-head-sha 592141f35520df62578a00cbb805eeaa7371a940 --fetch-github
```

Expected:

```text
RC delivery status: commercial_rc_ready
```

### 3. Configure Pilot Runtime

Use environment variables or a deployment secret store. Do not write production
secrets into source files.

Required:

- `XAGENT_DATABASE_URL`
- `XAGENT_REDIS_URL`
- `XAGENT_LLM_BACKEND`
- Provider-specific API key or local model settings
- `XAGENT_CORS_ORIGINS`

Recommended defaults:

- `XAGENT_ENABLE_HIGH_RISK_TOOLS=false`
- explicit non-wildcard CORS origins
- owner-gated external smoke checks

### 4. Start Services

Use the deployment path selected by the pilot owner:

```powershell
docker compose up -d
```

or local development mode:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### 5. Smoke Core Entrypoints

```powershell
python -m pytest tests/test_first_release_entrypoints.py tests/test_security.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected tests pass.

### 6. Smoke Workbench And Thread Flow

Target behavior:

1. Open `/chat` or Web Workbench.
2. Start one agent run.
3. Observe run status.
4. Trigger one safe tool or workflow event.
5. Inspect trace/audit evidence.

Current backing endpoints:

- `/chat`
- `/api/v1/workbench`
- `/api/v1/agent/run`
- `/api/v1/runs`
- `/api/v1/traces`
- `/api/v1/audit`

### 7. Smoke One Pilot Channel

Use Feishu as the first commercial pilot channel for the domestic China launch.
Telegram is not required for the first domestic pilot and remains a later
preview channel.

Feishu test command group:

```powershell
python -m pytest tests/test_feishu_channel_api.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: signed Feishu/Lark events are accepted, missing signatures are
rejected, and invalid signatures are rejected. Live Feishu app credentials and
network callback delivery remain owner-gated evidence.

Owner live Feishu verification:

```powershell
$env:XAGENT_FEISHU_APP_ID="<your-feishu-app-id>"
$env:XAGENT_FEISHU_APP_SECRET="<your-feishu-app-secret>"
$env:XAGENT_FEISHU_ENCRYPT_KEY="<your-feishu-event-encrypt-key>"
$env:XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_EVIDENCE="1"
python scripts\rc_external_smoke.py --check feishu_webhook_contract --require-configured
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Expose the local service through an HTTPS tunnel and configure the Feishu event
subscription request URL to:

```text
https://<your-public-https-host>/api/v1/integrations/feishu/events
```

In Feishu Open Platform, set the same Encrypt Key as
`XAGENT_FEISHU_ENCRYPT_KEY`, enable `im.message.receive_v1`, save the request
URL, then send one real message to the app. A successful inbound event writes:

```text
.xagent_runtime/reports/commercial-pilot-feishu-live.json
```

Then refresh pilot evidence:

```powershell
python scripts\commercial_pilot_channel_readiness.py
python scripts\commercial_pilot_refresh_chain.py
```

### 8. Smoke Plugin/Skill Governance

```powershell
python -m pytest tests/test_skill_curator_models.py tests/test_skill_curator_scoring.py tests/test_skill_curator_api.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected:

- Skill Curator can analyze evidence.
- Drafts remain staged only.
- No generated skill is auto-promoted without review.

## Pilot Evidence Template

Create a pilot evidence report separate from RC evidence:

```json
{
  "status": "pilot_ready",
  "generated_at": "2026-06-08T00:00:00Z",
  "rc_tag": "x-agent-commercial-rc-20260608-6",
  "rc_commit": "592141f35520df62578a00cbb805eeaa7371a940",
  "pilot_channel": "feishu",
  "checks": [
    {"name": "rc_delivery_status", "status": "passed"},
    {"name": "core_entrypoints", "status": "passed"},
    {"name": "workbench_thread_loop", "status": "passed"},
    {"name": "pilot_channel_loop", "status": "passed"},
    {"name": "skill_governance", "status": "passed"},
    {"name": "approval_audit", "status": "passed"}
  ],
  "full_codex_parity_claimed": false,
  "known_limits": []
}
```

Recommended future path:

- `.xagent_runtime/reports/commercial-pilot-readiness.json`
- `.xagent_runtime/reports/commercial-pilot-refresh-chain.json`
- `.xagent_runtime/reports/commercial-pilot-channel-readiness.json`
- `scripts/commercial_pilot_readiness.py`
- `scripts/commercial_pilot_refresh_chain.py`
- `scripts/commercial_pilot_channel_readiness.py`

## Rollback

### Config Rollback

1. Revert environment variables to the previous deployment snapshot.
2. Restart API, worker, and scheduler services.
3. Re-run `/health` and `/ready`.

### Deployment Rollback

1. Deploy the previous image or source artifact.
2. Keep database migrations forward-only unless a tested rollback exists.
3. Disable the pilot channel webhook before rolling back if duplicate replies
   are possible.

### Provider Rollback

1. Switch `XAGENT_LLM_BACKEND` to the previous provider.
2. Clear only runtime caches that are safe to clear.
3. Re-run provider smoke.

### Channel Rollback

1. Disable webhook or rotate webhook secret.
2. Stop channel worker/handler.
3. Verify no queued messages remain.
4. Record the rollback in audit evidence.

## Known Limits

- The RC is commercial-ready as a release candidate, not GA.
- Full Codex parity is not claimed.
- Channel maturity is pilot-level unless owner live checks pass.
- Sandbox SLA is not claimed until real workload evidence exists.
- Skill Curator is review-gated; it does not safely auto-promote skills yet.
- Some full-suite tests are environment-dependent and may require owner machine
  validation.

## Customer Success Checklist

- [ ] Confirm deployment owner and pilot owner.
- [ ] Confirm selected pilot channel.
- [ ] Confirm data boundary and retention requirements.
- [ ] Confirm allowed model provider.
- [ ] Confirm high-risk tools are disabled by default.
- [ ] Confirm approval owner for guarded actions.
- [ ] Confirm evidence report path.
- [ ] Confirm rollback contact and rollback window.

## Next Engineering Tasks

1. Run `python scripts\commercial_pilot_refresh_chain.py`.
2. Confirm `.xagent_runtime/reports/commercial-pilot-refresh-chain.json`
   reports `pilot_ready`.
3. Confirm `.xagent_runtime/reports/commercial-pilot-readiness.json`
   reports `pilot_ready`.
4. Confirm `.xagent_runtime/reports/commercial-pilot-channel-readiness.json`
   reports `ready_with_owner_gates`.
5. Add control-plane compatibility adapter.
