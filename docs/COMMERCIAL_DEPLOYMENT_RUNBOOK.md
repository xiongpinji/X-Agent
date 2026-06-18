# X-Agent Commercial RC Deployment Runbook

Last updated: 2026-06-18

> Current status note (2026-06-18): this runbook is for the first-version
> commercial RC path, not GA. The current delivery ledger is
> `docs/superpowers/plans/2026-06-18-xagent-commercial-delivery-master-plan.md`.
> Desktop/Tauri is first-version scope. Browser extension work is deferred and
> must not be shipped, demoed, or documented as part of the first-version
> customer delivery. Do not paste secret values into this file; use secret
> manager references or CI/environment variable names.

This runbook is the deployment handoff for the current commercial RC evidence
chain. It turns the broader deployment docs into a commercial RC procedure with
explicit verification gates.

It is not a GA claim and it is not a full Codex/Hermes parity claim. It is a
commercial pilot/RC deployment path that must still be validated with the
customer's real provider configuration, channel credentials, and infrastructure.
Current commercial RC readiness is machine-report driven, not inferred from any
historical tag-ready snapshot. For the active RC candidate, read the master plan,
`.xagent_runtime/reports/rc-delivery-status.json`, and the latest RC gate
reports before making any tag or deployment claim.

Current local owner gates are verified with DeepSeek, Feishu webhook contract
checks, GitHub issue-to-PR dry-run/execute preflight, and hosted GitHub Actions
run evidence for RC branch `codex/p0-c-ci-deployment-gates`, hosted Commercial
RC Gate run `27717463270`, SHA
`dca6a063e9c21ee5e420d3346c28735b17a92fdf`.
`python scripts/rc_final_gate.py --require-ready-to-tag` is the current
machine gate for the owner-verified evidence chain; read the live status from
`.xagent_runtime/reports/rc-final-gate.json`.
The current final gate status is `ready_with_owner_gates`, so RC tagging still
requires the owner-controlled gates named in the live report.
During evidence refresh, expected interim machine states include `failed` and
`ready_with_receipt_refresh_required`; only the live JSON report controls the
current decision.

This does not close final Stage3/production evidence. P0-D2 remains open until
an owner-controlled real domain points to `111.228.49.160`, HTTPS/443 serves
`/health` and `/ready` with trusted TLS, and the Stage3 external evidence intake
records release-bound observability and environment-protection references.
Temporary HTTP on `http://111.228.49.160:8899` is useful smoke evidence only;
the `sslip.io` host path is not acceptable commercial evidence on this server.

Older Ollama/local-provider snapshots, earlier pushed tags, and historical
owner-verified reports are historical evidence only. Do not treat them as
current commercial handoff proof.

## 1. Release Scope

Included in this RC:

- FastAPI backend with health/readiness probes, web chat entrypoint, workbench
  bootstrap, workflow-chat creation, gateway dry-run mode, Feishu channel
  adapter, GitHub issue-to-PR dry-run/guarded execute path, and Skill Curator
  MVP.
- Frontend Vite app with `/`, `/chat`, and API proxy coverage.
- CLI command surface for gateway and GitHub issue-to-PR operations.
- Docker Compose environment wiring for API, worker, beat, PostgreSQL, Redis,
  Qdrant, and Neo4j.
- Commercial RC verification workflow in `.github/workflows/commercial-rc.yml`.

Excluded from an unaudited commercial rollout:

- Full production GA status.
- Full Codex/Hermes product parity.
- Real provider, Feishu app, or GitHub execute claims without live token and
  test-resource evidence.
- Staging of local agent config paths: `.agents/`, `.codex/`, `AGENTS.md`, and
  `COMPETITIVE_ANALYSIS_2026.md`.

## 2. Required Production Secrets

Generate deployment secrets outside source control:

```bash
python scripts/generate_secrets.py --format env
```

Store the generated values in the deployment owner's secret manager or CI secret
store. Do not commit `.env.production` or generated secret output.
The RC secrets gate also rejects prohibited secret artifact paths in the source
bundle, including real `.env` files, private key/certificate containers, and
`secret`/`secrets` directories; only explicit example/template env files are
allowed.

