# X-Agent Full Parallel Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining X-Agent commercial delivery blockers through same-directory parallel sessions while the main coordinator owns dispatch, validation, review, and final readiness reporting.

**Architecture:** Worktree forks are avoided because prior forked worktree setup failed. The closeout uses existing same-directory Codex sessions with strict file ownership. Owner-gated delivery artifacts, dirty-worktree convergence, P0 readiness behavior, Panda/UI+BFF validation, and final claim audit run in separate lanes. No lane may stage, commit, push, tag, deploy, fabricate owner approval, or claim delivery-ready until the closure snapshot reports complete.

**Tech Stack:** PowerShell, git porcelain, Python 3.11, uv, pytest, FastAPI, React/TypeScript Panda frontend, local JSON/Markdown evidence under `.xagent_runtime/reports`, and plan files under `docs/superpowers/plans`.

---

## Current Evidence Baseline

- Branch: `feat/commercial-delivery-v1`.
- HEAD: `c03c9e5f842dc305cfe5980ae17e43bd950d58c0`.
- Current expanded dirty worktree: `631 total`, `108 tracked`, `523 untracked`.
- Current closure snapshot: `commercial_delivery_closure_blocked`.
- `delivery_complete=false`, `owner_gated=true`, `stage_ready=false`, `approval_ready=false`, `stage_execution_ready=false`, `post_stage_ready=false`, `commit_ready=false`.
- Current owner staging surface: `stage_include_count=102`, `owner_stage_command_count=12`.
- Current stage digests:
  - `stage_path_digest=6bc69e96297933ce4bff392ed5437dff2a5f3a71667f8f1a8e543558bd0ff19d`
  - `stage_command_digest=33a70f44d3912e34b7026d4ff24e44f4d5a2f0d9d1516a9b76e4bc94af549533`
  - `expected_stage_path_set_digest=b10127e7db8966648f84dd5e56c036a9c5902ef93aae0d2c66c7c6acafbc6fb6`
- Real owner approval artifact is stale and still reflects an old 6-command surface.
- Owner draft exists but is not real approval evidence: `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.owner-draft-20260614.json`.

## Global Guardrails

- Do not run `git add`, `git commit`, `git push`, `git tag`, deployment, external mutation, or cleanup.
- Do not edit `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.json` unless the owner provides explicit real approval values.
- Do not copy the owner draft into the real approval artifact.
- Do not delete, move, archive, or bulk-clean untracked files.
- Do not use broad staging commands such as `git add .`, `git add -A`, or `git add --all`.
- Do not claim release-ready, delivery-ready, full Codex parity, or commercial completion while `commercial-delivery-closure-snapshot.json` remains blocked.
- If two sessions need the same file, the later session must stop and report a conflict instead of editing.

## Phase Map

### Phase 1: Owner-Gated Delivery Chain

Owner: lane A5 and lane C5.

Exit criteria:
- Real owner approval payload matches the 12-command surface.
- Read-only approval audit and stage approval gate pass.
- Exact 12 stage commands are authorized but not run by agents without owner instruction.
- Closure snapshot remains blocked until actual staging/post-stage/commit proof exists.

### Phase 2: Worktree Convergence

Owner: lane B5.

Exit criteria:
- Every tracked and untracked path is assigned to a batch.
- Each batch has an owner decision: include, exclude, defer, or hold.
- Delivery script batch is kept separate from Panda UI, generated candidates, docs, env/deps, and local runtime data.
- No cleanup or staging occurs.

### Phase 3: Residual P0 Code/Test Closure

Owner: lane R5 and lane C5.

Exit criteria:
- P0-3 readiness packet import baseline stays fixed.
- Behavior contract failures are either fixed in the shared helper or reported as the next minimal patch set.
- Commercial delivery closure snapshot regression remains protected.
- P0-4/P0-5/P0-6/P0-7 evidence stays valid and is not contradicted by new reports.

### Phase 4: UI/BFF Validation and Final Acceptance Matrix

Owner: lane D5, lane E5, lane F5.

Exit criteria:
- Panda/UI+BFF state is validated or explicitly blocked with command output.
- Docs and reports do not overclaim delivery readiness or full Codex parity.
- Final validation matrix records each lane as `passed`, `blocked`, `failed`, `pending`, or `environment_error`.
- Main coordinator signs off only on evidence-backed readiness, not on owner-gated delivery.

## Parallel Lane A5: Owner Approval and Gate Chain

