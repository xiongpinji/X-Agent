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
- Modify: `backend/app/api/control_plane.py`
- Keep untouched by this backend task: UI-facing `backend/app/api/workbench.py`
- Modify: existing thread/run service modules only if needed
- Test: `tests/test_control_plane_protocol.py`
- Test: `tests/test_workbench_thread_loop.py`
- Test: `tests/test_commercial_pilot_workbench_thread.py`

- [x] Expose durable run state for thread, turn, item, tool call, approval, artifact, channel event, and evidence link through the control-plane read contract.
- [x] Add fork/resume/rollback metadata without claiming file rollback.
- [x] Expose worktree and automation state as metadata-only/evidence-only fields with no file mutation.
- [ ] Promote metadata-only worktree and automation fields into real owner-gated adapters after cloud task and scheduler contracts land.
- [ ] Validate with:

```powershell
python -m pytest tests/test_control_plane_protocol.py tests/test_workbench_thread_loop.py tests/test_commercial_pilot_workbench_thread.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected workbench/thread tests pass.

### Task 5: P0 Cloud Task Environment Contract

**Target:** Add a Codex-cloud-style task environment contract for isolated task execution.

**Files:**
- Create: `docs/specs/xagent-cloud-task-environment.md`
- Create: `tests/test_cloud_task_environment_contract.py`

- [x] Define checkout identity, setup script, maintenance script, runtime network policy, task loop, artifact diff, and evidence export.
- [x] Keep secrets available only to setup or owner-approved phases.
- [x] Keep hosted container, network, PR, and checkout mutation behind future owner-gated adapters.
- [ ] Implement the owner-gated hosted runner adapter and smoke report after this contract stabilizes.
- [ ] Validate with:

```powershell
python -m pytest tests/test_cloud_task_environment_contract.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: cloud task environment contract tests pass.

### Task 6: P0 GitHub Review And Action Workflow

**Target:** Package existing GitHub issue-to-PR and CI evidence into a Codex-style dry-run review/action loop.

**Files:**
- Modify or add under: `scripts/`
- Test: `tests/test_github_review_action_report.py`
- Test: `tests/test_issue_to_pr_api.py`
- Test: `tests/test_issue_to_pr_pipeline.py`
- Test: `tests/test_cli_github.py`

- [x] Add a read-only report that maps issue, PR, branch, patch, CI, and review evidence.
- [x] Keep network mutation behind explicit owner-approved execution.
- [x] Redact secret-like issue content from generated report evidence.
- [ ] Implement owner-gated GitHub execute adapters for PR creation, review comments, issue comments, and GitHub Action dispatch after dry-run evidence review.
- [ ] Validate with:

```powershell
python scripts\github_review_action_report.py
python -m pytest tests/test_github_review_action_report.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected GitHub workflow tests pass.

### Task 7: P0 Skills, Plugins, MCP, And Hooks Governance

**Target:** Convert strong existing primitives into a commercial lifecycle.

**Files:**
- Create: `scripts/governance_lifecycle_report.py`
- Create: `tests/test_governance_lifecycle_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/governance-lifecycle-report.json`
- Runtime evidence: `.xagent_runtime/reports/governance-lifecycle-report.md`
- Future adapter scope: `backend/app/core/skill_curator/`
- Future adapter scope: `backend/app/core/mcp/`
- Future adapter scope: `backend/app/core/hooks/`
- Test: `tests/test_skill_curator_api.py`
- Test: `tests/test_mcp_manager.py`
- Test: `tests/test_hooks_manager.py`

- [x] Add lifecycle states: draft, validate, review, approve, promote, rollback.
- [x] Attach permission, MCP dependency, data-access, test-command, and rollback metadata.
- [x] Keep skill promotion, plugin enablement, MCP registration, hook persistence, and rollback as owner-gated future adapters.
- [ ] Implement real owner-gated lifecycle adapters after governance evidence review.
- [ ] Validate with:

```powershell
python scripts\governance_lifecycle_report.py
python -m pytest tests/test_skill_curator_api.py tests/test_mcp_manager.py tests/test_hooks_manager.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected governance tests pass.

### Task 8: P0 Approval, Sandbox, And Enterprise Admin Contract

**Target:** Normalize safety decisions across API, CLI, channel, MCP, browser, and GitHub flows.

**Files:**
- Modify: `backend/app/core/approvals.py`
- Modify: `backend/app/core/sandbox/security.py`
- Create: `scripts/approval_sandbox_admin_report.py`
- Create: `tests/test_approval_sandbox_admin_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/approval-sandbox-admin-report.json`
- Runtime evidence: `.xagent_runtime/reports/approval-sandbox-admin-report.md`
- Test: `tests/test_approvals.py`
- Test: `tests/test_security_sandbox.py`

