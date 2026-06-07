# X-Agent Commercial RC Diff Review

Last updated: 2026-06-06

Branch: `codex/codex-hermes-gap-closure`

This review covers the current commercial RC candidate file set listed in
`docs/RC_STAGING_MANIFEST.md`. No files have been staged as part of this review.

## Review Outcome

Status: locally acceptable for RC candidate staging after owner review.

Important correction made during review:

- `backend/app/core/security.py` had temporarily added `audit:read` and
  `sandbox:read` to the default `user` role. That widened ordinary-user access
  beyond the existing authorization model, so it was reverted. The first-run
  workbench/chat contract still works through route-local non-production
  principals and does not require broad user audit/sandbox permissions.
- Provider owner gate evidence was corrected from a broad "ready to run" state
  to `action_required` when the latest external smoke contains skipped/failed
  provider diagnostics.
- Owner env templates now prefill only non-secret local/Ollama reproduction
  fields from provider smoke details; secret-bearing fields remain placeholders.

## Reviewed Areas

### Security And Auth

- `backend/app/main.py` adds routers for channels, issue-to-PR, and Skill
  Curator, plus route-local CSRF exemptions only for controlled endpoints:
  workflow-chat bootstrap, issue-to-PR dry-run, and Feishu webhook.
- `/api/v1/channels/telegram/webhook` remains signature-token authenticated and
  is allowed through API-key/CSRF middleware because Feishu cannot provide
  browser CSRF tokens.
- `/api/v1/issue-to-pr/execute` still requires `execute=true`,
  `GITHUB_TOKEN`/`XAGENT_GITHUB_TOKEN`, CSRF protection, and a configured
  executor before real mutation can occur.
- Skill Curator custom `draft_root` is blocked when API-key mode or production
  mode is active.
- `Principal` gains `session_id` and `created_at` contract fields without
  granting anonymous principals scopes.

### External Mutation Boundaries

- GitHub issue-to-PR dry-run produces deterministic branch/PR metadata and
  explicitly performs no repository writes.
- Execute mode returns a readiness response when no backend runner is
  configured, rather than silently performing partial writes.
- CLI `github issue-to-pr` defaults to dry-run and requires a token for execute
  preflight.

### Channel And Gateway Loop

- Feishu channel routing normalizes inbound messages, verifies the Feishu
  secret-token header case-insensitively, dispatches through the existing
  dispatch boundary, and returns a stable receipt.
- Gateway mode remains dry-run by default and reports scheduler degradation when
  no scheduler is configured.

### Sandbox Runtime

- Windows subprocess fallback now prefers Git Bash over the System32 WSL relay,
  converts workspace paths for Git Bash, and terminates timed-out process trees
  with `taskkill /T /F`.

### Frontend And Dependencies

- Vite config was simplified to remove missing compression/visualizer/decorator
  plugins, keeping Vite 6.4.2, `@vitejs/plugin-react` 4.7.0, `terser`, and
  `lightningcss`.
- Frontend `/chat` now consumes the workflow-chat contract and displays run
  status, run id, approval state, and tool-event placeholders.
- `tsconfig.json` is narrowed to the first-run RC surface. This is acceptable
  for the current RC gate but does not prove type health for every legacy
  console module.

### Deployment And Release Gates

- `docker-compose.yml` now passes aligned production-relevant `XAGENT_*`
  variables to API and worker services.
- `.github/workflows/commercial-rc.yml` adds the targeted commercial RC gate:
  frontend audit/type-check/build, doctor, gap matrix, release audit, runtime
  smoke, sequential release evidence refresh, and Windows installer dry-run.
- `scripts/rc_release_audit.py` verifies candidate-file manifest coverage,
  excluded local artifacts, secret-like patterns, excluded references,
  local user/runtime path findings, and file hygiene findings such as NUL
  bytes, UTF-8 decode failures, merge conflict markers, or trailing whitespace.
- `scripts/rc_refresh_release_chain.py` refreshes dependent release reports in
  order so downstream gates do not read half-written upstream JSON.
- `scripts/rc_owner_verified_finalize.py` wraps the owner-verified refresh
  chain for release owners, records only env variable names, and does not
  create git tags or store secret values.
- `scripts/rc_runtime_smoke.py` starts backend + Vite and validates health,
  readiness, `/chat`, workflow-chat, and proxied workbench.

## Evidence

Latest local review evidence:

```powershell
python -m pytest tests/test_rc_runtime_smoke.py tests/test_rc_external_smoke.py tests/test_docker_compose_env_contract.py tests/test_rc_release_audit.py tests/test_rc_release_diff_review_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_ci_contract.py tests/test_rc_evidence_pack.py tests/test_rc_refresh_release_chain.py tests/test_rc_owner_gate_plan.py tests/test_rc_owner_env_template.py tests/test_rc_owner_gate_checklist.py tests/test_rc_install_release_gate.py tests/test_rc_single_user_local_gate.py tests/test_rc_supply_chain_gate.py tests/test_rc_secrets_gate.py tests/test_rc_artifact_integrity_gate.py tests/test_rc_final_gate.py tests/test_rc_release_receipt.py tests/test_rc_source_bundle.py tests/test_rc_staging_plan.py tests/test_codex_hermes_gap_matrix.py -o addopts="" -p no:cov -p no:cacheprovider -q
python scripts\rc_release_audit.py
python scripts\rc_single_user_local_gate.py --require-rc2-handoff
python scripts\rc_refresh_release_chain.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://localhost:11434
python scripts\rc_release_diff_review_gate.py
python scripts\codex_hermes_gap_matrix.py --write-report
python scripts\rc_runtime_smoke.py
npm audit --audit-level=moderate
npm run type-check
npm run build
git diff --check
```

Observed local results:

- RC release gate group: 299 passed.
- Release audit: passed, 121 candidate files, no secret-like findings, no
  manifest unsafe paths, no excluded-area references, no local user/runtime
  path findings, and no file hygiene findings.
- Release diff review gate: passed.
- Gap matrix: passed, 9/9 categories, `full_parity_claimed=false`.
- Runtime smoke: passed.
- Frontend audit/type-check/build: passed.
- Diff whitespace check: clean.
- Provider owner gate: not verified in the current local evidence. The latest
  explicit Ollama attempt uses `qwen2.5:1.5b` at `http://localhost:11434` and is
  skipped with an HTTP 500 model-load failure.

## Explicit Non-Staged / Excluded Files

Do not stage without owner approval:

- `.agents/`
- `.codex/`
- `AGENTS.md`
- `COMPETITIVE_ANALYSIS_2026.md`
- `docs/01-项目规划/05-Creative-Studio短剧成片工作流.md`
- `.xagent_runtime/`

## Remaining Owner Or External Gates

These are not completed by local diff review:

- Owner-generated production secrets and owner approval of secret handling.
- `provider`
- `feishu_webhook_contract`
- `github_issue_to_pr_dry_run`
- `github_issue_to_pr_execute_preflight`
- `hosted_github_actions_commercial_rc`
- Final staging review with `git diff --cached --stat`.
