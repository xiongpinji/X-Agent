# X-Agent SLO/SLI Definitions

## Overview

This document defines Service Level Objectives (SLOs) and Service Level Indicators (SLIs) for X-Agent. SLOs represent commitments to end users; SLIs are the measurable metrics used to track compliance.

**Current effective date**: 2026-06-13  
**Review cycle**: Quarterly (aligned with product releases)

---

## Service Level Objectives (SLOs)

### 1. Availability / Uptime (99.9%)

**Definition**: Percentage of time the API responds to requests without 5xx errors.

| Metric | Target | Window | Alert Threshold |
|--------|--------|--------|-----------------|
| **Availability** | 99.9% | Monthly | Error rate > 0.1% for 5m → critical |
| **Error budget** | 43 minutes/month | 30 days | — |

**Rationale**: Enterprise SaaS standard. 99.9% allows ~43 minutes of downtime per month (vs. 99% = 7.2 hours).

**Exclusions**:
- Scheduled maintenance (announced >48h in advance)
- Client-side errors (4xx)
- Third-party service failures (LLM provider outages)

---

### 2. Latency / Response Time (P99 < 500ms)

**Definition**: 99th percentile of HTTP request latency end-to-end.

| Metric | Target | Window | Alert Threshold |
|--------|--------|--------|-----------------|
| **P99 Latency** | < 500ms | 5-minute rolling | > 500ms for 5m → warning; > 1s for 2m → critical |
| **P95 Latency** | < 300ms | 5-minute rolling | > 300ms for 10m → info (trend) |

**Rationale**: 
- 500ms P99 supports interactive agent operations (CLI, chat, API calls).
- 300ms P95 targets typical happy-path performance.

**Included operations**:
- REST API request/response (e.g., /api/v1/agents/run)
- Web dashboard page loads
- Chat message send/receive roundtrip

**Excluded operations** (measured separately):
- Async agent background tasks (LLM inference, long workflows)

---

### 3. Agent Task Success Rate (> 90%)

**Definition**: Percentage of agent execution tasks that complete without terminal failure.

| Metric | Target | Window | Alert Threshold |
|--------|--------|--------|-----------------|
| **Task Success** | ≥ 90% | 10-minute rolling | < 90% for 10m → warning; < 75% for 5m → critical |

**Rationale**: 
- Accounts for agent-side retries, LLM inference errors, tool failures.
- 90% baseline allows for transient external issues (API rate limits, network blips).

**Task states**:
- ✅ **Completed**: Agent achieved terminal success (result returned to user)
- ⚠️ **Paused**: Awaiting user input or manual retry (not counted as failure)
- ❌ **Failed**: Terminal failure (exhausted retries, unrecoverable error)
- ⏳ **Timeout**: Exceeded max duration (counts as failure)

---

### 4. Request Success Rate (API Contract Fulfilled)

**Definition**: Percentage of API requests that succeed within the defined service contract.

| Metric | Target | Window | Alert Threshold |
|--------|--------|--------|-----------------|
| **Request Success** | ≥ 99% | 5-minute rolling | < 99% for 5m → warning; < 98% for 2m → critical |

**Includes**:
- 2xx (success)
- 3xx (redirect, accepted for async)
- 4xx (user error; counts as success — request fulfilled)
- ❌ 5xx (server error; counts as failure)

---

### 5. Vector Search Latency (P95 < 100ms)

**Definition**: 99th percentile of latency for vector similarity search (Qdrant).

| Metric | Target | Window | Alert Threshold |
|--------|--------|--------|-----------------|
| **Vector Search P95** | < 100ms | 5-minute rolling | > 100ms for 5m → warning |
| **Vector Search P99** | < 250ms | 5-minute rolling | > 250ms for 2m → warning |

**Rationale**: 
- Memory retrieval is on the critical path for agent context enrichment.
- <100ms P95 keeps end-to-end latency within budget.

---

### 6. LLM Inference Availability (99%)

**Definition**: Percentage of LLM requests that receive a response (not counting timeout/retry exhaustion).

| Metric | Target | Window | Alert Threshold |
|--------|--------|--------|-----------------|
| **LLM Success Rate** | ≥ 99% | 5-minute rolling | < 99% for 5m → warning; < 95% for 2m → critical |