- [x] Normalize approval subjects: command, file change, network request, MCP elicitation, browser action, channel send, issue-to-PR execute.
- [x] Add decision types: approve once, approve for run, approve for session, deny, abort.
- [x] Attach sandbox profile, owner gate, admin policy, and audit-required metadata to each mutating subject.
- [x] Keep adapter-level execution enforcement as a future owner-gated implementation step.
- [ ] Implement adapter-level enforcement for CLI, channel, MCP, browser, and GitHub execute flows after contract evidence review.
- [ ] Validate with:

```powershell
python scripts\approval_sandbox_admin_report.py
python -m pytest tests/test_approvals.py tests/test_security_sandbox.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Expected: selected approval and sandbox tests pass.

### Task 9: P1 SDK, Non-Interactive CLI, And Domestic Channel Expansion

**Target:** Follow P0 only after control-plane and governance contracts stabilize.

**Files:**
- Modify: `cli/`
- Create: `backend/app/sdk/control_plane.py`
- Create: `cli/commands/sdk_cmd.py`
- Create: `tests/test_xagent_sdk_contract.py`
- Create: `scripts/sdk_noninteractive_report.py`
- Create: `tests/test_sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.md`
- Modify domestic channel docs only after Pilot V1 acceptance.

- [x] Add SDK-style thread start/resume/run wrappers over the control plane.
- [x] Add non-interactive CLI JSON commands for thread start/resume/turn-run/read envelopes.
- [x] Keep Feishu as first domestic channel; add DingTalk or WeChat Work after pilot acceptance.
- [x] Keep Slack non-blocking for the domestic first version.
- [ ] Implement real SDK HTTP adapters and long-running non-interactive execution after the contract report is reviewed.

### Task 10: SDK Backend Stub And Control-Plane Binding

**Target:** Accept SDK/non-interactive envelopes through the backend control-plane without enabling real execution.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.md`

- [x] Add `/api/v1/control-plane/sdk/invoke` backend stub.
- [x] Normalize SDK envelopes into `/api/v1/control-plane/invoke`.
- [x] Preserve SDK `dry_run`, `idempotency_key`, `sdk_surface`, and `non_interactive` metadata.
- [x] Bind SDK execution intent to the approval/sandbox/admin contract as an owner-gated `command` subject.
- [x] Keep agent runner invocation, channel send, file mutation, and network mutation disabled.
- [ ] Implement real SDK HTTP adapters and long-running non-interactive execution after backend stub review.

### Task 11: SDK HTTP Dry-Run Client Adapter

**Target:** Let CLI `--execute` submit SDK envelopes to the backend SDK stub without enabling real agent execution.

**Files:**
- Modify: `cli/client.py`
- Modify: `cli/commands/sdk_cmd.py`
- Modify: `backend/app/sdk/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.md`

- [x] Add `HTTPClient.invoke_sdk_contract`.
- [x] Keep local client SDK backend invocation unsupported.
- [x] Make `xagent sdk <write-command> --execute` call `/api/v1/control-plane/sdk/invoke`.
- [x] Keep commands without `--execute` as local envelope-only output.
- [x] Keep `--execute` bounded to the owner-gated backend stub; no agent runner, channel send, file, or network mutation is enabled.
- [ ] Implement owner-approved long-running SDK execution adapters after dry-run adapter review.

### Task 12: SDK Execution Approval Intent Flow

**Target:** Convert SDK write-method `--execute` requests into owner approval intent records without running the agent.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.md`

- [x] Create pending approval intent for SDK write methods submitted to `/api/v1/control-plane/sdk/invoke`.
- [x] Use normalized approval subject `command` with `sdk:<method>` resource ids.
- [x] Keep SDK read methods approval-free.
- [x] Keep approval creation separate from execution; no `mark_executed`, agent runner, channel send, file mutation, or network mutation.
- [ ] Implement owner-approved long-running SDK execution adapters after approval intent evidence review.

### Task 13: SDK Approval Handoff And Readback

**Target:** Return actionable owner handoff metadata after SDK approval intent creation without executing the approved work.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.md`

- [x] Include approval id in SDK handoff metadata.
- [x] Include `xagent approvals show <approval_id>` and `xagent approvals approve <approval_id>` next commands.
- [x] Include approval API links and `approval/read` control-plane readback metadata.
- [x] Keep `xagent approvals execute <approval_id>` explicitly blocked for SDK long-running runs in this task.
- [x] Keep agent runner invocation, `mark_executed`, channel send, file mutation, and network mutation disabled.
- [ ] Implement owner-approved long-running SDK execution adapters after approval handoff evidence review.

### Task 14: Owner-Approved SDK Execution Adapter Contract

**Target:** Let SDK/CLI submit an approved approval id for backend readback/preflight while still preventing real execution.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `backend/app/sdk/control_plane.py`
- Modify: `cli/commands/sdk_cmd.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`

- [x] Add SDK envelope support for `approved_approval_id` / owner-approved preflight metadata.
- [x] Add CLI `--approved-approval-id <approval_id>` on SDK write commands.
- [x] Add backend approval readback/preflight contract for approved SDK ids.
- [x] Return `approved_ready` only when approval exists, is approved, matches `sdk:<method>`, and passes tenant checks.
- [x] Keep `adapter_execution_enabled`, agent execution, `mark_executed`, file/network/channel mutation disabled.
- [ ] Implement concrete owner-approved SDK runner after runtime safety review.

