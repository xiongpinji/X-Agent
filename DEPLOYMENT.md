# X-Agent Deployment Guide

Complete guide for deploying X-Agent using the TypeScript SDK and Helm charts.

## Deliverables Overview

This deployment package includes:

### 1. TypeScript SDK (`sdk-ts/`)
Pilot/RC Node.js/TypeScript SDK package for X-Agent integration. It is not GA
or production-readiness evidence without the Stage 5 evidence gates.

**Key Components:**
- `XAgent` client class with full API support
- Type definitions for all data structures
- Error handling hierarchy
- Task polling with exponential backoff
- Comprehensive documentation

**Installation:**
```bash
npm install @xagent/sdk
```

**Quick Example:**
```typescript
import { XAgent } from '@xagent/sdk';

const apiKey = process.env.XAGENT_API_KEY;
if (!apiKey) {
  throw new Error('Set XAGENT_API_KEY from your secret manager or CI secret store');
}

const agent = new XAgent({
  baseUrl: process.env.XAGENT_URL || 'http://localhost:8000',
  apiKey,
});

const task = await agent.submitTask('Fix the login bug');
const result = await task.wait();
console.log(`PR created: ${result.pr_url}`);
```

### 2. Helm Chart (`deployment/helm/`)
Multi-environment Kubernetes deployment with production-grade configurations.

**Environments Supported:**
- **Development** (`values.yaml`) - 1 replica, relaxed limits
- **Staging** (`values-staging.yaml`) - 2 replicas, moderate scaling
- **Production** (`values-production.yaml`) - 3+ replicas, strict limits, HA

## Quick Start

### Prerequisites
- Node.js 18+ (for SDK)
- Kubernetes 1.24+ (for Helm)
- Helm 3.0+
- PostgreSQL 14+
- Redis (optional)

### SDK Setup

```bash
cd sdk-ts

# Install dependencies
npm install

# Build TypeScript
npm run build

# Run tests
npm run test

# Use in your project
npm install /path/to/sdk-ts
```

### Kubernetes Deployment

#### Step 1: Prepare Secrets

```bash
# Load secrets into the current shell from your secret manager.
# Do not commit secret values to this repository or paste them into docs.
export DB_URL="<secret-manager-ref:database-url>"
export API_KEY="<secret-manager-ref:xagent-api-key>"
export LANGFUSE_KEY="<secret-manager-ref:langfuse-public-key>"
export LANGFUSE_SECRET="<secret-manager-ref:langfuse-secret-key>"
```

#### Step 2: Deploy to Development

```bash
helm install xagent ./deployment/helm \
  --namespace xagent-dev \
  --create-namespace \
  --set-string secrets.databaseUrl="$DB_URL" \
  --set-string secrets.apiKey="$API_KEY"
```

#### Step 3: Deploy to Staging

```bash
helm install xagent ./deployment/helm \
  -f ./deployment/helm/values-staging.yaml \
  --namespace xagent-staging \
  --create-namespace \
  --set-string secrets.databaseUrl="$DB_URL" \
  --set-string secrets.apiKey="$API_KEY"
```

#### Step 4: Deploy to Production

```bash
helm install xagent ./deployment/helm \
  -f ./deployment/helm/values-production.yaml \
  --namespace xagent-prod \
  --create-namespace \
  --set replicaCount=3 \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="api.x-agent.dev" \
  --set-string secrets.databaseUrl="$DB_URL" \
  --set-string secrets.apiKey="$API_KEY" \
  --set-string secrets.langfusePublicKey="$LANGFUSE_KEY" \
  --set-string secrets.langfuseSecretKey="$LANGFUSE_SECRET"
```

## SDK API Documentation

### Client Initialization

```typescript
const apiKey = process.env.XAGENT_API_KEY;
if (!apiKey) {
  throw new Error('Set XAGENT_API_KEY from your secret manager or CI secret store');
}

const agent = new XAgent({
  baseUrl: process.env.XAGENT_URL || 'http://localhost:8000',
  apiKey,
  timeout: 30000,                     // Request timeout (ms)
});
```

