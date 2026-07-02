# X-Agent Remaining Blockers Owner Worktree Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the remaining release blockers into owner-executable packets without staging, committing, pushing, or fabricating delivery approval.

**Architecture:** The remaining work is split into two independent report-only lanes. A3 produces the owner delivery-gate unblock packet. B3 produces the live dirty-worktree convergence packet using `git status --porcelain=v1 -uall`. The coordinator validates both packets, refreshes local checks, and keeps the final status non-delivery-ready until the owner gate and worktree are actually resolved.

**Tech Stack:** PowerShell, git porcelain, Python 3.11, uv, pytest, React/TypeScript Panda frontend, `.xagent_runtime/reports` JSON/Markdown evidence.

---

## Global Constraints

- Do not run `git add`, `git commit`, `git push`, tag creation, or deployment.
- Do not edit real owner approval artifacts to make a gate pass.
- Do not claim delivery-ready or release-ready while A delivery gate is blocked or the worktree is dirty.
- Do not delete, move, or clean untracked files without a later explicit owner decision.
- All new evidence for this round must be report-only under `.xagent_runtime/reports/workflow-a3-*`, `.xagent_runtime/reports/workflow-b3-*`, or coordinator summary reports.

## Task 1: A3 Owner Gate Unblock Packet

**Files:**
- Read: `.xagent_runtime/reports/workflow-a-delivery-gate-20260614.json`
- Read: `.xagent_runtime/reports/workflow-a-owner-approval-payload-audit.json`
- Read: `.xagent_runtime/reports/workflow-a-owner-stage-approval-gate.json`
- Read: `.xagent_runtime/reports/workflow-a-owner-stage-execution-plan.json`
- Read: `.xagent_runtime/reports/workflow-a-closure-snapshot.json`
- Create: `.xagent_runtime/reports/workflow-a3-owner-unblock-packet-20260614.json`
- Create: `.xagent_runtime/reports/workflow-a3-owner-unblock-packet-20260614.md`

- [ ] **Step 1: Parse current A receipts**

Run:

```powershell
$files = @(
  '.xagent_runtime\reports\workflow-a-delivery-gate-20260614.json',
  '.xagent_runtime\reports\workflow-a-owner-approval-payload-audit.json',
  '.xagent_runtime\reports\workflow-a-owner-stage-approval-gate.json',
  '.xagent_runtime\reports\workflow-a-owner-stage-execution-plan.json',
  '.xagent_runtime\reports\workflow-a-closure-snapshot.json'
)
foreach ($file in $files) {
  Get-Content -Raw $file | ConvertFrom-Json | Out-Null
}
```

Expected: all JSON parses; delivery gate remains `blocked`.

- [ ] **Step 2: Extract owner mismatch facts**

Record these known current mismatches from the receipts:

```text
approval_owner_stage_command_count=6
expected_owner_stage_command_count=10
approval_stage_path_digest=95bfc445fb8a2c38687722e64f65ab83b9cb1050910d68876dcef2fcd68ecc8e
expected_stage_path_digest=4eb5fe4a33021f1ccf61f80d0a957cfac8361175896af25ea7e2731c3013c1f4
approval_stage_command_digest=1f23cadfc7610378ea3be498a75c75072a029235c72791fd981a6b21bc75e0a9
expected_stage_command_digest=f574145bddb5cee6ed1896daaa28dc67403ec15f71ca160bbb08d3ac57afb217
approval_expected_stage_path_set_digest=a22df35aea9f41e8d5c4ebd5c8348f098c5ff71c5a782000306ae103d7fab9db
expected_stage_path_set_digest=aa442848559f3e79901c59103e490e799b852b45aad53e6b2d7c0035b7d58741
```

- [ ] **Step 3: Write the owner unblock packet**

Create JSON with:

```json
{
  "status": "blocked",
  "delivery_ready": false,
  "owner_artifact_to_fix": ".xagent_runtime/reports/commercial-delivery-owner-stage-approval.json",
  "required_owner_action": "recreate_or_correct_owner_stage_approval_payload",
  "forbidden_until_owner_fix": ["git add", "git commit", "git push", "tag", "delivery-ready claim"]
}
```

Expected: no source files changed.

- [ ] **Step 4: Validate report parse**

Run:

```powershell
Get-Content -Raw '.xagent_runtime\reports\workflow-a3-owner-unblock-packet-20260614.json' | ConvertFrom-Json | Out-Null
```

Expected: parse succeeds.

## Task 2: B3 Live Worktree Convergence Packet

**Files:**
- Read: `git status --porcelain=v1 -uall`
- Read: `.xagent_runtime/reports/workflow-b-worktree-convergence-20260614.json`
- Create: `.xagent_runtime/reports/workflow-b3-live-worktree-convergence-20260614.json`
- Create: `.xagent_runtime/reports/workflow-b3-live-worktree-convergence-20260614.md`

- [ ] **Step 1: Capture live status with expanded untracked files**

Run:

```powershell
$status = git status --porcelain=v1 -uall
$tracked = $status | Where-Object { -not $_.StartsWith('?? ') }
$untracked = $status | Where-Object { $_.StartsWith('?? ') }
"total=$($status.Count) tracked=$($tracked.Count) untracked=$($untracked.Count)"
```

Expected current baseline: approximately `total=628 tracked=106 untracked=522`. If the numbers move, record the new numbers and reason.

- [ ] **Step 2: Classify tracked changes**

Use path prefixes to classify tracked changes into:

```text
p0_fixes
delivery_scripts
panda_ui
backend_database_or_core
docs_claims
whitespace_only
unknown
```

- [ ] **Step 3: Classify untracked changes**

Use top-level path prefixes to classify untracked changes into:

```text
.agents/.codex/.xagent tooling
backend candidates
test candidates
frontend candidates
docs/reports
data/runtime/generated
unknown owner decision
```

- [ ] **Step 4: Write the live convergence packet**

The report must say:

```text
No cleanup executed.
No files staged.
No bulk staging allowed.
A delivery gate must be ready before delivery scripts can be staged.
Panda UI is a separate validated batch.
Untracked files require owner decision before release packaging.
```

- [ ] **Step 5: Validate report parse**

Run:

```powershell
Get-Content -Raw '.xagent_runtime\reports\workflow-b3-live-worktree-convergence-20260614.json' | ConvertFrom-Json | Out-Null
```

Expected: parse succeeds.

## Task 3: Coordinator Acceptance

**Files:**
- Read: A3 and B3 reports
- Read: `.xagent_runtime/reports/workflow-e-final-validation-20260614-233200.json`

- [ ] **Step 1: Parse A3/B3/E reports**

Run:

```powershell
$files = @(
  '.xagent_runtime\reports\workflow-a3-owner-unblock-packet-20260614.json',
  '.xagent_runtime\reports\workflow-b3-live-worktree-convergence-20260614.json',
  '.xagent_runtime\reports\workflow-e-final-validation-20260614-233200.json'
)
foreach ($file in $files) {
  Get-Content -Raw $file | ConvertFrom-Json | Out-Null
}
```

Expected: parse succeeds.

- [ ] **Step 2: Rerun non-mutating checks**

Run:

```powershell
git diff --check
```

Expected: exit 0, CRLF/LF warnings are acceptable.

- [ ] **Step 3: Final status**

Final status must remain:

```text
delivery_ready=false
release_ready=false
blocked_by=owner_stage_approval_payload_and_dirty_worktree
```
