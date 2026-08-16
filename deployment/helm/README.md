# X-Agent Helm Chart

唯一权威的部署入口(Phase 2 Wave A / P1-15 收敛后)。
旧的 `deployment/kubernetes/` 第二套清单已于 2026-07-20 归档至
`archive/legacy_kubernetes_manifests_2026-07-20/`; 原始裸清单
`deployment/k8s/`(仅参考用、无执行路径)已于 2026-08-05 归档至
`archive/legacy_k8s_manifests_2026-08/`, 本 Chart 自此为唯一部署资产。

## 包含的模板

| 模板 | 内容 |
|---|---|
| `namespace.yaml` | Release 命名空间 |
| `serviceaccount.yaml` | `xagent` ServiceAccount(无 Role, 最小权限) |
| `configmap.yaml` / `secret.yaml` | 应用配置；Chart 不生成 Secret，只引用操作员预置 Secret |
| `migration-job.yaml` | 带已验证备份编号的 Alembic 前向迁移 Job |
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

### 模式 B —— 外部托管依赖(商用生产必须)

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

## 生产必填项

`values-production.yaml` 故意保留空值，未完成以下项目时 Helm 必须拒绝渲染：

- 经审计的应用镜像仓库和不可变 SHA tag；
- 备份工具镜像仓库和同一 SHA tag；
- 外部 PostgreSQL、Redis、Qdrant 端点；
- Ingress 生产域名；
- 操作员预置的 Kubernetes Secret 名；
- 可被 API 和 worker 共享的 ReadWriteMany 工件 PVC；
- 本次迁移前已验证可恢复备份的编号 `migration.verifiedBackupId`。

预置 Secret 至少包含：

```text
DB_USER
DB_PASSWORD
REDIS_PASSWORD
QDRANT_API_KEY
NEO4J_PASSWORD
XAGENT_JWT_SECRET
XAGENT_ENCRYPTION_KEY
XAGENT_AUDIT_HMAC_SECRET
XAGENT_GITHUB_WEBHOOK_SECRET
```

Secret 必须由密钥管理器或受控的集群流程创建；不得用 `--set`
传入密钥，Chart 也不会渲染 Secret 对象。

### 首版实时流伸缩边界

当前 Console/协作 SSE 事件总线为有界的进程内实现，还没有 Redis Streams
或等价的跨进程后端。因此 `values-production.yaml` 强制 `api.replicas=1`、
`api.workers=1` 并关闭 API HPA；这是防止用户连接假绿或丢协作事件的正确性
门禁，不是高可用声明。在分布式事件总线与跨 Pod 重放验收完成前，
不得提高这三个值。

仍使用文件的少量运行态和 run artifacts 共用操作员提供的 RWX PVC，
挂载到 `/var/lib/xagent`；多实例主数据（用户、工作流、聊天、记忆、trace、
run、计费、审计）必须使用 PostgreSQL 后端。

## 迁移顺序与恢复边界

Helm 先运行 revision-scoped migration Job，API、worker、beat 的 init container
再用 `check_heads=True` 等待数据库达到单一 Alembic head。生产迁移缺少
`XAGENT_PRE_MIGRATION_BACKUP_ID` 时会在连接数据库前拒绝执行。

`0002_commercial_schema` 不支持破坏性 downgrade。部署失败不会自动回滚
数据库；代码回滚前必须先评估 schema 兼容性。确需恢复时，只能使用
`deployment/scripts/restore-database.sh` 对已校验备份执行显式确认的恢复。

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

# 生产渲染示例（值必须来自受控环境）
helm upgrade --install xagent deployment/helm \
  --namespace xagent --create-namespace \
  --values deployment/helm/values-production.yaml \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.tag="sha-$GIT_SHA" \
  --set-string backup.image.repository="$BACKUP_IMAGE_REPOSITORY" \
  --set-string backup.image.tag="sha-$GIT_SHA" \
  --set-string secrets.existingSecret="$XAGENT_K8S_SECRET_NAME" \
  --set-string artifacts.existingClaim="$XAGENT_ARTIFACTS_PVC" \
  --set-string migration.verifiedBackupId="$XAGENT_PRE_MIGRATION_BACKUP_ID" \
  --set-string external.postgresHost="$PRODUCTION_POSTGRES_HOST" \
  --set-string external.redisHost="$PRODUCTION_REDIS_HOST" \
  --set-string external.qdrantHost="$PRODUCTION_QDRANT_HOST" \
  --set-string ingress.hosts[0].host="$PRODUCTION_API_HOST" \
  --wait --wait-for-jobs
```

注意：上述命令不包含密钥值。JWT、加密密钥和审计 HMAC 密钥只能来自
`secrets.existingSecret` 引用的预置 Secret。
