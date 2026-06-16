# X-Agent Codex-Aligned Commercial Delivery Plan

> For agentic workers: use this plan as the execution board after the
> `x-agent-commercial-rc-20260608-6` RC. Keep RC readiness separate from
> product maturity. Do not claim full Codex parity until the acceptance evidence
> below is produced.

## Goal

Turn X-Agent from a commercial RC candidate into a Codex-aligned commercial
pilot platform while preserving X-Agent's core positioning: an enterprise
autonomous-agent framework, not a personal IDE-only assistant.

The plan aligns X-Agent with the current Codex platform direction observed in
the local Codex install and public OpenAI materials:

- App Server style protocol and multi-client control plane.
- Threads, goals, memory, fork/resume/search, and audit history as first-class
  product objects.
- Plugins, skills, apps/connectors, and MCP as a governed ecosystem.
- Browser/computer/channel entrypoints, not only REST APIs.
- Fine-grained permissions, sandbox readiness, approval routing, and commercial
  handoff gates.

## Current Baseline

- Branch: `codex/codex-hermes-gap-closure`.
- Commercial RC tag: `x-agent-commercial-rc-20260608-6`.
- Release commit: `592141f35520df62578a00cbb805eeaa7371a940`.
- Delivery report: `.xagent_runtime/reports/rc-delivery-status.json`.
- Current delivery status: `commercial_rc_ready`.
- Passed gates: expected commit, remote branch, hosted CI,
  owner-verified finalize, and tag consistency.
- Non-claim: this is not GA and not full Codex/Hermes parity.

## Commercial Product Thesis

X-Agent should not chase Codex by becoming a clone of Codex Desktop or an IDE
agent. The commercial wedge is:

1. Enterprise-owned deployment and data boundary.
2. Workflow orchestration with approvals, audit, and multi-agent execution.
3. Channel and API-first agent operations for enterprise teams.
4. Governed skill/plugin lifecycle.
5. Evidence-driven commercial handoff.

Codex is the benchmark for platform ergonomics. X-Agent should copy the product
primitives that make Codex usable: unified protocol, durable thread state,
plugin/skill surfaces, approval UX, and fast setup loops.

## Definition Of Done

The next commercial milestone is complete when all items below have evidence:

- A typed X-Agent control-plane contract exists for threads, turns, tools,
  approvals, plugins, skills, channels, and runtime evidence.
- Web Workbench can start, resume, inspect, and hand off agent runs without
  relying on internal-only API knowledge.
- At least one non-REST user channel is production-pilot ready end to end.
- Plugin/Skill lifecycle supports list, inspect, draft, validate, approve, and
  promote with audit records.
- Approval and sandbox decisions are normalized across CLI, API, channels,
  browser automation, MCP, and issue-to-PR flows.
- Commercial pilot packaging has setup, smoke, rollback, and known-limits docs.
- A generated report records the Codex-alignment score without claiming full
  parity.

## Workstreams

### WS0: Preserve RC Integrity

Purpose: keep the current commercial RC usable while new Codex-alignment work
continues.

Scope:

- Do not weaken `scripts/rc_delivery_status.py`.
- Do not remove owner-gate checks.
- Do not stage runtime evidence by default.
- Keep `.xagent_runtime/reports/rc-delivery-status.json` as the current handoff
  proof.

Tasks:

- [ ] Add a short post-RC policy note to release docs: RC evidence is frozen
      unless explicitly refreshed.
- [ ] Add a post-RC smoke command group for commercial-pilot work.
- [ ] Keep `full_parity_claimed=false` in any generated Codex-alignment report.

Acceptance:

```powershell
python scripts\rc_delivery_status.py --expected-commit-sha 592141f35520df62578a00cbb805eeaa7371a940 --tag-name x-agent-commercial-rc-20260608-6 --github-actions-run-url https://github.com/xiongpinji/X-Agent/actions/runs/27112069486 --github-actions-head-sha 592141f35520df62578a00cbb805eeaa7371a940 --fetch-github
```

Expected status: `commercial_rc_ready`.

### WS1: X-Agent Control Plane Protocol

Purpose: give X-Agent an App Server style contract so UI, CLI, channels, and
future desktop clients do not bind directly to scattered REST endpoints.

Target contract groups:

- `thread/start`, `thread/resume`, `thread/read`, `thread/search`,
  `thread/fork`, `thread/rollback`, `thread/compact`.
