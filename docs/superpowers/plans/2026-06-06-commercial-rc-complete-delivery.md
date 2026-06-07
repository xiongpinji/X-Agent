# X-Agent Commercial RC Complete Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the current X-Agent `codex/codex-hermes-gap-closure` branch from a local RC candidate to a directly deployable commercial release candidate with owner-verified external evidence.

**Architecture:** Treat commercial readiness as a gated release system, not a single feature patch. Keep local gates, external owner gates, artifact generation, receipt generation, staging, deployment documentation, and final tag authorization as separate evidence-producing units.

**Tech Stack:** Python 3.11+ / FastAPI / pytest / Typer / React / Vite / Docker Compose / GitHub Actions / Telegram Bot API / GitHub REST API / X-Agent RC gate scripts under `scripts/`.

---

## Current Baseline

As of 2026-06-06, the active long-running objective is to deliver X-Agent as a commercial RC without claiming full Codex/Hermes parity.

Current verified local state:
- Branch: `codex/codex-hermes-gap-closure`
- Final gate status: `ready_with_owner_gates`
- RC candidate: `true`
- Can stage candidate files: `true`
- Can tag RC now: `false`
- Full parity claimed: `false`
- Current source bundle: read from `.xagent_runtime/reports/rc-source-bundle.json`
- Current artifact SHA-256: read from `.xagent_runtime/reports/rc-artifact-integrity-gate.json`
- Current artifact file count: read from `.xagent_runtime/reports/rc-artifact-integrity-gate.json`

The work is complete only when `python scripts\rc_final_gate.py --require-ready-to-tag` exits successfully and the release owner has approved exact-path staging, commit, tag, and deployment.

## Non-Negotiable Release Rules

- Do not use `git add .`.
- Do not stage `.xagent_runtime/` unless the release owner explicitly requests runtime evidence in source control.
- Do not stage `.agents/`, `.codex/`, `AGENTS.md`, Creative Studio files, or unrelated local artifacts unless the release owner explicitly requests them.
- Do not commit, tag, or push without explicit release-owner approval.
- Keep `full_parity_claimed=false` unless a separate product-parity evidence process proves otherwise.
- Treat generated reports as evidence, not source changes.
- Owner-controlled gates must be verified with real configured credentials or test resources; skipped checks do not count as commercial deployment readiness.

## Task 1: Keep Local RC Evidence Fresh

**Files:**
- Read: `.xagent_runtime/reports/rc-final-gate.json`
- Read: `.xagent_runtime/reports/rc-source-bundle.json`
- Read: `.xagent_runtime/reports/rc-artifact-integrity-gate.json`
- Read: `.xagent_runtime/release/x-agent-commercial-rc-receipt.json`
- Modify generated evidence only: `.xagent_runtime/reports/*.json`
- Modify generated artifact only: `.xagent_runtime/release/*`

- [x] **Step 1: Refresh the release receipt after the current artifact was created**

Run:
```powershell
python scripts\rc_release_receipt.py
```

Expected:
```text
RC release receipt status: created
```

- [x] **Step 2: Re-run the final gate**

Run:
```powershell
python scripts\rc_final_gate.py
```

Expected:
```text
RC final gate status: ready_with_owner_gates
```

- [x] **Step 3: Confirm the release decision fields**

Run:
```powershell
@'
import json
from pathlib import Path
root = Path(r"D:\AI编程库\项目库\进行中的项目\X-Agent")
final = json.loads((root / ".xagent_runtime" / "reports" / "rc-final-gate.json").read_text(encoding="utf-8"))
print(final["status"])
print(final["rc_candidate"])
print(final["release_decision"]["can_stage_candidate_files"])
print(final["release_decision"]["can_tag_rc_now"])
print(final["full_parity_claimed"])
'@ | python -
```

Expected:
```text
ready_with_owner_gates
True
True
False
False
```

## Task 2: Complete Provider Owner Gate

