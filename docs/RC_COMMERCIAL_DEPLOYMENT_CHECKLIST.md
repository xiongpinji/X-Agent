# X-Agent Commercial RC Deployment Checklist

Last updated: 2026-06-08

This checklist is the release gate for turning the current
`codex/codex-hermes-gap-closure` branch into a commercial deployment release
candidate. It is intentionally stricter than the Codex/Hermes gap-closure
matrix: repository evidence can show P0 closure, but commercial deployment also
needs security, runtime, CI, documentation, and rollback proof.

## Release Target

- Target: commercial release candidate, not a GA or full competitor-parity claim.
- Product scope: enterprise autonomous-agent framework with web chat/workbench,
  Feishu channel loop, GitHub issue-to-PR dry-run/guarded execute, Skill
  Curator MVP, Gateway dry-run mode, installer, doctor, and IDE roadmap.
- Non-claim: do not claim full Codex or Hermes parity without broader external
  product, production, IDE, ecosystem, and real-provider evidence.
- Machine boundary: do not treat the current checkout as fully commercial-RC
  ready until the owner-verified finalization command passes for the current
  HEAD, the hosted Actions head SHA matches that HEAD, and the selected RC tag
  passes `scripts\rc_tag_consistency_gate.py --require-match`.

## Current Evidence Snapshot

These checks were last verified locally on 2026-06-08:

```powershell
python scripts\codex_hermes_gap_matrix.py --write-report
npm audit --audit-level=moderate
npm run type-check
npm run build
powershell -ExecutionPolicy Bypass -File scripts\install-xagent.ps1 -DryRun
& 'C:\Program Files\Git\bin\bash.exe' scripts/install-xagent.sh --dry-run
python scripts\rc_runtime_smoke.py
python scripts\rc_external_smoke.py
python scripts\rc_release_audit.py
python scripts\rc_owner_verified_finalize.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435 --github-actions-run-url https://github.com/xiongpinji/X-Agent/actions/runs/27105724396 --github-actions-head-sha e0febc0d92ce348503e995c1a0d0bc897f5585df --expected-commit-sha e0febc0d92ce348503e995c1a0d0bc897f5585df
python scripts\rc_tag_consistency_gate.py --expected-commit-sha e0febc0d92ce348503e995c1a0d0bc897f5585df --tag-name x-agent-commercial-rc-20260608-3 --require-match
python scripts\rc_delivery_status.py --expected-commit-sha e0febc0d92ce348503e995c1a0d0bc897f5585df --tag-name x-agent-commercial-rc-20260608-3 --github-actions-run-url https://github.com/xiongpinji/X-Agent/actions/runs/27105724396 --github-actions-head-sha e0febc0d92ce348503e995c1a0d0bc897f5585df
python scripts\rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime\reports\rc-owner-env-template.env
python scripts\xagent_doctor.py --json
git diff --check
python -m pytest tests/test_rc_runtime_smoke.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_external_smoke.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_release_audit.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_ci_contract.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_evidence_pack.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_owner_gate_plan.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_owner_gate_runner.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_owner_handoff_gate.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_owner_env_template.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_owner_gate_checklist.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_delivery_status.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_install_release_gate.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_supply_chain_gate.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_secrets_gate.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_artifact_integrity_gate.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_final_gate.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_release_receipt.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_source_bundle.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_rc_staging_plan.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_docker_compose_env_contract.py -o addopts="" -p no:cov -p no:cacheprovider -q
python -m pytest tests/test_issue_to_pr_pipeline.py tests/test_issue_to_pr_api.py tests/test_cli_github.py -o addopts="" -p no:cov -p no:cacheprovider -q
```

Observed status:

- Gap matrix: 9/9 categories passed; `full_parity_claimed=false`.
- Frontend dependency audit: 0 vulnerabilities.
- Frontend type-check: passed.
- Frontend production build: passed with Vite 6.4.2.
- Windows installer dry-run: passed.
- POSIX installer dry-run: passed under Git Bash; native `bash` on this
  workstation points to an unavailable WSL relay and is not a script failure.
