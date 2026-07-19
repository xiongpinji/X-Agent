# 部署配置和环境设置指南

## 目录

1. [环境变量配置](#环境变量配置)
2. [GitHub Secrets设置](#github-secrets设置)
3. [AWS IAM角色配置](#aws-iam角色配置)
4. [Kubernetes部署](#kubernetes部署)
5. [Docker镜像配置](#docker镜像配置)
6. [监控和告警](#监控和告警)

## 环境变量配置

### 开发环境 (.env.development)

```bash
# 数据库
DATABASE_URL=postgresql://xagent:xagent@localhost:5432/xagent_dev
POSTGRES_USER=xagent
POSTGRES_PASSWORD=xagent
POSTGRES_DB=xagent_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant向量数据库
QDRANT_URL=http://localhost:6333

# LLM配置
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Langfuse追踪
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
LANGFUSE_HOST=https://cloud.langfuse.com

# 日志级别
LOG_LEVEL=DEBUG

# 应用配置
APP_ENV=development
DEBUG=true
```

### 测试环境 (.env.test)

```bash
# 数据库
DATABASE_URL=postgresql://xagent:xagent@localhost:5432/xagent_test
POSTGRES_USER=xagent
POSTGRES_PASSWORD=xagent
POSTGRES_DB=xagent_test

# Redis
REDIS_URL=redis://localhost:6379/1

# Qdrant
QDRANT_URL=http://localhost:6333

# 测试配置
LOG_LEVEL=WARNING
APP_ENV=test
DEBUG=false

# Mock服务
OPENAI_API_KEY=test-key
LANGFUSE_PUBLIC_KEY=test-key
```

### Staging环境 (.env.staging)

```bash
# 数据库
DATABASE_URL=postgresql://xagent:xagent@staging-db.example.com:5432/xagent_staging
POSTGRES_USER=xagent
POSTGRES_PASSWORD=${STAGING_DB_PASSWORD}

# Redis
REDIS_URL=redis://staging-redis.example.com:6379/0

# Qdrant
QDRANT_URL=http://staging-qdrant.example.com:6333

# LLM配置
OPENAI_API_KEY=${STAGING_OPENAI_API_KEY}
OPENAI_MODEL=gpt-4

# Langfuse
LANGFUSE_PUBLIC_KEY=${STAGING_LANGFUSE_PUBLIC_KEY}
LANGFUSE_SECRET_KEY=${STAGING_LANGFUSE_SECRET_KEY}

# 应用配置
LOG_LEVEL=INFO
APP_ENV=staging
DEBUG=false

# 监控
SENTRY_DSN=${STAGING_SENTRY_DSN}
```

### Production环境 (.env.production)

```bash
# 数据库
DATABASE_URL=postgresql://xagent:${PROD_DB_PASSWORD}@prod-db.example.com:5432/xagent_prod
POSTGRES_USER=xagent

# Redis
REDIS_URL=redis://:${PROD_REDIS_PASSWORD}@prod-redis.example.com:6379/0

# Qdrant
QDRANT_URL=http://prod-qdrant.example.com:6333

# LLM配置
OPENAI_API_KEY=${PROD_OPENAI_API_KEY}
OPENAI_MODEL=gpt-4

# Langfuse
LANGFUSE_PUBLIC_KEY=${PROD_LANGFUSE_PUBLIC_KEY}
LANGFUSE_SECRET_KEY=${PROD_LANGFUSE_SECRET_KEY}

# 应用配置
LOG_LEVEL=WARNING
APP_ENV=production
DEBUG=false

# 监控和告警
SENTRY_DSN=${PROD_SENTRY_DSN}
DATADOG_API_KEY=${PROD_DATADOG_API_KEY}

# 安全
CORS_ORIGINS=https://xagent.example.com
ALLOWED_HOSTS=xagent.example.com
```

## GitHub Secrets设置

### 设置步骤

1. 进入仓库 > Settings > Secrets and variables > Actions
2. 点击 "New repository secret"
3. 添加以下Secrets:

### 必需的Secrets

| Secret名称 | 说明 | 示例值 |
|-----------|------|-------|
| `AWS_ROLE_TO_ASSUME_STAGING` | Staging AWS IAM角色ARN | `arn:aws:iam::123456789:role/xagent-staging-deploy` |
| `AWS_ROLE_TO_ASSUME_PRODUCTION` | Production AWS IAM角色ARN | `arn:aws:iam::123456789:role/xagent-prod-deploy` |
| `STAGING_DEPLOY_KEY` | Staging部署SSH密钥 | (SSH私钥) |
| `PRODUCTION_DEPLOY_KEY` | Production部署SSH密钥 | (SSH私钥) |
| `CODECOV_TOKEN` | Codecov上传令牌 | (可选) |
| `STAGING_OPENAI_API_KEY` | Staging OpenAI API密钥 | `sk-...` |
| `STAGING_LANGFUSE_PUBLIC_KEY` | Staging Langfuse公钥 | `pk_...` |
| `STAGING_LANGFUSE_SECRET_KEY` | Staging Langfuse密钥 | `sk_...` |
| `PROD_OPENAI_API_KEY` | Production OpenAI API密钥 | `sk_...` |
| `PROD_LANGFUSE_PUBLIC_KEY` | Production Langfuse公钥 | `pk_...` |
| `PROD_LANGFUSE_SECRET_KEY` | Production Langfuse密钥 | `sk_...` |
| `PROD_DB_PASSWORD` | Production数据库密码 | (强密码) |
| `PROD_REDIS_PASSWORD` | Production Redis密码 | (强密码) |
| `STAGING_DB_PASSWORD` | Staging数据库密码 | (强密码) |
| `STAGING_SENTRY_DSN` | Staging Sentry DSN | `https://...@sentry.io/...` |
| `PROD_SENTRY_DSN` | Production Sentry DSN | `https://...@sentry.io/...` |
| `PROD_DATADOG_API_KEY` | Production Datadog API密钥 | (API密钥) |

### 环境Secrets

为不同环境配置特定的Secrets:

**Staging环境**:
1. Settings > Environments > New environment > "staging"
2. 添加环境特定的Secrets:
   - `STAGING_DEPLOY_KEY`
   - `STAGING_OPENAI_API_KEY`
   - 等等

**Production环境**:
1. Settings > Environments > New environment > "production"
2. 添加环境特定的Secrets
3. 配置部署审批人员

## AWS IAM角色配置

### Staging IAM角色策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters"
      ],
      "Resource": "arn:aws:eks:us-east-1:123456789:cluster/xagent-staging"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::123456789:role/xagent-staging-deploy"
    }
  ]
}
```

### Production IAM角色策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters"
      ],
      "Resource": "arn:aws:eks:us-east-1:123456789:cluster/xagent-production"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:AssumeRole"
      ],
      "Resource": "arn:aws:iam::123456789:role/xagent-prod-deploy"
    },
    {
      "Effect": "Allow",
      "Action": [
        "autoscaling:UpdateAutoScalingGroup",
        "autoscaling:DescribeAutoScalingGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

## Kubernetes部署

### Staging部署配置 (k8s/staging/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-api
  namespace: staging
  labels:
    app: xagent-api
    environment: staging
spec:
  replicas: 2
  selector:
    matchLabels:
      app: xagent-api
  template:
    metadata:
      labels:
        app: xagent-api
        environment: staging
    spec:
      containers:
      - name: xagent-api
        image: ghcr.io/your-org/xagent:develop
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: APP_ENV
          value: "staging"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: redis-url
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: xagent-api
  namespace: staging
spec:
  selector:
    app: xagent-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Production部署配置 (k8s/production/deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xagent-api
  namespace: production
  labels:
    app: xagent-api
    environment: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: xagent-api
  template:
    metadata:
      labels:
        app: xagent-api
        environment: production
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - xagent-api
              topologyKey: kubernetes.io/hostname
      containers:
      - name: xagent-api
        image: ghcr.io/your-org/xagent:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: APP_ENV
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: xagent-secrets
              key: redis-url
        resources:
          requests:
            cpu: 1000m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          failureThreshold: 2
---
apiVersion: v1
kind: Service
metadata:
  name: xagent-api
  namespace: production
spec:
  selector:
    app: xagent-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: xagent-api-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: xagent-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Docker镜像配置

### 多阶段构建 (Dockerfile)

```dockerfile
# 构建阶段
FROM python:3.12-slim as builder

WORKDIR /build

COPY pyproject.toml ./
RUN pip install --user --no-cache-dir -e ".[prod]"

# 运行阶段
FROM python:3.12-slim

WORKDIR /app

# 复制Python依赖
COPY --from=builder /root/.local /root/.local

# 设置PATH
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY backend ./backend

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (docker-compose.yml)

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://xagent:xagent@postgres:5432/xagent
      REDIS_URL: redis://redis:6379
      QDRANT_URL: http://qdrant:6333
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend

  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: xagent
      POSTGRES_PASSWORD: xagent
      POSTGRES_DB: xagent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U xagent"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

## 监控和告警

### Prometheus配置 (prometheus.yml)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'xagent-api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Grafana仪表板

关键指标:
- 请求延迟 (p50, p95, p99)
- 错误率
- 吞吐量 (RPS)
- 数据库连接池使用率
- Redis命中率
- CPU和内存使用率

### 告警规则 (alerts.yml)

```yaml
groups:
  - name: xagent
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"

      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        annotations:
          summary: "High request latency detected"

      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total[15m]) > 0.1
        for: 5m
        annotations:
          summary: "Pod is crash looping"
```

## 部署检查清单

部署前检查:

- [ ] 所有测试通过
- [ ] 代码审查完成
- [ ] 安全扫描通过
- [ ] 覆盖率达到目标
- [ ] 数据库迁移已准备
- [ ] 环境变量已配置
- [ ] Secrets已设置
- [ ] 监控告警已配置
- [ ] 回滚计划已准备
- [ ] 部署窗口已确认

## 故障排查

### 部署失败

1. 检查GitHub Actions日志
2. 验证AWS凭证
3. 检查Kubernetes集群状态
4. 查看Pod日志

### 应用崩溃

1. 检查Pod日志: `kubectl logs -f deployment/xagent-api -n production`
2. 检查事件: `kubectl describe pod <pod-name> -n production`
3. 检查资源限制
4. 查看应用日志

### 性能问题

1. 检查数据库连接
2. 监控Redis使用率
3. 检查CPU和内存使用
4. 分析慢查询日志
