# Creative Studio External Video API-only Delivery

## Scope

This slice gives X-Agent a Creative Studio video-generation boundary that can call external model APIs without requiring local ComfyUI, local video models, or user GPU capacity.

The implementation is intentionally opt-in:

- Creative Studio is not mounted in `backend/app/main.py`.
- Creative Studio tools are not added to `build_default_tool_registry`.
- External video calls require explicit `human_review_approved=true`.
- Reviewed execution also requires a principal with `workflow:control`.
- The workflow endpoint defaults to dry-run planning and does not call providers unless `execute=true`.

## Provider Configuration

Set these environment variables only in the runtime that owns the external provider call:

```text
XAGENT_CREATIVE_VIDEO_API_URL=https://provider.example/video/generate
XAGENT_CREATIVE_VIDEO_API_KEY=...
XAGENT_CREATIVE_VIDEO_PROVIDER=external-provider-name
XAGENT_CREATIVE_VIDEO_MODEL=provider-model-name
```

Status responses expose only redacted configuration state. Raw API URL and raw API key are not returned.

## Local Endpoints

These endpoints live under the Creative Studio router only:

```text
GET  /api/v1/creative-studio/video-provider-status
POST /api/v1/creative-studio/shot-video
POST /api/v1/creative-studio/video-workflow
```

`/video-provider-status` reports whether provider config exists and whether human review is required.

`/shot-video` runs a single external video request only after human review approval. Without approval it fails closed with `provider_api_call_attempted=false`.

`/video-workflow` accepts a storyboard JSON payload and returns a deterministic plan by default. It only executes shot video calls when both `execute=true` and `human_review_approved=true`.

Execution is capped to 8 shots per request. Invalid storyboard requests return the same workflow response envelope with `workflow_status=invalid` and `provider_api_call_attempted=false`.

## Panda Frontend Contract

Panda now has API-only contracts and a fetch client:

```text
frontend/src/panda/api/creativeStudioApiContracts.ts
frontend/src/panda/api/creativeStudioClient.ts
```

The client attaches auth headers, has no React dependency, and does not add axios coupling.

## Delivery Gate

Run the gate:

```text
python scripts/creative_studio_external_video_gate.py
```

Expected evidence file:

```text
.xagent_runtime/reports/creative-studio-external-video-gate.json
```

The report must keep:

- `status=passed`
- `dry_run=true`
- `mutation_performed=false`
- `network_mutation_performed=false`
- `full_release_claimed=false`

## Verification

Focused backend and delivery gate:

```text
python -m pytest tests/test_creative_studio.py tests/test_creative_studio_external_video_gate.py -q --no-cov
```

Default tool surface regression:

```text
python -m pytest tests/test_tools.py tests/enterprise/test_tools.py::test_build_default_tool_registry_registers_expected_tools tests/enterprise/test_tools.py::test_build_default_tool_registry_marks_write_tools_high_risk -q --no-cov
```

Frontend contract and build:

```text
cd frontend
npm run verify:creative-studio:contracts
npm run verify:creative-studio:contracts:json
npm run type-check
npm run build
npm run verify:panda:contracts
```

## Release Boundary

This is a feature-slice delivery, not a commercial RC promotion. Promotion still requires owner approval to mount the router, expose UI entry points, choose provider credentials, define cost limits, and run a real provider staging test.
