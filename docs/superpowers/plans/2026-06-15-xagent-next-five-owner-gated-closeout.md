# X-Agent Next Five Owner-Gated Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Advance the next five commercial delivery closeout tasks in order while preserving owner-gated safety and avoiding broad staging.

**Architecture:** The five tasks are sequential gates with parallel-safe preparation lanes. Task 1 prepares the real owner approval decision package. Task 2 reruns read-only approval gates after real approval exists. Task 3 executes exact owner-approved staging only if `stage_allowed=true`. Task 4 performs post-stage verification, commit gate, owner commit packet, delivery packet, closure snapshot, and E5 refresh. Task 5 keeps the dirty worktree batch decisions separate from the delivery gate. Agents may prepare reports in parallel, but mutation gates remain sequential.

**Tech Stack:** PowerShell, git porcelain, Python 3.11, commercial delivery scripts, `.xagent_runtime/reports` JSON/Markdown receipts.

---

## Current Baseline

- Branch: `feat/commercial-delivery-v1`
- HEAD: `c03c9e5f842dc305cfe5980ae17e43bd950d58c0`
- Current expanded status: `635 total / 111 tracked / 524 untracked`
- Current closure: `commercial_delivery_closure_blocked`
- `delivery_complete=false`
- Real approval: stale `6-command`
- Required surface: `12-command`
- `stage_allowed=false`

## Global Guardrails

- Do not run `git add`, `git commit`, `git push`, `git tag`, deploy, cleanup, delete, move, or bulk-stage unless the task explicitly permits it and its gate condition is true.
- Do not edit `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.json` unless real owner-provided values are available.
- Do not copy `.owner-draft-20260614.json` into the real approval path as-is.
- Do not claim `delivery-ready`, `release-ready`, or commercial delivery complete until closure snapshot reports complete.
- Do not use `git add .`, `git add -A`, or `git add --all`.

## Task 1: Owner Approval Decision Package

**Purpose:** Produce the exact owner approval packet that a human owner can approve or reject for the current 12-command surface.

**May write:**
- `.xagent_runtime/reports/workflow-n5-task1-owner-approval-decision-20260615.json`
- `.xagent_runtime/reports/workflow-n5-task1-owner-approval-decision-20260615.md`

**Must read:**
- `.xagent_runtime/reports/workflow-a4-owner-approval-draft-packet-20260614.json`
- `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.owner-draft-20260614.json`
- `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.json`
- `.xagent_runtime/reports/workflow-a4-owner-stage-commands-20260614.txt`

- [ ] **Step 1: Parse owner artifacts**

Run:

```powershell
$files = @(
  '.xagent_runtime\reports\workflow-a4-owner-approval-draft-packet-20260614.json',
  '.xagent_runtime\reports\commercial-delivery-owner-stage-approval.owner-draft-20260614.json',
  '.xagent_runtime\reports\commercial-delivery-owner-stage-approval.json'
)
foreach ($file in $files) {
  Get-Content -LiteralPath $file -Raw | ConvertFrom-Json | Out-Null
}
Get-Content -LiteralPath '.xagent_runtime\reports\workflow-a4-owner-stage-commands-20260614.txt' -Raw
```

Expected: JSON parse succeeds; current real approval is stale 6-command; stage command file has 12 commands.

- [ ] **Step 2: Write decision package**

The package must include:

```json
{
  "status": "owner_action_required",
  "delivery_ready": false,
  "real_owner_approval_written": false,
  "required_owner_decision": "approve_or_reject_12_command_stage_surface",
  "current_required_surface": {
    "stage_include_count": 102,
    "owner_stage_command_count": 12,
    "stage_path_digest": "6bc69e96297933ce4bff392ed5437dff2a5f3a71667f8f1a8e543558bd0ff19d",
    "stage_command_digest": "33a70f44d3912e34b7026d4ff24e44f4d5a2f0d9d1516a9b76e4bc94af549533",
    "expected_stage_path_set_digest": "b10127e7db8966648f84dd5e56c036a9c5902ef93aae0d2c66c7c6acafbc6fb6"
  },
  "forbidden_until_real_owner_approval": [
    "git add",
    "git commit",
    "git push",
    "tag",
    "delivery-ready claim"
  ]
}
```

- [ ] **Step 3: Validate package**

Run:

```powershell
Get-Content -LiteralPath '.xagent_runtime\reports\workflow-n5-task1-owner-approval-decision-20260615.json' -Raw | ConvertFrom-Json | Out-Null
```

Expected: parse succeeds.

## Task 2: Read-Only Approval Gate Rerun

**Purpose:** Rerun approval audit and stage gate only after Task 1 shows whether real owner approval exists.

