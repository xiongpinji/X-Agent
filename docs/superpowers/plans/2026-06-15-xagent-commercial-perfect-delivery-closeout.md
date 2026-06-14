# X-Agent Commercial Perfect Delivery Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the current `feat/commercial-delivery-v1` branch to an evidence-backed commercial pilot delivery state with owner-gated release actions.

**Architecture:** Preserve the verified owner-gated commercial delivery commit as the release-control nucleus, then validate the broader product surface around it: backend contracts, Panda UI/BFF, pilot readiness, deployment/security configuration, documentation, and release handoff. External mutation steps remain gated by explicit target credentials and rollback evidence, even though owner approval for local work is granted.

**Tech Stack:** Python 3.11, pytest, commercial delivery scripts, FastAPI backend, React/Vite/TypeScript Panda UI, npm, git, `.xagent_runtime/reports` evidence receipts.

---

## Delivery Standard

This plan targets **controlled commercial pilot delivery**, not general availability and not full Codex parity. A final handoff may say `commercial pilot delivery ready` only when all local gates below pass and external-only gates are explicitly marked owner-gated with the missing evidence named.

Required pass criteria:

1. Owner-gated commercial closeout commit exists and closure snapshot reports `commercial_delivery_complete`.
2. Backend focused commercial and entrypoint tests pass on this machine.
3. Panda UI/BFF type/build/contract verification passes or reports a precise environment blocker.
4. Commercial pilot readiness chain reports ready or names owner-gated live checks.
5. Deployment/security docs do not claim GA/full parity and list rollback/data-boundary requirements.
6. Final evidence packet records commands, outputs, commit SHA, staged/uncommitted categories, and residual risks.

Forbidden without a separate explicit target:

- Production deploy.
- Tag push.
- Remote push to protected branch.
- Secret insertion into source files.
- Cleanup/delete of unrelated dirty worktree paths.
- Full Codex parity or GA claim.

## Task 1: Commit And Gate Baseline

**Files:**
- Read: `.xagent_runtime/reports/commercial-delivery-closure-snapshot.json`
- Read: `.xagent_runtime/reports/commercial-delivery-owner-commit-packet.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-baseline-20260615.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-baseline-20260615.md`

- [ ] **Step 1: Capture git and closure baseline**

Run:

```powershell
git rev-parse --short HEAD
git status --short --branch
python scripts\commercial_delivery_closure_snapshot.py
```

Expected: closure status is `commercial_delivery_complete`.

- [ ] **Step 2: Write baseline report**

The JSON report must include:

```json
{
  "status": "baseline_ready",
  "commercial_delivery_status": "commercial_delivery_complete",
  "owner_gated_commit_present": true,
  "full_codex_parity_claimed": false
}
```

## Task 2: Backend Verification Matrix

**Files:**
- Read: `pyproject.toml`
- Read: `tests/`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-backend-20260615.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-backend-20260615.md`

- [ ] **Step 1: Run commercial owner focused tests**

Run:

```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_commercial_delivery_owner_approval_handoff.py tests/test_commercial_delivery_owner_approval_payload_audit.py tests/test_commercial_delivery_owner_delivery_packet.py tests/test_commercial_delivery_pre_approval_drift_guard.py tests/test_original_kernel_delivery_manifest.py tests/test_commercial_delivery_owner_stage_execution_plan.py tests/test_commercial_delivery_owner_approval_resume_packet.py tests/test_commercial_delivery_owner_post_approval_operator_checklist.py tests/test_commercial_delivery_closure_snapshot.py -q -o addopts=--no-cov --tb=short
```

Expected: all selected tests pass.

- [ ] **Step 2: Run commercial pilot focused tests**

Run available tests only if the files exist:

```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_first_release_entrypoints.py tests/test_security.py tests/test_workbench*.py tests/test_feishu_channel_api.py tests/test_skill_curator_models.py tests/test_skill_curator_scoring.py tests/test_skill_curator_api.py -q -o addopts=--no-cov --tb=short
```

Expected: pass, or record exact missing files/environment blockers.

## Task 3: Panda UI/BFF Verification Matrix

**Files:**
- Read: `frontend/package.json`
- Read: `frontend/src/panda/`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-panda-20260615.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-panda-20260615.md`

- [ ] **Step 1: Run frontend type/build**

Run:

```powershell
npm --prefix frontend run type-check
npm --prefix frontend run build
```

Expected: both commands exit 0.

- [ ] **Step 2: Run Panda verification scripts**

Run:

```powershell
npm --prefix frontend run verify:panda
npm --prefix frontend run report:panda:strict
npm --prefix frontend run qa:panda:json
```

Expected: pass, or record exact component/BFF blockers.

## Task 4: Commercial Pilot Readiness Chain

**Files:**
- Read: `docs/COMMERCIAL_PILOT_READINESS.md`
- Read: `scripts/commercial_pilot_*.py`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-pilot-20260615.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-pilot-20260615.md`

- [ ] **Step 1: Run pilot readiness scripts**

Run:

```powershell
python scripts\commercial_pilot_channel_readiness.py
python scripts\commercial_pilot_refresh_chain.py
python scripts\commercial_pilot_readiness.py
python scripts\commercial_pilot_final_gate.py
```

Expected: ready or ready-with-owner-gates. Live provider/channel checks may be owner-gated if credentials/network target are absent.

## Task 5: Security, Deployment, And Claims Audit

**Files:**
- Read: `.env.example`
- Read: `DEPLOYMENT.md`
- Read: `docs/COMMERCIAL_PILOT_READINESS.md`
- Read: `docs/current-env-secret-audit.md`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-security-20260615.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-security-20260615.md`

- [ ] **Step 1: Run deployment/security contract tests if present**

Run:

```powershell
uv run --isolated --python 3.11 --extra dev pytest tests/test_deployment_security_contracts.py tests/test_output_redaction.py tests/test_url_safety.py tests/test_policy_risk_analysis.py -q -o addopts=--no-cov --tb=short
```

Expected: all selected tests pass.

- [ ] **Step 2: Scan claims**

Run:

```powershell
rg -n "GA|general availability|full Codex parity|production ready|commercial ready|delivery ready" README.md DEPLOYMENT.md docs -g "*.md"
```

Expected: no unsupported GA/full-parity claim for the current branch. Historical RC claims must be clearly bounded.

## Task 6: Final Evidence Packet

**Files:**
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-final-20260615.json`
- Write: `.xagent_runtime/reports/commercial-perfect-delivery-final-20260615.md`

- [ ] **Step 1: Aggregate evidence**

Read reports from Tasks 1-5 and produce:

```json
{
  "status": "commercial_pilot_delivery_ready",
  "ga_ready": false,
  "full_codex_parity_claimed": false,
  "owner_gated_external_actions": [],
  "passed_commands": [],
  "failed_or_blocked_commands": [],
  "residual_risks": []
}
```

- [ ] **Step 2: Verify final gate**

Run:

```powershell
git status --short --branch
python scripts\commercial_delivery_closure_snapshot.py
```

Expected: local owner-gated closure remains complete; unrelated dirty worktree paths are recorded but not silently staged.
