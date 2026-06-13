# X-Agent API Versioning Strategy

## Overview

X-Agent maintains **multiple API versions** to support gradual feature evolution, breaking changes, and smooth client migrations. This document describes the versioning scheme, deprecation policy, and migration guidance.

**Current status**: v1 (stable), v2 (preview)  
**Last updated**: 2026-06-13

---

## Versioning Model

### Version Lifecycle

```
   PREVIEW           STABLE            DEPRECATED        SUNSET
      |                |                   |                |
  Introduced      Released for          Marked for         |
  (v2 beta)     general use (v1)     removal (6mo)     Removed
      |                |                   |                |
    [------ 3 months ------][------ 6 months ------][--- final 6mo ---]
```

**Key dates**:
- **PREVIEW**: Experimental. May have breaking changes. Not production-ready.
- **STABLE**: Production-ready. Backward compatibility guaranteed for 12 months minimum.
- **DEPRECATED**: Marked for removal. Clients must migrate. 6-month notice period.
- **SUNSET**: Removed. No longer accepts requests. Redirects to successor version.

### Version Numbering

- **v1**: Latest stable API. Ships with every release. 100% backward compatibility within v1.
- **v2**: Preview API. New features, breaking changes allowed. Graduates to stable in ~3 months.
- **v3+**: Future versions, following same lifecycle.

**Format**: `/api/{version}/{resource}` (e.g., `/api/v1/agents/run`, `/api/v2/workflows/advanced`).

---

## Current API Versions

### v1 (Stable)

**Status**: Production-ready, actively supported

**Base URL**: `https://api.xagent.ai/api/v1`

**Features**:
- ✅ Agent execution (`/agents/run`, `/agents/pause`, `/agents/resume`)
- ✅ Tool execution (`/tools/execute`, `/tools/list`)
- ✅ Memory operations (`/memory/store`, `/memory/retrieve`)
- ✅ Skills marketplace (`/skills/search`, `/skills/install`)
- ✅ Billing & usage (`/billing/usage`, `/billing/current-plan`)
- ✅ Audit logs (`/audit/list`)
- ✅ WebSocket support for streaming

**Support**: Through 2027-06-13 (12 months from v2 stable release).

**Rate limits**: 1000 req/min per API key.

---

### v2 (Preview)

**Status**: Experimental, subject to breaking changes

**Base URL**: `https://api.xagent.ai/api/v2`

**New features** (not in v1):
- ✨ Parallel agent execution (`/agents/run-parallel`)
- ✨ Batch tool execution (`/tools/execute-batch`)
- ✨ Memory fusion (`/memory/fusion`, AI-powered deduplication)
- ✨ Advanced workflows (`/workflows/create`, DAG-based execution)
- ✨ Multi-channel delivery (`/channels/send`, unified chat platform support)
- ✨ Streaming responses with metadata
- ✨ Response compression (gzip, brotli)

**Breaking changes vs v1**:
| Endpoint | Change | Migration |
|----------|--------|-----------|
| `/agents/run` | `agent_type` → `role_type` enum | Rename field: `{"agent_type": "coder"}` → `{"role_type": "CODER"}` |
| `/tools/execute` | `tool_id` now required (was optional with name) | Always provide tool_id; use `/tools/search` to lookup by name |
| `/memory/store` | Response includes vector_id in addition to id | Update client to handle new field (optional, backward-safe) |
| `/workflows/*` | New endpoint family (not in v1) | Use v1 `/agents/run` for simple cases; v2 for DAGs |

**Graduated to stable**: ~September 2026 (after 3 months of production usage).

**Rate limits**: 500 req/min per API key (preview tier).

---

## Version Negotiation

Client must specify API version via one of:

### 1. URL Path (Recommended)
```
GET /api/v2/agents/run
```

### 2. Accept Header
```
Accept: application/vnd.xagent.v2+json
```

### 3. X-API-Version Header
```
X-API-Version: v2
```

**Priority** (if multiple specified):
1. URL path (highest priority)
2. Accept header
3. X-API-Version header
4. Default (v1)

**Example**:
```bash
# Request to v2 (URL takes precedence)
curl -H "X-API-Version: v1" \
     -H "Accept: application/vnd.xagent.v1+json" \
     https://api.xagent.ai/api/v2/agents/run

# Uses v2 (from URL path)
```

---

## Response Headers

All responses include version metadata:

```http
HTTP/1.1 200 OK
X-API-Version: v1
X-API-Supported-Versions: v1, v2
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1623456789

{
  "agent_id": "...",
  "status": "running",
  ...
}
```

### Deprecation Warning Headers