**Files:**
- Read: `.xagent_runtime/reports/rc-owner-gate-plan.json`
- Modify generated evidence only: `.xagent_runtime/reports/rc-external-smoke.json`
- Modify generated evidence only: `.xagent_runtime/reports/rc-owner-gate-plan.json`
- Modify generated evidence only: `.xagent_runtime/reports/rc-final-gate.json`

- [ ] **Step 1: Configure exactly one intended provider**

Set one provider in the release-owner shell or secret store:
```powershell
$env:XAGENT_LLM_BACKEND = "openai"
```

If the intended provider is not OpenAI, use one of:
```powershell
$env:XAGENT_LLM_BACKEND = "deepseek"
$env:XAGENT_LLM_BACKEND = "anthropic"
$env:XAGENT_LLM_BACKEND = "ollama"
$env:XAGENT_LLM_BACKEND = "local"
```

- [ ] **Step 2: Run configured provider smoke**

Run:
```powershell
python scripts\rc_external_smoke.py --provider openai --require-configured
```

Replace `openai` with the configured provider when needed.

Expected:
```text
RC external smoke status: passed
```

- [ ] **Step 3: Verify provider evidence**

Run:
```powershell
@'
import json
from pathlib import Path
report = json.loads(Path(".xagent_runtime/reports/rc-external-smoke.json").read_text(encoding="utf-8"))
checks = {check["name"]: check for check in report["checks"]}
provider = checks["provider"]
print(provider["status"])
print(provider.get("details", {}).get("provider"))
print(provider.get("details", {}).get("sentinel"))
'@ | python -
```

Expected:
```text
passed
openai
xagent-rc-ok
```

The provider name may differ if a non-OpenAI provider was selected.

## Task 3: Complete Telegram Owner Gate

**Files:**
- Read: `.xagent_runtime/reports/rc-owner-gate-plan.json`
- Modify generated evidence only: `.xagent_runtime/reports/rc-external-smoke.json`

- [ ] **Step 1: Configure disposable Telegram test resources**

Run in the release-owner shell:
```powershell
$env:XAGENT_TELEGRAM_WEBHOOK_SECRET = "<release-owner-secret-value>"
$env:XAGENT_TELEGRAM_BOT_TOKEN = "<disposable-test-bot-token>"
```

The values must come from the release owner and must not be written to source files or reports.

- [ ] **Step 2: Run Telegram live preflight**

Run:
```powershell
python scripts\rc_external_smoke.py --require-configured --telegram-live-preflight
```

Expected:
```text
RC external smoke status: passed
```

- [ ] **Step 3: Verify Telegram checks**

Run:
```powershell
@'
import json
from pathlib import Path
report = json.loads(Path(".xagent_runtime/reports/rc-external-smoke.json").read_text(encoding="utf-8"))
checks = {check["name"]: check["status"] for check in report["checks"]}
print(checks["telegram_webhook_contract"])
print(checks["telegram_bot_preflight"])
'@ | python -
```

Expected:
```text
passed
passed
```

## Task 4: Complete GitHub Issue-To-PR Owner Gates

**Files:**
- Read: `.xagent_runtime/reports/rc-owner-gate-plan.json`
- Modify generated evidence only: `.xagent_runtime/reports/rc-external-smoke.json`

- [ ] **Step 1: Configure a disposable GitHub issue URL**

Run:
```powershell
$env:XAGENT_GITHUB_TEST_ISSUE_URL = "https://github.com/<owner>/<repo>/issues/<number>"
```

Use a disposable issue created by the release owner.

- [ ] **Step 2: Run dry-run smoke**

Run:
```powershell
python scripts\rc_external_smoke.py --require-configured --github-issue-url $env:XAGENT_GITHUB_TEST_ISSUE_URL
```

Expected:
```text
RC external smoke status: passed
```

- [ ] **Step 3: Configure read-only execute preflight token**

Run:
```powershell
$env:XAGENT_GITHUB_TOKEN = "<release-owner-github-token>"
```

The token must be scoped by the release owner for the disposable repository. The smoke must not push branches, create pull requests, or write comments.

