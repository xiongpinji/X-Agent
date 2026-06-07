# X-Agent Commercial RC Release Notes

Date: 2026-06-06
Branch: `codex/codex-hermes-gap-closure`
Status: commercial release candidate, not GA

## Summary

This RC turns the Codex/Hermes P0 gap-closure work into a deployable commercial
candidate. It adds first-run browser entrypoints, channel and GitHub automation
loops, a Skill Curator MVP, installer/doctor tooling, runtime smoke evidence,
CI release gates, and production deployment handoff docs.

## User-Facing Changes

- `/chat` first-run browser entrypoint and workflow-chat creation contract.
- `/api/v1/workbench` bootstrap with tenant, user, agent, session, tools,
  workflow, memory, role-catalog, and UI metadata.
- Feishu signed event callback loop with inbound message-event handling and no outbound mutation in RC smoke coverage.
- GitHub issue-to-PR dry-run and guarded execute surface, including CLI command
  coverage.
- Gateway dry-run/status command surface.
- Skill Curator MVP for deterministic skill scoring, proposal generation, and
  staged draft creation.
- Frontend Vite build/type-check path repaired and pinned to Vite 6.x.

## Deployment And Operations

- Added `scripts/rc_runtime_smoke.py` for repeatable backend + Vite runtime
  smoke checks.
- Added `scripts/rc_external_smoke.py` for safe provider, Feishu, and GitHub
  readiness evidence without default repository mutations.
- Added Feishu owner-gate smoke for X-Lark signed event callbacks so domestic-channel acceptance can prove app credentials and event encrypt-key handling without sending messages.
- Hardened GitHub issue-to-PR execute preflight so final external smoke requires
  a token-authenticated read-only probe against a disposable test issue with
  `read_probe.state=open` before it can clear that owner gate.
- Hardened provider external smoke so real-provider acceptance requires the
  `xagent-rc-ok` sentinel in the model response, not merely non-empty content.
- Added `scripts/rc_final_gate.py` to consolidate gap matrix, release audit,
  runtime smoke, and external readiness into one RC decision report.
- Added `scripts/rc_ci_contract.py` to locally validate the commercial RC
  GitHub Actions workflow contract before hosted CI runs.
- Added `scripts/rc_owner_gate_plan.py` to generate a machine-readable
  real-resource gate handoff for provider, Feishu, GitHub, and hosted CI
  acceptance.
- Added `scripts/rc_owner_gate_runner.py` to execute owner-controlled gates
  through an allowlisted, non-mutating preflight command set and refresh owner
  evidence reports without accepting skipped checks as success.
- Hardened `scripts/rc_owner_gate_runner.py` so non-dry-run owner gate runs
  fail at `env_preflight` before launching external smoke when selected owner
  env groups are still missing.
- Added `scripts/rc_owner_handoff_gate.py` to validate the owner gate handoff
  package before real owner execution, including env templates, checklist
  Markdown/JSON, command tokens, evidence references, and no-secret boundaries.
- Hardened `scripts/rc_owner_gate_plan.py` so skipped or failed provider smoke
  diagnostics are propagated into the provider owner gate as `action_required`
  instead of being reported as merely ready to run.
- Hardened `scripts/rc_owner_env_template.py` so non-secret local/Ollama
  reproduction fields from provider smoke details can be prefilled while
  token-bearing fields remain placeholders.
- Added `scripts/rc_install_release_gate.py` to aggregate installer dry-runs,
  doctor output, source bundle, and staging plan evidence. Installer dry-runs
  require `npm ci`, not `npm install`, so frontend deployment follows the
  committed `frontend/package-lock.json`.
- Added `scripts/rc_supply_chain_gate.py` to validate Python/Node dependency
  manifests, lockfile consistency, npm audit, Python vulnerability audit
  evidence through `pip-audit`, and CI install discipline. The tool is required
  through the `pyproject.toml` dev extra and CI verifies it with
  `python -m pip show pip-audit`.
- Added `scripts/rc_secrets_gate.py` to validate production secret generation
  readiness, uniqueness, release-audit secret scans, and non-leaking evidence
  reports, plus prohibited secret artifact paths in the source bundle.
- Added `scripts/rc_source_bundle.py` to plan or create a manifest-scoped RC
  source bundle without touching the git index.
- Added `scripts/rc_artifact_integrity_gate.py` to verify the created source
  bundle zip against the manifest report by path, size, SHA-256, and excluded
  path rules, then scan the zip text entries for secret-like findings and
  excluded Creative Studio references plus local user/runtime path findings.
- Added `scripts/rc_release_receipt.py` to generate a release handoff receipt
  and `.zip.sha256` sidecar after final gate evaluation, including an
  `approval_request` section for release-owner staging approval.
- Hardened `scripts/rc_final_gate.py` release receipt freshness checks so the
  receipt `generated_at` must not be older than the source bundle, artifact
  integrity, owner gate plan, owner handoff gate, `owner_env_template`,
  `owner_gate_checklist`, release diff review, deployment docs, staging plan,
  install, supply-chain, or secrets reports.