### Core Methods

#### Health Check
```typescript
const health = await agent.health();
// Returns: { status, version, uptime_seconds, components }
```

#### Task Management
```typescript
// Submit task
const task = await agent.submitTask('Fix bug', {
  priority: 'high',
  timeout_seconds: 300,
  tags: ['urgent', 'backend'],
});

// Get task by ID
const task = await agent.getTask(taskId);

// List tasks
const tasks = await agent.listTasks(limit, offset);

// Cancel task
await agent.cancelTask(taskId);
```

#### Task Polling
```typescript
// Wait for completion (auto-polling)
const result = await task.wait(timeoutMs);

// Manual refresh
await task.refresh();

// Check status
if (task.isTerminal()) {
  if (task.isSuccess()) {
    console.log('Task succeeded:', task.getPRUrl());
  }
}
```

#### Chat Interface
```typescript
const response = await agent.chat('What tools are available?');
// Returns: { message, task_id, tool_calls, confidence }
```

#### Tool Discovery
```typescript
// List all tools
const tools = await agent.listTools();

// Filter by category
const browserTools = await agent.listTools({
  category: 'browser',
  limit: 50,
});

// Get tool details
const tool = await agent.getTool('github_create_pr');
```

#### Configuration
```typescript
// Get current config
const config = await agent.getConfig();

// Update config
await agent.updateConfig({
  timeout_ms: 60000,
  max_retries: 3,
});
```

## Helm Chart Configuration

### Values Structure

**Basic:**
```yaml
replicaCount: 1
image:
  repository: x-agent/x-agent
  tag: "1.0.0"
  pullPolicy: IfNotPresent
```

**Resources:**
```yaml
resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 256Mi
```

**Database:**
```yaml
database:
  host: postgres.default.svc.cluster.local
  port: 5432
  name: xagent
  poolSize: 10
```

**Ingress:**
```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.x-agent.dev
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: x-agent-tls
      hosts:
        - api.x-agent.dev
```

**Observability:**
```yaml
observability:
  metrics:
    enabled: true
  traces:
    enabled: true
    endpoint: "https://api.langfuse.com"
```

### Environment-Specific Overrides

**Staging Example:**
```yaml
replicaCount: 2
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
resources:
  limits:
    cpu: 500m
    memory: 512Mi
```

**Production Example:**
```yaml
replicaCount: 3
autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
resources:
  limits:
    cpu: 2000m
    memory: 2Gi
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution: [...]
```

## Operations

### Monitoring

```bash
# Check deployment
kubectl get deployment -n xagent-prod

# View pods
kubectl get pods -n xagent-prod

# Check pod logs
kubectl logs -f deployment/xagent -n xagent-prod

# Port forward
kubectl port-forward svc/xagent 8000:80 -n xagent-prod

# Check health
curl http://localhost:8000/health
```

### Scaling

```bash
# Manual scale
kubectl scale deployment xagent --replicas=5 -n xagent-prod

# Auto-scaling status
kubectl get hpa -n xagent-prod

# Metrics
kubectl top pods -n xagent-prod
kubectl top nodes
```

### Updates

```bash
# Update image
helm upgrade xagent ./deployment/helm \
  -f values-production.yaml \
  --set image.tag="1.1.0" \
  -n xagent-prod

# Rollback
helm rollback xagent 1 -n xagent-prod
```

## File Structure

