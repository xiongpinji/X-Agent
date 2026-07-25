# Codex Hermes Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the highest-value gaps between X-Agent and Codex/Hermes by turning the existing backend-heavy framework into a usable, verifiable first-release product with a working entrypoint, channel loop, GitHub workflow, skill-learning loop, installer, and acceptance matrix.

**Architecture:** Preserve X-Agent's enterprise-agent positioning instead of copying IDE-assistant products wholesale. Build thin product-facing layers over existing core modules: security principal contract, workbench/chat, channels, issue-to-PR, skill/memory, scheduling, and acceptance reports. Keep each work package independently testable so the long task can run in waves without file collisions.

**Tech Stack:** Python 3.11+ / FastAPI / Typer / pytest / React 18 / Vite / TypeScript / PWA / GitHub API / existing X-Agent MCP, hooks, channels, skill, memory, workflow, and sandbox modules.

---

## Current Gap Summary

X-Agent already has strong platform primitives: MCP manager, hooks, CLI, context management, enterprise IM manager, Telegram/Discord/DingTalk channel adapters, Web Chat/PWA files, Chrome MV3 extension, workflow scheduling, skill marketplace, memory v2, GitHub issue-to-PR pipeline, sandbox modules, and enterprise security. The current gap is productization and verified end-to-end loops.

Primary gaps versus Codex:
- Developer workflow surface is weaker: no mature IDE extension, weak GitHub issue/PR automation evidence, no first-class worktree/cloud-task experience.
- Product entrypoint is fragile: `/api/v1/workbench` currently fails because `Principal` lacks `session_id` and `created_at`.
- No current acceptance/parity report exists in this working tree under `.xagent_runtime/reports`.
- Install/onboarding is not competitive with one-command Codex/Claude/Hermes/OpenClaw flows.

Primary gaps versus Hermes:
- No autonomous Skill Curator that learns from successful tasks and improves skills over time.
- Messaging channels are adapters, not a full inbound event -> agent run -> reply loop.
- Persistent personal memory and scheduled automation exist in modules, but are not exposed as an integrated product workflow.
- No gateway-style daemon/onboarding path that makes the agent always available from chat.

## Long Task Definition

The long task is complete only when all of these outcomes are true:

1. `/chat`, `/api/v1/workbench`, `/api/v1/health`, readiness, and core first-release API entrypoints pass in one smoke test.
2. Telegram channel loop works in test mode: signed inbound webhook payload creates an agent/task dispatch and returns/sends a reply through a mocked sender.
3. GitHub issue-to-PR flow has a deterministic dry-run path: issue payload -> plan -> branch metadata -> patch summary -> PR draft payload, with no network writes by default.
4. Skill Curator MVP exists: reads skill execution/memory evidence, scores skills, writes improvement proposals, and can create a candidate skill draft without executing unsafe code.
5. PWA/Web Chat exposes run status, tool events, approvals, and channel handoff status enough for first-release usability.
6. One-command local installer/check script validates Python, Node, env, frontend build, backend import, and representative tests.
7. Acceptance matrix regenerates `.xagent_runtime/reports/codex-hermes-gap-closure.json` and fails if any P0 loop is broken.
8. Docs state exact competitive parity claims and remaining gaps without saying "100%" unless acceptance evidence exists.

## Work Package Map

### WP0: Stabilize First-Release Contract