- [ ] **Step 4: Run execute preflight**

Run:
```powershell
python scripts\rc_external_smoke.py --require-configured --github-execute-preflight
```

Expected:
```text
RC external smoke status: passed
```

- [ ] **Step 5: Verify GitHub checks**

Run:
```powershell
@'
import json
from pathlib import Path
report = json.loads(Path(".xagent_runtime/reports/rc-external-smoke.json").read_text(encoding="utf-8"))
checks = {check["name"]: check["status"] for check in report["checks"]}
print(checks["github_issue_to_pr_dry_run"])
print(checks["github_issue_to_pr_execute_preflight"])
'@ | python -
```

Expected:
```text
passed
passed
```

## Task 5: Complete Hosted GitHub Actions Owner Gate

**Files:**
- Read: `.github/workflows/commercial-rc.yml`
- Modify generated evidence only: `.xagent_runtime/reports/rc-external-smoke.json`
- Modify generated evidence only: `.xagent_runtime/reports/rc-owner-gate-plan.json`

- [ ] **Step 1: Trigger hosted Commercial RC Gate**

Run the workflow from GitHub Actions:
```text
.github/workflows/commercial-rc.yml
```

Expected hosted jobs:
```text
commercial-rc-linux
commercial-rc-windows-installer
```

- [ ] **Step 2: Record the successful workflow run URL**

Run:
```powershell
$env:XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL = "https://github.com/<owner>/<repo>/actions/runs/<run-id>"
```

- [ ] **Step 3: Verify hosted Actions run by API preflight**

Run:
```powershell
python scripts\rc_external_smoke.py --require-configured --github-actions-preflight
```

Expected:
```text
RC external smoke status: passed
```

- [ ] **Step 4: Verify hosted Actions check**

Run:
```powershell
@'
import json
from pathlib import Path
report = json.loads(Path(".xagent_runtime/reports/rc-external-smoke.json").read_text(encoding="utf-8"))
checks = {check["name"]: check["status"] for check in report["checks"]}
print(checks["hosted_github_actions_run"])
'@ | python -
```

Expected:
```text
passed
```

## Task 6: Regenerate Final Commercial RC Evidence Chain

**Files:**
- Modify generated evidence only: `.xagent_runtime/reports/*.json`
- Modify generated artifact only: `.xagent_runtime/release/*`

- [ ] **Step 1: Run the full local evidence chain**

Run:
```powershell
python scripts\rc_ci_contract.py
python scripts\rc_release_audit.py
python scripts\rc_staging_plan.py
python scripts\rc_source_bundle.py --create
python scripts\rc_artifact_integrity_gate.py
python scripts\rc_secrets_gate.py
python scripts\rc_supply_chain_gate.py
python scripts\rc_install_release_gate.py
python scripts\rc_owner_gate_plan.py
python scripts\rc_owner_env_template.py
python scripts\rc_owner_gate_checklist.py
python scripts\rc_final_gate.py
python scripts\rc_release_receipt.py
python scripts\rc_evidence_pack.py
python scripts\rc_final_gate.py --require-ready-to-tag
```

Expected final command:
```text
RC final gate status: ready_for_rc_tag
```

- [ ] **Step 2: Run the RC test aggregate**

Run:
```powershell
python -m pytest tests\test_rc_runtime_smoke.py tests\test_rc_external_smoke.py tests\test_docker_compose_env_contract.py tests\test_rc_release_audit.py tests\test_rc_ci_contract.py tests\test_rc_evidence_pack.py tests\test_rc_owner_gate_plan.py tests\test_rc_owner_env_template.py tests\test_rc_owner_gate_checklist.py tests\test_rc_install_release_gate.py tests\test_rc_supply_chain_gate.py tests\test_rc_secrets_gate.py tests\test_rc_artifact_integrity_gate.py tests\test_rc_final_gate.py tests\test_rc_release_receipt.py tests\test_rc_source_bundle.py tests\test_rc_staging_plan.py tests\test_codex_hermes_gap_matrix.py -o addopts= -p no:cov -q
```

