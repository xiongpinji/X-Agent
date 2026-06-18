# X-Agent Stage5 Blocked Evidence Template Generators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local read-only generators for blocked Stage5 evidence templates so owners and environment operators can collect missing GA evidence without any agent fabricating proof.

**Architecture:** Each generator owns one Stage5 evidence domain and writes blocked JSON skeletons only when explicitly invoked. Generators must not overwrite existing real evidence unless `--force` is supplied, and every payload must state `template_not_evidence=true`, `real_evidence_collected=false`, `mutation_performed=false`, `deploy_performed=false`, and `owner_approval_created=false`.

**Tech Stack:** Python 3.11, dataclasses, argparse, pathlib, JSON/Markdown report files, existing commercial Stage5 gate specs, pytest via `uv run --isolated --python 3.11`.

---

## Global Rules

- Do not stage, commit, push, tag, deploy, workflow-dispatch, delete, move, or clean files.
- Do not edit owner approval artifacts or secrets.
- Do not modify existing Stage5 gates unless the assigned task explicitly says so.
- Template output is not evidence and must keep downstream gates blocked until replaced with real ready evidence.

## Task 1: Artifact Evidence Templates

**Files:**
- Create: `scripts/commercial_stage5_artifact_evidence_templates.py`
- Create: `tests/test_commercial_stage5_artifact_evidence_templates.py`
- Write report: `.xagent_runtime/reports/controller-stage5-artifact-templates-worker-20260615.json`
- Write report: `.xagent_runtime/reports/controller-stage5-artifact-templates-worker-20260615.md`

- [ ] **Step 1: Implement generator**

Generator must expose `build_template_payloads(report_dir, current_head_sha=None, release_sha=None)`, `write_templates(...)`, `write_report(...)`, `write_markdown_report(...)`, and a CLI.

It must generate blocked skeletons for:

```text
stage5-image-digests-20260615.json
stage5-sbom-20260615.json
stage5-helm-package-20260615.json
```

Each skeleton must include domain-specific placeholders, expected ready statuses, and a required owner/operator action list.

- [ ] **Step 2: Add tests**

Tests must use `tmp_path` and verify:

```text
payloads are blocked templates, not evidence
write_templates creates all three files
existing files are not overwritten without force
force overwrites template files
artifact release gate still blocks with generated templates
CLI writes JSON/MD summary into tmp_path
```

- [ ] **Step 3: Validate**

Run:

```powershell
uv run --isolated --python 3.11 pytest tests/test_commercial_stage5_artifact_evidence_templates.py tests/test_commercial_artifacts_release_gate.py tests/test_commercial_stage5_artifact_evidence_pack.py -q -o addopts=--no-cov --tb=short
```

## Task 2: Performance Evidence Templates

**Files:**
- Create: `scripts/commercial_stage5_performance_evidence_templates.py`
- Create: `tests/test_commercial_stage5_performance_evidence_templates.py`
- Write report: `.xagent_runtime/reports/controller-stage5-performance-templates-worker-20260615.json`
- Write report: `.xagent_runtime/reports/controller-stage5-performance-templates-worker-20260615.md`

- [ ] **Step 1: Implement generator**

Generator must use the existing performance evidence names from `commercial_performance_capacity_gate.default_required_evidence`.

It must generate blocked skeletons for:

```text
stage5-load-performance-result-20260615.json
stage5-capacity-target-20260615.json
stage5-latency-error-thresholds-20260615.json
stage5-cost-guardrail-20260615.json
stage5-performance-tests-skipped-disposition-20260615.json
stage5-resource-sizing-20260615.json
```

- [ ] **Step 2: Add tests**

Tests must prove templates are blocked, non-overwriting by default, force-overwritable, and still blocked by `build_performance_capacity_gate`.

- [ ] **Step 3: Validate**

Run:

```powershell
uv run --isolated --python 3.11 pytest tests/test_commercial_stage5_performance_evidence_templates.py tests/test_commercial_performance_capacity_gate.py tests/test_commercial_stage5_performance_evidence_pack.py -q -o addopts=--no-cov --tb=short
```

## Task 3: Ops/Support Evidence Templates

**Files:**
- Create: `scripts/commercial_stage5_ops_support_evidence_templates.py`
- Create: `tests/test_commercial_stage5_ops_support_evidence_templates.py`
- Write report: `.xagent_runtime/reports/controller-stage5-ops-support-templates-worker-20260615.json`
- Write report: `.xagent_runtime/reports/controller-stage5-ops-support-templates-worker-20260615.md`

- [ ] **Step 1: Implement generator**

Generator must use the existing ops evidence names from `commercial_ops_support_gate.default_required_evidence`.

It must generate blocked skeletons for:

```text
stage5-slo-sla-evidence-20260615.json
stage5-alert-routing-evidence-20260615.json
stage5-backup-restore-rehearsal-20260615.json
stage5-incident-process-evidence-20260615.json
stage5-support-escalation-evidence-20260615.json
stage5-cost-capacity-guardrails-20260615.json
stage5-on-call-ownership-evidence-20260615.json
```

- [ ] **Step 2: Add tests**

Tests must prove templates are blocked, non-overwriting by default, force-overwritable, and still blocked by `build_ops_support_gate`.

- [ ] **Step 3: Validate**

Run:

```powershell
uv run --isolated --python 3.11 pytest tests/test_commercial_stage5_ops_support_evidence_templates.py tests/test_commercial_ops_support_gate.py tests/test_commercial_stage5_ops_evidence_pack.py -q -o addopts=--no-cov --tb=short
```

## Task 4: Production Rehearsal Evidence Templates

**Files:**
- Create: `scripts/commercial_stage5_production_rehearsal_evidence_templates.py`
- Create: `tests/test_commercial_stage5_production_rehearsal_evidence_templates.py`
- Write report: `.xagent_runtime/reports/controller-stage5-production-rehearsal-templates-worker-20260615.json`
- Write report: `.xagent_runtime/reports/controller-stage5-production-rehearsal-templates-worker-20260615.md`

- [ ] **Step 1: Implement generator**

Generator must use `commercial_environment_rehearsal_gate.default_evidence_specs("production")`.

It must generate blocked skeletons for:

```text
stage5-production-deploy-rehearsal-20260615.json
stage5-production-smoke-tests-20260615.json
stage5-production-rollback-rehearsal-20260615.json
stage5-production-observability-20260615.json
stage5-production-release-approval-20260615.json
```

- [ ] **Step 2: Add tests**

Tests must prove templates are blocked, non-overwriting by default, force-overwritable, and still blocked by `build_environment_rehearsal_report("production")`.

- [ ] **Step 3: Validate**

Run:

```powershell
uv run --isolated --python 3.11 pytest tests/test_commercial_stage5_production_rehearsal_evidence_templates.py tests/test_commercial_environment_rehearsal_gate.py -q -o addopts=--no-cov --tb=short
```

## Coordinator Verification

- [ ] Parse all four worker reports.
- [ ] Run all four focused test commands.
- [ ] Run `git diff --cached --name-only` and confirm it is empty.
- [ ] Run `python scripts\commercial_delivery_closure_snapshot.py`.
- [ ] Write refreshed controller summary after worker results.