**Rationale**: 
- LLM providers (OpenAI, Anthropic) have their own SLOs (~99.99%), so XAgentTarget at 99%.
- Accounts for provider rate limiting, overload, temporary outages.

**Not included in API availability** (separate SLI) due to third-party dependency.

---

## Service Level Indicators (SLIs)

### Request-Level SLIs

#### SLI-1.1: HTTP Request Success Rate

**Definition**: Count of requests with status != 5xx / total requests.

**Collection**:
```promql
sum(rate(http_requests_total{status!~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))
```

**Alerts**:
- Warning: < 99.5% for 5 minutes
- Critical: < 99% for 2 minutes

**Collection points**:
- Prometheus via middleware (FastAPI)
- Exported by `/metrics` endpoint

---

#### SLI-1.2: HTTP Latency P99

**Definition**: 99th percentile of request duration.

**Collection**:
```promql
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

**Alerts**:
- Warning: > 500ms for 5 minutes
- Critical: > 1.0s for 2 minutes

**Tracking**:
- Exported as histogram `http_request_duration_seconds_bucket`
- Includes router → handler → response serialization

**Exclusions**:
- Async agent execution (fire-and-forget)
- WebSocket upgrade handshake (long-poll if applicable)

---

### Agent-Level SLIs

#### SLI-2.1: Agent Task Completion Rate

**Definition**: Agent tasks with status ∈ {completed, paused} / total tasks.

**Collection**:
```promql
sum(rate(agent_tasks_total{status=~"completed|paused"}[10m])) /
sum(rate(agent_tasks_total[10m]))
```

**Alerts**:
- Warning: < 90% for 10 minutes
- Critical: < 75% for 5 minutes

**Task status enum**:
- `pending`, `running`, `completed`, `failed`, `timeout`, `paused`

**Tracking**:
- Emitted by agent execution engine at task lifecycle boundaries
- Includes retries within single task run

---

#### SLI-2.2: Agent Task Duration P95

**Definition**: 95th percentile of agent task execution time.

**Collection**:
```promql
histogram_quantile(0.95, rate(agent_task_duration_seconds_bucket[10m]))
```

**Baseline**: ~10–30 seconds (single agent iteration).

---

### System-Level SLIs

#### SLI-3.1: Database Connection Pool Utilization

**Definition**: (Used connections) / (Total pool size).

**Collection**:
```promql
xagent:db:connection_utilization:ratio
```

**Alerts**:
- Warning: > 0.9 for 2 minutes
- Critical: >= 1.0 for 1 minute

**Action**: Auto-scale pool or reject new connections.

---

#### SLI-3.2: Cache Hit Rate

**Definition**: Cache hits / (hits + misses).

**Collection**:
```promql
xagent:cache:hit_rate:5m = 
  redis_keyspace_hits_total / 
  (redis_keyspace_hits_total + redis_keyspace_misses_total)
