# X-Agent Commercial RC Deployment Runbook

Last updated: 2026-06-07

This runbook is the deployment handoff for the current
`codex/codex-hermes-gap-closure` release-candidate branch. It turns the broader
deployment docs into a commercial RC procedure with explicit verification gates.

It is not a GA claim and it is not a full Codex/Hermes parity claim. It is a
commercial pilot/RC deployment path that must still be validated with the
customer's real provider tokens, channel credentials, and infrastructure.
Current fixed-point local final-gate status is `ready_for_rc_tag`, with
`full_parity_claimed=false`, after the owner-verified refresh chain passed with
real Feishu, GitHub issue-to-PR, provider, and hosted Actions evidence. Earlier
intermediate refreshes can temporarily report
`ready_with_receipt_refresh_required` until receipt and evidence-pack reports
are regenerated in order. The owner finalization command below remains the
repeatable tag-readiness proof and must be rerun if any release evidence or
owner-controlled variable changes. This runbook does not claim full
Codex/Hermes parity.
Current local provider smoke is verified with Ollama at
`http://127.0.0.1:11435`, model `qwen2.5:1.5b`, after copying the required
model blobs to the ASCII-only model directory `D:\ollama-models`. The direct
proof command returned the required sentinel:
`ollama run qwen2.5:1.5b "Reply with exactly: xagent-rc-ok"`.
The previous `http://localhost:11434` Ollama instance still reproduces an HTTP
500 model-load failure because its model blob path is passed to the loader with
mojibake from the non-ASCII `D:\AI模型库` directory. For Windows local-provider
release smoke, use an ASCII-only `OLLAMA_MODELS` path, prove `ollama run
<model>` works, and pass the same `--ollama-base-url` and `--ollama-model` to
the refresh chain.
Feishu, GitHub issue-to-PR, and hosted GitHub Actions are owner-controlled
gates and must remain verified for the exact commit SHA used for RC tagging.
Tag evidence is for commit `643a017b3a2ae00be212d186e2681a147b46bf6b`. The
already-pushed tag `x-agent-commercial-rc-20260608` currently resolves to
`08cd6d114e0c0cb357ccea3e529aed7b2aea1045`, so release handoff must not treat
that pushed tag as verified until the owner either creates a new tag at
`643a017b3a2ae00be212d186e2681a147b46bf6b` or explicitly approves correcting
the existing remote tag.

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
python scripts/rc_owner_verified_finalize.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435
git rev-parse HEAD
git rev-parse x-agent-commercial-rc-20260608
```

Provider smoke is a sentinel check, not just a connectivity check: the selected
real backend must return content containing `xagent-rc-ok`, or
`scripts/rc_external_smoke.py` records the provider check as failed.

`scripts/rc_refresh_release_chain.py` is the recommended release-evidence
refresh entrypoint. It runs the dependent RC reports sequentially so downstream
gates never read a half-written JSON report from an upstream gate. Keep the
individual `rc_*` scripts available for focused debugging, but do not parallelize
the release refresh chain.
`scripts/rc_owner_verified_finalize.py` is the owner-facing finalization
entrypoint. It wraps the owner-verified refresh chain, summarizes
`rc_final_gate.py` tag-readiness state, writes
`.xagent_runtime/reports/rc-owner-verified-finalize.json`, and intentionally
does not create git tags or store secret values.
It binds `XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_HEAD_SHA` to the expected release
commit SHA, defaulting to `git rev-parse HEAD`; use `--expected-commit-sha`
only when finalizing a specific checked commit. The hosted Actions run SHA, the
local release commit, and the RC tag target must all match before handoff.
For Ollama/local release evidence, pass the exact `--ollama-model` and
`--ollama-base-url` used for provider smoke so refreshed reports do not
implicitly fall back to the default model.
For the final tag-ready refresh, also pass `--owner-verified`; that mode reruns
the owner-controlled external smoke checks with `--require-configured`,
`--github-execute-preflight`, and `--github-actions-preflight` so existing
Feishu, GitHub issue-to-PR, and hosted Actions evidence is not overwritten by a
non-owner local smoke snapshot.

The refresh chain uses `--allow-missing-evidence-pack` only for bootstrap
`rc_final_gate.py` passes that run before the first evidence pack exists. Final final gate remains strict:
`python scripts/rc_final_gate.py --require-ready-to-tag` must consume a created `rc-evidence-pack.json` with
passing freshness, artifact, secret-scan, and local-path privacy checks.
The final gate also treats `rc-refresh-release-chain.json` as a local gate and
as an evidence-pack freshness input. If the refresh-chain report is regenerated
after the evidence pack, rerun `rc_release_receipt.py`, `rc_evidence_pack.py`,
and `rc_final_gate.py --require-ready-to-tag` before handoff.

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
python scripts/rc_refresh_release_chain.py --provider ollama --ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435 --owner-verified
python scripts/rc_final_gate.py --require-ready-to-tag
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
  rerun `python scripts/rc_refresh_release_chain.py --provider ollama
  --ollama-model qwen2.5:1.5b --ollama-base-url http://127.0.0.1:11435
  --owner-verified`. This final refresh preserves owner-controlled external
  evidence and prevents a later mock or skipped local smoke snapshot from being
  packaged as tag-ready evidence.
- Skill Curator: keep custom draft roots disabled in production/API-key mode.

## 9. Residual RC Risks

Keep these items visible in the release report:

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
