# X-Agent Feishu Pilot V1 Delivery Pack

Last updated: 2026-06-08

This delivery pack is the customer-facing handoff for the first domestic
commercial pilot channel. It is scoped to Feishu inbound live validation,
pilot-readiness evidence, and a repeatable owner-gated verification path. It is
not a GA release note and it is not a full Codex parity claim.

## 1. Delivery Status

Current machine-readable handoff:

- Status: `pilot_handoff_ready`
- Pilot channel: `feishu`
- Pilot tag: `x-agent-commercial-pilot-feishu-20260608`
- Pilot commit: `765d44b69da061caba6585a4cee0105bbf3310a7`
- RC baseline tag: `x-agent-commercial-rc-20260608-6`
- RC baseline commit: `592141f35520df62578a00cbb805eeaa7371a940`
- Hosted CI run: `https://github.com/xiongpinji/X-Agent/actions/runs/27119766813`
- Operator status report: `.xagent_runtime/reports/commercial-pilot-ops-status.json`
- Handoff report: `.xagent_runtime/reports/commercial-pilot-handoff-status.json`

Confirmed evidence:

- Feishu live inbound callback accepted from the real Feishu network.
- Callback signature mode: `lark_sha256`.
- Encrypted callback: `true`.
- Event type: `im.message.receive_v1`.
- No outbound mutation was performed during live evidence capture.
- `full_codex_parity_claimed=false`.

Known boundary:

- This pack proves Feishu inbound pilot readiness only.
- Outbound Feishu message send remains a separate owner-gated verification.
- Telegram is not required for the first domestic pilot.
- DingTalk and WeChat Work are not release blockers for Pilot V1.

## 2. Artifact Map

Use these files as the canonical source of truth for this pilot:

| Artifact | Purpose |
| --- | --- |
| `.xagent_runtime/reports/commercial-pilot-ops-status.json` | Single operator and UI status rollup for Feishu Pilot V1. |
| `.xagent_runtime/reports/commercial-pilot-handoff-status.json` | Final aggregate Feishu pilot handoff status. |
| `.xagent_runtime/reports/commercial-pilot-feishu-live.json` | Real inbound Feishu event evidence. |
| `.xagent_runtime/reports/commercial-pilot-readiness.json` | Aggregate pilot readiness evidence. |
| `.xagent_runtime/reports/commercial-pilot-refresh-chain.json` | Rebuilt pilot evidence chain. |
| `.xagent_runtime/reports/commercial-pilot-channel-readiness.json` | Channel matrix showing Feishu ready and other channels preview. |
| `.xagent_runtime/reports/commercial-pilot-feishu-outbound-live.json` | Optional owner-approved outbound send evidence. |
| `.xagent_runtime/reports/rc-delivery-status.json` | Frozen commercial RC baseline proof. |
| `scripts/commercial_pilot_ops_status.py` | Read-only operations status rollup. |
| `scripts/commercial_pilot_handoff_status.py` | Read-only handoff gate. |
| `scripts/commercial_pilot_refresh_chain.py` | Readiness evidence refresh chain. |
| `scripts/commercial_pilot_feishu_outbound_smoke.py` | Owner-gated outbound smoke; dry-run by default. |
| `tests/test_feishu_channel_api.py` | Feishu callback contract and live-evidence tests. |

Generated reports under `.xagent_runtime/` are runtime evidence and are not
staged by default.

## 3. Roles And Ownership

X-Agent owner:

- Provides source branch, release tags, runbooks, and verification scripts.
- Keeps RC evidence and pilot evidence separate.
- Confirms no full competitor parity claim is made from this pilot.

Customer or pilot operator:

- Owns real Feishu app credentials.
- Owns public HTTPS callback exposure.
- Triggers Feishu subscription verification and live message delivery.
- Decides whether to run the separate outbound send gate.

Frontend/UI implementer:

- May build a status dashboard from the report fields listed in section 9.
- Should not rewrite or infer readiness status outside the machine reports.
- Should display inbound readiness and outbound owner gate as separate states.