- Installer dry-runs use `npm ci`, not `npm install`, so frontend deployment
  follows the committed `frontend/package-lock.json`.
- RC runtime smoke script: passed; it started backend and Vite frontend,
  validated `/health`, `/ready`, `/chat`, workflow-chat, and the workbench API
  through the frontend proxy.
- RC external smoke script: report generation passed and the provider check is
  verified with Ollama `qwen2.5:1.5b` at `http://127.0.0.1:11435` using the
  ASCII-only model directory `D:\ollama-models`; the sentinel response
  `xagent-rc-ok` was recorded. Feishu, GitHub issue-to-PR, and hosted Actions
  are verified in the owner-controlled RC evidence snapshot.
- RC final gate: the current release commit is
  `e0febc0d92ce348503e995c1a0d0bc897f5585df`, and hosted Commercial RC run
  `https://github.com/xiongpinji/X-Agent/actions/runs/27105724396` completed
  successfully for that same head SHA. The non-destructive RC tag
  `x-agent-commercial-rc-20260608-3` points locally and remotely at that commit
  and passes `scripts\rc_tag_consistency_gate.py --require-match`. Current
  local final gate status remains `ready_with_owner_gates`, and current
  delivery status is `owner_finalize_pending` until owner-controlled Feishu and
  GitHub issue-to-PR environment variables are provided and
  `scripts\rc_owner_verified_finalize.py` passes for that exact commit.
- RC final gate also enforces release receipt freshness: the receipt
  `generated_at` must not be older than the source bundle, artifact integrity,
  owner gate plan, owner handoff gate, `owner_env_template`,
  `owner_gate_checklist`, release diff review, deployment docs, staging plan,
  install, supply-chain, or secrets reports.
- RC final gate also treats `rc-refresh-release-chain.json` as both a local
  gate and an evidence-pack freshness input. If the refresh-chain report changes
  after evidence-pack generation, rerun `rc_release_receipt.py`,
  `rc_evidence_pack.py`, and `rc_final_gate.py --require-ready-to-tag`.
- RC CI contract: validates the local GitHub Actions workflow includes all
  commercial RC commands, artifact uploads, and no broad staging commands.
- RC evidence pack: archives the source zip, `.sha256` sidecar, release
  receipt, reports, and owner handoff files into one runtime handoff zip with a
  secret scan. It also checks that packed owner gate runner evidence carries
  the generated env-file label and variable names only, keeping the owner gate
  path reproducible without storing secret values.
- RC refresh release chain: runs the dependent RC evidence refresh scripts in
  order with
  `python scripts\rc_refresh_release_chain.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435 --owner-verified`,
  so downstream reports do not read half-written or stale upstream JSON and
  owner-controlled Feishu, GitHub, and hosted Actions evidence is refreshed in
  strict `--require-configured` mode before tagging.
- RC owner-verified finalization: wraps the owner-verified refresh chain,
  writes `.xagent_runtime\reports\rc-owner-verified-finalize.json`, records
  only owner env variable names, and reports whether the fixed-point final gate
  is tag-ready without creating a git tag or storing secret values.
- RC delivery status: `scripts\rc_delivery_status.py` reads current HEAD,
  remote branch, hosted CI metadata, owner finalize evidence, and the selected
  RC tag consistency report, then writes
  `.xagent_runtime\reports\rc-delivery-status.json`. It returns
  `owner_finalize_pending` until owner-controlled Feishu/GitHub evidence passes
  for the same commit.
- RC refresh release chain bootstrap uses `--allow-missing-evidence-pack` only
  before the first evidence pack exists. Final final gate remains strict:
  `python scripts\rc_final_gate.py --require-ready-to-tag` must consume a
  created `rc-evidence-pack.json` with passing freshness, artifact, secret-scan,
  and local user/runtime path privacy checks.
- RC owner gate plan: records the exact real-resource env vars, commands,
  evidence files, and remaining owner actions needed before RC tagging.
