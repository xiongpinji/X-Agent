# Owner / Operator Commercial Delivery Input Request

Status: `waiting_owner_operator_refs`

Purpose: collect redaction-safe owner/operator references needed to unblock X-Agent commercial delivery. This document is an intake request only. It is not evidence, approval, deployment proof, or tag readiness.

Current target SHA:

```text
adbce7a93854870ef665fe03c39051491a90b9d6
```

If the owner approves a different SHA, provide the replacement SHA and approval ref first. All downstream refs must be bound to that approved SHA.

## Structured Return Template

Preferred return format:

- Fill `docs/owner-operator-commercial-delivery-input-template.json`.
- Save the completed copy as `.xagent_runtime/reports/owner-operator-commercial-delivery-input.json`.
- Keep every value redaction-safe. Do not paste secret values.

Local intake check after the returned refs are saved:

```powershell
uv run --isolated --python 3.11 python scripts\owner_operator_commercial_delivery_intake.py --input .xagent_runtime\reports\owner-operator-commercial-delivery-input.json --output .xagent_runtime\reports\owner-operator-commercial-delivery-intake.json --fail-blocked
```

This intake check is read-only with respect to external systems. It does not run owner gates, Stage3/prod, release gates, deploys, tags, pushes, or final gate. A passing intake only means the returned refs are ready for Review/F routing; it is not evidence completion or tag readiness.

## Redaction Boundary

Allowed:

- refs, URLs, SHAs, run IDs, artifact IDs, statuses, timestamps
- variable names, key names, object names, namespace names, workflow/job names
- image refs and immutable `sha256:` digests
- dashboard/query/trace/event/alert/log-search refs
- owner approval refs and approver identity refs

Forbidden:

- secret values, tokens, API keys, webhook secrets
- private keys, auth headers, cookies
- DSNs, connection strings, passwords
- raw credential logs
- Kubernetes Secret `.data`, base64 secret payloads, or decoded secret values

## Required Owner Gate Refs

### Provider

- Provider/backend name.
- Model name or model ref.
- Credential variable name only.
- Provider smoke/status ref.

### Feishu Webhook Contract

- Feishu app ID variable name.
- Feishu app secret variable name.
- Feishu encrypt key variable name.
- Webhook contract verification ref/status.

### GitHub Issue-to-PR Dry Run

- Disposable GitHub issue URL/ref.
- Repository ref.
- Dry-run status/ref proving no execute mutation.

### GitHub Execute Preflight

- GitHub token variable name only.
- Disposable issue URL/ref.
- Permission/preflight status ref.

### Hosted GitHub Actions Commercial RC

- Hosted workflow run URL or run ID.
- Head SHA used by the hosted run.
- Required job names and statuses.
- Artifact ID/URL and artifact digest refs.
- Evidence pack digest ref, if produced by the run.

### Owner Approval

- Explicit approval ref.
- Approval timestamp.
- Approver identity ref.
- Scope: SHA, environment, and release boundary approved.

## Required Stage3 / Production Refs

### External Endpoint And Smoke

- Public HTTPS endpoint.
- Health URL.
- Ready URL.
- External smoke run URL/ID.
- Status-code summary and timestamp.

### DNS / TLS / LB / Ingress

- Hostname.
- DNS record ref.
- TLS certificate ref and validity window.
- Ingress ref.
- Load balancer ref/address ref.
- Namespace/environment name.

### Deployed Image / Provenance

- Image ref.
- Immutable `sha256:` digest.
- Workload imageID/digest ref observed in the running environment.
- Provenance/SBOM refs.
- Deployment or rollout run ref.

### Runtime Bindings

Provide refs only, not values:

- DB binding ref.
- Redis binding ref.
- RabbitMQ binding ref.
- Qdrant binding ref.
- Neo4j binding ref.
- Langfuse binding/ref.
- Sentry event/ref.

### ExternalSecret / ESO

- External Secrets Operator Ready ref.
- ClusterSecretStore object name and Ready ref.
- ExternalSecret object names and Ready/Synced refs.
- Target Secret object names.
- Expected key names only.
- Workload `secretKeyRef` refs.

### Observability

- Metrics dashboard/query refs.
- Alert rule and alert test/firing refs.
- Sanitized log-search ref with run/correlation ID.
- RabbitMQ health ref.
- Langfuse trace ref.
- Sentry event ref.

### Rollback

- Rollback rehearsal run URL/ID.
- Rollback target ref.
- Pre-rollback digest.
- Post-rollback digest.
- Post-rollback health/ready refs.
- Start and completion timestamps.

### Production Readiness Acceptance

- Owner prod-readiness acceptance ref.
- Acceptance timestamp.
- Accepted SHA/environment/ref boundary.

## Required Panda / Frontend Release Decisions

These are decision refs, not QA proof:

- `frontend/scripts/panda-qa-smoke.mjs`: include / defer / exclude.
- Canonical role PNG set decision.
- Modified role PNG include / exclude / defer decision.
- Untracked `frontend/src/panda/assets/roles/xagent-reference-*.png` include / exclude / defer decision.
- Smoke artifact treatment: local evidence only or release evidence.
- Allowed release notes wording for Panda/browser claims.
- Screenshot review refs.
- BFF contract refs.
- Auth/tenant refs.
- Accessibility/security messaging refs.
- Asset manifest refs.
- Release manifest refs.

## Routing After Submission

1. D line performs owner gate intake completeness and redaction check.
2. E line performs Stage3/prod admissibility triage.
3. M line performs Panda/frontend decision intake.
4. Review audits admissibility and overclaim risk.
5. F independently verifies accepted refs/artifacts.
6. B release consistency refresh is considered only after stable release boundary plus verified owner/Stage3 refs exist.
7. Mainline receives the accepted state.
8. Final gate with `--require-ready-to-tag` is run only after owner gates and Stage3/prod evidence are complete.

## Current Non-Claims

- Not commercial-ready.
- Not GA-ready.
- Not production-ready.
- Not ready-to-tag.
- Owner gates are not complete.
- Stage3/prod proof is not complete.
- Panda/frontend release payload is not approved.