If endpoint is deprecated:

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Fri, 13 Jun 2027 00:00:00 GMT
Link: </api/v2/agents>; rel="successor-version"
X-API-Migration-Guide: https://docs.xagent.ai/api/migration-guides
X-API-Warning: API version v2 is preview; use v1 for stable features
```

---

## Deprecation & Sunset Policy

### Timeline

1. **Month 0**: Announce deprecation via:
   - Deprecation header in API responses
   - Email to all registered API keys
   - Blog post + migration guide

2. **Month 0-6**: Grace period for client migration
   - Endpoint continues working
   - Returns deprecation warnings
   - Support team assists with migration

3. **Month 6**: Sunset announced (final 6-month notice)
   - Returns 410 Gone or 308 Permanent Redirect
   - Logs migration attempts for analytics

4. **Month 12**: Endpoint permanently removed

### Example: Deprecating v1 /agents/list

**Announced**: 2026-06-01  
**Sunset date**: 2027-06-01 (12 months)  
**Alternative**: `/api/v2/agents` (GET with filter query params)

```python
# From backend/app/api/versioning.py
mark_endpoint_deprecated(
    path="/api/v1/agents/list",
    sunset_date=datetime(2027, 6, 1),
    alternative="/api/v2/agents",
)
```

Response during grace period:
```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Wed, 01 Jun 2027 00:00:00 GMT
Link: </api/v2/agents>; rel="successor-version"
X-API-Migration-Guide: https://docs.xagent.ai/api/v1-to-v2-migration

[agent list response]
```

---

## Feature Flags

### Version-Gated Features

Features may be available only in certain API versions:

```python
# backend/app/api/versioning.py
VERSION_FEATURES = {
    "v1": {
        "agents_run",
        "tools_execute",
        "memory_store",
    },
    "v2": {
        "agents_run",
        "agents_parallel",  # NEW in v2
        "tools_execute",
        "tools_batch",      # NEW in v2
        "memory_store",
        "memory_fusion",    # NEW in v2
    },
}
```

### Decorator-Based Gating

Endpoints can be gated to minimum version:

```python
from backend.app.api.versioning import version_required, feature_flag

@app.post("/api/v2/agents/run-parallel")
@version_required("v2")
async def parallel_run(request: ParallelRunRequest) -> dict:
    """Requires API v2 or later."""
    ...

@app.post("/api/v2/workflows/create")
@feature_flag("workflows_advanced")
async def create_workflow(request: WorkflowRequest) -> dict:
    """Requires workflows_advanced feature (v2+)."""
    ...
```

Attempting to call a gated endpoint from v1:

```bash
curl -H "X-API-Version: v1" \
     https://api.xagent.ai/api/v2/agents/run-parallel