- RC owner gate runner: provides a safe allowlisted way to run one owner gate
  or all owner gates, refresh evidence reports, and fail on missing real
  owner-controlled credentials instead of treating skipped checks as passed.
  Non-dry-run owner gate runs perform an `env_preflight` check and stop before
  launching external smoke when required env groups remain unset.
- RC owner env template: renders owner-gate env placeholder files in JSON,
  `.env`, and PowerShell formats without reading or writing real secret values.
- RC owner gate checklist: renders the owner gate plan into JSON and Markdown
  handoff files without printing or storing secret values, and can fail with
  `--fail-action-required` before final tagging.
- RC owner handoff gate: validates the owner gate plan, env templates,
  checklist Markdown/JSON, evidence references, command tokens, and no-secret
  handoff boundary before release-owner execution.
- RC install/release gate: validates Windows/POSIX installer dry-runs, doctor
  JSON output, source bundle report, and staging plan report.
- RC supply-chain gate: validates Python dependency metadata, frontend lockfile
  consistency, npm audit, Python vulnerability audit evidence from
  `pip-audit`, and CI dependency-install discipline. CI must install the dev
  extra and run `python -m pip show pip-audit` so the audit tool is present
  before `scripts\rc_supply_chain_gate.py` runs.
- RC secrets gate: validates production secret generator fields, minimum
  strength/shape, uniqueness, and release-audit secret-scan status without
  writing generated secret values to runtime reports. It also runs
  `prohibited_secret_artifacts` so real env/key/pem/pfx/p12 files and secret
  directories cannot enter the source bundle.
- RC source bundle artifact: created from the manifest with `--create`; the
  zip is a runtime release artifact and is not intended for source-control
  staging.
- RC artifact integrity gate: validates the created zip exists, has a recorded
  SHA-256, and every archive entry matches the source-bundle report by path,
  size, and SHA-256 with excluded paths blocked. It also scans zip text entries
  for secret-like findings, excluded Creative Studio references, and local
  user/runtime path findings.
- RC release receipt: writes a handoff JSON receipt and `.zip.sha256` sidecar
  under `.xagent_runtime/release/` after the final gate. Its
  `approval_request` section carries final gate status, artifact path/SHA/file
  count, receipt path, remaining risks, and the exact staging command set for
  release-owner review.
- Doctor: pass/warn, with only optional channel/GitHub owner resources missing.
- Diff whitespace check: clean.
- RC aggregate test group: 299 passed.
- RC runtime smoke unit tests: passed.
- Docker Compose environment contract tests: passed.
- GitHub issue-to-PR API/CLI/pipeline tests: passed.
- RC external smoke unit tests: passed.
- RC final gate unit tests: passed.
- RC evidence pack unit tests: passed.
- RC owner env template unit tests: passed.
- RC owner gate checklist unit tests: passed.
- RC secrets gate unit tests: passed.
- RC artifact integrity gate unit tests: passed.
- RC source bundle unit tests: passed.
- RC release receipt unit tests: passed.
- RC staging plan unit tests: passed.

## RC-S0 Source Control Gate

- [x] Current branch identified: `codex/codex-hermes-gap-closure`.
- [x] Dirty worktree inspected before release planning.
- [x] Explicit staging manifest created: `docs/RC_STAGING_MANIFEST.md`.
- [x] Pre-existing dirty files reviewed before staging.
- [x] Generated/local-only files excluded from release commit.
- [x] Excluded Creative Studio files are guarded from partial RC staging.
- [x] Source bundle dry-run is generated from the explicit staging manifest.
- [x] Exact staging command dry-run is generated from the explicit staging
  manifest.
- [x] No `git add .` used.
- [ ] Final staged set reviewed with `git diff --cached --stat`.

## RC-S1 Security And Supply-Chain Gate

- [x] Frontend moderate npm audit findings cleared without force-upgrading to
  Vite 8.
- [x] Skill Curator custom `draft_root` blocked when API-key mode or production
  mode is active.