Minimum production variables:

```text
XAGENT_APP_MODE=production
XAGENT_AUDIT_HMAC_SECRET=<generated>
XAGENT_JWT_SECRET=<generated>
XAGENT_ENCRYPTION_KEY=<generated>
XAGENT_REQUIRE_API_KEY=true
XAGENT_BOOTSTRAP_API_KEY=<generated-or-secret-manager-value>
XAGENT_CORS_ORIGINS=https://<customer-console-origin>
XAGENT_DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>
XAGENT_REDIS_URL=redis://:<password>@<host>:6379/0
XAGENT_QDRANT_URL=http://<qdrant-host>:6333
XAGENT_QDRANT_API_KEY=<qdrant-api-key>
XAGENT_MEMORY_BACKEND=postgres
XAGENT_TRACE_BACKEND=jsonl
XAGENT_LLM_BACKEND=<mock|openai|deepseek>
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
XAGENT_PLAYWRIGHT_HEADLESS=true
```

Provider variables:

```text
XAGENT_OPENAI_API_KEY=<required when XAGENT_LLM_BACKEND=openai>
XAGENT_OPENAI_MODEL=gpt-4o-mini
XAGENT_DEEPSEEK_API_KEY=<required when XAGENT_LLM_BACKEND=deepseek>
XAGENT_DEEPSEEK_MODEL=deepseek-chat
XAGENT_DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
XAGENT_OLLAMA_BASE_URL=http://localhost:11434
XAGENT_OLLAMA_MODEL=<required when XAGENT_LLM_BACKEND=ollama-or-local>
XAGENT_LLM_FALLBACK_ORDER=openai,deepseek,mock
```

Optional integration variables:

```text
XAGENT_LANGFUSE_PUBLIC_KEY=<optional>
XAGENT_LANGFUSE_SECRET_KEY=<optional>
XAGENT_LANGFUSE_HOST=<optional>
XAGENT_GITHUB_TOKEN=<required for issue-to-PR execute mode>
XAGENT_GITHUB_WEBHOOK_SECRET=<required for signed GitHub webhooks>
XAGENT_GITHUB_TEST_ISSUE_URL=https://github.com/<owner>/<disposable-repo>/issues/<number>
XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL=https://github.com/<owner>/<repo>/actions/runs/<run-id>
XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA=<40-character-git-commit-sha>
XAGENT_FEISHU_APP_ID=<required for Feishu owner gate>
XAGENT_FEISHU_APP_SECRET=<required for Feishu tenant token and legacy signatures>
XAGENT_FEISHU_ENCRYPT_KEY=<required for signed Feishu/Lark event callbacks>
XAGENT_TELEGRAM_BOT_TOKEN=<optional when Telegram is enabled outside this RC gate>
XAGENT_TELEGRAM_WEBHOOK_SECRET=<optional when Telegram webhook is enabled outside this RC gate>
XAGENT_TELEGRAM_BASE_URL=<optional Telegram override>
```

## 3. Pre-Deploy RC Gate

Run these from the repository root before packaging or tagging:

```bash
python scripts/codex_hermes_gap_matrix.py --write-report
python scripts/xagent_doctor.py --json
python scripts/rc_runtime_smoke.py
python scripts/rc_external_smoke.py --provider deepseek --check provider --check feishu_webhook_contract --check github_issue_to_pr_dry_run --check github_issue_to_pr_execute_preflight --check hosted_github_actions_run --require-configured --github-execute-preflight --github-actions-preflight --timeout 40
python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60
python scripts/rc_final_gate.py --require-ready-to-tag
python scripts/rc_release_receipt.py
python scripts/rc_evidence_pack.py
python scripts/rc_final_gate.py --require-ready-to-tag
python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal
git rev-parse HEAD
```

Provider smoke is a sentinel check, not just a connectivity check: the selected
real backend must return content containing `xagent-rc-ok`, or
`scripts/rc_external_smoke.py` records the provider check as failed.

