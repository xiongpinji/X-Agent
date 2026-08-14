# RC Staging Manifest

Release candidate staging manifest for X-Agent commercial release process.

Post-commit full-payload manifest: lists the complete commercial RC file set
(already-committed payload plus the current pending fixes). Stage only explicit
paths after owner review; never `git add .`.

## Tracked Modified Candidate Files

```text
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
docs/RC_STAGING_MANIFEST.md
docs/operations/deployment/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md
docs/operations/deployment/RC_RELEASE_DIFF_REVIEW.md
docs/operations/deployment/RELEASE_READINESS.md
frontend/package.json
frontend/src/components/AnalyticsDashboard.tsx
frontend/src/pages/ChatPage.tsx
frontend/src/pages/ToolsPage.tsx
frontend/src/services/api.ts
frontend/src/utils/pwaManager.ts
frontend/tsconfig.json
frontend/vite.config.ts
pyproject.toml
requirements-lock.txt
scripts/codex_hermes_gap_matrix.py
tests/test_docker_sandbox.py
tests/test_issue_to_pr_pipeline.py
tests/test_security.py
```

## New Candidate Files

```text
.github/workflows/commercial-rc.yml
archive/process_docs_2026-07-19/RELEASE_NOTES.md
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
docs/concepts/architecture/GATEWAY_MODE.md
docs/concepts/planning/IDE_EXTENSION_ROADMAP.md
docs/developer/plugins/SKILL_CURATOR_MVP.md
docs/developer/reports/CODEX_HERMES_GAP_CLOSURE_REPORT.md
docs/developer/specs/vscode-extension-mvp.md
docs/operations/deployment/COMMERCIAL_DEPLOYMENT_RUNBOOK.md
docs/operations/setup/INSTALL_QUICKSTART.md
frontend/package-lock.json
frontend/src/vite-env.d.ts
frontend/tsconfig.node.json
scripts/install-xagent.ps1
scripts/install-xagent.sh
scripts/rc_artifact_integrity_gate.py
scripts/rc_ci_contract.py
scripts/rc_deployment_docs_gate.py
scripts/rc_evidence_pack.py
scripts/rc_external_smoke.py
scripts/rc_final_gate.py
scripts/rc_install_release_gate.py
scripts/rc_owner_env_template.py
scripts/rc_owner_gate_checklist.py
scripts/rc_owner_gate_plan.py
scripts/rc_owner_gate_runner.py
scripts/rc_owner_handoff_gate.py
scripts/rc_refresh_release_chain.py
scripts/rc_release_audit.py
scripts/rc_release_diff_review_gate.py
scripts/rc_release_receipt.py
scripts/rc_runtime_smoke.py
scripts/rc_secrets_gate.py
scripts/rc_source_bundle.py
scripts/rc_staging_plan.py
scripts/rc_supply_chain_gate.py
scripts/xagent_doctor.py
tests/test_channel_router.py
tests/test_chat_entrypoint_contract.py
tests/test_cli_github.py
tests/test_codex_hermes_gap_matrix.py
tests/test_docker_compose_env_contract.py
tests/test_gateway_mode.py
tests/test_issue_to_pr_api.py
tests/test_rc_artifact_integrity_gate.py
tests/test_rc_ci_contract.py
tests/test_rc_deployment_docs_gate.py
tests/test_rc_evidence_pack.py
tests/test_rc_external_smoke.py
tests/test_rc_final_gate.py
tests/test_rc_install_release_gate.py
tests/test_rc_owner_env_template.py
tests/test_rc_owner_gate_checklist.py
tests/test_rc_owner_gate_plan.py
tests/test_rc_owner_gate_runner.py
tests/test_rc_owner_handoff_gate.py
tests/test_rc_refresh_release_chain.py
tests/test_rc_release_audit.py
tests/test_rc_release_diff_review_gate.py
tests/test_rc_release_receipt.py
tests/test_rc_runtime_smoke.py
tests/test_rc_secrets_gate.py
tests/test_rc_source_bundle.py
tests/test_rc_staging_plan.py
tests/test_rc_supply_chain_gate.py
tests/test_skill_curator_api.py
tests/test_skill_curator_models.py
tests/test_skill_curator_scoring.py
tests/test_telegram_channel_api.py
tests/test_xagent_doctor.py
```