- [x] Review all new CSRF exemptions against route-local compensating controls.
- [x] Confirm Feishu event callback remains fail-closed without configured signature credentials.
- [x] Confirm GitHub issue-to-PR execute mode requires explicit execute flag,
  token, CSRF, and configured executor.
- [x] Confirm anonymous/global principal has no production scopes.
- [x] Review sandbox fallback behavior on Windows and Linux.
- [x] Run tracked-secret, local user/runtime path, manifest unsafe paths,
  excluded-area reference, and file hygiene scans before staging.
- [x] Run supply-chain gate for Python/Node manifests, lockfile consistency,
  npm audit, Python vulnerability audit evidence via `pip-audit`, and CI
  install discipline. `pyproject.toml` must keep `pip-audit` in the dev extra,
  and CI must verify it with `python -m pip show pip-audit`.
- [x] Add a non-leaking production secrets readiness gate for generated-field,
  strength, uniqueness, tracked-secret scan evidence, and prohibited secret
  artifact paths.
- [ ] Deployment owner generates and stores final production secrets in the
  target secret manager before customer traffic.

## RC-S2 Real Environment Smoke Gate

- [x] Start backend and frontend locally from a clean shell.
- [x] Open `/chat` and verify first-run web loop in browser.
- [x] Run mock-provider smoke with `XAGENT_LLM_BACKEND=mock`.
- [x] Add safe external smoke harness for provider, Feishu, and GitHub
  readiness reports.
- [x] Add machine-readable owner gate execution plan for real provider,
  Feishu, GitHub, and hosted CI acceptance.
- [x] Add a non-secret owner env template renderer for release-owner handoff.
- [x] Add `--env-file` support to `scripts\rc_owner_gate_runner.py` so release
  owners can fill `.xagent_runtime\reports\rc-owner-env-template.env` and load
  only non-placeholder `KEY=value` entries into the allowlisted smoke
  subprocess. The runner rejects env-file variable names that are not declared
  by the current owner gate plan, so shell/runtime controls such as `PATH` or
  `PYTHONPATH` cannot be injected through the handoff template. Scoped
  single-gate runs inject only that gate's required variables into the owner
  smoke subprocess, even when the env file also contains filled variables for
  other owner gates.
- [x] Add a release-owner checklist renderer for owner gates that records only
  env variable names, commands, evidence paths, and missing actions.
- [x] Run one configured real provider smoke for the intended deployment
  backend: OpenAI, Anthropic, DeepSeek, or local model. The provider response
  must contain the `xagent-rc-ok` sentinel recorded by `rc_external_smoke.py`.
  Current local RC evidence uses Ollama at `http://127.0.0.1:11435` with
  `qwen2.5:1.5b` after copying the selected model to the ASCII-only
  `D:\ollama-models` directory. The direct proof command
  `ollama run qwen2.5:1.5b "Reply with exactly: xagent-rc-ok"` returned
  `xagent-rc-ok`, and `rc_external_smoke.py --provider ollama` recorded the
  provider check as passed. Customer deployment may replace this with a stable
  customer provider and rerun the same gate.
  The previous local `http://localhost:11434` Ollama instance still reproduces
  an HTTP 500 model-load failure because its model blob path reaches the loader
  with mojibake from the non-ASCII `D:\AI模型库` directory.
  For local/Ollama smoke, record `XAGENT_OLLAMA_BASE_URL` and
  `XAGENT_OLLAMA_MODEL` in the owner env template so the same model can be
  rerun before tagging. If Ollama returns HTTP 404, verify the base URL is the
  Ollama root endpoint and pull or select an installed model. If it returns
  HTTP 500, inspect Ollama logs and prove `ollama run <model>` works locally.
  When the response mentions `failed to load model` or `llama_model_loader`,
  verify `OLLAMA_MODELS`/model storage points to readable, intact model blobs
  and reinstall or move the selected model before rerunning. On Windows, avoid
  non-ASCII `OLLAMA_MODELS` paths for release smoke providers; use an ASCII
  model directory such as `%USERPROFILE%\.ollama\models` or `D:\ollama-models`,
  restart the Ollama service, and prove `ollama run <model>` works from that
  directory before rerunning the provider gate. If the connection fails, start
  Ollama and confirm `<base-url>/api/generate` is reachable before rerunning
  the provider gate.