- Added `scripts/rc_evidence_pack.py` to archive the release receipt, source
  artifact, `.zip.sha256` sidecar, required RC reports, and owner handoff files
  into a secret-scanned evidence pack.
- Hardened the evidence pack gate so packed owner gate runner evidence must
  include the generated owner env-file label and env variable names only.
- Hardened final gate/evidence pack ordering: `--allow-missing-evidence-pack`
  is only a bootstrap path inside the refresh chain before the first pack
  exists. Final final gate remains strict and must consume a created evidence
  pack with passing freshness, artifact, secret-scan, and local user/runtime
  path privacy checks. The owner-verified fixed-point gate can report tag
  readiness only after owner-controlled external evidence is verified.
- Hardened `scripts/rc_refresh_release_chain.py` so Ollama refreshes can pin
  `--ollama-model` and `--ollama-base-url`, while only non-secret provider env
  override names are recorded in release-chain reports.
- Added `scripts/rc_owner_verified_finalize.py` as the owner-facing final RC
  finalization entrypoint. It wraps the strict owner-verified refresh chain,
  summarizes tag readiness from the fixed-point final gate, writes
  `rc-owner-verified-finalize.json`, and records only owner env variable names.
- Added `scripts/rc_deployment_docs_gate.py` to keep the commercial deployment
  runbook, checklist, install quickstart, and release notes aligned with the
  current RC evidence and owner-gate status.
- Added `scripts/rc_staging_plan.py` to emit exact non-mutating `git add --`
  command chunks for owner review.
- Added `.github/workflows/commercial-rc.yml` with Linux RC verification and
  Windows installer dry-run jobs.
- Added `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md` for production secrets,
  Compose/K8s deployment, monitoring, rollback, and residual-risk handoff.
- Added `docs/RC_RELEASE_DIFF_REVIEW.md` and `scripts/rc_release_audit.py` for
  release-level diff review, manifest coverage, secret-pattern scanning,
  excluded-reference scanning, local user/runtime path scanning, manifest unsafe paths,
  and candidate file hygiene scanning.
- Updated `docker-compose.yml` so API and worker services receive aligned
  security, LLM, Langfuse, GitHub, Feishu, and optional Feishu `XAGENT_*` environment
  variables.

## Current Verification Evidence

Latest local verification on 2026-06-06:

```powershell
python scripts\codex_hermes_gap_matrix.py --write-report
npm audit --audit-level=moderate
npm run type-check
npm run build
powershell -ExecutionPolicy Bypass -File scripts\install-xagent.ps1 -DryRun
& 'C:\Program Files\Git\bin\bash.exe' scripts/install-xagent.sh --dry-run
python scripts\xagent_doctor.py --json
python scripts\rc_runtime_smoke.py
python scripts\rc_external_smoke.py
python scripts\rc_release_audit.py
python scripts\rc_refresh_release_chain.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://localhost:11434
python scripts\rc_release_diff_review_gate.py
python scripts\rc_deployment_docs_gate.py
python scripts\rc_ci_contract.py
python scripts\rc_owner_gate_plan.py
python scripts\rc_owner_env_template.py
python scripts\rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime\reports\rc-owner-env-template.env
python scripts\rc_owner_handoff_gate.py
python scripts\rc_supply_chain_gate.py
python scripts\rc_secrets_gate.py
python scripts\rc_source_bundle.py --create
python scripts\rc_artifact_integrity_gate.py
python scripts\rc_staging_plan.py
python scripts\rc_install_release_gate.py
python scripts\rc_owner_verified_finalize.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435 --dry-run
python scripts\rc_final_gate.py
python scripts\rc_release_receipt.py
python -m pytest tests/test_rc_runtime_smoke.py tests/test_rc_external_smoke.py tests/test_docker_compose_env_contract.py tests/test_rc_release_audit.py tests/test_rc_release_diff_review_gate.py tests/test_rc_deployment_docs_gate.py tests/test_rc_ci_contract.py tests/test_rc_evidence_pack.py tests/test_rc_refresh_release_chain.py tests/test_rc_owner_gate_plan.py tests/test_rc_owner_env_template.py tests/test_rc_owner_gate_checklist.py tests/test_rc_install_release_gate.py tests/test_rc_supply_chain_gate.py tests/test_rc_secrets_gate.py tests/test_rc_artifact_integrity_gate.py tests/test_rc_final_gate.py tests/test_rc_release_receipt.py tests/test_rc_source_bundle.py tests/test_rc_staging_plan.py tests/test_codex_hermes_gap_matrix.py -o addopts="" -p no:cov -p no:cacheprovider -q
git diff --check
```

Observed result:

- RC aggregate test group passed with targeted RC tests, including owner
  verified finalization coverage.
- Gap matrix passed all 9 categories and does not claim full parity.
- Frontend audit reported 0 moderate-or-higher vulnerabilities.
- Python vulnerability audit evidence now requires `pip-audit` from the dev
  extra and the CI `python -m pip show pip-audit` check before the
  supply-chain gate can pass.