## 4. Required Environment

Do not write real secret values into source files or committed docs.

Required for Feishu inbound owner verification:

```powershell
$env:XAGENT_FEISHU_APP_ID="<feishu-app-id>"
$env:XAGENT_FEISHU_APP_SECRET="<feishu-app-secret>"
$env:XAGENT_FEISHU_ENCRYPT_KEY="<feishu-event-encrypt-key>"
$env:XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_EVIDENCE="1"
```

Optional:

```powershell
$env:XAGENT_FEISHU_BASE_URL="https://open.feishu.cn"
$env:XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_REPORT_PATH=".xagent_runtime/reports/commercial-pilot-feishu-live.json"
```

Recommended deployment safety defaults:

```powershell
$env:XAGENT_ENABLE_HIGH_RISK_TOOLS="false"
$env:XAGENT_REQUIRE_API_KEY="true"
$env:XAGENT_PLAYWRIGHT_HEADLESS="true"
```

## 5. Start Service

From repository root:

```powershell
cd "<repo-root>"
git status --short --branch
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Expected startup:

- FastAPI starts on `http://0.0.0.0:8000`.
- MCP may be skipped if no MCP config is present; that is not a Feishu pilot
  blocker.
- Feishu callback route is available at:

```text
/api/v1/integrations/feishu/events
```

Public callback URL format:

```text
https://<public-https-host>/api/v1/integrations/feishu/events
```

## 6. Feishu App Configuration

Configure the Feishu app with:

- App ID: same value as `XAGENT_FEISHU_APP_ID`.
- App Secret: same value as `XAGENT_FEISHU_APP_SECRET`.
- Event Encrypt Key: same value as `XAGENT_FEISHU_ENCRYPT_KEY`.
- Event callback request URL:

```text
https://<public-https-host>/api/v1/integrations/feishu/events
```

Enable the event:

```text
im.message.receive_v1
```

The callback handler supports:

- Plain URL verification challenge.
- Encrypted URL verification challenge.
- Encrypted Feishu/Lark callbacks.
- Official `X-Lark-*` callback signature headers.
- Legacy `x-feishu-*` HMAC headers for compatibility.

The inbound live evidence path intentionally performs no outbound send.

## 7. Verification Commands

Run the local Feishu callback contract tests:

```powershell
python -m pytest tests/test_feishu_channel_api.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Refresh channel readiness:

```powershell
python scripts\commercial_pilot_channel_readiness.py
```

Refresh operator status rollup:

```powershell
python scripts\commercial_pilot_ops_status.py
```

Refresh full pilot evidence:

```powershell
python scripts\commercial_pilot_refresh_chain.py
```

Verify final pilot handoff:

```powershell
python scripts\commercial_pilot_handoff_status.py `
  --expected-pilot-commit-sha 765d44b69da061caba6585a4cee0105bbf3310a7 `
  --pilot-tag-name x-agent-commercial-pilot-feishu-20260608 `
  --expected-rc-commit-sha 592141f35520df62578a00cbb805eeaa7371a940 `
  --rc-tag-name x-agent-commercial-rc-20260608-6 `
  --github-actions-run-url https://github.com/xiongpinji/X-Agent/actions/runs/27119766813 `
  --github-actions-head-sha 765d44b69da061caba6585a4cee0105bbf3310a7 `
  --fetch-github
```

Expected final output:

```text
Commercial pilot handoff status: pilot_handoff_ready
- pilot_commit: passed
- remote_branch: passed
- hosted_ci: passed
- rc_baseline: passed
- feishu_live_evidence: passed
- pilot_readiness: passed
- refresh_chain: passed
- pilot_tag_consistency: passed
```

## 8. Evidence Acceptance Criteria

The live Feishu evidence report must contain:

```json
{
  "status": "passed",
  "channel": "feishu",
  "evidence_type": "commercial_pilot_feishu_live",
  "event_type": "im.message.receive_v1",
  "signature_mode": "lark_sha256",
  "encrypted_callback": true,
  "mutation_performed": false,
  "outbound_message_sent": false
}
```