- [ ] Verify `feishu_webhook_contract` with Feishu app ID, app secret, and event encrypt key; the smoke must accept valid X-Lark signed callbacks, reject invalid/missing signatures, and perform no outbound Feishu mutation.
- [ ] Verify `github_issue_to_pr_dry_run` with a test issue URL. The scoped
  command `python scripts\rc_owner_gate_runner.py --gate github_issue_to_pr_dry_run`
  must require only `XAGENT_GITHUB_TEST_ISSUE_URL` and must not require
  `XAGENT_GITHUB_TOKEN`. When using the generated env template, add
  `--env-file .xagent_runtime\reports\rc-owner-env-template.env`.
- [ ] Verify `github_issue_to_pr_execute_preflight` with a token-authenticated
  read-only probe against a disposable test issue and repository permission
  probe confirming `read_probe.state=open` and `permissions.push=true` before
  any real customer repository use.
- [ ] Run `hosted_github_actions_commercial_rc` by executing the hosted GitHub
  Actions Commercial RC Gate. Trigger the hosted Commercial RC Gate workflow
  first, then record the successful
  run URL in `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL` and the exact hosted
  run commit in `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA`; the URL value
  must be a GitHub Actions run URL, not a project, commit, or workflow-list URL,
  and the SHA value must be a 40-character hex git commit SHA. Then run
  `--github-actions-preflight` so the read-only Actions run API confirms
  `status=completed`, `conclusion=success`, and `head_sha_verified=true`.
- [ ] Run `refresh_release_chain_owner_verified` after all owner external gates
  pass for the current commit: `python scripts\rc_refresh_release_chain.py
  --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url
  http://127.0.0.1:11435 --owner-verified`. This is the only refresh chain
  mode that can produce tag-ready evidence because it reruns required provider,
  Feishu, GitHub issue-to-PR, and hosted Actions checks without falling back to
  mock or skipped smoke evidence.
- [x] Record external-service limitations and missing tokens in the final report.
- [x] Aggregate local and owner-controlled gates into a final machine-readable
  RC decision report.

## RC-S2 Evidence Notes

Runtime smoke evidence captured on 2026-06-06:

- Backend mock smoke started `uvicorn backend.app.main:app` on
  `http://127.0.0.1:8765`; `/health`, `/ready`, `/chat`, and
  `POST /api/v1/workflows/create/chat` passed.
- Frontend smoke started Vite on `http://127.0.0.1:5174` with
  `VITE_API_URL=http://127.0.0.1:8765`; `/`, `/chat`, Vite dev-client
  injection, and `/api/v1/workbench` proxy passed.
- `scripts/rc_runtime_smoke.py` now reproduces the backend + frontend smoke as
  a single command and writes `.xagent_runtime/smoke/rc-runtime-smoke.json`.
  It falls back to a free port when the requested Vite port is already in use,
  while recording both requested and actual ports in the report.
- Browser visual verification opened Vite `/chat` with Playwright, confirmed
  title/text contained `X-Agent`, and wrote
  `.xagent_runtime/smoke/chat-browser-visual.{json,png}`.
- Smoke reports are runtime artifacts under `.xagent_runtime/smoke/` and are
  not intended for source-control staging.
- `python scripts\rc_external_smoke.py` wrote
  `.xagent_runtime/reports/rc-external-smoke.json`. Provider is verified:
  the current local Ollama attempt uses `qwen2.5:1.5b` at
  `http://127.0.0.1:11435` with `D:\ollama-models` and records
  `sentinel_matched=true`. The owner-verified RC evidence snapshot also records
  Feishu webhook contract, GitHub dry-run, GitHub execute-preflight, and hosted
  Actions as verified. If this command is rerun in a workstation without the
  owner-controlled credentials/test resources, those non-provider checks will
  correctly fall back to skipped/action-required. Execute preflight now requires
  token-authenticated read-only GitHub issue API and repository permission
  probes against the disposable test repository; the repo probe must confirm
  `permissions.push=true`, and the smoke still performs no repository
  mutations.