**Purpose:** Fix the current blocking regression and create a stable principal/session contract used by workbench, chat, dispatch, audit, and acceptance tests.

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/workbench.py` only if graceful fallback is still needed after the principal fix
- Test: `tests/test_first_release_entrypoints.py`
- Test: `tests/test_security.py`

**Required behavior:**
- `Principal` must include `session_id: str` and `created_at: datetime | str` with stable defaults.
- `anonymous_principal()` may be development-authenticated only when `require_api_key=False`, but it must not break endpoint models.
- `/api/v1/workbench` must return 200 in development test mode.

**Steps:**
- [ ] Write or update `tests/test_security.py::test_anonymous_principal_has_workbench_contract_fields`.
- [ ] Run `python -m pytest tests/test_security.py::test_anonymous_principal_has_workbench_contract_fields -o addopts="" -p no:cov -q` and verify it fails before implementation if the field is missing.
- [ ] Add `session_id` and `created_at` to `Principal` in `backend/app/core/security.py`.
- [ ] Run `python -m pytest tests/test_security.py tests/test_first_release_entrypoints.py -o addopts="" -p no:cov -q`.
- [ ] Verify the prior failure `AttributeError: 'Principal' object has no attribute 'session_id'` is gone.

**Acceptance command:**
```powershell
python -m pytest tests/test_first_release_entrypoints.py tests/test_security.py -o addopts="" -p no:cov -q
```

Expected: all selected tests pass.

### WP1: Web Chat and Workbench First-Run Product Loop

**Purpose:** Make X-Agent feel usable from a browser, not just from API docs.

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/workbench.py`
- Modify: `backend/app/api/workflows.py`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/console/pages/chat/RealtimeChatPage.tsx`
- Modify: `frontend/src/utils/pwaManager.ts`
- Test: `tests/test_first_release_entrypoints.py`
- Add: `tests/test_chat_entrypoint_contract.py`
- Optional frontend tests: `frontend/src/__tests__/pages/ChatPage.test.tsx` if frontend test infra is already reliable

**Required behavior:**
- `/chat` returns the static first-run HTML.
- React `/chat` can submit a prompt to a backend endpoint and render a run id/status.
- Chat response schema includes `run_id`, `status`, `message`, `events`, `approval_required`, and `next_actions`.
- Workbench bootstrap includes user/session/agent/tenant fields.
- PWA shortcut points to `/chat`.

**Steps:**
- [ ] Add backend contract tests for `GET /chat`, `POST /api/v1/workflows/create/chat`, and `GET /api/v1/workbench`.
- [ ] Standardize the chat response shape in `backend/app/api/workflows.py`.
- [ ] Add frontend API helper for chat submit if none exists.
- [ ] Update `ChatPage.tsx` to show run status, latest assistant message, and approval/tool event placeholders from the response.
- [ ] Keep UI controls minimal: prompt input, submit, status, run id, event list.
- [ ] Run backend tests first.
- [ ] Run `cd frontend; npm run type-check`.

**Acceptance commands:**
```powershell
python -m pytest tests/test_chat_entrypoint_contract.py tests/test_first_release_entrypoints.py -o addopts="" -p no:cov -q
cd frontend
npm run type-check
```

Expected: backend contract tests pass; frontend type-check passes.

### WP2: Telegram Channel End-to-End Loop

**Purpose:** Close the Hermes/OpenClaw messaging gap with one complete production-shaped channel before adding more channels.

**Files:**
- Modify: `backend/app/core/channels/base.py`
- Modify: `backend/app/core/channels/telegram_adapter.py`
- Add: `backend/app/core/channels/router.py`
- Add: `backend/app/api/channels.py`
- Modify: `backend/app/main.py` to include the router
- Test: `tests/test_channels.py`
- Add: `tests/test_channel_router.py`
- Add: `tests/test_telegram_channel_api.py`

**Required behavior:**
- Telegram webhook verifies `X-Telegram-Bot-Api-Secret-Token`.
- Inbound message is normalized to `ChannelMessage`.
- Router dispatches message to existing workflow/agent dispatch boundary.
- Reply sender is injectable and mocked in tests; no real Telegram network call in unit tests.
- Event processing returns a stable receipt: `channel`, `conversation_id`, `message_id`, `run_id`, `status`, `reply_sent`.

**Steps:**
- [ ] Add `ChannelDispatchResult` model to `backend/app/core/channels/base.py`.
- [ ] Add `ChannelRouter` that accepts adapter registry plus a dispatch callable.
- [ ] Add `POST /api/v1/channels/telegram/webhook`.
- [ ] Add tests for valid signature, invalid signature, unsupported payload, and successful mocked dispatch/reply.
- [ ] Keep Discord/DingTalk adapters untouched except for shared base model compatibility.

**Acceptance command:**
```powershell
python -m pytest tests/test_channels.py tests/test_channel_router.py tests/test_telegram_channel_api.py -o addopts="" -p no:cov -q
```

Expected: all selected tests pass, no external network required.

### WP3: Codex-Style GitHub Issue-to-PR Dry-Run Workflow

**Purpose:** Make X-Agent credible against Codex on code-agent automation without risking uncontrolled repository writes.

**Files:**
- Modify: `backend/app/core/pipelines/issue_to_pr.py`
- Modify: `backend/app/core/github_integration.py`
- Add: `backend/app/api/issue_to_pr.py`
- Add: `cli/commands/github_cmd.py`
- Modify: `cli/main.py`
- Test: `tests/test_issue_to_pr_pipeline.py`
- Add: `tests/test_issue_to_pr_api.py`
- Add: `tests/test_cli_github.py`

**Required behavior:**
- Dry-run is default.
- Input can be a GitHub issue URL or structured issue payload.
- Output includes parsed repo, issue number, plan, touched file candidates, branch name, commit title, PR title/body, and risk flags.
- Execute mode requires explicit `execute=true` and token presence.
- No real network in unit tests; use fake GitHub client.

**Steps:**
- [ ] Extend pipeline models with `IssueToPRPlan`, `IssueToPRDryRunResult`, and `IssueToPRExecutionResult`.
- [ ] Add dry-run API endpoint `POST /api/v1/issue-to-pr/dry-run`.
- [ ] Add guarded execute endpoint `POST /api/v1/issue-to-pr/execute`.
- [ ] Add CLI command `xagent github issue-to-pr --issue <url> --dry-run`.
- [ ] Test URL parsing, dry-run result, missing token execute failure, and fake successful execute.

**Acceptance command:**
```powershell
python -m pytest tests/test_issue_to_pr_pipeline.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts="" -p no:cov -q
```

Expected: dry-run works without network; execute path is guarded.

### WP4: Hermes-Style Skill Curator MVP

**Purpose:** Add the missing self-improvement loop: learn from usage, score skills, propose improvements, draft new skills.

**Files:**
- Add: `backend/app/core/skill_curator/models.py`
- Add: `backend/app/core/skill_curator/evidence.py`
- Add: `backend/app/core/skill_curator/scoring.py`
- Add: `backend/app/core/skill_curator/planner.py`
- Add: `backend/app/core/skill_curator/writer.py`
- Add: `backend/app/core/skill_curator/__init__.py`
- Add: `backend/app/api/skill_curator.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_skill_curator_models.py`
- Test: `tests/test_skill_curator_scoring.py`
- Test: `tests/test_skill_curator_api.py`
- Docs: `docs/SKILL_CURATOR_MVP.md`

**Required behavior:**
- Curator reads evidence from skill execution history if available, and can also accept explicit evidence in tests.
- Curator computes score from success rate, recency, frequency, error rate, and manual rating.
- Curator produces `SkillImprovementProposal` objects with reason, action, confidence, and safety level.
- Curator can draft a `SKILL.md` candidate into a safe staging directory, not active skills.
- API exposes analyze/draft endpoints with dry-run default.

**Steps:**
- [ ] Define Pydantic models for evidence, scores, proposals, and drafts.
- [ ] Implement deterministic scoring with no LLM dependency.
- [ ] Implement proposal planner rules: low success -> improve, repeated manual workflow -> create skill, unused stale skill -> review.
- [ ] Implement safe writer under `.xagent/skill-curator/drafts/`.
- [ ] Add API endpoints `POST /api/v1/skill-curator/analyze` and `POST /api/v1/skill-curator/draft`.
- [ ] Add docs showing how this maps to Hermes-style learning without unsafe auto-install.

**Acceptance command:**
```powershell
python -m pytest tests/test_skill_curator_models.py tests/test_skill_curator_scoring.py tests/test_skill_curator_api.py -o addopts="" -p no:cov -q
```

Expected: curator MVP passes with deterministic local evidence.

### WP5: Scheduling and Always-Available Gateway Mode

**Purpose:** Package existing scheduler/workflow worker into a product feature comparable to Hermes cron and OpenClaw gateway.

**Files:**
- Modify: `backend/app/api/scheduler.py`
- Modify: `backend/app/workflow_worker.py`
- Add: `backend/app/core/channels/gateway.py`
- Add: `cli/commands/gateway_cmd.py`
- Modify: `cli/main.py`
- Test: `tests/test_scheduler.py`
- Add: `tests/test_gateway_mode.py`
- Docs: `docs/GATEWAY_MODE.md`

**Required behavior:**
- `xagent gateway start --once` runs due schedules once and exits for testability.
- `xagent gateway status` reports configured channels and scheduler status.
- Scheduled workflow can target a channel delivery method in dry-run mode.
- Gateway does not require real Telegram credentials for local status/dry-run tests.

**Steps:**
- [ ] Add gateway service wrapper around workflow scheduler and channel registry.
- [ ] Add CLI status/start commands.
- [ ] Add tests for status, once-run dry-run, and missing credentials.
- [ ] Document production daemon options separately from local dev mode.

**Acceptance command:**
```powershell
python -m pytest tests/test_scheduler.py tests/test_gateway_mode.py -o addopts="" -p no:cov -q
```

Expected: scheduler and gateway dry-run behavior passes without external services.

### WP6: One-Command Local Installer and Doctor

**Purpose:** Close the onboarding gap with Hermes/OpenClaw one-liners and reduce environment ambiguity.

**Files:**
- Add: `scripts/install-xagent.ps1`
- Add: `scripts/install-xagent.sh`
- Add: `scripts/xagent_doctor.py`
- Add: `tests/test_xagent_doctor.py`
- Docs: `docs/INSTALL_QUICKSTART.md`
- Modify: `README.md` if present and appropriate

**Required behavior:**
- Doctor checks Python version, Node version, package install status, env vars, frontend dependencies, backend import, and representative test command availability.
- Install script defaults to dry-run unless `-Execute` or `--execute` is passed.
- Windows script must not modify global PATH without explicit confirmation.
- Scripts print exact next commands for backend and frontend.

**Steps:**
- [ ] Implement pure Python doctor checks with JSON output mode.
- [ ] Add tests for doctor using monkeypatched command results.
- [ ] Add PowerShell install script with `-DryRun` default and `-Execute`.
- [ ] Add POSIX shell script with `--dry-run` default and `--execute`.
- [ ] Add quickstart docs with Windows-first commands.

**Acceptance commands:**
```powershell
python -m pytest tests/test_xagent_doctor.py -o addopts="" -p no:cov -q
python scripts/xagent_doctor.py --json
powershell -ExecutionPolicy Bypass -File scripts/install-xagent.ps1 -DryRun
```

Expected: tests pass; doctor reports actionable status; dry-run installer makes no changes.

### WP7: Acceptance Matrix and Competitive Parity Report

**Purpose:** Replace stale completion claims with generated evidence.

**Files:**
- Add: `scripts/codex_hermes_gap_matrix.py`
- Add: `tests/test_codex_hermes_gap_matrix.py`
- Add generated output path: `.xagent_runtime/reports/codex-hermes-gap-closure.json`
- Docs: `docs/CODEX_HERMES_GAP_CLOSURE_REPORT.md`

**Required behavior:**
- Matrix checks P0 command list and summarizes pass/fail/skipped.
- Matrix records git status, Python version, selected test results, generated timestamp, and missing evidence.
- Matrix has explicit categories: first_release, web_chat, telegram_loop, github_issue_to_pr, skill_curator, gateway, installer, frontend, docs.
- Report must not claim full parity if any P0 category is missing.

**Steps:**
- [ ] Implement matrix runner using `subprocess.run` with timeouts.
- [ ] Add `--dry-run` to print planned commands.
- [ ] Add `--write-report` to generate JSON.
- [ ] Add tests using fake command runner.
- [ ] Add docs explaining how to interpret the report.

**Acceptance command:**
```powershell
python -m pytest tests/test_codex_hermes_gap_matrix.py -o addopts="" -p no:cov -q
python scripts/codex_hermes_gap_matrix.py --dry-run
```

Expected: tests pass; dry-run prints all planned checks.

### WP8: IDE Extension Strategy Without Blocking Release

**Purpose:** Address Codex/Claude Code IDE gap pragmatically without derailing the first release.

**Files:**
- Add: `docs/IDE_EXTENSION_ROADMAP.md`
- Add: `docs/specs/vscode-extension-mvp.md`
- Optional later create: `vscode-extension/package.json`
- Optional later create: `vscode-extension/src/extension.ts`

**Required behavior for this long task:**
- Produce a concrete MVP spec, not full implementation.
- MVP must include commands: connect to X-Agent, open chat, send selected code to agent, show run status, apply patch preview.
- Identify API endpoints needed from existing backend and gaps.
- Defer marketplace publishing until Web Chat, channel loop, GitHub dry-run, and acceptance matrix are green.

**Steps:**
- [ ] Write `docs/specs/vscode-extension-mvp.md` with command list, UX flow, API calls, security model, and test plan.
- [ ] Write `docs/IDE_EXTENSION_ROADMAP.md` with milestone order: spec -> local extension -> patch preview -> marketplace.
- [ ] Link IDE roadmap from gap closure report.

**Acceptance command:**
```powershell
Test-Path docs/specs/vscode-extension-mvp.md
Test-Path docs/IDE_EXTENSION_ROADMAP.md
```

Expected: both docs exist and contain API/UX/security/test sections.

## Execution Order

Use this order for fastest risk reduction:

1. WP0: First-release contract fix.
2. WP7 skeleton: acceptance matrix dry-run, so later WPs can register checks.
3. WP1: Web Chat/workbench loop.
4. WP2: Telegram E2E loop.
5. WP3: GitHub issue-to-PR dry-run.
6. WP4: Skill Curator MVP.
7. WP5: Gateway/scheduler mode.
8. WP6: Installer/doctor.
9. WP8: IDE roadmap.
10. WP7 final: generated report with all checks wired.

## Parallelization Plan

Safe parallel lanes after WP0:

- Lane A: WP1 frontend/backend chat.
- Lane B: WP2 channels.
- Lane C: WP3 GitHub issue-to-PR.
- Lane D: WP4 Skill Curator.
- Lane E: WP6 installer/doctor.
- Lane F: WP7 matrix.

Avoid parallel edits to:
- `backend/app/main.py`
- `cli/main.py`
- shared security files

Merge rule:
- Each lane must land with its own tests passing.
- Re-run WP7 matrix after every lane merge.
- Never use `git add .`; stage explicit files only.

## Verification Suite

Minimum final commands:

```powershell
python -m pytest tests/test_first_release_entrypoints.py tests/test_security.py -o addopts="" -p no:cov -q
python -m pytest tests/test_channels.py tests/test_channel_router.py tests/test_telegram_channel_api.py -o addopts="" -p no:cov -q
python -m pytest tests/test_issue_to_pr_pipeline.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts="" -p no:cov -q
python -m pytest tests/test_skill_curator_models.py tests/test_skill_curator_scoring.py tests/test_skill_curator_api.py -o addopts="" -p no:cov -q
python -m pytest tests/test_scheduler.py tests/test_gateway_mode.py tests/test_xagent_doctor.py tests/test_codex_hermes_gap_matrix.py -o addopts="" -p no:cov -q
cd frontend
npm run type-check
cd ..
python scripts/codex_hermes_gap_matrix.py --write-report
```

Expected:
- All selected backend tests pass.
- Frontend type-check passes.
- `.xagent_runtime/reports/codex-hermes-gap-closure.json` is generated and reports all P0 categories passed.

## Completion Criteria

Do not mark the long task complete until:

- Current `/api/v1/workbench` regression is fixed.
- Web Chat and PWA entry are verified.
- Telegram loop has mocked E2E tests.
- GitHub issue-to-PR dry-run is implemented and guarded.
- Skill Curator MVP exists and writes drafts only to staging.
- Gateway dry-run/status exists.
- Installer/doctor exists and is dry-run safe.
- Acceptance matrix writes a fresh report.
- Docs clearly state remaining gaps: full IDE extension, real mobile native apps, production cloud sandbox SLA, broad channel count parity, and full external provider matrix.

## Self-Review Notes

Spec coverage:
- Codex gap covered by WP1, WP3, WP7, WP8.
- Hermes gap covered by WP2, WP4, WP5, WP6.
- Current local failures covered by WP0.
- Productization covered by WP1, WP6, WP7.

Placeholder scan:
- No task depends on undefined "later" behavior for P0 completion.
- IDE full implementation is explicitly out of long-task completion and documented as roadmap.

Type consistency:
- Shared channel models are introduced in WP2 before API use.
- Principal contract is fixed before workbench/chat acceptance.
- Matrix report is introduced early and finalized after all checks are available.
