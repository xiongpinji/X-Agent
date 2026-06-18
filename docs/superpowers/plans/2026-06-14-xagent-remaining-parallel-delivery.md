# X-Agent Remaining Parallel Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the remaining X-Agent delivery work through bounded parallel sessions while the main coordinator owns verification, conflict review, and final readiness reporting.

**Architecture:** The current checkout is not delivery-ready because the delivery gate is blocked and the worktree is not converged. Work is split into five same-directory sessions with disjoint ownership boundaries: delivery gate, worktree convergence, commercial scripts, UI/BFF fusion, and final validation. No worker may stage, commit, push, tag, fabricate owner approval, or claim delivery-ready status.

**Tech Stack:** Python 3.11, uv, pytest, FastAPI, Typer CLI, React/TypeScript Panda frontend, local `.xagent_runtime/reports` evidence packets.

---

## Global Constraints

- Current branch: `feat/commercial-delivery-v1`.
- Current HEAD: `c03c9e5f842dc305cfe5980ae17e43bd950d58c0`.
- No workflow may run `git add`, `git commit`, `git push`, create tags, deploy, or mutate external systems.
- No workflow may fabricate owner approval, production checks, or delivery-ready receipts.
- Report files under `.xagent_runtime/reports/workflow-*.json` and `.md` are ignored evidence artifacts and must not be treated as staged release content.
- If two workflows need the same source file, the workflow must stop and report the conflict instead of editing.

## Parallel Workflows

### Workflow A: Delivery Gate Unlock Chain

**Thread:** `019ec66d-4661-7be2-84af-89c47c38cd96`

**Files:**
- Write: `.xagent_runtime/reports/workflow-a-delivery-gate-*.json`
- Write: `.xagent_runtime/reports/workflow-a-delivery-gate-*.md`
- Read: `scripts/commercial_delivery_*.py`
- Read: existing `.xagent_runtime/reports/*delivery*`, `*owner*`, `*closure*`

- [ ] **Step 1: Read the current stage 1 blocked report**

Run:

```powershell
Get-Content -LiteralPath '.xagent_runtime\reports\stage1-current-head-delivery-gate-20260614.json' -Raw | ConvertFrom-Json
```

Expected: `delivery_gate_status` is `blocked`.

- [ ] **Step 2: Re-run safe local refresh commands into workflow A outputs**

Run:

```powershell
python scripts\commercial_delivery_owner_approval_payload_audit.py
python scripts\commercial_delivery_owner_stage_approval_gate.py
python scripts\commercial_delivery_owner_stage_execution_plan.py
python scripts\commercial_delivery_owner_approval_resume_packet.py --output .xagent_runtime\reports\workflow-a-owner-approval-resume-packet.json --markdown-output .xagent_runtime\reports\workflow-a-owner-approval-resume-packet.md
python scripts\commercial_delivery_closure_snapshot.py --output .xagent_runtime\reports\workflow-a-closure-snapshot.json --markdown-output .xagent_runtime\reports\workflow-a-closure-snapshot.md
python scripts\commercial_delivery_refresh_chain_receipt.py --dry-run --output .xagent_runtime\reports\workflow-a-refresh-chain.json --markdown-output .xagent_runtime\reports\workflow-a-refresh-chain.md
```

Expected: commands may return blocked; blocked is valid evidence if real owner or staging gates are missing.

- [ ] **Step 3: Write the workflow A summary**

Create `.xagent_runtime/reports/workflow-a-delivery-gate-20260614.json` and `.md` with:

```json
{
  "workflow": "A-delivery-gate",
  "current_head": "c03c9e5f842dc305cfe5980ae17e43bd950d58c0",
  "delivery_gate_status": "blocked-or-ready",
  "blocked_receipts": [],
  "safe_local_refresh_commands": [],
  "owner_required_actions": [],
  "next_minimal_execution_chain": []
}
```

- [ ] **Step 4: Stop at owner boundary**

If any owner gate remains blocked, do not stage files. Return the exact owner action required.

### Workflow B: Worktree Convergence Plan

**Thread:** `019ec66f-1f4e-7c90-98a1-8335df79ddb3`

**Files:**
- Write: `.xagent_runtime/reports/workflow-b-worktree-convergence-*.json`
- Write: `.xagent_runtime/reports/workflow-b-worktree-convergence-*.md`
- Read: `git status --porcelain=v1 -uall`
- Read: `.xagent_runtime/reports/stage2-worktree-ownership-audit-20260614-212646.json`

- [ ] **Step 1: Capture current worktree state**

Run:

```powershell
$status = git status --short
$tracked = $status | Where-Object { -not $_.StartsWith('?? ') }
$untracked = $status | Where-Object { $_.StartsWith('?? ') }
"total=$($status.Count) tracked=$($tracked.Count) untracked=$($untracked.Count)"
```

Expected: counts are evidence only; do not delete, move, stage, or rewrite files.

- [ ] **Step 2: Convert stage 2 categories into staging batches**

Required batch order:

```text
1. p0_fixes
2. codex_readiness_generated
3. delivery_scripts
4. panda_ui
5. backend_capability_candidates
6. docs_reports
7. tooling_agent_scaffold
8. temporary_or_generated_local
9. unknown_owner_decision
```

- [ ] **Step 3: Write the workflow B convergence report**

Create `.xagent_runtime/reports/workflow-b-worktree-convergence-20260614.json` and `.md` with owner, action, validation dependency, and staging eligibility for every category.