- Provider smoke is a sentinel check: the selected real backend must return
  content containing `xagent-rc-ok`, and the report records
  `sentinel_matched=true` before the provider owner gate is considered passed.
  For Ollama/local runs, `rc_external_smoke.py` also records actionable
  diagnostics for HTTP 404 model/base-URL problems, HTTP 500 service/model
  generation failures including `OLLAMA_MODELS`/model storage load failures,
  and connection failures to `/api/generate`.
- `scripts/rc_external_smoke.py` now records these external gates in
  `.xagent_runtime/reports/rc-external-smoke.json`. In default mode it reports
  skipped checks for missing tokens/resources; in final release mode run it
  with
  `--require-configured --github-execute-preflight --github-actions-preflight`
  plus the intended provider/test resources.
- `scripts/rc_final_gate.py` reads the gap matrix, release audit, runtime
  smoke, external smoke, owner gate plan, install/release, supply-chain,
  secrets, source bundle, and staging plan reports, then writes
  `.xagent_runtime/reports/rc-final-gate.json`. The last owner-verified
  snapshot reported tag readiness because Feishu, GitHub issue-to-PR, and
  hosted Actions owner resources were verified for its recorded commit. Rerun
  `scripts/rc_owner_verified_finalize.py` for the current HEAD before making
  any current tag-readiness claim.
- `scripts/rc_owner_gate_plan.py` writes
  `.xagent_runtime/reports/rc-owner-gate-plan.json`. Hosted GitHub Actions
  remains an owner gate until `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL`
  records a valid successful commercial RC workflow run URL shaped like
  `https://github.com/<owner>/<repo>/actions/runs/<id>` and
  `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA` records the expected hosted
  run commit SHA as a 40-character hex git commit SHA.
  `rc_external_smoke.py --github-actions-preflight` verifies
  the run via the read-only GitHub Actions API and must record
  `head_sha_verified=true`.
- `scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime\reports\rc-owner-env-template.env` records the exact
  allowlisted preflight sequence in
  `.xagent_runtime/reports/rc-owner-gate-runner.json` without using arbitrary
  commands from the plan, plus the env-template file label and loaded variable
  names only. It also records `missing_env_groups` as variable-name groups so
  release owners can see which owner-controlled credentials or URLs remain
  unset without exposing values. Placeholder values are reported as
  `unresolved_env_names`, and placeholders relevant to the selected gate are
  reported as `owner_gate_unresolved_env_names`; if the runner says
  `Replace owner env template placeholder values`, replace those placeholders
  before rerunning. Release owners can rerun it without `--dry-run` after
  filling the generated template and setting the real Feishu/GitHub/Actions
  variables; non-dry-run execution fails locally at `env_preflight` before
  external smoke if any selected gate's required env groups are still missing.
- `scripts/rc_owner_env_template.py` writes non-secret owner handoff templates
  to `.xagent_runtime/reports/rc-owner-env-template.{json,env,ps1}`. These
  files keep secret values as placeholders while allowing non-secret provider
  reproduction fields, such as local/Ollama model and base URL, to be prefilled
  for release-owner reproduction.
- `scripts/rc_owner_handoff_gate.py` validates that owner handoff reports and
  templates remain internally consistent, include the required Feishu,
  GitHub, and hosted Actions commands, and do not contain secret-like values.
- `scripts/rc_source_bundle.py --create` builds the commercial RC source bundle
  from `docs/RC_STAGING_MANIFEST.md` only and writes
  `.xagent_runtime/reports/rc-source-bundle.json` plus a zip under
  `.xagent_runtime/release/`. The artifact remains outside source control.