The handoff report must contain:

```json
{
  "status": "pilot_handoff_ready",
  "pilot_tag_name": "x-agent-commercial-pilot-feishu-20260608",
  "rc_tag_name": "x-agent-commercial-rc-20260608-6",
  "full_codex_parity_claimed": false
}
```

The operator status report must contain:

```json
{
  "status": "pilot_ops_ready",
  "pilot_channel": "feishu",
  "outbound_owner_gate_status": "preview",
  "full_codex_parity_claimed": false
}
```

Do not accept the pilot as ready if:

- `full_codex_parity_claimed` is `true`.
- `outbound_message_sent` is `true` in the inbound evidence report.
- `commercial-pilot-ops-status.json` is not `pilot_ops_ready`.
- The pilot tag points at a different commit.
- The RC baseline report is not `commercial_rc_ready`.
- Hosted CI head SHA does not match the pilot commit.

## 9. UI Status Contract

The frontend session can read or display these report fields without changing
the backend contract:

From `.xagent_runtime/reports/commercial-pilot-ops-status.json`:

- `status`
- `generated_at`
- `pilot_channel`
- `pilot_tag_name`
- `pilot_commit_sha`
- `rc_tag_name`
- `rc_commit_sha`
- `handoff_status`
- `channel_readiness_status`
- `inbound_live_status`
- `outbound_owner_gate_status`
- `full_codex_parity_claimed`
- `checks[].name`
- `checks[].status`
- `checks[].details`
- `checks[].error`
- `reports`
- `known_limits[]`

From `.xagent_runtime/reports/commercial-pilot-handoff-status.json`:

- `status`
- `generated_at`
- `pilot_tag_name`
- `expected_pilot_commit_sha`
- `rc_tag_name`
- `expected_rc_commit_sha`
- `github_actions_run_url`
- `github_actions_head_sha`
- `full_codex_parity_claimed`
- `checks[].name`
- `checks[].status`
- `checks[].error`
- `known_limits[]`

From `.xagent_runtime/reports/commercial-pilot-channel-readiness.json`:

- `channels[].channel`
- `channels[].status`
- `channels[].capabilities[].name`
- `channels[].capabilities[].status`
- `channels[].capabilities[].details.optional`
- `channels[].capabilities[].details.source_status`
- `channels[].capabilities[].details.mutation_performed`
- `channels[].capabilities[].details.outbound_message_sent`
- `channels[].capabilities[].error`

For Feishu, `outbound_owner_gate` is optional in Pilot V1:

- `preview`: outbound send is not yet owner-approved or is only dry-run ready.
- `passed`: one owner-approved outbound test send has completed.
- It must not change inbound pilot readiness by itself.

Suggested UI status mapping:

| Report status | UI label | Meaning |
| --- | --- | --- |
| `pilot_ops_ready` | Ready | Feishu Pilot V1 operations evidence is complete. |
| `pilot_ops_action_required` | Action required | A required evidence source is missing or not ready. |
| `pilot_ops_blocked` | Blocked | A hard mismatch or unsafe claim exists in the evidence chain. |
| `pilot_handoff_ready` | Ready | Feishu Pilot V1 evidence is complete. |
| `pilot_tag_action_required` | Tag required | Evidence is ready, but pilot tag is missing or stale. |
| `ci_evidence_pending` | CI pending | Hosted CI URL or head SHA evidence is missing. |
| `action_required` | Action required | At least one owner or evidence step is pending. |
| `failed` | Blocked | A hard mismatch or failed gate exists. |

Display inbound and outbound separately:

- Inbound Feishu live evidence: ready when `feishu_live_evidence` is `passed`.
- Outbound Feishu message send: owner-gated until a separate outbound report is
  added and passed.

## 10. Outbound Owner-Gated Follow-Up

Pilot V1 currently does not require outbound send. A separate outbound smoke is
available, but it is dry-run by default and must not be treated as part of the
inbound handoff unless the owner explicitly approves a real send.

