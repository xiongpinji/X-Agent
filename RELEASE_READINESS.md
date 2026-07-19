# X-Agent Release Readiness

Last updated: 2026-06-05

## Current release-candidate status

X-Agent is now in commercial-delivery convergence mode. The current
`codex/codex-hermes-gap-closure` branch includes the core enterprise agent
framework, MCP integration, CLI, hooks, enhanced context management, Phase 5.5
cloud sandbox / Issue-to-PR infrastructure, Phase 5.6 channel adapters, and the
DeepSeek real-LLM e2e fix.

Latest confirmed commit at the start of this readiness pass:

```text
c2b7dc9 fix: ensure agent replan applies code changes after read
```

The project is suitable for internal pilot and PoC demonstration. It is not yet
a final GA release until the production deployment checklist, security
decisions, and full release-candidate baseline are completed. The active
commercial RC gate is tracked in `docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md`.

## Confirmed working capabilities

The following capabilities have direct implementation and recent targeted validation evidence: MCP discovery/config tests, CLI command modules, hook lifecycle integration, context/session recovery subsystems, multi-channel adapter framework, cloud sandbox task API, GitHub Issue-to-PR pipeline scaffolding, AgentFixRunner, and DeepSeek real-LLM e2e mutation flow.

Most recent real-LLM validation:

```powershell
$env:XAGENT_E2E="1"
$env:XAGENT_E2E_LLM="1"
$env:XAGENT_ENABLE_HIGH_RISK_TOOLS="true"
$env:XAGENT_QDRANT_URL=""
python scripts/release_candidate_check.py --include-real-llm
```

Expected result:

```text
--- agent tool sequence ---
inspect_tree -> read_file -> apply_text_patch
1 passed
```

## Release-candidate validation commands

Use these commands from the repository root. They intentionally clear pytest's default coverage addopts and avoid the cache provider so targeted verification remains deterministic in constrained environments.

### Windows PowerShell

```powershell
$env:XAGENT_QDRANT_URL=""
$env:XAGENT_LLM_BACKEND="mock"
$env:XAGENT_DEEPSEEK_API_KEY=""
$env:XAGENT_TOOL_EXECUTION_STORE_PATH="$env:TEMP\xagent_tool_executions_test.json"
$env:XAGENT_AUDIT_STORE_PATH="$env:TEMP\xagent_audit_test.jsonl"
$env:XAGENT_RUN_STORE_PATH="$env:TEMP\xagent_runs_test.jsonl"
$env:XAGENT_MEMORY_STORE_PATH="$env:TEMP\xagent_memory_test.jsonl"
Remove-Item $env:XAGENT_TOOL_EXECUTION_STORE_PATH,$env:XAGENT_AUDIT_STORE_PATH,$env:XAGENT_RUN_STORE_PATH,$env:XAGENT_MEMORY_STORE_PATH -ErrorAction SilentlyContinue
python scripts/release_candidate_check.py
```

For real DeepSeek e2e, additionally set a valid `XAGENT_DEEPSEEK_API_KEY` in `.env` or the shell and run:

```powershell
$env:XAGENT_E2E="1"
$env:XAGENT_E2E_LLM="1"
$env:XAGENT_ENABLE_HIGH_RISK_TOOLS="true"
python scripts/release_candidate_check.py --include-real-llm
```

### Linux / macOS

```bash
unset ALL_PROXY all_proxy HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ftp_proxy grpc_proxy
export XAGENT_QDRANT_URL=""
export XAGENT_LLM_BACKEND=mock
export XAGENT_DEEPSEEK_API_KEY=""
export XAGENT_TOOL_EXECUTION_STORE_PATH=/tmp/xagent_tool_executions_test.json
export XAGENT_AUDIT_STORE_PATH=/tmp/xagent_audit_test.jsonl
export XAGENT_RUN_STORE_PATH=/tmp/xagent_runs_test.jsonl
export XAGENT_MEMORY_STORE_PATH=/tmp/xagent_memory_test.jsonl
rm -f "$XAGENT_TOOL_EXECUTION_STORE_PATH" "$XAGENT_AUDIT_STORE_PATH" "$XAGENT_RUN_STORE_PATH" "$XAGENT_MEMORY_STORE_PATH"
python3 -m pytest tests/test_channels.py tests/test_mcp_discovery.py tests/test_mcp_config.py tests/test_agent_loop.py tests/test_agent_fix_runner.py tests/test_sandbox_api.py -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short
```

For real DeepSeek e2e:

```bash
export XAGENT_E2E=1
export XAGENT_E2E_LLM=1
export XAGENT_ENABLE_HIGH_RISK_TOOLS=true
python3 -m pytest tests/e2e/test_agent_fix_real_llm.py -s -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short
```

## Known constraints and release risks

The sandbox used by Cowork has a short command wall time, so full test-suite validation cannot be completed there. Use targeted tests in the sandbox and full-suite validation on the developer workstation or CI.

Persistent JSON stores under `data/` can become corrupted by interrupted local test runs. Release validation should always point `XAGENT_TOOL_EXECUTION_STORE_PATH`, `XAGENT_AUDIT_STORE_PATH`, `XAGENT_RUN_STORE_PATH`, and `XAGENT_MEMORY_STORE_PATH` at temporary test files.

`pytest.ini` enables coverage by default. Release-targeted commands must use `-o addopts="" -p no:cov` when the goal is correctness verification rather than coverage generation.

Playwright, real PostgreSQL/Qdrant, heavy ML, and performance/bcrypt tests remain environment-dependent. They should be marked as CI-profile or workstation-profile tests before GA.

## Production deployment checklist

Commercial RC convergence now uses the stricter gate in
`docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md`, with the exact source-control
candidate list in `docs/RC_STAGING_MANIFEST.md`. The operational deployment
handoff is `docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md`. The checklist below remains
a production configuration quick reference.

Before external commercial deployment, complete the following checklist:

```text
[ ] Set XAGENT_APP_MODE=production.
[ ] Generate strong XAGENT_AUDIT_HMAC_SECRET, XAGENT_JWT_SECRET, and XAGENT_ENCRYPTION_KEY with scripts/generate_secrets.py.
[ ] Set XAGENT_REQUIRE_API_KEY=true and provision XAGENT_BOOTSTRAP_API_KEY securely.
[ ] Set XAGENT_ENABLE_HIGH_RISK_TOOLS=false by default; enable only for controlled e2e or approved automation flows.
[ ] Use explicit non-wildcard XAGENT_CORS_ORIGINS.
[ ] Configure XAGENT_DATABASE_URL, XAGENT_REDIS_URL, and optional XAGENT_QDRANT_URL with production credentials.
[ ] Configure the desired LLM backend and API keys via XAGENT_* variables only.
[ ] Confirm docker-compose.yml passes XAGENT_* variables to API, worker, and beat containers.
[ ] Run the release-candidate targeted baseline.
[ ] Run the real DeepSeek or chosen LLM e2e if the deployment includes autonomous code modification.
[ ] Review tracked secret hygiene before tagging or distributing a release.
```

## High-risk decisions still requiring owner approval

The following items should not be changed automatically without explicit owner approval: untracking or rotating any already-tracked secret-bearing files, changing production authentication policy, weakening or bypassing audit HMAC enforcement, altering sandbox/path-traversal protections, and changing high-risk tool approval semantics.

## Recommended next milestone

The next milestone is `v1.0.0-beta`: a deployable pilot release with documented setup, deterministic targeted verification, mock and DeepSeek modes, Docker Compose alignment, and an explicit known-limits section. GA should follow only after the full workstation/CI baseline and security decision list are closed.