- `turn/start`, `turn/steer`, `turn/interrupt`.
- `tool/list`, `tool/call`, `tool/progress`.
- `approval/list`, `approval/decide`, `approval/execute`.
- `plugin/list`, `plugin/read`, `plugin/install`, `plugin/share`.
- `skill/list`, `skill/analyze`, `skill/draft`, `skill/promote`.
- `mcp/status`, `mcp/resource/read`, `mcp/tool/call`.
- `channel/status`, `channel/send`, `channel/webhook/ingest`.
- `runtime/evidence/read`, `runtime/smoke/run`.

Tasks:

- [ ] Create `docs/specs/xagent-control-plane-protocol.md`.
- [ ] Add JSON schema examples for each request/response group.
- [ ] Map every request group to existing REST endpoints or mark as missing.
- [ ] Add a compatibility table against Codex app-server primitives.
- [ ] Add a no-secret logging rule for all control-plane events.

Acceptance:

- Protocol doc includes at least 10 request groups.
- Every request group has owner, implementation status, and acceptance test.
- No request group requires raw production credentials in request payloads.

### WS2: Thread Workbench And Durable Run State

Purpose: make X-Agent usable as a product surface, not only as backend APIs.

Tasks:

- [ ] Define thread/run data model for product use: thread, turn, item,
      tool-call, approval, artifact, channel event, evidence link.
- [ ] Add Workbench requirements for list/search/read/resume/fork/rollback.
- [ ] Make run status, approvals, tool progress, and channel handoff visible in
      Web Workbench.
- [ ] Add a targeted smoke test for a complete first-run loop:
      start -> tool event -> approval -> result -> audit.
- [ ] Add known-limits text for rollback: history rollback does not revert file
      changes unless a separate patch/file revert exists.

Acceptance:

```powershell
python -m pytest tests/test_first_release_entrypoints.py tests/test_workbench*.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected tests pass or missing test files are replaced with the new
targeted Workbench smoke.

### WS3: Plugin And Skill Commercial Lifecycle

Purpose: move from "plugins exist" to a governed commercial ecosystem.

Tasks:

- [ ] Define plugin metadata required for commercial listing: name, version,
      owner, permissions, tools, MCP dependencies, data access, test command,
      rollback notes.
- [ ] Extend Skill Curator MVP roadmap from draft-only to:
      validate -> review -> approve -> promote -> rollback.
- [ ] Add a plugin/skill risk model: safe, guarded, high-risk, prohibited.
- [ ] Add signing/review placeholders without enforcing production signing yet.
- [ ] Add CLI commands or docs for list/read/validate/promote.

Acceptance:

```powershell
python -m pytest tests/test_skill_curator_models.py tests/test_skill_curator_scoring.py tests/test_skill_curator_api.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: current curator tests pass, plus new lifecycle tests when implemented.

### WS4: Approval, Guardian, And Sandbox Governance

Purpose: align X-Agent's enterprise governance with Codex-style fine-grained
permission flows.

Tasks:

- [ ] Normalize approval subjects: command, file change, network request, MCP
      elicitation, browser action, channel send, issue-to-PR execute.
- [ ] Add approval decision types: approve once, approve for run, approve for
      session, deny, abort.
- [ ] Add risk explanation fields suitable for UI and audit export.
- [ ] Ensure CLI and API expose the same approval model.
- [ ] Add sandbox readiness checks for Docker, subprocess fallback, and high-risk
      tool disablement.

Acceptance:

```powershell
python -m pytest tests/test_approvals*.py tests/test_security.py tests/test_sandbox*.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected approval/security/sandbox tests pass.

### WS5: Channels And Browser Entry Points

Purpose: close the largest productization gap: users need practical entrypoints.

Priority order:

1. Web Workbench and `/chat` as commercial pilot default.
2. Feishu as the domestic China enterprise pilot loop.
3. Telegram as an optional later preview channel.
4. Browser automation as a visible work surface.
5. Chrome extension as optional companion, not the main commercial claim.

Tasks:

- [ ] Choose one pilot channel and mark the others as preview.
- [ ] Add a channel readiness matrix with webhook, signature, dispatch, reply,
      retry, audit, and disable controls.
- [ ] Add a browser automation smoke that captures page state, performs one safe
      action, and records evidence.
- [ ] Add channel-to-thread mapping in docs and tests.
- [ ] Add customer setup instructions for the chosen pilot channel.

Acceptance:

```powershell
python -m pytest tests/test_feishu_channel_api.py tests/test_browser*.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected channel and browser tests pass, with live external checks
kept behind owner-controlled gates.

