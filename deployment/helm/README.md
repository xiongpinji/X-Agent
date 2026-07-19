# X-Agent Helm Chart

唯一权威的 Helm 部署入口(Phase 2 Wave A / P1-15 收敛后)。
原始 K8s 清单见 `deployment/k8s/`(与本 Chart 模板保持一致), 旧的
`deployment/kubernetes/` 第二套清单已于 2026-07-20 归档至
`archive/legacy_kubernetes_manifests_2026-07-20/`。

## 包含的模板

| 模板 | 内容 |
|---|---|
| `namespace.yaml` | Release 命名空间 |
| `serviceaccount.yaml` | `xagent` ServiceAccount(无 Role, 最小权限) |
| `configmap.yaml` / `secret.yaml` | 应用配置与密钥(`XAGENT_` 前缀, 对照 `backend/app/settings.py`) |
| `api-deployment.yaml` | API Deployment + Service + HPA |
| `worker-deployment.yaml` | Worker Deployment + HPA |
| `beat-deployment.yaml` | Beat Deployment(单副本) |
| `postgres.yaml` / `redis.yaml` / `qdrant.yaml` / `neo4j.yaml` | 集群内依赖(可关闭) |
| `backup-cronjob.yaml` | 定时备份 CronJob(P1-17) |
| `ingress.yaml` | Ingress + TLS |

## 数据库依赖: 两种模式

### 模式 A —— 集群内依赖(默认, 适合演示/中小规模)

`postgres/redis/qdrant/neo4j` 的 `enabled: true`(默认), Chart 会在集群内
部署单副本 Deployment + Service + PVC。

### 模式 B —— 外部托管依赖(商用生产建议)

将对应组件关闭, 并在 `external.*Host` 显式填写外部端点:

```yaml
postgres:
  enabled: false
redis:
  enabled: false
qdrant:
  enabled: false
neo4j:
  enabled: false

external:
  postgresHost: "my-pg.example.com"
  redisHost: "my-redis.example.com"
  qdrantHost: "my-qdrant.example.com"
  neo4jHost: "my-neo4j.example.com"
```

模板通过 `templates/_helpers.tpl` 解析主机名; 组件关闭且未提供外部端点时,
`helm template`/`helm install` 会因 `required` 校验**显式报错**(不静默降级)。

## 优雅停机(P1-16)

所有 Pod 模板均带:

- `terminationGracePeriodSeconds >= 60`(api 90 / worker 120 / beat 60 / 依赖 60)
- `preStop` 钩子 `sleep N`(api/worker 10s, 其余 5s), 等待 Endpoints 摘除传播后再 SIGTERM

可用各组件的 `terminationGracePeriodSeconds` / `preStopSleepSeconds` 覆盖。

## 定时备份(P1-17)

`backup.enabled: true` 时渲染 CronJob(默认每天 02:00):
脚本为 `deployment/backup/backup.sh`, 镜像由 `deployment/backup/Dockerfile` 构建:

```bash
docker build -t your-registry/xagent-backup:latest -f deployment/backup/Dockerfile .
```

备份内容: PostgreSQL(pg_dump custom) + Redis(RDB) + Qdrant(官方快照 API
`POST /collections/{name}/snapshots` 创建后下载), 可选 S3 上传(`backup.s3.*`)。

## 使用

```bash
# 渲染检查
helm template xagent deployment/helm -n xagent

# 生产部署
helm upgrade --install xagent deployment/helm \
  --namespace xagent --create-namespace \
  --values deployment/helm/values-production.yaml
```

注意: `values*.yaml` 中的 `secrets.*` 均为占位符, 生产必须覆盖为强随机值
(`jwtSecret`/`encryptionKey` 需 >=32 字符且含大写字母与数字, 否则后端拒绝启动)。
