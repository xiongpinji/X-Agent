# Latest Codex Alignment Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align X-Agent's post-Feishu-Pilot roadmap with the current Codex platform surface while preserving the no-full-parity boundary.

**Architecture:** Treat Codex as the product-ergonomics benchmark, not as a clone target. X-Agent remains an enterprise autonomous-agent framework; the next increments add Codex-style control-plane, thread, cloud-task, GitHub, Skills/MCP, approval, sandbox, SDK, and app/IDE surfaces behind evidence gates.

**Tech Stack:** Python 3.11+, FastAPI, Typer, pytest, existing X-Agent commercial-pilot reports, control-plane protocol docs, CI workflows, MCP/hooks/skills/approval/sandbox modules.

---

## Current State

- Feishu Pilot V1 customer acceptance status: `customer_acceptance_pack_ready`.
- Current commercial pilot channel: `feishu`.
- Current delivery boundary: first domestic commercial pilot is deliverable; full Codex parity is not claimed.
- Current generated alignment report: `.xagent_runtime/reports/latest-codex-alignment.json`.
- Current stable source of Codex capability truth: official OpenAI Codex manual and OpenAI Codex GA materials.

## Latest Codex Capability Surface

The current Codex platform surface to track is:

- App, CLI, IDE, web/cloud, and local/worktree/cloud thread modes.
- Cloud environments with setup, cache, branch/commit checkout, and controlled agent internet access.
- App-server JSON-RPC style control plane for rich clients.
- Skills, plugins, MCP, custom prompts, rules, hooks, and AGENTS.md guidance.
- GitHub code review and Codex GitHub Action automation.
- Slack task creation and completion links for collaboration workflows.
- SDK and non-interactive mode for programmatic embedding.
- Approval, sandbox, enterprise admin, RBAC, audit, analytics, and managed configuration.

## Execution Tasks

### Task 1: Keep Feishu Pilot V1 Evidence Fresh

**Files:**
- Modify only if needed: `scripts/commercial_pilot_customer_acceptance_pack.py`
- Runtime evidence: `.xagent_runtime/reports/commercial-pilot-customer-acceptance-pack.json`

- [x] Run the final Feishu customer acceptance pack.

```powershell
python scripts\commercial_pilot_customer_acceptance_pack.py
```

Expected: `Commercial pilot customer acceptance pack status: customer_acceptance_pack_ready`.

- [ ] Re-run this command after any Feishu live evidence, final gate, delivery receipt, acceptance gate, or handoff index refresh.

### Task 2: Publish The Latest Codex Alignment Matrix

**Files:**
- Create: `scripts/latest_codex_alignment.py`
- Create: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.md`

- [x] Generate a read-only latest Codex alignment report.

```powershell
python scripts\latest_codex_alignment.py
```

Expected: `Latest Codex alignment status: latest_codex_alignment_plan_ready`.

- [x] Verify the report never sets `full_codex_parity_claimed=true`.

```powershell
python -m pytest tests/test_latest_codex_alignment.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: all selected tests pass.

### Task 3: P0 Control Plane Execution

**Target:** Convert `docs/specs/xagent-control-plane-protocol.md` from specification into backend contract endpoints.

**Files:**
- Modify: `backend/app/api/`
- Test: `tests/test_control_plane_protocol.py`

- [x] Add a thin control-plane API over these groups: `thread`, `turn`, `tool`, `approval`, `plugin`, `skill`, `mcp`, `channel`, and `runtime/evidence`.
- [x] Keep every operation auditable.
- [x] Reject raw production secrets in request payloads.
- [x] Validate with:

```powershell
python -m pytest tests/test_control_plane_protocol.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: all new control-plane protocol tests pass.

### Task 4: P0 Thread, Worktree, And Automation State

**Target:** Make X-Agent runs inspectable like durable Codex threads while preserving enterprise run/audit semantics.

**Files:**
- Modify: `backend/app/api/workbench.py`
- Modify: existing thread/run service modules as needed
- Test: `tests/test_workbench_thread_loop.py`
- Test: `tests/test_commercial_pilot_workbench_thread.py`

- [ ] Expose durable run state for thread, turn, item, tool call, approval, artifact, channel event, and evidence link.
- [ ] Add fork/resume/rollback metadata without claiming file rollback.
- [ ] Validate with:

```powershell
python -m pytest tests/test_workbench_thread_loop.py tests/test_commercial_pilot_workbench_thread.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected workbench/thread tests pass.