- `scripts/rc_artifact_integrity_gate.py` reads the source-bundle report,
  validates the created zip exists, rejects excluded or unsafe archive names,
  verifies every entry's path/size/SHA-256, scans zip text entries for
  secret-like findings, excluded-area references, and local user/runtime path
  findings, and writes
  `.xagent_runtime/reports/rc-artifact-integrity-gate.json`.
- `scripts/rc_release_receipt.py` reads the artifact integrity, final gate,
  source bundle, staging plan, and owner gate reports, then writes
  `.xagent_runtime/release/x-agent-commercial-rc-receipt.json` and a
  `.zip.sha256` sidecar for archive/upload handoff.
- `scripts/rc_evidence_pack.py` creates a separate evidence zip under
  `.xagent_runtime/release/` that includes the release receipt, source artifact,
  `.sha256` sidecar, RC reports, and owner handoff files. It also scans text
  evidence for secret-like values, manifest unsafe paths, and local
  user/runtime path findings before writing a successful report.
- `scripts/rc_staging_plan.py` writes
  `.xagent_runtime/reports/rc-staging-plan.json` with exact `git add -- ...`
  commands split into safe chunks. It does not stage files. The latest dry-run
  planned 125 files across 7 commands, and `git diff --cached --name-only`
  remained empty.

## RC-S1 Evidence Notes

Security and supply-chain evidence captured on 2026-06-06:

- `npm audit --audit-level=moderate`: 0 vulnerabilities.
- `python scripts\rc_supply_chain_gate.py`: passed; Python manifest,
  frontend lockfile, npm audit, Python vulnerability audit evidence via
  `pip-audit`, and CI dependency contract checks passed. The CI contract
  includes `python -m pip show pip-audit` after the editable dev/CLI install.
- `python scripts\rc_artifact_integrity_gate.py`: passed after source bundle
  creation; the artifact SHA-256 is recorded in
  `.xagent_runtime/reports/rc-artifact-integrity-gate.json`.
- `python scripts\rc_release_receipt.py`: created a release receipt and
  `.zip.sha256` sidecar under `.xagent_runtime/release/`. The receipt includes
  `approval_request` so the release owner can review final gate status,
  artifact SHA, remaining risks, and exact staging commands before any
  source-control action.
- `python scripts\xagent_doctor.py --json`: pass/warn; warnings are missing
  optional channel/GitHub owner resources only.
- Secret-pattern scan excluding local agent config and runtime outputs found
  placeholder examples only, not live credentials.
- `python scripts\rc_release_audit.py` now also fails when candidate release
  files import, route, or register excluded Creative Studio modules, include
  local user/runtime path findings, manifest unsafe paths, or contain file
  hygiene findings such as NUL bytes, UTF-8 decode failures, merge conflict
  markers, or trailing whitespace. The latest run passed with 111
  dirty/untracked candidate files, no missing manifest entries, no secret-like
  findings, no excluded-area references, no local user/runtime path findings,
  no manifest unsafe paths, and no file hygiene findings.
- `tests/test_chat_entrypoint_contract.py`,
  `tests/test_issue_to_pr_api.py`, `tests/test_feishu_channel_api.py`, and
  `tests/test_skill_curator_api.py`: 15 passed.
- `tests/test_security.py`: 24 passed.
- `tests/test_docker_sandbox.py`: 13 passed; Windows Git Bash fallback rejects
  the System32 WSL relay, converts workspace paths, and kills timed-out process
  trees.
- `python scripts\rc_secrets_gate.py`: passed; required production secret
  fields are generated with expected shape/length, values are unique, release
  audit has no tracked secret findings, `prohibited_secret_artifacts` passed,
  and the generated values are not written into
  `.xagent_runtime/reports/rc-secrets-gate.json`.
- `scripts/generate_secrets.py --format json`: remains the owner-facing command
  for generating final deployment secrets; actual production secrets must still
  be generated and stored by the deployment owner in the target secret manager.

## RC-S3 Deployment And CI Gate

- [x] `scripts/install-xagent.ps1 -DryRun` passes on Windows.
- [x] `scripts/install-xagent.sh --dry-run` passes on Linux/macOS-compatible
  shell. Verified under Git Bash on Windows.
