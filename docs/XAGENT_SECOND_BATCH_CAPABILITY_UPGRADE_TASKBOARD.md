# X-Agent Second Batch Capability Upgrade Taskboard

## Direction

Second-batch upgrades target API-first capability expansion for users with unknown local machine capacity. Local model runtimes are out of scope for this batch. Every model capability must use external provider APIs, explicit auth, budget gates, audit evidence, and deterministic verification.

## Current Workstreams

| ID | Capability | Status | Delivery Boundary | Verification |
|---|---|---|---|---|
| B2-P0-01 | External LLM API governance route | Merged and locally verified | Mounted `/api/v1/llm` route with external API-only provider list, completion budget guard, explicit `auto` completion rejection, official external HTTPS base URL enforcement for DeepSeek, in-process cost tracker, audit records, stats endpoint, and dry-run gate report | `python -m pytest tests/test_llm_governance_api.py tests/test_llm_governance_api_gate.py tests/test_llm_router.py tests/test_llm_providers.py tests/test_route_auth_audit.py -q --no-cov`; `python scripts/llm_governance_api_gate.py`; `git diff --check` |
| B2-P0-02 | Unified quality gate and audit pack | Implemented and locally verified | Standard report schema aggregator for second-batch capability slices: pass status, dry-run flag, mutation flags, release-claim boundary, check counts, failed checks, and replay commands | `python -m pytest tests/test_second_batch_quality_gate.py -q --no-cov`; `python scripts/second_batch_quality_gate.py`; `git diff --check` |
| B2-P0-03 | API-only RAG and knowledge retrieval | Planned | External embedding/search APIs only; no local vector model requirement; tenant-scoped retrieval contracts | Add API tests for auth, tenant isolation, provider failure, and budget cap |
| B2-P1-01 | Multi-agent workflow dispatcher hardening | Planned | Explicit handoff contracts, timeout/cost controls, retry policy, and fan-in validation | Add workflow contract tests and trace/audit assertions |
| B2-P1-02 | Browser/workspace verification harness | Planned | Replayable scripts and report artifacts for UI/API workflows; AI-assisted exploration cannot be final proof | Add Playwright/API smoke gate with stored evidence |
| B2-P1-03 | Provider health and failover evidence | Planned | Provider readiness matrix with redacted config status and no secret exposure | Add provider status tests and redaction checks |

## B2-P0-01 Acceptance

The first slice is considered merge-ready when all are true:

- `/api/v1/llm/providers` lists only API-first providers: `openai`, `deepseek`, `mock`.
- `/api/v1/llm/complete` requires `agent:run`.
- `/api/v1/llm/stats` requires `audit:read`.
- `ollama`, `local`, `localhost`, and `comfyui` are rejected as local providers.
- `auto` is rejected on `/complete` until routed-provider cost governance is explicit.
- DeepSeek `base_url` must use the official external HTTPS DeepSeek API host and must not route to localhost, private/local addresses, or OpenAI-compatible proxy gateways.
- Request input tokens and estimated provider cost are checked before provider calls.
- Successful and failed completion attempts are recorded in `CostTracker` and `AuditStore`.
- Provider errors return a controlled API error without leaking raw provider exception text.
- Existing LLM router/provider tests keep passing.

## B2-P0-01 Current Verification

```text
python -m py_compile backend\app\api\llm_governance.py scripts\llm_governance_api_gate.py tests\test_llm_governance_api.py tests\test_llm_governance_api_gate.py
python -m pytest tests/test_llm_governance_api.py tests/test_llm_governance_api_gate.py tests/test_llm_router.py tests/test_llm_providers.py tests/test_route_auth_audit.py -q --no-cov
python scripts\llm_governance_api_gate.py
git diff --check
```

Latest local results:

- `python -m py_compile ...`: passed.
- `tests/test_llm_governance_api.py tests/test_llm_governance_api_gate.py tests/test_llm_router.py tests/test_llm_providers.py tests/test_route_auth_audit.py`: 48 passed.
- `scripts/llm_governance_api_gate.py`: passed and wrote `.xagent_runtime/reports/llm-governance-api-gate.json`, including `auto_completion_rejected_until_costed` and `deepseek_base_url_must_be_official_external_https`.
- `git diff --check`: passed.

## B2-P0-02 Acceptance

The unified quality gate is considered merge-ready when all are true:

- It reads the Creative Studio and LLM governance gate reports from `.xagent_runtime/reports/`.
- It fails if any capability report is missing or not `passed`.
- It fails if any capability report sets `dry_run=false`, `mutation_performed=true`, or `network_mutation_performed=true`.
- It fails if any capability report claims full release readiness.
- It fails if a capability report has no checks, failed checks, or no replay commands.
- It writes a single audit-pack report without calling external providers.

## B2-P0-02 Current Verification

```text
python -m py_compile scripts\second_batch_quality_gate.py tests\test_second_batch_quality_gate.py
python -m pytest tests/test_second_batch_quality_gate.py -q --no-cov
python scripts\second_batch_quality_gate.py
git diff --check
```

Latest local results:

- `python -m py_compile ...`: passed.
- `tests/test_second_batch_quality_gate.py`: 2 passed.
- `scripts/second_batch_quality_gate.py`: passed and wrote `.xagent_runtime/reports/second-batch-quality-gate.json`.

## Known Limits

- Cost tracking is process-local in this slice. It is governance evidence, not billing truth.
- Fine-grained `llm:*` scopes are intentionally deferred; this slice reuses `agent:run` and `audit:read` to avoid breaking existing API key roles.
- Real OpenAI/DeepSeek live calls are not part of this local gate. Provider staging requires owner credentials and an explicit network-mutation approval.