### Task 5: P0 Cloud Task Environment Contract

**Target:** Add a Codex-cloud-style task environment contract for isolated task execution.

**Files:**
- Create: `docs/specs/xagent-cloud-task-environment.md`
- Create: `tests/test_cloud_task_environment_contract.py`

- [ ] Define checkout identity, setup script, maintenance script, runtime network policy, task loop, artifact diff, and evidence export.
- [ ] Keep secrets available only to setup or owner-approved phases.
- [ ] Validate with:

```powershell
python -m pytest tests/test_cloud_task_environment_contract.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: cloud task environment contract tests pass.

### Task 6: P0 GitHub Review And Action Workflow

**Target:** Package existing GitHub issue-to-PR and CI evidence into a Codex-style dry-run review/action loop.

**Files:**
- Modify or add under: `scripts/`
- Test: `tests/test_issue_to_pr_api.py`
- Test: `tests/test_issue_to_pr_pipeline.py`
- Test: `tests/test_cli_github.py`

- [ ] Add a read-only report that maps issue, PR, branch, patch, CI, and review evidence.
- [ ] Keep network mutation behind explicit owner-approved execution.
- [ ] Validate with:

```powershell
python -m pytest tests/test_issue_to_pr_api.py tests/test_issue_to_pr_pipeline.py tests/test_cli_github.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected GitHub workflow tests pass.

### Task 7: P0 Skills, Plugins, MCP, And Hooks Governance

**Target:** Convert strong existing primitives into a commercial lifecycle.

**Files:**
- Modify: `backend/app/core/skill_curator/`
- Modify: `backend/app/core/mcp/`
- Modify: `backend/app/core/hooks/`
- Test: `tests/test_skill_curator_api.py`
- Test: `tests/test_mcp_manager.py`
- Test: `tests/test_hooks_manager.py`

- [ ] Add lifecycle states: draft, validate, review, approve, promote, rollback.
- [ ] Attach permission, MCP dependency, data-access, test-command, and rollback metadata.
- [ ] Validate with:

```powershell
python -m pytest tests/test_skill_curator_api.py tests/test_mcp_manager.py tests/test_hooks_manager.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected governance tests pass.

### Task 8: P0 Approval, Sandbox, And Enterprise Admin Contract

**Target:** Normalize safety decisions across API, CLI, channel, MCP, browser, and GitHub flows.

**Files:**
- Modify: `backend/app/core/approvals.py`
- Modify: `backend/app/core/sandbox/`
- Test: `tests/test_approvals.py`
- Test: `tests/test_security_sandbox.py`

- [ ] Normalize approval subjects: command, file change, network request, MCP elicitation, browser action, channel send, issue-to-PR execute.
- [ ] Add decision types: approve once, approve for run, approve for session, deny, abort.
- [ ] Validate with:

```powershell
python -m pytest tests/test_approvals.py tests/test_security_sandbox.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected approval and sandbox tests pass.

### Task 9: P1 SDK, Non-Interactive CLI, And Domestic Channel Expansion

**Target:** Follow P0 only after control-plane and governance contracts stabilize.

**Files:**
- Modify: `cli/`
- Add future SDK contract tests under: `tests/`
- Modify domestic channel docs after Pilot V1 acceptance.

- [ ] Add SDK-style thread start/resume/run wrappers over the control plane.
- [ ] Keep Feishu as first domestic channel; add DingTalk or WeChat Work after pilot acceptance.
- [ ] Keep Slack non-blocking for the domestic first version.

## Completion Criteria

- `scripts/latest_codex_alignment.py` returns `latest_codex_alignment_plan_ready`.
- P0 task board is complete and machine-readable.
- Feishu Pilot V1 remains `customer_acceptance_pack_ready`.
- `full_codex_parity_claimed=false` remains true in all generated alignment and pilot reports.
- UI session files remain untouched by this backend alignment work.
