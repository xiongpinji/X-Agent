# X-Agent Five Stage Commercial Delivery Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move X-Agent from local controlled commercial pilot readiness to an auditable full commercial delivery path without overstating GA or full Codex parity before the final gate proves it.

**Architecture:** The main controller owns staging decisions, file integration, verification, commits, and final claims. Parallel sessions may inspect or implement disjoint scopes, but they must not stage, commit, push, tag, deploy, delete files, or overwrite other sessions. Each phase produces evidence reports under `.xagent_runtime/reports/` and only advances when the controller verifies the phase gate.

**Tech Stack:** Git, PowerShell, Python 3.11 via `uv`, FastAPI backend, Vite/TypeScript frontend, Panda UI, local `.xagent_runtime/reports` gate scripts, GitHub/remote CI when explicitly executed.

---

## Current Baseline

- Branch: `feat/commercial-delivery-v1`
- Last local delivery commit: `91109e3 fix: harden commercial pilot panda bff gates`
- Previous closeout commit: `7bfd9bb fix: complete owner gated commercial delivery closeout`
- Local commercial delivery snapshot: `.xagent_runtime/reports/commercial-delivery-closure-snapshot.json`
- Local pilot final gate: `.xagent_runtime/reports/commercial-pilot-final-gate.json`
- Current verified status: controlled commercial pilot ready locally
- Forbidden claim until Stage 5 final gate: GA ready, production ready, full Codex parity

## Controller Rules

- The controller is the only actor allowed to stage, commit, push, tag, or trigger deploy.
- Worker sessions must assume other sessions are active and must not revert or overwrite others.
- Worker sessions should write only their assigned report path unless the controller assigns a disjoint implementation scope.
- No `git add .`, no cleanup/reset, no destructive delete, no tag/deploy/push without an explicit controller step.
- Every success claim requires fresh verification output from the current controller run.

## Phase Gates

### Stage 1: Worktree Boundary Closeout

**Objective:** Convert the dirty worktree into an auditable delivery boundary before any remote push or PR.

**Parallel lanes already dispatched:**
- Stage 1-A tracked dirty audit: `.xagent_runtime/reports/stage1-tracked-dirty-audit-20260615.md`
- Stage 1-B readiness packet audit: `.xagent_runtime/reports/stage1-readiness-packet-audit-20260615.md`
- Stage 1-C frontend assets/docs audit: `.xagent_runtime/reports/stage1-frontend-assets-docs-audit-20260615.md`
- Stage 1-D release/staging gate audit: `.xagent_runtime/reports/stage1-release-staging-gate-audit-20260615.md`

**Controller steps:**
- [ ] Run `git status --short --branch` and save the current dirty boundary in the controller notes.
- [ ] Read all four Stage 1 audit reports.
- [ ] Create `.xagent_runtime/reports/stage1-worktree-boundary-decision-20260615.md` with four classifications: include now, defer to GA/parity branch, local/private, discard/manual review.
- [ ] For files classified "include now", inspect diffs and stage only exact paths with `git add -- <path>`.
- [ ] For files classified "defer" or "local/private", leave unstaged and document the reason.
- [ ] For files classified "discard/manual review", do not delete automatically; record the command a human/controller may run later.
- [ ] Run `git diff --check --cached`.
- [ ] Run the minimum verification matrix required by the included file scope.
- [ ] Commit the Stage 1 boundary decision only if there are included paths.

**Stage 1 exit gate:**
- `git diff --cached --stat` is empty or contains only reviewed include-now files.
- No unrelated generated assets, secrets, or local environment files are staged.
- Stage 1 decision report exists and names every dirty family.

### Stage 2: Remote Delivery Chain

**Objective:** Move the controlled pilot branch through remote review and CI without mutating production.

**Controller steps:**
- [ ] Confirm Stage 1 exit gate.
- [ ] Run `git status --short --branch`.
- [ ] Run `git log --oneline -5`.
- [ ] Run fresh local gate:
  - `uv run --isolated --python 3.11 --extra dev pytest tests/test_workbench_bff.py tests/test_lite_mode.py tests/test_security.py::test_workflow_run_ignores_client_tenant_id -q -o addopts=--no-cov --tb=short`
  - `npm --prefix frontend run type-check`
  - `npm --prefix frontend run build`
  - `npm --prefix frontend run report:panda:strict`
  - `python scripts\commercial_delivery_closure_snapshot.py`
  - `python scripts\commercial_pilot_final_gate.py`