**May write:**
- `.xagent_runtime/reports/workflow-n5-task2-approval-gate-rerun-20260615.json`
- `.xagent_runtime/reports/workflow-n5-task2-approval-gate-rerun-20260615.md`

- [ ] **Step 1: Probe real approval state**

Run:

```powershell
python -c "from scripts.commercial_delivery_owner_approval_payload_audit import build_owner_approval_payload_audit; r=build_owner_approval_payload_audit(); print(r.status); print(r.approval_payload_valid); print(r.ready_for_approval_gate); print([c.name for c in r.checks if c.status!='passed'])"
python -c "from scripts.commercial_delivery_owner_stage_approval_gate import build_owner_stage_approval_gate; r=build_owner_stage_approval_gate(); print(r.status); print(r.stage_allowed); print(r.summary.get('blocking_reasons'))"
```

Expected before real owner approval: `owner_approval_payload_blocked`, `owner_stage_approval_blocked`, `stage_allowed=false`.

- [ ] **Step 2: Write gate rerun report**

If `stage_allowed=false`, the report must stop the sequence and mark Task 3/4 blocked. If `stage_allowed=true`, it must allow Task 3 exact staging.

## Task 3: Exact Owner-Approved Staging

**Purpose:** Stage exactly the 12 owner-approved paths.

**Gate condition:** Only run this task if Task 2 reports `stage_allowed=true`.

**May run only if gate condition is true:**

```powershell
git add -- 'scripts/original_kernel_delivery_manifest.py'
git add -- 'scripts/commercial_delivery_owner_approval_payload_audit.py'
git add -- 'scripts/commercial_delivery_pre_approval_drift_guard.py'
git add -- 'scripts/commercial_delivery_owner_approval_handoff.py'
git add -- 'scripts/commercial_delivery_owner_delivery_packet.py'
git add -- 'scripts/commercial_delivery_closure_snapshot.py'
git add -- 'tests/test_original_kernel_delivery_manifest.py'
git add -- 'tests/test_commercial_delivery_owner_approval_payload_audit.py'
git add -- 'tests/test_commercial_delivery_pre_approval_drift_guard.py'
git add -- 'tests/test_commercial_delivery_owner_approval_handoff.py'
git add -- 'tests/test_commercial_delivery_owner_delivery_packet.py'
git add -- 'tests/test_commercial_delivery_closure_snapshot.py'
```

**May write:**
- `.xagent_runtime/reports/workflow-n5-task3-exact-staging-20260615.json`
- `.xagent_runtime/reports/workflow-n5-task3-exact-staging-20260615.md`

If the gate is false, write a blocked report and do not run any `git add`.

## Task 4: Post-Stage Verification, Commit Gate, Closure Refresh

**Purpose:** Verify staged paths and refresh delivery receipts after exact staging.

**Gate condition:** Only run this task if Task 3 reports exact staging performed and post-stage path set exists.

**May write:**
- `.xagent_runtime/reports/workflow-n5-task4-post-stage-closure-20260615.json`
- `.xagent_runtime/reports/workflow-n5-task4-post-stage-closure-20260615.md`

If Task 3 is blocked, write a blocked report and do not run commit, push, tag, or deployment.

## Task 5: Worktree Batch Owner Decision Packet

**Purpose:** Keep non-delivery dirty worktree decisions separate from owner-gated delivery scripts.

**May write:**
- `.xagent_runtime/reports/workflow-n5-task5-worktree-owner-decision-20260615.json`
- `.xagent_runtime/reports/workflow-n5-task5-worktree-owner-decision-20260615.md`

- [ ] **Step 1: Capture current expanded status**

Run:

```powershell
$status = git status --porcelain=v1 -uall
$tracked = $status | Where-Object { -not $_.StartsWith('?? ') }
$untracked = $status | Where-Object { $_.StartsWith('?? ') }
[pscustomobject]@{
  total = $status.Count
  tracked = $tracked.Count
  untracked = $untracked.Count
} | ConvertTo-Json
```

- [ ] **Step 2: Write owner decision categories**

Use:

```text
delivery_gate_exact_12_paths
p0_fixes
panda_ui
backend_database
readiness_generated
backend_capability_candidates
tests_candidates
docs_claims
agent_tooling_scaffold
runtime_generated_data
unknown_owner_decision
```

Do not stage or clean any category.

## Coordinator Acceptance

- [ ] Task 1 report exists and does not write real approval.
- [ ] Task 2 report exists and accurately reports `stage_allowed`.
- [ ] Task 3 either exact-staged only after `stage_allowed=true` or wrote blocked report.
- [ ] Task 4 either refreshed post-stage receipts only after Task 3 or wrote blocked report.
- [ ] Task 5 report exists and keeps worktree batch decisions separate from delivery gate.
- [ ] No `git commit`, `git push`, tag, deploy, cleanup, delete, or broad staging occurred.