```
X-Agent/
├── sdk-ts/                           # TypeScript SDK
│   ├── package.json                  # NPM configuration
│   ├── tsconfig.json                 # TypeScript config
│   ├── README.md                     # SDK documentation
│   └── src/
│       ├── index.ts                  # Main exports
│       ├── client.ts                 # XAgent client
│       ├── types.ts                  # Type definitions
│       ├── errors.ts                 # Error classes
│       └── task.ts                   # Task class
│
└── deployment/helm/                  # Helm Chart
    ├── Chart.yaml                    # Chart metadata
    ├── README.md                     # Chart documentation
    ├── values.yaml                   # Default values
    ├── values-staging.yaml           # Staging overrides
    ├── values-production.yaml        # Production overrides
    └── templates/
        ├── _helpers.tpl              # Template helpers
        ├── deployment.yaml           # K8s Deployment
        ├── service.yaml              # K8s Service
        ├── ingress.yaml              # K8s Ingress
        ├── configmap.yaml            # ConfigMap
        ├── secret.yaml               # Secret
        ├── hpa.yaml                  # HorizontalPodAutoscaler
        ├── pvc.yaml                  # PersistentVolumeClaim
        ├── pdb.yaml                  # PodDisruptionBudget
        ├── serviceaccount.yaml       # ServiceAccount
        ├── networkpolicy.yaml        # NetworkPolicy
        └── NOTES.txt                 # Post-install notes
```

## Examples

### Example 1: Node.js Integration

```typescript
import { XAgent } from '@xagent/sdk';

const agent = new XAgent({
  baseUrl: process.env.XAGENT_URL || 'http://localhost:8000',
  apiKey: process.env.XAGENT_API_KEY,
});

async function fixBug(description: string) {
  try {
    const task = await agent.submitTask(description, {
      priority: 'high',
      timeout_seconds: 600,
    });

    console.log(`Task created: ${task.id}`);

    const result = await task.wait(600000);

    if (result.status === 'success') {
      console.log(`Success! PR: ${result.pr_url}`);
      console.log(`Changes: ${result.changes_count}`);
    } else {
      console.error(`Task failed: ${result.error}`);
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

fixBug('Fix null pointer exception in auth handler');
```

### Example 2: Batch Processing

```typescript
const tasks = await Promise.all([
  agent.submitTask('Fix bug 1'),
  agent.submitTask('Fix bug 2'),
  agent.submitTask('Fix bug 3'),
]);

const results = await Promise.all(tasks.map(t => t.wait()));

results.forEach((result, i) => {
  console.log(`Task ${i + 1}: ${result.status} - ${result.pr_url}`);
});
```

### Example 3: Kubernetes Deployment with Monitoring

```bash
# Deploy with monitoring enabled
helm install xagent ./deployment/helm \
  -f values-production.yaml \
  --set observability.enabled=true \
  --set observability.metrics.enabled=true \
  --set observability.traces.enabled=true \
  -n xagent-prod

# Port forward to Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n monitoring

# View metrics at http://localhost:9090
```

## Troubleshooting

### Pod not starting
```bash
kubectl describe pod <pod-name> -n xagent-prod
kubectl logs <pod-name> -n xagent-prod
```

### Database connection failed
```bash
# Verify database URL secret
kubectl get secret xagent-secrets -n xagent-prod \
  -o jsonpath='{.data.database-url}' | base64 -d
```

### High memory usage
```bash
# Increase memory limit
helm upgrade xagent ./deployment/helm \
  --set resources.limits.memory="2Gi" \
  -n xagent-prod
```

### DNS/Network issues
```bash
# Enable network policy debugging
kubectl exec -it <pod-name> -n xagent-prod -- \
  curl http://postgres.default.svc.cluster.local:5432
```

## Support

- SDK Issues: https://github.com/x-agent/sdk-ts/issues
- Helm Chart Issues: https://github.com/x-agent/x-agent/issues
- Documentation: https://x-agent.dev/docs
- Community: https://discord.gg/x-agent

## License

MIT

## Changelog

### Version 1.0.0 (2026-06-14)
- Initial release of TypeScript SDK
- Pilot/RC Helm chart package with multi-environment support
- Full Kubernetes integration (HPA, PDB, NetworkPolicy)
- Observability support (Prometheus, Langfuse)
- Comprehensive documentation and examples