- [x] `scripts/xagent_doctor.py --json` returns machine-readable output.
- [x] Install/release artifact gate aggregates installer dry-runs, doctor,
  source bundle, and staging plan reports.
- [x] CI job exists or is updated to run the gap matrix, type-check, audit,
  doctor, and targeted pytest groups.
- [x] Local CI workflow contract checker guards the commercial RC workflow from
  drift before hosted GitHub Actions execution.
- [x] Docker Compose production-like environment documents required `XAGENT_*`
  variables.
- [x] Rollback path references existing deployment rollback scripts or a tested
  manual fallback.

## RC-S3 Evidence Notes

Deployment gate evidence captured on 2026-06-06:

- `powershell -ExecutionPolicy Bypass -File scripts\install-xagent.ps1 -DryRun`
  printed the expected venv, editable install, frontend install/type-check, and
  doctor commands without mutating the workstation.
- `scripts/install-xagent.sh --dry-run` passed under
  `C:\Program Files\Git\bin\bash.exe`; `C:\Windows\system32\bash.exe` is an
  unavailable WSL relay on this machine.
- `python scripts\xagent_doctor.py --json` returned `warn` only because optional
  external tokens were not configured: OpenAI, Anthropic, GitHub, and Feishu.
- `npm run build` passed and produced a production Vite build without
  compression errors or empty manual chunks.
- `python scripts\codex_hermes_gap_matrix.py --write-report` passed all 9
  categories. The GitHub issue-to-PR group is intentionally slow in this local
  profile and the full matrix took about 5 minutes 41 seconds.
- `.github/workflows/commercial-rc.yml` now defines a focused commercial RC
  workflow with Linux gap matrix, frontend audit/type-check/build, doctor,
  runtime smoke, external readiness smoke, owner gate execution plan,
  supply-chain gate, secrets readiness gate, source-bundle creation, artifact
  integrity validation, install/release artifact gate, final RC gate, and
  release receipt generation plus Windows installer dry-run jobs.
  `scripts/rc_ci_contract.py`
  validates this workflow contract locally; the hosted workflow evidence is
  recorded in the owner-verified RC snapshot before final RC tagging.
- `docker-compose.yml` now passes production-relevant security, LLM, Langfuse,
  GitHub, and Feishu `XAGENT_*` variables to API/worker services, with
  `tests/test_docker_compose_env_contract.py` covering the contract.
- `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` documents the commercial RC
  deployment flow, required secrets, Compose/K8s rollout, monitoring, rollback,
  and residual RC risks.
- `docs/RC_RELEASE_DIFF_REVIEW.md` records the release-level diff review. During
  review, an ordinary-user `audit:read`/`sandbox:read` scope expansion was found
  and reverted before final validation.

## RC-S4 Documentation And Artifact Gate

- [x] `RELEASE_READINESS.md` links to this commercial RC checklist.
- [x] `docs/INSTALL_QUICKSTART.md` covers one-command setup path.
- [x] Production deployment guide documents required secrets, API-key mode, CORS,
  database, Redis, Qdrant, and LLM backend settings.
- [x] Release notes describe user-facing capability changes and known limits.
- [x] Final acceptance report separates repository readiness from competitor
  parity and market maturity.
- [x] Residual risk list is explicit and dated.

## RC-S5 Final Acceptance Gate

- [x] `python scripts\codex_hermes_gap_matrix.py --write-report` passes.
- [x] `npm audit --audit-level=moderate` returns 0 vulnerabilities.
- [x] `npm run type-check` passes.
- [x] `python scripts\xagent_doctor.py --json` passes or only warns about
  intentionally optional integrations.
- [x] `git diff --check` is clean.
- [ ] Final staged files match `docs/RC_STAGING_MANIFEST.md`.
- [ ] Owner approves any remaining security or secret-handling decisions.
- [ ] Release can be tagged as an RC without including local agent config,
  generated runtime data, or unreviewed secret-bearing files.
