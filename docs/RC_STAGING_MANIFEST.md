# X-Agent RC Staging Manifest

Last updated: 2026-06-06

This manifest defines the candidate release files for the current
`codex/codex-hermes-gap-closure` branch. It is a source-control guard: stage
only explicit paths after review, never `git add .`.

## Always Exclude Unless Owner Explicitly Approves

These paths are local agent configuration, project instructions, or broad
analysis artifacts that should not be bundled into the commercial RC commit
without a separate owner decision:

- `.agents/`
- `.codex/`
- `AGENTS.md`
- `COMPETITIVE_ANALYSIS_2026.md`
- `backend/app/api/creative_studio.py`
- `backend/app/core/creative_studio/`
- `docs/01-项目规划/05-Creative-Studio短剧成片工作流.md`
- `tests/test_creative_studio.py`

## Tracked Modified Candidate Files

These tracked files are part of the current Codex/Hermes gap-closure delivery
surface and require final review before staging:

```text
RELEASE_READINESS.md
pyproject.toml
requirements-lock.txt
backend/app/api/feishu.py
backend/app/api/workbench.py
backend/app/api/workflows.py
backend/app/core/channels/__init__.py
backend/app/core/channels/base.py
backend/app/core/channels/telegram_adapter.py
backend/app/core/config/settings.py
backend/app/core/feishu_bridge.py
backend/app/core/org.py
backend/app/core/pipelines/issue_to_pr.py
backend/app/core/sandbox/docker_sandbox.py
backend/app/main.py
cli/commands/__init__.py
cli/main.py
docker-compose.yml
frontend/package.json
frontend/src/components/AnalyticsDashboard.tsx
frontend/src/pages/ChatPage.tsx
frontend/src/pages/ToolsPage.tsx
frontend/src/services/api.ts
frontend/src/utils/pwaManager.ts
frontend/tsconfig.json
frontend/vite.config.ts
tests/test_docker_sandbox.py
tests/test_issue_to_pr_pipeline.py
tests/test_security.py
```

Special review note:

- `backend/app/core/security.py`, `backend/app/core/tools.py`, and
  `backend/app/main.py` are intentionally not in the current staging set unless
  they become dirty again. Re-run `scripts/rc_release_audit.py` before staging;
  it fails if this manifest contains files outside the current candidate diff.

## New Candidate Files

These untracked files are candidate release additions for the current delivery:

```text
.github/workflows/commercial-rc.yml
RELEASE_NOTES.md
backend/app/api/channels.py
backend/app/api/issue_to_pr.py
backend/app/api/skill_curator.py
backend/app/core/channels/gateway.py
backend/app/core/channels/router.py
backend/app/core/skill_curator/__init__.py
backend/app/core/skill_curator/evidence.py
backend/app/core/skill_curator/models.py
backend/app/core/skill_curator/planner.py
backend/app/core/skill_curator/scoring.py
backend/app/core/skill_curator/writer.py
cli/commands/gateway_cmd.py
cli/commands/github_cmd.py
docs/CODEX_HERMES_GAP_CLOSURE_REPORT.md
docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md
docs/GATEWAY_MODE.md
docs/IDE_EXTENSION_ROADMAP.md
docs/INSTALL_QUICKSTART.md
docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md
docs/RC_RELEASE_DIFF_REVIEW.md
docs/RC_STAGING_MANIFEST.md
docs/SKILL_CURATOR_MVP.md
docs/specs/vscode-extension-mvp.md
docs/superpowers/plans/2026-06-05-codex-hermes-gap-closure.md
docs/superpowers/plans/2026-06-06-commercial-rc-complete-delivery.md
frontend/package-lock.json
frontend/src/vite-env.d.ts
frontend/tsconfig.node.json
scripts/codex_hermes_gap_matrix.py
scripts/install-xagent.ps1
scripts/install-xagent.sh
scripts/rc_external_smoke.py
scripts/rc_final_gate.py
scripts/rc_ci_contract.py
scripts/rc_deployment_docs_gate.py
scripts/rc_evidence_pack.py
scripts/rc_owner_gate_plan.py
scripts/rc_owner_gate_runner.py
scripts/rc_owner_handoff_gate.py
scripts/rc_owner_gate_checklist.py
scripts/rc_owner_env_template.py
scripts/rc_install_release_gate.py
scripts/rc_single_user_local_gate.py
scripts/rc_supply_chain_gate.py
scripts/rc_secrets_gate.py
scripts/rc_artifact_integrity_gate.py
scripts/rc_release_audit.py
scripts/rc_release_diff_review_gate.py
scripts/rc_release_receipt.py
scripts/rc_refresh_release_chain.py
scripts/rc_runtime_smoke.py
scripts/rc_source_bundle.py
scripts/rc_staging_plan.py
scripts/xagent_doctor.py
tests/test_channel_router.py
tests/test_chat_entrypoint_contract.py
tests/test_cli_github.py
tests/test_codex_hermes_gap_matrix.py
tests/test_docker_compose_env_contract.py
tests/test_gateway_mode.py
tests/test_issue_to_pr_api.py
tests/test_rc_runtime_smoke.py
tests/test_rc_external_smoke.py
tests/test_rc_final_gate.py
tests/test_rc_ci_contract.py
tests/test_rc_evidence_pack.py
tests/test_rc_owner_gate_plan.py
tests/test_rc_owner_gate_runner.py
tests/test_rc_owner_handoff_gate.py
tests/test_rc_owner_gate_checklist.py
tests/test_rc_owner_env_template.py
tests/test_rc_install_release_gate.py
tests/test_rc_single_user_local_gate.py
tests/test_rc_supply_chain_gate.py
tests/test_rc_secrets_gate.py
tests/test_rc_artifact_integrity_gate.py
tests/test_rc_release_audit.py
tests/test_rc_release_diff_review_gate.py
tests/test_rc_deployment_docs_gate.py
tests/test_rc_release_receipt.py
tests/test_rc_refresh_release_chain.py
tests/test_skill_curator_api.py
tests/test_rc_source_bundle.py
tests/test_rc_staging_plan.py
tests/test_skill_curator_models.py
tests/test_skill_curator_scoring.py
tests/test_telegram_channel_api.py
tests/test_xagent_doctor.py
```