### Workflow C: Commercial Delivery Script Regression

**Thread:** `019ec66a-5e25-7b43-b357-9c5e2453dff9`

**Files:**
- May modify: `scripts/commercial_delivery_owner_approval_handoff.py`
- May modify: `scripts/commercial_delivery_owner_approval_payload_audit.py`
- May modify: `scripts/commercial_delivery_owner_delivery_packet.py`
- May modify: `scripts/commercial_delivery_pre_approval_drift_guard.py`
- May modify: `scripts/original_kernel_delivery_manifest.py`
- May modify: `tests/test_commercial_delivery_*.py`
- May modify: `tests/test_original_kernel_delivery_manifest.py`
- Write: `.xagent_runtime/reports/workflow-c-commercial-scripts-*.json`
- Write: `.xagent_runtime/reports/workflow-c-commercial-scripts-*.md`

- [ ] **Step 1: Run focused commercial script tests**

Run:

```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_commercial_delivery_owner_approval_handoff.py tests/test_commercial_delivery_owner_approval_payload_audit.py tests/test_commercial_delivery_owner_delivery_packet.py tests/test_commercial_delivery_pre_approval_drift_guard.py tests/test_original_kernel_delivery_manifest.py -q -o addopts=--no-cov --tb=short
```

Expected: pass or fail with concrete code-level errors.

- [ ] **Step 2: Fix only code-level failures**

If a test fails because a script incorrectly handles current HEAD, JSON parsing, digest comparison, or a blocked receipt state, patch only the owned scripts/tests.

- [ ] **Step 3: Preserve owner gate semantics**

If a test or script fails because owner approval, staging, or commit proof is absent, write the blocked condition into the workflow C report and do not change it to ready.

### Workflow D: UI/BFF Fusion

**Thread:** `019ec66a-c1e9-7e93-945a-c4360f1acd76`

**Files:**
- May modify: `backend/app/api/workbench.py`
- May modify: `backend/app/api/workbench_resources_bff.py`
- May modify: backend tests directly covering workbench control/runtime summaries
- May modify: `frontend/src/services/api.ts`
- May modify: `frontend/src/panda/**` workbench home, types, state, view model, and read-only UI surface
- Write: `.xagent_runtime/reports/workflow-d-ui-bff-fusion-*.json`
- Write: `.xagent_runtime/reports/workflow-d-ui-bff-fusion-*.md`

- [ ] **Step 1: Add read-only backend summaries**

Add `control_summary` from the existing control-mode store and `runtime_capability_summary` from runtime capability manifest. Do not hard-code ready.

- [ ] **Step 2: Add typed frontend fields**

Extend workbench API types and view model with read-only control/runtime summaries. Keep fallbacks explicit and do not add mutation or `execute=true` UI.

- [ ] **Step 3: Render a read-only status surface**

Expose plan/goal loop and runtime capability state without claiming detached candidates are mainline capability.

- [ ] **Step 4: Verify**

Run:

```powershell
uv run --isolated --python 3.11 pytest tests/test_control_modes.py tests/test_control_modes_api.py tests/test_control_cli.py -q -o addopts=--no-cov
```

If frontend dependencies are available, run:

```powershell
npm run type-check
npm run build
npm run verify:panda
```

### Workflow E: Final Validation Matrix

**Thread:** `019ec66b-27be-7223-8315-91a36711d6ef`

**Files:**
- Write: `.xagent_runtime/reports/workflow-e-final-validation-*.json`
- Write: `.xagent_runtime/reports/workflow-e-final-validation-*.md`

- [ ] **Step 1: Run independent stable tests**

Run:

```powershell
$files = Get-ChildItem -LiteralPath 'tests' -Filter 'test_codex_*readiness_packet.py' | Sort-Object Name | ForEach-Object { $_.FullName }
uv run --isolated --python 3.11 --extra dev pytest @files -q -o addopts=--no-cov --tb=short
uv run --python 3.11 --extra dev --extra cli pytest tests/test_observability.py tests/test_agent_loop.py -q -o addopts=--no-cov --tb=short
uv run --isolated --python 3.11 --extra dev pytest tests/test_lite_mode.py -q -o addopts=--no-cov --tb=short
uv run --isolated --python 3.11 pytest tests/test_runtime_capability_manifest.py -q -o addopts=--no-cov
uv run --isolated --python 3.11 pytest tests/test_control_modes.py tests/test_control_modes_api.py tests/test_control_cli.py -q -o addopts=--no-cov
```

- [ ] **Step 2: Mark dependent tests pending until C/D finish**

Do not run or pass the commercial and frontend final items until workflows C and D return.

- [ ] **Step 3: Run static checks**

Run:

```powershell
git diff --check
```

Parse workflow JSON reports with `ConvertFrom-Json`.

- [ ] **Step 4: Write validation matrix report**

Every item must be one of:

```text
passed
failed
pending
environment_error
blocked
```

## Main Coordinator Review Gates

- [ ] All workflow report JSON files parse.
- [ ] No workflow writes outside its declared boundary.
- [ ] C and D code changes, if any, receive focused verification and review.
- [ ] E matrix is rerun after C/D complete.
- [ ] Stage 1 delivery gate is not marked ready unless closure snapshot is complete and owner gates are real.
- [ ] Final response separates code/test readiness from delivery readiness.