```

**Target**: > 50% (typical for agent memory)

**Alerts**:
- Warning: < 50% for 10 minutes
- Critical: < 30% for 5 minutes

---

#### SLI-3.3: Vector Database Latency (P95)

**Definition**: P95 latency of vector search queries.

**Collection**:
```promql
histogram_quantile(0.95, rate(qdrant_search_duration_seconds_bucket[5m]))
```

**Target**: < 100ms

---

### Audit & Compliance SLIs

#### SLI-4.1: Audit Log Write Success Rate

**Definition**: Successful audit log writes / total writes.

**Collection**:
```promql
sum(rate(audit_write_total{status="ok"}[5m])) /
sum(rate(audit_write_total[5m]))
```

**Target**: 100% (audit writes are critical; failure is a breach).

**Alerts**:
- Critical: Any failure (rate > 0 for 1 minute)

---

#### SLI-4.2: Rate Limiting Enforcement

**Definition**: Requests throttled due to rate limits / total requests.

**Collection**:
```promql
sum(rate(rate_limit_exceeded_total[5m])) /
sum(rate(http_requests_total[5m]))
```

**Target**: < 0.1% under normal load (< 1 per 1000 requests).

**Alerting**: > 100 events/sec → spam or attack detected.

---

## Error Budget Policy

### Error Budget Allocation

For a **99.9% monthly SLO** (43 minutes/month):

| Period | Budget | Alert Threshold |
|--------|--------|-----------------|
| **Daily** | 4.3 minutes | ~50 errors/hour |
| **Weekly** | 30 minutes | ~6 errors/hour avg |
| **Monthly** | 43 minutes | — |

**Policy**:
- Error budget tracked continuously in Prometheus.
- When budget approaches 30% consumed: escalate to on-call.
- When budget 80% consumed: start incident severity increase.
- When budget 100% consumed by week 3: mandatory incident review + preventive action.

### Incident Response

1. **Detection**: Alert fires (e.g., error rate > 0.1%)
2. **Page on-call**: Via PagerDuty (severity = alert severity)
3. **Triage** (5 min): Gather logs, check recent deployments, external dependencies
4. **Mitigation** (15 min): Rollback, failover, or scale-out
5. **Resolution** (ongoing): RCA, preventive actions, post-incident review

---

## SLI Reporting & Dashboards

### Grafana Dashboards

1. **SLO Compliance** (`SLO_Overview.json`)
   - Monthly uptime trend
   - Error budget burndown
   - By-component latency distribution
   - Request success rate by status code

2. **Agent Performance** (`Agent_Health.json`)
   - Task success rate (real-time)
   - Task duration percentiles
   - Failure mode breakdown (timeout vs. error vs. retry exhausted)

3. **System Health** (`Infrastructure.json`)
   - Database latency + connection pool
   - Redis memory + eviction rate
   - Vector DB latency + search throughput
   - Disk/memory/CPU trends

### Weekly Report

Generated by Prometheus rules + Langfuse analytics:

```
✅ Availability: 99.92% (Target: 99.9%) — ON TRACK
✅ P99 Latency: 420ms (Target: 500ms) — AHEAD OF TARGET
⚠️  Agent Success: 88% (Target: 90%) — AT RISK
✅ Cache Hit Rate: 62% (Target: 50%) — EXCEEDING
✅ Audit Write: 100% (Target: 100%) — OK
🔴 LLM Provider Availability: 98% (Target: 99%) — VENDOR ISSUE
```

---

## Quarterly Review Checklist

Every quarter (Q1, Q2, Q3, Q4):

- [ ] Analyze error budget consumption trends
- [ ] Update SLO targets based on capacity changes
- [ ] Review new components (new channels, new integrations) for SLI coverage
- [ ] Audit alert tuning (false positives, missed incidents)
- [ ] Incorporate user feedback on latency/availability experience
- [ ] Update incident playbooks with learned lessons
- [ ] Document any temporary SLO exemptions or carve-outs

---

## Dependency SLOs

X-Agent depends on external services with their own SLOs:

| Dependency | SLO | Notes |
|-----------|-----|-------|
| **OpenAI API** | 99.99% | Upstream SLO; XAgent targets 99% to account for retry exhaustion |
| **Anthropic API** | 99.9% | Similar to OpenAI |
| **PostgreSQL** | 99.95% | On-prem or RDS; customer responsibility |
| **Qdrant** | 99.9% | Vector DB; consider replicated setup in production |
| **Redis** | 99.95% | Cache; highly available (Cluster or Sentinel) recommended |

**X-Agent SLO is bounded by weakest dependency.** For 99.9% overall, ensure all dependencies ≥ 99.9%.

---

## Future Enhancements (Q3 2026+)

- [ ] **Multi-region SLO**: Separate targets for each geographic region
- [ ] **Per-tenant SLOs**: Tiered SLAs (Premium, Standard, Free)
- [ ] **Percentile-based contracts**: SLI triples (P50, P95, P99) in API contract
- [ ] **Economic penalties**: Automatic credits for SLO breaches (if offered)
- [ ] **Cost optimization**: Track cost per unit of SLI met (cost/availability %)

---

## References

- [Google SRE Book: SLOs](https://sre.google/sre-book/service-level-objectives/)
- [Prometheus Monitoring](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)
- X-Agent `monitoring/alert_rules.yml` (alert definitions)
- X-Agent `monitoring/prometheus.yml` (metrics scrape config)

---

**Last updated**: 2026-06-13  
**Owner**: Platform SRE Team  
**Stakeholders**: Product, Engineering, Customer Success
