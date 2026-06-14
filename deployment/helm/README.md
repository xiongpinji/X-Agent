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
helm install xagent ./deployment/helm \
  --set-string secrets.databaseUrl="postgresql://user:pass@postgres:5432/xagent" \
  --set-string secrets.apiKey="dev-api-key-change-me"
```

### Staging

```bash
helm install xagent ./deployment/helm -f ./deployment/helm/values-staging.yaml \
  --namespace xagent-staging --create-namespace \
  --set-string secrets.databaseUrl="postgresql://user:pass@postgres-staging:5432/xagent" \
  --set-string secrets.apiKey="staging-api-key"
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
helm install xagent ./deployment/helm -f ./deployment/helm/values-production.yaml \
  --namespace xagent-prod --create-namespace \
  --set replicaCount=3 \
  --set-string secrets.databaseUrl="postgresql://user:pass@postgres-prod:5432/xagent_prod" \
  --set-string secrets.apiKey="<strong-production-key>" \
  --set-string secrets.langfusePublicKey="<langfuse-key>" \
  --set-string secrets.langfuseSecretKey="<langfuse-secret>"
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
helm install xagent ./deployment/helm \
  --set-string secrets.databaseUrl="postgresql://user:password@host:5432/dbname"
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
    metrics_path: /metrics
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
helm install xagent ./deployment/helm \
  --set-string secrets.langfusePublicKey="pk-prod-xxx" \
  --set-string secrets.langfuseSecretKey="sk-prod-xxx"
```

## Deployment Examples

### Minimal Development Deployment

```bash
helm install xagent ./deployment/helm \
  --namespace xagent-dev \
  --create-namespace \
  --set-string secrets.databaseUrl="postgresql://localhost:5432/xagent" \
  --set-string secrets.apiKey="dev-key"
```

### High-Availability Production

```bash
helm install xagent ./deployment/helm -f ./deployment/helm/values-production.yaml \
  --namespace xagent-prod \
  --create-namespace \
  --set replicaCount=3 \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="api.x-agent.dev" \
  --set autoscaling.enabled=true \
  --set autoscaling.maxReplicas=10 \
  --set persistence.enabled=true \
  --set persistence.size="100Gi" \
  --set-string secrets.databaseUrl="$DB_URL" \
  --set-string secrets.apiKey="$API_KEY"
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