- [ ] Push `feat/commercial-delivery-v1` only after the status is auditable.
- [ ] Create or update the PR with bounded wording: controlled commercial pilot, not GA, not full Codex parity.
- [ ] Watch remote CI and record results in `.xagent_runtime/reports/stage2-remote-ci-handoff-20260615.md`.
- [ ] If CI fails, patch only the failing scope and rerun the failing job locally before pushing a fix.

**Stage 2 exit gate:**
- Remote branch exists.
- PR exists or explicit owner decision says no PR.
- CI status is green or failures are documented with exact blockers.
- No production deploy, tag, or outbound customer message is sent.

### Stage 3: Staging Release Rehearsal

**Objective:** Prove deployability, rollback, observability, and smoke coverage in staging or a staging-equivalent local environment.

**Controller steps:**
- [ ] Confirm Stage 2 exit gate.
- [ ] Read Stage 1-D release/staging gate audit for required secrets and commands.
- [ ] Create `.xagent_runtime/reports/stage3-staging-rehearsal-plan-20260615.md` with exact environment names, required variables, and no secret values.
- [ ] Run config validation scripts in dry-run mode where available.
- [ ] Deploy to staging only through approved deployment commands.
- [ ] Run staging smoke checks for health, auth, Panda BFF, workflow entrypoints, audit logs, and rollback readiness.
- [ ] Capture staging evidence in `.xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.md`.

**Stage 3 exit gate:**
- Staging smoke checks pass.
- Rollback command and expected rollback target are documented.
- Monitoring/logging signals are visible.
- Secrets are referenced by name only, never committed.

### Stage 4: Pilot Delivery Package

**Objective:** Produce the real pilot handoff package for owner/customer execution.

**Controller steps:**
- [ ] Confirm Stage 3 exit gate.
- [ ] Generate or update the pilot handoff package under `.xagent_runtime/reports/`.
- [ ] Include exact version, branch, commit, CI result, staging result, known limitations, rollback, support path, and acceptance checklist.
- [ ] Run the final pilot gate after packaging:
  - `python scripts\commercial_pilot_final_gate.py`
- [ ] Prepare owner-facing message text without sending outbound messages unless owner explicitly requests sending.

**Stage 4 exit gate:**
- Handoff package is complete and internally consistent.
- Pilot final gate is green.
- Known limitations include no GA claim and no full Codex parity claim.
- Owner/customer execution steps are clear.

### Stage 5: GA Commercial Delivery Completion

**Objective:** Close the remaining product, security, operations, and commercial gaps required for full commercial delivery.

**Controller workstreams:**
- Security/compliance: secrets audit, dependency audit, RBAC/tenant isolation, audit log review, data retention, threat model.
- Operations: SLO/SLA, alerting, backup/restore, incident runbook, capacity/performance, cost guardrails.
- Product/commercial: onboarding, admin docs, usage/accounting, support workflow, release notes, customer acceptance.
- Engineering quality: full regression suite, remote CI, staging/production parity, migration/rollback proof.
- Claim gate: implement or run a `commercial-ga-final-gate` that explicitly distinguishes GA readiness from controlled pilot readiness.

**Stage 5 exit gate:**
- GA final gate exists and passes.
- Remote CI and staging/prod rehearsal evidence are green.
- Security and ops checklists are complete.
- Commercial docs and support process are complete.
- Only then may the project claim full commercial delivery readiness.

## Verification Matrix By Scope

**Backend BFF/auth scope:**
```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_workbench_bff.py tests/test_lite_mode.py tests/test_security.py::test_workflow_run_ignores_client_tenant_id -q -o addopts=--no-cov --tb=short
```

**Frontend Panda scope:**
```powershell
npm --prefix frontend run type-check
npm --prefix frontend run build
npm --prefix frontend run verify:panda
npm --prefix frontend run report:panda:strict
```

**Commercial pilot gate scope:**
```powershell
python scripts\commercial_delivery_closure_snapshot.py
python scripts\commercial_pilot_final_gate.py
```

**Staged diff hygiene:**
```powershell
git diff --check --cached
git diff --cached --name-status
git diff --cached --stat
```

## Commit Strategy

- Commit Stage 1 boundary decisions separately from feature fixes.
- Commit CI or staging fixes separately with the failing command named in the commit body.
- Do not combine generated reports, environment changes, and product code unless the report is the explicit deliverable.
- Use bounded messages such as:
  - `chore: classify commercial delivery worktree boundary`
  - `fix: align commercial pilot ci gate`
  - `docs: add commercial pilot handoff package`

## Final Reporting Format

At the end of each stage, the controller reports:
- Stage status
- Commands run and result counts
- Files changed/committed
- Remaining blockers
- Next stage entry decision
- Whether any claim is still bounded to controlled commercial pilot