`scripts/rc_refresh_release_chain.py` is the recommended release-evidence
refresh entrypoint. It runs the dependent RC reports sequentially so downstream
gates never read a half-written JSON report from an upstream gate. Keep the
individual `rc_*` scripts available for focused debugging, but do not parallelize
the release refresh chain.
For the final tag-ready refresh, also pass `--owner-verified`; that mode reruns
the owner-controlled external smoke checks with `--require-configured`,
`--github-execute-preflight`, and `--github-actions-preflight` so existing
Feishu, GitHub issue-to-PR, and hosted Actions evidence is not overwritten by a
non-owner local smoke snapshot.
The hosted Actions run SHA, local release commit, and evidence reports must all
refer to the same selected release commit before handoff. Historical
`rc_owner_verified_finalize.py`, `rc_delivery_status.py`, and tag-consistency
reports can be used for focused debugging, but the current first-RC handoff must
be based on the owner-verified refresh chain above.

The refresh chain uses `--allow-missing-evidence-pack` only for bootstrap
`rc_final_gate.py` passes that run before the first evidence pack exists. Final final gate remains strict:
`python scripts/rc_final_gate.py --require-ready-to-tag` must consume a created `rc-evidence-pack.json` with
passing freshness, artifact, secret-scan, and local-path privacy checks.
The final gate also treats `rc-refresh-release-chain.json` as a local gate and
as an evidence-pack freshness input. If the refresh-chain report is regenerated
after the evidence pack, rerun `rc_release_receipt.py`, `rc_evidence_pack.py`,
and `rc_final_gate.py --require-ready-to-tag` before handoff.
For commercial handoff after Stage3 evidence is filled, run
`python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal`.
That stricter mode requires
`.xagent_runtime/reports/stage3-staging-rehearsal-result-20260615.json` to
report `staging_rehearsal_ready`, `rehearsal_ready=true`, `environment=staging`,
a release SHA, no `missing_or_mismatched` evidence, no gate side effects, and
passed rehearsal checks. The rehearsal `release_sha` must match the
owner-verified hosted GitHub Actions `head_sha`, so an older ready rehearsal
cannot be reused for a different RC candidate. The ordinary
`--require-ready-to-tag` command is still useful for owner-gate debugging, but
it is not the final P0-D2 commercial gate.
Final-gate fixed-point reports are validators only: they must not relax
receipt, refresh-chain, owner-gate, secrets, artifact, or source-bundle
freshness requirements.

The RC final gate also enforces release receipt freshness. The
`x-agent-commercial-rc-receipt.json` `generated_at` value must not be older than
the source bundle, artifact integrity, owner gate plan, owner handoff gate,
`owner_env_template`, `owner_gate_checklist`, release diff review, deployment
docs, staging plan, install, supply-chain, or secrets reports. The final gate
reads `owner_env_template` and `owner_gate_checklist` directly in addition to
the release receipt, so stale owner handoff summaries force a receipt refresh.
The release receipt includes an `approval_request` section with final gate
status, artifact path/SHA/file count, receipt path, remaining owner risks, and
the exact staging command set. Release owners must review that section before
any staging, commit, tag, or deployment.

Focused debugging entrypoints remain:

```bash
python scripts/rc_external_smoke.py --provider deepseek --check provider --check feishu_webhook_contract --check github_issue_to_pr_dry_run --check github_issue_to_pr_execute_preflight --check hosted_github_actions_run --require-configured --github-execute-preflight --github-actions-preflight --timeout 40
python scripts/rc_refresh_release_chain.py --provider deepseek --owner-verified --timeout 60
python scripts/rc_final_gate.py --require-ready-to-tag
python scripts/rc_final_gate.py --require-ready-to-tag --require-stage3-rehearsal
python scripts/rc_owner_gate_runner.py --gate all --dry-run --env-file .xagent_runtime/reports/rc-owner-env-template.env
python scripts/rc_owner_handoff_gate.py
python scripts/rc_evidence_pack.py
```

Archive handoff materials are generated under `.xagent_runtime/release/` and
must include `x-agent-commercial-rc-receipt.json`, the source artifact
`.zip.sha256` sidecar, and the evidence pack generated by
`rc_evidence_pack.py`.