Expected:
```text
passed
```

- [ ] **Step 3: Verify release summary**

Run:
```powershell
@'
import json
from pathlib import Path
root = Path(r"D:\AI编程库\项目库\进行中的项目\X-Agent")
final = json.loads((root / ".xagent_runtime" / "reports" / "rc-final-gate.json").read_text(encoding="utf-8"))
artifact = json.loads((root / ".xagent_runtime" / "reports" / "rc-artifact-integrity-gate.json").read_text(encoding="utf-8"))
print(final["status"])
print(final["release_decision"]["can_tag_rc_now"])
print(final["full_parity_claimed"])
print(artifact["artifact_sha256"])
print(artifact["file_count"])
'@ | python -
```

Expected:
```text
ready_for_rc_tag
True
False
<current-artifact-sha256>
<current-artifact-file-count>
```

## Task 7: Prepare Exact-Path Staging Request

**Files:**
- Read: `docs/RC_STAGING_MANIFEST.md`
- Read: `.xagent_runtime/reports/rc-staging-plan.json`
- Do not stage until release owner approves.

- [ ] **Step 1: Inspect staging plan**

Run:
```powershell
Get-Content -LiteralPath ".xagent_runtime\reports\rc-staging-plan.json"
```

Expected:
```text
"status": "planned"
```

- [ ] **Step 2: Confirm no broad staging command exists**

Run:
```powershell
Select-String -LiteralPath ".xagent_runtime\reports\rc-staging-plan.json" -Pattern "git add \."
```

Expected: no output.

- [ ] **Step 3: Check whitespace and status**

Run:
```powershell
git diff --check
git status --short --branch
```

Expected:
```text
## codex/codex-hermes-gap-closure
```

Dirty files may exist, but staging must remain exact-path only.

## Task 8: Release Owner Approval And Tagging

**Files:**
- Read: `.xagent_runtime/reports/rc-final-gate.json`
- Read: `.xagent_runtime/release/x-agent-commercial-rc-receipt.json`
- Read: `.xagent_runtime/release/*.zip.sha256`
- Stage exact source paths only after explicit owner approval.

- [ ] **Step 1: Ask for release-owner approval**

The approval request must include:
```text
final gate status
artifact path
artifact SHA-256
artifact file count
receipt path
remaining risks
exact staging command set
```

- [ ] **Step 2: Stage exact approved paths only**

Run only after approval:
```powershell
git add <approved-path-1> <approved-path-2> <approved-path-n>
```

Do not use:
```powershell
git add .
```

- [ ] **Step 3: Verify staged diff**

Run:
```powershell
git diff --cached --stat
git diff --cached --check
```

Expected: staged files match the approved manifest and whitespace check is clean.

- [ ] **Step 4: Commit only after approval**

Run only after approval:
```powershell
git commit -m "feat: prepare X-Agent commercial RC"
```

- [ ] **Step 5: Tag only after `ready_for_rc_tag`**

Run only after final owner approval:
```powershell
git tag -a commercial-rc-YYYYMMDD -m "X-Agent commercial RC YYYY-MM-DD"
```

## Completion Definition

The long-running commercial delivery task is complete only when all of these are true:

- `python scripts\rc_final_gate.py --require-ready-to-tag` succeeds.
- `rc-final-gate.json` reports `status=ready_for_rc_tag`.
- `release_decision.can_tag_rc_now=true`.
- `full_parity_claimed=false`.
- Provider, Telegram, GitHub issue-to-PR dry-run, GitHub execute preflight, and hosted GitHub Actions owner gates are all `passed`.
- Release owner approves exact-path staging.
- Staged diff is clean and reviewed.
- Release commit and RC tag are created only after approval.
- Production secrets are generated and stored outside the repo.
- Deployment runbook, install quickstart, release notes, staging manifest, release receipt, and artifact checksum are available to the release owner.