### Task 15: SDK Read-Only Runner Contract

**Target:** Let SDK/CLI read-only methods call the backend through `/sdk/invoke` and return control-plane read results, while write execution remains disabled.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `backend/app/sdk/control_plane.py`
- Modify: `cli/commands/sdk_cmd.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`

- [x] Add SDK `runtime/evidence/read` wrapper.
- [x] Allow `xagent sdk thread-read <thread_id> --execute` to call `/sdk/invoke`.
- [x] Add `xagent sdk evidence-read <report_name> --execute` read-only command.
- [x] Return `read_only_runner_contract` metadata from `/sdk/invoke`.
- [x] Keep write SDK methods owner-gated; no agent runner, `mark_executed`, file/network/channel mutation.
- [ ] Implement concrete owner-approved write SDK runner after runtime safety review.

### Task 16: Owner-Approved Write Runner Safety Contract

**Target:** Add an auditable safety plan and receipt template for future owner-approved write SDK execution without invoking the write runner.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `backend/app/sdk/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`

- [x] Return `write_runner_safety_contract` from `/sdk/invoke`.
- [x] Include runner plan fields, guard order, and receipt template.
- [x] Mark approved write preflight as `ready_for_runner_contract=true` only when approval/resource/tenant checks pass.
- [x] Keep `runner_invoked=false`, agent/write execution disabled, `mark_executed=false`, and all mutation flags false.
- [ ] Implement concrete owner-approved write SDK runner after runtime safety review.

### Task 17: Owner-Approved Write Dry-Run Executor Stub

**Target:** Add an audited dry-run executor stub for approved write SDK requests without invoking the real agent runner.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`

- [x] Add `dry_run_executor_stub` to `/sdk/invoke` metadata.
- [x] Record `sdk.write_runner.dry_run_planned` audit event when approved write preflight is ready.
- [x] Include receipt with audit id, method, operation, approval id, and mutation flags.
- [x] Keep `runner_invoked=false`, agent/write execution disabled, `mark_executed=false`, and all mutation flags false.
- [ ] Implement concrete owner-approved write SDK runner after runtime safety review.

### Task 18: SDK Dry-Run Runtime Evidence Readback

**Target:** Let SDK and CLI read back the dry-run executor receipt schema through `runtime/evidence/read` while keeping the backend owner-gated stub non-mutating.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `backend/app/sdk/control_plane.py`
- Modify: `cli/commands/sdk_cmd.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`

- [x] Add dynamic `sdk_dry_run_executor_stub` evidence metadata to `runtime/evidence/read`.
- [x] Add SDK and CLI parameters for `--evidence-type`, `--approval-id`, and `--method`.
- [x] Include receipt schema and audit readback hints for `sdk.write_runner.dry_run_planned`.
- [x] Keep `runner_invoked=false`, agent/write execution disabled, `mark_executed=false`, and all mutation flags false.
- [x] Persist concrete SDK dry-run receipts before enabling any owner-approved write runner.

### Task 19: SDK Dry-Run Receipt Persistence

**Target:** Persist owner-approved SDK dry-run executor receipts in the audit log and read them back through `runtime/evidence/read`, without enabling real write execution.

**Files:**
- Modify: `backend/app/api/control_plane.py`
- Modify: `scripts/sdk_noninteractive_report.py`
- Modify: `scripts/latest_codex_alignment.py`
- Modify: `tests/test_control_plane_protocol.py`
- Modify: `tests/test_xagent_sdk_contract.py`
- Modify: `tests/test_cli_client.py`
- Modify: `tests/test_sdk_noninteractive_report.py`
- Modify: `tests/test_latest_codex_alignment.py`
- Runtime evidence: `.xagent_runtime/reports/sdk-noninteractive-report.json`
- Runtime evidence: `.xagent_runtime/reports/latest-codex-alignment.json`

- [x] Store the dry-run executor receipt on the `sdk.write_runner.dry_run_planned` audit event.
- [x] Read back persisted receipts by `approval_id`, `method`, and optional `audit_id`.
- [x] Surface `receipt_available`, `receipt_persisted`, audit hash, and signature presence in runtime evidence.
- [x] Keep `runner_invoked=false`, agent/write execution disabled, `mark_executed=false`, and all mutation flags false.
- [ ] Implement the concrete owner-approved write SDK runner only after persisted receipt safety review.

## Completion Criteria

- `scripts/latest_codex_alignment.py` returns `latest_codex_alignment_plan_ready`.
- P0 task board is complete and machine-readable.
- Feishu Pilot V1 remains `customer_acceptance_pack_ready`.
- `full_codex_parity_claimed=false` remains true in all generated alignment and pilot reports.
- UI session files remain untouched by this backend alignment work.