**Assigned same-directory session:** `019ec66d-4661-7be2-84af-89c47c38cd96` (`X-Agent A2 交付门解锁链`)

**Dependency Guardrail:** If C5 modifies any commercial delivery gate script or matching test, A5 must rerun its read-only gate commands after the C5 report exists. If A5 cannot confirm C5 made no code changes or has completed, A5 must record `pending_due_to_c5_write_scope` instead of treating its gate results as final.

**Files:**
- Read: `.xagent_runtime/reports/commercial-delivery-owner-stage-approval-request.json`
- Read: `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.template.json`
- Read: `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.owner-draft-20260614.json`
- Read: `.xagent_runtime/reports/commercial-delivery-owner-stage-approval.json`
- Read: `.xagent_runtime/reports/workflow-a4-owner-approval-draft-packet-20260614.json`
- Read: `.xagent_runtime/reports/workflow-a4-owner-stage-commands-20260614.txt`
- Write: `.xagent_runtime/reports/workflow-a5-owner-gate-chain-20260614.json`
- Write: `.xagent_runtime/reports/workflow-a5-owner-gate-chain-20260614.md`

- [ ] **Step 1: Parse current owner artifacts**

Run:

```powershell
$files = @(
  '.xagent_runtime\reports\commercial-delivery-owner-stage-approval-request.json',
  '.xagent_runtime\reports\commercial-delivery-owner-stage-approval.template.json',
  '.xagent_runtime\reports\commercial-delivery-owner-stage-approval.owner-draft-20260614.json',
  '.xagent_runtime\reports\commercial-delivery-owner-stage-approval.json',
  '.xagent_runtime\reports\workflow-a4-owner-approval-draft-packet-20260614.json'
)
foreach ($file in $files) {
  Get-Content -LiteralPath $file -Raw | ConvertFrom-Json | Out-Null
}
```

Expected: all parse. The real approval remains stale unless the owner has changed it outside this lane.

- [ ] **Step 2: Recompute read-only gate status**

Run:

```powershell
python -c "from scripts.commercial_delivery_owner_approval_payload_audit import build_owner_approval_payload_audit; r=build_owner_approval_payload_audit(); print(r.status); print(r.approval_payload_valid); print(r.ready_for_approval_gate); print([c.name for c in r.checks if c.status!='passed'])"
python -c "from scripts.commercial_delivery_owner_stage_approval_gate import build_owner_stage_approval_gate; r=build_owner_stage_approval_gate(); print(r.status); print(r.stage_allowed); print(r.summary.get('blocking_reasons'))"
```

Expected before real owner action: blocked because the real approval artifact does not match the 12-command surface.

- [ ] **Step 3: Write A5 gate report**

Create the JSON report with:

```json
{
  "report_id": "workflow-a5-owner-gate-chain-20260614",
  "status": "owner_action_required",
  "delivery_ready": false,
  "release_ready": false,
  "mutation_performed": false,
  "real_owner_approval_written": false,
  "git_stage_performed": false,
  "git_commit_performed": false,
  "git_push_performed": false,
  "network_mutation_performed": false,
  "agent_execution_enabled": false,
  "required_owner_action": [
    "Review owner draft.",
    "Replace owner, approval_id, approved_at, and rationale with real owner-provided values.",
    "Copy reviewed payload to the real owner approval path only after real approval."
  ],
  "current_expected_surface": {
    "stage_include_count": 102,
    "owner_stage_command_count": 12,
    "stage_path_digest": "6bc69e96297933ce4bff392ed5437dff2a5f3a71667f8f1a8e543558bd0ff19d",
    "stage_command_digest": "33a70f44d3912e34b7026d4ff24e44f4d5a2f0d9d1516a9b76e4bc94af549533",
    "expected_stage_path_set_digest": "b10127e7db8966648f84dd5e56c036a9c5902ef93aae0d2c66c7c6acafbc6fb6"
  }
}
```

- [ ] **Step 4: Validate A5 report**

Run:

```powershell
Get-Content -LiteralPath '.xagent_runtime\reports\workflow-a5-owner-gate-chain-20260614.json' -Raw | ConvertFrom-Json | Out-Null
```

Expected: parse succeeds. Final lane status is blocked unless owner approval is real and current.

## Parallel Lane B5: Worktree Batch Decision

**Assigned same-directory session:** `019ec66f-1f4e-7c90-98a1-8335df79ddb3` (`X-Agent B2 工作树收敛`)

