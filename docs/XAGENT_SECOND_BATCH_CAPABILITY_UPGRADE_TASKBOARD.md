# X-Agent Second Batch Capability Upgrade Taskboard

## Direction

Second-batch upgrades target API-first capability expansion for users with unknown local machine capacity. Local model runtimes are out of scope for this batch. Every model capability must use external provider APIs, explicit auth, budget gates, audit evidence, and deterministic verification.

## Current Workstreams

| ID | Capability | Status | Delivery Boundary | Verification |
|---|---|---|---|---|
| B2-P0-01 | External LLM API governance route | Merged and locally verified | Mounted `/api/v1/llm` route with external API-only provider list, protocol-llm gateway boundary, completion budget guard, explicit `auto` completion rejection, official external HTTPS base URL enforcement for DeepSeek, verification-only mock provider disabled by default, in-process cost tracker, audit records, stats endpoint, and dry-run gate report | `python -m pytest tests/test_llm_governance_api.py tests/test_llm_governance_api_gate.py tests/test_llm_router.py tests/test_llm_providers.py tests/test_route_auth_audit.py -q --no-cov`; `python scripts/llm_governance_api_gate.py`; `git diff --check` |
| B2-P0-02 | Unified quality gate and audit pack | Implemented and locally verified | Standard report schema aggregator for second-batch capability slices: pass status, dry-run flag, mutation flags, release-claim boundary, current git SHA binding, check counts, failed checks, and replay commands | `python -m pytest tests/test_second_batch_quality_gate.py -q --no-cov`; `python scripts/second_batch_quality_gate.py`; `git diff --check` |
| B2-P0-03 | API-only RAG and knowledge retrieval | Implemented and locally verified | Mounted `/api/v1/rag` read/query governance route with API-only provider list, local retrieval provider rejection, protocol-search boundary with optional provider adapters, tenant-scoped mock retrieval, budget guard, audit records, and dry-run gate report | `python -m pytest tests/test_rag_governance_api.py tests/test_rag_governance_api_gate.py -q --no-cov`; `python scripts/rag_governance_api_gate.py`; `python scripts/second_batch_quality_gate.py`; `git diff --check` |
| B2-P1-01 | Multi-agent workflow dispatcher hardening | Implemented and locally verified | Explicit handoff contracts with timeout/cost controls, bounded retry policy, required handoff artifacts, fan-in, trace, and audit requirements | `python -m pytest tests/test_agent_dispatch_contract_gate.py -q --no-cov`; `python scripts/agent_dispatch_contract_gate.py`; `python scripts/second_batch_quality_gate.py`; `git diff --check` |
| B2-P1-02 | Browser/workspace verification harness | Implemented and locally verified | Replayable local verification steps and report artifacts for UI/API workflows; AI-assisted exploration is not accepted as final proof | `python -m pytest tests/test_browser_workspace_verification_gate.py -q --no-cov`; `python scripts/browser_workspace_verification_gate.py`; `python scripts/second_batch_quality_gate.py`; `git diff --check` |
| B2-P1-03 | Provider health, failover, and runtime preflight | Implemented and locally verified | Provider readiness matrix plus `/api/v1/providers/preflight` runtime API with `audit:read`, API-only/local=false entries, redacted credential status, protocol LLM/search seams, mock/dry-run fallback, DeepSeek official-host guard, Creative Video protocol external HTTPS guard, and declared failover paths | `python -m pytest tests/test_provider_health_failover_gate.py tests/test_provider_preflight_api.py tests/test_provider_preflight_api_gate.py -q --no-cov`; `python scripts/provider_health_failover_gate.py`; `python scripts/provider_preflight_api_gate.py`; `python scripts/second_batch_quality_gate.py`; `git diff --check` |

## B2-P0-01 Acceptance

The first slice is considered merge-ready when all are true:

- `/api/v1/llm/providers` lists only API-first providers: `protocol-llm`, `deepseek`, `mock`; `mock` is marked verification-only and disabled for completion by default.
- `/api/v1/llm/complete` requires `agent:run`.
- `/api/v1/llm/stats` requires `audit:read`.
- `ollama`, `local`, `localhost`, and `comfyui` are rejected as local providers.
- `auto` is rejected on `/complete` until routed-provider cost governance is explicit.
- `protocol-llm` must use an explicitly configured external HTTPS protocol-compatible gateway; DeepSeek `base_url` must use the official external HTTPS DeepSeek API host and must not route to localhost or private/local addresses.
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
- `tests/test_llm_governance_api.py tests/test_llm_governance_api_gate.py tests/test_llm_router.py tests/test_llm_providers.py tests/test_route_auth_audit.py`: 50 passed.
- `scripts/llm_governance_api_gate.py`: passed and wrote `.xagent_runtime/reports/llm-governance-api-gate.json`, including `auto_completion_rejected_until_costed` and `deepseek_base_url_must_be_official_external_https`.
- `git diff --check`: passed.

## B2-P0-02 Acceptance

The unified quality gate is considered merge-ready when all are true:

- It reads the current second-batch capability gate reports from `.xagent_runtime/reports/`.
- It fails if any capability report is missing or not `passed`.
- It fails if any capability report sets `dry_run=false`, `mutation_performed=true`, or `network_mutation_performed=true`.
- It fails if any capability report claims full release readiness.
- It fails if any capability report was generated from a different git revision than the current checkout.
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

## B2-P0-03 Acceptance

The API-only RAG slice is considered merge-ready when all are true:

