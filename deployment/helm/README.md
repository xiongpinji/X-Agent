# X-Agent Helm Chart

Production-ready Helm chart for deploying X-Agent enterprise autonomous agent framework on Kubernetes.

## Features

- Multi-environment support (development, staging, production)
- High availability with pod disruption budgets
- Horizontal Pod Autoscaling
- Network policies for security
- Comprehensive health checks
- Observability integration (Prometheus, Langfuse)
- Persistent storage support
- RBAC integration
- ConfigMap and Secret management

## Prerequisites

- Kubernetes 1.24+
- Helm 3.0+
- PostgreSQL 14+ (external or via separate Helm chart)
- Redis (optional, external or via separate Helm chart)

## Quick Start

### Development (Default)

```bash
kubectl create namespace xagent-dev --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic xagent-secrets \
  --namespace xagent-dev \
  --from-literal=database-url="postgresql://user:pass@postgres:5432/xagent" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --from-literal=api-key="dev-api-key-change-me" \
  --from-literal=jwt-secret="dev-jwt-secret-change-me" \
  --from-literal=encryption-key="dev-encryption-key-change-me" \
  --from-literal=audit-hmac-secret="dev-audit-hmac-secret-change-me" \
  --from-literal=langfuse-public-key="" \
  --from-literal=langfuse-secret-key="" \
  --from-literal=sentry-dsn="" \
  --from-literal=workflow-event-rabbitmq-url="" \
  --dry-run=client -o yaml | kubectl apply -f -
helm install xagent ./deployment/helm \
  --namespace xagent-dev \
  --set secrets.enabled=true \
  --set secrets.create=false \
  --set-string secrets.existingSecretName=xagent-secrets
```

### Staging

```bash
kubectl create namespace xagent-staging --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic xagent-secrets \
  --namespace xagent-staging \
  --from-literal=database-url="$STAGING_DATABASE_URL" \
  --from-literal=redis-url="$STAGING_REDIS_URL" \
  --from-literal=api-key="$STAGING_API_KEY" \
  --from-literal=jwt-secret="$STAGING_JWT_SECRET" \
  --from-literal=encryption-key="$STAGING_ENCRYPTION_KEY" \
  --from-literal=audit-hmac-secret="$STAGING_AUDIT_HMAC_SECRET" \
  --from-literal=langfuse-public-key="$STAGING_LANGFUSE_PUBLIC_KEY" \
  --from-literal=langfuse-secret-key="$STAGING_LANGFUSE_SECRET_KEY" \
  --from-literal=sentry-dsn="$STAGING_SENTRY_DSN" \
  --from-literal=workflow-event-rabbitmq-url="$STAGING_WORKFLOW_EVENT_RABBITMQ_URL" \
  --dry-run=client -o yaml | kubectl apply -f -
helm install xagent ./deployment/helm -f ./deployment/helm/values-staging.yaml \
  --namespace xagent-staging \
  --set secrets.enabled=true \
  --set secrets.create=false \
  --set-string secrets.existingSecretName=xagent-secrets
```

When using `deployment/scripts/deploy.sh` for a staging route, keep the same
chart, release, and namespace assumptions explicit:

```bash
ENVIRONMENT=staging NAMESPACE=xagent-staging RELEASE_NAME=xagent ./deployment/scripts/deploy.sh
```

The script resolves the chart from the repository root as `deployment/helm` and
uses `deployment/helm/values-staging.yaml` for the staging values file.

### Production