**Files:**
- Read: `git status --porcelain=v1 -uall`
- Read: `.xagent_runtime/reports/workflow-b4-worktree-batch-decision-20260614.json`
- Write: `.xagent_runtime/reports/workflow-b5-worktree-batch-decision-20260614.json`
- Write: `.xagent_runtime/reports/workflow-b5-worktree-batch-decision-20260614.md`

- [ ] **Step 1: Capture expanded current status**

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

Expected current baseline: `total=631`, `tracked=108`, `untracked=523`. If different, record the new count and timestamp.

- [ ] **Step 2: Classify tracked batches**

Use these batch names and route rules:

```text
delivery_gate_logic_and_scripts: hold until real owner approval and gate readiness
p0_fixes: validate before owner include decision
panda_ui: separate UI batch after frontend validation
backend_database: backend review and focused tests
docs_claims_env_deps: claim/security/dependency review before staging
unknown_tracked: hold
```

- [ ] **Step 3: Classify untracked batches**

Use these batch names and route rules:

```text
agent_tooling_scaffold: exclude by default or separate tooling batch
backend_candidates: candidate review before include
tests_candidates: pair with backend/readiness candidate owners
frontend_candidates: pair with Panda UI owner
docs_reports: claim audit before include
data_runtime_generated: exclude by default
unknown_owner_decision: hold
```

- [ ] **Step 4: Write B5 decision report**

The report must state:

```text
No cleanup executed.
No files staged.
No bulk staging allowed.
Delivery script batch requires real owner approval.
Panda UI must remain a separate batch.
Untracked files require owner decision before release packaging.
```

- [ ] **Step 5: Validate B5 report**

Run:

```powershell
Get-Content -LiteralPath '.xagent_runtime\reports\workflow-b5-worktree-batch-decision-20260614.json' -Raw | ConvertFrom-Json | Out-Null
```

Expected: parse succeeds.

## Parallel Lane C5: Commercial Delivery Script Regression

**Assigned same-directory session:** `019ec66a-5e25-7b43-b357-9c5e2453dff9` (`X-Agent C 商业脚本回归`)

**Dependency Guardrail:** If C5 changes any commercial delivery gate script or matching test, C5 must flag `a5_rerun_required=true` in its report. A5 is the owner of the final gate rerun after such a change; C5 must not claim gate readiness from its own script tests.

**Files:**
- May modify: `scripts/commercial_delivery_closure_snapshot.py`
- May modify: `tests/test_commercial_delivery_closure_snapshot.py`
- May modify only if required by failing focused tests: `scripts/commercial_delivery_owner_approval_handoff.py`, `scripts/commercial_delivery_owner_approval_payload_audit.py`, `scripts/commercial_delivery_owner_delivery_packet.py`, `scripts/commercial_delivery_pre_approval_drift_guard.py`, `scripts/original_kernel_delivery_manifest.py`
- May modify only matching tests: `tests/test_commercial_delivery_*.py`, `tests/test_original_kernel_delivery_manifest.py`
- Write: `.xagent_runtime/reports/workflow-c5-commercial-regression-20260614.json`
- Write: `.xagent_runtime/reports/workflow-c5-commercial-regression-20260614.md`

- [ ] **Step 1: Rerun the known green closure matrix**

Run:

```powershell
uv run --isolated --python 3.11 pytest tests/test_commercial_delivery_closure_snapshot.py tests/test_commercial_delivery_refresh_chain_receipt.py -q -o addopts=--no-cov --tb=short
```

Expected current baseline: `103 passed`.

- [ ] **Step 2: Run the wider commercial scripts matrix**

Run:

```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_commercial_delivery_owner_approval_handoff.py tests/test_commercial_delivery_owner_approval_payload_audit.py tests/test_commercial_delivery_owner_delivery_packet.py tests/test_commercial_delivery_pre_approval_drift_guard.py tests/test_original_kernel_delivery_manifest.py -q -o addopts=--no-cov --tb=short
```

Expected: pass, or fail only with exact code-level issues to fix. Owner-gated blocked status is expected and must not be turned into ready.

- [ ] **Step 3: Verify closure remains blocked**

Run:

```powershell
python scripts\commercial_delivery_closure_snapshot.py
```

Expected: `commercial_delivery_closure_blocked` and `Delivery complete: False`.

- [ ] **Step 4: Write C5 regression report**