Artifact integrity and evidence-pack gates scan release zip/evidence text for
secret-like findings, excluded references, and local user/runtime path findings.
Release audit also scans candidate files for local user/runtime path findings,
manifest unsafe paths, and file hygiene findings such as NUL bytes, UTF-8
decode failures, merge conflict markers, or trailing whitespace before staging.
The secrets gate adds a source-bundle path-level `prohibited_secret_artifacts`
check so real env/key/pem/pfx/p12 files or secret directories cannot enter the
commercial RC bundle.

Supply-chain gate:

```bash
python scripts/rc_supply_chain_gate.py
python -m pip show pip-audit
```

`pip-audit` is a required dev extra in `pyproject.toml`, not an optional local
tool. The supply-chain gate uses it to produce Python vulnerability audit evidence
from `requirements-lock.txt` and requires zero reported Python dependency
vulnerabilities before commercial RC handoff. The source bundle must
include both `pyproject.toml` and `requirements-lock.txt` so the dependency
manifest, vulnerability-audit tool declaration, and lockfile evidence can be
reviewed together.

Frontend gate:

```bash
cd frontend
npm ci
npm audit --audit-level=moderate
npm run type-check
npm run build
```

Frontend install and installer dry-runs must use `npm ci`, not `npm install`,
so `frontend/package-lock.json` remains the deployment source of truth.

Installer dry-runs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-xagent.ps1 -DryRun
```

```bash
sh scripts/install-xagent.sh --dry-run
```

The smoke and gap reports are runtime evidence under `.xagent_runtime/`; they
are not source-control staging candidates unless the owner explicitly requests
archival.

## 4. Docker Compose RC Deployment

Use Compose for pilot or staging RC environments. The defaults in
`docker-compose.yml` are intentionally development-safe, so production-like
deployments must provide an external env file or secret injection layer.

Preview resolved configuration:

```bash
docker compose --env-file .env.production config
```

Start services:

```bash
docker compose --env-file .env.production up -d postgres redis qdrant neo4j
docker compose --env-file .env.production up -d xagent-api xagent-worker xagent-beat
```

Verify:

```bash
docker compose ps
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
python scripts/rc_runtime_smoke.py --backend-port 8000 --backend-only
python scripts/rc_external_smoke.py --require-configured --github-execute-preflight --github-actions-preflight
```

For customer-facing web access, place TLS termination and authentication-aware
routing in front of the API/frontend host. Do not expose PostgreSQL, Redis,
Qdrant, or Neo4j directly to the public internet.

### 4.1 Stage3 HTTPS Evidence Checklist

P0-D2 cannot be closed from the temporary HTTP smoke endpoint. Use this
redaction-safe checklist after a real owner-controlled domain exists. Do not
paste secret values into any command output or evidence file.

What the owner must decide:

- The real domain name, for example `xagent.example.com`, with a DNS A record
  pointing to `111.228.49.160`.
- Whether first-RC observability uses real broker, trace, error, metrics, and
  alert refs, or an explicit owner-approved first-RC observability exception
  ref.
- The approval ref and UTC approval timestamp for the exact release SHA.

What Codex/operator tooling can fill after the domain exists:

- `https://<domain>/health` and `https://<domain>/ready` probe refs.
- Nginx site path, `nginx -t`, reload output, and certificate refs.
- Running Stage3 image ref/digest and secret variable-name refs.
- The regenerated Stage3 intake report and final validation command output.

Generate the no-secret owner/operator domain guide before editing DNS or the
server. This guide writes the exact DNS, Nginx, Certbot, preflight, owner-draft,
and strict final-gate command sequence without executing any of it:

```powershell
python scripts/stage3_owner_domain_guide.py `
  --domain "<REAL_DOMAIN>"