# Response
HTTP/1.1 403 Forbidden
{
  "error": "Feature requires API v2 or later (using v1)",
  "upgrade_link": "https://docs.xagent.ai/api/upgrade"
}
```

---

## Migration Guides

### v1 → v2 (Planned for Q3 2026)

#### Breaking Changes Summary

| Change | v1 | v2 | Migration |
|--------|----|----|-----------|
| Agent execution | Sequential (1 at a time) | Parallel supported | Use `/agents/run-parallel` |
| Tool batching | Single tool per request | Batch requests supported | Use `/tools/execute-batch` |
| Memory format | JSON-only | Vector + JSON + structured | Responses include vector embeddings automatically |
| Workflow | Simple DAG implied | Explicit DAG definition | Use new `/workflows/*` endpoints |

#### Step-by-Step Migration

**Step 1: Update SDK/Client**
```bash
# Install latest client
pip install xagent>=2.0.0  # includes v2 support
npm install xagent@2.0.0   # JavaScript client
```

**Step 2: Update Endpoints (non-breaking)**
```python
# Old (v1)
agent = client.agents.run(agent_type="coder", task="write tests")

# New (v2) - backward compatible with v1 names
agent = client.agents.run(role_type=AgentRole.CODER, task="write tests")
```

**Step 3: Use New v2 Features**
```python
# Parallel execution (v2 only)
agents = client.agents.run_parallel(
    roles=["coder", "reviewer", "tester"],
    task="implement feature X",
)

# Wait for all
results = await agents.wait_all()
```

**Step 4: Switch to v2 endpoint**
```python
# At deployment time
client = XAgentClient(
    api_version="v2",  # Switch from default "v1"
    api_key="...",
)
```

**Step 5: Monitor and Rollback**
```bash
# Gradual rollout: 10% traffic to v2 for 1 week
# Monitor error rates, latency, business metrics
# If issues, rollback: client.api_version = "v1"
```

### Parallel v1 and v2 Support (During Grace Period)

You can run both versions simultaneously during the migration window:

```python
from xagent import XAgentClient

v1_client = XAgentClient(api_version="v1", api_key="...")
v2_client = XAgentClient(api_version="v2", api_key="...")

# Old code path (still works)
legacy_result = v1_client.agents.run(agent_type="coder", ...)

# New code path (parallel)
modern_result = v2_client.agents.run(role_type=AgentRole.CODER, ...)
```

---

## API Health & Status Endpoint

### GET /api/versions

Returns current versioning state (works on all versions):

```bash
curl https://api.xagent.ai/api/versions
```

```json
{
  "current_stable": "v1",
  "supported_versions": {
    "v1": {
      "status": "stable",
      "features": ["agents_run", "tools_execute", "memory_store", "skills_marketplace"]
    },
    "v2": {
      "status": "preview",
      "features": [
        "agents_run",
        "agents_parallel",
        "tools_execute",
        "tools_batch",
        "memory_store",
        "memory_fusion",
        "workflows_advanced",
        "channels_multi"
      ]
    }
  },
  "deprecated_endpoints": [
    {
      "path": "/api/v1/agents/list",
      "status": "deprecated",
      "sunset": "2027-06-01T00:00:00Z",
      "alternative": "/api/v2/agents"
    }
  ],
  "breaking_changes": {
    "v1->v2": [
      {
        "endpoint": "/agents/run",
        "change": "agent_type parameter renamed to role_type",
        "migration": "Rename request field: {'agent_type': 'x'} -> {'role_type': 'x'}"
      },
      ...
    ]
  }
}
```

---

## Best Practices

### For API Users

1. **Specify version explicitly**: Don't rely on default versioning
   ```bash
   # Good
   curl https://api.xagent.ai/api/v1/agents/run
   
   # Avoid
   curl https://api.xagent.ai/agents/run
   ```

2. **Monitor deprecation headers**: Parse `Deprecation` and `Sunset` headers
   ```python
   if response.headers.get("Deprecation") == "true":
       migration_url = response.headers.get("X-API-Migration-Guide")
       logger.warning(f"Endpoint is deprecated. See: {migration_url}")
   ```

3. **Plan for version upgrades**: Schedule quarterly reviews of your API version
   ```python
   # Every quarter, check:
   # GET /api/versions -> check for new features, deprecations
   # Update SDK if new features are beneficial
   ```

4. **Use SDKs for version abstraction**: Let SDK handle compatibility
   ```python
   # SDK automatically picks stable version
   from xagent import XAgentClient
   client = XAgentClient(api_key="...")  # Uses v1 by default
   ```

### For API Developers (X-Agent Team)

1. **Add versioning middleware early**: Every new feature should consider version gating
   ```python
   @app.post("/api/v2/workflows/create")
   @feature_flag("workflows_advanced")
   async def create_workflow(...):
       ...
   ```

2. **Document breaking changes**: Update `BREAKING_CHANGES` in versioning.py
   ```python
   BREAKING_CHANGES = {
       "v1->v2": [
           {
               "endpoint": "/agents/run",
               "change": "...",
               "migration": "...",
           },
       ],
   }
   ```

3. **Announce deprecations 6+ months ahead**: Use `mark_endpoint_deprecated()`
   ```python
   # At code review time
   mark_endpoint_deprecated(
       path="/api/v1/old-endpoint",
       sunset_date=datetime(2027, 6, 1),
       alternative="/api/v2/new-endpoint",
   )
   ```

4. **Monitor API usage during grace periods**: Track deprecation adoption
   ```python
   # Query to find v1-only clients still using old endpoints
   SELECT client_id, COUNT(*) as requests
   FROM api_requests
   WHERE endpoint = "/api/v1/agents/list"
   AND timestamp > NOW() - INTERVAL '1 month'
   GROUP BY client_id
   ORDER BY requests DESC;
   ```

---

## Future Roadmap

### v2 Graduation (Q3 2026)

- [ ] Reach 50% production traffic on v2
- [ ] Validate performance & reliability under load
- [ ] Graduate v2 to stable (STABLE status)
- [ ] Begin 6-month grace period for v1 deprecation

### v3 Planning (Q4 2026)

- [ ] Design new architecture (e.g., multi-agent orchestration, distributed DAGs)
- [ ] Open v3 for preview
- [ ] Incremental feature rollout

### SaaS Tiers & Rate Limits (2027)

- [ ] Separate rate limits by subscription tier
- [ ] Premium: unlimited rate limit, priority support
- [ ] Standard: 1000 req/min
- [ ] Free: 100 req/min

---

## References

- [HTTP Semantics: Deprecation (RFC 8594)](https://www.rfc-editor.org/rfc/rfc8594.html)
- [HTTP Semantics: Sunset (RFC 7231)](https://www.rfc-editor.org/rfc/rfc7231.html)
- [Semantic Versioning](https://semver.org/)
- [API Versioning Best Practices - AWS](https://docs.aws.amazon.com/apigateway/latest/developerguide/versioning-a-rest-api.html)
- X-Agent `backend/app/api/versioning.py` (implementation)
- X-Agent `/api/versions` endpoint (live status)

---

**Last updated**: 2026-06-13  
**Owner**: API Platform Team  
**Stakeholders**: Product, Engineering, Customer Success