Record command, result, files changed, and whether the C4 safety fix still holds.

## Parallel Lane R5: P0-3 Readiness Packet Behavior Contract

**Assigned same-directory session:** `019ec5f6-dc90-7310-b0c9-ff12afb0c383` (`P0-3 readiness drift worker`)

**Files:**
- May modify: `backend/app/core/codex_readiness_packet.py`
- May modify only if needed by shared helper tests: `backend/app/core/_codex_readiness_packet_core.py`, `backend/app/core/_codex_readiness_packet_specs.py`
- May modify matching tests only if the test expectation is demonstrably stale: `tests/test_codex_*_readiness_packet.py`
- Write: `.xagent_runtime/reports/workflow-r5-readiness-packet-contract-20260614.json`
- Write: `.xagent_runtime/reports/workflow-r5-readiness-packet-contract-20260614.md`

- [ ] **Step 1: Confirm import baseline**

Run:

```powershell
$files = Get-ChildItem -LiteralPath tests -Filter 'test_codex_*_readiness_packet.py' | Sort-Object Name | ForEach-Object { $_.FullName }
uv run --isolated --python 3.11 --extra dev pytest $files --collect-only -q -o addopts=--no-cov --tb=short
```

Expected: collection succeeds; no `ModuleNotFoundError` for `backend.app.core.codex_*_readiness_packet`.

- [ ] **Step 2: Measure current behavior failures**

Run:

```powershell
$files = Get-ChildItem -LiteralPath tests -Filter 'test_codex_*_readiness_packet.py' | Sort-Object Name | ForEach-Object { $_.FullName }
uv run --isolated --python 3.11 --extra dev pytest $files -q -o addopts=--no-cov --tb=short
```

Expected before fix: behavior failures remain. Capture first 20 failing node ids and shared assertion themes.

- [ ] **Step 3: Fix only shared helper semantics**

Allowed fixes:

```text
packet missing calculation
status mapping
conditional reference handling
live_attempted recognition
alias fields such as review_findings
dataclass/value normalization
```

Forbidden fixes:

```text
new route wiring
agent loop wiring
frontend wiring
delivery gate changes
broad regeneration that overwrites parallel work
```

- [ ] **Step 4: Verify a representative subset and full packet suite**

Run:

```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_codex_artifact_evidence_index_readiness_packet.py tests/test_codex_background_task_readiness_packet.py tests/test_codex_ci_gate_readiness_packet.py tests/test_codex_code_review_findings_readiness_packet.py -q -o addopts=--no-cov --tb=short
```

Then rerun the full `$files` command from Step 2. If full suite remains red, write the exact remaining failure classes into the R5 report.

## Parallel Lane D5: Panda UI and BFF Validation

**Assigned same-directory session:** `019ec66a-c1e9-7e93-945a-c4360f1acd76` (`X-Agent D UI BFF 融合`)

**Files:**
- May modify: `backend/app/api/workbench.py`
- May modify: `backend/app/core/database.py`
- May modify: `frontend/src/services/api.ts`
- May modify: `frontend/src/panda/**`
- Write: `.xagent_runtime/reports/workflow-d5-ui-bff-validation-20260614.json`
- Write: `.xagent_runtime/reports/workflow-d5-ui-bff-validation-20260614.md`

- [ ] **Step 1: Capture backend-focused validation**

Run relevant backend tests that cover workbench/database changes. If exact tests are not known, first run:

```powershell
rg -n "workbench|database|Panda|panda" tests backend frontend/src/panda
```

Then run the smallest matching backend pytest set.

- [ ] **Step 2: Capture frontend validation**

Run available frontend commands from `frontend/package.json`, preferring:

```powershell
npm run type-check
npm run build
npm run verify:panda
```

If command names differ, read `frontend/package.json` and run the closest type/build/Panda verification commands.

- [ ] **Step 3: Check UI claim boundary**

The report must say whether Panda changes are:

```text
validated_current
blocked_by_frontend_environment
blocked_by_type_or_build_errors
not_delivery_scope
```

Do not claim commercial delivery readiness from UI validation alone.

## Parallel Lane E5: Final Validation Matrix

**Assigned same-directory session:** `019ec66b-27be-7223-8315-91a36711d6ef` (`X-Agent E 最终验收矩阵`)

**Files:**
- Write: `.xagent_runtime/reports/workflow-e5-final-validation-20260614.json`
- Write: `.xagent_runtime/reports/workflow-e5-final-validation-20260614.md`