- `/api/v1/rag/providers` lists only API-first providers; concrete adapters are optional and must stay behind external HTTPS protocol boundaries.
- `/api/v1/rag/providers` and `/api/v1/rag/query` require `memory:read`.
- `local`, `qdrant`, `chroma`, `pgvector`, `ollama`, `comfyui`, and `localhost` are rejected as local retrieval providers.
- Retrieval cost is estimated and checked before provider use.
- Query results are tenant-scoped and cross-tenant `tenant_scope` requests are rejected.
- Successful and failed query attempts are recorded in `AuditStore`.
- Optional search adapters use external HTTPS APIs and require credentials before live provider use.
- The local gate explicitly uses only the mock provider and performs no external search calls.

## B2-P0-03 Current Verification

```text
python -m py_compile backend\app\api\rag_governance.py scripts\rag_governance_api_gate.py tests\test_rag_governance_api.py tests\test_rag_governance_api_gate.py backend\app\main.py
python -m pytest tests/test_rag_governance_api.py tests/test_rag_governance_api_gate.py -q --no-cov
python scripts\rag_governance_api_gate.py
python scripts\second_batch_quality_gate.py
git diff --check
```

Latest local results:

- `python -m py_compile ...`: passed.
- `tests/test_rag_governance_api.py tests/test_rag_governance_api_gate.py`: 8 passed.
- `scripts/rag_governance_api_gate.py`: passed and wrote `.xagent_runtime/reports/rag-governance-api-gate.json`.

## B2-P1-01 Acceptance

The dispatcher hardening slice is considered merge-ready when all are true:

- A default second-batch dispatch contract validates successfully.
- Every handoff has explicit objective, input refs, output artifact requirements, timeout, cost budget, and retry cap.
- Parallel dispatch requires fan-in validation.
- Trace and audit requirements are explicit.
- The local gate does not spawn agents or perform network work.

## B2-P1-01 Current Verification

```text
python -m py_compile backend\app\core\agent_dispatch_contracts.py scripts\agent_dispatch_contract_gate.py tests\test_agent_dispatch_contract_gate.py
python -m pytest tests/test_agent_dispatch_contract_gate.py -q --no-cov
python scripts\agent_dispatch_contract_gate.py
python scripts\second_batch_quality_gate.py
git diff --check
```

Latest local results:

- `tests/test_agent_dispatch_contract_gate.py`: 2 passed.
- `scripts/agent_dispatch_contract_gate.py`: passed and wrote `.xagent_runtime/reports/agent-dispatch-contract-gate.json`.

## B2-P1-02 Acceptance

The browser/workspace verification harness is considered merge-ready when all are true:

- It defines replayable local commands and evidence paths.
- It disallows network mutation in every step.
- It does not treat AI exploration as final proof.
- Evidence paths are local and can be attached to later browser/UI runs.
- The local gate does not launch browsers or mutate the workspace.

## B2-P1-02 Current Verification

```text
python -m py_compile scripts\browser_workspace_verification_gate.py tests\test_browser_workspace_verification_gate.py
python -m pytest tests/test_browser_workspace_verification_gate.py -q --no-cov
python scripts\browser_workspace_verification_gate.py
python scripts\second_batch_quality_gate.py
git diff --check
```

Latest local results:

- `tests/test_browser_workspace_verification_gate.py`: 2 passed.
- `scripts/browser_workspace_verification_gate.py`: passed and wrote `.xagent_runtime/reports/browser-workspace-verification-gate.json`.

## B2-P1-03 Acceptance

The provider health/failover/preflight slice is considered merge-ready when all are true:

- Provider matrix entries are API-only and `local=false`.
- Credential status is redacted and never includes raw secret values.
- Mock fallback is always available for local verification.
- DeepSeek declares the official-host-only guard.
- Creative Video provider declares the protocol external-HTTPS-only guard and does not preselect image/video models.
- Failover order is present for each provider entry.
- `/api/v1/providers/preflight` is mounted, requires `audit:read`, and imports runtime preflight logic from `backend.app.core`, not `scripts.*`.
- Runtime preflight reports `dry_run=true`, `network_mutation_performed=false`, and per-provider `network_call_attempted=false`.
- The local gate does not call external providers.

## B2-P1-03 Current Verification

```text
python -m py_compile scripts\provider_health_failover_gate.py scripts\provider_preflight_api_gate.py tests\test_provider_health_failover_gate.py tests\test_provider_preflight_api.py tests\test_provider_preflight_api_gate.py
python -m pytest tests/test_provider_health_failover_gate.py tests/test_provider_preflight_api.py tests/test_provider_preflight_api_gate.py -q --no-cov
python scripts\provider_health_failover_gate.py
python scripts\provider_preflight_api_gate.py
python scripts\second_batch_quality_gate.py
git diff --check
```

Latest local results:

- `tests/test_provider_health_failover_gate.py tests/test_provider_preflight_api.py tests/test_provider_preflight_api_gate.py`: passed.
- `scripts/provider_health_failover_gate.py`: passed and wrote `.xagent_runtime/reports/provider-health-failover-gate.json`.
- `scripts/provider_preflight_api_gate.py`: passed and wrote `.xagent_runtime/reports/provider-preflight-api-gate.json`.

## Known Limits

- Cost tracking is process-local in this slice. It is governance evidence, not billing truth.
- Fine-grained `llm:*` scopes are intentionally deferred; this slice reuses `agent:run` and `audit:read` to avoid breaking existing API key roles.
- Real protocol LLM/Search or DeepSeek live calls are not part of this local gate. Provider staging requires owner credentials and an explicit network-mutation approval.
- Creative Studio video API is a reserved protocol interface. Image-generation and video-generation models are matched only when the owner selects the real provider/gateway.