### WS6: Commercial Pilot Package

Purpose: make the release deployable and explainable for a paying pilot.

Tasks:

- [ ] Create `docs/COMMERCIAL_PILOT_READINESS.md`.
- [ ] Add a 30-minute setup path: env, docker compose, first login, first agent
      run, first channel event, first approval.
- [ ] Add known limits: not GA, no full Codex parity, channel count preview,
      sandbox SLA not yet proven, external provider coverage owner-gated.
- [ ] Add rollback procedure for config, deployment, and model provider.
- [ ] Add customer success checklist and evidence collection template.

Acceptance:

- Pilot doc includes setup, smoke, rollback, known limits, and evidence template.
- Pilot doc links to RC delivery status and this plan.

## First 72 Hours Execution Order

1. WS1: write the control-plane protocol spec and endpoint mapping.
2. WS6: write commercial pilot readiness doc.
3. WS5: select Feishu as the first domestic pilot channel and add readiness
   matrix; keep Telegram as preview.
4. WS2: add Workbench/thread product requirements and smoke target.
5. WS4: draft unified approval model.
6. WS3: extend Skill Curator lifecycle plan.

Do not start broad refactors until WS1 mapping is complete. The current repo has
many overlapping APIs; the protocol map is the control point that prevents more
surface-area drift.

## 30-Day Milestones

### Week 1: Protocol And Pilot Docs

- Control-plane protocol spec.
- Commercial pilot readiness doc.
- Channel readiness matrix.
- Unified approval model draft.
- Workbench smoke definition.

Exit criteria: product and engineering teams can point to one plan and one
protocol for all commercial-pilot work.

### Week 2: First Pilot Loop

- Web Workbench first-run loop.
- One channel end-to-end pilot.
- Approval decision path visible from CLI/API.
- Runtime smoke report updated for pilot loop.

Exit criteria: a pilot user can trigger an agent, inspect it, approve a guarded
action, and receive a result through one non-REST entrypoint.

### Week 3: Ecosystem Governance

- Skill lifecycle validate/review/promote/rollback design.
- Plugin metadata and risk model.
- MCP resource/tool-call status surfaced in control-plane spec.

Exit criteria: third-party extension work has a governed path and audit model.

### Week 4: Commercial Pilot Freeze

- Targeted pilot test group passes.
- Docs and known-limits reviewed.
- Owner-gated external checks refreshed.
- A new pilot evidence report is generated.

Exit criteria: X-Agent can be offered as a commercial pilot without overstating
GA or full Codex parity.

## Metrics

- First-run setup time: target <= 30 minutes.
- First agent run from UI/channel: target <= 5 minutes after setup.
- Approval audit coverage: 100% for guarded actions.
- Pilot channel reliability: 95% successful dispatch in test window.
- Targeted pilot tests: 100% pass.
- Full parity claim: must remain false until separately proven.

## Risks And Controls

- Risk: copying Codex's IDE/product shape dilutes X-Agent positioning.
  Control: keep enterprise workflow orchestration as the core claim.
- Risk: RC evidence gets overwritten by experimental pilot work.
  Control: freeze RC proof and generate separate pilot evidence.
- Risk: channel and plugin work expands without governance.
  Control: require readiness matrix and risk model before adding more channels.
- Risk: approval semantics diverge across CLI/API/UI/channel.
  Control: WS4 must define one decision model before implementation expands.
- Risk: full parity claims appear in docs.
  Control: every report must include non-claim language until broader evidence
  exists.

## Source Calibration

- Local evidence: Codex CLI 0.135.0 on this machine exposes app-server,
  plugins, MCP, cloud, remote-control, features, browser/computer-use, goals,
  memories, multi-agent, and workspace dependency features.
- Public source: OpenAI's Codex materials emphasize the harness, CLI/IDE/cloud
  workflows, plugins, skills, and app-connected capabilities.
- Current latest visible release line: Codex CLI 0.137.0 is available upstream,
  so local 0.135.0 findings should be treated as slightly behind current Codex.
