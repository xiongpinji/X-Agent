# X-Agent Stage 5 GA Gate Parallel Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Advance X-Agent from a controlled commercial pilot boundary toward a stricter Stage 5 GA gate by adding automated claim scanning, a single-SHA evidence index, GA final-gate consumption, verification, and controller reporting.

**Architecture:** Keep the main controller as the only actor that integrates, stages, commits, pushes, and summarizes. Subagents work in same-directory sessions with disjoint write scopes. All gates fail closed and must preserve the current claim boundary: controlled commercial pilot readiness is allowed; GA, production-ready, full commercial delivery, staging-proven, and full Codex parity claims are forbidden until evidence is complete for one immutable SHA.

**Tech Stack:** Python 3.11, uv, pytest, ruff, PowerShell, GitHub REST check-runs, local `.xagent_runtime/reports`, and existing X-Agent commercial pilot/GA gate scripts.

---

## Phase 1: Controller Baseline And Dispatch

**Files:**
- Read: `.xagent_runtime/reports/stage5-*-20260615.md`
- Read: `scripts/commercial_ga_final_gate.py`
- Read: `tests/test_commercial_ga_final_gate.py`
- Write: this plan only

- [ ] Confirm current branch, head SHA, dirty worktree, Stage 4 package, Stage 5 GA gate output, and PR check-run status.
- [ ] Close completed read-only subagents to free concurrency slots.
- [ ] Dispatch independent workers:
  - Claim scanner worker owns `scripts/commercial_claim_scan.py` and `tests/test_commercial_claim_scan.py`.
  - Single-SHA evidence-index worker owns `scripts/commercial_ga_evidence_index.py` and `tests/test_commercial_ga_evidence_index.py`.
- [ ] Main controller owns only final gate integration, review, validation, exact-path staging, commit, push, and remote check verification.

## Phase 2: Claim-Safe Docs Gate

**Files:**
- Create: `scripts/commercial_claim_scan.py`
- Create: `tests/test_commercial_claim_scan.py`
- Generate: `.xagent_runtime/reports/stage5-claim-safe-docs-gate-20260615.json`
- Generate: `.xagent_runtime/reports/stage5-claim-safe-docs-gate-20260615.md`

- [ ] Add a read-only scanner over README, deployment docs, release notes, runbooks, and selected package docs.
- [ ] Block positive unqualified GA/production/full-delivery/full-parity/staging-proven/customer-delivery claims.
- [ ] Allow explicit negative, forbidden-claims, draft, RC, pilot, owner-gated, and blocked contexts.
- [ ] Emit machine-readable JSON and concise Markdown.
- [ ] Verify with temporary-file tests so real dirty docs do not become a brittle fixture.

## Phase 3: Single-SHA GA Evidence Index

**Files:**
- Create: `scripts/commercial_ga_evidence_index.py`
- Create: `tests/test_commercial_ga_evidence_index.py`
- Generate: `.xagent_runtime/reports/stage5-single-sha-evidence-index-20260615.json`
- Generate: `.xagent_runtime/reports/stage5-single-sha-evidence-index-20260615.md`

- [ ] Bind every GA evidence category to a selected SHA.
- [ ] Fail closed when reports are missing, stale, not ready, or bound to a different SHA.
- [ ] Keep pilot evidence usable as history but not as GA proof.
- [ ] Emit missing/mismatched evidence by category.
- [ ] Verify all-missing, SHA-mismatch, all-ready, and real-checkout blocked scenarios.

## Phase 4: GA Final Gate Integration

**Files:**
- Modify: `scripts/commercial_ga_final_gate.py`
- Modify: `tests/test_commercial_ga_final_gate.py`

- [ ] Consume claim-scan and single-SHA index reports when present.
- [ ] Keep missing reports as blockers.
- [ ] Preserve current fail-closed behavior and no-mutation flags.
- [ ] Ensure source claim flags cannot promote pilot evidence to GA.
- [ ] Regenerate `commercial-ga-final-gate.json` and `.md`.

## Phase 5: Verification, Commit, Remote Checks, And Delivery Summary

**Files:**
- Commit only exact code/test paths required for the Stage 5 gate foundation.
- Do not stage `.xagent_runtime` reports unless explicitly requested.

- [ ] Run focused tests for claim scanner, evidence index, GA final gate, and Stage 4 package.
- [ ] Run ruff and py_compile for changed scripts/tests.
- [ ] Run `git diff --check` for exact changed paths.
- [ ] Stage exact paths only; no `git add .`, no cleanup, no revert.
- [ ] Commit and push to `feat/commercial-delivery-v1`.
- [ ] Verify GitHub check-runs for the new head with REST.
- [ ] Rerun Stage 4 package and GA final gate locally.
- [ ] Write controller summary report under `.xagent_runtime/reports/`.

## Acceptance Boundary

Success for this plan means:

- Claim-safe docs and single-SHA evidence index gates exist and are consumed by the GA final gate.
- The GA final gate remains blocked unless all GA evidence exists, is ready, is bound to the selected SHA, and the release worktree boundary is clean.
- The project can still only claim controlled commercial pilot readiness, not GA or production readiness.

This plan does not authorize deploy, tag, release, workflow dispatch, outbound customer messages, secret access, destructive cleanup, broad staging, or owner-approval fabrication.