```bash
kubectl create namespace xagent-prod --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic xagent-secrets \
  --namespace xagent-prod \
  --from-literal=database-url="$PROD_DATABASE_URL" \
  --from-literal=redis-url="$PROD_REDIS_URL" \
  --from-literal=api-key="$PROD_API_KEY" \
  --from-literal=jwt-secret="$PROD_JWT_SECRET" \
  --from-literal=encryption-key="$PROD_ENCRYPTION_KEY" \
  --from-literal=audit-hmac-secret="$PROD_AUDIT_HMAC_SECRET" \
  --from-literal=langfuse-public-key="$PROD_LANGFUSE_PUBLIC_KEY" \
  --from-literal=langfuse-secret-key="$PROD_LANGFUSE_SECRET_KEY" \
  --from-literal=sentry-dsn="$PROD_SENTRY_DSN" \
  --from-literal=workflow-event-rabbitmq-url="$PROD_WORKFLOW_EVENT_RABBITMQ_URL" \
  --dry-run=client -o yaml | kubectl apply -f -
helm install xagent ./deployment/helm -f ./deployment/helm/values-production.yaml \
  --namespace xagent-prod \
  --set replicaCount=3 \
  --set secrets.enabled=true \
  --set secrets.create=false \
  --set-string secrets.existingSecretName=xagent-secrets
```

## Configuration

### Environment Variables

Core settings via `values.yaml`:

```yaml
env:
  LOG_LEVEL: info
  DEBUG: "false"
  ENVIRONMENT: development
```

### Scaling

#### Auto-scaling (HPA)

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80
```

#### Manual scaling

```bash
kubectl scale deployment xagent --replicas=5
```

### Database Configuration

PostgreSQL connection via secrets:

```bash
kubectl create secret generic xagent-secrets \
  --namespace xagent-dev \
  --from-literal=database-url="postgresql://user:password@host:5432/dbname" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Redis Cache

Configure Redis connection:

```yaml
redis:
  host: redis.default.svc.cluster.local
  port: 6379
  db: 0
  password: null  # Set via secrets if needed
```

### Ingress Configuration

Enable and configure Ingress:

```yaml
ingress:
  enabled: true
  className: "nginx"
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

### Storage

Enable persistent storage:

```yaml
persistence:
  enabled: true
  size: 10Gi
  storageClassName: "fast-ssd"
  mountPath: /data
```

### Observability

#### Metrics (Prometheus)

```yaml
observability:
  metrics:
    enabled: true
    port: 8000
```

Scrape config for Prometheus:

```yaml
scrape_configs:
  - job_name: xagent
    static_configs:
      - targets: ['xagent:8000']
    metrics_path: /api/v1/metrics/prometheus
```

#### Traces (Langfuse)

```yaml
observability:
  traces:
    enabled: true
    endpoint: "https://api.langfuse.com"
```

Set Langfuse credentials:

```bash
kubectl create secret generic xagent-secrets \
  --namespace xagent-prod \
  --from-literal=langfuse-public-key="$PROD_LANGFUSE_PUBLIC_KEY" \
  --from-literal=langfuse-secret-key="$PROD_LANGFUSE_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

## Deployment Examples

### Minimal Development Deployment

```bash
kubectl create namespace xagent-dev --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic xagent-secrets \
  --namespace xagent-dev \
  --from-literal=database-url="postgresql://localhost:5432/xagent" \
  --from-literal=redis-url="redis://localhost:6379/0" \
  --from-literal=api-key="dev-key" \
  --from-literal=jwt-secret="dev-jwt-secret-change-me" \
  --from-literal=encryption-key="dev-encryption-key-change-me" \
  --from-literal=audit-hmac-secret="dev-audit-hmac-secret-change-me" \
  --from-literal=langfuse-public-key="" \
  --from-literal=langfuse-secret-key="" \
  --from-literal=sentry-dsn="" \
  --from-literal=workflow-event-rabbitmq-url="" \
  --dry-run=client -o yaml | kubectl apply -f -
helm install xagent ./deployment/helm \
  --namespace xagent-dev \
  --set secrets.enabled=true \
  --set secrets.create=false \
  --set-string secrets.existingSecretName=xagent-secrets
```

### High-Availability Production

```bash
helm install xagent ./deployment/helm -f ./deployment/helm/values-production.yaml \
  --namespace xagent-prod \
  --set replicaCount=3 \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="api.x-agent.dev" \
  --set autoscaling.enabled=true \
  --set autoscaling.maxReplicas=10 \
  --set persistence.enabled=true \
  --set persistence.size="100Gi" \
  --set secrets.enabled=true \
  --set secrets.create=false \
  --set-string secrets.existingSecretName=xagent-secrets
```