## Generated Evidence Not Intended For Git

The following evidence should remain runtime output unless the owner asks to
archive it in source control:

- `.xagent_runtime/reports/codex-hermes-gap-closure.json`
- `.xagent_runtime/reports/rc-external-smoke.json`
- `.xagent_runtime/reports/rc-ci-contract.json`
- `.xagent_runtime/reports/rc-release-diff-review-gate.json`
- `.xagent_runtime/reports/rc-deployment-docs-gate.json`
- `.xagent_runtime/reports/rc-evidence-pack.json`
- `.xagent_runtime/reports/rc-owner-gate-plan.json`
- `.xagent_runtime/reports/rc-owner-gate-runner.json`
- `.xagent_runtime/reports/rc-owner-handoff-gate.json`
- `.xagent_runtime/reports/rc-owner-gate-checklist.json`
- `.xagent_runtime/reports/rc-owner-gate-checklist.md`
- `.xagent_runtime/reports/rc-owner-env-template.json`
- `.xagent_runtime/reports/rc-owner-env-template.env`
- `.xagent_runtime/reports/rc-owner-env-template.ps1`
- `.xagent_runtime/reports/rc-refresh-release-chain.json`
- `.xagent_runtime/reports/rc-install-release-gate.json`
- `.xagent_runtime/reports/rc-single-user-local-gate.json`
- `.xagent_runtime/reports/rc-supply-chain-gate.json`
- `.xagent_runtime/reports/rc-secrets-gate.json`
- `.xagent_runtime/reports/rc-artifact-integrity-gate.json`
- `.xagent_runtime/reports/rc-final-gate.json`
- `.xagent_runtime/reports/rc-release-audit.json`
- `.xagent_runtime/reports/rc-source-bundle.json`
- `.xagent_runtime/reports/rc-staging-plan.json`
- `.xagent_runtime/release/`
- `.xagent_runtime/release/x-agent-commercial-rc-receipt.json`
- `.xagent_runtime/release/x-agent-commercial-rc-evidence-*.zip`
- `.xagent_runtime/release/*.zip.sha256`
- `.xagent_runtime/smoke/rc-runtime-smoke.json`

## Excluded-Area Leakage Guard

The commercial RC excludes Creative Studio until it receives a separate owner
approval and release review. Candidate files must not import, route, or register
excluded Creative Studio modules; `scripts/rc_release_audit.py` fails on those
references so a partial source-control stage cannot produce a broken release.

## Recommended Review Order

1. Security and auth files:
   `backend/app/main.py`, `backend/app/core/security.py`,
   `backend/app/api/workflows.py`, `backend/app/api/skill_curator.py`.
2. External mutation boundaries:
   `backend/app/core/pipelines/issue_to_pr.py`,
   `backend/app/api/issue_to_pr.py`, `cli/commands/github_cmd.py`.
3. Channel and gateway loop:
   `backend/app/api/channels.py`, `backend/app/core/channels/*.py`,
   `cli/commands/gateway_cmd.py`.
4. Frontend and dependency lock:
   `frontend/package.json`, `frontend/package-lock.json`,
   `frontend/src/pages/ChatPage.tsx`, `frontend/tsconfig*.json`.
5. Installer, doctor, reports, and tests:
   `scripts/*.py`, `scripts/install-xagent.*`, `docs/*.md`, `tests/*.py`.

## Staging Rule

After review, stage exact paths only. Do not stage top-level agent config,
runtime outputs, or broad local analysis artifacts.