```

The guide writes `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.json`
and `.xagent_runtime/reports/stage3-owner-domain-guide-20260618.md`. If the
domain is a bare IP, localhost, a single-label host, or temporary wildcard DNS
such as `sslip.io`, the guide is intentionally blocked and will not print
server commands. When `--release-sha` is omitted, the guide reads the verified
hosted GitHub Actions `head_sha` from `.xagent_runtime/reports/rc-external-smoke.json`;
use `--release-sha <40-character-sha>` only when intentionally preparing a
different owner-verified RC commit.

Run the read-only HTTPS preflight after DNS and TLS are configured:

```powershell
python scripts/stage3_https_preflight.py `
  --domain "<REAL_DOMAIN>"
```

The preflight writes
`.xagent_runtime/reports/stage3-https-preflight-20260618.json` and
`.xagent_runtime/reports/stage3-https-preflight-20260618.md`. When the JSON
report is `stage3_https_preflight_ready`, pass it into the owner draft helper
with `--https-preflight-report` so the HTTPS endpoint, DNS, TLS, `/health`, and
`/ready` refs are prefilled. Do not paste secret-bearing logs.

Required evidence fields are listed in the generated owner draft:

```powershell
python scripts/commercial_stage3_staging_external_evidence_intake.py `
  --write-owner-draft `
  --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf `
  --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf `
  --domain "<REAL_DOMAIN>" `
  --https-preflight-report .xagent_runtime\reports\stage3-https-preflight-20260618.json `
  --owner xiongpinji `
  --force
```

The generated Markdown checklist is
`.xagent_runtime/reports/stage3-staging-external-evidence-owner-draft-20260616.md`.
Immediately convert the draft into a no-secret owner todo list:

```powershell
python scripts/stage3_owner_evidence_todo.py
```

This writes `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.json`
and `.xagent_runtime/reports/stage3-owner-evidence-todo-20260618.md`. Use the
Markdown todo file as the beginner-facing fill list; it does not mutate the
draft, deploy, dispatch workflows, or record raw secret values.

For a shorter owner/operator checklist, generate the six-step quickstart:

```powershell
python scripts/stage3_owner_quickstart.py
```

This writes `.xagent_runtime/reports/stage3-owner-quickstart-20260618.json`
and `.xagent_runtime/reports/stage3-owner-quickstart-20260618.md`. It is a
summary only; it does not replace the full todo report and cannot be used as
Stage3 evidence by itself.

The JSON draft remains blocked while `template_not_external_evidence=true`,
even when `prefill_refs.https_preflight_applied=true`; change it to `false`
only after every placeholder has been replaced with a real reference. Keep
`secret_binding.redaction_confirmed=false` until the file has been reviewed and
contains only variable names or secret-manager refs, never secret values. Keep
`deployed_image.not_external_deploy_proof=true` until the image ref/digest comes
from the running Stage3 environment.

After the draft is filled with real references:

```powershell
python scripts/commercial_stage3_staging_external_evidence_intake.py `
  --input-json .xagent_runtime\reports\stage3-staging-external-evidence-owner-draft-20260616.json `
  --current-head-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf `
  --release-sha dca6a063e9c21ee5e420d3346c28735b17a92fdf `
  --force