## Upgrades

### Update to new version

```bash
helm upgrade xagent ./deployment/helm \
  --values ./deployment/helm/values-production.yaml \
  --set image.tag="1.1.0"
```

### Rollback to previous version

```bash
helm rollback xagent 1
```

## Monitoring

### Check deployment status

```bash
kubectl get deployment -n xagent-prod
kubectl get pods -n xagent-prod
kubectl describe deployment xagent -n xagent-prod
```

### View logs

```bash
# Latest logs
kubectl logs deployment/xagent -n xagent-prod

# Follow logs
kubectl logs -f deployment/xagent -n xagent-prod

# Previous replica logs
kubectl logs deployment/xagent -n xagent-prod --previous
```

### Check health

```bash
# Port forward
kubectl port-forward svc/xagent 8000:80 -n xagent-prod

# Check health endpoint
curl http://localhost:8000/health
```

### View metrics

```bash
# Pod metrics
kubectl top pods -n xagent-prod

# Node metrics
kubectl top nodes
```

## Troubleshooting

### Pod not starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n xagent-prod

# Check logs
kubectl logs <pod-name> -n xagent-prod

# Check events
kubectl get events -n xagent-prod --sort-by='.lastTimestamp'
```

### Database connection issues

```bash
# Verify database URL secret
kubectl get secret xagent-secrets -n xagent-prod -o jsonpath='{.data.database-url}' | base64 -d

# Test connection from pod
kubectl exec -it <pod-name> -n xagent-prod -- python -c "import psycopg2; ..."
```

### Out of memory

Adjust resource limits:

```bash
helm upgrade xagent ./deployment/helm \
  --set resources.limits.memory="2Gi" \
  --set resources.requests.memory="512Mi"
```

### High CPU usage

Enable autoscaling or increase resource limits:

```bash
helm upgrade xagent ./deployment/helm \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=3
```

## Security

### Network Policies

Enable network policies for ingress/egress control:

```yaml
networkPolicy:
  enabled: true
```

### Pod Security Standards

Configured for restricted PSS:

```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
```

### Secret Management

Use external secret manager (Vault, AWS Secrets):

```yaml
secrets:
  externalSecrets:
    enabled: true
    backend: vault
    vaultServer: https://vault.example.com
```

## Backup and Restore

### Backup Helm release

```bash
helm get values xagent -n xagent-prod > xagent-values.yaml
helm get manifest xagent -n xagent-prod > xagent-manifest.yaml
```

### Restore from backup

```bash
helm install xagent ./deployment/helm \
  -f xagent-values.yaml \
  -n xagent-prod
```

## Uninstall

```bash
# Remove release
helm uninstall xagent -n xagent-prod

# Clean up namespace
kubectl delete namespace xagent-prod
```

## File Structure

```
deployment/helm/
├── Chart.yaml                 # Chart metadata
├── README.md                  # This file
├── values.yaml                # Default values
├── values-staging.yaml        # Staging overrides
├── values-production.yaml     # Production overrides
└── templates/
    ├── _helpers.tpl           # Template helpers
    ├── deployment.yaml        # Deployment template
    ├── service.yaml           # Service template
    ├── ingress.yaml           # Ingress template
    ├── configmap.yaml         # ConfigMap template
    ├── secret.yaml            # Secret template
    ├── hpa.yaml               # HPA template
    ├── pvc.yaml               # PVC template
    ├── pdb.yaml               # PDB template
    ├── serviceaccount.yaml    # ServiceAccount template
    ├── networkpolicy.yaml     # NetworkPolicy template
    └── NOTES.txt              # Post-install notes
```

## Support

- Documentation: https://x-agent.dev/docs/deployment
- Issues: https://github.com/x-agent/x-agent/issues
- Community: https://discord.gg/x-agent

## License

MIT