Default non-mutating check:

```powershell
python scripts\commercial_pilot_feishu_outbound_smoke.py
```

Expected without owner configuration:

```text
Commercial pilot Feishu outbound smoke status: owner_action_required
Mutation performed: False
Outbound message sent: False
```

Configured dry-run before real send:

```powershell
python scripts\commercial_pilot_feishu_outbound_smoke.py `
  --receive-id <disposable-feishu-chat-id>
```

Expected:

```text
Commercial pilot Feishu outbound smoke status: ready_to_execute
Mutation performed: False
Outbound message sent: False
```

Owner-approved real send:

```powershell
python scripts\commercial_pilot_feishu_outbound_smoke.py `
  --receive-id <disposable-feishu-chat-id> `
  --receive-id-type chat_id `
  --text "X-Agent Feishu outbound owner-gated smoke" `
  --execute `
  --owner-approved
```

The real-send path:

1. Requires explicit owner env vars and a disposable Feishu chat.
2. Requires both `--execute` and `--owner-approved`.
3. Records `outbound_message_sent=true` in a separate outbound evidence file.
4. Never overwrites `commercial-pilot-feishu-live.json`.
5. Adds a new handoff check only after the owner approves outbound mutation.

Suggested future report:

```text
.xagent_runtime/reports/commercial-pilot-feishu-outbound-live.json
```

## 11. Rollback

If inbound callback delivery fails:

1. Disable the Feishu event subscription request URL.
2. Stop the exposed API service or HTTPS tunnel.
3. Rotate the Feishu Encrypt Key if the callback URL or tunnel was exposed to
   the wrong environment.
4. Restart the API with corrected env vars.
5. Rerun `tests/test_feishu_channel_api.py`.
6. Trigger one new real Feishu event and regenerate live evidence.
7. Rerun `scripts\commercial_pilot_handoff_status.py`.

If pilot deployment needs rollback:

1. Keep the RC tag unchanged.
2. Deploy the previous known-good source or container image.
3. Disable outbound Feishu send if it was enabled separately.
4. Preserve the old evidence reports for audit.
5. Create a new evidence report for the rollback state instead of editing the
   historical handoff report.

## 12. Troubleshooting

Missing signature headers:

- Confirm Feishu is sending signed event callbacks.
- Confirm the public callback URL points to `/api/v1/integrations/feishu/events`.
- Confirm the request is not being rewritten by the HTTPS tunnel.

Invalid signature:

- Confirm `XAGENT_FEISHU_ENCRYPT_KEY` matches the Feishu app event Encrypt Key.
- Confirm the signature is calculated over the original request body.
- For encrypted callbacks, verify the encrypted wrapper body is what reaches
  the API.

No live evidence file:

- Confirm `XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_EVIDENCE=1`.
- Confirm the inbound event was accepted and was not a duplicate event ID.
- Confirm the process can write to `.xagent_runtime/reports/`.

Handoff status not ready:

- Inspect `.xagent_runtime/reports/commercial-pilot-ops-status.json`.
- Inspect `.xagent_runtime/reports/commercial-pilot-handoff-status.json`.
- Fix the first non-passing check.
- Rerun the handoff status command with `--fetch-github`.
- Rerun `scripts\commercial_pilot_ops_status.py`.

## 13. Sign-Off Checklist

- [ ] RC baseline remains `commercial_rc_ready`.
- [ ] Pilot tag points at `765d44b69da061caba6585a4cee0105bbf3310a7`.
- [ ] Hosted CI run is completed successfully for the pilot commit.
- [ ] Feishu inbound live evidence is present and passed.
- [ ] Operator status report is `pilot_ops_ready`.
- [ ] `mutation_performed=false`.
- [ ] `outbound_message_sent=false` for inbound evidence.
- [ ] `full_codex_parity_claimed=false`.
- [ ] Customer has reviewed known limits.
- [ ] Rollback owner and communication channel are confirmed.
- [ ] Frontend/UI status, if present, reads from machine reports rather than
  duplicating readiness logic.