```

The command must report `stage3_staging_external_evidence_ready` before P0-D2
can move forward. HTTP URLs, bare IP addresses, localhost, non-443 HTTPS ports,
URL credentials, and temporary wildcard DNS such as `sslip.io`, `nip.io`, or
`xip.io` are intentionally rejected by the intake.

## 5. Kubernetes Or Helm Deployment

Use the existing deployment assets as the baseline:

- Helm chart: `deployment/helm/`
- Production values: `deployment/helm/values-production.yaml`
- K8s manifests: `deployment/k8s/`
- Monitoring stack: `deployment/prometheus/`, `deployment/grafana/`

Minimum verification after rollout:

```bash
kubectl rollout status deployment/xagent-api -n xagent --timeout=5m
kubectl rollout status deployment/xagent-worker -n xagent --timeout=5m
kubectl get pods -n xagent
curl -f https://<deployment-host>/health
curl -f https://<deployment-host>/ready
```

Run the backend-only runtime smoke against the exposed API by passing the
deployment port through a tunnel or staging ingress.

## 6. Observability And Operations

Health probes:

- `/health`: liveness, process-only.
- `/ready`: readiness, local stores plus optional integration degradation.

Operational docs:

- `docs/OPERATIONS.md`
- `deployment/MONITORING_QUICKSTART.md`
- `monitoring/DEPLOYMENT_CHECKLIST.md`

Minimum production monitoring:

- API 5xx rate and p95 latency.
- Worker queue depth and task failures.
- PostgreSQL availability and disk usage.
- Redis memory usage and connection count.
- Qdrant health and storage usage.
- Audit log write failures.
- Langfuse trace ingestion when Langfuse is enabled.

## 7. Rollback

Primary rollback references:

- `ROLLBACK_PROCEDURE.md`
- `ROLLBACK_PLAN.md`
- `deployment/rollback.sh`
- `deployment/scripts/backup-database.sh`
- `deployment/scripts/restore-database.sh`

Kubernetes fast rollback:

```bash
kubectl rollout undo deployment/xagent-api -n xagent
kubectl rollout undo deployment/xagent-worker -n xagent
kubectl rollout status deployment/xagent-api -n xagent --timeout=5m
kubectl rollout status deployment/xagent-worker -n xagent --timeout=5m
curl -f https://<deployment-host>/health
curl -f https://<deployment-host>/ready
```

Compose rollback:

```bash
docker compose --env-file .env.production pull
docker compose --env-file .env.production up -d --no-deps xagent-api xagent-worker xagent-beat
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready
```

Database rollback must only be performed after confirming a current backup and
the migration rollback path for the target version.

## 8. External Integration Acceptance

Before enabling an integration for a customer:

- OpenAI/DeepSeek/other LLM: run one real provider smoke with a capped budget
  and record provider, model, timestamp, result, and `sentinel_matched=true`.
  For Ollama/local acceptance, set both `XAGENT_OLLAMA_BASE_URL` and
  `XAGENT_OLLAMA_MODEL` to the exact model used for the smoke.
  If the Ollama provider smoke returns HTTP 404, first confirm the base URL
  points to the Ollama root endpoint rather than a UI/proxy path, then run
  `ollama pull <model>` or switch `XAGENT_OLLAMA_MODEL` to an installed model.
  If it returns HTTP 500, inspect the Ollama service logs and verify the model
  can generate locally with `ollama run <model>`. When the response mentions
  `failed to load model` or `llama_model_loader`, also verify
  `OLLAMA_MODELS`/model storage points to readable, intact model blobs and
  reinstall or move the selected model before rerunning. On Windows, avoid
  non-ASCII `OLLAMA_MODELS` paths for release smoke providers; use an ASCII
  model directory such as `%USERPROFILE%\.ollama\models` or `D:\ollama-models`,
  restart the Ollama service, and prove `ollama run <model>` works from that
  directory. If the connection fails, start Ollama and confirm
  `<base-url>/api/generate` is reachable before rerunning
  `python scripts/rc_external_smoke.py --check provider --provider ollama --require-configured`.
- `scripts/rc_owner_gate_runner.py --gate <gate>` may be used by the release
  owner to execute the allowlisted non-mutating preflight command for one gate
  and refresh owner/final reports. It still requires real owner-controlled
  credentials for the selected gate and fails rather than marking skipped
  checks as passed. Use `--gate all` only when all owner resources are ready;
  scoped single-gate runs intentionally avoid unrelated token requirements.
  After filling `.xagent_runtime/reports/rc-owner-env-template.env`, pass
  `--env-file .xagent_runtime/reports/rc-owner-env-template.env` to load only
  non-placeholder `KEY=value` entries into the allowlisted subprocess. The
  runner accepts only variable names declared by
  `.xagent_runtime/reports/rc-owner-gate-plan.json`; runtime-control variables
  such as `PATH` or `PYTHONPATH` are rejected even if they appear in the env
  file. For a scoped single-gate run, only the selected gate's required env
  names are injected into the owner smoke subprocess; unrelated filled tokens
  from the same env file are kept out of that subprocess. The runner report
  records `missing_env_groups` as variable-name groups only, so the deployment
  owner can see what remains unset without leaking values. It also records
  `unresolved_env_names` for placeholder values that were not loaded and
  `owner_gate_unresolved_env_names` for placeholders relevant to the selected
  gate. If the report says `Replace owner env template placeholder values`,
  replace those placeholders before rerunning. In non-dry-run mode, the runner
  performs an `env_preflight` check and fails before launching external smoke
  when any selected gate still has missing env groups.
- `feishu_webhook_contract`: verify Feishu/Lark signed event callback headers,
  inbound message event handling, duplicate-event rejection, and no outbound
  Feishu mutation. This is the required domestic channel gate for this RC.
- `github_issue_to_pr_dry_run`: run dry-run against a test issue URL. A scoped
  runner invocation for this gate requires `XAGENT_GITHUB_TEST_ISSUE_URL` but
  does not require a GitHub token:
  `python scripts/rc_owner_gate_runner.py --gate github_issue_to_pr_dry_run`.
  Filled env templates can be supplied with
  `--env-file .xagent_runtime/reports/rc-owner-env-template.env`.
- `github_issue_to_pr_execute_preflight`: execute mode must
  use a disposable test repository first. `scripts/rc_external_smoke.py
  --github-execute-preflight --require-configured` performs a token-authenticated
  read-only GitHub issue API probe that must confirm `read_probe.state=open`,
  a repository permission probe requiring `permissions.push=true`, and the
  local dry-run plan; it does not push
  branches, open PRs, or comment. Customer repository execute mode still
  requires token, CSRF, explicit execute flag, and configured executor.
- `hosted_github_actions_commercial_rc`: run the hosted Commercial RC workflow
  and verify the recorded Actions run through `--github-actions-preflight`.
  The owner must record both `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL` and
  `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA`; the latter must be a
  40-character hex git commit SHA. The read-only Actions run API must report
  `head_sha_verified=true` before the gate can be treated as verified.
- `refresh_release_chain_owner_verified`: after provider, Feishu, GitHub
  issue-to-PR, and hosted Actions evidence all pass for the current commit,
  rerun `python scripts/rc_refresh_release_chain.py --provider deepseek
  --owner-verified --timeout 60`. This final refresh preserves
  owner-controlled external evidence and prevents a later mock, local Ollama, or
  skipped smoke snapshot from being packaged as tag-ready evidence.
- Skill Curator: keep custom draft roots disabled in production/API-key mode.

## 9. Residual RC Risks

Keep these items visible in the release report:

- P0-D2 remains open until a real owner-controlled domain points to
  `111.228.49.160`, trusted HTTPS/443 serves `/health` and `/ready`, and
  release-bound observability and environment-protection evidence is recorded.
- GitHub Actions commercial RC workflow has run successfully in GitHub for this
  RC evidence snapshot. The hosted Commercial RC Gate workflow run is recorded
  in `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL`, and the exact hosted run
  commit is recorded in `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA` as a
  40-character hex git commit SHA before running
  `scripts/rc_owner_gate_runner.py`, `scripts/rc_external_smoke.py`,
  `scripts/rc_owner_gate_plan.py`, `scripts/rc_owner_env_template.py`, and
  `scripts/rc_owner_gate_checklist.py --fail-action-required` for the final tag
  gate. Trigger the hosted Commercial RC Gate workflow again if any staged
  release input changes. The value must be a
  GitHub Actions run URL shaped like
  `https://github.com/<owner>/<repo>/actions/runs/<run-id>`, and
  `scripts/rc_external_smoke.py --github-actions-preflight` must confirm
  `status=completed`, `conclusion=success`, and `head_sha_verified=true` via
  the read-only Actions run API.
- Full workstation/CI baseline across all tests is still separate from targeted
  RC evidence.
- Real external provider, Feishu, and GitHub execute evidence depends on
  deployment-owner tokens and test resources.
- High-risk tool execution must remain disabled by default and enabled only for
  approved controlled workflows.
- Existing secret-bearing tracked files or local config must not be staged
  without owner review.
