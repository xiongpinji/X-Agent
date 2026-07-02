# Creative Studio External Video API-only Delivery

## Scope

This slice gives X-Agent a Creative Studio video-generation boundary that can call an external protocol API without requiring local ComfyUI, local video models, or user GPU capacity.

It intentionally does not choose the final image-generation model or video-generation model. Those providers are matched later when the owner decides which paid API, internal gateway, or partner model endpoint to use.

The implementation is intentionally opt-in:

- Creative Studio is not mounted in `backend/app/main.py`.
- Creative Studio tools are not added to `build_default_tool_registry`.
- External video calls require explicit `human_review_approved=true`.
- Reviewed execution also requires a principal with `workflow:control`.
- The workflow endpoint defaults to dry-run planning and does not call providers unless `execute=true`.

## Provider Configuration

Set these environment variables only in the runtime that owns the external protocol call:

```text
XAGENT_CREATIVE_VIDEO_API_URL=https://api.your-video-gateway.invalid/v1/video/generate
XAGENT_CREATIVE_VIDEO_API_KEY=...
XAGENT_CREATIVE_VIDEO_PROVIDER=protocol-video
XAGENT_CREATIVE_VIDEO_MODEL=matched-later
```

Status responses expose only redacted configuration state. Raw API URL and raw API key are not returned. The URL must be an external HTTPS endpoint; localhost, private-network endpoints, and ComfyUI-style local providers are rejected before any provider call.

The current protocol payload is intentionally small and provider-neutral:

```json
{
  "prompt": "<compiled shot video prompt>",
  "model": "<configured model or request override>",
  "duration_seconds": 4,
  "aspect_ratio": "9:16",
  "provider": "protocol-video",
  "metadata": {}
}
```

Accepted response references are also provider-neutral: `video_url`, `output_url`, `url`, `download_url`, `output`, or an async job reference such as `job_id`, `id`, or `request_id`.

## Local Endpoints

These endpoints live under the Creative Studio router only:

```text
GET  /api/v1/creative-studio/video-provider-status
POST /api/v1/creative-studio/shot-video
POST /api/v1/creative-studio/video-workflow
```

`/video-provider-status` reports whether protocol config exists and whether human review is required.

`/shot-video` runs a single external protocol video request only after human review approval. Without approval it fails closed with `provider_api_call_attempted=false`.

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

This is a feature-slice delivery, not a commercial RC promotion. Promotion still requires owner approval to mount the router, expose UI entry points, choose image/video provider credentials, define cost limits, map the provider-specific request/response fields, and run a real provider staging test.