- Frontend type-check and production build passed.
- Windows and POSIX installer dry-runs passed.
- Doctor returned `warn` only for optional external provider/channel tokens.
- Runtime smoke passed for backend health/readiness/chat/workflow-chat and
  frontend `/`, `/chat`, and proxied workbench API.
- Release audit passed with manifest coverage, no secret-like findings, no
  excluded-area references, no local user/runtime path findings, no manifest unsafe paths,
  and no file hygiene findings.
- CI workflow contract passed locally.
- Deployment docs gate passed locally and preserves the conditional
  owner-evidence handoff plus `full_parity_claimed=false` in owner-facing
  docs.
- Owner gate execution plan generated the real-resource handoff while keeping
  token-controlled checks and hosted GitHub Actions evidence as owner gates.
- Provider owner gate is currently `action_required`: the explicit Ollama
  smoke attempt for `qwen2.5:1.5b` at `http://localhost:11434` returns HTTP 500
  model-load failure, and this diagnostic is now carried into owner handoff
  evidence.
- Owner env templates prefill the non-secret Ollama model/base URL needed to
  reproduce that provider smoke, while GitHub/Feishu/provider token fields
  remain placeholders.
- Owner gate runner dry-run passed locally with the generated owner env
  template and records the allowlisted Feishu/GitHub/Actions preflight
  sequence plus missing owner env groups for release-owner execution. It also
  reports `unresolved_env_names` and `owner_gate_unresolved_env_names` when
  placeholders are still present, and tells the release owner to
  `Replace owner env template placeholder values` before rerunning.
- Owner handoff gate passed locally for the generated plan, env templates,
  checklist, required command tokens, evidence references, and no-secret
  boundary.
- Hosted GitHub Actions owner evidence now requires a GitHub Actions run URL
  shape before the owner gate can be marked verified.
- Hosted GitHub Actions owner evidence now also supports a read-only Actions
  run API preflight that requires `status=completed` and `conclusion=success`.
- Hosted GitHub Actions owner evidence now requires
  `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA` as a 40-character hex git commit SHA
  and records `head_sha_verified=true`, so an older successful run cannot
  satisfy the current RC gate.
- Install/release artifact gate passed locally.
- Supply-chain gate passed locally.
- Secrets readiness gate passed locally without writing generated secret values
  into the evidence report, and `prohibited_secret_artifacts` passed for the
  source bundle.
- Source bundle artifact was created locally and artifact integrity gate passed
  with a recorded zip SHA-256.
- Release receipt and `.zip.sha256` sidecar were generated for archive handoff.
  The receipt includes `approval_request` with final gate status, artifact
  SHA, remaining risks, and exact staging commands.
- Archive handoff includes
  `.xagent_runtime/release/x-agent-commercial-rc-receipt.json`,
  the source artifact `.zip.sha256` sidecar, and the evidence pack generated by
  `rc_evidence_pack.py` under `.xagent_runtime/release/`.
- Current owner-verified fixed-point final gate status is `ready_for_rc_tag`;
  local gates and owner-controlled provider, Feishu, GitHub test-resource, and
  hosted GitHub Actions evidence for commit
  `643a017b3a2ae00be212d186e2681a147b46bf6b` passed through the owner-facing
  finalization command. The existing pushed tag
  `x-agent-commercial-rc-20260608` resolves to
  `08cd6d114e0c0cb357ccea3e529aed7b2aea1045`, not the verified commit; treat
  this as a release consistency blocker until the owner creates a new tag at
  the verified commit or explicitly approves correcting the pushed tag.
  Intermediate refreshes can temporarily report
  `ready_with_receipt_refresh_required` until receipt and evidence-pack reports
  are regenerated in order.
- Source bundle creation passed from the staging manifest, wrote a zip under
  `.xagent_runtime/release/`, and excluded local/runtime/Creative Studio
  artifacts.
- Staging plan dry-run passed and produced exact `git add --` command chunks
  without mutating the git index.
- New smoke and Compose contract tests passed.
- Diff whitespace check passed.

## Known Limits

- GitHub Actions commercial RC workflow evidence is recorded for run
  `https://github.com/xiongpinji/X-Agent/actions/runs/27101646137` with
  `head_sha_verified=true`.
- Real OpenAI/DeepSeek/other provider smoke requires deployment-owner tokens;
  this RC owner-verified path uses Ollama `qwen2.5:1.5b`.
- Feishu and GitHub execute-mode acceptance is recorded for the owner-verified
  RC evidence snapshot; new customer resources require a fresh owner gate run.
- Full GA requires a broader workstation/CI baseline beyond the targeted RC
  checks.
- This release does not claim full Codex, Hermes, Claude Code, OpenClaw, or IDE
  marketplace parity.

## Staging Notes

Use `docs/RC_STAGING_MANIFEST.md` as the source-control guard. Stage exact
paths only and keep `.agents/`, `.codex/`, `AGENTS.md`,
`COMPETITIVE_ANALYSIS_2026.md`, and `.xagent_runtime/` out of the release commit
unless the owner explicitly approves otherwise.