- [ ] **Step 1: Wait for A5/B5/C5/R5/D5 reports or mark pending**

Read each lane report if present:

```powershell
$reports = @(
  '.xagent_runtime\reports\workflow-a5-owner-gate-chain-20260614.json',
  '.xagent_runtime\reports\workflow-b5-worktree-batch-decision-20260614.json',
  '.xagent_runtime\reports\workflow-c5-commercial-regression-20260614.json',
  '.xagent_runtime\reports\workflow-r5-readiness-packet-contract-20260614.json',
  '.xagent_runtime\reports\workflow-d5-ui-bff-validation-20260614.json',
  '.xagent_runtime\reports\workflow-f5-docs-claim-audit-20260614.json'
)
foreach ($report in $reports) {
  if (Test-Path $report) {
    Get-Content -LiteralPath $report -Raw | ConvertFrom-Json | Out-Null
  }
}
```

Expected: reports that do not yet exist must be recorded as `pending`, including F5. E5 must not present the final matrix as complete while the docs claim audit is missing or still running.

- [ ] **Step 2: Run non-mutating global checks**

Run:

```powershell
git diff --check
git status --porcelain=v1 -uall | Measure-Object | Select-Object -ExpandProperty Count
python scripts\commercial_delivery_closure_snapshot.py
```

Expected: whitespace check passes or reports exact files; status count remains evidence only; closure remains blocked until owner/stage/commit gates are real.

- [ ] **Step 3: Write validation matrix**

Every item must be one of:

```text
passed
blocked
failed
pending
environment_error
```

The matrix must include:

```text
owner approval gate
worktree convergence
commercial script regression
P0-3 readiness packet behavior
P0-4 dependency/test definition
P0-5 current HEAD delivery gate
P0-6 env/secret/config safety
P0-7 runtime-vs-detached claim boundary
Panda UI/BFF validation
docs claim audit
final closure snapshot
```

## Parallel Lane F5: Docs Claim and Release Boundary Audit

**Assigned same-directory session:** `019ec5f7-93cd-7dd0-9a55-a6be833c000d` (`P0-7 runtime/detached boundary worker`)

**Files:**
- May modify: root markdown reports that overclaim readiness.
- May modify: `docs/codex*.md`
- May modify: `docs/original-kernel-secondary-handoff.md` only for claim correction, not queue rewriting.
- Write: `.xagent_runtime/reports/workflow-f5-docs-claim-audit-20260614.json`
- Write: `.xagent_runtime/reports/workflow-f5-docs-claim-audit-20260614.md`

- [ ] **Step 1: Search for overclaims**

Run:

```powershell
rg -n "delivery-ready|release-ready|commercial delivery complete|full Codex parity|100%|ready to ship|可交付|交付完成|完全对标|完整对标" . --glob '!node_modules/**' --glob '!.git/**'
```

- [ ] **Step 2: Classify each hit**

Use:

```text
safe_historical_context
needs_boundary_note
must_fix_overclaim
ignored_generated_runtime_evidence
```

- [ ] **Step 3: Apply minimal wording fixes**

Only change statements that currently imply completed delivery despite the blocked closure snapshot. Prefer a one-paragraph boundary note over rewriting whole documents.

- [ ] **Step 4: Validate docs**

Run:

```powershell
git diff --check -- COMMERCIAL_GAP_AUDIT_20260613.md COMPETITIVE_ANALYSIS_2026.md DELIVERABLES_THREE_SYSTEMS.md README_DELIVERABLES.md docs
```

If a file is untracked and not covered by `git diff --check`, use `git diff --no-index --check -- NUL <file>`.

## Coordinator Acceptance Checklist

- [ ] A5 report exists and does not fabricate real owner approval.
- [ ] B5 report exists and does not clean, move, stage, or delete files.
- [ ] C5 report confirms commercial closure safety and focused regression results.
- [ ] R5 report confirms P0-3 import baseline and behavior contract status.
- [ ] D5 report confirms Panda/UI+BFF current validation status.
- [ ] E5 final matrix parses and uses only accepted statuses.
- [ ] F5 report confirms no active docs overclaim commercial delivery completion.
- [ ] `git diff --check` is run after lane updates.
- [ ] `commercial-delivery-closure-snapshot.json` is checked before any final readiness statement.
- [ ] Final user report separates local code/test readiness from owner-gated delivery readiness.
